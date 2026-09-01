#!/usr/bin/env python3
"""
Barras agrupadas para la Figura 4.x (Cap. 4): consumo por tramo y
vehiculo, con los 9 tramos de las Tablas 4.18/4.19 (Nissan Vanette /
Changan Honor) cargados a mano -- son solo 18 numeros por vehiculo, ya
validados en el texto, no vale la pena un CSV aparte.

Si cambian los valores de las tablas, actualizar VANETTE/CHANGAN aqui
para que no queden desincronizados con el capitulo.

Uso:
    python comparacion_consumo_plot.py

Requisitos:
    pip install matplotlib
"""

TRAYECTOS = [
    "Corto 1\n(ida)", "Corto 1\n(vuelta)", "Corto 2\n(ida)", "Corto 2\n(vuelta)",
    "Medio 1\n(ida)", "Medio 1\n(vuelta)", "Medio 2\n(ida)", "Medio 2\n(vuelta)",
    "Largo",
]

# (sistema propio, ELM327 + app), litros -- Tablas 4.18/4.19 del Capitulo 4
VANETTE = {
    "sistema": [0.52, 0.46, 1.12, 1.24, 1.23, 1.57, 1.66, 1.86, 2.43],
    "elm327":  [0.50, 0.49, 1.15, 1.28, 1.22, 1.61, 1.68, 1.89, 2.44],
}
CHANGAN = {
    "sistema": [0.519, 0.580, 0.60, 0.40, 1.000, 1.39, 1.30, 1.71, 1.839],
    "elm327":  [0.527, 0.569, 0.56, 0.420, 0.991, 1.31, 1.33, 1.68, 1.825],
}


def plot():
    import matplotlib.pyplot as plt

    color_sistema = "#2a78d6"  # slot 1 -- azul: sistema propuesto
    color_elm327 = "#eb6834"   # slot 2 -- naranja: ELM327 + app
    color_grid = "#e1e0d9"
    color_ink = "#0b0b0b"
    color_muted = "#52514e"

    fig, axes = plt.subplots(2, 1, figsize=(10, 8.5), dpi=150, sharey=False)
    fig.patch.set_facecolor("#fcfcfb")

    datasets = [("Nissan Vanette", VANETTE), ("Changan Honor", CHANGAN)]

    for ax, (titulo, data) in zip(axes, datasets):
        ax.set_facecolor("#fcfcfb")
        x = range(len(TRAYECTOS))
        width = 0.35

        bars_s = ax.bar([i - width / 2 for i in x], data["sistema"], width,
                         label="Sistema propuesto", color=color_sistema,
                         edgecolor="#fcfcfb", linewidth=0.5, zorder=3)
        bars_e = ax.bar([i + width / 2 for i in x], data["elm327"], width,
                         label="ELM327 + app", color=color_elm327,
                         edgecolor="#fcfcfb", linewidth=0.5, zorder=3)

        for bars in (bars_s, bars_e):
            for rect in bars:
                h = rect.get_height()
                ax.annotate(f"{h:.2f}", xy=(rect.get_x() + rect.get_width() / 2, h),
                            xytext=(0, 3), textcoords="offset points",
                            ha="center", va="bottom", fontsize=7, color=color_ink)

        ax.set_xticks(list(x))
        ax.set_xticklabels(TRAYECTOS, color=color_ink, fontsize=8)
        ax.set_ylabel("Combustible (L)", color=color_ink)
        ax.set_title(titulo, color=color_ink, fontsize=10)

        ax.grid(axis="y", color=color_grid, linewidth=0.8, zorder=0)
        ax.set_axisbelow(True)
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)
        ax.spines["bottom"].set_color(color_muted)
        ax.spines["left"].set_color(color_muted)
        ax.tick_params(colors=color_muted)
        ax.legend(frameon=False, loc="upper left", fontsize=8, labelcolor=color_ink)

    fig.suptitle("Consumo por tramo: sistema propuesto vs. ELM327 + Car Scanner",
                  color=color_ink, fontsize=11)
    fig.tight_layout()
    png_path = "figura_comparacion_consumo.png"
    fig.savefig(png_path, facecolor=fig.get_facecolor())
    print(f"Grafica guardada: {png_path}")


if __name__ == "__main__":
    plot()
