#!/usr/bin/env python3
"""
Impacto de la curva VE en el consumo estimado -- Seccion 4.4.5
(consumo estimado vs. real), a partir de un registro real
(speed_density_drive_log.csv, Nissan Vanette).

Conecta la curva VE(N) calibrada (Figura 3.x) con su efecto en litros:
convierte el MAF estimado y el de referencia a L/100km por muestra,
agrupa por bin de RPM, y grafica dos paneles que comparten el eje de
RPM: la curva VE(N) arriba, y el error de consumo promedio por bin
abajo (subestima en azul, sobrestima en naranja).

Uso:
    python ve_consumo_impacto.py speed_density_drive_log.csv

Requisitos:
    pip install matplotlib
"""
import csv
import sys

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

FUEL_AFR_STOICH = 14.7
FUEL_DENSITY_G_PER_L = 745.0

BIN_WIDTH_RPM = 250
MIN_SAMPLES_PER_BIN = 5


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


def maf_to_L100km(maf_gs, speed_kmh):
    fuel_gs = maf_gs / FUEL_AFR_STOICH
    instant_Lh = fuel_gs * 3600.0 / FUEL_DENSITY_G_PER_L
    return (instant_Lh / speed_kmh) * 100.0 if speed_kmh > 2.0 else None


def load_samples(csv_path):
    samples = []  # (rpm, error_L100km = est - ref)
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            try:
                rpm = float(row["rpm"])
                speed_kmh = float(row["speed_kmh"])
                maf_est = float(row["maf_estimado_gs"])
                maf_ref = float(row["maf_referencia_gs"])
            except (KeyError, ValueError):
                continue
            if maf_ref <= 0.1:
                continue
            l100_est = maf_to_L100km(maf_est, speed_kmh)
            l100_ref = maf_to_L100km(maf_ref, speed_kmh)
            if l100_est is None or l100_ref is None:
                continue
            samples.append((rpm, l100_est - l100_ref))
    return samples


def bin_samples(samples):
    bins = {}
    for rpm, err in samples:
        k = int(rpm // BIN_WIDTH_RPM)
        bins.setdefault(k, []).append((rpm, err))

    result = []
    for k in sorted(bins):
        pts = bins[k]
        if len(pts) < MIN_SAMPLES_PER_BIN:
            continue
        n = len(pts)
        rpm_center = sum(p[0] for p in pts) / n
        err_avg = sum(p[1] for p in pts) / n
        result.append((rpm_center, err_avg, n))
    return result


def main():
    if len(sys.argv) < 2:
        print("Uso: python ve_consumo_impacto.py speed_density_drive_log.csv")
        sys.exit(1)

    samples = load_samples(sys.argv[1])
    if not samples:
        print("Sin muestras validas (revisa que el CSV tenga las columnas esperadas).")
        sys.exit(1)

    bins = bin_samples(samples)
    if len(bins) < 2:
        print(f"Muy pocos bins de confianza ({len(bins)}) para graficar.")
        sys.exit(1)

    print("================================================")
    print("Error de consumo por bin de RPM (estimado - referencia)")
    print("================================================")
    for rpm_c, err_avg, n in bins:
        print(f"  rpm~{rpm_c:7.1f}  VE={ve_for_rpm(rpm_c):5.1f}%  "
              f"error={err_avg:+.2f} L/100km  (n={n})")

    plot(bins)


def plot(bins):
    try:
        import matplotlib.pyplot as plt
    except ModuleNotFoundError:
        print("\nFalta matplotlib para graficar. Instala con: pip install matplotlib")
        return

    color_ve = "#2a78d6"
    color_under = "#2a78d6"   # subestima (azul)
    color_over = "#eb6834"    # sobrestima (naranja)
    color_grid = "#e1e0d9"
    color_ink = "#0b0b0b"
    color_muted = "#52514e"

    rpm_min = min(b[0] for b in bins)
    rpm_max = max(b[0] for b in bins)

    fig, (ax_ve, ax_err) = plt.subplots(
        2, 1, figsize=(7.5, 6.5), dpi=150, sharex=True,
        gridspec_kw={"height_ratios": [1, 1.2]})
    fig.patch.set_facecolor("#fcfcfb")

    # --- Panel superior: curva VE(N) calibrada ---
    ax_ve.set_facecolor("#fcfcfb")
    xs_curve = [rpm_min + i * (rpm_max - rpm_min) / 200.0 for i in range(201)]
    ys_curve = [ve_for_rpm(x) for x in xs_curve]
    ax_ve.plot(xs_curve, ys_curve, color=color_ve, linewidth=2, label="VE calibrada (kVeTable)")
    ax_ve.set_ylabel("VE (%)", color=color_ink)
    ax_ve.set_title("Curva VE calibrada y su impacto en el consumo estimado, ruta real (Nissan Vanette)",
                     color=color_ink, fontsize=10)
    ax_ve.grid(color=color_grid, linewidth=0.8, zorder=0)
    ax_ve.set_axisbelow(True)
    for spine in ("top", "right"):
        ax_ve.spines[spine].set_visible(False)
    ax_ve.spines["bottom"].set_color(color_muted)
    ax_ve.spines["left"].set_color(color_muted)
    ax_ve.tick_params(colors=color_muted)
    ax_ve.legend(frameon=False, loc="best", fontsize=8, labelcolor=color_ink)

    # --- Panel inferior: error de consumo (L/100km) por bin de RPM ---
    ax_err.set_facecolor("#fcfcfb")
    xs = [b[0] for b in bins]
    ys = [b[1] for b in bins]
    colors = [color_over if y >= 0 else color_under for y in ys]
    width = BIN_WIDTH_RPM * 0.8
    ax_err.bar(xs, ys, width=width, color=colors, edgecolor="#fcfcfb", linewidth=0.5, zorder=3)
    ax_err.axhline(0, color=color_muted, linewidth=1, zorder=2)

    ax_err.set_xlabel("RPM", color=color_ink)
    ax_err.set_ylabel("Error de consumo\n(estimado - referencia) [L/100km]", color=color_ink)
    ax_err.grid(axis="y", color=color_grid, linewidth=0.8, zorder=0)
    ax_err.set_axisbelow(True)
    for spine in ("top", "right"):
        ax_err.spines[spine].set_visible(False)
    ax_err.spines["bottom"].set_color(color_muted)
    ax_err.spines["left"].set_color(color_muted)
    ax_err.tick_params(colors=color_muted)

    from matplotlib.patches import Patch
    legend_elems = [
        Patch(facecolor=color_over, label="Sobrestima consumo"),
        Patch(facecolor=color_under, label="Subestima consumo"),
    ]
    ax_err.legend(handles=legend_elems, frameon=False, loc="best", fontsize=8, labelcolor=color_ink)

    fig.tight_layout()
    png_path = "figura_ve_consumo_impacto.png"
    fig.savefig(png_path, facecolor=fig.get_facecolor())
    print(f"\nGrafica guardada: {png_path}")


if __name__ == "__main__":
    main()
