#pragma once

// Initializes I2C + SSD1306. Returns true on success (reports
// ErrorCode::OLED_FAIL and returns false otherwise).
bool displayInit();

// FreeRTOS task: periodically redraws the OLED from g_vehicleData.
void displayTask(void *pvParameters);
