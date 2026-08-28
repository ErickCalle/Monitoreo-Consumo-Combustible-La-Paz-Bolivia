// Benchmark de comunicacion CAN, ESP32-S3 -- SOLO para llenar la columna
// "ESP32-S3 (sesion propia)" de la Tabla 4.6 del Capitulo 4. No es parte
// del firmware de produccion (ver ../esp32s3_obd2_speeddensity/).
//
// Que hace: durante 5 minutos, con el motor del vehiculo en ralenti,
// solicita repetidamente el PID 0x0C (RPM) y mide tres cosas:
//   - tramas de respuesta validas recibidas
//   - tramas de error detectadas por el controlador TWAI (bus-off / error
//     pasivo), como indicador aproximado de "tramas con error"
//   - latencia promedio entre la solicitud y la respuesta
//
// Por que PID 0x0C y no los 9 PIDs del firmware real: 0x0C (RPM) es
// obligatorio en todo ECU OBD-II, asi que aisla "esta funcionando la
// comunicacion" de "el vehiculo soporta este PID en particular" -- lo
// segundo ya se verifico por separado en la Tabla 4.x de PIDs soportados.
//
// Conexion identica al firmware real: TX=GPIO4, RX=GPIO5 hacia el
// SN65HVD230, 500 kbit/s. Resultados por Serial a 115200 baudios.

#include <Arduino.h>
#include "driver/twai.h"

#define PIN_CAN_TX GPIO_NUM_4
#define PIN_CAN_RX GPIO_NUM_5

#define OBD2_REQUEST_ID     0x7DF
#define OBD2_RESP_ID_MIN    0x7E8
#define OBD2_RESP_ID_MAX    0x7EF
#define PID_TO_TEST         0x0C   // RPM
#define TEST_DURATION_MS    (5UL * 60UL * 1000UL) // 5 minutos
#define REQUEST_PERIOD_MS   100
#define RESPONSE_TIMEOUT_MS 150

static uint32_t requestsSent = 0;
static uint32_t responsesOk  = 0;
static uint32_t errorFrames  = 0;
static uint64_t latencySumUs = 0;

static bool sendPidRequest(uint8_t pid) {
  twai_message_t msg = {};
  msg.identifier = OBD2_REQUEST_ID;
  msg.data_length_code = 8;
  msg.data[0] = 0x02;
  msg.data[1] = 0x01;
  msg.data[2] = pid;
  return twai_transmit(&msg, pdMS_TO_TICKS(50)) == ESP_OK;
}

// Descarta cualquier trama que no sea la respuesta esperada al PID pedido,
// igual que en el firmware real (can_obd2.cpp / receivePidResponse).
static bool waitForResponse(uint8_t pid, uint32_t timeoutMs) {
  uint32_t start = millis();
  twai_message_t msg;
  while ((millis() - start) < timeoutMs) {
    uint32_t elapsed = millis() - start;
    uint32_t remaining = (elapsed >= timeoutMs) ? 0 : (timeoutMs - elapsed);
    if (remaining == 0) break;
    if (twai_receive(&msg, pdMS_TO_TICKS(remaining)) != ESP_OK) break;
    if (!msg.extd &&
        msg.identifier >= OBD2_RESP_ID_MIN && msg.identifier <= OBD2_RESP_ID_MAX &&
        msg.data_length_code >= 3 && msg.data[1] == 0x41 && msg.data[2] == pid) {
      return true;
    }
  }
  return false;
}

void setup() {
  Serial.begin(115200);
  delay(1500);
  Serial.println("\nBenchmark CAN ESP32-S3 -- 5 min, PID 0x0C (RPM)");
  Serial.println("Conectar al OBD-II y poner el motor en ralenti antes de continuar.");

  twai_general_config_t g_config =
      TWAI_GENERAL_CONFIG_DEFAULT(PIN_CAN_TX, PIN_CAN_RX, TWAI_MODE_NORMAL);
  twai_timing_config_t t_config = TWAI_TIMING_CONFIG_500KBITS();
  twai_filter_config_t f_config = TWAI_FILTER_CONFIG_ACCEPT_ALL();

  if (twai_driver_install(&g_config, &t_config, &f_config) != ESP_OK) {
    Serial.println("ERROR: twai_driver_install fallo");
    while (1) delay(1000);
  }
  if (twai_start() != ESP_OK) {
    Serial.println("ERROR: twai_start fallo");
    while (1) delay(1000);
  }
  twai_reconfigure_alerts(TWAI_ALERT_BUS_ERROR | TWAI_ALERT_ERR_PASS | TWAI_ALERT_BUS_OFF, nullptr);

  Serial.println("Iniciando...");
  uint32_t testStart = millis();
  uint32_t lastPrint = testStart;

  while ((millis() - testStart) < TEST_DURATION_MS) {
    uint32_t reqStartUs = micros();
    requestsSent++;

    if (sendPidRequest(PID_TO_TEST) && waitForResponse(PID_TO_TEST, RESPONSE_TIMEOUT_MS)) {
      responsesOk++;
      latencySumUs += (uint64_t)(micros() - reqStartUs);
    }

    uint32_t alerts = 0;
    if (twai_read_alerts(&alerts, 0) == ESP_OK && alerts != 0) {
      if (alerts & (TWAI_ALERT_BUS_ERROR | TWAI_ALERT_ERR_PASS | TWAI_ALERT_BUS_OFF)) {
        errorFrames++;
      }
    }

    if (millis() - lastPrint > 30000) {
      lastPrint = millis();
      Serial.printf("...%lu s | solicitudes=%lu respuestas=%lu errores=%lu\n",
                     (unsigned long)((millis() - testStart) / 1000),
                     (unsigned long)requestsSent, (unsigned long)responsesOk,
                     (unsigned long)errorFrames);
    }

    delay(REQUEST_PERIOD_MS);
  }

  double avgLatencyMs = responsesOk ? (double)latencySumUs / 1000.0 / responsesOk : 0.0;

  Serial.println("\n================================================");
  Serial.println("RESULTADO -- Tabla 4.6, columna ESP32-S3 (sesion propia)");
  Serial.println("================================================");
  Serial.printf("Solicitudes enviadas:            %lu\n", (unsigned long)requestsSent);
  Serial.printf("Tramas recibidas en 5 min:        %lu\n", (unsigned long)responsesOk);
  Serial.printf("Tramas con error de CRC/bus:       %lu\n", (unsigned long)errorFrames);
  Serial.printf("Latencia promedio (ms):           %.1f\n", avgLatencyMs);
  Serial.println("================================================");
  Serial.println("Copia estos 3 numeros a la Tabla 4.6 y vuelve a");
  Serial.println("flashear el firmware real (esp32s3_obd2_speeddensity).");
}

void loop() {
  delay(1000);
}
