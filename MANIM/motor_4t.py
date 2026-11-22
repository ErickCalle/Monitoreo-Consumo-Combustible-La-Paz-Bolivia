"""
Animación de un motor de 4 tiempos (corte transversal) con Manim Community.

Ejecutar:
    manim -pqh motor_4t.py Motor4T        # alta calidad (1080p)
    manim -pql motor_4t.py Motor4T        # vista rápida (480p)
"""
from manim import *
import numpy as np

# ---------------- Parámetros geométricos ----------------
C = np.array([0.0, -2.2, 0.0])   # centro del cigüeñal
R_CRANK = 0.70                   # radio de manivela (carrera = 2*R)
L_ROD = 2.00                     # longitud de la biela
BORE = 0.92                      # medio diámetro del cilindro
Y_DECK = 1.25                    # inicio de la culata
DOME = 0.37                      # altura de la cámara de combustión
PIN_TOP = 0.50                   # del bulón a la cabeza del pistón
PIN_BOT = 0.30                   # del bulón a la falda del pistón

# ---------------- Colores ----------------
C_BLOQUE = "#8A98A8"
C_INTERIOR = "#DDE7F0"
C_CULATA = "#6F7D8C"
C_PISTON = "#B7BEC6"
C_BIELA = "#5E6B78"
C_CIG = "#3E4852"
C_VALV = "#9AA3AD"
C_LABEL = "#1F2A36"

# Colores del gas según el tiempo del ciclo
GAS_ADM = "#4FA3E0"   # mezcla aire-combustible
GAS_COMP = "#2F6FB0"  # mezcla comprimida
GAS_EXP = "#FF7A1A"   # combustión
GAS_ESC = "#8C8C8C"   # gases de escape

ANG_V = 20 * DEGREES  # inclinación de las válvulas


def dome_y(x):
    """Altura del techo de la cámara de combustión (parábola)."""
    return Y_DECK + DOME * (1 - (x / BORE) ** 2)


def crank_pin(t):
    """Posición del muñón de biela (giro horario, t=0 en PMS)."""
    return C + R_CRANK * np.array([np.sin(t), np.cos(t), 0])


def piston_pin(t):
    """Posición del bulón: cinemática biela-manivela."""
    y = C[1] + R_CRANK * np.cos(t) + np.sqrt(L_ROD**2 - (R_CRANK * np.sin(t)) ** 2)
    return np.array([0.0, y, 0.0])


def fase(t):
    """Devuelve (índice de tiempo 0-3, avance 0-1 dentro del tiempo)."""
    a = t % (4 * PI)
    i = int(a // PI)
    return i, (a - i * PI) / PI


def build_engine(ox=None, oy=None, theta=None, scale=None):
    """Construye el motor de 4 tiempos, reutilizable y transformable.

    Pensado para combinarse con otra escena (p. ej. la deduccion del
    metodo Speed-Density): se puede mover (ox/oy) y escalar (scale) el
    motor completo sin romper las piezas que dependen de theta
    (piston, biela, ciguenal, valvulas, gas, chispa).

    ox, oy, scale, theta: ValueTracker opcionales (se crean si no se
    pasan, con scale=1 y el resto en 0).

    Devuelve un dict con:
      - theta, ox, oy, scale: los ValueTracker.
      - fixed: VGroup estatico (bloque, interior, culata, camara,
        puertos, bujia) en coordenadas LOCALES nativas (como en
        Motor4T) -- no depende de theta ni de los trackers; quien lo
        use debe animarlo con .animate.scale(s, about_point=ORIGIN)
        .shift(v) a la vez que anima scale/ox/oy con los MISMOS
        valores, para que quede sincronizado con moving.
      - moving: VGroup animado por theta, ya sensible a
        ox/oy/scale (se reconstruye cada frame).
      - chamber_point(), crank_point(): devuelven la posicion actual
        (mundo) de la camara de combustion y del eje del ciguenal,
        utiles para apuntar la camara.
    """
    if theta is None:
        theta = ValueTracker(0)
    if ox is None:
        ox = ValueTracker(0)
    if oy is None:
        oy = ValueTracker(0)
    if scale is None:
        scale = ValueTracker(1.0)

    def off():
        return np.array([ox.get_value(), oy.get_value(), 0.0])

    def xf(mob):
        """Aplica el escalado/traslado actuales a una pieza recien
        construida en coordenadas locales nativas (identicas a las de
        Motor4T)."""
        return mob.scale(scale.get_value(), about_point=ORIGIN).shift(off())

    # ---- partes fijas (no dependen de theta): coordenadas locales
    # nativas, identicas a Motor4T. Quien las use las mueve/escala con
    # un .animate normal, en sincronia con ox/oy/scale. ----
    xs = np.linspace(-BORE, BORE, 40)
    u_adm = np.array([-np.sin(ANG_V), np.cos(ANG_V), 0])
    u_esc = np.array([np.sin(ANG_V), np.cos(ANG_V), 0])
    s_adm = np.array([-0.45, dome_y(-0.45), 0])
    s_esc = np.array([0.45, dome_y(0.45), 0])

    bloque = Union(
        Rectangle(width=2.7, height=Y_DECK + 1.5).move_to([0, (Y_DECK - 1.5) / 2, 0]),
        Circle(radius=1.6).move_to(C),
        color=C_LABEL, stroke_width=3,
    ).set_fill(C_BLOQUE, 1)

    interior = Union(
        Rectangle(width=2 * BORE, height=Y_DECK + 1.3).move_to([0, (Y_DECK - 1.3) / 2, 0]),
        Circle(radius=1.4).move_to(C),
        stroke_width=0,
    ).set_fill(C_INTERIOR, 1)

    culata = RoundedRectangle(width=3.3, height=1.05, corner_radius=0.15,
                              color=C_LABEL, stroke_width=3)
    culata.set_fill(C_CULATA, 1).move_to([0, Y_DECK + 0.5, 0])

    camara = Polygon(*[[x, dome_y(x), 0] for x in xs], [BORE, Y_DECK - 0.01, 0],
                     [-BORE, Y_DECK - 0.01, 0], stroke_width=0).set_fill(C_INTERIOR, 1)

    def puerto(s, u, lado):
        p = VMobject(stroke_color=C_INTERIOR, stroke_width=26)
        p.set_points_smoothly([s, s + 0.35 * u, [lado * 1.0, Y_DECK + 0.75, 0],
                               [lado * 1.65, Y_DECK + 0.75, 0]])
        return p

    puertos = VGroup(puerto(s_adm, u_adm, -1), puerto(s_esc, u_esc, 1))

    tip0 = np.array([0, dome_y(0), 0])
    bujia = VGroup(
        Line(tip0, tip0 + UP * 0.12, color=C_LABEL, stroke_width=4),
        Rectangle(width=0.22, height=0.62, stroke_width=2, color=C_LABEL)
        .set_fill("#55606B", 1).move_to(tip0 + UP * 0.43),
        Rectangle(width=0.44, height=0.26, stroke_width=2, color=C_LABEL)
        .set_fill("#C9CED3", 1).move_to(tip0 + UP * 0.87),
        RoundedRectangle(width=0.28, height=0.75, corner_radius=0.08, stroke_width=2,
                         color=C_LABEL).set_fill(WHITE, 1).move_to(tip0 + UP * 1.38),
        Rectangle(width=0.12, height=0.16, stroke_width=2, color=C_LABEL)
        .set_fill("#C9CED3", 1).move_to(tip0 + UP * 1.83),
    )
    for k in range(3):
        bujia.add(Line(tip0 + UP * (1.15 + 0.15 * k) + LEFT * 0.14,
                       tip0 + UP * (1.15 + 0.15 * k) + RIGHT * 0.14,
                       color="#B0B6BC", stroke_width=2))

    fixed = VGroup(bloque, interior, culata, camara, puertos, bujia)

    # ---- partes moviles (dependen de theta): formulas LOCALES
    # identicas a Motor4T; xf() aplica el escalado/traslado actuales
    # cada vez que always_redraw reconstruye la pieza. ----
    def gas_color():
        i, f = fase(theta.get_value())
        if i == 0:
            return GAS_ADM, 0.25 + 0.35 * f
        if i == 1:
            return interpolate_color(ManimColor(GAS_ADM), ManimColor(GAS_COMP), f), 0.6 + 0.25 * f
        if i == 2:
            return interpolate_color(ManimColor(GAS_EXP), ManimColor(GAS_ESC), f ** 1.5), 0.9 - 0.3 * f
        return GAS_ESC, 0.6 - 0.4 * f

    def make_gas():
        top = piston_pin(theta.get_value())[1] + PIN_TOP
        col, op = gas_color()
        return Polygon(*[[x, dome_y(x), 0] for x in xs], [BORE, top, 0], [-BORE, top, 0],
                       stroke_width=0).set_fill(col, op)

    def make_contrapeso():
        t = theta.get_value()
        phi = PI / 2 - t + PI
        return Sector(radius=0.95, angle=0.95 * PI, start_angle=phi - 0.475 * PI,
                      arc_center=C, color=C_LABEL, stroke_width=2).set_fill(C_CIG, 1)

    def make_piston():
        p = piston_pin(theta.get_value())
        top, bot = p[1] + PIN_TOP, p[1] - PIN_BOT
        cuerpo = Rectangle(width=2 * BORE - 0.04, height=top - bot, color=C_LABEL,
                           stroke_width=2.5).set_fill(C_PISTON, 1)
        cuerpo.move_to([0, (top + bot) / 2, 0])
        anillos = VGroup(*[Line([-BORE + 0.02, top - 0.08 - 0.09 * k, 0],
                                [BORE - 0.02, top - 0.08 - 0.09 * k, 0],
                                color=C_LABEL, stroke_width=3) for k in range(3)])
        return VGroup(cuerpo, anillos)

    def make_biela():
        t = theta.get_value()
        a, b = piston_pin(t), crank_pin(t)
        d = (b - a) / np.linalg.norm(b - a)
        n = np.array([-d[1], d[0], 0])
        cuerpo = Polygon(a + n * 0.11, b + n * 0.2, b - n * 0.2, a - n * 0.11,
                         color=C_LABEL, stroke_width=2).set_fill(C_BIELA, 1)
        pie = Circle(radius=0.17, color=C_LABEL, stroke_width=2).set_fill(C_BIELA, 1).move_to(a)
        buje = Circle(radius=0.09, color=C_LABEL, stroke_width=2).set_fill("#2A323A", 1).move_to(a)
        cabeza = Circle(radius=0.32, color=C_LABEL, stroke_width=2).set_fill(C_BIELA, 1).move_to(b)
        return VGroup(cuerpo, pie, cabeza, buje)

    def make_munones():
        b = crank_pin(theta.get_value())
        brazo = Line(C, b, color=C_CIG, stroke_width=22)
        return VGroup(
            brazo,
            Circle(radius=0.18, color=C_LABEL, stroke_width=2).set_fill("#C9CED3", 1).move_to(b),
            Circle(radius=0.24, color=C_LABEL, stroke_width=2).set_fill("#C9CED3", 1).move_to(C),
        )

    def lift(t, tiempo):
        i, f = fase(t)
        return 0.22 * np.sin(PI * f) if i == tiempo else 0.0

    def make_valvula(s, u, tiempo):
        h = lift(theta.get_value(), tiempo)
        s2 = s - u * h
        n = np.array([u[1], -u[0], 0])
        cabeza = Polygon(s2 + n * 0.27, s2 - n * 0.27, s2 + u * 0.12 - n * 0.07,
                         s2 + u * 0.12 + n * 0.07, color=C_LABEL, stroke_width=2).set_fill(C_VALV, 1)
        vastago = Line(s2 + u * 0.1, s2 + u * 1.35, color=C_LABEL, stroke_width=6)
        reten = Line(s2 + u * 1.25 + n * 0.16, s2 + u * 1.25 - n * 0.16,
                     color=C_LABEL, stroke_width=7)
        return VGroup(vastago, cabeza, reten)

    def make_chispa():
        t = theta.get_value() % (4 * PI)
        on = 2 * PI - 0.05 <= t <= 2 * PI + 0.45
        tip = np.array([0, dome_y(0), 0])
        return Star(n=8, outer_radius=0.28, inner_radius=0.1, color=YELLOW,
                    stroke_width=0).set_fill(YELLOW, 1 if on else 0).move_to(tip + DOWN * 0.08)

    gas = always_redraw(lambda: xf(make_gas()))
    piston = always_redraw(lambda: xf(make_piston()))
    biela = always_redraw(lambda: xf(make_biela()))
    contrapeso = always_redraw(lambda: xf(make_contrapeso()))
    munones = always_redraw(lambda: xf(make_munones()))
    valv_adm = always_redraw(lambda: xf(make_valvula(s_adm, u_adm, 0)))
    valv_esc = always_redraw(lambda: xf(make_valvula(s_esc, u_esc, 3)))
    chispa = always_redraw(lambda: xf(make_chispa()))

    moving = VGroup(gas, piston, biela, contrapeso, munones, valv_adm, valv_esc, chispa)

    def chamber_point():
        return off() + scale.get_value() * np.array([0.0, Y_DECK + 0.55, 0.0])

    def crank_point():
        return off() + scale.get_value() * C

    return {
        "theta": theta, "ox": ox, "oy": oy, "scale": scale,
        "fixed": fixed, "moving": moving,
        "chamber_point": chamber_point, "crank_point": crank_point,
    }


class Motor4T(Scene):
    def construct(self):
        self.camera.background_color = "#F4F1EA"
        theta = ValueTracker(0)

        # ================= PARTES FIJAS =================
        bloque = Union(
            Rectangle(width=2.7, height=Y_DECK + 1.5).move_to([0, (Y_DECK - 1.5) / 2, 0]),
            Circle(radius=1.6).move_to(C),
            color=C_LABEL, stroke_width=3,
        ).set_fill(C_BLOQUE, 1)

        interior = Union(
            Rectangle(width=2 * BORE, height=Y_DECK + 1.3).move_to([0, (Y_DECK - 1.3) / 2, 0]),
            Circle(radius=1.4).move_to(C),
            stroke_width=0,
        ).set_fill(C_INTERIOR, 1)

        culata = RoundedRectangle(width=3.3, height=1.05, corner_radius=0.15,
                                  color=C_LABEL, stroke_width=3)
        culata.set_fill(C_CULATA, 1).move_to([0, Y_DECK + 0.5, 0])

        xs = np.linspace(-BORE, BORE, 40)
        camara = Polygon(*[[x, dome_y(x), 0] for x in xs], [BORE, Y_DECK - 0.01, 0],
                         [-BORE, Y_DECK - 0.01, 0], stroke_width=0).set_fill(C_INTERIOR, 1)

        # Asientos y ejes de las válvulas (admisión izq., escape der.)
        u_adm = np.array([-np.sin(ANG_V), np.cos(ANG_V), 0])
        u_esc = np.array([np.sin(ANG_V), np.cos(ANG_V), 0])
        s_adm = np.array([-0.45, dome_y(-0.45), 0])
        s_esc = np.array([0.45, dome_y(0.45), 0])

        def puerto(s, u, lado):
            p = VMobject(stroke_color=C_INTERIOR, stroke_width=26)
            p.set_points_smoothly([s, s + 0.35 * u, [lado * 1.0, Y_DECK + 0.75, 0],
                                   [lado * 1.65, Y_DECK + 0.75, 0]])
            return p

        puertos = VGroup(puerto(s_adm, u_adm, -1), puerto(s_esc, u_esc, 1))

        # ================= BUJÍA =================
        tip = np.array([0, dome_y(0), 0])
        bujia = VGroup(
            Line(tip, tip + UP * 0.12, color=C_LABEL, stroke_width=4),
            Rectangle(width=0.22, height=0.62, stroke_width=2, color=C_LABEL)
            .set_fill("#55606B", 1).move_to(tip + UP * 0.43),
            Rectangle(width=0.44, height=0.26, stroke_width=2, color=C_LABEL)
            .set_fill("#C9CED3", 1).move_to(tip + UP * 0.87),
            RoundedRectangle(width=0.28, height=0.75, corner_radius=0.08, stroke_width=2,
                             color=C_LABEL).set_fill(WHITE, 1).move_to(tip + UP * 1.38),
            Rectangle(width=0.12, height=0.16, stroke_width=2, color=C_LABEL)
            .set_fill("#C9CED3", 1).move_to(tip + UP * 1.83),
        )
        for k in range(3):  # nervaduras del aislante
            bujia.add(Line(tip + UP * (1.15 + 0.15 * k) + LEFT * 0.14,
                           tip + UP * (1.15 + 0.15 * k) + RIGHT * 0.14,
                           color="#B0B6BC", stroke_width=2))

        # ================= PARTES MÓVILES =================
        def gas_color():
            i, f = fase(theta.get_value())
            if i == 0:
                return GAS_ADM, 0.25 + 0.35 * f
            if i == 1:
                return interpolate_color(ManimColor(GAS_ADM), ManimColor(GAS_COMP), f), 0.6 + 0.25 * f
            if i == 2:
                return interpolate_color(ManimColor(GAS_EXP), ManimColor(GAS_ESC), f**1.5), 0.9 - 0.3 * f
            return GAS_ESC, 0.6 - 0.4 * f

        def make_gas():
            top = piston_pin(theta.get_value())[1] + PIN_TOP
            col, op = gas_color()
            return Polygon(*[[x, dome_y(x), 0] for x in xs], [BORE, top, 0], [-BORE, top, 0],
                           stroke_width=0).set_fill(col, op)

        gas = always_redraw(make_gas)

        def make_contrapeso():
            t = theta.get_value()
            phi = PI / 2 - t + PI  # opuesto al muñón
            return Sector(radius=0.95, angle=0.95 * PI, start_angle=phi - 0.475 * PI,
                          arc_center=C, color=C_LABEL, stroke_width=2).set_fill(C_CIG, 1)

        def make_piston():
            p = piston_pin(theta.get_value())
            top, bot = p[1] + PIN_TOP, p[1] - PIN_BOT
            cuerpo = Rectangle(width=2 * BORE - 0.04, height=top - bot, color=C_LABEL,
                               stroke_width=2.5).set_fill(C_PISTON, 1)
            cuerpo.move_to([0, (top + bot) / 2, 0])
            anillos = VGroup(*[Line([-BORE + 0.02, top - 0.08 - 0.09 * k, 0],
                                    [BORE - 0.02, top - 0.08 - 0.09 * k, 0],
                                    color=C_LABEL, stroke_width=3) for k in range(3)])
            return VGroup(cuerpo, anillos)

        def make_biela():
            t = theta.get_value()
            a, b = piston_pin(t), crank_pin(t)
            d = (b - a) / np.linalg.norm(b - a)
            n = np.array([-d[1], d[0], 0])
            cuerpo = Polygon(a + n * 0.11, b + n * 0.2, b - n * 0.2, a - n * 0.11,
                             color=C_LABEL, stroke_width=2).set_fill(C_BIELA, 1)
            pie = Circle(radius=0.17, color=C_LABEL, stroke_width=2).set_fill(C_BIELA, 1).move_to(a)
            buje = Circle(radius=0.09, color=C_LABEL, stroke_width=2).set_fill("#2A323A", 1).move_to(a)
            cabeza = Circle(radius=0.32, color=C_LABEL, stroke_width=2).set_fill(C_BIELA, 1).move_to(b)
            return VGroup(cuerpo, pie, cabeza, buje)

        def make_munones():
            b = crank_pin(theta.get_value())
            brazo = Line(C, b, color=C_CIG, stroke_width=22)
            return VGroup(
                brazo,
                Circle(radius=0.18, color=C_LABEL, stroke_width=2).set_fill("#C9CED3", 1).move_to(b),
                Circle(radius=0.24, color=C_LABEL, stroke_width=2).set_fill("#C9CED3", 1).move_to(C),
            )

        def lift(t, tiempo):
            i, f = fase(t)
            return 0.22 * np.sin(PI * f) if i == tiempo else 0.0

        def make_valvula(s, u, tiempo):
            h = lift(theta.get_value(), tiempo)
            s2 = s - u * h
            n = np.array([u[1], -u[0], 0])
            cabeza = Polygon(s2 + n * 0.27, s2 - n * 0.27, s2 + u * 0.12 - n * 0.07,
                             s2 + u * 0.12 + n * 0.07, color=C_LABEL, stroke_width=2).set_fill(C_VALV, 1)
            vastago = Line(s2 + u * 0.1, s2 + u * 1.35, color=C_LABEL, stroke_width=6)
            reten = Line(s2 + u * 1.25 + n * 0.16, s2 + u * 1.25 - n * 0.16,
                         color=C_LABEL, stroke_width=7)
            return VGroup(vastago, cabeza, reten)

        valv_adm = always_redraw(lambda: make_valvula(s_adm, u_adm, 0))
        valv_esc = always_redraw(lambda: make_valvula(s_esc, u_esc, 3))

        def make_chispa():
            t = theta.get_value() % (4 * PI)
            on = 2 * PI - 0.05 <= t <= 2 * PI + 0.45
            st = Star(n=8, outer_radius=0.28, inner_radius=0.1, color=YELLOW,
                      stroke_width=0).set_fill(YELLOW, 1 if on else 0).move_to(tip + DOWN * 0.08)
            return st

        piston = always_redraw(make_piston)
        biela = always_redraw(make_biela)
        contrapeso = always_redraw(make_contrapeso)
        munones = always_redraw(make_munones)
        chispa = always_redraw(make_chispa)

        # ================= ETIQUETAS =================
        def etiqueta(texto, pos, target_fn, lado=LEFT):
            t = Text(texto, font_size=26, weight=BOLD, color=C_LABEL, line_spacing=0.8).move_to(pos)
            ancla = t.get_right() if np.array_equal(lado, LEFT) else t.get_left()

            def linea():
                p = target_fn()
                return VGroup(Line(ancla + (RIGHT if np.array_equal(lado, LEFT) else LEFT) * 0.1, p,
                                   color=C_LABEL, stroke_width=2),
                              Dot(p, radius=0.04, color=C_LABEL))
            return VGroup(t, always_redraw(linea))

        lbl_camara = etiqueta("Cámara de\ncombustión", [-4.3, 2.3, 0], lambda: np.array([-0.25, 1.45, 0]))
        lbl_valv = etiqueta("Válvulas", [4.0, 3.3, 0], lambda: s_esc + u_esc * 1.0, RIGHT)
        lbl_bujia = etiqueta("Bujía", [4.0, 2.3, 0], lambda: tip + UP * 1.3 + RIGHT * 0.14, RIGHT)
        lbl_piston = etiqueta("Pistón", [-4.3, 0.6, 0],
                              lambda: np.array([-BORE + 0.05, piston_pin(theta.get_value())[1] + 0.1, 0]))
        lbl_biela = etiqueta("Biela", [-4.3, -1.0, 0],
                             lambda: (piston_pin(theta.get_value()) + crank_pin(theta.get_value())) / 2)
        lbl_cig = etiqueta("Cigüeñal", [-4.3, -3.2, 0], lambda: C + np.array([-0.55, -0.55, 0]))
        etiquetas = VGroup(lbl_camara, lbl_valv, lbl_bujia, lbl_piston, lbl_biela, lbl_cig)

        # ================= INDICADOR DEL TIEMPO =================
        NOMBRES = ["1. Admisión", "2. Compresión", "3. Explosión", "4. Escape"]
        COLS = [GAS_ADM, GAS_COMP, GAS_EXP, GAS_ESC]

        def make_tiempo():
            i, _ = fase(theta.get_value())
            filas = VGroup()
            for k, nom in enumerate(NOMBRES):
                activo = k == i
                cuadro = Square(0.28, stroke_width=0).set_fill(COLS[k], 1 if activo else 0.25)
                txt = Text(nom, font_size=24, weight=BOLD if activo else NORMAL,
                           color=C_LABEL).set_opacity(1 if activo else 0.4)
                filas.add(VGroup(cuadro, txt).arrange(RIGHT, buff=0.2))
            filas.arrange(DOWN, aligned_edge=LEFT, buff=0.22)
            return filas.move_to([4.5, -1.8, 0])

        tiempo = always_redraw(make_tiempo)

        # ================= ANIMACIÓN =================
        titulo = Text("Motor de 4 tiempos", font_size=34, weight=BOLD, color=C_LABEL).to_corner(UL)

        self.play(FadeIn(bloque), FadeIn(interior), FadeIn(culata), FadeIn(camara),
                  FadeIn(puertos), Write(titulo), run_time=1.2)
        self.add(gas)
        self.play(FadeIn(contrapeso), FadeIn(piston), FadeIn(biela), FadeIn(munones),
                  FadeIn(valv_adm), FadeIn(valv_esc), FadeIn(bujia), run_time=1.2)
        self.add(chispa)
        self.play(LaggedStart(*[FadeIn(e) for e in etiquetas], lag_ratio=0.25), run_time=2)
        self.play(FadeIn(tiempo))
        self.wait(0.5)

        # Primer ciclo lento (para explicar), luego dos ciclos más rápidos
        self.play(theta.animate.set_value(4 * PI), run_time=10, rate_func=linear)
        self.play(theta.animate.set_value(12 * PI), run_time=8, rate_func=linear)
        self.wait(1)
