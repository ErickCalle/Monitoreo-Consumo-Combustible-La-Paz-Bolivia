// ============================================================================
// K-Line (ISO 9141-2 / ISO 14230 KWP2000) simple -- ESP32-S3 + L9637D --
// lee solo RPM (PID 0x0C)
// ============================================================================
//
// Version minima, un solo archivo, sin libreria externa ninguna (solo
// Arduino core), para probar en el banco que el handshake con K-Line
// funciona y que se puede leer un PID. Es un subconjunto de
// CODIGOS/K_LINE/src/kline_obd2.cpp (el modulo completo, con web, SD,
// OLED, etc.) -- mismos pines, misma temporizacion, mismo formato de
// trama, verificados contra el datasheet del L9637D y el propio
// estandar ISO 9141-2:1994(E) (ver CODIGOS/K_LINE/README.md para las
// fuentes exactas).
//
// Intenta DOS metodos de inicializacion, uno despues del otro: el lento
// a 5 baudios (ISO9141-2) y, si ese no contesta nada, el "fast init" de
// ISO14230 (KWP2000). Esto no es opcional ni un capricho: el propio
// estandar ISO 14230-4:2000 (clausula 4.4, "StartCommunication
// service") dice textualmente que el ECU del vehiculo "shall only
// support ONE of the two following methods of initialisation" (5 baud
// o fast init, uno solo) -- por eso una herramienta de diagnostico
// real like un ELM327 siempre prueba los dos. El formato del fast init
// (bytes C1 33 F1 81 66 y su checksum) esta verificado cruzando varias
// fuentes independientes, con el checksum confirmado a mano en dos
// ejemplos reales distintos -- ver las notas junto a klineFastInit().
//
// Una vez que esto funcione y veas las RPM por el monitor serie, se
// agregan mas PIDs copiando el patron de requestPidSlowInit() /
// requestPidFastInit() segun cual de los dos init haya contestado --
// no hace falta reescribir nada del handshake.
//
// ----------------------------------------------------------------------
// CABLEADO (igual que CODIGOS/K_LINE/README.md):
//
//   +12V (pin 16 OBD-II) ----+------------------------+
//                             |                        |
//                        [510 ohm, 1/2W]             VS (pin 7, L9637D)
//                             |                        |
//   OBD-II pin 7 (K-Line) ----+------- K (pin 6, L9637D)
//
//   OBD-II pin 4/5 (GND) ----+------------------- GND (pin 5, L9637D)
//                              |
//                           ESP32-S3 GND
//
//   Rail 3,3V ------------------------------------ VCC (pin 3, L9637D)
//     (IMPORTANTE: VCC a 3,3V, NO a 5V -- el RX/LO del L9637D salen
//      hasta VCC, y el ESP32-S3 no tolera 5V en sus GPIO)
//
//   ESP32-S3 GPIO38 (TX) -------------------------- TX (pin 4, L9637D)
//   ESP32-S3 GPIO39 (RX) <------------------------- RX (pin 1, L9637D)
//                                        GND ------- LI (pin 8, no se usa L-line)
//                                        NC  ------- LO (pin 2, no se usa)
// ----------------------------------------------------------------------

#include <Arduino.h>

// ---- Pines --------------------------------------------------------------
static const int PIN_KLINE_TX = 38; // ESP32-S3 -> L9637D pin 4 (TX)
static const int PIN_KLINE_RX = 39; // ESP32-S3 <- L9637D pin 1 (RX)

// UART1 de hardware. Durante el init a 5 baudios estos mismos pines se
// controlan a mano con pinMode/digitalWrite; recien despues del
// handshake se le entrega el pin TX al periferico UART.
static HardwareSerial KlineSerial(1);

// ---- Temporizacion ISO 9141-2 (Anexo A, tablas A.1/A.2) ------------------
// Min/max oficiales del estandar; donde hace falta un solo numero para
// un delay() se usa un punto intermedio con margen hacia el lado seguro.
static const uint32_t KLINE_BIT_MS           = 200; // 1000/5 baudios
static const uint32_t W0_IDLE_MS             = 3;   // W0 >= 2 ms
static const uint32_t W1_SYNC_TIMEOUT_MS     = 400; // W1: 60-300 ms (+margen)
static const uint32_t W2_KW1_TIMEOUT_MS      = 60;  // W2: 5-20 ms (+margen)
static const uint32_t W3_KW2_TIMEOUT_MS      = 60;  // W3: 0-20 ms (+margen)
static const uint32_t W4_DELAY_MS            = 30;  // W4: 25-50 ms -> enviar en el medio
static const uint32_t W4_ECHO_TIMEOUT_MS     = 80;  // leer el eco de nuestro propio byte
static const uint32_t W4_ADDR_INV_TIMEOUT_MS = 100; // esperar ~0x33 del ECU
static const uint32_t P3_MIN_MS              = 60;  // P3 min = 55 ms (clause 12), +margen
static const uint32_t P4_BYTE_GAP_MS         = 10;  // P4: 5-20 ms entre bytes que ENVIAMOS
static const uint32_t RESPONSE_FIRST_BYTE_TIMEOUT_MS = 300; // P2(08) max=50ms +margen real
static const uint32_t RESPONSE_BYTE_GAP_TIMEOUT_MS   = 50;  // P1 max=20ms +margen

static const uint8_t KLINE_INIT_ADDRESS = 0x33; // direccion funcional OBD-II

// ---- Init lento a 5 baudios (ISO9141-2 clausula 7.2, Figura 4) -----------
// Bit de arranque (0), 8 bits de direccion LSB primero, bit de parada (1),
// cada uno sostenido 200 ms. Se hace a mano porque ningun UART baja de
// ~1200 baudios -- 5 baudios no es representable en hardware.
static void klineSendAddressSlow(uint8_t address) {
  pinMode(PIN_KLINE_TX, OUTPUT);
  digitalWrite(PIN_KLINE_TX, HIGH); // reposo = linea K liberada (pull-up de 510 ohm a VS)
  delay(W0_IDLE_MS);

  digitalWrite(PIN_KLINE_TX, LOW); // bit de arranque
  delay(KLINE_BIT_MS);

  for (int i = 0; i < 8; i++) { // 8 bits de datos, LSB primero
    bool bitHigh = (address >> i) & 0x1;
    digitalWrite(PIN_KLINE_TX, bitHigh ? HIGH : LOW);
    delay(KLINE_BIT_MS);
  }

  digitalWrite(PIN_KLINE_TX, HIGH); // bit de parada
  delay(KLINE_BIT_MS);
}

// Lee un byte con timeout corto; se usa tanto para el handshake como
// para descartar el eco de lo que el propio ESP32 transmite (el K-Line
// es un solo hilo: todo lo que este tester escribe se escucha a si
// mismo en RX un instante despues, ademas de lo que responda el ECU).
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

static bool klineWriteByteAndDiscardEcho(uint8_t b, uint32_t echoTimeout_ms) {
  KlineSerial.write(b);
  KlineSerial.flush();
  uint8_t echo;
  return klineReadByte(echo, echoTimeout_ms);
}

// Secuencia completa de inicializacion ISO9141-2 (clausulas 6 y 7,
// Figura 6 / tabla A.1): direccion a 5 baudios -> sync 0x55 -> KW1 ->
// KW2 -> complemento de KW2 (tester) -> complemento de la direccion
// (ECU). Imprime por donde se corta si algo falla, para depurar en el banco.
static bool klineSlowInit() {
  KlineSerial.end();
  klineSendAddressSlow(KLINE_INIT_ADDRESS);
  KlineSerial.begin(10400, SERIAL_8N1, PIN_KLINE_RX, PIN_KLINE_TX);

  uint8_t sync = 0;
  if (!klineReadByte(sync, W1_SYNC_TIMEOUT_MS) || sync != 0x55) {
    Serial.println("  init: no llego el byte de sincronismo 0x55");
    return false;
  }

  uint8_t kw1 = 0, kw2 = 0;
  if (!klineReadByte(kw1, W2_KW1_TIMEOUT_MS)) {
    Serial.println("  init: no llego la key word 1");
    return false;
  }
  if (!klineReadByte(kw2, W3_KW2_TIMEOUT_MS)) {
    Serial.println("  init: no llego la key word 2");
    return false;
  }

  delay(W4_DELAY_MS); // dentro de la ventana W4 (25-50 ms) antes de contestar
  if (!klineWriteByteAndDiscardEcho((uint8_t)(~kw2), W4_ECHO_TIMEOUT_MS)) {
    Serial.println("  init: no se pudo enviar/confirmar el complemento de KW2");
    return false;
  }

  uint8_t addrInv = 0;
  if (!klineReadByte(addrInv, W4_ADDR_INV_TIMEOUT_MS) || addrInv != (uint8_t)(~KLINE_INIT_ADDRESS)) {
    Serial.println("  init: no llego el complemento de la direccion (se esperaba 0xCC)");
    return false;
  }

  delay(P3_MIN_MS); // P3 min = 55 ms antes del primer mensaje (clause 12)
  Serial.printf("  init OK -- KW1=0x%02X KW2=0x%02X\n", kw1, kw2);
  return true;
}

// ---- Pedido/respuesta Modo 01 -- variante ISO9141-2 (clausula 11, tabla 1)
// Pedido: [0x68, 0x6A, 0xF1, 0x01, PID, checksum]
// Respuesta esperada: [0x48, 0x6B, SRC, 0x41, PID, datos..., checksum]
// Checksum = suma de 8 bits de todos los bytes anteriores, modulo 256.
// Se usa SOLO si el bus se inicializo con klineSlowInit().
static bool requestPidSlowInit(uint8_t pid, uint8_t *outData, uint8_t &outLen) {
  uint8_t msg[6] = {0x68, 0x6A, 0xF1, 0x01, pid, 0x00};
  uint8_t cs = 0;
  for (int i = 0; i < 5; i++) cs += msg[i];
  msg[5] = cs;

  for (int i = 0; i < 6; i++) {
    if (!klineWriteByteAndDiscardEcho(msg[i], W4_ECHO_TIMEOUT_MS)) return false;
    if (i < 5) delay(P4_BYTE_GAP_MS); // P4: 5-20 ms entre bytes del tester
  }

  uint8_t buf[11];
  uint8_t len = 0;
  uint8_t b;

  if (!klineReadByte(b, RESPONSE_FIRST_BYTE_TIMEOUT_MS)) return false; // primer byte: timeout largo (P2)
  buf[len++] = b;
  while (len < sizeof(buf)) {
    if (!klineReadByte(b, RESPONSE_BYTE_GAP_TIMEOUT_MS)) break; // fin del mensaje (P1)
    buf[len++] = b;
  }

  if (len < 6) return false; // header(3) + 0x41 + pid + checksum, minimo
  if (buf[0] != 0x48 || buf[1] != 0x6B || buf[3] != 0x41 || buf[4] != pid) return false;

  cs = 0;
  for (int i = 0; i < len - 1; i++) cs += buf[i];
  if (cs != buf[len - 1]) return false; // checksum invalido -> trama descartada

  outLen = len;
  memcpy(outData, buf, len);
  return true;
}

// ---- Fast init (ISO14230-4:2000 clausula 4.4 + ISO14230 KWP2000) --------
// Patron de reactivacion: linea K en reposo, despues 25 ms en bajo + 25 ms
// en alto (bit-banged, no por el UART -- nada que ver con los 5 baudios
// del otro metodo). Inmediatamente despues, el StartCommunication Service
// a 10400 baudios: pedido fijo [0xC1, 0x33, 0xF1, 0x81, 0x66] (format,
// target=0x33 funcional, source=0xF1 tester, servicio 0x81, checksum).
// El checksum 0x66 es siempre el mismo porque los 4 bytes anteriores son
// fijos: 0xC1+0x33+0xF1+0x81 = 0x266, modulo 256 = 0x66.
// Respuesta positiva esperada: [0x83, 0xF1, ECU, 0xC1, KB1, KB2, checksum]
// (formato 0x83 = 0x80 | 3 bytes de datos: 0xC1 + 2 key words).
static bool klineFastInit() {
  KlineSerial.end();
  pinMode(PIN_KLINE_TX, OUTPUT);
  digitalWrite(PIN_KLINE_TX, HIGH); // reposo
  delay(300); // bus en reposo antes del pulso de reactivacion

  digitalWrite(PIN_KLINE_TX, LOW);
  delay(25);
  digitalWrite(PIN_KLINE_TX, HIGH);
  delay(25);

  KlineSerial.begin(10400, SERIAL_8N1, PIN_KLINE_RX, PIN_KLINE_TX);

  const uint8_t req[5] = {0xC1, 0x33, 0xF1, 0x81, 0x66};
  for (int i = 0; i < 5; i++) {
    if (!klineWriteByteAndDiscardEcho(req[i], W4_ECHO_TIMEOUT_MS)) {
      Serial.println("  fast init: no se pudo enviar/confirmar el pedido StartCommunication");
      return false;
    }
    if (i < 4) delay(P4_BYTE_GAP_MS);
  }

  uint8_t buf[7];
  uint8_t len = 0;
  uint8_t b;
  if (!klineReadByte(b, RESPONSE_FIRST_BYTE_TIMEOUT_MS)) {
    Serial.println("  fast init: no llego respuesta al StartCommunication");
    return false;
  }
  buf[len++] = b;
  while (len < sizeof(buf)) {
    if (!klineReadByte(b, RESPONSE_BYTE_GAP_TIMEOUT_MS)) break;
    buf[len++] = b;
  }

  if (len < 6 || buf[1] != 0xF1 || buf[3] != 0xC1) {
    Serial.println("  fast init: respuesta invalida o incompleta al StartCommunication");
    return false;
  }

  uint8_t cs = 0;
  for (int i = 0; i < len - 1; i++) cs += buf[i];
  if (cs != buf[len - 1]) {
    Serial.println("  fast init: checksum invalido en la respuesta");
    return false;
  }

  delay(P3_MIN_MS);
  Serial.printf("  fast init OK -- ECU addr=0x%02X KB1=0x%02X KB2=0x%02X\n", buf[2], buf[4], buf[5]);
  return true;
}

// ---- Pedido/respuesta Modo 01 -- variante KWP2000 (ISO14230-4 clausula 4.2)
// A diferencia de ISO9141-2, el byte de formato codifica la cantidad de
// bytes de datos en sus 6 bits bajos (0xC0 | longitud para pedidos con
// direccionamiento funcional, 0x80 | longitud para respuestas con
// direccionamiento fisico) en vez de usar siempre 0x68/0x48 fijos.
// Pedido Modo 01 + 1 PID -> 2 bytes de datos -> formato = 0xC0|2 = 0xC2.
// Se usa SOLO si el bus se inicializo con klineFastInit().
static bool requestPidFastInit(uint8_t pid, uint8_t *outData, uint8_t &outLen) {
  uint8_t msg[6] = {0xC2, 0x33, 0xF1, 0x01, pid, 0x00};
  uint8_t cs = 0;
  for (int i = 0; i < 5; i++) cs += msg[i];
  msg[5] = cs;

  for (int i = 0; i < 6; i++) {
    if (!klineWriteByteAndDiscardEcho(msg[i], W4_ECHO_TIMEOUT_MS)) return false;
    if (i < 5) delay(P4_BYTE_GAP_MS);
  }

  uint8_t buf[11];
  uint8_t len = 0;
  uint8_t b;

  if (!klineReadByte(b, RESPONSE_FIRST_BYTE_TIMEOUT_MS)) return false;
  buf[len++] = b;
  while (len < sizeof(buf)) {
    if (!klineReadByte(b, RESPONSE_BYTE_GAP_TIMEOUT_MS)) break;
    buf[len++] = b;
  }

  // buf[0] = formato (0x80|longitud, no se valida el valor exacto de
  // longitud por si el ECU manda algun byte extra); buf[1] = target
  // (deberia ser 0xF1, el tester); buf[3] = 0x41 (respuesta positiva a
  // Modo 01); buf[4] = pid.
  if (len < 6) return false;
  if (buf[1] != 0xF1 || buf[3] != 0x41 || buf[4] != pid) return false;

  cs = 0;
  for (int i = 0; i < len - 1; i++) cs += buf[i];
  if (cs != buf[len - 1]) return false;

  outLen = len;
  memcpy(outData, buf, len);
  return true;
}

// ---------------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\nK-Line simple -- ESP32-S3 + L9637D -- lectura de RPM (PID 0x0C)");
}

void loop() {
  bool usingFastInit = false;

  Serial.println("Inicializando K-Line (5 baudios, ISO9141-2)...");
  if (klineSlowInit()) {
    usingFastInit = false;
  } else {
    Serial.println("Sin respuesta al init lento. Probando fast init (ISO14230/KWP2000)...");
    if (klineFastInit()) {
      usingFastInit = true;
    } else {
      Serial.println("Sin contacto por ninguno de los dos metodos. Reintentando en 2 s.\n");
      delay(2000);
      return;
    }
  }

  // Con el bus ya inicializado, se puede pedir PID 0x0C varias veces
  // seguidas (con el espaciado P3 entre pedidos) sin tener que repetir
  // el handshake cada vez.
  for (int i = 0; i < 20; i++) {
    uint8_t data[11];
    uint8_t len = 0;
    bool ok = usingFastInit ? requestPidFastInit(0x0C, data, len)
                             : requestPidSlowInit(0x0C, data, len);
    if (ok) {
      // PID 0x0C: RPM = ((A*256)+B)/4, A=data[5], B=data[6] -- mismo
      // offset en los dos formatos, ambos tienen header(3) + 0x41 + pid
      // antes de los bytes de datos.
      uint16_t rpm = ((uint16_t)data[5] << 8 | data[6]) / 4;
      Serial.printf("RPM: %u\n", rpm);
    } else {
      Serial.println("Sin respuesta al PID 0x0C.");
    }
    delay(P3_MIN_MS); // P3 min entre el fin de una respuesta y el siguiente pedido
  }

  Serial.println("Reinicializando bus...\n");
}
