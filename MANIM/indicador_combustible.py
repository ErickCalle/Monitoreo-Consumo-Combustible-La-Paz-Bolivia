"""
Animación de un indicador de nivel de combustible con Manim Community.

Ejecutar:
    manim -pql indicador_combustible.py IndicadorCombustible     # vista rápida
    manim -pqh indicador_combustible.py IndicadorCombustible     # 1080p
    manim -pqh -t indicador_combustible.py IndicadorCombustible  # fondo transparente (.mov)
"""
from manim import *
import numpy as np

# ---------------- Parámetros ----------------
CICLOS = 2                 # cuántas veces se repite el ciclo
CENTRO = DOWN * 1.2        # centro del indicador (eje de la aguja)
RADIO = 3.0                # radio del arco
ANG_E = 150 * DEGREES      # posición de E (vacío)
ANG_F = 30 * DEGREES       # posición de F (lleno)
NIVEL_MEDIO = 0.5          # dónde se queda oscilando (0 = E, 1 = F)

NEGRO = "#111111"
ROJO = "#D0202E"
FONDO = WHITE


def angulo(v):
    """Nivel v (0 = E, 1 = F) -> ángulo de la aguja."""
    return ANG_E + v * (ANG_F - ANG_E)


def build_indicador(ox=None, oy=None, scale=None, nivel=None):
    """Construye el indicador de combustible, reutilizable y transformable
    (mismo patron que motor_4t.build_engine): piezas "fixed" (arco, marcas,
    letras E/F) en coordenadas locales nativas, y piezas "moving" (icono de
    surtidor, aguja) sensibles a 'nivel', ya envueltas para responder a
    ox/oy/scale via always_redraw.

    Devuelve un dict con: nivel, ox, oy, scale, fixed, moving.
    """
    if ox is None:
        ox = ValueTracker(0)
    if oy is None:
        oy = ValueTracker(0)
    if scale is None:
        scale = ValueTracker(1.0)
    if nivel is None:
        nivel = ValueTracker(1.0)

    def off():
        return np.array([ox.get_value(), oy.get_value(), 0.0])

    def xf(mob):
        return mob.scale(scale.get_value(), about_point=ORIGIN).shift(off())

    arco = Arc(radius=RADIO, start_angle=ANG_F - 4 * DEGREES,
               angle=(ANG_E - ANG_F) + 8 * DEGREES, arc_center=CENTRO,
               color=NEGRO, stroke_width=10)

    marcas = VGroup()
    n = 8
    for k in range(n + 1):
        a = angulo(k / n)
        mayor = k % 2 == 0
        largo = 0.55 if mayor else 0.38
        p1 = CENTRO + (RADIO - 0.12) * np.array([np.cos(a), np.sin(a), 0])
        p2 = CENTRO + (RADIO - 0.12 - largo) * np.array([np.cos(a), np.sin(a), 0])
        color = ROJO if k == 0 else NEGRO
        marcas.add(Line(p1, p2, color=color, stroke_width=11 if mayor else 6))

    def letra_local(t, a):
        pos = CENTRO + (RADIO - 0.35) * np.array([np.cos(a), np.sin(a), 0]) + DOWN * 1.35
        return Text(t, font_size=64, weight=BOLD, font="Arial", color=NEGRO).move_to(pos)

    letra_e = letra_local("E", ANG_E)
    letra_f = letra_local("F", ANG_F)

    fixed = VGroup(arco, marcas, letra_e, letra_f)

    def make_icono():
        color = ROJO if nivel.get_value() < 0.12 else NEGRO
        cuerpo = RoundedRectangle(width=0.48, height=0.72, corner_radius=0.06,
                                  stroke_width=0).set_fill(color, 1)
        ventana = Rectangle(width=0.3, height=0.2, stroke_width=0).set_fill(FONDO, 1)
        ventana.move_to(cuerpo.get_top() + DOWN * 0.18)
        base = Rectangle(width=0.62, height=0.1, stroke_width=0).set_fill(color, 1)
        base.next_to(cuerpo, DOWN, buff=0)
        manguera = VMobject(stroke_color=color, stroke_width=5)
        manguera.set_points_smoothly([
            cuerpo.get_left() + UP * 0.2,
            cuerpo.get_left() + LEFT * 0.18 + UP * 0.1,
            cuerpo.get_left() + LEFT * 0.2 + DOWN * 0.25,
            cuerpo.get_left() + LEFT * 0.12 + DOWN * 0.38,
        ])
        boquilla = Rectangle(width=0.08, height=0.2, stroke_width=0).set_fill(color, 1)
        boquilla.move_to(cuerpo.get_left() + LEFT * 0.2 + UP * 0.32)
        flecha = Triangle(stroke_width=0).set_fill(color, 1).scale(0.1).rotate(-PI / 2)
        flecha.next_to(cuerpo, RIGHT, buff=0.08).shift(UP * 0.12)
        return VGroup(manguera, boquilla, cuerpo, ventana, base, flecha).move_to(CENTRO + UP * 1.35)

    def make_aguja():
        a = angulo(nivel.get_value())
        d = np.array([np.cos(a), np.sin(a), 0])
        nrm = np.array([-d[1], d[0], 0])
        punta = CENTRO + d * (RADIO - 0.3)
        cola = CENTRO - d * 0.25
        aguja = Polygon(cola + nrm * 0.09, punta + nrm * 0.04, punta - nrm * 0.04,
                        cola - nrm * 0.09, stroke_width=0).set_fill(ROJO, 1)
        eje = Circle(radius=0.32, stroke_width=0).set_fill(NEGRO, 1).move_to(CENTRO)
        brillo = Circle(radius=0.08, stroke_width=0).set_fill("#444444", 1).move_to(CENTRO)
        return VGroup(aguja, eje, brillo)

    icono = always_redraw(lambda: xf(make_icono()))
    aguja = always_redraw(lambda: xf(make_aguja()))
    moving = VGroup(icono, aguja)

    return {
        "nivel": nivel, "ox": ox, "oy": oy, "scale": scale,
        "fixed": fixed, "moving": moving,
    }


class IndicadorCombustible(Scene):
    def construct(self):
        # Encuadre más cerrado para que el indicador ocupe la pantalla
        # (solo afecta a esta escena en solitario; build_indicador() de
        # arriba no lo toca, para no romper otras escenas que lo importen).
        config.frame_height = 5.6
        config.frame_width = 5.6 * 16 / 9

        self.camera.background_color = FONDO
        nivel = ValueTracker(1.0)  # empieza lleno

        # ================= CARÁTULA =================
        arco = Arc(radius=RADIO, start_angle=ANG_F - 4 * DEGREES,
                   angle=(ANG_E - ANG_F) + 8 * DEGREES, arc_center=CENTRO,
                   color=NEGRO, stroke_width=10)

        marcas = VGroup()
        n = 8  # divisiones (E, 1/8, ..., F)
        for k in range(n + 1):
            a = angulo(k / n)
            mayor = k % 2 == 0
            largo = 0.55 if mayor else 0.38
            p1 = CENTRO + (RADIO - 0.12) * np.array([np.cos(a), np.sin(a), 0])
            p2 = CENTRO + (RADIO - 0.12 - largo) * np.array([np.cos(a), np.sin(a), 0])
            color = ROJO if k == 0 else NEGRO
            marcas.add(Line(p1, p2, color=color, stroke_width=11 if mayor else 6))

        def letra(t, a):
            pos = CENTRO + (RADIO - 0.35) * np.array([np.cos(a), np.sin(a), 0]) + DOWN * 1.35
            return Text(t, font_size=64, weight=BOLD, font="Arial", color=NEGRO).move_to(pos)

        letra_e = letra("E", ANG_E)
        letra_f = letra("F", ANG_F)

        # ================= ÍCONO DE SURTIDOR =================
        def surtidor(color):
            cuerpo = RoundedRectangle(width=0.48, height=0.72, corner_radius=0.06,
                                      stroke_width=0).set_fill(color, 1)
            ventana = Rectangle(width=0.3, height=0.2, stroke_width=0).set_fill(FONDO, 1)
            ventana.move_to(cuerpo.get_top() + DOWN * 0.18)
            base = Rectangle(width=0.62, height=0.1, stroke_width=0).set_fill(color, 1)
            base.next_to(cuerpo, DOWN, buff=0)
            manguera = VMobject(stroke_color=color, stroke_width=5)
            manguera.set_points_smoothly([
                cuerpo.get_left() + UP * 0.2,
                cuerpo.get_left() + LEFT * 0.18 + UP * 0.1,
                cuerpo.get_left() + LEFT * 0.2 + DOWN * 0.25,
                cuerpo.get_left() + LEFT * 0.12 + DOWN * 0.38,
            ])
            boquilla = Rectangle(width=0.08, height=0.2, stroke_width=0).set_fill(color, 1)
            boquilla.move_to(cuerpo.get_left() + LEFT * 0.2 + UP * 0.32)
            flecha = Triangle(stroke_width=0).set_fill(color, 1).scale(0.1).rotate(-PI / 2)
            flecha.next_to(cuerpo, RIGHT, buff=0.08).shift(UP * 0.12)
            return VGroup(manguera, boquilla, cuerpo, ventana, base, flecha)

        icono = always_redraw(
            lambda: surtidor(ROJO if nivel.get_value() < 0.12 else NEGRO)
            .move_to(CENTRO + UP * 1.35)
        )

        # ================= AGUJA =================
        def make_aguja():
            a = angulo(nivel.get_value())
            d = np.array([np.cos(a), np.sin(a), 0])
            nrm = np.array([-d[1], d[0], 0])
            punta = CENTRO + d * (RADIO - 0.3)
            cola = CENTRO - d * 0.25
            aguja = Polygon(cola + nrm * 0.09, punta + nrm * 0.04, punta - nrm * 0.04,
                            cola - nrm * 0.09, stroke_width=0).set_fill(ROJO, 1)
            eje = Circle(radius=0.32, stroke_width=0).set_fill(NEGRO, 1).move_to(CENTRO)
            brillo = Circle(radius=0.08, stroke_width=0).set_fill("#444444", 1).move_to(CENTRO)
            return VGroup(aguja, eje, brillo)

        aguja = always_redraw(make_aguja)

        # ================= ANIMACIÓN =================
        self.play(Create(arco), LaggedStart(*[Create(m) for m in marcas], lag_ratio=0.1),
                  FadeIn(letra_e), FadeIn(letra_f), run_time=1.5)
        self.play(FadeIn(icono), FadeIn(aguja), run_time=0.8)
        self.wait(0.5)

        def oscilar(m, alpha):
            # oscilación amortiguada alrededor del nivel medio (combustible "chapoteando")
            amp = 0.06 * (1 - 0.6 * alpha)
            m.set_value(NIVEL_MEDIO + amp * np.sin(alpha * 5 * TAU))

        for _ in range(CICLOS):
            # 1) De F a la mitad, lento
            self.play(nivel.animate.set_value(NIVEL_MEDIO), run_time=5, rate_func=smooth)
            # 2) Oscila un poco en la mitad
            self.play(UpdateFromAlphaFunc(nivel, oscilar), run_time=3, rate_func=linear)
            # 3) Baja hasta E
            self.play(nivel.animate.set_value(0.0), run_time=4, rate_func=smooth)
            self.wait(1)  # el ícono queda en rojo (reserva)
            # 4) Se llena gradualmente hasta F
            self.play(nivel.animate.set_value(1.0), run_time=4, rate_func=linear)
            self.wait(0.8)
