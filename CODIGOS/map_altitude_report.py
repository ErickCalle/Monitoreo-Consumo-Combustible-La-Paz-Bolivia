#!/usr/bin/env python3
"""
Reporte de validacion del sensor MAP frente a la altitud -- SOLO para
llenar la Tabla 4.x de la seccion 4.3.4 del Capitulo 4.

Que mide: con el contacto puesto y el motor APAGADO (key-on, engine-off,
sin vacio de admision), el MAP del vehiculo deberia leer aproximadamente
lo mismo que la presion barometrica real, porque en ese estado no hay
vacio que lo separe de la presion atmosferica. Comparar ambas confirma
si el sensor MAP del vehiculo esta bien calibrado para operar a los
~3600 msnm de La Paz (ver README del firmware y Seccion 4.3.4).

Fuente de la presion barometrica de referencia:
    1. PID 0x33 (presion barometrica), si el vehiculo lo soporta.
    2. Si no lo soporta ("NO DATA"), se usa el modelo ISA evaluado en
       SITE_ALTITUDE_M (idéntica formula a isaPressureKpaAt() en
       can_obd2.cpp), igual que hace el firmware real como respaldo.

Uso:
    1. Contacto puesto, motor APAGADO (no arrancar el vehiculo).
    2. Cambiar PORT y VEHICULO abajo.
    3. Ejecutar: python map_altitude_report.py
    4. Repetir para el segundo vehiculo cambiando VEHICULO.
    El script anexa cada corrida a map_altitude_report.csv y al final
    imprime la fila lista para copiar a la Tabla 4.x del Capitulo 4.

Requisitos:
    pip install pyserial
"""
import csv
import os
import time
import serial

PORT = "COM3"                    # <-- cambiar al puerto COM real del ELM327
VEHICULO = "Nissan Vanette"      # <-- cambiar por "Changan Honor" Nissan Vanette segun corresponda
BAUDRATE = 38400
RESPONSE_TIMEOUT_S = 0.2
N_MUESTRAS = 10                  # promedio de N lecturas para reducir ruido
SAMPLE_PERIOD_S = 0.5

SITE_ALTITUDE_M = 3640.0         # La Paz, Bolivia -- igual que config.h
CSV_PATH = "map_altitude_report.csv"


def isa_pressure_kpa_at(altitude_m):
    """Identica a isaPressureKpaAt() en can_obd2.cpp."""
    P0 = 101.325   # kPa
    T0 = 288.15    # K
    L = 0.0065     # K/m
    g = 9.80665    # m/s^2
    M = 0.0289644  # kg/mol
    R = 8.31447    # J/(mol*K)
    return P0 * (1.0 - (L * altitude_m) / T0) ** ((g * M) / (R * L))


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


def main():
    ser = serial.Serial(PORT, BAUDRATE, timeout=RESPONSE_TIMEOUT_S)

    print("Inicializando ELM327...")
    print(send_at(ser, "ATZ", 1.0))
    print(send_at(ser, "ATE0"))
    print(send_at(ser, "ATSP6"))
    print(send_at(ser, "0100"))

    print(f"\nVehiculo: {VEHICULO}")
    print("Confirma: contacto puesto, motor APAGADO, antes de continuar.")
    input("Presiona Enter para iniciar el muestreo...")

    map_samples = []
    baro_samples = []
    baro_is_estimated = False

    for i in range(N_MUESTRAS):
        b = parse_bytes_after(query_pid(ser, "010B"), "41 0B")
        map_kpa = float(b[0]) if b and len(b) >= 1 else None

        resp_baro = query_pid(ser, "0133")
        b = parse_bytes_after(resp_baro, "41 33")
        if b and len(b) >= 1:
            baro_kpa = float(b[0])
        else:
            baro_kpa = isa_pressure_kpa_at(SITE_ALTITUDE_M)
            baro_is_estimated = True

        if map_kpa is not None:
            map_samples.append(map_kpa)
            baro_samples.append(baro_kpa)
            print(f"  muestra {i + 1}/{N_MUESTRAS}: MAP={map_kpa:.1f} kPa  "
                  f"baro={baro_kpa:.1f} kPa"
                  f"{' (estimado ISA, PID 0x33 no soportado)' if baro_is_estimated else ' (PID 0x33)'}")
        else:
            print(f"  muestra {i + 1}/{N_MUESTRAS}: sin respuesta, descartada")

        time.sleep(SAMPLE_PERIOD_S)

    ser.close()

    if not map_samples:
        print("\nSin muestras validas. Revisa la conexion e intenta de nuevo.")
        return

    map_avg = sum(map_samples) / len(map_samples)
    baro_avg = sum(baro_samples) / len(baro_samples)
    diff_pct = (map_avg - baro_avg) / baro_avg * 100.0

    row = [VEHICULO, f"{map_avg:.1f}", f"{baro_avg:.1f}", f"{diff_pct:+.1f}",
           "ISA estimado" if baro_is_estimated else "PID 0x33 real", len(map_samples)]

    write_header = not os.path.exists(CSV_PATH)
    with open(CSV_PATH, "a", newline="") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(["vehiculo", "map_koeo_kpa", "baro_kpa", "diferencia_pct",
                        "fuente_baro", "n_muestras"])
        w.writerow(row)

    print("\n================================================")
    print(f"RESULTADO -- Tabla 4.x, fila '{VEHICULO}'")
    print("================================================")
    print(f"MAP en KOEO (kPa):     {map_avg:.1f}")
    print(f"baro_kpa (kPa):        {baro_avg:.1f}  ({row[4]})")
    print(f"Diferencia (%):        {diff_pct:+.1f}")
    print("================================================")
    print(f"Fila anexada a {CSV_PATH}. Copia estos 3 valores a la Tabla 4.x del Capitulo 4.")


if __name__ == "__main__":
    main()
