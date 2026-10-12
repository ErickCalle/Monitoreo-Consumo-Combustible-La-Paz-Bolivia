// ESP32-S3 N16R8 -- OBD2 (K-Line ISO9141-2 / L9637D) speed-density fuel
// consumption meter con OLED (I2C), registro CSV en microSD (SPI) y un
// panel web local (ESPAsyncWebServer). Es la misma arquitectura que
// CODIGOS/esp32s3_obd2_speeddensity/ -- unica diferencia real: la
// adquisicion usa kline_obd2.cpp (K-Line/L9637D) en vez de can_obd2.cpp
// (TWAI/SN65HVD230). Ver README.md para el pinout del L9637D y los
// pasos de calibracion.
//
// Task/core layout (identico al original):
//   core 0: sondeo K-Line/OBD2 + fuel calc (maxima prioridad),
//           pila WiFi/AsyncTCP + tarea de push por WebSocket
//   core 1: refresco OLED, logger de microSD, driver de LEDs de estado
//
// Power: la rail 1 (ESP32-S3 + L9637D) va cableada directo a los 12V
// constantes del OBD2 y nunca se corta. La rail 2 (LEDs+OLED, microSD)
// se corta con dos MOSFET que el propio chip maneja. setup() hace un
// ping al bus K-Line antes de tocar la rail 2 -- sin respuesta se asume
// "sin contacto" y el board entra directo en deep sleep en vez de
// terminar el arranque (ver power_sleep.cpp).
#include <Arduino.h>
#include "config.h"
#include "types.h"
#include "kline_obd2.h"
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
  Serial.println("\nESP32-S3 OBD2 K-Line Speed-Density - iniciando");

  g_dataMutex = xSemaphoreCreateMutex();
  g_sdMutex   = xSemaphoreCreateMutex();

  // Rail 2 (LEDs+OLED, microSD) stays off and the K-Line transceiver is
  // the only thing brought up until contact is confirmed -- igual
  // criterio que la version CAN, ver el comentario de cabecera arriba.
  powerGateInit();
  bool klineOk = klineObd2Init();

#if FORCE_AWAKE_FOR_BENCH_TEST
  Serial.println("FORCE_AWAKE_FOR_BENCH_TEST=1 -- omitiendo chequeo de contacto (banco de pruebas).");
#else
  if (klineOk) {
    bool contact = false;
    for (int i = 0; i < CONTACT_CHECK_RETRIES && !contact; i++) {
      contact = klineObd2CheckContact();
    }
    if (!contact) {
      Serial.println("Sin contacto.");
      enterDeepSleepUntilContact(); // never returns
    }
  }
#endif

  Serial.println("Contacto detectado (o K-Line con falla) -- encendiendo perifericos.");
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

  if (klineOk) {
    xTaskCreatePinnedToCore(klineObd2Task, "klineObd2", STACK_KLINE_TASK, nullptr,
                             PRIO_KLINE_TASK, nullptr, CORE_KLINE_TASK);
  }
  if (oledOk) {
    xTaskCreatePinnedToCore(displayTask, "display", STACK_DISPLAY_TASK, nullptr,
                             PRIO_DISPLAY_TASK, nullptr, CORE_DISPLAY_TASK);
  }
  if (sdOk) {
    xTaskCreatePinnedToCore(sdLoggerTask, "sdLogger", STACK_SD_TASK, nullptr,
                             PRIO_SD_TASK, nullptr, CORE_SD_TASK);
  }

  Serial.printf("Listo. K-Line=%d OLED=%d SD=%d  AP=%s pass=%s IP=%s\n",
                klineOk, oledOk, sdOk, WIFI_AP_SSID, WIFI_AP_PASS, WIFI_AP_IP_HINT);
}

void loop() {
  // Everything runs in the dedicated tasks above; nothing to do here.
  vTaskDelay(pdMS_TO_TICKS(1000));
}
