#pragma once

// Mounts the microSD card (dedicated SPI bus), creates /logs if needed
// and opens a new session CSV file (trip_NNN.csv). Reports
// ErrorCode::SD_FAIL and returns false on failure -- the rest of the
// firmware keeps running without logging in that case.
bool sdLoggerInit();

// FreeRTOS task: appends one CSV row every SD_LOG_INTERVAL_MS from
// g_vehicleData. Takes g_sdMutex around every card access so it can
// safely interleave with web_server.cpp reading history files.
void sdLoggerTask(void *pvParameters);

// Full path ("/logs/trip_003.csv") of the file being written this
// session, or "" if logging is not active. Caller must hold g_sdMutex
// only if it intends to open the file too; reading the path itself is
// safe without it (set once at init and never mutated afterwards).
const char *sdLoggerCurrentFile();

// Closes the current file and unmounts the card. Called by power_sleep
// before cutting the microSD's power rail. Safe to call multiple times.
void sdLoggerShutdown();
