"""
Animación del conector OBD-II (SAE J1962) con la función de cada pin.

Ejecutar:
    manim -pql conector_obd2.py ConectorOBD2     # vista rápida
    manim -pqh conector_obd2.py ConectorOBD2     # 1080p
"""
from manim import *
import numpy as np

# =====================================================================
#  AJUSTES
# =====================================================================
FUENTE = "Segoe UI"
FONDO = WHITE
TEXTO = "#2B2B2B"
AZUL_TIT = "#133984"   # XIOPMblue

# Orden en que aparecen los cables
ORDEN = [16, 8, 15, 7, 14, 6, 13, 5, 12, 4]
INCLUIR_RESTO = False          # True = también 11, 3, 10, 2, 9, 1
RESALTAR_PROYECTO = True       # al final resalta los pines que usa tu sistema
PINES_PROYECTO = [4, 5, 6, 14, 16]
PAUSA_CABLE = 0.4              # pausa entre cable y cable

ROJO, MORADO, AZUL, VERDE = "#E53935", "#A93BD6", "#1E88E5", "#2E9E48"
NARANJA, GRIS, GRIS_OSC = "#F39C12", "#8A94A6", "#4A5563"

# pin: (nombre, color)
PINES = {
    1: ("GM UART / ALDL", GRIS),
    2: ("SAE J1850 VPW Bus +", NARANJA),
    3: ("CAN detección de objetos +", GRIS),
    4: ("Tierra del chasis", VERDE),
    5: ("Tierra de señal", VERDE),
    6: ("CAN High (ISO 15765-4)", AZUL),
    7: ("Línea K (ISO 9141-2 / 14230-4)", MORADO),
    8: ("Libre (uso del fabricante)", GRIS),
    9: ("GM UART / ALDL", GRIS),
    10: ("SAE J1850 PWM Bus −", GRIS),
    11: ("CAN detección de objetos −", GRIS),
    12: ("CAN alta velocidad +", GRIS),
    13: ("CAN alta velocidad −", GRIS),
    14: ("CAN Low (ISO 15765-4)", AZUL),
    15: ("Línea L (ISO 9141-2 / 14230-4)", MORADO),
    16: ("Alimentación batería (+12 V)", ROJO),
}

# =====================================================================
#  GEOMETRÍA
# =====================================================================
CY = 0.05                      # centro vertical del conector
PASO = 0.62                    # separación entre pines
X0 = -3.5 * PASO               # x del pin 1 / pin 9
Y_SUP, Y_INF = CY + 0.36, CY - 0.36
LADO_PIN = 0.44
X_DER, X_IZQ = 3.25, -3.25     # donde terminan los cables

# Altura del tramo horizontal de cada cable (anidados para que no se crucen)
NIVEL = {
    # fila superior -> suben
    6: 2.3, 7: 1.75, 8: 1.2,                      # derecha
    5: 2.3, 4: 1.75, 3: 2.85, 2: 1.2, 1: 0.65,     # izquierda (5 alineado con 6, 4 con 7)
    # fila inferior -> bajan
    13: -2.85, 14: -2.3, 15: -1.75, 16: -1.2,   # derecha
    12: -2.85, 11: -2.3, 10: -1.75, 9: -1.2,    # izquierda
}


def pos_pin(n):
    if n <= 8:
        return np.array([X0 + (n - 1) * PASO, Y_SUP, 0])
    return np.array([X0 + (n - 9) * PASO, Y_INF, 0])


def lado_pin(n):
    """Derecha: 6-8 y 13-16. Izquierda: 1-5 y 9-12 (tierra de señal,
    pin 5, se agrupa con tierra de chasis, pin 4, del lado izquierdo)."""
    if n == 5:
        return -1
    k = n if n <= 8 else n - 8
    return 1 if k >= 5 else -1


def build_conector(pines_dict=None):
    """Construye el conector OBD-II + los 16 pines (sin cables todavia),
    reutilizable fuera de esta escena. Devuelve (conector, pines) donde
    'pines' es un dict {n: VGroup(caja, numero)} ya posicionado segun
    pos_pin(n). No depende de self/Scene.
    """
    sup, inf, h = 5.7, 4.9, 1.75
    carcasa = Polygon([-sup / 2, CY + h / 2, 0], [sup / 2, CY + h / 2, 0],
                      [inf / 2, CY - h / 2, 0], [-inf / 2, CY - h / 2, 0],
                      stroke_color="#2A3442", stroke_width=3).set_fill("#4B5A6C", 1)
    carcasa.round_corners(0.28)
    k = 0.17
    cara = Polygon([-sup / 2 + k, CY + h / 2 - k, 0], [sup / 2 - k, CY + h / 2 - k, 0],
                   [inf / 2 - k, CY - h / 2 + k, 0], [-inf / 2 + k, CY - h / 2 + k, 0],
                   stroke_width=0).set_fill("#2F3B4A", 1)
    cara.round_corners(0.2)
    nervio = RoundedRectangle(width=5.0, height=0.14, corner_radius=0.06,
                              stroke_width=0).set_fill("#5C6B7E", 1).move_to([0, CY, 0])
    lengueta = RoundedRectangle(width=0.9, height=0.28, corner_radius=0.06,
                                stroke_color="#2A3442", stroke_width=3).set_fill("#4B5A6C", 1)
    lengueta.move_to([0, CY - h / 2 - 0.08, 0])
    conector = VGroup(lengueta, carcasa, cara, nervio)

    pines = {}
    for n in range(1, 17):
        caja = RoundedRectangle(width=LADO_PIN, height=LADO_PIN, corner_radius=0.06,
                                stroke_color="#C9D1DC", stroke_width=2).set_fill("#1F2833", 1)
        num = Text(str(n), font=FUENTE, font_size=22, weight=BOLD, color=WHITE)
        num.scale_to_fit_height(min(num.height, 0.2)).move_to(caja)
        pines[n] = VGroup(caja, num).move_to(pos_pin(n))

    return conector, pines


def make_cable_anims(n, pin, pines_dict):
    """Construye (sin reproducir) las animaciones del cable del pin n,
    usando los nombres/colores de 'pines_dict'. Devuelve dos listas de
    animaciones: (anims_cable, anims_etiqueta), para que el llamador
    controle el run_time."""
    nombre, color = pines_dict[n]
    p = pos_pin(n)
    s = lado_pin(n)
    arriba = n <= 8
    y_n = NIVEL[n]
    inicio = p + (UP if arriba else DOWN) * (LADO_PIN / 2)
    codo = np.array([p[0], y_n, 0])
    fin = np.array([X_DER if s > 0 else X_IZQ, y_n, 0])

    linea = VMobject(stroke_color=color, stroke_width=4)
    linea.set_points_as_corners([inicio, codo, fin])
    punto = Dot(fin, radius=0.06, color=color)

    col_txt = GRIS_OSC if color == GRIS else color
    etiqueta = Text(nombre, font=FUENTE, font_size=20, weight=BOLD, color=col_txt)
    if etiqueta.width > 3.5:
        etiqueta.scale_to_fit_width(3.5)
    if s > 0:
        etiqueta.next_to(fin, RIGHT, buff=0.15)
    else:
        etiqueta.next_to(fin, LEFT, buff=0.15)

    anims_cable = [pin[0].animate.set_fill(color, 1).set_stroke(color), Create(linea)]
    anims_etiqueta = [FadeIn(punto, scale=2), Write(etiqueta)]
    return anims_cable, anims_etiqueta


# =====================================================================
#  ESCENA
# =====================================================================
class ConectorOBD2(Scene):
    def construct(self):
        self.camera.background_color = FONDO

        titulo = Text("Conector OBD-II (SAE J1962)", font=FUENTE, font_size=30,
                      weight=BOLD, color=AZUL_TIT).to_corner(UL, buff=0.35)
        barrita = Rectangle(width=0.1, height=titulo.height + 0.08, stroke_width=0)
        barrita.set_fill(AZUL_TIT, 1).next_to(titulo, LEFT, buff=0.12)

        # ---------- Conector ----------
        sup, inf, h = 5.7, 4.9, 1.75
        carcasa = Polygon([-sup / 2, CY + h / 2, 0], [sup / 2, CY + h / 2, 0],
                          [inf / 2, CY - h / 2, 0], [-inf / 2, CY - h / 2, 0],
                          stroke_color="#2A3442", stroke_width=3).set_fill("#4B5A6C", 1)
        carcasa.round_corners(0.28)
        k = 0.17
        cara = Polygon([-sup / 2 + k, CY + h / 2 - k, 0], [sup / 2 - k, CY + h / 2 - k, 0],
                       [inf / 2 - k, CY - h / 2 + k, 0], [-inf / 2 + k, CY - h / 2 + k, 0],
                       stroke_width=0).set_fill("#2F3B4A", 1)
        cara.round_corners(0.2)
        nervio = RoundedRectangle(width=5.0, height=0.14, corner_radius=0.06,
                                  stroke_width=0).set_fill("#5C6B7E", 1).move_to([0, CY, 0])
        lengueta = RoundedRectangle(width=0.9, height=0.28, corner_radius=0.06,
                                    stroke_color="#2A3442", stroke_width=3).set_fill("#4B5A6C", 1)
        lengueta.move_to([0, CY - h / 2 - 0.08, 0])
        conector = VGroup(lengueta, carcasa, cara, nervio)

        # ---------- Pines ----------
        pines = {}
        for n in range(1, 17):
            caja = RoundedRectangle(width=LADO_PIN, height=LADO_PIN, corner_radius=0.06,
                                    stroke_color="#C9D1DC", stroke_width=2).set_fill("#1F2833", 1)
            num = Text(str(n), font=FUENTE, font_size=22, weight=BOLD, color=WHITE)
            num.scale_to_fit_height(min(num.height, 0.2)).move_to(caja)
            pines[n] = VGroup(caja, num).move_to(pos_pin(n))

        self.play(GrowFromEdge(barrita, DOWN), FadeIn(titulo, shift=RIGHT * 0.3), run_time=0.8)
        self.play(FadeIn(conector, scale=0.85), run_time=1.2)
        self.play(LaggedStart(*[FadeIn(pines[n][0], scale=0.6) for n in range(1, 17)],
                              lag_ratio=0.06), run_time=1.2)
        self.play(LaggedStart(*[Write(pines[n][1]) for n in range(1, 17)], lag_ratio=0.06),
                  run_time=1.6)
        self.wait(0.5)

        # ---------- Cables ----------
        orden = ORDEN + ([11, 3, 10, 2, 9, 1] if INCLUIR_RESTO else [])
        for n in orden:
            self.cable(n, pines[n])
            self.wait(PAUSA_CABLE)

        # ---------- Resaltar pines del proyecto ----------
        if RESALTAR_PROYECTO:
            self.wait(0.6)
            marcos = VGroup(*[
                SurroundingRectangle(pines[n], buff=0.07, corner_radius=0.08,
                                     stroke_color="#F4B400", stroke_width=5)
                for n in PINES_PROYECTO])
            nota = Text("Pines utilizados por el sistema", font=FUENTE, font_size=24,
                        weight=BOLD, color="#B07F00")
            nota.move_to([0, -3.55, 0])
            self.play(LaggedStart(*[Create(m) for m in marcos], lag_ratio=0.15),
                      FadeIn(nota, shift=UP * 0.2), run_time=1.5)
            self.play(*[Indicate(pines[n], color="#F4B400", scale_factor=1.15)
                        for n in PINES_PROYECTO], run_time=1.2)
        self.wait(2)

    # -----------------------------------------------------------------
    def cable(self, n, pin):
        nombre, color = PINES[n]
        p = pos_pin(n)
        s = lado_pin(n)
        arriba = n <= 8
        y_n = NIVEL[n]
        inicio = p + (UP if arriba else DOWN) * (LADO_PIN / 2)
        codo = np.array([p[0], y_n, 0])
        fin = np.array([X_DER if s > 0 else X_IZQ, y_n, 0])

        linea = VMobject(stroke_color=color, stroke_width=4)
        linea.set_points_as_corners([inicio, codo, fin])
        punto = Dot(fin, radius=0.06, color=color)

        col_txt = GRIS_OSC if color == GRIS else color
        etiqueta = Text(nombre, font=FUENTE, font_size=20, weight=BOLD, color=col_txt)
        if etiqueta.width > 3.5:
            etiqueta.scale_to_fit_width(3.5)
        if s > 0:
            etiqueta.next_to(fin, RIGHT, buff=0.15)
        else:
            etiqueta.next_to(fin, LEFT, buff=0.15)

        self.play(pin[0].animate.set_fill(color, 1).set_stroke(color),
                  Create(linea), run_time=0.9, rate_func=smooth)
        self.play(FadeIn(punto, scale=2), Write(etiqueta), run_time=0.7)
