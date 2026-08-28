#!/usr/bin/env python3
"""
Registro continuo del modelo Speed-Density durante una ruta real -- SOLO
para la prueba DINAMICA de la Seccion 4.3.3 del Capitulo 4 (Nissan
Vanette, unico vehiculo con PID 0x10/MAF real de referencia).

Diferencia con speed_density_bench.py: aquel esta pensado para la prueba
ESTATICA de pasos de RPM (motor detenido, sosteniendo 800/1500/2500/3500
rpm) y por eso agrupa muestras por punto objetivo y corta solo al
completar los 4. Ese mismo criterio, aplicado a una ruta real, cortaria
la prueba antes de tiempo apenas el RPM de manejo normal pase cerca de
cualquiera de esos 4 puntos. Este script no agrupa nada: registra TODAS
las muestras tal como llegan, sin ningun punto objetivo ni corte
automatico, pensado para ir en el asiento mientras alguien maneja una
ruta real (arrancar, acelerar, crucero a distintas velocidades, frenar).

Por que esta prueba importa mas alla de llenar la tabla: la calibracion
de la tabla VE (Capitulo 3, "Calculo general de la eficiencia
volumetrica") se valido sobre el MISMO dataset con el que se calibro, lo
cual no prueba que el modelo generalice. Los datos de una ruta real,
que nunca participaron en la calibracion, son la validacion
independiente que quedo pendiente como trabajo futuro (Capitulo 6).

Ademas del MAF (para la validacion), este script ya calcula el consumo
de combustible en vivo -- fuel_gs, L/h, L/100km y los acumulados de
viaje (litros y km) -- con la MISMA cadena de calculo de fuel_calc.cpp
(Seccion~3.9.6 del Capitulo 3): MAF -> combustible via AFR -> volumen.
Simplificacion deliberada frente al firmware real: aqui NO se aplica la
correccion de AFR por STFT/LTFT (USE_FUEL_TRIM_CORRECTION en el
firmware) -- se usa siempre el AFR estequiometrico fijo (14.7). Pedir
tambien esos dos PID por ciclo alargaria cada muestra y no es
indispensable para tener una cifra de consumo razonable en una ruta
larga; si se necesita la cifra exacta que reportaria el dispositivo
instalado, usar ese en paralelo.

Uso:
    python speed_density_drive_log.py

Requisitos:
    pip install pyserial

Antes de correr, cambiar PORT abajo por el puerto COM del ELM327.
Iniciar el script con el motor ya encendido, antes de arrancar a
manejar; Ctrl+C al terminar la ruta (o desconexion natural del ELM327
al llegar). No requiere ninguna interaccion mientras se maneja.
"""
import csv
import os
import time
import serial

PORT = "COM3"             # <-- cambiar al puerto COM real del ELM327
BAUDRATE = 38400
RESPONSE_TIMEOUT_S = 0.2
SAMPLE_PERIOD_S = 0.3

# --- Motor: Nissan Vanette (identico a config.h / speed_density_bench.py) ---
ENGINE_DISPLACEMENT_L = 1.626

# --- Tabla VE calibrada (identica a kVeTable en fuel_calc.cpp) ---
VE_TABLE = [
    (940,  82.7),
    (1500, 79.7),
    (2500, 79.7),
    (3500, 72.7),
    (4000, 88.0),
    (5500, 83.0),
    (7000, 74.0),
]

MM_AIR = 28.97   # g/mol
R = 8.314        # L*kPa/(mol*K)

# --- Combustible (identico a config.h) ---
FUEL_AFR_STOICH = 14.7          # sin correccion por STFT/LTFT, ver docstring
FUEL_DENSITY_G_PER_L = 745.0
FUEL_CALIBRATION_FACTOR = 1.0   # sin calibrar aun contra un tanque lleno real

DT_MAX_S = 3.0  # dt mayor a esto (reconexion, pausa) no se acumula al viaje


def ve_for_rpm(rpm):
    if rpm <= VE_TABLE[0][0]:
        return VE_TABLE[0][1]
    if rpm >= VE_TABLE[-1][0]:
        return VE_TABLE[-1][1]
    for (rpm_a, ve_a), (rpm_b, ve_b) in zip(VE_TABLE, VE_TABLE[1:]):
        if rpm_a <= rpm <= rpm_b:
            t = (rpm - rpm_a) / (rpm_b - rpm_a)
            return ve_a + t * (ve_b - ve_a)
    return VE_TABLE[-1][1]


def maf_estimado_gs(rpm, map_kpa, iat_c):
    ve = ve_for_rpm(rpm)
    iat_k = iat_c + 273.15
    if iat_k < 233.15 or iat_k > 373.15:
        iat_k = 288.15
    maf = (ve / 100.0) * rpm * map_kpa * ENGINE_DISPLACEMENT_L * MM_AIR / (2.0 * R * iat_k * 60.0)
    return max(maf, 0.0)


def fuel_from_maf(maf_gs, speed_kmh):
    """Misma cadena que fuel_calc.cpp: MAF -> combustible (AFR) -> volumen."""
    fuel_gs = (maf_gs / FUEL_AFR_STOICH) * FUEL_CALIBRATION_FACTOR
    instant_Lh = fuel_gs * 3600.0 / FUEL_DENSITY_G_PER_L
    instant_L100km = (instant_Lh / speed_kmh) * 100.0 if speed_kmh > 2.0 else 0.0
    return fuel_gs, instant_Lh, instant_L100km


def send_at(ser, cmd, wait=0.3):
    ser.reset_input_buffer()
    ser.write((cmd + "\r").encode())
    time.sleep(wait)
    return ser.read(ser.in_waiting or 1).decode(errors="ignore")


def query_pid(ser, pid_cmd):
    ser.reset_input_buffer()
    ser.write((pid_cmd + "\r").encode())
    resp = ser.read(64).decode(errors="ignore")
    return resp.replace("\r", " ").replace(">", " ").upper()


def parse_bytes_after(resp, header):
    idx = resp.find(header)
    if idx < 0:
        return None
    rest = resp[idx + len(header):].split()
    try:
        return [int(b, 16) for b in rest]
    except ValueError:
        return None


def read_rpm(ser):
    b = parse_bytes_after(query_pid(ser, "010C"), "41 0C")
    return ((b[0] * 256) + b[1]) / 4.0 if b and len(b) >= 2 else None


def read_speed_kmh(ser):
    b = parse_bytes_after(query_pid(ser, "010D"), "41 0D")
    return float(b[0]) if b and len(b) >= 1 else None


def connect(port):
    ser = serial.Serial(port, BAUDRATE, timeout=RESPONSE_TIMEOUT_S)
    send_at(ser, "ATZ", 1.0)
    send_at(ser, "ATE0")
    send_at(ser, "ATSP6")
    send_at(ser, "0100")
    return ser


def main():
    print("Inicializando ELM327...")
    ser = connect(PORT)

    print("\nRegistro continuo iniciado. Maneja la ruta con normalidad.")
    print("Ctrl+C para terminar cuando llegues.\n")

    # Se escribe cada fila al toque (igual que el firmware real hace
    # flush() por fila): si el Bluetooth se corta a mitad de la ruta, lo
    # unico que se pierde es la fila en curso, no la hora completa.
    csv_path = os.path.abspath("speed_density_drive_log.csv")
    csv_file = open(csv_path, "w", newline="")
    writer = csv.writer(csv_file)
    writer.writerow(["hora", "rpm", "map_kpa", "iat_c", "speed_kmh",
                      "maf_estimado_gs", "maf_referencia_gs",
                      "fuel_gs", "instant_Lh", "instant_L100km",
                      "trip_km", "trip_fuel_L"])
    csv_file.flush()

    n_rows = 0
    errores_pct = []
    trip_km = 0.0
    trip_fuel_L = 0.0
    last_t = None  # marca de tiempo real (time.time()) de la muestra anterior

    try:
        while True:
            try:
                rpm = read_rpm(ser)
                if rpm is None:
                    time.sleep(SAMPLE_PERIOD_S)
                    continue

                b = parse_bytes_after(query_pid(ser, "010B"), "41 0B")
                map_kpa = float(b[0]) if b and len(b) >= 1 else None

                b = parse_bytes_after(query_pid(ser, "010F"), "41 0F")
                iat_c = float(b[0] - 40) if b and len(b) >= 1 else None

                speed_kmh = read_speed_kmh(ser)

                b = parse_bytes_after(query_pid(ser, "0110"), "41 10")
                maf_ref = ((b[0] * 256) + b[1]) / 100.0 if b and len(b) >= 2 else None

                ts = time.strftime("%H:%M:%S")
                now = time.time()

                if None not in (map_kpa, iat_c, speed_kmh, maf_ref):
                    maf_est = maf_estimado_gs(rpm, map_kpa, iat_c)
                    fuel_gs, instant_Lh, instant_L100km = fuel_from_maf(maf_est, speed_kmh)

                    # dt real entre muestras (no un valor fijo), igual que
                    # fuel_calc.cpp -- acotado para no acumular de mas tras
                    # una reconexion o pausa larga.
                    dt = (now - last_t) if last_t is not None else SAMPLE_PERIOD_S
                    if dt > DT_MAX_S or dt <= 0:
                        dt = SAMPLE_PERIOD_S
                    last_t = now

                    trip_fuel_L += fuel_gs * dt / FUEL_DENSITY_G_PER_L
                    trip_km += speed_kmh * dt / 3600.0

                    writer.writerow([ts, f"{rpm:.0f}", map_kpa, iat_c, speed_kmh,
                                      f"{maf_est:.3f}", f"{maf_ref:.3f}",
                                      f"{fuel_gs:.3f}", f"{instant_Lh:.2f}", f"{instant_L100km:.1f}",
                                      f"{trip_km:.3f}", f"{trip_fuel_L:.4f}"])
                    csv_file.flush()
                    n_rows += 1

                    if maf_ref > 0.1:
                        err_pct = (maf_est - maf_ref) / maf_ref * 100.0
                        errores_pct.append(err_pct)
                        print(f"[{ts}] rpm={rpm:5.0f} v={speed_kmh:3.0f}km/h  "
                              f"MAF_est={maf_est:5.2f} MAF_ref={maf_ref:5.2f} g/s  error={err_pct:+.1f}%  "
                              f"| {instant_L100km:4.1f} L/100km  trip={trip_fuel_L:.2f} L / {trip_km:.1f} km")
                    else:
                        print(f"[{ts}] rpm={rpm:5.0f}  (referencia ~0, motor detenido)  "
                              f"trip={trip_fuel_L:.2f} L / {trip_km:.1f} km")
                else:
                    last_t = now
                    print(f"[{ts}] rpm={rpm:5.0f}  (esperando MAP/IAT/velocidad/MAF todavia)")

                time.sleep(SAMPLE_PERIOD_S)

            except KeyboardInterrupt:
                raise
            except Exception as e:
                # Corte de Bluetooth, timeout raro, etc: no se pierde lo ya
                # guardado (cada fila anterior ya esta en disco). Se intenta
                # reconectar y seguir, en vez de morir con toda la ruta perdida.
                print(f"  ... error de conexion ({e}); reintentando en 2 s...")
                try:
                    ser.close()
                except Exception:
                    pass
                time.sleep(2.0)
                try:
                    ser = connect(PORT)
                    print("  reconectado.")
                except Exception as e2:
                    print(f"  no se pudo reconectar todavia ({e2})")

    except KeyboardInterrupt:
        pass
    finally:
        try:
            ser.close()
        except Exception:
            pass
        csv_file.close()

    avg_L100km = (trip_fuel_L / trip_km * 100.0) if trip_km > 0.05 else 0.0

    print("\n================================================")
    print(f"Registro terminado: {n_rows} muestras")
    print(f"Distancia recorrida:        {trip_km:.1f} km")
    print(f"Combustible consumido:      {trip_fuel_L:.2f} L")
    print(f"Promedio del viaje:         {avg_L100km:.1f} L/100km")
    if errores_pct:
        prom = sum(errores_pct) / len(errores_pct)
        print(f"Error porcentual promedio (bruto, sin RMSE/MAPE): {prom:+.1f}%")
    print(f"Log guardado en:\n  {csv_path}")
    print("Siguiente paso: python speed_density_drive_validation.py speed_density_drive_log.csv")
    print("================================================")
    print("Nota: fuel_gs usa AFR estequiometrico fijo (14.7), sin correccion")
    print("por STFT/LTFT y sin FUEL_CALIBRATION_FACTOR calibrado todavia --")
    print("es una cifra de consumo razonable, no la misma exactitud que")
    print("tendria el dispositivo instalado ya calibrado contra un tanque real.")


if __name__ == "__main__":
    main()
