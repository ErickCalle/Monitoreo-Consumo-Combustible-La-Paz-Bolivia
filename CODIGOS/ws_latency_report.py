#!/usr/bin/env python3
"""
Analisis de la latencia/estabilidad del panel web -- SOLO para llenar la
Tabla y la Figura de la seccion 4.3.7 del Capitulo 4 ("Pruebas del panel
de control web").

De donde sale el CSV que este script lee: web_server.cpp instrumenta el
propio panel (sin afectar su funcionamiento normal) contando, en el
navegador, el intervalo real entre cada mensaje WebSocket recibido y las
veces que la conexion se cae y se reconecta. Con el panel abierto:

    1. Dejarlo correr el tiempo que dure la prueba (ver protocolo en la
       tesis: sesion corta para latencia, sesion larga para estabilidad).
    2. Abrir la consola del navegador (F12) y correr:
         wsStatsReport()      -> imprime un resumen (n, media, desv,
                                  min, max, reconexiones, duracion)
         wsStatsDownload()    -> descarga ws_intervals.csv con TODOS
                                  los intervalos individuales (ms)
    3. Correr este script sobre ese CSV:
         python ws_latency_report.py ws_intervals.csv

Genera:
    - Resumen estadistico impreso en consola (mismo contenido que
      wsStatsReport(), pero recalculado en Python para el reporte).
    - figura_ws_latencia.png: histograma de los intervalos, con una
      linea vertical marcando el valor nominal (WS_PUSH_PERIOD_MS=500 ms
      en config.h) para visualizar el jitter frente al valor esperado.

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

    color_bars = "#2a78d6"    # slot 1 -- azul: distribucion medida (serie unica)
    color_nominal = "#eb6834"  # slot 2 -- naranja: referencia nominal
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
