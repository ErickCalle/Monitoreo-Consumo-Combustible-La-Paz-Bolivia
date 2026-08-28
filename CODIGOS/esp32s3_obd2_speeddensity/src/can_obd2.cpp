// TWAI (CAN) driver + OBD2 Mode 01 polling (ISO 15765-4, single-frame
// requests/responses only -- every PID we need fits in one CAN frame,
// so no multi-frame ISO-TP flow-control is required).
#include <math.h>
#include "driver/twai.h"
#include "config.h"
#include "types.h"
#include "can_obd2.h"
#include "fuel_calc.h"
#include "power_sleep.h"

static const uint8_t kPollPids[] = {0x0C, 0x0D, 0x0B, 0x0F, 0x05, 0x06, 0x07, 0x04, 0x33};
static const size_t  kPollPidCount = sizeof(kPollPids) / sizeof(kPollPids[0]);

// ISA (Atmosfera Estandar Internacional) evaluada en SITE_ALTITUDE_M, usada
// solo como respaldo de baro_kpa cuando el PID 0x33 no esta soportado -- ver
// la nota en config.h: esto es un dato de validacion/registro, nunca un
// factor que se multiplique sobre el calculo de consumo.
static float isaPressureKpaAt(float altitude_m) {
  const float P0 = 101.325f;   // kPa
  const float T0 = 288.15f;    // K
  const float L  = 0.0065f;    // K/m
  const float g  = 9.80665f;   // m/s^2
  const float M  = 0.0289644f; // kg/mol
  const float R  = 8.31447f;   // J/(mol*K)
  return P0 * powf(1.0f - (L * altitude_m) / T0, (g * M) / (R * L));
}

// -----------------------------------------------------------------------
static bool sendPidRequest(uint8_t pid) {
  twai_message_t msg = {};
  msg.identifier = OBD2_REQUEST_ID;
  msg.extd = 0;
  msg.rtr = 0;
  msg.data_length_code = 8;
  msg.data[0] = 0x02; // SF, 2 following bytes (mode + pid)
  msg.data[1] = 0x01; // Mode 01: show current data
  msg.data[2] = pid;
  msg.data[3] = 0x00;
  msg.data[4] = 0x00;
  msg.data[5] = 0x00;
  msg.data[6] = 0x00;
  msg.data[7] = 0x00;
  return twai_transmit(&msg, pdMS_TO_TICKS(50)) == ESP_OK;
}

// Waits up to timeout_ms for the matching Mode-01 response to `pid`,
// silently discarding any other traffic seen on the bus meanwhile.
static bool receivePidResponse(uint8_t pid, uint8_t *outData, uint8_t &outLen, uint32_t timeout_ms) {
  uint32_t start = millis();
  twai_message_t msg;
  while ((millis() - start) < timeout_ms) {
    uint32_t elapsed = millis() - start;
    uint32_t remaining = (elapsed >= timeout_ms) ? 0 : (timeout_ms - elapsed);
    if (remaining == 0) break;
    if (twai_receive(&msg, pdMS_TO_TICKS(remaining)) != ESP_OK) break; // timeout / bus error
    if (!msg.extd &&
        msg.identifier >= OBD2_RESPONSE_ID_MIN && msg.identifier <= OBD2_RESPONSE_ID_MAX &&
        msg.data_length_code >= 3 &&
        msg.data[1] == 0x41 && msg.data[2] == pid) {
      outLen = msg.data_length_code;
      memcpy(outData, msg.data, outLen);
      return true;
    }
    // not the frame we're waiting for -> loop again with the time left
  }
  return false;
}

static void decodeAndStore(uint8_t pid, const uint8_t *data, uint8_t len, VehicleData &vd) {
  switch (pid) {
    case 0x0C: // RPM, 2 bytes A,B -> ((A*256)+B)/4
      if (len >= 5) vd.rpm = ((uint16_t)data[3] << 8 | data[4]) / 4;
      break;
    case 0x0D: // Vehicle speed, km/h
      if (len >= 4) vd.speed_kmh = data[3];
      break;
    case 0x0B: // Intake manifold absolute pressure, kPa
      if (len >= 4) vd.map_kpa = data[3];
      break;
    case 0x0F: // Intake air temperature, C
      if (len >= 4) vd.iat_c = (float)data[3] - 40.0f;
      break;
    case 0x05: // Engine coolant temperature, C
      if (len >= 4) vd.coolant_c = (float)data[3] - 40.0f;
      break;
    case 0x04: // Calculated engine load, %
      if (len >= 4) vd.load_pct = data[3] * 100.0f / 255.0f;
      break;
    case 0x06: // Short term fuel trim bank1, %
      if (len >= 4) vd.stft_pct = ((float)data[3] - 128.0f) * 100.0f / 128.0f;
      break;
    case 0x07: // Long term fuel trim bank1, %
      if (len >= 4) vd.ltft_pct = ((float)data[3] - 128.0f) * 100.0f / 128.0f;
      break;
    case 0x33: // Barometric pressure, kPa -- logged/displayed for sensor
               // validation only (compare vs. MAP at key-on/engine-off, or
               // vs. the ISA estimate); never fed into fuel_calc.
      if (len >= 4) {
        vd.baro_kpa = data[3];
        vd.baro_is_estimated = false;
      }
      break;
    default:
      break;
  }
}

// Queries PID 0x00 (supported PIDs 01-20 bitmask) once at startup so we
// can skip PIDs the ECU doesn't implement instead of always timing out
// on them. If the query itself fails (e.g. bus not ready yet) we just
// assume everything is supported and let per-PID timeouts handle it.
static void queryPidSupport(VehicleData &vd) {
  uint8_t data[8];
  uint8_t len = 0;
  if (!sendPidRequest(0x00) || !receivePidResponse(0x00, data, len, 300) || len < 7) {
    return; // keep defaults (assume supported)
  }
  uint32_t bitmask = ((uint32_t)data[3] << 24) | ((uint32_t)data[4] << 16) |
                      ((uint32_t)data[5] << 8) | data[6];
  auto supported = [&](uint8_t p) { return (bitmask >> (32 - p)) & 0x1; };
  vd.pid_rpm_supported   = supported(0x0C);
  vd.pid_map_supported   = supported(0x0B);
  vd.pid_iat_supported   = supported(0x0F);
  vd.pid_speed_supported = supported(0x0D);
}

// PID 0x33 falls in the 0x21-0x40 range, outside the 0x00 bitmask queried
// above (which only covers 0x01-0x20), so its support is settled directly
// with a one-shot request/response instead of a bitmask bit.
static void queryBaroSupport(VehicleData &vd) {
  uint8_t data[8];
  uint8_t len = 0;
  vd.pid_baro_supported = sendPidRequest(0x33) && receivePidResponse(0x33, data, len, 300);
}

// One lightweight ping ("does anything answer at all") used both by the
// power-on gate in main.cpp and by the runtime contact-lost check below --
// RPM is a mandatory PID on every OBD2 ECU, so it doubles as a generic
// "is the bus alive" probe without needing a dedicated PID for it.
bool canObd2CheckContact() {
  uint8_t data[8];
  uint8_t len = 0;
  return sendPidRequest(0x0C) && receivePidResponse(0x0C, data, len, OBD2_PID_TIMEOUT_MS);
}

// -----------------------------------------------------------------------
bool canObd2Init() {
  twai_general_config_t g_config =
      TWAI_GENERAL_CONFIG_DEFAULT(PIN_CAN_TX, PIN_CAN_RX, TWAI_MODE_NORMAL);
  twai_timing_config_t t_config = TWAI_TIMING_CONFIG_500KBITS();
  // Accept everything in software (receivePidResponse filters by ID/PID);
  // simpler and just as correct as a hardware acceptance mask here.
  twai_filter_config_t f_config = TWAI_FILTER_CONFIG_ACCEPT_ALL();

  if (twai_driver_install(&g_config, &t_config, &f_config) != ESP_OK) {
    systemReportError(ErrorCode::CAN_INIT_FAIL);
    return false;
  }
  if (twai_start() != ESP_OK) {
    systemReportError(ErrorCode::CAN_INIT_FAIL);
    return false;
  }
  twai_reconfigure_alerts(TWAI_ALERT_BUS_OFF | TWAI_ALERT_ERR_PASS, nullptr);
  return true;
}

// Non-blocking bus-off recovery. twai_initiate_recovery() only moves the
// controller from BUS_OFF to RECOVERING; per the ESP-IDF TWAI driver it
// only reaches STOPPED (the state twai_start() actually requires) after
// 128 occurrences of 11 consecutive recessive bits on the bus, which can
// take much longer than any fixed delay on a busy bus. This is polled
// once per canObd2Task iteration instead of blocking, and keeps retrying
// twai_start() every call until it actually succeeds.
static bool s_recoveryInProgress = false;

static twai_state_t handleBusRecoveryIfNeeded() {
  twai_status_info_t status;
  if (twai_get_status_info(&status) != ESP_OK) return TWAI_STATE_RUNNING; // unknown -> don't block on it

  if (status.state == TWAI_STATE_BUS_OFF) {
    if (!s_recoveryInProgress) {
      twai_initiate_recovery();
      s_recoveryInProgress = true;
    }
  } else if (s_recoveryInProgress && status.state == TWAI_STATE_STOPPED) {
    if (twai_start() == ESP_OK) {
      s_recoveryInProgress = false;
    }
    // else: still not ready, next call will retry
  } else if (s_recoveryInProgress && status.state == TWAI_STATE_RUNNING) {
    s_recoveryInProgress = false; // recovered through some other path
  }
  return status.state;
}

void canObd2Task(void *pvParameters) {
  (void)pvParameters;

  // Snapshot support flags once; the ECU's PID support list doesn't
  // change at runtime.
  VehicleData localSupport;
  queryPidSupport(localSupport);
  queryBaroSupport(localSupport);

  uint32_t lastCycleMs = millis();
  uint8_t data[8];
  uint8_t len = 0;
  uint8_t noResponseStreak = 0;

  for (;;) {
    twai_state_t busState = handleBusRecoveryIfNeeded();

    // Raw PID results are accumulated in a local scratch struct during
    // the ~0.2-1.4s poll window. g_vehicleData/g_dataMutex are only
    // touched in the brief merge step at the end of the cycle -- this
    // is what stops a concurrent write (e.g. the web UI's /api/reset)
    // from ever being clobbered by data staged before it landed.
    VehicleData scratch;
    // Seeded with the ISA estimate up front so a vehicle without PID 0x33
    // (or a single dropped frame for it this cycle) still logs a usable
    // baro_kpa; decodeAndStore() overwrites both fields with the real
    // reading and baro_is_estimated=false the moment 0x33 actually answers.
    scratch.baro_kpa = isaPressureKpaAt(SITE_ALTITUDE_M);
    scratch.baro_is_estimated = true;
    bool anyResponse = false;
    bool criticalOk = true; // RPM, MAP, IAT, speed all answered (or aren't supported)

    for (size_t i = 0; i < kPollPidCount; i++) {
      uint8_t pid = kPollPids[i];
      bool isCritical = (pid == 0x0C || pid == 0x0B || pid == 0x0F || pid == 0x0D);
      bool supported = true;
      if (pid == 0x0C) supported = localSupport.pid_rpm_supported;
      else if (pid == 0x0B) supported = localSupport.pid_map_supported;
      else if (pid == 0x0F) supported = localSupport.pid_iat_supported;
      else if (pid == 0x0D) supported = localSupport.pid_speed_supported;
      else if (pid == 0x33) supported = localSupport.pid_baro_supported;

      if (!supported) {
        // A critical value we can never get makes this cycle invalid --
        // speed-density cannot run without RPM/MAP/IAT/speed.
        if (isCritical) criticalOk = false;
        continue;
      }

      if (sendPidRequest(pid) && receivePidResponse(pid, data, len, OBD2_PID_TIMEOUT_MS)) {
        decodeAndStore(pid, data, len, scratch);
        anyResponse = true;
      } else if (isCritical) {
        criticalOk = false;
      }
      vTaskDelay(pdMS_TO_TICKS(OBD2_CYCLE_PERIOD_MS));
    }

    uint32_t now = millis();
    float dt = (now - lastCycleMs) / 1000.0f;
    lastCycleMs = now;

    CanStatus status;
    if (busState == TWAI_STATE_BUS_OFF) status = CanStatus::BUS_OFF;
    else if (criticalOk) status = CanStatus::OK;
    else if (anyResponse) status = CanStatus::BUS_ERROR;  // bus alive, but a critical PID didn't answer
    else status = CanStatus::NO_RESPONSE;                 // ECU completely silent

    // fuelCalcUpdate() reads/writes g_vehicleData.trip_* in place while
    // this mutex is held, which is also what handleReset() (web_server.cpp)
    // takes before calling fuelCalcResetTrip() -- so the two can never
    // interleave (see the invariant documented in fuel_calc.h).
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
      g.pid_rpm_supported = localSupport.pid_rpm_supported;
      g.pid_map_supported = localSupport.pid_map_supported;
      g.pid_iat_supported = localSupport.pid_iat_supported;
      g.pid_speed_supported = localSupport.pid_speed_supported;
      g.pid_baro_supported = localSupport.pid_baro_supported;
      g.can_status = status;
      g.data_valid = criticalOk;
      g.last_update_ms = now;

      if (criticalOk && dt > 0.0f && dt < 5.0f) {
        fuelCalcUpdate(g, dt);
      }
      xSemaphoreGive(g_dataMutex);
    }

    g_systemStatus.can_ok = criticalOk;

    // "Sin contacto" (no CAN response at all) sustained for a few cycles
    // in a row -- not just one, so a single dropped frame on a busy bus
    // doesn't send the whole board to sleep -- means the ignition just
    // went off. enterDeepSleepUntilContact() closes the SD file, cuts the
    // LED/OLED and microSD MOSFETs and never returns; the next "boot" is
    // the timer waking the chip back up to check again.
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
