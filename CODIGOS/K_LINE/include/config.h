#pragma once

// =====================================================================
// PIN MAP  (ESP32-S3 N16R8 -- GPIO26-37 are reserved for internal
// flash/octal-PSRAM and must NEVER be used here; 0/3/19/20/43-46 are
// strapping/USB/UART-console pins and are avoided too)
//
// Identico al config.h de esp32s3_obd2_speeddensity, salvo que
// PIN_CAN_TX/RX y los parametros OBD2/CAN se reemplazan por
// PIN_KLINE_TX/RX y los parametros K-Line (ver CODIGOS/K_LINE/README.md
// para el pinout completo del L9637D y por que VCC va a 3,3V).
// =====================================================================

// ---- K-Line (ISO 9141-2) -> L9637D ----------------------------------
#define PIN_KLINE_TX    38   // ESP32-S3 TX -> L9637D pin 4 (TX)
#define PIN_KLINE_RX    39   // ESP32-S3 RX <- L9637D pin 1 (RX)

// ---- I2C -> OLED SSD1306 -------------------------------------------
#define PIN_I2C_SDA     8
#define PIN_I2C_SCL     9
#define OLED_I2C_ADDR   0x3C
#define OLED_WIDTH      128
#define OLED_HEIGHT     64
#define OLED_RESET_PIN  -1   // shares ESP32 reset, no dedicated pin

// ---- SPI (dedicated bus) -> microSD ---------------------------------
#define PIN_SD_SCK      12
#define PIN_SD_MISO     11
#define PIN_SD_MOSI     13
#define PIN_SD_CS       14

// ---- Status LEDs (active HIGH) --------------------------------------
#define PIN_LED_CAN     15   // nombre heredado de can_obd2 -- aqui indica "bus K-Line OK"
#define PIN_LED_SD      16
#define PIN_LED_SERVER  17
#define PIN_LED_ERROR   18

// ---- Power-gate MOSFETs (active HIGH) -- rail 1 (ESP32-S3 + L9637D)
// siempre encendido; estos dos cortan la rail 2 completa sin "contacto",
// en vez de solo dejarla en reposo por software. Ambos GPIO0-21 son
// RTC-capable en el S3, necesario para que gpio_hold_en() retenga su
// estado durante el deep sleep.
#define PIN_PWR_LED_OLED  6   // LEDs + OLED
#define PIN_PWR_SD        10   // microSD

// =====================================================================
// K-Line / OBD2 (ISO 9141-2) -- ver kline_obd2.cpp y README.md para el
// detalle de cada constante (verificadas contra el propio estandar).
// =====================================================================
#define CORE_KLINE_TASK   0
#define PRIO_KLINE_TASK   5
#define STACK_KLINE_TASK  4096

// =====================================================================
// "Contacto" (llave en accesorios o mas) y deep sleep -- igual criterio
// que la version CAN: sin respuesta del ECU se asume "sin contacto" y
// el chip entra en deep sleep real, despertando solo por temporizador.
// =====================================================================
#define CONTACT_CHECK_RETRIES        3
#define CONTACT_LOST_DEBOUNCE_CYCLES 3

// Banco de pruebas SIN vehiculo conectado -- ver la nota identica en el
// config.h de esp32s3_obd2_speeddensity. Poner en 1 mientras se prueba
// en el banco sin auto; volver a 0 antes de instalar en el vehiculo.
#define FORCE_AWAKE_FOR_BENCH_TEST   1
#define DEEP_SLEEP_WAKE_INTERVAL_US  (20ULL * 1000000ULL)
#define POWER_RAIL_SETTLE_MS         200

// =====================================================================
// Engine parameters -- CALIBRATE THESE PER VEHICLE
//
// A diferencia de Vanette/Changan (config.h de esp32s3_obd2_speeddensity),
// este vehiculo K-Line todavia no tiene cilindrada real documentada en
// este proyecto. NO se pone un numero inventado aqui -- el build falla
// a proposito (#error) hasta que se pase el valor real por build_flags,
// ver platformio.ini / README.md. Esto es intencional: un numero de
// cilindrada equivocado arruina el calculo de consumo de forma
// silenciosa (no hay forma de notar el error solo mirando el resultado).
// =====================================================================
#if defined(VEHICLE_KLINE_CUSTOM)
  #ifndef ENGINE_DISPLACEMENT_L
    #error "Falta ENGINE_DISPLACEMENT_L: agrega -DENGINE_DISPLACEMENT_L=X.XXf (cilindrada REAL en litros de tu vehiculo K-Line) al build_flags de [env:kline] en platformio.ini antes de compilar. Ver README.md."
  #endif
#else
  #error "Definir VEHICLE_KLINE_CUSTOM (ver [env:kline] en platformio.ini)"
#endif

#define VOLUMETRIC_EFFICIENCY_DEFAULT  80.0f   // % , used when RPM falls outside the VE table
#define FUEL_AFR_STOICH                14.7f   // gasoline stoichiometric air/fuel ratio
#define FUEL_DENSITY_G_PER_L           745.0f  // gasoline ~0.745 kg/L
#define USE_FUEL_TRIM_CORRECTION       1       // apply STFT+LTFT to AFR estimate
#define FUEL_PRICE_BS_PER_L            6.96f   // precio surtidor, Bolivianos por litro -- AJUSTAR
#define FUEL_CALIBRATION_FACTOR        1.0f    // ajustar tras comparar litros reales de un
                                                // tanque lleno vs. trip_fuel_L calculado

// Igual criterio que la version CAN: el calculo speed-density ya usa la
// presion real del colector (MAP) en cada ciclo, asi que el consumo ya
// queda corregido por altitud sin ningun factor adicional. SITE_ALTITUDE_M
// solo alimenta el modelo ISA de respaldo para baro_kpa cuando el PID
// 0x33 no esta soportado -- se registra como dato de VALIDACION, nunca
// se usa para escalar fuel_gs. AJUSTAR a la altitud real de uso si no es La Paz.
#define SITE_ALTITUDE_M                3640.0f // La Paz, Bolivia (msnm aprox.)

// =====================================================================
// WiFi -- idem esp32s3_obd2_speeddensity.
// =====================================================================
#define WIFI_AP_SSID     "ESP32_KLINE"
#define WIFI_AP_PASS     "obd2trip123"   // >= 8 chars, required by WPA2
#define WIFI_AP_IP_HINT  "192.168.4.1"   // default ESP32 SoftAP IP, shown on OLED

#define WIFI_STA_SSID    ""              // leave empty to disable STA
#define WIFI_STA_PASS    ""
#define WIFI_STA_CONNECT_TIMEOUT_MS  8000

#define WEB_SERVER_PORT   80
#define WS_PUSH_PERIOD_MS 500            // live dashboard push rate

// =====================================================================
// SD logging -- idem esp32s3_obd2_speeddensity.
// =====================================================================
#define SD_LOG_DIR              "/logs"
#define SD_LOG_INTERVAL_MS      1000
#define SD_LOG_FILE_PREFIX      "trip_"
#define SD_LOG_FILE_EXT         ".csv"
#define SD_LOG_MAX_FILENAME_LEN 40

// =====================================================================
// OLED refresh
// =====================================================================
#define OLED_REFRESH_PERIOD_MS  400

// =====================================================================
// Task cores / priorities
// =====================================================================
#define CORE_WEBSOCK_TASK   0
#define CORE_DISPLAY_TASK   1
#define CORE_SD_TASK        1
#define CORE_LED_TASK       1

#define PRIO_SD_TASK        4
#define PRIO_WEBSOCK_TASK   3
#define PRIO_DISPLAY_TASK   2
#define PRIO_LED_TASK       1

#define STACK_SD_TASK        6144
#define STACK_DISPLAY_TASK   4096
#define STACK_LED_TASK       2048
#define STACK_WEBSOCK_TASK   4096
