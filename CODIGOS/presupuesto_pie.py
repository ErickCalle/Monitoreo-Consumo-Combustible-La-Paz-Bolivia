#!/usr/bin/env python3
"""
Grafica de pastel para la Figura 5.1 (Cap. 5): distribucion porcentual
del presupuesto total por categoria, con los 4 subtotales ya sumados en
la Tabla 5.9.

Si cambian los subtotales de la Tabla 5.9, actualizar CATEGORIAS aqui
para que no se desincronice con el capitulo.

Uso:
    python presupuesto_pie.py

Requisitos:
    pip install matplotlib
"""

# (subtotal en Bs) -- Tabla 5.9. "Fabricacion y ensamblaje" usa la placa
# preliminar (Robokit, ya soldada a mano), no la cotizacion JLCPCB.
CATEGORIAS = {
    "Componentes\nelectrónicos": 235.79,
    "Desarrollo y\nsoftware": 0.00,
    "Fabricación y\nensamblaje": 154.81,
    "Pruebas y\nvalidación": 316.32,
}

# Paleta categorica fija del skill de dataviz (orden fijo, no ciclico):
# slot1 azul, slot2 naranja, slot3 aqua, slot4 amarillo.
COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]


def fmt_bs(value):
    """1927.8 -> '1.927,80' (separador de miles con punto, decimal con coma)."""
    entero, decimales = f"{value:,.2f}".split(".")
    entero = entero.replace(",", ".")
    return f"{entero},{decimales}"


def plot():
    import matplotlib.pyplot as plt

    color_surface = "#fcfcfb"
    color_ink = "#0b0b0b"
    color_muted = "#52514e"

    labels = list(CATEGORIAS.keys())
    values = list(CATEGORIAS.values())
    total = sum(values)

    fig, ax = plt.subplots(figsize=(7.5, 6), dpi=150)
    fig.patch.set_facecolor(color_surface)
    ax.set_facecolor(color_surface)

    # Desarrollo y software es 0%: una cuna de 0 grados no se ve, se anota aparte
    plot_values = [v if v > 0 else 1e-9 for v in values]

    def autopct_fmt(pct):
        return f"{pct:.2f}".replace(".", ",") + " %"

    wedges, texts, autotexts = ax.pie(
        plot_values,
        colors=COLORS,
        startangle=90,
        counterclock=False,
        wedgeprops={"edgecolor": color_surface, "linewidth": 2},
        autopct=autopct_fmt,
        pctdistance=0.75,
        textprops={"color": "white", "fontsize": 10, "fontweight": "bold"},
    )

    # quitar la etiqueta autopct flotante de la cuna de 0%
    for i, v in enumerate(values):
        if v <= 0:
            autotexts[i].set_text("")

    ax.annotate(
        "Desarrollo y software: 0,00 %\n(tarifa asignada en 0 Bs/h, Tabla 5.5)",
        xy=(0, -1), xytext=(0, -1.35),
        ha="center", va="top", fontsize=8.5, color=color_muted,
    )

    legend_labels = [
        f"{lbl.replace(chr(10), ' ')} ({fmt_bs(val)} Bs)"
        for lbl, val in zip(labels, values)
    ]
    ax.legend(
        wedges, legend_labels,
        loc="center left", bbox_to_anchor=(1.0, 0.5),
        frameon=False, fontsize=9, labelcolor=color_ink,
    )

    ax.set_title(
        f"Distribución del presupuesto total del prototipo (Bs {fmt_bs(total)})",
        color=color_ink, fontsize=11,
    )
    ax.axis("equal")

    fig.tight_layout()
    png_path = "figura_presupuesto_pastel.png"
    fig.savefig(png_path, facecolor=fig.get_facecolor(), bbox_inches="tight")
    print(f"Grafica guardada: {png_path}")


if __name__ == "__main__":
    plot()
