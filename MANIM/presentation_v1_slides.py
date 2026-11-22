"""Migracion (parcial) de PRESENTACION/V1/main.tex (tema XIOPM) a
manim-slides: caratula, "El punto de partida" (la pregunta),
"Generalidades" (separador de capitulo) e "Introduccion" (iconos).

Paleta identica a la plantilla XIOPM (XIOPMblue = RGB(19,57,132)).
Usa XeLaTeX + fontawesome5 para los iconos reales de la plantilla.

Cada diapositiva lleva, arriba a la derecha, el logo de la Facultad de
Ingenieria + "Universidad Mayor de San Andres / Facultad de Ingenieria",
y abajo la fecha de renderizado (equivalente a \\today en Beamer: se fija
al renderizar, no es una fecha "en vivo") y el numero de pagina.

Render (alta calidad):
    manim-slides render presentation_v1_slides.py CaratulaSlide PreguntaSlide GeneralidadesSlide IntroduccionSlide -q h

Presentar / exportar: igual que speed_density.py (ver ese archivo).
"""

import datetime
import textwrap
import numpy as np
from manim import *
import _ms_compat  # noqa: F401
from manim_slides import Slide
from indicador_combustible import build_indicador
import conector_obd2

XIOPM_BLUE = ManimColor.from_rgb((19, 57, 132))
INK = ManimColor.from_rgb((30, 30, 30))

config.background_color = WHITE

FA_TEMPLATE = TexTemplate(tex_compiler="xelatex", output_format=".xdv")
FA_TEMPLATE.add_to_preamble(r"\usepackage{fontawesome5}")

Tex.set_default(tex_template=FA_TEMPLATE, color=INK)
MathTex.set_default(tex_template=FA_TEMPLATE, color=INK)

V1 = "../PRESENTACION/V1"
BG_PORTADA = f"{V1}/source/background/Monitor OBD-II en tablero de automóvil.png"
BG_GENERALIDADES = f"{V1}/IMAGENES/dawn-mcdonald-lBP2muAsD94-unsplash.jpg"
BG_MARCO_TEORICO = "assets/backgrounds/marco_teorico.jpg"
LOGO_FACULTAD = f"{V1}/source/logo facultad de ingenieria.png"

MESES_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def fecha_hoy():
    hoy = datetime.date.today()
    return f"{hoy.day} de {MESES_ES[hoy.month - 1]} de {hoy.year}"


def cover_image(path):
    """Imagen que cubre todo el cuadro 16:9 (recorte natural arriba/abajo,
    igual que object-fit: cover)."""
    img = ImageMobject(path)
    img.set(width=config.frame_width)
    img.move_to(ORIGIN)
    return img


def circular_reveal(scene, icon, cover_color, run_time=0.98):
    """Revela 'icon' con un barrido circular: lo cubre con un rectangulo
    del color de la caja con un agujero circular que crece hasta
    descubrirlo del todo."""
    center = icon.get_center()
    half_diag = np.hypot(icon.width, icon.height) / 2 + 0.08
    r = ValueTracker(0.001)

    def make_mask():
        cover = Rectangle(
            width=icon.width + 0.3, height=icon.height + 0.3,
            fill_color=cover_color, fill_opacity=1, stroke_width=0,
        ).move_to(center)
        hole = Circle(radius=r.get_value()).move_to(center)
        return Difference(cover, hole, fill_color=cover_color, fill_opacity=1, stroke_width=0)

    mask = always_redraw(make_mask)
    scene.add(icon, mask)
    scene.play(r.animate.set_value(half_diag), run_time=run_time, rate_func=smooth)
    scene.remove(mask)


def paragraph(text, width=46, font_size=22, color=INK, align=LEFT, line_buff=0.09):
    """Parrafo envuelto a 'width' caracteres, con cada linea como su
    propio Tex alineado a la izquierda (o derecha) -- un Tex multilinea
    con '\\\\' centra las lineas entre si, lo cual no sirve aqui."""
    # break_long_words=False: un "token" sin espacios (comando LaTeX,
    # formula $...$) nunca se parte a la mitad -- eso corrompe la sintaxis.
    lines = textwrap.wrap(text, width=width, break_long_words=False,
                           break_on_hyphens=False) or [text]
    group = VGroup(*[Tex(line, font_size=font_size, color=color) for line in lines])
    group.arrange(DOWN, aligned_edge=align, buff=line_buff)
    return group


def bullet_list(items, font_size=22, color=INK, bullet_color=XIOPM_BLUE,
                 width=46, buff=0.28, dot_radius=0.05):
    """Lista de vinetas: cada item es un parrafo que se envuelve solo."""
    rows = VGroup()
    for item in items:
        dot = Dot(radius=dot_radius, color=bullet_color)
        txt = paragraph(item, width=width, font_size=font_size, color=color)
        row = VGroup(dot, txt).arrange(RIGHT, buff=0.2, aligned_edge=UP)
        row[0].align_to(row[1], UP).shift(DOWN * 0.12)
        rows.add(row)
    rows.arrange(DOWN, buff=buff, aligned_edge=LEFT)
    return rows


def wipe_reveal(scene, mobject, cover_color=WHITE, direction=RIGHT, run_time=0.75):
    """Revela 'mobject' con un barrido: lo cubre con un rectangulo del
    color de fondo y lo retira deslizandolo en 'direction', como una
    cortina que se corre."""
    cover = Rectangle(
        width=mobject.width + 0.15, height=mobject.height + 0.15,
        fill_color=cover_color, fill_opacity=1, stroke_width=0,
    ).move_to(mobject.get_center())
    scene.add(mobject, cover)
    scene.play(cover.animate.shift(direction * (mobject.width + 0.3)), run_time=run_time)
    scene.remove(cover)


CARD_BODY_BG = ManimColor.from_rgb((234, 234, 225))


def make_card(title, desc, width=5.8, header_h=0.65, body_h=1.9,
              desc_width=32, title_fs=28, desc_fs=25, radius=0.18):
    """Tarjeta redondeada con encabezado azul (titulo) + cuerpo claro
    (descripcion, centrada). Las esquinas se redondean solo arriba
    (header) y solo abajo (body), para que la tarjeta completa luzca
    como una sola pastilla redondeada."""
    # Orden de RoundedRectangle.corner_radius: [arriba-izq, abajo-izq,
    # abajo-der, arriba-der] (verificado empiricamente).
    body = RoundedRectangle(
        corner_radius=[0, radius, radius, 0], width=width, height=body_h,
        fill_color=CARD_BODY_BG, fill_opacity=1, stroke_color=XIOPM_BLUE, stroke_width=1.5,
    )
    desc_txt = paragraph(desc, width=desc_width, font_size=desc_fs, color=INK, align=ORIGIN)
    desc_txt.move_to(body.get_center())

    header = RoundedRectangle(
        corner_radius=[radius, 0, 0, radius], width=width, height=header_h,
        fill_color=XIOPM_BLUE, fill_opacity=1, stroke_width=0,
    )
    header.next_to(body, UP, buff=0)
    title_txt = Tex(f"\\textbf{{{title}}}", font_size=title_fs, color=WHITE).move_to(header.get_center())

    return VGroup(body, desc_txt, header, title_txt)


def add_corner_badge(scene, text_color=XIOPM_BLUE, chip=False, run_time=0.68):
    """Logo de la Facultad + texto institucional, arriba a la derecha."""
    logo = ImageMobject(LOGO_FACULTAD).set(height=0.62)
    inst = VGroup(
        Tex("Universidad Mayor de San Andr\u00e9s", font_size=14, color=text_color),
        Tex("Facultad de Ingenier\u00eda", font_size=14, color=text_color),
    ).arrange(DOWN, buff=0.05, aligned_edge=RIGHT)
    badge = Group(inst, logo).arrange(RIGHT, buff=0.2)
    badge.to_corner(UR, buff=0.3)

    mobs = [badge]
    if chip:
        bg = RoundedRectangle(
            corner_radius=0.08, width=badge.width + 0.3, height=badge.height + 0.22,
            fill_color=WHITE, fill_opacity=0.85, stroke_width=0,
        ).move_to(badge.get_center())
        mobs = [bg, badge]
    scene.play(*[FadeIn(m) for m in mobs], run_time=run_time)
    return Group(*mobs)


def add_footer(scene, page_num, text_color=GRAY_D, chip=False, run_time=0.52):
    """Fecha (abajo-izquierda) y numero de pagina (abajo-derecha)."""
    fecha = Tex(fecha_hoy(), font_size=16, color=text_color).to_corner(DL, buff=0.3)
    pagina = Tex(str(page_num), font_size=16, color=text_color).to_corner(DR, buff=0.3)

    mobs = []
    if chip:
        for m in (fecha, pagina):
            bg = RoundedRectangle(
                corner_radius=0.06, width=m.width + 0.25, height=m.height + 0.16,
                fill_color=WHITE, fill_opacity=0.8, stroke_width=0,
            ).move_to(m.get_center())
            mobs.append(bg)
    mobs += [fecha, pagina]
    scene.play(*[FadeIn(m) for m in mobs], run_time=run_time)
    return Group(*mobs)


class CaratulaSlide(Slide):
    def construct(self):
        fondo = cover_image(BG_PORTADA)
        self.play(FadeIn(fondo), run_time=1.2)

        velo = Rectangle(
            width=config.frame_width, height=config.frame_height,
            fill_color=BLACK, fill_opacity=0.35, stroke_width=0,
        )

        caja = RoundedRectangle(
            corner_radius=0.18, width=11.2, height=4.3,
            fill_color=WHITE, fill_opacity=0.92, stroke_color=XIOPM_BLUE, stroke_width=3,
        )

        titulo = Tex(
            "\\textbf{SISTEMA EMBEBIDO DE ESTIMACI\u00d3N Y MONITOREO}\\\\"
            "\\textbf{DEL CONSUMO DE COMBUSTIBLE}\\\\"
            "\\textbf{MEDIANTE EL PROTOCOLO OBD-II EN VEH\u00cdCULOS}\\\\"
            "\\textbf{A GASOLINA CON INYECCI\u00d3N ELECTR\u00d3NICA}",
            font_size=28, color=XIOPM_BLUE,
        )
        linea = Line(LEFT, RIGHT, color=XIOPM_BLUE, stroke_width=2).set_width(8)
        autor = Tex("Univ. Cristian Erick Calle Ali", font_size=24, color=INK)
        fecha = Tex("Universidad Mayor de San Andr\u00e9s --- Ingenier\u00eda Mecatr\u00f3nica",
                     font_size=18, color=GRAY_D)

        contenido = VGroup(titulo, linea, autor, fecha).arrange(DOWN, buff=0.3)
        contenido.move_to(caja.get_center())

        self.play(FadeIn(velo), run_time=0.6)
        self.play(GrowFromCenter(caja), run_time=0.75)
        self.play(FadeIn(titulo, shift=UP * 0.15), run_time=0.9)
        self.play(Create(linea), run_time=0.45)
        self.play(FadeIn(autor, shift=UP * 0.1), FadeIn(fecha, shift=UP * 0.1), run_time=0.75)

        add_corner_badge(self, text_color=XIOPM_BLUE, chip=True)
        add_footer(self, 1, text_color=XIOPM_BLUE, chip=True)
        self.next_slide()


class PreguntaSlide(Slide):
    def construct(self):
        titulo = Tex("\\textbf{EL PUNTO DE PARTIDA}", font_size=36, color=XIOPM_BLUE).to_edge(UP, buff=0.6)
        linea = Line(LEFT, RIGHT, color=XIOPM_BLUE, stroke_width=2).set_width(
            config.frame_width - 1.5
        ).next_to(titulo, DOWN, buff=0.3)
        self.play(FadeIn(titulo, shift=DOWN * 0.1), Create(linea), run_time=0.9)
        add_corner_badge(self, text_color=XIOPM_BLUE)

        caja = RoundedRectangle(
            corner_radius=0.25, width=10.5, height=2.6,
            fill_color=ManimColor.from_rgb((235, 240, 248)), fill_opacity=1,
            stroke_color=XIOPM_BLUE, stroke_width=2.5,
        ).move_to(ORIGIN)

        self.play(DrawBorderThenFill(caja), run_time=1.2)

        pregunta = Tex(
            "\\textbf{\u00bfAlguna vez se han preguntado cu\u00e1nto combustible}\\\\"
            "\\textbf{consume realmente un veh\u00edculo durante su funcionamiento?}",
            font_size=30, color=XIOPM_BLUE,
        ).move_to(caja.get_center())

        self.play(FadeIn(pregunta, shift=UP * 0.2), run_time=1.12)
        add_footer(self, 2, text_color=GRAY_D)
        self.next_slide()


class GeneralidadesSlide(Slide):
    def construct(self):
        fondo = cover_image(BG_GENERALIDADES)
        self.play(FadeIn(fondo), run_time=1.2)

        velo = Rectangle(
            width=config.frame_width, height=config.frame_height,
            fill_color=XIOPM_BLUE, fill_opacity=0.55, stroke_width=0,
        )
        self.play(FadeIn(velo), run_time=0.9)

        titulo = Tex("\\textbf{GENERALIDADES}", font_size=64, color=WHITE)
        linea = Line(LEFT, RIGHT, color=WHITE, stroke_width=3).set_width(4).next_to(titulo, DOWN, buff=0.3)
        self.play(FadeIn(titulo, scale=1.15), run_time=0.98)
        self.play(Create(linea), run_time=0.6)

        add_corner_badge(self, text_color=WHITE)
        add_footer(self, 3, text_color=WHITE)
        self.next_slide()


class IntroduccionSlide(Slide):
    def construct(self):
        titulo = Tex("\\textbf{INTRODUCCI\u00d3N}", font_size=36, color=XIOPM_BLUE).to_edge(UP, buff=0.5)
        linea = Line(LEFT, RIGHT, color=XIOPM_BLUE, stroke_width=2).set_width(
            config.frame_width - 1.5
        ).next_to(titulo, DOWN, buff=0.3)
        self.play(FadeIn(titulo, shift=DOWN * 0.1), Create(linea), run_time=0.9)
        add_corner_badge(self, text_color=XIOPM_BLUE)

        datos = [
            (r"\faCarSide", "Electr\u00f3nica vehicular", "Sensores y actuadores con la ECU"),
            (r"\faPlug", "Est\u00e1ndar OBD-II", "Acceso a los datos del veh\u00edculo"),
            (r"\faMicrochip", "Procesamiento", "Consumo estimado en tiempo real"),
            (r"\faWifi", "Interfaz", "Panel web generado por el ESP32"),
        ]

        positions = [
            LEFT * 5.5 + UP * 1.3,
            RIGHT * 5.5 + UP * 1.3,
            LEFT * 5.5 + DOWN * 1.6,
            RIGHT * 5.5 + DOWN * 1.6,
        ]

        for (icon_tex, label, desc), pos in zip(datos, positions):
            is_left_col = pos[0] < 0
            text_dir = RIGHT if is_left_col else LEFT
            align_edge = LEFT if is_left_col else RIGHT

            caja = RoundedRectangle(
                corner_radius=0.2, width=1.9, height=1.9,
                fill_color=XIOPM_BLUE, fill_opacity=1, stroke_width=0,
            ).move_to(pos)

            icono = Tex(icon_tex, font_size=78, color=WHITE).move_to(pos)
            icono.set_fill(WHITE, 1).set_stroke(width=0)

            barra = Rectangle(width=0.08, height=0.78, fill_color=XIOPM_BLUE,
                               fill_opacity=1, stroke_width=0)
            texto = VGroup(
                Tex(f"\\textbf{{{label}}}", font_size=30, color=XIOPM_BLUE),
                Tex(desc, font_size=18, color=INK),
            ).arrange(DOWN, aligned_edge=align_edge, buff=0.1)

            if is_left_col:
                fila = VGroup(barra, texto).arrange(RIGHT, buff=0.25)
            else:
                fila = VGroup(texto, barra).arrange(RIGHT, buff=0.25)

            fila.next_to(caja, text_dir, buff=0.5)

            self.play(FadeIn(caja), run_time=0.38)
            circular_reveal(self, icono, XIOPM_BLUE, run_time=0.9)
            self.play(FadeIn(fila, shift=text_dir * 0.15), run_time=0.68)
            self.next_slide()

        add_footer(self, 4, text_color=GRAY_D)
        self.next_slide()


def section_title(text):
    titulo = Tex(f"\\textbf{{{text}}}", font_size=36, color=XIOPM_BLUE).to_edge(UP, buff=0.5)
    linea = Line(LEFT, RIGHT, color=XIOPM_BLUE, stroke_width=2).set_width(
        config.frame_width - 1.5
    ).next_to(titulo, DOWN, buff=0.3)
    return titulo, linea


class PlanteamientoSlide(Slide):
    def construct(self):
        titulo, linea = section_title("PLANTEAMIENTO DEL PROBLEMA")
        self.play(FadeIn(titulo, shift=DOWN * 0.1), Create(linea), run_time=0.9)
        add_corner_badge(self, text_color=XIOPM_BLUE)

        # ------- Indicador de combustible: aparece centrado, 3 s, luego
        # se reduce y se mueve a la derecha (sigue "vivo" de fondo). -------
        ind = build_indicador()
        nivel, ox, oy, scale = ind["nivel"], ind["ox"], ind["oy"], ind["scale"]
        fixed, moving = ind["fixed"], ind["moving"]
        arco, marcas, letra_e, letra_f = fixed

        self.play(
            Create(arco), LaggedStart(*[Create(m) for m in marcas], lag_ratio=0.1),
            FadeIn(letra_e), FadeIn(letra_f), run_time=1.12,
        )
        self.play(FadeIn(moving), run_time=0.6)
        self.wait(0.7)  # ~3 s en total con el reveal de arriba

        IND_SCALE = 0.78
        target_point = RIGHT * 4.6 + DOWN * 0.5
        native_center = fixed.get_center()
        IND_SHIFT = target_point - IND_SCALE * native_center
        self.play(
            fixed.animate.scale(IND_SCALE, about_point=ORIGIN).shift(IND_SHIFT),
            scale.animate.set_value(IND_SCALE),
            ox.animate.set_value(IND_SHIFT[0]),
            oy.animate.set_value(IND_SHIFT[1]),
            run_time=1.05,
        )

        # El indicador queda "vivo" (oscilando suave) de fondo; PERIOD es
        # un ciclo COMPLETO de la oscilacion, para que el loop de abajo
        # (next_slide(loop=True)) no se note al repetirse.
        PERIOD = 2 * np.pi / 0.6
        t_acc = {"t": 0.0}

        def oscilar_fondo(m, dt):
            t_acc["t"] += dt
            m.set_value(0.5 + 0.42 * np.sin(t_acc["t"] * 0.6))

        nivel.add_updater(oscilar_fondo)
        self.add(nivel)

        bullets = bullet_list([
            "El consumo de combustible es una variable clave para la eficiencia "
            "energ\u00e9tica y el desempe\u00f1o de los veh\u00edculos.",
            "En Bolivia, el uso del transporte creci\u00f3 un 11,92\\,\\% seg\u00fan el INE, "
            "aumentando la demanda de combustible.",
            "La variabilidad en precio y calidad de la gasolina genera incertidumbre "
            "y puede afectar las lecturas de los sensores OBD-II.",
            "No existen herramientas accesibles que permitan estimar el consumo de "
            "combustible en tiempo real.",
        ], font_size=29, width=46, buff=0.6)
        bullets.to_edge(LEFT, buff=0.9)
        bullets.set_y(-0.3)

        self.play(LaggedStart(*[FadeIn(r, shift=UP * 0.1) for r in bullets], lag_ratio=0.25), run_time=1.65)
        add_footer(self, 5, text_color=GRAY_D)

        # Segmento en loop: el indicador sigue oscilando indefinidamente
        # mientras el presentador se queda en esta diapositiva (en vez de
        # congelarse en el ultimo frame).
        self.next_slide(loop=True)
        self.wait(PERIOD)
        nivel.clear_updaters()
        self.next_slide()


class JustificacionSlide(Slide):
    def construct(self):
        titulo, linea = section_title("JUSTIFICACI\u00d3N")
        self.play(FadeIn(titulo, shift=DOWN * 0.1), Create(linea), run_time=0.9)
        add_corner_badge(self, text_color=XIOPM_BLUE)

        tecnica = make_card(
            "T\u00c9CNICA",
            "Integra adquisici\u00f3n OBD-II con un modelo f\u00edsico-matem\u00e1tico, "
            "frente a m\u00e9todos basados solo en mantenimiento correctivo o preventivo.",
        ).move_to(LEFT * 3.3 + UP * 0.85)

        economica = make_card(
            "ECON\u00d3MICA",
            "Permite optimizar el uso del veh\u00edculo y reducir gastos "
            "asociados a un consumo excesivo de gasolina.",
        ).move_to(RIGHT * 3.3 + UP * 0.85)

        social = make_card(
            "SOCIAL",
            "Promueve un uso m\u00e1s responsable del combustible y mayor "
            "transparencia en el desempe\u00f1o de los veh\u00edculos.",
        ).move_to(DOWN * 1.95)

        # Triangulo: tecnica (arriba-izq) -> economica (arriba-der) -> social (abajo-centro),
        # cada una revelada con un barrido.
        for grupo in (tecnica, economica, social):
            wipe_reveal(self, grupo, cover_color=WHITE, direction=RIGHT, run_time=0.75)
            self.next_slide()

        add_footer(self, 6, text_color=GRAY_D)
        self.next_slide()


OBJ_GENERAL = (
    "Implementar un sistema embebido capaz de adquirir datos en tiempo real "
    "desde el puerto OBD-II, con el fin de estimar el consumo instant\u00e1neo de "
    "combustible en veh\u00edculos a gasolina con inyecci\u00f3n electr\u00f3nica, generar "
    "un registro hist\u00f3rico y validar los resultados frente a mediciones de "
    "referencia."
)
OBJ_ESPECIFICOS = [
    "Determinar los par\u00e1metros OBD-II disponibles (MAF/MAP, RPM, velocidad).",
    "Desarrollar un modelo matem\u00e1tico basado en la relaci\u00f3n aire-combustible.",
    "Dise\u00f1ar un sistema embebido de adquisici\u00f3n, guardado y procesamiento de datos.",
    "Integrar una plataforma telem\u00e9trica IoT (ESP32-S3) para transmisi\u00f3n y almacenamiento.",
    "Evaluar el sistema en condiciones reales, validando su precisi\u00f3n frente a referencias.",
]

GRIS_FIG = ManimColor.from_rgb((58, 66, 80))
ORO_FIG = ManimColor.from_rgb((244, 180, 0))
XIOPM_BLUE_LIGHT = ManimColor.from_rgb((127, 166, 224))


def color_barra(i):
    return interpolate_color(XIOPM_BLUE_LIGHT, XIOPM_BLUE, i / 4)


def make_barra(x, w, h, color, suelo, numero=None):
    """Barra con esquinas superiores redondeadas. g[0] es el cuerpo."""
    cuerpo = RoundedRectangle(width=w, height=h, corner_radius=[0.12, 0.12, 0, 0],
                               stroke_width=0).set_fill(color, 1)
    cuerpo.move_to([x, suelo + h / 2, 0])
    g = VGroup(cuerpo)
    if numero is not None:
        badge = VGroup(
            Circle(radius=0.24, stroke_width=0).set_fill(WHITE, 1),
            Tex(f"\\textbf{{{numero}}}", font_size=22, color=color),
        )
        badge[1].move_to(badge[0])
        badge.move_to([x, suelo + max(h - 0.38, h / 2), 0])
        g.add(badge)
    return g


def make_persona(alto=1.6):
    """Pictograma de ingeniero con casco. Pies en el origen."""
    s = alto / 1.6
    rr = lambda w, h, r, p: RoundedRectangle(width=w, height=h, corner_radius=r,
                                             stroke_width=0).set_fill(GRIS_FIG, 1).move_to(p)
    g = VGroup(
        rr(0.16, 0.62, 0.08, [-0.11, 0.31, 0]),
        rr(0.16, 0.62, 0.08, [0.11, 0.31, 0]),
        rr(0.46, 0.62, 0.16, [0, 0.88, 0]),
        rr(0.13, 0.5, 0.06, [-0.31, 0.92, 0]),
        rr(0.13, 0.5, 0.06, [0, 0, 0]).rotate(-50 * DEGREES).move_to([0.36, 1.08, 0]),
        Circle(radius=0.2, stroke_width=0).set_fill(GRIS_FIG, 1).move_to([0, 1.39, 0]),
        Sector(radius=0.23, angle=PI, start_angle=0, arc_center=[0, 1.45, 0],
               stroke_width=0).set_fill(XIOPM_BLUE, 1),
        RoundedRectangle(width=0.62, height=0.07, corner_radius=0.03, stroke_width=0)
        .set_fill(XIOPM_BLUE, 1).move_to([0.04, 1.45, 0]),
    )
    return g.scale(s, about_point=ORIGIN)


def make_big_card(title, desc, numero=None, width=10.2, header_h=0.85, body_h=3.3,
                   desc_width=46, title_fs=33, desc_fs=29, radius=0.2):
    """Tarjeta grande (estilo de la presentacion: header azul redondeado
    arriba + cuerpo claro redondeado abajo) para la escalera de objetivos."""
    body = RoundedRectangle(
        corner_radius=[0, radius, radius, 0], width=width, height=body_h,
        fill_color=CARD_BODY_BG, fill_opacity=1, stroke_color=XIOPM_BLUE, stroke_width=1.5,
    )
    desc_txt = paragraph(desc, width=desc_width, font_size=desc_fs, color=INK, align=LEFT)
    desc_txt.move_to(body.get_center())

    header = RoundedRectangle(
        corner_radius=[radius, 0, 0, radius], width=width, height=header_h,
        fill_color=XIOPM_BLUE, fill_opacity=1, stroke_width=0,
    )
    header.next_to(body, UP, buff=0)

    if numero is not None:
        badge = VGroup(
            Circle(radius=0.32, stroke_width=0).set_fill(WHITE, 1),
            Tex(f"\\textbf{{{numero}}}", font_size=28, color=XIOPM_BLUE),
        )
        badge[1].move_to(badge[0])
        badge.move_to(header.get_left()).shift(RIGHT * 0.55)
        title_txt = Tex(f"\\textbf{{{title}}}", font_size=title_fs, color=WHITE)
        title_txt.next_to(badge, RIGHT, buff=0.3)
        encabezado = VGroup(badge, title_txt)
    else:
        title_txt = Tex(f"\\textbf{{{title}}}", font_size=title_fs, color=WHITE)
        title_txt.move_to(header.get_center())
        encabezado = VGroup(title_txt)

    return body, header, encabezado, desc_txt


class ObjetivosSlide(Slide, MovingCameraScene):
    def construct(self):
        frame = self.camera.frame

        titulo, linea = section_title("OBJETIVOS")
        titulo.set_z_index(5)
        linea.set_z_index(5)
        self.play(FadeIn(titulo, shift=DOWN * 0.1), Create(linea), run_time=0.9)
        badge_inst = add_corner_badge(self, text_color=XIOPM_BLUE, run_time=0.7)
        badge_inst.set_z_index(5)
        footer = add_footer(self, 7, text_color=GRAY_D, run_time=0.55)
        footer.set_z_index(5)

        SUELO = -3.3
        XS = np.linspace(-4.6, 2.4, 5)
        HS = np.linspace(0.55, 2.6, 5)
        XG, WG, HG = 4.8, 1.3, 3.6

        suelo = Line([-7.3, SUELO, 0], [7.3, SUELO, 0], color=GRIS_FIG, stroke_width=3)
        self.play(Create(suelo), run_time=0.6)

        # ---------- columna principal + bandera ----------
        columna = make_barra(XG, WG, HG, XIOPM_BLUE, SUELO)
        self.play(GrowFromEdge(columna, DOWN), run_time=1.0, rate_func=smooth)

        reloj = ValueTracker(0)
        reloj.add_updater(lambda m, dt: m.increment_value(dt))
        self.add(reloj)
        despliegue = ValueTracker(0)
        viento = ValueTracker(1.0)

        base_asta = np.array([XG + 0.35, SUELO + HG, 0])
        punta_asta = base_asta + UP * 1.1
        asta = Line(base_asta, punta_asta, color=GRIS_FIG, stroke_width=5)
        remate = Dot(punta_asta, radius=0.06, color=GRIS_FIG)

        def make_tela():
            t = reloj.get_value()
            L, A = 0.75 * max(despliegue.get_value(), 0.001), 0.44
            amp = 0.07 * viento.get_value()
            n = 26
            xs = np.linspace(0, L, n)
            ola = lambda x, fase: amp * (x / 0.75) * np.sin(7 * x - 5 * t + fase)
            arriba = [punta_asta + [x, ola(x, 0), 0] for x in xs]
            abajo = [punta_asta + [x, -A + ola(x, 0.6), 0] for x in xs[::-1]]
            return Polygon(*arriba, *abajo, stroke_width=0).set_fill(XIOPM_BLUE, 0.85)

        tela = always_redraw(make_tela)
        self.play(Create(asta), FadeIn(remate), run_time=0.4)
        self.add(tela)
        self.play(despliegue.animate.set_value(1), run_time=0.6, rate_func=smooth)

        lbl_gral = Tex("\\textbf{Objetivo General}", font_size=34, color=XIOPM_BLUE)
        lbl_gral.move_to([-1.2, 1.3, 0])
        guia = VGroup(
            Line(lbl_gral.get_corner(DR) + [0.15, 0.1, 0], [XG - 0.75, SUELO + HG - 0.25, 0],
                 color=GRAY_C, stroke_width=2.5),
            Dot([XG - 0.75, SUELO + HG - 0.25, 0], radius=0.06, color=GRAY_C),
        )
        self.play(FadeIn(lbl_gral, shift=RIGHT * 0.3), Create(guia), run_time=0.75)
        self.next_slide()

        self.mostrar_tarjeta(columna, "Objetivo General", OBJ_GENERAL, None)
        self.play(FadeOut(lbl_gral), FadeOut(guia), run_time=0.4)

        # ---------- ingeniero + 5 barras como escalera ----------
        ing = make_persona(1.4).move_to([-6.2, SUELO, 0], aligned_edge=DOWN)
        self.play(LaggedStart(*[FadeIn(p, shift=UP * 0.15) for p in ing], lag_ratio=0.12),
                  run_time=1.0)

        barras = [make_barra(x, 1.0, h, color_barra(i), SUELO, i + 1)
                  for i, (x, h) in enumerate(zip(XS, HS))]
        self.play(LaggedStart(*[GrowFromEdge(b, DOWN) for b in barras], lag_ratio=0.25),
                  run_time=1.6)

        c0 = np.array([-5.2, SUELO + 1.0, 0])
        c1 = np.array([-2.6, SUELO + 2.0, 0])
        c2 = np.array([0.6, SUELO + 2.8, 0])
        c3 = np.array([XG - 0.6, SUELO + HG + 0.5, 0])
        camino = DashedVMobject(
            CubicBezier(c0, c1, c2, c3, color=GRAY_C, stroke_width=2.5), num_dashes=26,
        )
        tang = c3 - c2
        punta = Triangle(stroke_width=0).set_fill(GRAY_C, 1).scale(0.11)
        punta.rotate(np.arctan2(tang[1], tang[0]) - PI / 2).move_to(c3)
        self.play(Create(camino), run_time=0.85)
        self.play(FadeIn(punta, scale=1.5), run_time=0.25)
        self.next_slide()

        # El encabezado/pie estan fijos en coordenadas del MUNDO, no de
        # pantalla: si la camara hace zoom, se verian deformados. Se
        # ocultan durante la seccion de zoom y vuelven al final.
        ui_fija = [titulo, linea, badge_inst, footer]
        self.play(*[FadeOut(m) for m in ui_fija], run_time=0.3)

        # ---------- los 5 objetivos especificos ----------
        for i, b in enumerate(barras):
            frame.save_state()
            self.play(frame.animate.scale(0.46).move_to(b.get_center() + UP * 0.6), run_time=0.85)
            self.mostrar_tarjeta(b, f"Objetivo Espec\u00edfico {i + 1}", OBJ_ESPECIFICOS[i],
                                 i + 1, desde_zoom=True)
            self.play(ing.animate(path_arc=-1.0).move_to([XS[i], SUELO + HS[i], 0],
                                                          aligned_edge=DOWN), run_time=0.6)

        self.play(*[FadeIn(m) for m in ui_fija], run_time=0.3)

        # ---------- llega a la meta ----------
        self.play(ing.animate(path_arc=-1.2).move_to([XG - 0.3, SUELO + HG, 0],
                                                      aligned_edge=DOWN), run_time=0.85)
        self.play(viento.animate.set_value(1.8), Indicate(columna[0], color=XIOPM_BLUE, scale_factor=1.03),
                  run_time=0.75)
        reloj.clear_updaters()
        self.next_slide()

    def mostrar_tarjeta(self, origen, titulo, texto, numero=None, desde_zoom=False):
        """La barra se amplia hasta convertirse en la tarjeta del objetivo."""
        frame = self.camera.frame
        fondo = Rectangle(
            width=config.frame_width + 0.6, height=config.frame_height + 0.6,
            stroke_width=0, fill_color=WHITE, fill_opacity=1,
        )
        body, header, encabezado, desc_txt = make_big_card(titulo, texto, numero)

        semilla = origen[0].copy()
        self.add(semilla)
        anims = [ReplacementTransform(semilla, fondo)]
        if desde_zoom:
            anims.append(Restore(frame))
        self.play(*anims, run_time=0.9)
        self.play(FadeIn(body, scale=0.92), run_time=0.4)
        self.play(GrowFromEdge(header, UP), run_time=0.4)
        self.play(FadeIn(encabezado, shift=RIGHT * 0.3), run_time=0.45)
        self.play(FadeIn(desc_txt, shift=UP * 0.15), run_time=0.55)
        self.next_slide()
        self.play(FadeOut(VGroup(body, header, encabezado, desc_txt)), run_time=0.4)
        destino = origen[0].copy()
        self.play(ReplacementTransform(fondo, destino), run_time=0.7)
        self.remove(destino)


class AlcancesSlide(Slide):
    def construct(self):
        titulo, linea = section_title("ALCANCES")
        self.play(FadeIn(titulo, shift=DOWN * 0.1), Create(linea), run_time=0.9)
        add_corner_badge(self, text_color=XIOPM_BLUE)

        bullets = bullet_list([
            "Lectura en tiempo real de parámetros OBD-II (RPM, MAP, IAT, ajustes de "
            "combustible) vía ESP32-S3 y bus CAN.",
            "Estimación del consumo mediante el modelo Speed-Density, calibrado en "
            "dos vehículos de prueba.",
            "Interfaz web propia servida por el ESP32-S3 (SoftAP), sin apps ni "
            "conexión a internet.",
            "Validación experimental en condiciones reales: MAPE 2,75\\,\\% frente a "
            "ELM327 y 4,84\\,\\% frente al aforo real.",
        ], font_size=26, width=52, buff=0.45)
        bullets.move_to(ORIGIN).set_y(-0.3)

        self.play(LaggedStart(*[FadeIn(r, shift=UP * 0.1) for r in bullets], lag_ratio=0.25), run_time=1.5)
        add_footer(self, 8, text_color=GRAY_D)
        self.next_slide()


class LimitesSlide(Slide):
    def construct(self):
        titulo, linea = section_title("LÍMITES")
        self.play(FadeIn(titulo, shift=DOWN * 0.1), Create(linea), run_time=0.9)
        add_corner_badge(self, text_color=XIOPM_BLUE)

        bullets = bullet_list([
            "Enfocado solo en vehículos a gasolina con inyección electrónica "
            "(no diésel ni bi-fuel).",
            "Requiere puerto OBD-II; no es compatible con sistemas OBD-I.",
            "Pruebas realizadas en dos vehículos disponibles (Nissan Vanette y "
            "Changan Honor), no en minibuses del transporte público.",
            "La precisión depende del estado mecánico del vehículo evaluado.",
        ], font_size=26, width=52, buff=0.45)
        bullets.move_to(ORIGIN).set_y(-0.3)

        self.play(LaggedStart(*[FadeIn(r, shift=UP * 0.1) for r in bullets], lag_ratio=0.25), run_time=1.5)
        add_footer(self, 9, text_color=GRAY_D)
        self.next_slide()


class MarcoTeoricoSlide(Slide):
    def construct(self):
        fondo = cover_image(BG_MARCO_TEORICO)
        self.play(FadeIn(fondo), run_time=1.2)

        velo = Rectangle(
            width=config.frame_width, height=config.frame_height,
            fill_color=XIOPM_BLUE, fill_opacity=0.55, stroke_width=0,
        )
        self.play(FadeIn(velo), run_time=0.9)

        titulo = Tex("\\textbf{MARCO TEÓRICO}", font_size=64, color=WHITE)
        linea = Line(LEFT, RIGHT, color=WHITE, stroke_width=3).set_width(4).next_to(titulo, DOWN, buff=0.3)
        self.play(FadeIn(titulo, scale=1.15), run_time=0.98)
        self.play(Create(linea), run_time=0.6)

        add_corner_badge(self, text_color=WHITE)
        add_footer(self, 10, text_color=WHITE)
        self.next_slide()


def content_slide(scene, titulo_txt, items, page_num, font_size=26, width=52, buff=0.45):
    """Diapositiva estandar: titulo + linea + vinetas centradas, sin caja."""
    titulo, linea = section_title(titulo_txt)
    scene.play(FadeIn(titulo, shift=DOWN * 0.1), Create(linea), run_time=0.9)
    add_corner_badge(scene, text_color=XIOPM_BLUE)

    bullets = bullet_list(items, font_size=font_size, width=width, buff=buff)
    bullets.move_to(ORIGIN).set_y(-0.3)

    scene.play(LaggedStart(*[FadeIn(r, shift=UP * 0.1) for r in bullets], lag_ratio=0.25), run_time=1.5)
    add_footer(scene, page_num, text_color=GRAY_D)
    scene.next_slide()


FIG_ECU = "assets/figures/fig2_1_ecu.png"


class ECUSlide(Slide):
    def construct(self):
        titulo, linea = section_title("ECU")
        self.play(FadeIn(titulo, shift=DOWN * 0.1), Create(linea), run_time=0.9)
        add_corner_badge(self, text_color=XIOPM_BLUE)

        img = ImageMobject(FIG_ECU).set(height=4.2)
        img.move_to(ORIGIN).set_y(-0.35)

        self.play(FadeIn(img, scale=0.95), run_time=0.9)
        self.next_slide()

        self.play(img.animate.set(height=3.3).move_to(LEFT * 3.5 + DOWN * 0.1), run_time=0.83)

        cita = Tex(
            "\\footnotesize Figura 2.1 \u2014 Kaiser (2014)",
            font_size=18, color=GRAY_D,
        ).next_to(img, DOWN, buff=0.3)
        self.play(FadeIn(cita), run_time=0.45)

        texto = bullet_list([
            "Microprocesador + memorias (RAM, ROM, EPROM): procesa sensores y decide.",
            "Controla inyecci\u00f3n, encendido, admisi\u00f3n de aire y diagn\u00f3stico OBD-II.",
            "Se comunica con otras ECUs mediante la red CAN.",
            "Ajusta la mezcla aire-combustible en tiempo real para optimizar el consumo.",
        ], font_size=22, width=28, buff=0.4)
        texto.move_to(RIGHT * 3.3 + DOWN * 0.1)

        self.play(FadeIn(texto, shift=LEFT * 0.15), run_time=1.05)
        add_footer(self, 11, text_color=GRAY_D)
        self.next_slide()


CAN_L_COLOR = "#00ACC1"  # distinto de CAN High, para diferenciarlos


class OBD2Slide(Slide):
    def construct(self):
        titulo, linea = section_title("OBD-II")
        self.play(FadeIn(titulo, shift=DOWN * 0.1), Create(linea), run_time=0.9)
        add_corner_badge(self, text_color=XIOPM_BLUE)
        footer = add_footer(self, 12, text_color=GRAY_D)

        # Pines con los colores propios del proyecto: CAN High y CAN Low
        # distinguibles entre si (en el archivo original comparten color).
        pines_dict = dict(conector_obd2.PINES)
        nombre_h, _ = pines_dict[6]
        nombre_l, _ = pines_dict[14]
        pines_dict[6] = (nombre_h, conector_obd2.AZUL)
        pines_dict[14] = (nombre_l, CAN_L_COLOR)

        conector, pines = conector_obd2.build_conector()

        self.play(FadeIn(conector), run_time=0.68)
        self.play(LaggedStart(*[FadeIn(pines[n][0], scale=0.6) for n in range(1, 17)],
                              lag_ratio=0.06), run_time=0.68)
        self.play(LaggedStart(*[Write(pines[n][1]) for n in range(1, 17)], lag_ratio=0.06),
                  run_time=0.9)
        self.next_slide()

        for n in conector_obd2.ORDEN:
            anims_cable, anims_etiqueta = conector_obd2.make_cable_anims(n, pines[n], pines_dict)
            self.play(*anims_cable, run_time=0.49)
            self.play(*anims_etiqueta, run_time=0.38)
            self.wait(0.15)
        self.next_slide()

        marcos = VGroup(*[
            SurroundingRectangle(pines[n], buff=0.07, corner_radius=0.08,
                                 stroke_color="#F4B400", stroke_width=5)
            for n in conector_obd2.PINES_PROYECTO])
        nota = Tex("\\textbf{Pines utilizados por el sistema}", font_size=22, color="#B07F00")
        nota.move_to([0, -3.55, 0])
        self.play(LaggedStart(*[Create(m) for m in marcos], lag_ratio=0.15),
                  FadeIn(nota, shift=UP * 0.2), run_time=0.83)
        self.play(*[Indicate(pines[n], color="#F4B400", scale_factor=1.15)
                    for n in conector_obd2.PINES_PROYECTO], run_time=0.68)
        self.next_slide()


class RedCANSlide(Slide):
    def construct(self):
        content_slide(self, "RED CAN", [
            "El bus CAN (Controller Area Network), creado por Bosch en los a\u00f1os 80, "
            "permite que varias ECUs se comuniquen por un solo canal compartido, sin cableado "
            "punto a punto.",
            "Comunicaci\u00f3n multi-maestro basada en mensajes con identificador y prioridad; "
            "cada trama incluye datos y verificaci\u00f3n de errores (CRC).",
            "Usa dos l\u00edneas diferenciales, CAN High y CAN Low, con alta inmunidad al ruido "
            "electromagn\u00e9tico del entorno automotriz.",
            "Cada nodo se compone de un microcontrolador, un controlador CAN y un transceptor CAN "
            "que adapta las se\u00f1ales al bus f\u00edsico.",
        ], 13)


class ConsumoGasolinaSlide(Slide):
    def construct(self):
        content_slide(self, "CONSUMO DE GASOLINA", [
            "El consumo de combustible mide cu\u00e1nta gasolina usa el motor por distancia "
            "(L/100\\,km) o por tiempo (L/h), reflejando la eficiencia energ\u00e9tica del "
            "veh\u00edculo.",
            "Puede estimarse con modelos estad\u00edsticos (velocidad/distancia), mecanicistas "
            "(fuerzas resistivas) o basados en sensores de la ECU (MAF, MAP, TPS), estos \u00faltimos "
            "los m\u00e1s precisos en tiempo real.",
            "La relaci\u00f3n aire-combustible (AFR) define la calidad de la mezcla; en gasolina la "
            "relaci\u00f3n estequiom\u00e9trica es 14,7:1, regulada por el factor lambda ($\\lambda$).",
            "El modelo basado en MAF estima el consumo instant\u00e1neo directamente: "
            "$\\dot{F}_{(L/h)}\\approx\\mathrm{MAF}_{(g/s)}\\times0{,}33$.",
        ], 14)


class MicrocontroladoresSlide(Slide):
    def construct(self):
        content_slide(self, "MICROCONTROLADORES", [
            "Un microcontrolador integra en un solo chip la CPU, memoria y perif\u00e9ricos de "
            "entrada/salida, a diferencia de un microprocesador que necesita componentes externos.",
            "Es la base de todo sistema embebido: hardware + firmware dedicados a una tarea "
            "espec\u00edfica, con restricciones de tiempo, consumo y recursos.",
            "Incluye un n\u00facleo (RISC: ARM Cortex-M, AVR, PIC), memorias on-chip (Flash, RAM, "
            "EEPROM) y perif\u00e9ricos (ADC, PWM, UART, SPI, I2C, controladores CAN).",
            "El ESP32-S3 usado en este proyecto es un SoC: doble n\u00facleo Xtensa LX7, controlador "
            "CAN nativo (TWAI), Wi-Fi y Bluetooth integrados.",
        ], 15)
