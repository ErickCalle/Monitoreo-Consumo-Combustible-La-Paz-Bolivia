#!/usr/bin/env python3
"""
Barras horizontales para la Figura 5.2 (Cap. 5): costo inicial del
sistema propuesto vs. alternativas comerciales, con la fila "Costo
inicial" de la Tabla 5.10.

Solo FuelForce publica un costo inicial de pago unico (USD 5000); el
resto de proveedores revisados cobra suscripcion mensual sin publicar
ese monto, asi que se grafica solo el dato real disponible.

Escala logaritmica en X (rango de 85 a 58 000 Bs) con el valor exacto
como etiqueta en cada barra. Si cambian los montos de la Tabla 5.10,
actualizar ALTERNATIVAS.

Uso:
    python comparacion_comercial_bar.py

Requisitos:
    pip install matplotlib
"""

# (costo inicial en Bs, nota) -- Tabla 5.10
ALTERNATIVAS = [
    ("Sistema propuesto\n(costo marginal/unidad)", 772.22, None),
    ("ELM327 + Car Scanner", 85.00, None),
    ("Telemetría de flota\ncomercial", 58000.00, "FuelForce, pago único\n(USD 5 000); resto de\nproveedores: suscripción"),
]

# Paleta categorica fija del skill de dataviz (orden fijo, no ciclico).
COLORS = ["#2a78d6", "#eb6834", "#1baf7a"]


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

    labels = [a[0] for a in ALTERNATIVAS]
    values = [a[1] for a in ALTERNATIVAS]
    notes = [a[2] for a in ALTERNATIVAS]
    y = range(len(labels))

    fig, ax = plt.subplots(figsize=(7.5, 4.2), dpi=150)
    fig.patch.set_facecolor(color_surface)
    ax.set_facecolor(color_surface)

    ax.barh(list(y), values, color=COLORS, height=0.55, zorder=3)

    for i, (val, note) in enumerate(zip(values, notes)):
        ax.annotate(f"{fmt_bs(val)} Bs", xy=(val, i), xytext=(6, 0),
                    textcoords="offset points", va="center",
                    ha="left", fontsize=9.5, color=color_ink,
                    fontweight="bold")
        if note:
            ax.annotate(note, xy=(val, i), xytext=(6, 18),
                        textcoords="offset points", va="bottom", ha="left",
                        fontsize=7.5, color=color_muted, style="italic")

    ax.set_xscale("log")
    ax.set_yticks(list(y))
    ax.set_yticklabels(labels, color=color_ink, fontsize=9.5)
    ax.invert_yaxis()
    ax.set_xlabel("Costo inicial, Bs (escala logarítmica)", color=color_ink)
    ax.set_xlim(30, 300000)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: fmt_bs(v).split(",")[0]))

    ax.grid(axis="x", which="major", color=color_grid, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color(color_muted)
    ax.tick_params(colors=color_muted, left=False)

    ax.set_title("Costo inicial: sistema propuesto vs. alternativas comerciales",
                  color=color_ink, fontsize=11)

    fig.tight_layout()
    png_path = "figura_comparacion_comercial.png"
    fig.savefig(png_path, facecolor=fig.get_facecolor(), bbox_inches="tight")
    print(f"Grafica guardada: {png_path}")


if __name__ == "__main__":
    plot()
