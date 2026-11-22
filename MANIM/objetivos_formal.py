"""
Animación de OBJETIVOS (general + 5 específicos) — estilo corporativo plano.

Ejecutar:
    manim -pql objetivos_formal.py Objetivos      # vista rápida
    manim -pqh objetivos_formal.py Objetivos      # 1080p
"""
from manim import *
import numpy as np
import textwrap

# =====================================================================
#  TEXTOS: REEMPLAZA CON LOS OBJETIVOS EXACTOS DE TU DOCUMENTO
# =====================================================================
OBJ_GENERAL = (
    "Desarrollar un sistema de monitoreo del consumo de combustible en "
    "tiempo real para vehículos a gasolina con inyección electrónica, "
    "basado en un ESP32-S3 y en la adquisición de datos por OBD-II "
    "sobre red CAN, con corrección por altitud para la ciudad de La Paz."
)
OBJ_ESPECIFICOS = [
    "Analizar el protocolo OBD-II y la red CAN para identificar los "
    "parámetros del motor necesarios para estimar el consumo.",
    "Diseñar el hardware del sistema: alimentación automotriz protegida, "
    "interfaz CAN y PCB a medida.",
    "Implementar el algoritmo Speed-Density con corrección por altitud y "
    "ajuste adaptativo mediante STFT/LTFT.",
    "Desarrollar una interfaz web embebida para visualizar en tiempo real "
    "los parámetros y el consumo estimado.",
    "Validar el sistema experimentalmente en vehículos reales, comparando "
    "sus resultados con instrumentos de referencia.",
]

# =====================================================================
#  AJUSTES DE ESTILO
# =====================================================================
FUENTE = "Segoe UI"        # Windows. Alternativas: "Calibri", "Arial"
LECTURA = 5                # segundos que se queda cada tarjeta
AZUL = "#133984"           # XIOPMblue
AZUL_CLARO = "#7FA6E0"
ORO = "#F4B400"
GRIS = "#3A4250"
GRIS_LINEA = "#9AA4B2"
SOMBRA = "#D5DCE6"
FONDO = WHITE
TEXTO = "#2B2B2B"

SUELO = -3.0
XS = np.linspace(-4.2, 2.2, 5)          # posición de las 5 barras
HS = np.linspace(0.6, 3.2, 5)           # alturas de las 5 barras
XG, WG, HG = 4.2, 1.3, 4.4              # columna del objetivo general


# =====================================================================
#  ELEMENTOS
# =====================================================================
def color_barra(i):
    return interpolate_color(ManimColor(AZUL_CLARO), ManimColor(AZUL), i / 4)


def barra(x, w, h, color, numero=None):
    """Barra con esquinas superiores redondeadas. g[0] es el cuerpo."""
    cuerpo = RoundedRectangle(width=w, height=h, corner_radius=[0.12, 0.12, 0, 0],
                              stroke_width=0).set_fill(color, 1)
    cuerpo.move_to([x, SUELO + h / 2, 0])
    g = VGroup(cuerpo)
    if numero is not None:
        badge = VGroup(Circle(radius=0.24, stroke_width=0).set_fill(WHITE, 1),
                       Text(str(numero), font=FUENTE, font_size=26, weight=BOLD, color=color))
        badge[1].move_to(badge[0])
        badge.move_to([x, SUELO + max(h - 0.38, h / 2), 0])
        g.add(badge)
    return g


def persona(alto=1.6):
    """Pictograma de ingeniero con casco. Pies en el origen."""
    s = alto / 1.6
    rr = lambda w, h, r, p: RoundedRectangle(width=w, height=h, corner_radius=r,
                                             stroke_width=0).set_fill(GRIS, 1).move_to(p)
    g = VGroup(
        rr(0.16, 0.62, 0.08, [-0.11, 0.31, 0]),
        rr(0.16, 0.62, 0.08, [0.11, 0.31, 0]),
        rr(0.46, 0.62, 0.16, [0, 0.88, 0]),
        rr(0.13, 0.5, 0.06, [-0.31, 0.92, 0]),
        rr(0.13, 0.5, 0.06, [0, 0, 0]).rotate(-50 * DEGREES).move_to([0.36, 1.08, 0]),
        Circle(radius=0.2, stroke_width=0).set_fill(GRIS, 1).move_to([0, 1.39, 0]),
        Sector(radius=0.23, angle=PI, start_angle=0, arc_center=[0, 1.45, 0],
               stroke_width=0).set_fill(ORO, 1),
        RoundedRectangle(width=0.62, height=0.07, corner_radius=0.03, stroke_width=0)
        .set_fill(ORO, 1).move_to([0.04, 1.45, 0]),
    )
    return g.scale(s, about_point=ORIGIN)


def tarjeta(titulo, texto, numero=None):
    """Tarjeta formal. Devuelve (fondo que cubre la pantalla, contenido)."""
    fondo = Rectangle(width=config.frame_width + 0.6, height=config.frame_height + 0.6,
                      stroke_width=0).set_fill(FONDO, 1)
    W, H = 12, 6
    hoja = RoundedRectangle(width=W, height=H, corner_radius=0.2, stroke_width=1,
                            stroke_color=SOMBRA).set_fill(WHITE, 1)
    sombra = hoja.copy().set_stroke(width=0).set_fill(SOMBRA, 1).shift(DR * 0.09)
    cab = RoundedRectangle(width=W, height=1.4, corner_radius=[0.2, 0.2, 0, 0],
                           stroke_width=0).set_fill(AZUL, 1).align_to(hoja, UP)
    acento = Rectangle(width=1.6, height=0.08, stroke_width=0).set_fill(ORO, 1)
    acento.next_to(cab, DOWN, buff=0.45).align_to(hoja, LEFT).shift(RIGHT * 0.6)

    t = Text(titulo, font=FUENTE, font_size=40, weight=BOLD, color=WHITE)
    if numero is not None:
        badge = VGroup(Circle(radius=0.42, stroke_width=0).set_fill(WHITE, 1),
                       Text(str(numero), font=FUENTE, font_size=40, weight=BOLD, color=AZUL))
        badge[1].move_to(badge[0])
        badge.move_to(cab).align_to(cab, LEFT).shift(RIGHT * 0.5)
        t.next_to(badge, RIGHT, buff=0.35)
        encabezado = VGroup(badge, t)
    else:
        t.move_to(cab).align_to(cab, LEFT).shift(RIGHT * 0.6)
        encabezado = VGroup(t)

    cuerpo = Text(textwrap.fill(texto, width=60), font=FUENTE, font_size=30, color=TEXTO,
                  line_spacing=1.25)
    cuerpo.scale_to_fit_width(min(cuerpo.width, W - 1.4))
    cuerpo.next_to(acento, DOWN, buff=0.45).align_to(acento, LEFT)
    return fondo, VGroup(sombra, hoja, cab), encabezado, VGroup(acento, cuerpo)


# =====================================================================
#  ESCENA
# =====================================================================
class Objetivos(MovingCameraScene):
    def construct(self):
        self.camera.background_color = FONDO
        frame = self.camera.frame

        # Reloj para la bandera que flamea
        reloj = ValueTracker(0)
        reloj.add_updater(lambda m, dt: m.increment_value(dt))
        self.add(reloj)
        despliegue = ValueTracker(0)   # 0 = enrollada, 1 = desplegada
        viento = ValueTracker(1.0)     # intensidad del flameo

        titulo = Text("OBJETIVOS", font=FUENTE, font_size=34, weight=BOLD, color=AZUL)
        titulo.to_corner(UL, buff=0.5)
        barrita = Rectangle(width=0.12, height=titulo.height + 0.1, stroke_width=0)
        barrita.set_fill(AZUL, 1).next_to(titulo, LEFT, buff=0.15)
        suelo = Line([-7.5, SUELO, 0], [7.5, SUELO, 0], stroke_color=GRIS, stroke_width=3)

        self.play(GrowFromEdge(barrita, DOWN), FadeIn(titulo, shift=RIGHT * 0.3),
                  Create(suelo), run_time=1)

        # ---------- 1) Columna principal + bandera ----------
        columna = barra(XG, WG, HG, AZUL)
        self.play(GrowFromEdge(columna, DOWN), run_time=1.8, rate_func=smooth)

        base_asta = np.array([XG + 0.35, SUELO + HG, 0])
        punta_asta = base_asta + UP * 1.3
        asta = Line(base_asta, punta_asta, stroke_color=GRIS, stroke_width=5)
        remate = Dot(punta_asta, radius=0.06, color=GRIS)

        def make_tela():
            t = reloj.get_value()
            L, A = 0.85 * max(despliegue.get_value(), 0.001), 0.5
            amp = 0.08 * viento.get_value()
            n = 30
            xs = np.linspace(0, L, n)
            ola = lambda x, fase: amp * (x / 0.85) * np.sin(7 * x - 5 * t + fase)
            arriba = [punta_asta + [x, ola(x, 0), 0] for x in xs]
            abajo = [punta_asta + [x, -A + ola(x, 0.6), 0] for x in xs[::-1]]
            tela = Polygon(*arriba, *abajo, stroke_width=0).set_fill(ORO, 1)
            # sombra suave del pliegue
            pliegue = Polygon(*[punta_asta + [x, ola(x, 0) - 0.02, 0] for x in xs],
                              *[punta_asta + [x, -A * 0.45 + ola(x, 0.3), 0] for x in xs[::-1]],
                              stroke_width=0).set_fill("#D99A00", 0.35)
            return VGroup(tela, pliegue)

        tela = always_redraw(make_tela)
        self.play(Create(asta), FadeIn(remate), run_time=0.6)
        self.add(tela)
        self.play(despliegue.animate.set_value(1), run_time=1.0, rate_func=smooth)

        lbl_gral = Text("Objetivo general", font=FUENTE, font_size=46, weight=BOLD, color=AZUL)
        lbl_gral.move_to([0.0, 1.9, 0])
        guia = VGroup(
            Line(lbl_gral.get_corner(DR) + [0.15, 0.1, 0], [XG - 0.75, SUELO + HG - 0.25, 0],
                 stroke_color=GRIS_LINEA, stroke_width=2.5),
            Dot([XG - 0.75, SUELO + HG - 0.25, 0], radius=0.06, color=GRIS_LINEA),
        )
        self.play(FadeIn(lbl_gral, shift=RIGHT * 0.3), Create(guia), run_time=1.2)
        self.wait(0.8)

        # ---------- 2) Presentación del objetivo general ----------
        self.mostrar_tarjeta(columna, "Objetivo general", OBJ_GENERAL, None)
        self.play(FadeOut(lbl_gral), FadeOut(guia), run_time=0.6)

        # ---------- 3) Ingeniero + 5 barras como escalera ----------
        ing = persona(1.6).move_to([-5.8, SUELO, 0], aligned_edge=DOWN)
        self.play(LaggedStart(*[FadeIn(p, shift=UP * 0.15) for p in ing], lag_ratio=0.12),
                  run_time=1.8)

        barras = [barra(x, 1.05, h, color_barra(i), i + 1)
                  for i, (x, h) in enumerate(zip(XS, HS))]
        self.play(LaggedStart(*[GrowFromEdge(b, DOWN) for b in barras], lag_ratio=0.25),
                  run_time=2.8)

        c0, c1, c2, c3 = (np.array([-4.9, SUELO + 1.1, 0]), np.array([-2.5, 0.2, 0]),
                          np.array([0.5, 2.3, 0]), np.array([XG - 0.6, SUELO + HG + 0.7, 0]))
        camino = DashedVMobject(CubicBezier(c0, c1, c2, c3, stroke_color=GRIS_LINEA,
                                            stroke_width=2.5), num_dashes=30)
        tang = c3 - c2
        punta = Triangle(stroke_width=0).set_fill(GRIS_LINEA, 1).scale(0.11)
        punta.rotate(np.arctan2(tang[1], tang[0]) - PI / 2).move_to(c3)
        self.play(Create(camino), run_time=1.4)
        self.play(FadeIn(punta, scale=1.5), run_time=0.3)
        self.wait(0.6)

        # ---------- 4) Los 5 objetivos específicos ----------
        for i, b in enumerate(barras):
            frame.save_state()
            self.play(frame.animate.scale(0.42).move_to(b.get_center() + UP * 0.6), run_time=1.3)
            self.mostrar_tarjeta(b, f"Objetivo específico {i + 1}", OBJ_ESPECIFICOS[i], i + 1,
                                 desde_zoom=True)
            self.play(ing.animate(path_arc=-1.0).move_to([XS[i], SUELO + HS[i], 0],
                                                         aligned_edge=DOWN), run_time=0.9)
            self.wait(0.3)

        # ---------- 5) Llega a la meta ----------
        self.play(ing.animate(path_arc=-1.2).move_to([XG - 0.3, SUELO + HG, 0],
                                                     aligned_edge=DOWN), run_time=1.3)
        self.play(viento.animate.set_value(1.8), Indicate(columna[0], color=AZUL, scale_factor=1.03),
                  run_time=1.0)
        self.wait(2.5)

    # -----------------------------------------------------------------
    def mostrar_tarjeta(self, origen, titulo, texto, numero, desde_zoom=False):
        """La barra se amplía hasta convertirse en la tarjeta del objetivo."""
        frame = self.camera.frame
        fondo, base, encabezado, cuerpo = tarjeta(titulo, texto, numero)
        semilla = origen[0].copy()
        self.add(semilla)
        anims = [ReplacementTransform(semilla, fondo)]
        if desde_zoom:
            anims.append(Restore(frame))
        self.play(*anims, run_time=1.3)
        self.play(FadeIn(VGroup(base[0], base[1]), scale=0.92), run_time=0.5)
        self.play(GrowFromEdge(base[2], UP), run_time=0.5)
        self.play(FadeIn(encabezado, shift=RIGHT * 0.3), run_time=0.6)
        self.play(GrowFromEdge(cuerpo[0], LEFT), FadeIn(cuerpo[1], shift=UP * 0.15), run_time=0.9)
        self.wait(LECTURA)
        self.play(FadeOut(VGroup(base, encabezado, cuerpo)), run_time=0.5)
        destino = origen[0].copy()
        self.play(ReplacementTransform(fondo, destino), run_time=1.0)
        self.remove(destino)
