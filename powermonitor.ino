// powercounter.ino
// Counts 1 Wh/blink pulses from a mains meter LED using the onboard APDS9960
// and exposes total energy (Wh) and current power (mW) over BLE.
//
// BLE characteristics
//   ENERGY_UUID   uint32  Wh   read + notify
//   POWER_UUID    uint32  mW   read + notify  (divide by 1000 for W, 1 000 000 for kW)
//   INTERVAL_UUID uint16  s    read + write   (notification interval, default 10 s)

#include <ArduinoBLE.h>
#include <Arduino_APDS9960.h>

// ── BLE UUIDs ──────────────────────────────────────────────────────────────
static const char* SERVICE_UUID  = "12340000-0000-1000-8000-00805F9B34FB";
static const char* ENERGY_UUID   = "12340001-0000-1000-8000-00805F9B34FB";
static const char* POWER_UUID    = "12340002-0000-1000-8000-00805F9B34FB";
static const char* INTERVAL_UUID = "12340003-0000-1000-8000-00805F9B34FB";

// ── BLE objects ────────────────────────────────────────────────────────────
BLEService                     meterService(SERVICE_UUID);
BLEUnsignedIntCharacteristic   energyChar(ENERGY_UUID,   BLERead | BLENotify);
BLEUnsignedIntCharacteristic   powerChar(POWER_UUID,     BLERead | BLENotify);
BLEUnsignedShortCharacteristic intervalChar(INTERVAL_UUID, BLERead | BLEWrite);

// ── Blink tracking ─────────────────────────────────────────────────────────
uint32_t      totalWh      = 0;
unsigned long lastBlinkMs  = 0;   // millis() of the most recent blink
unsigned long prevBlinkMs  = 0;   // millis() of the blink before that
bool          aboveThresh  = false;

// ── Light sensor config ────────────────────────────────────────────────────
int baseline  = 0;
int threshold = 0;

// Minimum milliseconds between two counted blinks (debounce).
// At 10 kW load each blink is 360 ms apart, so 200 ms is a safe floor.
static const unsigned long DEBOUNCE_MS = 200;

// ── Notification interval ──────────────────────────────────────────────────
uint16_t      notifyIntervalSec = 10;
unsigned long lastNotifyMs      = 0;

// ── Forward declarations ───────────────────────────────────────────────────
void     calibrate();
void     detectBlink(int c);
uint32_t currentPowerMW();
void     sendNotification();

// ──────────────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  while (!Serial && millis() < 3000) {}   // wait for serial monitor (optional)

  // APDS9960 -----------------------------------------------------------------
  if (!APDS.begin()) {
    Serial.println("ERROR: APDS9960 init failed");
    while (true) {}
  }
  calibrate();

  // BLE ----------------------------------------------------------------------
  if (!BLE.begin()) {
    Serial.println("ERROR: BLE init failed");
    while (true) {}
  }

  BLE.setLocalName("PowerCounter");
  BLE.setAdvertisedService(meterService);

  meterService.addCharacteristic(energyChar);
  meterService.addCharacteristic(powerChar);
  meterService.addCharacteristic(intervalChar);
  BLE.addService(meterService);

  energyChar.writeValue((uint32_t)0);
  powerChar.writeValue((uint32_t)0);
  intervalChar.writeValue(notifyIntervalSec);

  BLE.advertise();
  Serial.println("PowerCounter ready — advertising over BLE");
}

void loop() {
  BLE.poll();

  // Accept interval updates written by a connected client
  if (intervalChar.written()) {
    notifyIntervalSec = intervalChar.value();
    if (notifyIntervalSec < 1) notifyIntervalSec = 1;   // sanity floor
    Serial.print("Notify interval → ");
    Serial.print(notifyIntervalSec);
    Serial.println(" s");
  }

  // Poll the light sensor
  if (APDS.colorAvailable()) {
    int r, g, b, c;
    APDS.readColor(r, g, b, c);
    detectBlink(c);
  }

  // Periodic BLE notification
  unsigned long now = millis();
  if (now - lastNotifyMs >= (unsigned long)notifyIntervalSec * 1000UL) {
    lastNotifyMs = now;
    sendNotification();
  }
}

// ── Calibration ────────────────────────────────────────────────────────────
// Averages 30 light readings taken in ambient conditions (no blink present).
// Threshold = baseline + 20 %, minimum +30 counts above baseline.
// Run this once at startup before the meter LED can blink.
void calibrate() {
  Serial.println("Calibrating light baseline — keep sensor away from meter LED…");
  long   sum     = 0;
  const int SAMPLES = 30;
  for (int i = 0; i < SAMPLES; i++) {
    while (!APDS.colorAvailable()) delay(5);
    int r, g, b, c;
    APDS.readColor(r, g, b, c);
    sum += c;
    delay(30);
  }
  baseline  = (int)(sum / SAMPLES);
  threshold = baseline + max((int)(baseline * 0.20f), 30);
  Serial.print("Baseline=");  Serial.print(baseline);
  Serial.print("  Threshold="); Serial.println(threshold);
}

// ── Blink detection ────────────────────────────────────────────────────────
// Detects a rising edge: clear channel crosses threshold after debounce time.
// One crossing = one Wh.
void detectBlink(int c) {
  unsigned long now = millis();

  if (!aboveThresh && c > threshold) {
    aboveThresh = true;
    // Ignore if within debounce window of the previous blink
    if (lastBlinkMs == 0 || (now - lastBlinkMs) >= DEBOUNCE_MS) {
      prevBlinkMs  = lastBlinkMs;
      lastBlinkMs  = now;
      totalWh++;
      Serial.print("Blink #"); Serial.print(totalWh);
      Serial.print("  c=");    Serial.print(c);
      Serial.print("  interval=");
      if (prevBlinkMs > 0) { Serial.print(lastBlinkMs - prevBlinkMs); Serial.println(" ms"); }
      else Serial.println("(first)");
    }
  } else if (aboveThresh && c <= threshold) {
    aboveThresh = false;  // trailing edge — ready for next blink
  }
}

// ── Power calculation ──────────────────────────────────────────────────────
// Uses the time between the last two blinks.
// Returns 0 if fewer than 2 blinks recorded, or if the reading is stale
// (no blink for more than 2× the last interval — load has dropped).
uint32_t currentPowerMW() {
  if (lastBlinkMs == 0 || prevBlinkMs == 0) return 0;

  unsigned long interval = lastBlinkMs - prevBlinkMs;  // ms between last two blinks
  if (interval == 0) return 0;

  // 1 Wh per blink  →  Power [W] = 3 600 000 ms·h⁻¹ / interval [ms]
  // Return milliwatts (×1000) using 64-bit arithmetic to avoid overflow
  uint32_t mw = (uint32_t)(3600000000ULL / (unsigned long long)interval);

  // Staleness guard: if silent for > 2 × last interval, consumption has fallen
  if ((millis() - lastBlinkMs) > interval * 2UL) return 0;

  return mw;
}

// ── BLE notification ───────────────────────────────────────────────────────
void sendNotification() {
  uint32_t mw = currentPowerMW();
  energyChar.writeValue(totalWh);
  powerChar.writeValue(mw);

  Serial.print("Notify → Wh="); Serial.print(totalWh);
  Serial.print("  W=");          Serial.print(mw / 1000.0, 2);
  Serial.print("  kW=");         Serial.println(mw / 1000000.0, 4);
}
