#pragma once
#include <Arduino.h>
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "config.h" // VOLUMETRIC_EFFICIENCY_DEFAULT used as a default member initializer below

enum class CanStatus : uint8_t { INIT = 0, OK = 1, NO_RESPONSE = 2, BUS_ERROR = 3, BUS_OFF = 4 };

// Blink codes on the ERROR led (used when no serial console is attached)
enum class ErrorCode : uint8_t {
  NONE = 0,
  CAN_INIT_FAIL = 1,
  SD_FAIL       = 2,
  OLED_FAIL     = 3,
  WIFI_FAIL     = 4
};

// ---------------------------------------------------------------------
// Shared vehicle/telemetry snapshot.
// Written by the CAN task (raw PIDs) and the fuel-calc step (derived
// values), read by the display, SD logger and web server tasks.
// ALWAYS take g_dataMutex before touching this struct.
// ---------------------------------------------------------------------
struct VehicleData {
  // ---- raw OBD2 values ----
  uint16_t rpm        = 0;
  float    speed_kmh  = 0;
  float    map_kpa    = 0;
  float    iat_c      = 0;
  float    coolant_c  = 0;
  float    load_pct   = 0;
  float    stft_pct   = 0;
  float    ltft_pct   = 0;
  float    baro_kpa   = 0;   // real PID 0x33, or ISA estimate for SITE_ALTITUDE_M if unsupported

  bool     pid_rpm_supported   = true;
  bool     pid_map_supported   = true;
  bool     pid_iat_supported   = true;
  bool     pid_speed_supported = true;
  // No "assume supported" default here: 0x33 falls outside the PID 0x00
  // bitmask (covers 0x01-0x20 only), so support is settled by a one-shot
  // probe in queryPidSupport() instead of a bitmask bit.
  bool     pid_baro_supported  = false;
  bool     baro_is_estimated   = false; // true when baro_kpa comes from the ISA fallback, not the ECU

  // ---- speed-density derived values ----
  float ve_pct         = VOLUMETRIC_EFFICIENCY_DEFAULT;
  float maf_calc_gs     = 0;   // calculated intake air mass flow, g/s
  float fuel_gs         = 0;   // calculated fuel mass flow, g/s
  float instant_Lh       = 0;   // instantaneous consumption, L/h
  float instant_L100km   = 0;   // instantaneous consumption, L/100km (0 while stopped)

  // ---- trip integration ----
  double   trip_distance_km = 0;
  double   trip_fuel_L      = 0;
  double   trip_avg_L100km  = 0;
  uint32_t trip_time_s      = 0;

  CanStatus can_status   = CanStatus::INIT;
  uint32_t  last_update_ms = 0;
  bool      data_valid    = false;
};

// ---------------------------------------------------------------------
// Lightweight status flags driving the 4 indicator LEDs.
// Only simple scalar fields set from single producer tasks -> plain
// volatile is enough, no mutex needed for these.
// ---------------------------------------------------------------------
struct SystemStatus {
  volatile bool      can_ok           = false; // recent successful OBD2 poll
  volatile uint32_t  sd_activity_until_ms = 0;  // LED task keeps SD led on until millis() passes this
  volatile bool      sd_ok            = false;
  volatile bool      server_active    = false;
  volatile ErrorCode error_code       = ErrorCode::NONE;
};

// Globals shared across tasks (defined in main.cpp)
extern VehicleData      g_vehicleData;
extern SystemStatus     g_systemStatus;
extern SemaphoreHandle_t g_dataMutex; // protects g_vehicleData
extern SemaphoreHandle_t g_sdMutex;   // protects the microSD SPI bus (shared by sd_logger + web_server)

// Helper: raise an error code + light the error LED pattern. Does not
// touch data/sd mutexes so it is safe to call from any task/ISR-free context.
void systemReportError(ErrorCode code);
