// Speed-Density fuel consumption calculation. Identico al fuel_calc.cpp
// de esp32s3_obd2_speeddensity -- la formula no depende de si los PIDs
// llegaron por CAN o por K-Line, solo de los valores ya decodificados
// en VehicleData. Unico cambio real: la tabla kVeTable de abajo, que es
// por vehiculo.
//
//   MAF(g/s) = (VE/100) * RPM * MAP(kPa) * Vd(L) * 28.97
//              --------------------------------------------
//                    2 * 8.314 * IAT(K) * 60
#include <Arduino.h>
#include "config.h"
#include "types.h"
#include "fuel_calc.h"

struct VePoint { uint16_t rpm; float ve_pct; };

// VEHICLE_KLINE_CUSTOM: sin PID 0x10 (MAF) confirmado todavia y sin
// corrida de calibracion real sobre este vehiculo -- se parte de la
// MISMA tabla generica de literatura ya usada como punto de partida
// para el Changan Honor en esp32s3_obd2_speeddensity/src/fuel_calc.cpp
// (sin datos reales de este motor en particular). Calibrarla en cuanto
// se tenga: si el ECU soporta PID 0x10, repetir el procedimiento de
// CODIGOS/calibrate_ve_table.py + CODIGOS/ve_curve_calibrator.py
// (Seccion 4.3.3 del Capitulo 4); si no, usar la ruta indirecta por
// STFT/LTFT descrita en la Seccion "Caso sin MAF" del Capitulo 3.
static const VePoint kVeTable[] = {
  { 700,  60.0f},
  {1500,  74.0f},
  {2500,  85.0f},
  {4000,  88.0f},
  {5500,  83.0f},
  {7000,  74.0f},
};
static const size_t kVeTableLen = sizeof(kVeTable) / sizeof(kVeTable[0]);

float fuelCalcVeForRpm(uint16_t rpm) {
  if (rpm <= kVeTable[0].rpm) return kVeTable[0].ve_pct;
  if (rpm >= kVeTable[kVeTableLen - 1].rpm) return kVeTable[kVeTableLen - 1].ve_pct;

  for (size_t i = 0; i + 1 < kVeTableLen; i++) {
    const VePoint &a = kVeTable[i];
    const VePoint &b = kVeTable[i + 1];
    if (rpm >= a.rpm && rpm <= b.rpm) {
      float span = (float)(b.rpm - a.rpm);
      float t = span > 0 ? (float)(rpm - a.rpm) / span : 0.0f;
      return a.ve_pct + t * (b.ve_pct - a.ve_pct);
    }
  }
  return VOLUMETRIC_EFFICIENCY_DEFAULT;
}

static uint32_t s_tripStartMs = 0;
static bool     s_tripStarted = false;

void fuelCalcResetTrip(VehicleData &vd) {
  vd.trip_distance_km = 0;
  vd.trip_fuel_L = 0;
  vd.trip_avg_L100km = 0;
  vd.trip_time_s = 0;
  s_tripStartMs = millis();
  s_tripStarted = true;
}

void fuelCalcUpdate(VehicleData &vd, float dt_seconds) {
  if (!s_tripStarted) {
    s_tripStartMs = millis();
    s_tripStarted = true;
  }

  float ve = fuelCalcVeForRpm(vd.rpm);
  vd.ve_pct = ve;

  float iat_K = vd.iat_c + 273.15f;
  if (iat_K < 233.15f || iat_K > 373.15f) iat_K = 288.15f; // guard bad/unset IAT (-40..100C range)

  const float MM_AIR = 28.97f; // g/mol
  const float R = 8.314f;      // L*kPa/(mol*K)

  float maf = (ve / 100.0f) * (float)vd.rpm * vd.map_kpa * ENGINE_DISPLACEMENT_L * MM_AIR /
              (2.0f * R * iat_K * 60.0f);
  if (maf < 0.0f) maf = 0.0f;
  vd.maf_calc_gs = maf;

  float afr = FUEL_AFR_STOICH;
#if USE_FUEL_TRIM_CORRECTION
  // Positive fuel trim means the ECU is adding fuel vs. the base map
  // (running leaner than expected), so the effective AFR is lower.
  float trimFraction = (vd.stft_pct + vd.ltft_pct) / 100.0f;
  afr = FUEL_AFR_STOICH / (1.0f + trimFraction);
  if (afr < 8.0f) afr = 8.0f;
  if (afr > 25.0f) afr = 25.0f;
#endif

  float fuel_gs = (maf / afr) * FUEL_CALIBRATION_FACTOR;
  vd.fuel_gs = fuel_gs;

  float fuel_Lh = (fuel_gs * 3600.0f) / FUEL_DENSITY_G_PER_L;
  vd.instant_Lh = fuel_Lh;

  vd.instant_L100km = (vd.speed_kmh > 2.0f) ? (fuel_Lh / vd.speed_kmh) * 100.0f : 0.0f;

  double fuelLThisStep = (double)fuel_gs * dt_seconds / FUEL_DENSITY_G_PER_L;
  double distKmThisStep = (double)vd.speed_kmh * (dt_seconds / 3600.0);

  vd.trip_fuel_L += fuelLThisStep;
  vd.trip_distance_km += distKmThisStep;
  vd.trip_time_s = (millis() - s_tripStartMs) / 1000;

  vd.trip_avg_L100km = (vd.trip_distance_km > 0.05)
                            ? (vd.trip_fuel_L / vd.trip_distance_km) * 100.0
                            : 0.0;
}
