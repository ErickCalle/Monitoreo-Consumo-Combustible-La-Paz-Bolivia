// Power-gate control (LED+OLED rail, microSD rail) and the deep-sleep
// transition used whenever the CAN bus goes quiet ("sin contacto"). Rail 1
// (ESP32-S3 + SN65HVD230) is wired straight to the OBD2 12V and is never
// switched -- the SN65 has to stay powered so the very next wake can ping
// the bus again.
#include <Arduino.h>
#include <WiFi.h>
#include "driver/gpio.h"
#include "esp_sleep.h"
#include "config.h"
#include "types.h"
#include "sd_logger.h"
#include "power_sleep.h"

void powerGateInit() {
  // Release any hold left from the deep sleep that brought us here --
  // gpio_hold_en() latches the pin until explicitly disabled, even across
  // the reset that follows deep sleep, so this must run before pinMode()
  // can take effect again.
  gpio_hold_dis((gpio_num_t)PIN_PWR_LED_OLED);
  gpio_hold_dis((gpio_num_t)PIN_PWR_SD);
  pinMode(PIN_PWR_LED_OLED, OUTPUT);
  pinMode(PIN_PWR_SD, OUTPUT);
  powerGateSet(false);
}

void powerGateSet(bool on) {
  digitalWrite(PIN_PWR_LED_OLED, on ? HIGH : LOW);
  digitalWrite(PIN_PWR_SD, on ? HIGH : LOW);
}

void enterDeepSleepUntilContact() {
  Serial.println("Sin contacto -- apagando perifericos y durmiendo.");
  Serial.flush();

  sdLoggerShutdown(); // close any open file cleanly before cutting its power
  WiFi.mode(WIFI_OFF); // clean radio shutdown before sleep

  powerGateSet(false);
  gpio_hold_en((gpio_num_t)PIN_PWR_LED_OLED);
  gpio_hold_en((gpio_num_t)PIN_PWR_SD);
  gpio_deep_sleep_hold_en(); // required for the per-pin holds above to survive deep sleep

  esp_sleep_enable_timer_wakeup(DEEP_SLEEP_WAKE_INTERVAL_US);
  esp_deep_sleep_start();
  // Never reached: esp_deep_sleep_start() does not return. Waking runs
  // setup() again from the top, as if the board had just powered on.
}
