#pragma once

void statusLedsInit();

// FreeRTOS task: drives the 4 indicator LEDs from g_systemStatus.
// CAN led = solid while OBD2 polling is healthy.
// SD led = pulses on every card read/write.
// Server led = solid once the web server + AP are up.
// Error led = blinks N times then pauses, N = ErrorCode (1=CAN,2=SD,3=OLED,4=WiFi).
void statusLedsTask(void *pvParameters);
