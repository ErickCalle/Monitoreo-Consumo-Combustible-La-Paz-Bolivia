#!/usr/bin/env python3
"""
Validador de los CSV de registro en MicroSD -- SOLO para llenar la Tabla
4.x de la seccion 4.3.6 del Capitulo 4 ("Pruebas de registro de datos en
MicroSD").

Que verifica, por cada archivo trip_NNN.csv (Sección~3.1 de este mismo
capítulo describe el formato, columnas idénticas a sd_logger.cpp):
    1. Que el encabezado sea exactamente el esperado (18 columnas).
    2. Lineas corruptas o incompletas: numero de columnas incorrecto, o
       algun campo que no se puede interpretar como numero.
    3. Huecos en el muestreo: saltos en uptime_ms mayores a la tolerancia
       (por defecto 2.5x el intervalo nominal de 1000 ms configurado en
       SD_LOG_INTERVAL_MS), que delatan una escritura perdida o un reinicio.
    4. Duracion cubierta, filas validas, tasa de muestreo real (Hz) y
       tamaño de archivo, extrapolado a tamaño por hora de registro.

Como usarlo para la prueba de corte abrupto de alimentacion: iniciar una
sesion de registro, dejar correr unos minutos y desconectar la
alimentacion del sistema de forma abrupta (simulando apagar el vehiculo),
luego reconectar y correr este script sobre el archivo resultante. Un
archivo integro debe tener como maximo la ultima linea incompleta (el
propio sd_logger.cpp llama flush() tras cada fila, así que en el peor
caso se pierde la fila que estaba a medio escribir, no el archivo
completo); cualquier corrupcion mas alla de eso indica un problema del
sistema de archivos, no solo de la ultima escritura.

Uso:
    python validate_sd_log.py trip_001.csv [trip_002.csv ...]
    python validate_sd_log.py logs/*.csv

Cada archivo analizado se anexa a sd_log_report.csv, lista para copiar a
la Tabla 4.x del Capítulo 4. No requiere ninguna conexión al vehículo ni
al ELM327 -- se corre sobre los CSV ya descargados (panel web
/api/download o copiados directamente de la tarjeta).
"""
import csv
import glob
import os
import sys

# Encabezado actual (sd_logger.cpp con baro_kpa/baro_is_estimated) y el
# formato anterior a esa columna, por si el CSV se grabó con un firmware
# más viejo. Cualquier otro encabezado se acepta igual, pero se marca
# como "desconocido" para que quede visible en el reporte.
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
