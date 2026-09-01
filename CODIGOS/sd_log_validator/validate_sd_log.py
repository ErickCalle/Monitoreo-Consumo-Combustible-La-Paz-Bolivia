#!/usr/bin/env python3
"""
Validador de los CSV de registro en MicroSD -- Tabla 4.x de la Seccion
4.3.6 (pruebas de registro en MicroSD).

Por cada trip_NNN.csv (columnas identicas a sd_logger.cpp) verifica:
    1. Encabezado esperado (18 columnas).
    2. Lineas corruptas/incompletas (columnas de mas/menos, campos no
       numericos).
    3. Huecos de muestreo: saltos en uptime_ms mayores a la tolerancia
       (2.5x el intervalo nominal SD_LOG_INTERVAL_MS).
    4. Duracion, filas validas, tasa de muestreo (Hz) y tamaño
       extrapolado por hora.

Para la prueba de corte abrupto: iniciar el registro, desconectar la
alimentacion de golpe a los pocos minutos, reconectar y correr este
script sobre el archivo resultante. Como sd_logger.cpp hace flush() por
fila, en el peor caso se pierde solo la ultima fila a medio escribir.

Uso:
    python validate_sd_log.py trip_001.csv [trip_002.csv ...]
    python validate_sd_log.py logs/*.csv

Cada archivo se anexa a sd_log_report.csv, lista para copiar a la Tabla
4.x. No requiere conexion al vehiculo ni al ELM327.
"""
import csv
import glob
import os
import sys

# encabezado actual y el formato anterior (sin baro); otros quedan como "desconocido"
KNOWN_HEADERS = {
    "actual (18 col, con baro)": [
        "uptime_ms", "rpm", "speed_kmh", "map_kpa", "iat_c", "coolant_c",
        "ve_pct", "maf_gs", "fuel_gs", "instant_Lh", "instant_L100km",
        "trip_km", "trip_fuel_L", "trip_avg_L100km", "can_status",
        "trip_cost_bs", "baro_kpa", "baro_is_estimated",
    ],
    "anterior (16 col, sin baro)": [
        "uptime_ms", "rpm", "speed_kmh", "map_kpa", "iat_c", "coolant_c",
        "ve_pct", "maf_gs", "fuel_gs", "instant_Lh", "instant_L100km",
        "trip_km", "trip_fuel_L", "trip_avg_L100km", "can_status",
        "trip_cost_bs",
    ],
}

SD_LOG_INTERVAL_MS = 1000          # igual que config.h
GAP_TOLERANCE_MS = SD_LOG_INTERVAL_MS * 2.5

REPORT_PATH = "sd_log_report.csv"


def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False


def detect_format(header):
    for name, known in KNOWN_HEADERS.items():
        if header == known:
            return name
    return "desconocido"


def validate_file(path):
    result = {
        "archivo": os.path.basename(path),
        "formato": "vacio",
        "filas_totales": 0,
        "filas_validas": 0,
        "filas_corruptas": 0,
        "huecos_muestreo": 0,
        "duracion_s": 0.0,
        "tasa_muestreo_hz": 0.0,
        "tamano_bytes": os.path.getsize(path),
    }

    with open(path, "r", newline="") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            return result
        result["formato"] = detect_format(header)
        expected_cols = len(header)  # se valida contra el propio encabezado del archivo

        prev_uptime = None
        first_uptime = None
        last_uptime = None

        for row in reader:
            result["filas_totales"] += 1

            if len(row) != expected_cols or not all(is_number(v) for v in row):
                result["filas_corruptas"] += 1
                continue

            uptime_ms = float(row[0])
            if first_uptime is None:
                first_uptime = uptime_ms
            if prev_uptime is not None:
                gap = uptime_ms - prev_uptime
                if gap > GAP_TOLERANCE_MS:
                    result["huecos_muestreo"] += 1
            prev_uptime = uptime_ms
            last_uptime = uptime_ms
            result["filas_validas"] += 1

        if first_uptime is not None and last_uptime is not None and last_uptime > first_uptime:
            result["duracion_s"] = (last_uptime - first_uptime) / 1000.0
            result["tasa_muestreo_hz"] = result["filas_validas"] / result["duracion_s"]

    return result


def print_and_save(results):
    fieldnames = ["archivo", "formato", "filas_totales", "filas_validas",
                  "filas_corruptas", "huecos_muestreo", "duracion_s",
                  "tasa_muestreo_hz", "tamano_bytes", "tamano_por_hora_kb"]

    write_header = not os.path.exists(REPORT_PATH)
    with open(REPORT_PATH, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            w.writeheader()

        for r in results:
            tamano_por_hora_kb = (
                (r["tamano_bytes"] / r["duracion_s"]) * 3600.0 / 1024.0
                if r["duracion_s"] > 0 else 0.0
            )
            r["tamano_por_hora_kb"] = round(tamano_por_hora_kb, 1)
            w.writerow(r)

            print("================================================")
            print(f"Archivo:                 {r['archivo']}")
            print(f"Formato de encabezado:   {r['formato']}")
            print(f"Filas totales:           {r['filas_totales']}")
            print(f"Filas validas:           {r['filas_validas']}")
            print(f"Filas corruptas:         {r['filas_corruptas']}")
            print(f"Huecos de muestreo:      {r['huecos_muestreo']}")
            print(f"Duracion (s):            {r['duracion_s']:.1f}")
            print(f"Tasa de muestreo (Hz):   {r['tasa_muestreo_hz']:.3f}")
            print(f"Tamano (bytes):          {r['tamano_bytes']}")
            print(f"Tamano extrapolado/hora: {tamano_por_hora_kb:.1f} KB")
    print("================================================")
    print(f"\nResultados anexados a {REPORT_PATH}. Copia las filas a la Tabla 4.x del Capitulo 4.")


def main():
    if len(sys.argv) < 2:
        print("Uso: python validate_sd_log.py archivo1.csv [archivo2.csv ...]")
        print("     python validate_sd_log.py logs/*.csv")
        sys.exit(1)

    paths = []
    for pattern in sys.argv[1:]:
        matched = glob.glob(pattern)
        paths.extend(matched if matched else [pattern])

    results = [validate_file(p) for p in paths if os.path.isfile(p)]
    if not results:
        print("Ningun archivo valido encontrado.")
        sys.exit(1)

    print_and_save(results)


if __name__ == "__main__":
    main()
