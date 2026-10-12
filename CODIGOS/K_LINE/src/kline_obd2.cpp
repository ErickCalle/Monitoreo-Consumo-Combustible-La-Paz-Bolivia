// K-Line (ISO 9141-2) OBD2 driver over an L9637D transceiver.
//
// Temporizacion y formato de trama verificados contra el propio
// estandar ISO 9141-2:1994(E) (clausulas 6, 7, 11, 12 y Anexo A,
// tablas A.1/A.2) -- no inventados. Ver README.md para las fuentes y
// el pinout del L9637D (verificado contra su datasheet oficial,
// STMicroelectronics, Sept. 2002, tabla "PIN DESCRIPTION").
//
// A diferencia de can_obd2.cpp (donde el bus CAN queda "abierto" y
// basta con pedir PIDs uno tras otro), el K-Line de ISO9141-2 exige
// repetir la inicializacion lenta a 5 baudios cada vez que el ECU deja
// de responder -- no existe un "modo streaming" nativo en este
// protocolo. Por eso klineObd2Task() reinicializa el bus al principio
// de cada ciclo de sondeo en vez de una sola vez como canObd2Init().
#include <Arduino.h>
#include <math.h>
#include "config.h"
#include "types.h"
#include "kline_obd2.h"
#include "fuel_calc.h"
#include "power_sleep.h"

// UART1 de hardware, remapeado a PIN_KLINE_TX/RX en kline10400Begin().
// Durante el init lento a 5 baudios estos mismos pines se controlan a
// mano con pinMode/digitalWrite (ver klineSendAddressSlow()); recien
// despues del handshake se le entrega el pin TX al periferico UART.
static HardwareSerial KlineSerial(1);

// -----------------------------------------------------------------------
// Temporizacion ISO 9141-2 (Anexo A, tablas A.1 y A.2). Todos los valores
// son los min/max oficiales del estandar; donde el codigo necesita un
// solo numero para un delay() se usa un punto intermedio con margen
// hacia el lado seguro (nunca por debajo del minimo de la norma).
// -----------------------------------------------------------------------
static const uint32_t KLINE_BIT_MS        = 200;   // 1000/5 baudios
static const uint32_t W0_IDLE_MS          = 3;      // W0 >= 2 ms
static const uint32_t W1_SYNC_TIMEOUT_MS  = 400;    // W1: 60-300 ms (+margen)
static const uint32_t W2_KW1_TIMEOUT_MS   = 60;     // W2: 5-20 ms (+margen)
static const uint32_t W3_KW2_TIMEOUT_MS   = 60;     // W3: 0-20 ms (+margen)
static const uint32_t W4_DELAY_MS         = 30;     // W4: 25-50 ms -> enviar en el medio
static const uint32_t W4_ECHO_TIMEOUT_MS  = 80;      // leer el eco de nuestro propio byte
static const uint32_t W4_ADDR_INV_TIMEOUT_MS = 100;  // esperar ~0x33 del ECU
static const uint32_t P3_MIN_MS           = 60;      // P3 min = 55 ms (clause 12); +margen
static const uint32_t P4_BYTE_GAP_MS      = 10;      // P4: 5-20 ms entre bytes que ENVIAMOS
static const uint32_t RESPONSE_FIRST_BYTE_TIMEOUT_MS = 300; // P2(08) max = 50 ms, mas margen real
static const uint32_t RESPONSE_BYTE_GAP_TIMEOUT_MS    = 50;  // P1 max = 20 ms, mas margen

static const uint8_t  KLINE_INIT_ADDRESS  = 0x33; // direccion funcional OBD-II (ISO9141-2 clause 11)

// A diferencia de can_obd2.cpp, esta version NO sondea de antemano cual
// de estos PIDs soporta el ECU (alla, queryPidSupport() lee el bitmask
// del PID 0x00 una sola vez al arrancar): en K-Line cada vuelta de ida
// y vuelta ya cuesta varias decenas de ms, y agregar una consulta mas
// por ciclo no se justifica todavia con un solo vehiculo de prueba. Se
// pide cada PID en cada ciclo y, si el ECU no lo soporta, simplemente
// no contesta ese PID -- klineObd2Task() ya maneja esa falta de
// respuesta como "no critico" salvo para RPM/MAP/IAT/velocidad. Si en
// el futuro se agrega el sondeo de PID 0x00, el bitmask se decodifica
// igual que en can_obd2.cpp::queryPidSupport().
static const uint8_t kPollPids[] = {0x0C, 0x0D, 0x0B, 0x0F, 0x05, 0x06, 0x07, 0x04, 0x33};
static const size_t  kPollPidCount = sizeof(kPollPids) / sizeof(kPollPids[0]);

// Misma ISA de respaldo que can_obd2.cpp -- ver la nota alli sobre por
// que baro_kpa nunca escala fuel_gs, solo se registra para validacion.
static float isaPressureKpaAt(float altitude_m) {
  const float P0 = 101.325f, T0 = 288.15f, L = 0.0065f, g = 9.80665f;
  const float M = 0.0289644f, R = 8.31447f;
  return P0 * powf(1.0f - (L * altitude_m) / T0, (g * M) / (R * L));
}

// -----------------------------------------------------------------------
// Init lento a 5 baudios (ISO9141-2 clausula 7.2, Figura 4): bit de
// arranque (logico 0), 8 bits de direccion LSB primero, bit de parada
// (logico 1), cada uno sostenido 200 ms. Se hace a mano con
// pinMode/digitalWrite porque ningun periferico UART estandar baja de
// ~1200 baudios -- 5 baudios no es representable en hardware.
// -----------------------------------------------------------------------
static void klineSendAddressSlow(uint8_t address) {
  pinMode(PIN_KLINE_TX, OUTPUT);
  digitalWrite(PIN_KLINE_TX, HIGH); // reposo = linea K liberada (pull-up externo de 510 ohm a VS)
  delay(W0_IDLE_MS);

  digitalWrite(PIN_KLINE_TX, LOW);  // bit de arranque
  delay(KLINE_BIT_MS);

  for (int i = 0; i < 8; i++) {     // 8 bits de datos, LSB primero
    bool bitHigh = (address >> i) & 0x1;
    digitalWrite(PIN_KLINE_TX, bitHigh ? HIGH : LOW);
    delay(KLINE_BIT_MS);
  }

  digitalWrite(PIN_KLINE_TX, HIGH); // bit de parada
  delay(KLINE_BIT_MS);
}

static void kline10400Begin() {
  KlineSerial.begin(10400, SERIAL_8N1, PIN_KLINE_RX, PIN_KLINE_TX);
}

static void kline10400End() {
  KlineSerial.end();
}

// Lee un byte con timeout corto; usado tanto para el handshake como
// para descartar el eco de lo que el propio ESP32 transmite (el bus
// K-Line es un solo hilo: todo lo que este tester escribe se escucha a
// si mismo en RX un instante despues, ademas de lo que responda el ECU).
static bool klineReadByte(uint8_t &outByte, uint32_t timeout_ms) {
  uint32_t start = millis();
  while ((millis() - start) < timeout_ms) {
    if (KlineSerial.available()) {
      outByte = (uint8_t)KlineSerial.read();
      return true;
    }
  }
  return false;
}

// Envia un byte y descarta su propio eco antes de devolver el control
// -- de lo contrario ese eco aparece como el primer byte "recibido" de
// cualquier lectura posterior y arruina el parseo.
static bool klineWriteByteAndDiscardEcho(uint8_t b, uint32_t echoTimeout_ms) {
  KlineSerial.write(b);
  KlineSerial.flush();
  uint8_t echo;
  return klineReadByte(echo, echoTimeout_ms); // no se valida el valor: con ruido en el bus
                                               // alcanza con liberar el buffer
}

// -----------------------------------------------------------------------
// Secuencia completa de inicializacion ISO9141-2 (clausulas 6 y 7,
// Figura 6 / tabla A.1): direccion a 5 baudios -> sync 0x55 -> KW1 ->
// KW2 -> complemento de KW2 (tester) -> complemento de la direccion
// (ECU). Devuelve true solo si las 4 etapas posteriores al init lento
// se completaron dentro de los tiempos W1-W4.
// -----------------------------------------------------------------------
static bool klineSlowInit() {
  kline10400End();
  klineSendAddressSlow(KLINE_INIT_ADDRESS);
  kline10400Begin();

  uint8_t sync = 0;
  if (!klineReadByte(sync, W1_SYNC_TIMEOUT_MS) || sync != 0x55) return false;

  uint8_t kw1 = 0, kw2 = 0;
  if (!klineReadByte(kw1, W2_KW1_TIMEOUT_MS)) return false;
  if (!klineReadByte(kw2, W3_KW2_TIMEOUT_MS)) return false;

  delay(W4_DELAY_MS); // dentro de la ventana W4 (25-50 ms) antes de contestar
  if (!klineWriteByteAndDiscardEcho((uint8_t)(~kw2), W4_ECHO_TIMEOUT_MS)) return false;

  uint8_t addrInv = 0;
  if (!klineReadByte(addrInv, W4_ADDR_INV_TIMEOUT_MS)) return false;
  if (addrInv != (uint8_t)(~KLINE_INIT_ADDRESS)) return false; // esperado: 0xCC

  delay(P3_MIN_MS); // P3 min = 55 ms antes del primer mensaje (clause 12)
  return true;
}

// -----------------------------------------------------------------------
// Mensaje de pedido Modo 01 (ISO9141-2 clausula 11, tabla 1, columna 1):
// [0x68, 0x6A, 0xF1, 0x01, PID, checksum]. El checksum es la suma de 8
// bits de todos los bytes anteriores, modulo 256 (clausula 11.2).
// Cada byte se envia con un espaciado P4 (5-20 ms) entre si, tal como
// exige la norma para mensajes del tester hacia el vehiculo -- un
// Serial.write(buffer, len) de una sola vez violaria ese minimo.
// -----------------------------------------------------------------------
static bool sendPidRequest(uint8_t pid) {
  uint8_t msg[6] = {0x68, 0x6A, 0xF1, 0x01, pid, 0x00};
  uint8_t cs = 0;
  for (int i = 0; i < 5; i++) cs += msg[i];
  msg[5] = cs;

  for (int i = 0; i < 6; i++) {
    if (!klineWriteByteAndDiscardEcho(msg[i], W4_ECHO_TIMEOUT_MS)) return false;
    if (i < 5) delay(P4_BYTE_GAP_MS);
  }
  return true;
}

// Respuesta esperada (tabla 1, columna 2): [0x48, 0x6B, SRC, 0x41, PID,
// datos..., checksum]. Se lee byte a byte con el timeout P1 (interbyte
// del vehiculo) entre cada uno; se corta apenas se completa un mensaje
// de longitud razonable o se agota RESPONSE_BYTE_GAP_TIMEOUT_MS.
static bool receivePidResponse(uint8_t pid, uint8_t *outData, uint8_t &outLen, uint32_t timeout_ms) {
  uint8_t buf[11]; // maximo segun ISO9141-2 clause 11.1: 5 a 11 bytes
  uint8_t len = 0;
  uint8_t b;

  if (!klineReadByte(b, timeout_ms)) return false; // primer byte: timeout largo (P2)
  buf[len++] = b;

  while (len < sizeof(buf)) {
    if (!klineReadByte(b, RESPONSE_BYTE_GAP_TIMEOUT_MS)) break; // fin del mensaje
    buf[len++] = b;
  }

  if (len < 6) return false; // header(3) + 0x41 + pid + checksum, minimo
  if (buf[0] != 0x48 || buf[1] != 0x6B || buf[3] != 0x41 || buf[4] != pid) return false;

  uint8_t cs = 0;
  for (int i = 0; i < len - 1; i++) cs += buf[i];
  if (cs != buf[len - 1]) return false; // checksum invalido -> trama descartada (clause 13.2.1)

  outLen = len;
  memcpy(outData, buf, len);
  return true;
}

// Mismos PIDs, mismo mapeo de bytes a VehicleData que can_obd2.cpp,
// solo que el primer byte de datos esta en el indice 5 (tras los 3
// bytes de encabezado + 0x41 + pid) en vez del indice 3 de una trama
// CAN de un solo frame.
static void decodeAndStore(uint8_t pid, const uint8_t *data, uint8_t len, VehicleData &vd) {
  switch (pid) {
    case 0x0C: if (len >= 7) vd.rpm = ((uint16_t)data[5] << 8 | data[6]) / 4; break;
    case 0x0D: if (len >= 6) vd.speed_kmh = data[5]; break;
    case 0x0B: if (len >= 6) vd.map_kpa = data[5]; break;
    case 0x0F: if (len >= 6) vd.iat_c = (float)data[5] - 40.0f; break;
    case 0x05: if (len >= 6) vd.coolant_c = (float)data[5] - 40.0f; break;
    case 0x04: if (len >= 6) vd.load_pct = data[5] * 100.0f / 255.0f; break;
    case 0x06: if (len >= 6) vd.stft_pct = ((float)data[5] - 128.0f) * 100.0f / 128.0f; break;
    case 0x07: if (len >= 6) vd.ltft_pct = ((float)data[5] - 128.0f) * 100.0f / 128.0f; break;
    case 0x33:
      if (len >= 6) { vd.baro_kpa = data[5]; vd.baro_is_estimated = false; }
      break;
    default: break;
  }
}

// -----------------------------------------------------------------------
bool klineObd2Init() {
  pinMode(PIN_KLINE_TX, OUTPUT);
  pinMode(PIN_KLINE_RX, INPUT);
  digitalWrite(PIN_KLINE_TX, HIGH); // linea K en reposo (liberada)
  return true; // el init de protocolo real ocurre por ciclo, ver klineSlowInit()
}

bool klineObd2CheckContact() {
  if (!klineSlowInit()) return false;
  uint8_t data[11];
  uint8_t len = 0;
  bool ok = sendPidRequest(0x0C) && receivePidResponse(0x0C, data, len, RESPONSE_FIRST_BYTE_TIMEOUT_MS);
  return ok;
}

void klineObd2Task(void *pvParameters) {
  (void)pvParameters;

  uint32_t lastCycleMs = millis();
  uint8_t data[11];
  uint8_t len = 0;
  uint8_t noResponseStreak = 0;

  for (;;) {
    bool initOk = klineSlowInit();

    VehicleData scratch;
    scratch.baro_kpa = isaPressureKpaAt(SITE_ALTITUDE_M);
    scratch.baro_is_estimated = true;
    bool anyResponse = false;
    bool criticalOk = initOk;

    if (initOk) {
      for (size_t i = 0; i < kPollPidCount; i++) {
        uint8_t pid = kPollPids[i];
        bool isCritical = (pid == 0x0C || pid == 0x0B || pid == 0x0F || pid == 0x0D);

        if (sendPidRequest(pid) &&
            receivePidResponse(pid, data, len, RESPONSE_FIRST_BYTE_TIMEOUT_MS)) {
          decodeAndStore(pid, data, len, scratch);
          anyResponse = true;
        } else if (isCritical) {
          criticalOk = false;
        }
        delay(P3_MIN_MS); // P3 min entre el fin de una respuesta y el siguiente pedido
      }
    }

    uint32_t now = millis();
    float dt = (now - lastCycleMs) / 1000.0f;
    lastCycleMs = now;

    CanStatus status;
    if (!initOk) status = CanStatus::NO_RESPONSE;
    else if (criticalOk) status = CanStatus::OK;
    else if (anyResponse) status = CanStatus::BUS_ERROR;
    else status = CanStatus::NO_RESPONSE;

    if (xSemaphoreTake(g_dataMutex, pdMS_TO_TICKS(100)) == pdTRUE) {
      VehicleData &g = g_vehicleData;
      g.rpm = scratch.rpm;
      g.speed_kmh = scratch.speed_kmh;
      g.map_kpa = scratch.map_kpa;
      g.iat_c = scratch.iat_c;
      g.coolant_c = scratch.coolant_c;
      g.load_pct = scratch.load_pct;
      g.stft_pct = scratch.stft_pct;
      g.ltft_pct = scratch.ltft_pct;
      g.baro_kpa = scratch.baro_kpa;
      g.baro_is_estimated = scratch.baro_is_estimated;
      g.can_status = status;
      g.data_valid = criticalOk;
      g.last_update_ms = now;

      if (criticalOk && dt > 0.0f && dt < 5.0f) {
        fuelCalcUpdate(g, dt);
      }
      xSemaphoreGive(g_dataMutex);
    }

    g_systemStatus.can_ok = criticalOk;

#if !FORCE_AWAKE_FOR_BENCH_TEST
    if (status == CanStatus::NO_RESPONSE) {
      noResponseStreak++;
      if (noResponseStreak >= CONTACT_LOST_DEBOUNCE_CYCLES) {
        enterDeepSleepUntilContact();
      }
    } else {
      noResponseStreak = 0;
    }
#endif
  }
}
