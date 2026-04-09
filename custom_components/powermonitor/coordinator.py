from __future__ import annotations

import asyncio
import logging
import struct
from dataclasses import dataclass

from bleak import BleakClient
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak_retry_connector import establish_connection

from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, ENERGY_UUID, MAXLIGHT_UUID, POWER_UUID, THRESHOLD_UUID

_LOGGER = logging.getLogger(__name__)


@dataclass
class PowerMonitorData:
    energy_wh: int = 0
    power_w: float = 0.0
    threshold: int = 0
    maxlight: int = 0
    available: bool = False


class PowerMonitorCoordinator(DataUpdateCoordinator[PowerMonitorData]):
    def __init__(self, hass: HomeAssistant, address: str) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN)
        self.address = address
        self._data = PowerMonitorData()
        self._client: BleakClient | None = None
        self._connection_task: asyncio.Task | None = None
        self._disconnect_event: asyncio.Event | None = None

    async def async_start(self) -> None:
        self._connection_task = self.hass.async_create_background_task(
            self._connection_loop(), "powermonitor_ble"
        )

    async def async_stop(self) -> None:
        if self._connection_task:
            self._connection_task.cancel()
            try:
                await self._connection_task
            except asyncio.CancelledError:
                pass
        if self._client and self._client.is_connected:
            await self._client.disconnect()

    async def async_set_threshold(self, value: int) -> None:
        """Write a new threshold value to the device."""
        if self._client is None or not self._client.is_connected:
            raise RuntimeError("Not connected to PowerMonitor")
        data = struct.pack("<H", max(0, min(value, 65535)))
        await self._client.write_gatt_char(THRESHOLD_UUID, data, response=True)
        self._data.threshold = value
        self.async_set_updated_data(self._data)

    async def _connection_loop(self) -> None:
        while True:
            try:
                await self._connect_and_listen()
            except asyncio.CancelledError:
                return
            except Exception as err:
                _LOGGER.warning("BLE connection error, retrying in 30s: %s", err)
                self._data.available = False
                self.async_set_updated_data(self._data)
                await asyncio.sleep(30)

    async def _connect_and_listen(self) -> None:
        ble_device = async_ble_device_from_address(self.hass, self.address, connectable=True)
        if ble_device is None:
            _LOGGER.debug("Device %s not in range, waiting 30s", self.address)
            await asyncio.sleep(30)
            return

        _LOGGER.debug("Connecting to PowerMonitor at %s", self.address)
        client = await establish_connection(
            BleakClient,
            ble_device,
            self.address,
            disconnected_callback=self._on_disconnect,
        )
        self._client = client

        try:
            energy_bytes = await client.read_gatt_char(ENERGY_UUID)
            self._data.energy_wh = struct.unpack("<I", bytes(energy_bytes))[0]

            power_bytes = await client.read_gatt_char(POWER_UUID)
            self._data.power_w = struct.unpack("<I", bytes(power_bytes))[0] / 1000.0

            threshold_bytes = await client.read_gatt_char(THRESHOLD_UUID)
            self._data.threshold = struct.unpack("<H", bytes(threshold_bytes))[0]

            maxlight_bytes = await client.read_gatt_char(MAXLIGHT_UUID)
            self._data.maxlight = struct.unpack("<H", bytes(maxlight_bytes))[0]

            self._data.available = True
            self.async_set_updated_data(self._data)

            await client.start_notify(ENERGY_UUID, self._on_energy)
            await client.start_notify(POWER_UUID, self._on_power)
            await client.start_notify(MAXLIGHT_UUID, self._on_maxlight)

            _LOGGER.info("Connected to PowerMonitor at %s", self.address)

            self._disconnect_event = asyncio.Event()
            await self._disconnect_event.wait()

        finally:
            self._client = None
            self._disconnect_event = None
            if client.is_connected:
                await client.disconnect()

    def _on_disconnect(self, client: BleakClient) -> None:
        _LOGGER.warning("Disconnected from PowerMonitor at %s", self.address)
        self._data.available = False
        self.async_set_updated_data(self._data)
        if self._disconnect_event is not None:
            self._disconnect_event.set()

    def _on_energy(self, _char: BleakGATTCharacteristic, data: bytearray) -> None:
        self._data.energy_wh = struct.unpack("<I", bytes(data))[0]
        self.async_set_updated_data(self._data)

    def _on_power(self, _char: BleakGATTCharacteristic, data: bytearray) -> None:
        self._data.power_w = struct.unpack("<I", bytes(data))[0] / 1000.0
        self.async_set_updated_data(self._data)

    def _on_maxlight(self, _char: BleakGATTCharacteristic, data: bytearray) -> None:
        self._data.maxlight = struct.unpack("<H", bytes(data))[0]
        self.async_set_updated_data(self._data)

    async def _async_update_data(self) -> PowerMonitorData:
        return self._data
