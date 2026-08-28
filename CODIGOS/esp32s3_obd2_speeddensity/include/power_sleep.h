#pragma once

// Configures the LED/OLED and microSD power-gate MOSFETs as outputs, both
// off, releasing any GPIO hold left over from a previous deep sleep. Call
// once at the very top of setup(), before anything else touches those pins.
void powerGateInit();

// Drives both power-gate MOSFETs: true powers the LED+OLED rail and the
// microSD rail, false cuts both.
void powerGateSet(bool on);

// Closes any open SD file, stops WiFi, cuts both power-gate MOSFETs and
// holds them off through deep sleep, arms a timer wakeup, and puts the
// ESP32-S3 into deep sleep. Never returns -- the next code to run is
// setup(), from the top, once the timer fires.
void enterDeepSleepUntilContact();
