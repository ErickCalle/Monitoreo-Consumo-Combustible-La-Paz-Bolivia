#!/usr/bin/env python3
"""
Validacion dinamica del modelo Speed-Density -- SOLO para la Tabla y
Figura de la Seccion 4.4.2 del Capitulo 4 ("Resultados de precision del
modelo Speed-Density"), a partir del registro de una ruta real generado
por speed_density_drive_log.py (Nissan Vanette).

A diferencia de la prueba estatica (calibrate_ve_table.py /
ve_curve_calibrator.py, que ajustan la tabla VE), este script NO
calibra nada -- solo mide que tan bien predice el modelo YA calibrado
sobre datos de una ruta real que nunca participaron en esa calibracion.
Es la validacion independiente documentada como pendiente en el
Capitulo 6.

Metricas, con las mismas formulas ya documentadas en la Seccion
"Herramientas y procesamiento de datos para el analisis" del Capitulo 4:
    RMSE  = sqrt(mean((est-ref)^2))
    MAE   = mean(abs(est-ref))
    MAPE  = mean(abs((est-ref)/ref)) * 100   (excluye ref ~ 0)
    r de Pearson entre estimado y referencia

Uso:
    python speed_density_drive_validation.py speed_density_drive_log.csv

Genera:
    - Resumen de metricas impreso en consola.
    - figura_dispersión_dinamica.png: diagrama de dispersion
      estimado vs. referencia, con la recta 1:1 de referencia.

Requisitos:
    pip install matplotlib
    (no requiere scipy: el coeficiente de Pearson se calcula manual)
"""
import csv
import math
import sys


def load_pairs(csv_path, ref_min=0.1):
    est, ref = [], []
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            try:
                e = float(row["maf_estimado_gs"])
                r = float(row["maf_referencia_gs"])
            except (KeyError, ValueError):
                continue
            if r > ref_min:  # excluye motor detenido / referencia ~0 (evita dividir casi por cero)
                est.append(e)
                ref.append(r)
    return est, ref


def pearson_r(est, ref):
    n = len(est)
    mean_e = sum(est) / n
    mean_r = sum(ref) / n
    cov = sum((e - mean_e) * (r - mean_r) for e, r in zip(est, ref))
    var_e = sum((e - mean_e) ** 2 for e in est)
    var_r = sum((r - mean_r) ** 2 for r in ref)
    if var_e == 0 or var_r == 0:
        return float("nan")
    return cov / math.sqrt(var_e * var_r)


def main():
    if len(sys.argv) < 2:
        print("Uso: python speed_density_drive_validation.py speed_density_drive_log.csv")
        sys.exit(1)

    est, ref = load_pairs(sys.argv[1])
    n = len(est)
    if n < 2:
        print("Muy pocas muestras validas para calcular metricas.")
        sys.exit(1)

    errores = [e - r for e, r in zip(est, ref)]
    rmse = math.sqrt(sum(d ** 2 for d in errores) / n)
    mae = sum(abs(d) for d in errores) / n
    mape = sum(abs(d / r) for d, r in zip(errores, ref)) / n * 100.0
    r_pearson = pearson_r(est, ref)
    r2 = r_pearson ** 2

    print("================================================")
    print("RESULTADO -- Tabla 4.x, validacion dinamica (ruta real, Vanette)")
    print("================================================")
    print(f"Muestras (n):        {n}")
    print(f"RMSE:                {rmse:.3f} g/s")
    print(f"MAE:                 {mae:.3f} g/s")
    print(f"MAPE:                {mape:.2f} %")
    print(f"Pearson r:           {r_pearson:.4f}")
    print(f"R^2:                 {r2:.4f}")
    print("================================================")

    plot_scatter(est, ref, r_pearson)
    plot_error_histogram(errores, ref)


def plot_scatter(est, ref, r_pearson):
    try:
        import matplotlib.pyplot as plt
    except ModuleNotFoundError:
        print("\nFalta matplotlib para graficar. Instala con: pip install matplotlib")
        return

    color_points = "#2a78d6"  # slot 1 -- azul: muestras
    color_ref = "#eb6834"     # slot 2 -- naranja: recta 1:1
    color_grid = "#e1e0d9"
    color_ink = "#0b0b0b"
    color_muted = "#52514e"

    fig, ax = plt.subplots(figsize=(6.5, 6), dpi=150)
    fig.patch.set_facecolor("#fcfcfb")
    ax.set_facecolor("#fcfcfb")

    ax.scatter(ref, est, s=10, color=color_points, alpha=0.5, edgecolors="none",
               label="Muestras (ruta real)", zorder=3)

    lo = min(min(ref), min(est))
    hi = max(max(ref), max(est))
    ax.plot([lo, hi], [lo, hi], color=color_ref, linewidth=2, linestyle="--",
            label="Referencia 1:1", zorder=4)

    ax.set_xlabel("MAF referencia (PID 0x10) [g/s]", color=color_ink)
    ax.set_ylabel("MAF estimado (Speed-Density) [g/s]", color=color_ink)
    ax.set_title(f"Estimado vs. referencia, ruta real (Nissan Vanette) -- r={r_pearson:.3f}",
                 color=color_ink, fontsize=10)

    ax.grid(color=color_grid, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color(color_muted)
    ax.spines["left"].set_color(color_muted)
    ax.tick_params(colors=color_muted)
    ax.set_aspect("equal", adjustable="box")
    ax.legend(frameon=False, loc="upper left", fontsize=8, labelcolor=color_ink)

    fig.tight_layout()
    png_path = "figura_dispersion_dinamica.png"
    fig.savefig(png_path, facecolor=fig.get_facecolor())
    print(f"\nGrafica guardada: {png_path}")


def plot_error_histogram(errores, ref):
    try:
        import matplotlib.pyplot as plt
    except ModuleNotFoundError:
        return  # el aviso ya se imprimio en plot_scatter

    errores_pct = [d / r * 100.0 for d, r in zip(errores, ref)]

    color_bars = "#2a78d6"
    color_zero = "#eb6834"
    color_grid = "#e1e0d9"
    color_ink = "#0b0b0b"
    color_muted = "#52514e"

    fig, ax = plt.subplots(figsize=(7, 4.5), dpi=150)
    fig.patch.set_facecolor("#fcfcfb")
    ax.set_facecolor("#fcfcfb")

    ax.hist(errores_pct, bins=30, color=color_bars, edgecolor="#fcfcfb", linewidth=0.5, zorder=3)
    ax.axvline(0, color=color_zero, linewidth=2, linestyle="--", label="Error 0%", zorder=4)

    ax.set_xlabel("Error porcentual (estimado - referencia) / referencia [%]", color=color_ink)
    ax.set_ylabel("Frecuencia (n° de muestras)", color=color_ink)
    ax.set_title("Distribución del error porcentual, ruta real (Nissan Vanette)",
                 color=color_ink, fontsize=10)

    ax.grid(axis="y", color=color_grid, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color(color_muted)
    ax.spines["left"].set_color(color_muted)
    ax.tick_params(colors=color_muted)
    ax.legend(frameon=False, loc="upper right", fontsize=8, labelcolor=color_ink)

    fig.tight_layout()
    png_path = "figura_histograma_error_dinamico.png"
    fig.savefig(png_path, facecolor=fig.get_facecolor())
    print(f"Grafica guardada: {png_path}")


if __name__ == "__main__":
    main()
