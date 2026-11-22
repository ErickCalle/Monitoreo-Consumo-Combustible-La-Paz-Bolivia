"""Diapositivas adicionales de la presentacion (piloto manim-slides).

Por ahora solo la portada; el resto de la deduccion vive en
speed_density.py (clase SpeedDensityDerivation, ya adaptada a Slide).

Render:
    manim-slides render presentation_slides.py TitleSlide -qh

Presentar (todas las escenas, en orden):
    manim-slides present TitleSlide SpeedDensityDerivation

Exportar a HTML (portable, se abre en cualquier navegador):
    manim-slides convert TitleSlide SpeedDensityDerivation presentacion.html --to html -ctoggle-controls=true
"""

from manim import *
import _ms_compat  # noqa: F401  (parche de compatibilidad manim-slides <-> manim 0.22)
from manim_slides import Slide

UMSA_BLUE = ManimColor.from_rgb((19, 57, 132))
INK = ManimColor.from_rgb((30, 30, 30))

config.background_color = WHITE
Tex.set_default(color=INK)


class TitleSlide(Slide):
    def construct(self):
        titulo = Tex(
            r"Sistema embebido de estimacion y monitoreo",
            r"\\del consumo de combustible",
            color=UMSA_BLUE, font_size=40,
        )
        subtitulo = Tex(
            r"Protocolo OBD-II en vehiculos a gasolina con inyeccion electronica",
            font_size=24, color=INK,
        )
        linea = Line(LEFT, RIGHT, color=UMSA_BLUE, stroke_width=2).set_width(8)

        autor = Tex(r"Univ. Cristian Erick Calle Ali", font_size=24)
        institute = Tex(
            r"UMSA --- Ingenieria Mecatronica \quad\textbar\quad "
            r"Tutor: Ing. Eloy C. Sarabia Yapuchura",
            font_size=18, color=GRAY_D,
        )
        fecha = Tex(r"Version beta --- La Paz, Bolivia", font_size=16, color=GRAY_D)

        bloque = VGroup(titulo, subtitulo).arrange(DOWN, buff=0.35)
        pie = VGroup(autor, institute, fecha).arrange(DOWN, buff=0.18)

        grupo = VGroup(bloque, linea, pie).arrange(DOWN, buff=0.5)

        self.play(FadeIn(bloque, shift=UP * 0.2), run_time=1.5)
        self.play(Create(linea), run_time=0.8)
        self.play(FadeIn(pie, shift=UP * 0.15), run_time=1.2)
        self.next_slide()
