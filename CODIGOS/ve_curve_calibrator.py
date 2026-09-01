#!/usr/bin/env python3
"""
Calculadora general de la curva de eficiencia volumetrica (VE) para el
modelo Speed-Density -- sirve para cualquier vehiculo, no solo el
Vanette (Capitulo 3, "Calculo general de la eficiencia volumetrica").

La VE no se puede predecir con una formula universal a partir de datos
de catalogo, siempre se obtiene de forma empirica. Este script
generaliza a calibrate_ve_table.py (que solo aceptaba 4 puntos fijos):
agrupa las muestras del CSV en bins de RPM configurables, promedia la
VE requerida por bin (invirtiendo la ecuacion de fuel_calc.cpp),
excluye los bins con pocas muestras en vez de inventar datos, y ajusta
un polinomio cubico eta_v(N) = c0 + c1*N + c2*N^2 + c3*N^3 ponderado
por numero de muestras.

Uso:
    python ve_curve_calibrator.py <csv> <cilindrada_L> [--bin-width 250]
                                   [--min-samples 5] [--vehiculo "Nombre"]

    <csv> debe tener las columnas: rpm, map_kpa, iat_c, maf_referencia_gs
    (mismo formato que genera speed_density_bench.py).

Ejemplo (Nissan Vanette, Vd=1.626 L):
    python ve_curve_calibrator.py speed_density_log.csv 1.626

Requisitos:
    pip install numpy matplotlib
"""
import argparse
import csv

R = 8.314        # L*kPa/(mol*K)
MM_AIR = 28.97   # g/mol


def estimate_ve(rpm, map_kpa, iat_c, maf_ref_gs, displacement_l):
    """Inversion algebraica de la ecuacion de fuel_calc.cpp: despeja VE."""
    iat_k = iat_c + 273.15
    if iat_k < 233.15 or iat_k > 373.15:
        iat_k = 288.15
    if rpm <= 0 or map_kpa <= 0:
        return None
    return maf_ref_gs * 100.0 * 2.0 * R * iat_k * 60.0 / (rpm * map_kpa * displacement_l * MM_AIR)


def load_samples(csv_path, displacement_l):
    samples = []  # (rpm, ve_requerida)
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            try:
                rpm = float(row["rpm"])
                map_kpa = float(row["map_kpa"])
                iat_c = float(row["iat_c"])
                maf_ref = float(row["maf_referencia_gs"])
            except (KeyError, ValueError):
                continue
            ve = estimate_ve(rpm, map_kpa, iat_c, maf_ref, displacement_l)
            if ve is not None and 0.0 < ve < 150.0:  # descarta divisiones por MAP casi nulo, ruido extremo
                samples.append((rpm, ve))
    return samples


def bin_samples(samples, bin_width, min_samples):
    bins = {}
    for rpm, ve in samples:
        k = int(rpm // bin_width)
        bins.setdefault(k, []).append((rpm, ve))

    confident, low_confidence = [], []
    for k in sorted(bins):
        pts = bins[k]
        n = len(pts)
        rpm_center = sum(p[0] for p in pts) / n
        ve_avg = sum(p[1] for p in pts) / n
        entry = (rpm_center, ve_avg, n)
        (confident if n >= min_samples else low_confidence).append(entry)
    return confident, low_confidence


def fit_cubic(confident):
    import numpy as np
    rpms = np.array([p[0] for p in confident])
    ves = np.array([p[1] for p in confident])
    weights = np.array([p[2] for p in confident])
    coeffs = np.polyfit(rpms, ves, deg=3, w=weights)  # c3, c2, c1, c0 (numpy: mayor grado primero)
    fitted = np.polyval(coeffs, rpms)
    ss_res = float(np.sum(weights * (ves - fitted) ** 2))
    ss_tot = float(np.sum(weights * (ves - np.average(ves, weights=weights)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    c3, c2, c1, c0 = coeffs
    return (c0, c1, c2, c3), r2


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv_path", help="CSV con columnas rpm, map_kpa, iat_c, maf_referencia_gs")
    ap.add_argument("displacement_l", type=float, help="Cilindrada del motor en litros (Vd)")
    ap.add_argument("--bin-width", type=float, default=250.0, help="Ancho de bin en rpm (por defecto 250)")
    ap.add_argument("--min-samples", type=int, default=5, help="Minimo de muestras por bin (por defecto 5)")
    ap.add_argument("--vehiculo", default="", help="Nombre del vehiculo, solo para el titulo de la grafica")
    args = ap.parse_args()

    samples = load_samples(args.csv_path, args.displacement_l)
    if not samples:
        print("Sin muestras validas en el CSV.")
        return

    confident, low_confidence = bin_samples(samples, args.bin_width, args.min_samples)

    print("================================================")
    print(f"Bins de confianza (n >= {args.min_samples} muestras)")
    print("================================================")
    for rpm_c, ve_avg, n in confident:
        print(f"  rpm~{rpm_c:7.1f}  VE={ve_avg:5.1f}%  (n={n})")

    if low_confidence:
        print("\nBins de BAJA confianza (excluidos del ajuste, no se inventan):")
        for rpm_c, ve_avg, n in low_confidence:
            print(f"  rpm~{rpm_c:7.1f}  VE={ve_avg:5.1f}%  (n={n} < {args.min_samples})")

    if len(confident) < 4:
        print(f"\nSe necesitan al menos 4 bins de confianza para el ajuste cubico "
              f"(hay {len(confident)}). Recolecta mas datos o reduce --min-samples/--bin-width.")
        return

    (c0, c1, c2, c3), r2 = fit_cubic(confident)
    print("\n================================================")
    print("Curva ajustada: eta_v(N) = c0 + c1*N + c2*N^2 + c3*N^3")
    print("================================================")
    print(f"  c0 = {c0:.6e}")
    print(f"  c1 = {c1:.6e}")
    print(f"  c2 = {c2:.6e}")
    print(f"  c3 = {c3:.6e}")
    print(f"  R^2 = {r2:.4f}")

    plot_curve(confident, low_confidence, (c0, c1, c2, c3), args.vehiculo)


def plot_curve(confident, low_confidence, coeffs, vehiculo):
    try:
        import numpy as np
        import matplotlib.pyplot as plt
    except ModuleNotFoundError:
        print("\nFalta numpy/matplotlib para graficar. Instala con:")
        print("  pip install numpy matplotlib")
        return

    c0, c1, c2, c3 = coeffs
    color_points = "#2a78d6"   # slot 1 -- azul: bins medidos
    color_curve = "#eb6834"    # slot 2 -- naranja: curva ajustada
    color_low = "#898781"      # muted -- bins de baja confianza (excluidos)
    color_grid = "#e1e0d9"
    color_ink = "#0b0b0b"
    color_muted = "#52514e"

    fig, ax = plt.subplots(figsize=(7, 4.5), dpi=150)
    fig.patch.set_facecolor("#fcfcfb")
    ax.set_facecolor("#fcfcfb")

    xs = [p[0] for p in confident]
    ys = [p[1] for p in confident]
    ns = [p[2] for p in confident]
    ax.scatter(xs, ys, s=[20 + 4 * n for n in ns], color=color_points,
               label="VE medida por bin (tamaño = n muestras)", zorder=3)

    if low_confidence:
        xs_lo = [p[0] for p in low_confidence]
        ys_lo = [p[1] for p in low_confidence]
        ax.scatter(xs_lo, ys_lo, s=20, color=color_low, marker="x",
                   label="Baja confianza (excluido del ajuste)", zorder=2)

    rpm_min = min(p[0] for p in confident + low_confidence)
    rpm_max = max(p[0] for p in confident + low_confidence)
    xs_fit = [rpm_min + i * (rpm_max - rpm_min) / 200.0 for i in range(201)]
    ys_fit = [c0 + c1 * x + c2 * x ** 2 + c3 * x ** 3 for x in xs_fit]
    ax.plot(xs_fit, ys_fit, color=color_curve, linewidth=2,
            label="Ajuste cúbico $\\eta_v(N)$", zorder=4)

    ax.set_xlabel("RPM", color=color_ink)
    ax.set_ylabel("Eficiencia volumétrica VE (%)", color=color_ink)
    title = "Curva de eficiencia volumétrica identificada"
    if vehiculo:
        title += f" ({vehiculo})"
    ax.set_title(title, color=color_ink, fontsize=10)

    ax.grid(color=color_grid, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color(color_muted)
    ax.spines["left"].set_color(color_muted)
    ax.tick_params(colors=color_muted)

    ax.legend(frameon=False, loc="best", fontsize=8, labelcolor=color_ink)

    fig.tight_layout()
    png_path = "ve_curve_fit.png"
    fig.savefig(png_path, facecolor=fig.get_facecolor())
    print(f"\nGrafica guardada: {png_path}")


if __name__ == "__main__":
    main()
