// Speed-Density fuel consumption calculation.
//
//   MAF(g/s) = (VE/100) * RPM * MAP(kPa) * Vd(L) * 28.97
//              --------------------------------------------
//                    2 * 8.314 * IAT(K) * 60
//
// (the "2" accounts for one intake stroke every 2 crank revolutions on
// a 4-stroke engine). Fuel mass flow = MAF / AFR, then converted to
// volume with the gasoline density constant.
//
// VE is not measured -- it is looked up from a calibration table below.
// The 940/1500/2500/3500 rpm points were calibrated against the Nissan
// Vanette's real MAF (PID 0x10) with a static RPM-step test (Seccion 4.3.3
// del Capitulo 4, Vd=1.626L real de Tabla 4.4): CLAUDE_PRO/speed_density_bench.py
// logged RPM/MAP/IAT/MAF_real, and CLAUDE_PRO/calibrate_ve_table.py inverted
// this same formula to solve for the VE that makes the estimate match the
// reference at each point. The 4000/5500/7000 rpm points remain generic
// (no real data collected there) -- for accurate results at those regimes,
// or for the Changan Honor (no MAF PID at all), calibrate against a known
// tank-to-tank fuel-up: compare real liters added vs. the trip_fuel_L this
// code produced over the same distance, then set FUEL_CALIBRATION_FACTOR =
// real_L / calculated_L so future runs are corrected without reshaping the
// whole VE table.
#include <Arduino.h>
#include "config.h"
#include "types.h"
#include "fuel_calc.h"

struct VePoint { uint16_t rpm; float ve_pct; };

#if defined(VEHICLE_VANETTE)
// Calibrada contra el MAF real (PID 0x10) del Nissan Vanette -- Seccion
// 4.3.3 del Capitulo 4 / "Calculo general de la eficiencia volumetrica"
// del Capitulo 3. Los tres ultimos puntos siguen sin datos reales.
static const VePoint kVeTable[] = {
  { 940,  82.7f},  // calibrado (ralenti real)
  {1500,  79.7f},  // calibrado
  {2500,  79.7f},  // calibrado
  {3500,  72.7f},  // calibrado
  {4000,  88.0f},  // sin calibrar (generico)
  {5500,  83.0f},  // sin calibrar (generico)
  {7000,  74.0f},  // sin calibrar (generico)
};
#else
// Changan Honor: no soporta el PID 0x10 (MAF), asi que no existe forma
// directa de calibrar esta tabla (Seccion "Caso sin MAF" del Capitulo
// 3). Tabla generica de literatura, punto de partida sin datos reales
// de este motor -- pendiente refinarla con
// CODIGOS/ve_curve_calibrator_indirect.py cuando se recolecte el
// registro de STFT/LTFT (CODIGOS/changan_trim_logger.py).
static const VePoint kVeTable[] = {
  { 700,  60.0f},
  {1500,  74.0f},
  {2500,  85.0f},
  {4000,  88.0f},
  {5500,  83.0f},
  {7000,  74.0f},
};
#endif
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
