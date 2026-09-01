#!/usr/bin/env python3
"""
Genera la Figura 4.9 (barras agrupadas, Sección 4.3.3 del Capítulo 4) y la
tabla de promedios directamente a partir de un speed_density_log.csv ya
grabado por speed_density_bench.py -- no requiere el vehículo ni el
ELM327 conectados, solo el CSV.

Uso:
    python plot_speed_density_from_csv.py [ruta_al_csv]

Si no se indica ruta, busca "speed_density_log.csv" en el directorio
actual. Agrupa las filas por la columna rpm_objetivo (ignorando las filas
sin objetivo, que quedaron fuera de tolerancia de los 4 puntos), promedia
maf_estimado_gs y maf_referencia_gs por grupo, calcula el error
porcentual, imprime la tabla lista para el Capítulo 4 y guarda
figura_4_9_speed_density.png en la misma carpeta del CSV.

Requisitos:
    pip install matplotlib
"""
import csv
import os
import sys

DEFAULT_CSV = "speed_density_log.csv"


def load_groups(csv_path):
    groups = {}  # rpm_objetivo (int) -> list of (maf_est, maf_ref)
    with open(csv_path, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            target = row.get("rpm_objetivo", "").strip()
            if not target:
                continue
            target = int(float(target))
            est = float(row["maf_estimado_gs"])
            ref = float(row["maf_referencia_gs"])
            groups.setdefault(target, []).append((est, ref))
    return groups


def summarize(groups):
    ordered_targets = sorted(groups.keys())
    results = {}
    for t in ordered_targets:
        pts = groups[t]
        avg_est = sum(p[0] for p in pts) / len(pts)
        avg_ref = sum(p[1] for p in pts) / len(pts)
        err_pct = ((avg_est - avg_ref) / avg_ref * 100.0) if avg_ref else 0.0
        results[t] = (avg_est, avg_ref, err_pct, len(pts))
    return results


def label_for(t, ordered_targets):
    # el punto mas bajo es el ralenti real medido, no un numero fijo
    if t == ordered_targets[0] and t < 1200:
        return f"Ralentí ({t} rpm)"
    return f"{t} rpm"


def main():
    csv_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CSV
    if not os.path.isfile(csv_path):
        print(f"No se encontro el archivo: {csv_path}")
        sys.exit(1)

    groups = load_groups(csv_path)
    if not groups:
        print("El CSV no tiene ninguna fila con rpm_objetivo asignado.")
        sys.exit(1)

    results = summarize(groups)
    ordered_targets = sorted(results.keys())

    print("================================================")
    print("RESULTADO -- promedios por punto (Tabla 4.x, Fig. 4.9)")
    print("================================================")
    for t in ordered_targets:
        avg_est, avg_ref, err_pct, n = results[t]
        print(f"{label_for(t, ordered_targets):>18} (n={n:>3}): estimado={avg_est:.2f} g/s  "
              f"referencia={avg_ref:.2f} g/s  error={err_pct:+.1f}%")
    print("================================================")

    try:
        import matplotlib.pyplot as plt
    except ModuleNotFoundError:
        print("\nFalta matplotlib para generar la grafica. Instala con:")
        print("  pip install matplotlib")
        sys.exit(1)

    labels = [label_for(t, ordered_targets) for t in ordered_targets]
    est_vals = [results[t][0] for t in ordered_targets]
    ref_vals = [results[t][1] for t in ordered_targets]

    # misma paleta que speed_density_bench.py (azul/naranja)
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
    ax.set_xticklabels(labels, color=color_ink)
    ax.set_ylabel("Flujo másico de aire (g/s)", color=color_ink)
    ax.set_title("Comparación MAF estimado vs. referencia por régimen (Nissan Vanette)",
                 color=color_ink, fontsize=10)

    ax.grid(axis="y", color=color_grid, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color(color_muted)
    ax.tick_params(colors=color_muted)

    ax.legend(frameon=False, loc="upper left", fontsize=8, labelcolor=color_ink)

    fig.tight_layout()
    out_dir = os.path.dirname(os.path.abspath(csv_path))
    png_path = os.path.join(out_dir, "figura_4_9_speed_density.png")
    fig.savefig(png_path, facecolor=fig.get_facecolor())
    print(f"\nGrafica guardada en:\n  {png_path}")


if __name__ == "__main__":
    main()
