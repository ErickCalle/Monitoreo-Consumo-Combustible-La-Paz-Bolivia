#!/usr/bin/env python3
"""
Prueba estatica del modelo Speed-Density -- Tabla 4.x y Figura 4.9
(Seccion 4.3.3, Nissan Vanette, unico vehiculo con MAF real PID 0x10).

Solo ELM327, sin el ESP32-S3: compara Speed-Density estimado vs. MAF
real a partir de las mismas lecturas de RPM/MAP/IAT, asi que no hace
falta mantener dos sesiones OBD-II simultaneas.

Protocolo: el motor arranca en ralenti (el script mide el ralenti real
en vez de forzar 800 rpm fijo, porque el piso del governor varia segun
el motor), luego se acelera y sostiene cada regimen objetivo (1500,
2500, 3500 rpm) con freno de mano puesto y vehiculo detenido. La
consola sirve de tacometro: cuando el RPM cae en +/-100 rpm de un
punto, cuenta muestras hasta TARGET_SAMPLES y avisa "LISTO". Al
terminar (Ctrl+C tras ver los 4 avisos) genera speed_density_log.csv y
figura_4_9_speed_density.png.

Formula y tabla VE identicas a fuel_calc.cpp:

    MAF(g/s) = (VE/100) * RPM * MAP(kPa) * Vd(L) * 28.97 / (2 * 8.314 * IAT(K) * 60)

Requisitos:
    pip install pyserial matplotlib

Antes de correr, cambiar PORT abajo (ver elm327_bench.py para como
identificar el puerto).
"""
import csv
import os
import time
import serial

PORT = "COM3"             # <-- cambiar al puerto COM real del ELM327
BAUDRATE = 38400
RESPONSE_TIMEOUT_S = 0.2
SAMPLE_PERIOD_S = 0.3

TARGET_RPMS = [1500, 2500, 3500]  # el primer punto (ralenti) se antepone en tiempo de ejecucion
RPM_TOLERANCE = 100
TARGET_SAMPLES = 20        # muestras dentro de tolerancia para marcar un punto como "listo"
IDLE_SAMPLE_COUNT = 8      # lecturas para promediar y detectar el ralenti real al inicio

# --- Motor: Nissan Vanette (parametros identicos a config.h) ---
ENGINE_DISPLACEMENT_L = 1.626  # litros, real de fabrica (Tabla 4.4, 1626 mL) -- antes 1.6 por error

# Tabla VE identica a kVeTable en fuel_calc.cpp. 940-3500 calibrados con
# calibrate_ve_table.py; 4000/5500/7000 siguen sin calibrar (genericos).
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
        iat_k = 288.15  # guarda igual que en el firmware
    maf = (ve / 100.0) * rpm * map_kpa * ENGINE_DISPLACEMENT_L * MM_AIR / (2.0 * R * iat_k * 60.0)
    return max(maf, 0.0)


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


def closest_target(rpm):
    best = min(TARGET_RPMS, key=lambda t: abs(t - rpm))
    return best if abs(best - rpm) <= RPM_TOLERANCE else None


def read_rpm(ser):
    b = parse_bytes_after(query_pid(ser, "010C"), "41 0C")
    return ((b[0] * 256) + b[1]) / 4.0 if b and len(b) >= 2 else None


def detect_idle_rpm(ser):
    """Mide el ralenti real en vez de asumir 800 rpm fijo (el piso del
    governor varia segun el motor)."""
    print(f"\nDeja el motor en ralenti (sin acelerar). Midiendo {IDLE_SAMPLE_COUNT} muestras...")
    readings = []
    while len(readings) < IDLE_SAMPLE_COUNT:
        rpm = read_rpm(ser)
        if rpm is not None:
            readings.append(rpm)
            print(f"  ralenti muestra {len(readings)}/{IDLE_SAMPLE_COUNT}: {rpm:.0f} rpm")
        time.sleep(SAMPLE_PERIOD_S)
    idle_rpm = round(sum(readings) / len(readings) / 10.0) * 10  # redondeado a la decena
    print(f"Ralenti detectado: {idle_rpm} rpm. Se usara como primer punto en vez de 800 rpm.\n")
    return idle_rpm


def main():
    global TARGET_RPMS
    ser = serial.Serial(PORT, BAUDRATE, timeout=RESPONSE_TIMEOUT_S)

    print("Inicializando ELM327...")
    print(send_at(ser, "ATZ", 1.0))
    print(send_at(ser, "ATE0"))
    print(send_at(ser, "ATSP6"))
    print(send_at(ser, "0100"))

    idle_rpm = detect_idle_rpm(ser)
    TARGET_RPMS = [idle_rpm] + TARGET_RPMS

    samples = {t: [] for t in TARGET_RPMS}  # t -> list of (maf_est, maf_ref)
    csv_rows = []
    listos = set()

    print(f"\nMuestreando. El RPM leido se imprime en cada linea -- usa esta consola como tacometro.")
    print(f"Sostener el motor en cada uno de {TARGET_RPMS} rpm hasta ver el aviso 'LISTO' (necesita {TARGET_SAMPLES} muestras en tolerancia).")
    print("Cuando los 4 digan LISTO, presiona Ctrl+C para finalizar.\n")

    try:
        while True:
            rpm = read_rpm(ser)

            if rpm is None:
                print("  ... sin lectura de RPM (revisa la conexion al ELM327)")
                time.sleep(SAMPLE_PERIOD_S)
                continue

            b = parse_bytes_after(query_pid(ser, "010B"), "41 0B")
            map_kpa = float(b[0]) if b and len(b) >= 1 else None

            b = parse_bytes_after(query_pid(ser, "010F"), "41 0F")
            iat_c = float(b[0] - 40) if b and len(b) >= 1 else None

            b = parse_bytes_after(query_pid(ser, "0110"), "41 10")
            maf_ref = ((b[0] * 256) + b[1]) / 100.0 if b and len(b) >= 2 else None

            target = closest_target(rpm)
            ts = time.strftime("%H:%M:%S")

            if None not in (map_kpa, iat_c, maf_ref):
                maf_est = maf_estimado_gs(rpm, map_kpa, iat_c)
                csv_rows.append([ts, f"{rpm:.0f}", map_kpa, iat_c, f"{maf_est:.3f}", f"{maf_ref:.3f}", target or ""])

                if target is not None:
                    samples[target].append((maf_est, maf_ref))
                    count = len(samples[target])
                    print(f"[{ts}] RPM actual: {rpm:5.0f}  -> objetivo {target} rpm  "
                          f"({min(count, TARGET_SAMPLES)}/{TARGET_SAMPLES})")

                    if count >= TARGET_SAMPLES and target not in listos:
                        listos.add(target)
                        print(f"\n>>> {target} RPM LISTO ({count} muestras). "
                              f"Sube al siguiente regimen. <<<\n")
                        if len(listos) == len(TARGET_RPMS):
                            print(">>> Los 4 puntos completos. Deteniendo la prueba automaticamente. <<<\n")
                            break
                else:
                    print(f"[{ts}] RPM actual: {rpm:5.0f}  (fuera de los 4 puntos objetivo)")
            else:
                print(f"[{ts}] RPM actual: {rpm:5.0f}  (sin MAP/IAT/MAF de referencia todavia)")

            time.sleep(SAMPLE_PERIOD_S)

    except KeyboardInterrupt:
        pass
    finally:
        ser.close()

    csv_path = os.path.abspath("speed_density_log.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["hora", "rpm", "map_kpa", "iat_c", "maf_estimado_gs", "maf_referencia_gs", "rpm_objetivo"])
        w.writerows(csv_rows)

    print("\n================================================")
    print("RESULTADO -- promedios por punto (Tabla 4.x, Fig. 4.9)")
    print("================================================")
    results = {}
    for t in TARGET_RPMS:
        pts = samples[t]
        if not pts:
            print(f"{t:>5} rpm: sin muestras")
            continue
        avg_est = sum(p[0] for p in pts) / len(pts)
        avg_ref = sum(p[1] for p in pts) / len(pts)
        err_pct = ((avg_est - avg_ref) / avg_ref * 100.0) if avg_ref else 0.0
        results[t] = (avg_est, avg_ref, err_pct)
        print(f"{t:>5} rpm (n={len(pts):>3}): estimado={avg_est:.2f} g/s  "
              f"referencia={avg_ref:.2f} g/s  error={err_pct:+.1f}%")
    print("================================================")
    print(f"Log completo ({len(csv_rows)} muestras) guardado en:\n  {csv_path}")

    plot_results(results)

    print(f"\nCarpeta de salida: {os.path.dirname(csv_path)}")


def plot_results(results):
    try:
        import matplotlib.pyplot as plt
    except ModuleNotFoundError:
        print("\nNo se genero la grafica: falta instalar matplotlib.")
        print("Los datos ya estan a salvo en speed_density_log.csv; instala con:")
        print("  pip install matplotlib")
        print("y vuelve a correr el script (reutiliza el CSV o repite la prueba) para generar la figura.")
        return

    targets = [t for t in TARGET_RPMS if t in results]
    if not targets:
        print("Sin datos suficientes para graficar.")
        return

    est_vals = [results[t][0] for t in targets]
    ref_vals = [results[t][1] for t in targets]

    color_est = "#2a78d6"   # azul: Estimado (Speed-Density)
    color_ref = "#eb6834"   # naranja: Referencia (MAF real, PID 0x10)
    color_grid = "#e1e0d9"
    color_ink = "#0b0b0b"
    color_muted = "#52514e"

    x = range(len(targets))
    width = 0.35
    fig, ax = plt.subplots(figsize=(7, 4.5), dpi=150)
    fig.patch.set_facecolor("#fcfcfb")
    ax.set_facecolor("#fcfcfb")

    bars_est = ax.bar([i - width / 2 for i in x], est_vals, width,
                       label="Estimado (Speed-Density)", color=color_est,
                       edgecolor="#fcfcfb", linewidth=0.5)
    bars_ref = ax.bar([i + width / 2 for i in x], ref_vals, width,
                       label="Referencia (MAF real, PID 0x10)", color=color_ref,
                       edgecolor="#fcfcfb", linewidth=0.5)

    for bars in (bars_est, bars_ref):
        for rect in bars:
            h = rect.get_height()
            ax.annotate(f"{h:.1f}", xy=(rect.get_x() + rect.get_width() / 2, h),
                        xytext=(0, 3), textcoords="offset points",
                        ha="center", va="bottom", fontsize=8, color=color_ink)

    ax.set_xticks(list(x))
    ax.set_xticklabels([f"{t} rpm" for t in targets], color=color_ink)
    ax.set_ylabel("Flujo masico de aire (g/s)", color=color_ink)
    ax.set_title("Comparacion MAF estimado vs. referencia por regimen (Nissan Vanette)",
                 color=color_ink, fontsize=10)

    ax.grid(axis="y", color=color_grid, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color(color_muted)
    ax.tick_params(colors=color_muted)

    ax.legend(frameon=False, loc="upper left", fontsize=8, labelcolor=color_ink)

    fig.tight_layout()
    png_path = os.path.abspath("figura_4_9_speed_density.png")
    fig.savefig(png_path, facecolor=fig.get_facecolor())
    print(f"Grafica guardada en:\n  {png_path}")


if __name__ == "__main__":
    main()
