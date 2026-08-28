#!/usr/bin/env python3
"""
Calibracion de la tabla de eficiencia volumetrica (VE) del modelo
Speed-Density -- SOLO para la Seccion 4.3.3 del Capitulo 4, subseccion
"Calibracion del modelo Speed-Density".

Por que existe este script: al correr speed_density_bench.py (RPM-step
estatico en el Nissan Vanette) se encontro un error grande y con signo
variable frente al MAF real (PID 0x10): -23,7% en ralenti, -9,8% en 1500
rpm, +4,7% en 2500 rpm, +18,7% en 3500 rpm. La tabla kVeTable de
fuel_calc.cpp es un valor generico de partida (asi lo dice su propio
comentario), no calibrado a este motor -- y ademas se detecto que
ENGINE_DISPLACEMENT_L estaba en 1.6 L cuando la cilindrada real del
Vanette es 1.626 L (Tabla 4.4). Este script corrige ambas cosas: invierte
la formula de fuel_calc.cpp para despejar, por cada muestra real, la VE
que hace que el estimado coincida exactamente con la referencia, y
promedia esa VE por punto de regimen:

    MAF = (VE/100) * RPM * MAP * Vd * 28.97 / (2 * 8.314 * IAT_K * 60)
    =>  VE_requerida = MAF_ref * 100 * 2 * 8.314 * IAT_K * 60 / (RPM * MAP * Vd * 28.97)

Uso:
    python calibrate_ve_table.py [ruta_al_csv]

Sin argumento, busca speed_density_log.csv en el directorio actual.
Imprime, por punto de regimen (ralenti, 1500, 2500, 3500 rpm):
    - la VE que exigia la tabla vieja (generica) en ese punto
    - la VE real requerida, medida contra el MAF de referencia
    - el fragmento de kVeTable ya calibrado, listo para copiar a
      fuel_calc.cpp y a speed_density_bench.py
    - una segunda pasada de validacion: recalcula el MAF estimado de cada
      muestra usando la tabla YA calibrada y reporta el error residual.

Advertencia metodologica importante: esta validacion usa el MISMO
dataset con el que se calibro, asi que un error residual cercano a 0% en
los 4 puntos calibrados es esperable por construccion (no es evidencia
de que el modelo generalice a otras condiciones) -- confirma que la
inversion algebraica se aplico bien, no reemplaza una validacion
independiente con datos nuevos, que quedo pendiente por no poder volver
a usar el vehiculo.

Requisitos: solo la libreria estandar (csv).
"""
import csv
import sys

DEFAULT_CSV = "speed_density_log.csv"

# --- Motor: Nissan Vanette, cilindrada real (Tabla 4.4, 1626 mL) ---
ENGINE_DISPLACEMENT_L = 1.626

MM_AIR = 28.97   # g/mol
R = 8.314        # L*kPa/(mol*K)

# Tabla VE vieja (generica, la que estaba en fuel_calc.cpp antes de calibrar)
OLD_VE_TABLE = [
    (700,  60.0),
    (1500, 74.0),
    (2500, 85.0),
    (4000, 88.0),
    (5500, 83.0),
    (7000, 74.0),
]


def ve_for_rpm(rpm, table):
    if rpm <= table[0][0]:
        return table[0][1]
    if rpm >= table[-1][0]:
        return table[-1][1]
    for (rpm_a, ve_a), (rpm_b, ve_b) in zip(table, table[1:]):
        if rpm_a <= rpm <= rpm_b:
            t = (rpm - rpm_a) / (rpm_b - rpm_a)
            return ve_a + t * (ve_b - ve_a)
    return table[-1][1]


def maf_estimado_gs(rpm, map_kpa, iat_c, table):
    ve = ve_for_rpm(rpm, table)
    iat_k = iat_c + 273.15
    if iat_k < 233.15 or iat_k > 373.15:
        iat_k = 288.15
    maf = (ve / 100.0) * rpm * map_kpa * ENGINE_DISPLACEMENT_L * MM_AIR / (2.0 * R * iat_k * 60.0)
    return max(maf, 0.0)


def load_rows(csv_path):
    rows = []
    for row in csv.DictReader(open(csv_path)):
        t = row["rpm_objetivo"].strip()
        if not t:
            continue
        rows.append({
            "target": int(float(t)),
            "rpm": float(row["rpm"]),
            "map_kpa": float(row["map_kpa"]),
            "iat_c": float(row["iat_c"]),
            "maf_ref": float(row["maf_referencia_gs"]),
        })
    return rows


def main():
    csv_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CSV
    rows = load_rows(csv_path)
    if not rows:
        print(f"Sin filas con rpm_objetivo en {csv_path}")
        sys.exit(1)

    targets = sorted(set(r["target"] for r in rows))

    # --- Paso 1: invertir la formula por muestra y promediar VE por punto ---
    ve_required = {}
    rpm_avg = {}
    for t in targets:
        pts = [r for r in rows if r["target"] == t]
        ves, rpms = [], []
        for r in pts:
            iat_k = r["iat_c"] + 273.15
            ve = r["maf_ref"] * 100.0 * 2.0 * R * iat_k * 60.0 / (
                r["rpm"] * r["map_kpa"] * ENGINE_DISPLACEMENT_L * MM_AIR)
            ves.append(ve)
            rpms.append(r["rpm"])
        ve_required[t] = sum(ves) / len(ves)
        rpm_avg[t] = sum(rpms) / len(rpms)

    print("================================================")
    print("VE requerida por punto (vs. tabla generica vieja)")
    print("================================================")
    for t in targets:
        ve_old = ve_for_rpm(rpm_avg[t], OLD_VE_TABLE)
        print(f"objetivo={t:5d}  rpm_prom={rpm_avg[t]:7.1f}  "
              f"VE_vieja={ve_old:5.1f}%  VE_requerida={ve_required[t]:5.1f}%")

    # --- Paso 2: construir la tabla calibrada ---
    # Se reemplazan/insertan solo los puntos con datos reales; los
    # extremos sin medir (4000, 5500, 7000) se dejan igual que antes,
    # marcados como no calibrados -- no se inventan valores para ellos.
    new_table = []
    for t in targets:
        new_table.append((t, round(ve_required[t], 1)))
    for rpm_old, ve_old in OLD_VE_TABLE:
        if rpm_old > max(targets):
            new_table.append((rpm_old, ve_old))
    new_table.sort(key=lambda p: p[0])

    print("\n================================================")
    print("kVeTable calibrada -- copiar a fuel_calc.cpp y speed_density_bench.py")
    print("================================================")
    for rpm, ve in new_table:
        calibrado = "calibrado" if rpm in targets else "SIN CALIBRAR (generico)"
        print(f"  {{{rpm:5d}, {ve:5.1f}f}},  // {calibrado}")

    # --- Paso 3: validar re-calculando el estimado con la tabla nueva ---
    print("\n================================================")
    print("VALIDACION -- error residual usando la tabla ya calibrada")
    print("(mismo dataset de calibracion: error ~0% es esperado, no")
    print(" es evidencia de generalizacion a otras condiciones)")
    print("================================================")
    post_calib = {}
    for t in targets:
        pts = [r for r in rows if r["target"] == t]
        est_new = [maf_estimado_gs(r["rpm"], r["map_kpa"], r["iat_c"], new_table) for r in pts]
        ref = [r["maf_ref"] for r in pts]
        avg_est = sum(est_new) / len(est_new)
        avg_ref = sum(ref) / len(ref)
        err_pct = (avg_est - avg_ref) / avg_ref * 100.0
        post_calib[t] = (avg_est, avg_ref, err_pct, len(pts))
        print(f"objetivo={t:5d}  n={len(pts):3d}  estimado={avg_est:.2f} g/s  "
              f"referencia={avg_ref:.2f} g/s  error={err_pct:+.2f}%")

    plot_post_calibration(targets, post_calib)


def plot_post_calibration(targets, post_calib):
    try:
        import matplotlib.pyplot as plt
    except ModuleNotFoundError:
        print("\nFalta matplotlib para generar la grafica de validacion. Instala con:")
        print("  pip install matplotlib")
        return

    labels = [f"Ralentí ({t} rpm)" if t == targets[0] and t < 1200 else f"{t} rpm" for t in targets]
    est_vals = [post_calib[t][0] for t in targets]
    ref_vals = [post_calib[t][1] for t in targets]

    color_est = "#2a78d6"
    color_ref = "#eb6834"
    color_grid = "#e1e0d9"
    color_ink = "#0b0b0b"
    color_muted = "#52514e"

    x = range(len(labels))
    width = 0.35
    fig, ax = plt.subplots(figsize=(7, 4.5), dpi=150)
    fig.patch.set_facecolor("#fcfcfb")
    ax.set_facecolor("#fcfcfb")

    bars_est = ax.bar([i - width / 2 for i in x], est_vals, width,
                       label="Estimado (VE calibrada)", color=color_est,
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
    ax.set_xticklabels(labels, color=color_ink)
    ax.set_ylabel("Flujo másico de aire (g/s)", color=color_ink)
    ax.set_title("MAF estimado (VE calibrada) vs. referencia, mismo dataset de calibración",
                 color=color_ink, fontsize=10)

    ax.grid(axis="y", color=color_grid, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color(color_muted)
    ax.tick_params(colors=color_muted)

    ax.legend(frameon=False, loc="upper left", fontsize=8, labelcolor=color_ink)

    fig.tight_layout()
    fig.savefig("figura_4_10_post_calibracion.png", facecolor=fig.get_facecolor())
    print("\nGrafica de validacion guardada: figura_4_10_post_calibracion.png")


if __name__ == "__main__":
    main()
