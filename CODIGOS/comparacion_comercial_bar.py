#!/usr/bin/env python3
"""
Grafica de barras horizontales para la Figura 5.2 del Capitulo 5
("Comparacion de costo inicial entre el sistema propuesto y
alternativas comerciales"), a partir de la fila "Costo inicial" de la
Tabla 5.10 (tab:comparacion_comercial) del propio capitulo.

El unico dato de costo inicial (pago unico) disponible para telemetria
de flota comercial es el de FuelForce (USD 5000, fuente citada en la
Nota de la Tabla 5.10); el resto de proveedores revisados (Fleetio,
Geotab, Motive, Samsara) cobra por suscripcion mensual con hardware
aparte, sin publicar ese monto -- por eso NO se promedia ni se inventa
un "costo inicial tipico" de la categoria, se grafica el unico dato
real disponible y se anota su origen para que no se lea como
representativo de todo el rubro.

La escala es logaritmica en el eje X porque el rango de valores abarca
casi tres ordenes de magnitud (85 a 58 000 Bs); en escala lineal las
dos primeras barras serian invisibles. Cada barra lleva su valor
exacto como etiqueta directa para que la distorsion de longitud propia
de la escala log no induzca a error de lectura.

Si cambian los montos de la Tabla 5.10, actualizar el diccionario
ALTERNATIVAS de este script antes de volver a correrlo.

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
