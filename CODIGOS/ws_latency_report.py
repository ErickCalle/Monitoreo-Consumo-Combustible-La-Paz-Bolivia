#!/usr/bin/env python3
"""
Analisis de latencia/estabilidad del panel web -- Tabla y Figura de la
Seccion 4.3.7 (pruebas del panel de control).

web_server.cpp instrumenta el propio panel contando el intervalo real
entre mensajes WebSocket y las reconexiones. Con el panel abierto:
    1. Dejarlo correr el tiempo de la prueba.
    2. Abrir la consola (F12) y correr wsStatsReport() (resumen) y
       wsStatsDownload() (descarga ws_intervals.csv).
    3. python ws_latency_report.py ws_intervals.csv

Genera el resumen estadistico en consola y figura_ws_latencia.png
(histograma con linea vertical en el valor nominal, WS_PUSH_PERIOD_MS).

Requisitos:
    pip install matplotlib
"""
import csv
import statistics
import sys

NOMINAL_MS = 500.0  # WS_PUSH_PERIOD_MS en config.h


def load_intervals(csv_path):
    intervals = []
    with open(csv_path, newline="") as f:
        reader = csv.reader(f)
        next(reader, None)  # encabezado
        for row in reader:
            if not row:
                continue
            try:
                intervals.append(float(row[0]))
            except ValueError:
                continue
    return intervals


def main():
    if len(sys.argv) < 2:
        print("Uso: python ws_latency_report.py ws_intervals.csv")
        sys.exit(1)

    intervals = load_intervals(sys.argv[1])
    if not intervals:
        print("Sin intervalos validos en el archivo.")
        sys.exit(1)

    n = len(intervals)
    mean = statistics.fmean(intervals)
    std = statistics.pstdev(intervals)
    minimo = min(intervals)
    maximo = max(intervals)
    desvio_nominal_pct = (mean - NOMINAL_MS) / NOMINAL_MS * 100.0

    print("================================================")
    print("RESULTADO -- Tabla 4.x, latencia de actualizacion del panel")
    print("================================================")
    print(f"Muestras (n):              {n}")
    print(f"Intervalo nominal:         {NOMINAL_MS:.0f} ms (WS_PUSH_PERIOD_MS)")
    print(f"Media:                     {mean:.1f} ms")
    print(f"Desviacion estandar:       {std:.1f} ms")
    print(f"Minimo:                    {minimo:.1f} ms")
    print(f"Maximo:                    {maximo:.1f} ms")
    print(f"Desvio frente al nominal:  {desvio_nominal_pct:+.1f} %")
    print("================================================")

    plot_histogram(intervals, mean)


def plot_histogram(intervals, mean):
    try:
        import matplotlib.pyplot as plt
    except ModuleNotFoundError:
        print("\nFalta matplotlib para graficar. Instala con: pip install matplotlib")
        return

    color_bars = "#2a78d6"     # azul: distribucion medida
    color_nominal = "#eb6834"  # naranja: referencia nominal
    color_grid = "#e1e0d9"
    color_ink = "#0b0b0b"
    color_muted = "#52514e"

    fig, ax = plt.subplots(figsize=(7, 4.5), dpi=150)
    fig.patch.set_facecolor("#fcfcfb")
    ax.set_facecolor("#fcfcfb")

    ax.hist(intervals, bins=30, color=color_bars, edgecolor="#fcfcfb", linewidth=0.5, zorder=3)
    ax.axvline(NOMINAL_MS, color=color_nominal, linewidth=2, linestyle="--",
               label=f"Nominal ({NOMINAL_MS:.0f} ms)", zorder=4)
    ax.axvline(mean, color=color_ink, linewidth=1.5, linestyle=":",
               label=f"Media medida ({mean:.0f} ms)", zorder=4)

    ax.set_xlabel("Intervalo entre mensajes WebSocket (ms)", color=color_ink)
    ax.set_ylabel("Frecuencia (n° de intervalos)", color=color_ink)
    ax.set_title("Distribución del intervalo de actualización del panel web",
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
    fig.savefig("figura_ws_latencia.png", facecolor=fig.get_facecolor())
    print("\nGrafica guardada: figura_ws_latencia.png")


if __name__ == "__main__":
    main()
