#include <Arduino.h>
#include "config.h"
#include "types.h"
#include "status_leds.h"

void statusLedsInit() {
  pinMode(PIN_LED_CAN, OUTPUT);
  pinMode(PIN_LED_SD, OUTPUT);
  pinMode(PIN_LED_SERVER, OUTPUT);
  pinMode(PIN_LED_ERROR, OUTPUT);
  digitalWrite(PIN_LED_CAN, LOW);
  digitalWrite(PIN_LED_SD, LOW);
  digitalWrite(PIN_LED_SERVER, LOW);
  digitalWrite(PIN_LED_ERROR, LOW);
}

// Stateless blink-code pattern: `blinks` short pulses then a pause,
// repeating every CYCLE_MS. Driven purely from millis(), so it needs
// no extra state and can't drift/desync.
static void serviceErrorLed() {
  ErrorCode code = g_systemStatus.error_code;
  if (code == ErrorCode::NONE) {
    digitalWrite(PIN_LED_ERROR, LOW);
    return;
  }
  const uint32_t SLOT_MS = 300;   // 150 ms on + 150 ms off per blink
  const uint32_t CYCLE_MS = 2200; // full pattern period including the pause
  uint8_t blinks = (uint8_t)code;

  uint32_t t = millis() % CYCLE_MS;
  uint32_t blinkWindow = blinks * SLOT_MS;
  if (t < blinkWindow) {
    bool on = (t % SLOT_MS) < (SLOT_MS / 2);
    digitalWrite(PIN_LED_ERROR, on ? HIGH : LOW);
  } else {
    digitalWrite(PIN_LED_ERROR, LOW);
  }
}

void statusLedsTask(void *pvParameters) {
  (void)pvParameters;
  for (;;) {
    // No per-LED idle logic needed anymore: with "sin contacto" the whole
    // LED rail loses power at the MOSFET (power_sleep.cpp) instead.
    digitalWrite(PIN_LED_CAN, g_systemStatus.can_ok ? HIGH : LOW);

    int32_t sdRemaining = (int32_t)(g_systemStatus.sd_activity_until_ms - millis());
    digitalWrite(PIN_LED_SD, sdRemaining > 0 ? HIGH : LOW);

    digitalWrite(PIN_LED_SERVER, g_systemStatus.server_active ? HIGH : LOW);

    serviceErrorLed();

    vTaskDelay(pdMS_TO_TICKS(50));
  }
}
