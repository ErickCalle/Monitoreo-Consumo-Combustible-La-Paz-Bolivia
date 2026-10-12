#include <SD.h>
#include <SPI.h>
#include <string.h>
#include "config.h"
#include "types.h"
#include "sd_logger.h"

static SPIClass sdSPI(FSPI);
static bool     s_ready = false;
static File     s_logFile;
static char     s_logPath[SD_LOG_MAX_FILENAME_LEN] = "";

static void pulseSdLed() {
  g_systemStatus.sd_activity_until_ms = millis() + 120;
}

// Scans /logs for existing trip_NNN.csv files and returns the next
// free index, so a fresh file is created every boot without needing a
// separate counter file (which could get out of sync after a crash).
static int findNextIndex() {
  int maxIdx = 0;
  File dir = SD.open(SD_LOG_DIR);
  if (!dir || !dir.isDirectory()) {
    if (dir) dir.close();
    return 1;
  }
  File f = dir.openNextFile();
  while (f) {
    if (!f.isDirectory()) {
      String name = f.name();
      int slash = name.lastIndexOf('/');
      if (slash >= 0) name = name.substring(slash + 1);
      if (name.startsWith(SD_LOG_FILE_PREFIX)) {
        String numPart = name.substring(strlen(SD_LOG_FILE_PREFIX));
        int dot = numPart.indexOf('.');
        if (dot > 0) numPart = numPart.substring(0, dot);
        int idx = numPart.toInt();
        if (idx > maxIdx) maxIdx = idx;
      }
    }
    f.close();
    f = dir.openNextFile();
  }
  dir.close();
  return maxIdx + 1;
}

bool sdLoggerInit() {
  sdSPI.begin(PIN_SD_SCK, PIN_SD_MISO, PIN_SD_MOSI, PIN_SD_CS);

  if (xSemaphoreTake(g_sdMutex, pdMS_TO_TICKS(2000)) != pdTRUE) {
    systemReportError(ErrorCode::SD_FAIL);
    return false;
  }

  bool ok = SD.begin(PIN_SD_CS, sdSPI);
  if (ok) {
    if (!SD.exists(SD_LOG_DIR)) {
      SD.mkdir(SD_LOG_DIR);
    }
    int idx = findNextIndex();
    snprintf(s_logPath, sizeof(s_logPath), "%s/%s%03d%s", SD_LOG_DIR, SD_LOG_FILE_PREFIX, idx, SD_LOG_FILE_EXT);

    s_logFile = SD.open(s_logPath, FILE_WRITE);
    if (s_logFile) {
      s_logFile.println(
          "uptime_ms,rpm,speed_kmh,map_kpa,iat_c,coolant_c,ve_pct,maf_gs,"
          "fuel_gs,instant_Lh,instant_L100km,trip_km,trip_fuel_L,trip_avg_L100km,can_status,"
          "trip_cost_bs,baro_kpa,baro_is_estimated");
      s_logFile.flush();
      pulseSdLed();
    } else {
      ok = false;
    }
  }
  xSemaphoreGive(g_sdMutex);

  s_ready = ok;
  g_systemStatus.sd_ok = s_ready;
  if (!s_ready) systemReportError(ErrorCode::SD_FAIL);
  return s_ready;
}

const char *sdLoggerCurrentFile() {
  return s_logPath;
}

// Closes the open trip file cleanly before power_sleep cuts the microSD's
// MOSFET -- pulling power out from under an open file risks corrupting the
// filesystem, not just losing the last row. Safe to call even if nothing
// was ever open (idempotent).
void sdLoggerShutdown() {
  if (xSemaphoreTake(g_sdMutex, pdMS_TO_TICKS(1000)) == pdTRUE) {
    if (s_logFile) s_logFile.close();
    SD.end();
    xSemaphoreGive(g_sdMutex);
  }
  s_ready = false;
  g_systemStatus.sd_ok = false;
}

void sdLoggerTask(void *pvParameters) {
  (void)pvParameters;
  TickType_t lastWake = xTaskGetTickCount();
  for (;;) {
    vTaskDelayUntil(&lastWake, pdMS_TO_TICKS(SD_LOG_INTERVAL_MS));
    if (!s_ready) continue;

    VehicleData vd;
    bool have = false;
    if (xSemaphoreTake(g_dataMutex, pdMS_TO_TICKS(50)) == pdTRUE) {
      vd = g_vehicleData;
      have = true;
      xSemaphoreGive(g_dataMutex);
    }
    if (!have || !vd.data_valid) continue; // skip rows before the first good CAN cycle

    char line[256];
    snprintf(line, sizeof(line),
             "%lu,%u,%.1f,%.1f,%.1f,%.1f,%.1f,%.2f,%.3f,%.2f,%.2f,%.3f,%.4f,%.2f,%d,%.2f,%.1f,%d",
             (unsigned long)millis(), (unsigned)vd.rpm, vd.speed_kmh, vd.map_kpa, vd.iat_c,
             vd.coolant_c, vd.ve_pct, vd.maf_calc_gs, vd.fuel_gs, vd.instant_Lh, vd.instant_L100km,
             vd.trip_distance_km, vd.trip_fuel_L, vd.trip_avg_L100km, (int)vd.can_status,
             vd.trip_fuel_L * FUEL_PRICE_BS_PER_L, vd.baro_kpa, (int)vd.baro_is_estimated);

    if (xSemaphoreTake(g_sdMutex, pdMS_TO_TICKS(300)) == pdTRUE) {
      if (s_logFile) {
        s_logFile.println(line);
        s_logFile.flush();
        pulseSdLed();
      }
      xSemaphoreGive(g_sdMutex);
    }
  }
}
