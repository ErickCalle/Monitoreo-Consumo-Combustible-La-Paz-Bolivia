#!/usr/bin/env python3
"""
Grafica de la Figura 5.3 (Cap. 5): punto de equilibrio entre el costo
del prototipo y el ahorro acumulado de combustible, con las tablas 5.9
y 5.11.

Ahorro acumulado = ahorro mensual (Tabla 5.11) x mes, una recta por
vehiculo. El cruce con la linea de costo (Tabla 5.9) es el periodo de
recuperacion. Si cambian los montos de esas tablas, actualizar las
constantes de abajo.

Uso:
    python breakeven_plot.py

Requisitos:
    pip install matplotlib
"""

COSTO_PROTOTIPO_BS = 706.92  # Tabla 5.9 (placa preliminar Robokit + carcasa)

# (ahorro mensual Bs/mes, periodo de recuperacion meses) -- Tabla 5.11
VEHICULOS = {
    "Nissan Vanette": {"ahorro_mensual": 287.47, "payback_meses": 2.46, "color": "#2a78d6"},
    "Changan Honor":  {"ahorro_mensual": 218.84, "payback_meses": 3.23, "color": "#eb6834"},
}

MESES_MAX = 5


def fmt_bs(value):
    entero, decimales = f"{value:,.2f}".split(".")
    entero = entero.replace(",", ".")
    return f"{entero},{decimales}"


def plot():
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter

    color_surface = "#fcfcfb"
    color_ink = "#0b0b0b"
    color_muted = "#52514e"
    color_grid = "#e1e0d9"

    xs = [m * 0.1 for m in range(0, MESES_MAX * 10 + 1)]

    fig, ax = plt.subplots(figsize=(7.5, 5), dpi=150)
    fig.patch.set_facecolor(color_surface)
    ax.set_facecolor(color_surface)

    ax.axhline(COSTO_PROTOTIPO_BS, color=color_muted, linewidth=1.6,
               linestyle=(0, (5, 3)), zorder=2)
    ax.annotate(f"Costo total del prototipo: {fmt_bs(COSTO_PROTOTIPO_BS)} Bs",
                xy=(0.3, COSTO_PROTOTIPO_BS), xytext=(0, 8),
                textcoords="offset points", fontsize=9, color=color_muted,
                va="bottom", ha="left")

    for nombre, d in VEHICULOS.items():
        ys = [d["ahorro_mensual"] * x for x in xs]
        ax.plot(xs, ys, color=d["color"], linewidth=2.2, label=nombre, zorder=3)
        px, py = d["payback_meses"], COSTO_PROTOTIPO_BS
        ax.plot([px], [py], marker="o", color=d["color"], markersize=6, zorder=4)
        ax.annotate(f"{d['payback_meses']:.2f} meses".replace(".", ","),
                    xy=(px, py), xytext=(6, -14), textcoords="offset points",
                    fontsize=8.5, color=d["color"], fontweight="bold")
        ax.plot([px, px], [0, py], color=d["color"], linewidth=1, linestyle=":", zorder=1)

    ax.set_xlim(0, MESES_MAX)
    ax.set_ylim(0, COSTO_PROTOTIPO_BS * 1.25)
    ax.set_xlabel("Tiempo (meses)", color=color_ink)
    ax.set_ylabel("Ahorro acumulado (Bs)", color=color_ink)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}".replace(",", ".")))
    ax.set_title("Punto de equilibrio: ahorro acumulado vs. costo del prototipo",
                  color=color_ink, fontsize=11)

    ax.grid(color=color_grid, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color(color_muted)
    ax.spines["left"].set_color(color_muted)
    ax.tick_params(colors=color_muted)
    ax.legend(frameon=False, loc="upper left", fontsize=9, labelcolor=color_ink)

    fig.tight_layout()
    png_path = "figura_breakeven.png"
    fig.savefig(png_path, facecolor=fig.get_facecolor(), bbox_inches="tight")
    print(f"Grafica guardada: {png_path}")


if __name__ == "__main__":
    plot()
