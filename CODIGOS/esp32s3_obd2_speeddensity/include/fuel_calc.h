#pragma once
#include "types.h"

// IMPORTANT: fuelCalcUpdate() and fuelCalcResetTrip() must only ever be
// called by a caller that already holds g_dataMutex, and must be called
// directly on g_vehicleData (not a local copy taken before the lock).
// Both functions read/write the file-scope trip-clock statics in
// fuel_calc.cpp; g_dataMutex is what serializes those accesses across
// tasks (there is no separate lock on the statics themselves). See
// can_obd2.cpp's canObd2Task (merges into g_vehicleData then calls this
// while holding the mutex) and web_server.cpp's handleReset() for the
// two call sites.

// Runs the speed-density fuel consumption calculation using the latest
// raw PID values already stored in vd, writes the derived fields back
// into vd (ve_pct, maf_calc_gs, fuel_gs, instant_Lh, instant_L100km) and
// integrates the trip_* totals by dt_seconds.
void fuelCalcUpdate(VehicleData &vd, float dt_seconds);

// Linear-interpolated Volumetric Efficiency (%) for a given RPM from
// the calibration table in fuel_calc.cpp. Exposed mainly for the web
// dashboard / diagnostics.
float fuelCalcVeForRpm(uint16_t rpm);

// Zeroes the trip_* accumulators and restarts the internal trip clock.
void fuelCalcResetTrip(VehicleData &vd);
