/*
 * Escaner OBD-II por K-Line (ISO 9141-2 / ISO 14230-4 KWP2000)
 * Hardware: ESP32-S3 + transceptor L9637D
 * Requiere: Arduino-ESP32 core 3.x
 *
 * Conexion (revisa los pines del L9637D en su datasheet):
 *   L9637D RXD  -> GPIO KLINE_RX_PIN  (el ESP32 NO tolera 5 V: usa divisor o level shifter si RXD sale a 5 V)
 *   L9637D TXD  <- GPIO KLINE_TX_PIN
 *   L9637D K    -> OBD2 pin 7
 *   L9637D Vs   -> OBD2 pin 16 (+12 V)
 *   GND comun   -> OBD2 pin 4/5
 *   Pull-up de ~510 ohm entre K (pin 7) y +12 V si la linea no sube a alto sola.
 *
 * Monitor serie: 115200 baudios. Comandos:
 *   r = reconectar   p = releer PIDs soportados   l = datos en vivo on/off
 *   d = mostrar/ocultar bytes crudos TX/RX        h = ayuda
 *
 * Flujo: autotest del bus -> inicio rapido (KWP2000) -> inicio lento 5 baudios
 *        (ISO 9141-2 / KWP2000) -> PIDs soportados (Modo 01) -> datos en vivo.
 */

#include <Arduino.h>

// ---------------- Configuracion ----------------
#define KLINE_RX_PIN   18      // L9637D RXD -> ESP32
#define KLINE_TX_PIN   17      // ESP32 -> L9637D TXD
#define KLINE_BAUD     10400
#define ECU_ADDR       0x33    // direccion funcional OBD-II
#define TESTER_ADDR    0xF1

HardwareSerial KLine(1);

enum Proto : uint8_t { PROTO_NONE, PROTO_ISO9141, PROTO_KWP };

static Proto    proto        = PROTO_NONE;
static bool     connected    = false;
static bool     liveOn       = true;
static bool     debugHex     = true;
static bool     supported[256];
static uint8_t  keyB1 = 0, keyB2 = 0;
static uint8_t  lastNrc      = 0;
static uint8_t  failCount    = 0;
static uint32_t lastActivity = 0;

// ---------------- Utilidades ----------------
static uint8_t checksum(const uint8_t *b, size_t n) {
  uint8_t s = 0;
  for (size_t i = 0; i < n; i++) s += b[i];
  return s;
}

static void printHex(const char *tag, const uint8_t *b, size_t n) {
  if (!debugHex) return;
  Serial.printf("    %s:", tag);
  for (size_t i = 0; i < n; i++) Serial.printf(" %02X", b[i]);
  Serial.println();
}

static const char *protoName() {
  switch (proto) {
    case PROTO_ISO9141: return "ISO 9141-2 (cabecera 68 6A F1)";
    case PROTO_KWP:     return "ISO 14230-4 KWP2000 (cabecera con byte de formato)";
    default:            return "ninguno";
  }
}

static void flushRx() {
  while (KLine.available()) KLine.read();
}

static void openUart() {
  KLine.begin(KLINE_BAUD, SERIAL_8N1, KLINE_RX_PIN, KLINE_TX_PIN);
  delay(5);
  flushRx();
}

static bool readByte(uint8_t *b, uint32_t timeoutMs) {
  uint32_t t0 = millis();
  while (millis() - t0 < timeoutMs) {
    if (KLine.available()) {
      *b = (uint8_t)KLine.read();
      return true;
    }
    delay(1);
  }
  return false;
}

// La K-Line es half-duplex: el L9637D devuelve por RX todo lo que se envia (eco).
static bool writeWithEcho(uint8_t b) {
  KLine.write(b);
  uint8_t e;
  if (!readByte(&e, 40)) return false;   // sin eco -> problema de cableado/transceptor
  return e == b;
}

// Recibe una trama: espera el primer byte y corta cuando hay un hueco > 30 ms (P1 max = 20 ms).
static int readFrame(uint8_t *buf, size_t maxLen, uint32_t firstTimeoutMs) {
  size_t n = 0;
  uint8_t b;
  if (!readByte(&b, firstTimeoutMs)) return 0;
  buf[n++] = b;
  while (n < maxLen && readByte(&b, 30)) buf[n++] = b;
  return (int)n;
}

static int headerLen(const uint8_t *b) {
  uint8_t fmt = b[0];
  if (proto == PROTO_ISO9141 || (fmt & 0xC0) == 0x40) return 3;
  int h = (fmt & 0xC0) ? 3 : 1;
  if ((fmt & 0x3F) == 0) h++;            // byte de longitud adicional
  return h;
}

// Envia un servicio (+parametros) y devuelve el payload de la respuesta en out.
// Retorno: >0 longitud del payload | 0 sin respuesta | -1 respuesta negativa
//          -2 trama invalida/checksum | -3 error de eco al transmitir
static int request(const uint8_t *req, uint8_t reqLen, uint8_t *out, uint8_t outMax, uint32_t timeoutMs) {
  uint8_t tx[24];
  uint8_t n = 0;
  if (proto == PROTO_ISO9141) {
    tx[n++] = 0x68; tx[n++] = 0x6A; tx[n++] = TESTER_ADDR;
  } else {
    tx[n++] = 0xC0 | reqLen; tx[n++] = ECU_ADDR; tx[n++] = TESTER_ADDR;
  }
  memcpy(tx + n, req, reqLen);
  n += reqLen;
  tx[n] = checksum(tx, n);
  n++;

  flushRx();
  printHex("TX", tx, n);
  for (uint8_t i = 0; i < n; i++) {
    if (!writeWithEcho(tx[i])) {
      Serial.println("    [!] Eco incorrecto o ausente al transmitir (cableado RX/TX o colision en el bus)");
      return -3;
    }
    if (i < n - 1) delay(5);             // P4 minimo 5 ms entre bytes del tester
  }

  uint8_t rx[40];
  for (int attempt = 0; attempt < 4; attempt++) {
    int len = readFrame(rx, sizeof(rx), timeoutMs);
    if (len == 0) return 0;
    printHex("RX", rx, len);
    if (len < 3 || checksum(rx, len - 1) != rx[len - 1]) return -2;
    int h = headerLen(rx);
    int pl = len - 1 - h;
    if (pl <= 0) return -2;
    if (pl > outMax) pl = outMax;
    memcpy(out, rx + h, pl);
    if (out[0] == 0x7F) {
      lastNrc = (pl >= 3) ? out[2] : 0;
      if (lastNrc == 0x78) { timeoutMs = 2000; continue; }  // respuesta pendiente: seguir esperando
      return -1;
    }
    lastActivity = millis();
    return pl;
  }
  return 0;
}

static bool readPid(uint8_t pid, uint8_t *data, uint8_t *len) {
  uint8_t req[2] = {0x01, pid};
  uint8_t pl[24];
  int n = request(req, 2, pl, sizeof(pl), 300);
  if (n >= 3 && pl[0] == 0x41 && pl[1] == pid) {
    uint8_t l = n - 2;
    if (l > 8) l = 8;
    memcpy(data, pl + 2, l);
    *len = l;
    failCount = 0;
    return true;
  }
  if (failCount < 255) failCount++;
  return false;
}

// ---------------- Autotest del bus (L9637D) ----------------
static void busSelfTest() {
  Serial.println("\n[TEST] Autotest del bus K-Line / L9637D");
  KLine.end();
  pinMode(KLINE_RX_PIN, INPUT);
  pinMode(KLINE_TX_PIN, OUTPUT);
  digitalWrite(KLINE_TX_PIN, HIGH);
  delay(20);
  bool idleHigh = digitalRead(KLINE_RX_PIN);
  digitalWrite(KLINE_TX_PIN, LOW);
  delay(5);
  bool followsLow = !digitalRead(KLINE_RX_PIN);
  digitalWrite(KLINE_TX_PIN, HIGH);
  delay(5);
  bool followsHigh = digitalRead(KLINE_RX_PIN);

  Serial.printf("  Reposo en alto: %s | TX bajo -> RX bajo: %s | TX alto -> RX alto: %s\n",
                idleHigh ? "OK" : "FALLA", followsLow ? "OK" : "FALLA", followsHigh ? "OK" : "FALLA");
  if (!followsLow) {
    Serial.println("  [!] RX no sigue a TX: revisa alimentacion Vs (12 V), GND, pines TX/RX y el propio L9637D.");
  } else if (!idleHigh || !followsHigh) {
    Serial.println("  [!] La linea K no sube a alto: llave en ON? Falta pull-up de ~510 ohm a +12 V en K?");
  } else {
    Serial.println("  Transceptor y cableado OK.");
  }
}

// ---------------- Inicializacion ----------------
static bool initFast() {
  Serial.println("\n[INIT] Inicio rapido (ISO 14230-4 KWP2000)...");
  KLine.end();
  pinMode(KLINE_TX_PIN, OUTPUT);
  digitalWrite(KLINE_TX_PIN, HIGH);
  delay(350);                                   // bus libre (W5 >= 300 ms)
  digitalWrite(KLINE_TX_PIN, LOW);  delayMicroseconds(25000);   // TiniL = 25 ms
  digitalWrite(KLINE_TX_PIN, HIGH); delayMicroseconds(25000);   // 25 ms alto (Twup = 50 ms)
  openUart();

  proto = PROTO_KWP;
  uint8_t req[1] = {0x81};                      // StartCommunication
  uint8_t pl[16];
  int n = request(req, 1, pl, sizeof(pl), 300);
  if (n >= 3 && pl[0] == 0xC1) {
    keyB1 = pl[1]; keyB2 = pl[2];
    Serial.printf("  La ECU respondio. Key bytes: 0x%02X 0x%02X\n", keyB1, keyB2);
    return true;
  }
  Serial.println("  Sin respuesta valida al inicio rapido.");
  proto = PROTO_NONE;
  return false;
}

static bool initSlow() {
  Serial.println("\n[INIT] Inicio lento 5 baudios (ISO 9141-2 / KWP2000), direccion 0x33...");
  KLine.end();
  pinMode(KLINE_TX_PIN, OUTPUT);
  digitalWrite(KLINE_TX_PIN, HIGH);
  delay(350);

  uint8_t addr = ECU_ADDR;
  int bitErrors = 0;                                            // bits cuyo nivel no se vio en RX
  digitalWrite(KLINE_TX_PIN, LOW);  delay(100);                 // bit de inicio (200 ms en total)
  if (digitalRead(KLINE_RX_PIN) != LOW) bitErrors++;
  delay(100);
  for (int i = 0; i < 8; i++) {                                 // 8 bits, LSB primero
    int bit = (addr >> i) & 1;
    digitalWrite(KLINE_TX_PIN, bit);
    delay(100);
    if (digitalRead(KLINE_RX_PIN) != bit) bitErrors++;          // RX debe copiar a TX a traves de la linea K
    delay(100);
  }
  digitalWrite(KLINE_TX_PIN, HIGH);                             // bit de parada
  openUart();
  Serial.printf("  Direccion 0x%02X enviada a 5 baudios. Eco de los bits en RX: %s\n",
                addr, bitErrors == 0 ? "OK" : "FALLA");
  if (bitErrors) Serial.printf("  [!] %d de 9 bits no se vieron en RX: el pin TX no esta manejando la linea K.\n", bitErrors);

  uint8_t sync, kb1, kb2, inv;
  if (!readByte(&sync, 800)) { Serial.println("  Sin respuesta (esperaba 0x55)."); return false; }
  if (sync != 0x55) { Serial.printf("  Sincronismo inesperado: 0x%02X (esperaba 0x55)\n", sync); return false; }
  if (!readByte(&kb1, 150) || !readByte(&kb2, 150)) { Serial.println("  No llegaron los key bytes."); return false; }
  keyB1 = kb1; keyB2 = kb2;
  Serial.printf("  Sync 0x55 OK. Key bytes: 0x%02X 0x%02X\n", kb1, kb2);

  delay(30);                                                    // W4 = 25..50 ms
  if (!writeWithEcho((uint8_t)~kb2)) { Serial.println("  Error de eco al enviar ~KB2."); return false; }
  if (!readByte(&inv, 200)) { Serial.println("  La ECU no confirmo con la direccion invertida."); return false; }
  if (inv != (uint8_t)~ECU_ADDR) Serial.printf("  Aviso: confirmacion 0x%02X (esperada 0x%02X), continuo igual.\n", inv, (uint8_t)~ECU_ADDR);

  proto = (kb1 == 0x08) ? PROTO_ISO9141 : PROTO_KWP;
  return true;
}

// Confirma el enlace con Modo 01 PID 00; si falla, prueba el otro estilo de cabecera.
static bool verifyLink() {
  delay(60);                                                    // P3 >= 55 ms
  for (int t = 0; t < 2; t++) {
    uint8_t d[8], l;
    if (readPid(0x00, d, &l)) return true;
    proto = (proto == PROTO_ISO9141) ? PROTO_KWP : PROTO_ISO9141;
    Serial.printf("  Sin respuesta a 01 00; probando con %s\n", protoName());
    delay(60);
  }
  proto = PROTO_NONE;
  return false;
}

static bool connectEcu() {
  proto = PROTO_NONE;
  debugHex = true;
  busSelfTest();
  if (initFast() && verifyLink()) return true;
  if (initSlow() && verifyLink()) return true;
  return false;
}

// ---------------- PIDs ----------------
static const char *pidName(uint8_t pid) {
  switch (pid) {
    case 0x01: return "Estado del monitor (MIL, nº DTC)";
    case 0x03: return "Estado del sistema de combustible";
    case 0x04: return "Carga calculada del motor";
    case 0x05: return "Temperatura del refrigerante";
    case 0x06: return "Ajuste corto de combustible B1";
    case 0x07: return "Ajuste largo de combustible B1";
    case 0x08: return "Ajuste corto de combustible B2";
    case 0x09: return "Ajuste largo de combustible B2";
    case 0x0A: return "Presion de combustible";
    case 0x0B: return "Presion absoluta del multiple (MAP)";
    case 0x0C: return "RPM";
    case 0x0D: return "Velocidad del vehiculo";
    case 0x0E: return "Avance de encendido";
    case 0x0F: return "Temperatura del aire de admision (IAT)";
    case 0x10: return "Caudal de aire (MAF)";
    case 0x11: return "Posicion del acelerador";
    case 0x13: return "Sensores O2 presentes";
    case 0x14: return "Sensor O2 B1S1";
    case 0x15: return "Sensor O2 B1S2";
    case 0x1C: return "Norma OBD del vehiculo";
    case 0x1F: return "Tiempo desde el arranque";
    case 0x20: return "PIDs soportados [21-40]";
    case 0x21: return "Distancia con MIL encendida";
    case 0x2C: return "EGR comandado";
    case 0x2E: return "Purga EVAP comandada";
    case 0x2F: return "Nivel de combustible";
    case 0x30: return "Calentamientos desde borrado de DTC";
    case 0x31: return "Distancia desde borrado de DTC";
    case 0x33: return "Presion barometrica";
    case 0x40: return "PIDs soportados [41-60]";
    case 0x42: return "Voltaje del modulo de control";
    case 0x43: return "Carga absoluta";
    case 0x44: return "Relacion aire-combustible comandada";
    case 0x45: return "Posicion relativa del acelerador";
    case 0x46: return "Temperatura ambiente";
    case 0x49: return "Posicion del pedal acelerador D";
    case 0x4C: return "Actuador de mariposa comandado";
    case 0x51: return "Tipo de combustible";
    case 0x5C: return "Temperatura del aceite";
    case 0x5E: return "Consumo de combustible del motor";
    case 0x60: return "PIDs soportados [61-80]";
    case 0x80: return "PIDs soportados [81-A0]";
    case 0xA0: return "PIDs soportados [A1-C0]";
    case 0xC0: return "PIDs soportados [C1-E0]";
    default:   return "(sin nombre en la tabla)";
  }
}

static bool decodePid(uint8_t pid, const uint8_t *d, uint8_t l, char *o, size_t sz) {
  if (l < 1) return false;
  float A = d[0];
  float B = (l > 1) ? d[1] : 0;
  switch (pid) {
    case 0x04: snprintf(o, sz, "Carga %.0f%%", A * 100.0f / 255.0f); return true;
    case 0x05: snprintf(o, sz, "ECT %.0fC", A - 40.0f); return true;
    case 0x06: snprintf(o, sz, "STFT %.1f%%", (A - 128.0f) * 100.0f / 128.0f); return true;
    case 0x07: snprintf(o, sz, "LTFT %.1f%%", (A - 128.0f) * 100.0f / 128.0f); return true;
    case 0x0B: snprintf(o, sz, "MAP %.0f kPa", A); return true;
    case 0x0D: snprintf(o, sz, "Vel %.0f km/h", A); return true;
    case 0x0E: snprintf(o, sz, "Avance %.1f deg", A / 2.0f - 64.0f); return true;
    case 0x0F: snprintf(o, sz, "IAT %.0fC", A - 40.0f); return true;
    case 0x11: snprintf(o, sz, "TPS %.0f%%", A * 100.0f / 255.0f); return true;
    case 0x0C: if (l < 2) return false; snprintf(o, sz, "RPM %.0f", (256.0f * A + B) / 4.0f); return true;
    case 0x10: if (l < 2) return false; snprintf(o, sz, "MAF %.2f g/s", (256.0f * A + B) / 100.0f); return true;
    case 0x42: if (l < 2) return false; snprintf(o, sz, "Vbat %.2f V", (256.0f * A + B) / 1000.0f); return true;
    default:   return false;
  }
}

static void scanSupportedPids() {
  memset(supported, 0, sizeof(supported));
  Serial.println("\n[PIDs] Consultando PIDs soportados (Modo 01)...");
  uint8_t base = 0x00;
  int count = 0;
  while (true) {
    uint8_t d[8], l;
    if (!readPid(base, d, &l) || l < 4) {
      Serial.printf("  Sin respuesta para el PID 0x%02X, termino la busqueda.\n", base);
      break;
    }
    uint32_t mask = ((uint32_t)d[0] << 24) | ((uint32_t)d[1] << 16) | ((uint32_t)d[2] << 8) | d[3];
    for (int i = 0; i < 32; i++) {
      if (mask & (1UL << (31 - i))) {
        supported[(uint8_t)(base + 1 + i)] = true;
        count++;
      }
    }
    if (!(mask & 1) || base >= 0xE0) break;     // el bit 0 indica si existe el siguiente rango
    base += 0x20;
    delay(60);
  }

  Serial.printf("  %d PIDs soportados:\n", count);
  for (int pid = 1; pid < 256; pid++) {
    if (supported[pid]) Serial.printf("    0x%02X  %s\n", pid, pidName((uint8_t)pid));
  }

  uint8_t d[8], l;
  delay(60);
  if (supported[0x01] && readPid(0x01, d, &l) && l >= 1) {
    Serial.printf("  MIL: %s | DTCs almacenados: %d\n", (d[0] & 0x80) ? "ENCENDIDA" : "apagada", d[0] & 0x7F);
  }
}

static void printStatus() {
  Serial.println("\n==================================================");
  Serial.println(" ECU RESPONDE - comunicacion K-Line establecida");
  Serial.printf(" Protocolo : %s\n", protoName());
  Serial.printf(" Key bytes : 0x%02X 0x%02X\n", keyB1, keyB2);
  Serial.println("==================================================");
}

static void pollLive() {
  static const uint8_t LIVE[] = {0x0C, 0x0D, 0x05, 0x0F, 0x0B, 0x10, 0x11, 0x04, 0x0E, 0x06, 0x07, 0x42};
  static bool warned = false;
  char line[400];
  size_t pos = 0;
  int tried = 0, ok = 0;
  line[0] = 0;

  for (size_t i = 0; i < sizeof(LIVE); i++) {
    uint8_t pid = LIVE[i];
    if (!supported[pid]) continue;
    tried++;
    delay(55);                                  // P3 >= 55 ms entre peticiones
    uint8_t d[8], l;
    if (readPid(pid, d, &l)) {
      char buf[48];
      if (decodePid(pid, d, l, buf, sizeof(buf)) && pos < sizeof(line) - 50) {
        pos += snprintf(line + pos, sizeof(line) - pos, "%s | ", buf);
        ok++;
      }
    }
    if (failCount >= 5) {
      Serial.println("[!] Se perdio la comunicacion con la ECU.");
      connected = false;
      return;
    }
  }
  if (tried == 0) {
    if (!warned) { Serial.println("  Ninguno de los PIDs de datos en vivo esta soportado por esta ECU."); warned = true; }
    delay(55);
    uint8_t d[8], l;
    readPid(0x00, d, &l);                       // keep-alive
    if (failCount >= 5) connected = false;
    return;
  }
  if (ok) Serial.println(line);
}

// ---------------- Comandos ----------------
static void printHelp() {
  Serial.println("\nComandos: r=reconectar  p=releer PIDs  l=datos en vivo on/off  d=bytes crudos on/off  h=ayuda");
}

static void handleCommands() {
  while (Serial.available()) {
    char c = (char)Serial.read();
    switch (c) {
      case 'r': connected = false; Serial.println("\n[CMD] Reconectando..."); break;
      case 'p': if (connected) scanSupportedPids(); break;
      case 'l': liveOn = !liveOn; Serial.printf("\n[CMD] Datos en vivo: %s\n", liveOn ? "ON" : "OFF"); break;
      case 'd': debugHex = !debugHex; Serial.printf("\n[CMD] Bytes crudos: %s\n", debugHex ? "ON" : "OFF"); break;
      case 'h': printHelp(); break;
      default: break;
    }
  }
}

// ---------------- Arduino ----------------
void setup() {
  Serial.begin(115200);
  uint32_t t0 = millis();
  while (!Serial && millis() - t0 < 3000) delay(10);
  delay(200);
  Serial.println("\n=== Escaner OBD-II K-Line | ESP32-S3 + L9637D ===");
  Serial.println("Pon la llave en ON (contacto) antes de continuar.");
  printHelp();
}

void loop() {
  handleCommands();

  if (!connected) {
    if (connectEcu()) {
      connected = true;
      failCount = 0;
      printStatus();
      scanSupportedPids();
      debugHex = false;                         // silencia los bytes crudos para los datos en vivo
      if (liveOn) Serial.println("\n[LIVE] Datos en vivo (solo PIDs soportados). 'l' para pausar, 'd' para ver bytes crudos.");
    } else {
      Serial.println("\n[!] No se pudo establecer comunicacion con la ECU. Reintento en 3 s (comando 'r' para forzar).");
      uint32_t t = millis();
      while (millis() - t < 3000) { handleCommands(); delay(10); }
    }
    return;
  }

  if (liveOn) {
    pollLive();
  } else {
    // Keep-alive: la ECU cierra la sesion si pasan ~5 s sin peticiones (P3 max).
    if (millis() - lastActivity > 2000) {
      uint8_t d[8], l;
      readPid(0x00, d, &l);
      if (failCount >= 5) { Serial.println("[!] Se perdio la comunicacion con la ECU."); connected = false; }
    }
    delay(20);
  }
}
