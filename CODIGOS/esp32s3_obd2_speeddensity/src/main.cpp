// ESP32-S3 N16R8 -- OBD2 (TWAI/SN65HVD230) speed-density fuel consumption
// meter with OLED (I2C), microSD CSV logging (SPI) and a local WiFi
// dashboard (ESPAsyncWebServer). See README.md for wiring + calibration.
//
// Task/core layout:
//   core 0: TWAI/OBD2 polling + fuel calc (highest priority),
//           WiFi/AsyncTCP stack + WebSocket push task
//   core 1: OLED refresh, microSD logger, status LED driver
//
// Power: rail 1 (ESP32-S3 + SN65HVD230) is wired straight to the OBD2's
// constant 12V and is never switched. Rail 2 (LEDs+OLED, microSD) is
// gated by two MOSFETs the chip drives itself. setup() pings the CAN bus
// before touching rail 2 at all; no answer means "sin contacto" and the
// board goes straight to deep sleep instead of finishing boot -- see
// power_sleep.cpp.
#include <Arduino.h>
#include "config.h"
#include "types.h"
#include "can_obd2.h"
#include "display_oled.h"
#include "sd_logger.h"
#include "web_server.h"
#include "status_leds.h"
#include "power_sleep.h"

VehicleData       g_vehicleData;
SystemStatus      g_systemStatus;
SemaphoreHandle_t g_dataMutex = nullptr;
SemaphoreHandle_t g_sdMutex   = nullptr;

// Only the most recent error is reflected on the LED; the running
// Serial log has the full history for bench debugging.
void systemReportError(ErrorCode code) {
  g_systemStatus.error_code = code;
  Serial.printf("[ERROR] code=%d\n", (int)code);
}

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println("\nESP32-S3 OBD2 Speed-Density - iniciando");

  g_dataMutex = xSemaphoreCreateMutex();
  g_sdMutex   = xSemaphoreCreateMutex();

  // Rail 2 (LEDs+OLED, microSD) stays off and TWAI is the only thing
  // brought up until contact is confirmed -- this runs identically on a
  // cold boot and on every timer wake from deep sleep. A TWAI driver
  // failure is a real hardware/config fault, not "sin contacto" -- that
  // case falls through to a full boot below so the error LED/log/web panel
  // are still reachable for diagnosis instead of sleeping forever silently.
  powerGateInit();
  bool canOk = canObd2Init();

#if FORCE_AWAKE_FOR_BENCH_TEST
  Serial.println("FORCE_AWAKE_FOR_BENCH_TEST=1 -- omitiendo chequeo de contacto (banco de pruebas).");
#else
  if (canOk) {
    bool contact = false;
    for (int i = 0; i < CONTACT_CHECK_RETRIES && !contact; i++) {
      contact = canObd2CheckContact();
    }
    if (!contact) {
      Serial.println("Sin contacto.");
      enterDeepSleepUntilContact(); // never returns
    }
  }
#endif

  Serial.println("Contacto detectado (o CAN con falla) -- encendiendo perifericos.");
  powerGateSet(true);
  delay(POWER_RAIL_SETTLE_MS); // let rail 2's 3.3V settle before touching the OLED/SD on it

  // LEDs first so init failures below are visible immediately via the
  // error blink-code even with nothing else running yet.
  statusLedsInit();
  xTaskCreatePinnedToCore(statusLedsTask, "leds", STACK_LED_TASK, nullptr,
                           PRIO_LED_TASK, nullptr, CORE_LED_TASK);

  bool oledOk = displayInit();
  if (!oledOk) {
    // I2C right after the rail 2 MOSFET closes can be flaky on the very
    // first transaction (module still settling) -- one retry is cheap
    // insurance before believing it's genuinely absent/broken.
    delay(100);
    oledOk = displayInit();
  }
  bool sdOk   = sdLoggerInit();

  webServerInit(); // reports ErrorCode::WIFI_FAIL internally if softAP fails

  if (canOk) {
    xTaskCreatePinnedToCore(canObd2Task, "canObd2", STACK_CAN_TASK, nullptr,
                             PRIO_CAN_TASK, nullptr, CORE_CAN_TASK);
  }
  if (oledOk) {
    xTaskCreatePinnedToCore(displayTask, "display", STACK_DISPLAY_TASK, nullptr,
                             PRIO_DISPLAY_TASK, nullptr, CORE_DISPLAY_TASK);
  }
  if (sdOk) {
    xTaskCreatePinnedToCore(sdLoggerTask, "sdLogger", STACK_SD_TASK, nullptr,
                             PRIO_SD_TASK, nullptr, CORE_SD_TASK);
  }

  Serial.printf("Listo. CAN=%d OLED=%d SD=%d  AP=%s pass=%s IP=%s\n",
                canOk, oledOk, sdOk, WIFI_AP_SSID, WIFI_AP_PASS, WIFI_AP_IP_HINT);
}

void loop() {
  // Everything runs in the dedicated tasks above; nothing to do here.
  vTaskDelay(pdMS_TO_TICKS(1000));
}
