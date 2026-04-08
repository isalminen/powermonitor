#!/usr/bin/env python3
"""
client.py — BLE client for the PowerMonitor Arduino sketch.

Connects to the Nano 33 BLE Sense, reads current values immediately,
then listens for periodic notifications.

Usage:
    pip install bleak
    python client.py [--interval SECONDS]
"""

import asyncio
import struct
import argparse
from datetime import datetime
from typing import Optional
from bleak import BleakClient, BleakScanner

DEVICE_NAME   = "PowerMonitor"
ENERGY_UUID   = "12340001-0000-1000-8000-00805f9b34fb"  # uint32, Wh
POWER_UUID    = "12340002-0000-1000-8000-00805f9b34fb"  # uint32, mW
INTERVAL_UUID = "12340003-0000-1000-8000-00805f9b34fb"  # uint16, seconds


def decode_uint32(data: bytearray) -> int:
    return struct.unpack("<I", data)[0]   # little-endian uint32


def decode_uint16(data: bytearray) -> int:
    return struct.unpack("<H", data)[0]


def fmt_energy(wh: int) -> str:
    return f"{wh} Wh  ({wh / 1000:.3f} kWh)"


def fmt_power(mw: int) -> str:
    w  = mw / 1000.0
    kw = mw / 1_000_000.0
    return f"{w:.1f} W  ({kw:.4f} kW)"


def on_energy(sender, data: bytearray):
    wh = decode_uint32(data)
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] Energy  {fmt_energy(wh)}")


def on_power(sender, data: bytearray):
    mw = decode_uint32(data)
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] Power   {fmt_power(mw)}")


async def main(notify_interval: int | None):
    print(f"Scanning for '{DEVICE_NAME}'…")
    device = await BleakScanner.find_device_by_name(DEVICE_NAME, timeout=15)
    if device is None:
        print("Device not found. Make sure the Nano is powered and advertising.")
        return

    async with BleakClient(device) as client:
        print(f"Connected: {device.name}  ({device.address})\n")

        # Optionally update the notification interval on the device
        if notify_interval is not None:
            interval_bytes = struct.pack("<H", notify_interval)
            await client.write_gatt_char(INTERVAL_UUID, interval_bytes, response=True)
            print(f"Notification interval set to {notify_interval} s")

        # Read the current interval stored on the device
        raw = await client.read_gatt_char(INTERVAL_UUID)
        print(f"Device notify interval: {decode_uint16(raw)} s")

        # Read current values immediately (don't wait for first notification)
        energy_raw = await client.read_gatt_char(ENERGY_UUID)
        power_raw  = await client.read_gatt_char(POWER_UUID)
        print(f"Current  energy : {fmt_energy(decode_uint32(energy_raw))}")
        print(f"Current  power  : {fmt_power(decode_uint32(power_raw))}")
        print("\nListening for notifications (Ctrl-C to stop)…\n")

        # Subscribe to notifications
        await client.start_notify(ENERGY_UUID, on_energy)
        await client.start_notify(POWER_UUID, on_power)

        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            pass

        await client.stop_notify(ENERGY_UUID)
        await client.stop_notify(POWER_UUID)
        print("\nDisconnected.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PowerMonitor BLE client")
    parser.add_argument(
        "--interval", type=int, default=None, metavar="SECONDS",
        help="Set notification interval on the device (1–65535 s). "
             "Omit to keep the current device setting."
    )
    args = parser.parse_args()
    asyncio.run(main(args.interval))
