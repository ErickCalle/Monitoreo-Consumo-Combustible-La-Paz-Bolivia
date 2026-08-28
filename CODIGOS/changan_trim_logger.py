#!/usr/bin/env python3
"""
Logger de ajustes de combustible (STFT/LTFT) y lambda comandado -- SOLO
para el Changan Honor, que NO soporta el PID 0x10 (MAF). Ver
Apendice O / DATASHEET/CHANGAN.pdf: este vehiculo si soporta 0x06
(STFT), 0x07 (LTFT) y 0x44 (relacion de equivalencia aire-combustible
comandada), que es la via indirecta que usa
ve_curve_calibrator_indirect.py para refinar su curva VE (Seccion
"Caso sin MAF" del Capitulo 3, Diseno de software).

Protocolo (igual estructura que speed_density_bench.py, pero SIN
referencia real que comparar -- este script solo registra, no valida):
sostener el motor en varios regimenes (ralenti detectado automaticamente,
luego 1500/2500/3500 rpm u otros que el motor alcance con normalidad),
uno a la vez, unos 20-30 s cada uno. La consola sirve de tacometro en
vivo igual que en speed_density_bench.py.

Uso:
    python changan_trim_logger.py

Genera changan_trim_log.csv con columnas:
    hora, rpm, map_kpa, iat_c, stft_pct, ltft_pct, lambda_cmd

Requisitos:
    pip install pyserial
"""
import csv
import os
import time
import serial

PORT = "COM3"              # <-- cambiar al puerto COM real del ELM327
BAUDRATE = 38400
RESPONSE_TIMEOUT_S = 0.2
SAMPLE_PERIOD_S = 0.3

TARGET_RPMS = [1500, 2500, 3500]  # el ralenti real se antepone en tiempo de ejecucion
RPM_TOLERANCE = 100
TARGET_SAMPLES = 20
IDLE_SAMPLE_COUNT = 8

CSV_PATH = "changan_trim_log.csv"


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


def read_stft(ser):
    b = parse_bytes_after(query_pid(ser, "0106"), "41 06")
    return (b[0] - 128) * 100.0 / 128.0 if b and len(b) >= 1 else None  # SAE J1979: (A-128)*100/128


def read_ltft(ser):
    b = parse_bytes_after(query_pid(ser, "0107"), "41 07")
    return (b[0] - 128) * 100.0 / 128.0 if b and len(b) >= 1 else None


def read_lambda_cmd(ser):
    b = parse_bytes_after(query_pid(ser, "0144"), "41 44")
    if not b or len(b) < 2:
        return None
    return ((b[0] * 256) + b[1]) * 2.0 / 65536.0  # SAE J1979: relacion de equivalencia comandada


def detect_idle_rpm(ser):
    print(f"\nDeja el motor en ralenti (sin acelerar). Midiendo {IDLE_SAMPLE_COUNT} muestras...")
    readings = []
    while len(readings) < IDLE_SAMPLE_COUNT:
        rpm = read_rpm(ser)
        if rpm is not None:
            readings.append(rpm)
            print(f"  ralenti muestra {len(readings)}/{IDLE_SAMPLE_COUNT}: {rpm:.0f} rpm")
        time.sleep(SAMPLE_PERIOD_S)
    idle_rpm = round(sum(readings) / len(readings) / 10.0) * 10
    print(f"Ralenti detectado: {idle_rpm} rpm.\n")
    return idle_rpm


def closest_target(rpm, targets):
    best = min(targets, key=lambda t: abs(t - rpm))
    return best if abs(best - rpm) <= RPM_TOLERANCE else None


def main():
    ser = serial.Serial(PORT, BAUDRATE, timeout=RESPONSE_TIMEOUT_S)

    print("Inicializando ELM327...")
    print(send_at(ser, "ATZ", 1.0))
    print(send_at(ser, "ATE0"))
    print(send_at(ser, "ATSP6"))
    print(send_at(ser, "0100"))

    idle_rpm = detect_idle_rpm(ser)
    targets = [idle_rpm] + TARGET_RPMS

    counts = {t: 0 for t in targets}
    listos = set()
    csv_rows = []

    print(f"\nMuestreando. Sostener el motor en cada uno de {targets} rpm hasta ver 'LISTO'.")
    print("Cuando todos digan LISTO, la prueba se detiene sola (o Ctrl+C para cortar antes).\n")

    try:
        while True:
            rpm = read_rpm(ser)
            if rpm is None:
                print("  ... sin lectura de RPM (revisa la conexion al ELM327)")
                time.sleep(SAMPLE_PERIOD_S)
                continue

            map_kpa_b = parse_bytes_after(query_pid(ser, "010B"), "41 0B")
            map_kpa = float(map_kpa_b[0]) if map_kpa_b else None

            iat_b = parse_bytes_after(query_pid(ser, "010F"), "41 0F")
            iat_c = float(iat_b[0] - 40) if iat_b else None

            stft = read_stft(ser)
            ltft = read_ltft(ser)
            lambda_cmd = read_lambda_cmd(ser)

            target = closest_target(rpm, targets)
            ts = time.strftime("%H:%M:%S")

            if None not in (map_kpa, iat_c, stft, ltft, lambda_cmd):
                csv_rows.append([ts, f"{rpm:.0f}", map_kpa, iat_c, f"{stft:.2f}", f"{ltft:.2f}", f"{lambda_cmd:.3f}"])

                if target is not None:
                    counts[target] += 1
                    n = counts[target]
                    print(f"[{ts}] RPM actual: {rpm:5.0f}  -> objetivo {target} rpm  "
                          f"({min(n, TARGET_SAMPLES)}/{TARGET_SAMPLES})  "
                          f"STFT={stft:+.1f}% LTFT={ltft:+.1f}% lambda_cmd={lambda_cmd:.2f}")

                    if n >= TARGET_SAMPLES and target not in listos:
                        listos.add(target)
                        print(f"\n>>> {target} RPM LISTO ({n} muestras). Sube al siguiente regimen. <<<\n")
                        if len(listos) == len(targets):
                            print(">>> Todos los puntos completos. Deteniendo automaticamente. <<<\n")
                            break
                else:
                    print(f"[{ts}] RPM actual: {rpm:5.0f}  (fuera de los puntos objetivo)")
            else:
                print(f"[{ts}] RPM actual: {rpm:5.0f}  (esperando STFT/LTFT/lambda todavia)")

            time.sleep(SAMPLE_PERIOD_S)

    except KeyboardInterrupt:
        pass
    finally:
        ser.close()

    csv_path = os.path.abspath(CSV_PATH)
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["hora", "rpm", "map_kpa", "iat_c", "stft_pct", "ltft_pct", "lambda_cmd"])
        w.writerows(csv_rows)

    print(f"\nLog guardado ({len(csv_rows)} muestras) en:\n  {csv_path}")
    print("Siguiente paso: python ve_curve_calibrator_indirect.py changan_trim_log.csv")


if __name__ == "__main__":
    main()
