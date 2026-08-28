#pragma once

// =====================================================================
// PIN MAP  (ESP32-S3 N16R8 -- GPIO26-37 are reserved for internal
// flash/octal-PSRAM and must NEVER be used here; 0/3/19/20/43-46 are
// strapping/USB/UART-console pins and are avoided too)
// =====================================================================

// ---- TWAI (CAN) -> SN65HVD230 -------------------------------------
#define PIN_CAN_TX      GPIO_NUM_4
#define PIN_CAN_RX      GPIO_NUM_5

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
#define PIN_LED_CAN     15
#define PIN_LED_SD      16
#define PIN_LED_SERVER  17
#define PIN_LED_ERROR   18

// ---- Power-gate MOSFETs (active HIGH) -- rail 1 (ESP32-S3 + SN65HVD230)
// is always on; these two switch rail 2 off entirely with no "contacto",
// vs. just idling it in software. Both GPIO0-21 are RTC-capable on the
// S3, needed so gpio_hold_en() can latch their state through deep sleep.
#define PIN_PWR_LED_OLED  6   // LEDs + OLED
#define PIN_PWR_SD        10   // microSD

// =====================================================================
// CAN / OBD2
// =====================================================================
#define OBD2_TWAI_BITRATE_500K   1
#define OBD2_REQUEST_ID          0x7DF   // functional broadcast request
#define OBD2_RESPONSE_ID_MIN     0x7E8   // ECU replies use 0x7E8-0x7EF
#define OBD2_RESPONSE_ID_MAX     0x7EF
#define OBD2_PID_TIMEOUT_MS      150     // wait per PID before giving up
#define OBD2_CYCLE_PERIOD_MS     20      // spacing between requests inside a poll cycle

// =====================================================================
// "Contacto" (llave en accesorios o mas) y deep sleep -- rail 1 (ESP32-S3
// + SN65HVD230) esta siempre alimentada desde el pin 16 del OBD2 (12V
// constante), asi que sin una linea de 12V conmutada del vehiculo la unica
// forma de saber si hay contacto es preguntandole al bus CAN. Sin
// respuesta -> se asume que no hay contacto y el chip entra en deep sleep
// real, despertando solo por temporizador para volver a preguntar.
// =====================================================================
#define CONTACT_CHECK_RETRIES        3        // intentos al arrancar antes de asumir "sin contacto"
#define CONTACT_LOST_DEBOUNCE_CYCLES 3        // ciclos NO_RESPONSE seguidos, ya despierto, antes de volver a dormir

// Banco de pruebas SIN vehiculo conectado (p.ej. el devkit suelto, sin
// SN65HVD230 respondiendo nada): sin esto, el chip nunca ve "contacto" y
// entra en deep sleep casi de inmediato -- lo que apaga el USB nativo y
// hace que el puerto COM se conecte/desconecte en loop cada
// DEEP_SLEEP_WAKE_INTERVAL_US. Poner en 1 mientras se prueba en el banco
// sin auto; volver a 0 antes de instalar en el vehiculo.
#define FORCE_AWAKE_FOR_BENCH_TEST   1
#define DEEP_SLEEP_WAKE_INTERVAL_US  (20ULL * 1000000ULL)  // cada cuanto se despierta a revisar de nuevo
#define POWER_RAIL_SETTLE_MS         200      // espera a que el 3.3V de perifericos se estabilice

// =====================================================================
// Engine parameters -- CALIBRATE THESE PER VEHICLE
//
// El vehiculo se selecciona con un build flag en platformio.ini
// ([env:vanette] / [env:changan]), no editando estas lineas a mano --
// asi se evita repetir el error de cilindrada que tenia esta constante
// (1.6f en vez de 1.626f) antes de calibrar contra datos reales.
// =====================================================================
#if defined(VEHICLE_CHANGAN)
  #define ENGINE_DISPLACEMENT_L        1.298f  // liters -- Changan Honor real (Tabla 4.4, 1298 mL)
#elif defined(VEHICLE_VANETTE)
  #define ENGINE_DISPLACEMENT_L        1.626f  // liters -- Nissan Vanette real (Tabla 4.4, 1626 mL)
#else
  #error "Definir VEHICLE_VANETTE o VEHICLE_CHANGAN (ver los entornos [env:vanette]/[env:changan] en platformio.ini)"
#endif

#define VOLUMETRIC_EFFICIENCY_DEFAULT  80.0f   // % , used when RPM falls outside the VE table
#define FUEL_AFR_STOICH                14.7f   // gasoline stoichiometric air/fuel ratio
#define FUEL_DENSITY_G_PER_L           745.0f  // gasoline ~0.745 kg/L
#define USE_FUEL_TRIM_CORRECTION       1       // apply STFT+LTFT to AFR estimate
#define FUEL_PRICE_BS_PER_L            6.96f   // precio surtidor, Bolivianos por litro
#define FUEL_CALIBRATION_FACTOR        1.0f    // ajustar tras comparar litros reales de un
                                                // tanque lleno vs. trip_fuel_L calculado

// El calculo speed-density ya usa la presion real del colector (MAP, PID
// 0x0B) en cada ciclo, asi que la densidad del aire -- y por lo tanto el
// consumo -- ya queda corregida por altitud sin ningun factor adicional:
// a mariposa cerrada el MAP nunca puede superar la presion atmosferica
// real, sea cual sea esta. SITE_ALTITUDE_M solo alimenta el modelo ISA de
// respaldo para estimar la presion barometrica (baro_kpa) cuando el PID
// 0x33 no esta soportado; baro_kpa se registra en el CSV y se expone en
// el panel web unicamente como dato de VALIDACION -- comparar contra el
// MAP leido con el motor apagado y el contacto puesto (ahi MAP ~= presion
// atmosferica real) -- nunca se usa para escalar fuel_gs.
#define SITE_ALTITUDE_M                3640.0f // La Paz, Bolivia (msnm aprox.)

// =====================================================================
// WiFi -- ESP32 always runs its own Access Point (guaranteed local
// access); optionally also joins a home router (STA) if credentials
// are set, purely so NTP time-sync can work for nicer CSV timestamps.
// =====================================================================
#define WIFI_AP_SSID     "ESP32_OBD2"
#define WIFI_AP_PASS     "obd2trip123"   // >= 8 chars, required by WPA2
#define WIFI_AP_IP_HINT  "192.168.4.1"   // default ESP32 SoftAP IP, shown on OLED

#define WIFI_STA_SSID    ""              // leave empty to disable STA
#define WIFI_STA_PASS    ""
#define WIFI_STA_CONNECT_TIMEOUT_MS  8000

#define WEB_SERVER_PORT   80
#define WS_PUSH_PERIOD_MS 500            // live dashboard push rate

// =====================================================================
// SD logging
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
#define CORE_CAN_TASK       0
#define CORE_WEBSOCK_TASK   0
#define CORE_DISPLAY_TASK   1
#define CORE_SD_TASK        1
#define CORE_LED_TASK       1

#define PRIO_CAN_TASK       5
#define PRIO_SD_TASK        4
#define PRIO_WEBSOCK_TASK   3
#define PRIO_DISPLAY_TASK   2
#define PRIO_LED_TASK       1

#define STACK_CAN_TASK       4096
#define STACK_SD_TASK        6144
#define STACK_DISPLAY_TASK   4096
#define STACK_LED_TASK       2048
#define STACK_WEBSOCK_TASK   4096
