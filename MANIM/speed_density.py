"""Deduccion animada del metodo Speed-Density.

Abre con el motor de 4 tiempos (motor_4t.build_engine) funcionando solo
en pantalla; luego se reduce y se desplaza a la derecha, donde queda
"vivo" (girando) durante toda la deduccion: AFR -> zoom in situ a la
camara de combustion -> eficiencia volumetrica -> ecuacion de gases
ideales -> zoom in situ al piston-biela-ciguenal -> por que el factor 2
-> combinacion final -> se retira al mostrar la ecuacion de flujo
masico de aire estimado (eq:speed_density), fiel a CAP3/cap3.tex.

El "zoom" NO mueve la camara de la escena (eso tapaba toda la pantalla
y el texto de alrededor). En vez de eso, el motor se agranda en su
propio sitio alrededor del punto de interes (ver zoom_in/zoom_out),
dejando el resto de la composicion (titulo, ecuaciones) intacto.

Render rapido (vista previa):
    manim -pql speed_density.py SpeedDensityDerivation

Render en alta calidad (para insertar en la presentacion):
    manim -qh speed_density.py SpeedDensityDerivation
"""

import numpy as np
from manim import *
import _ms_compat  # noqa: F401  (parche de compatibilidad manim-slides <-> manim 0.22)
from manim_slides import Slide
from motor_4t import build_engine, fase, GAS_ADM, GAS_COMP, GAS_EXP, GAS_ESC

UMSA_BLUE = ManimColor.from_rgb((19, 57, 132))
UMSA_GOLD = ManimColor.from_rgb((224, 176, 32))
INK = ManimColor.from_rgb((30, 30, 30))

config.background_color = WHITE
Tex.set_default(color=INK)
MathTex.set_default(color=INK)
Text.set_default(color=INK)

NOMBRES_TIEMPO = ["Admision", "Compresion", "Combustion", "Escape"]
COLORES_TIEMPO = [GAS_ADM, GAS_COMP, GAS_EXP, GAS_ESC]

ENG_SCALE = 0.65
ENG_SHIFT = RIGHT * 3.3 + DOWN * 0.3

# Cuanto se agranda el motor "in situ" en cada zoom (no es zoom de camara).
CHAMBER_ZOOM = 2.2
CRANK_ZOOM = 1.9


class SpeedDensityDerivation(Slide):
    def construct(self):
        eng = build_engine()
        theta, ox, oy, scale = eng["theta"], eng["ox"], eng["oy"], eng["scale"]

        def zoom_in(anchor_fn, factor, run_time=2.6):
            """Agranda el motor alrededor de anchor_fn() sin mover la
            camara: el punto de interes queda fijo en pantalla y el
            resto de la escena no se ve afectado."""
            world0 = anchor_fn()
            s0 = scale.get_value()
            off0 = np.array([ox.get_value(), oy.get_value(), 0.0])
            local = (world0 - off0) / s0
            s1 = s0 * factor
            off1 = off0 + (s0 - s1) * local
            self.play(
                eng["fixed"].animate.scale(s1 / s0, about_point=world0),
                scale.animate.set_value(s1),
                ox.animate.set_value(off1[0]),
                oy.animate.set_value(off1[1]),
                run_time=run_time,
            )
            return s0, off0, world0

        def zoom_out(state, run_time=2.1):
            s0, off0, world0 = state
            s1 = scale.get_value()
            self.play(
                eng["fixed"].animate.scale(s0 / s1, about_point=world0),
                scale.animate.set_value(s0),
                ox.animate.set_value(off0[0]),
                oy.animate.set_value(off0[1]),
                run_time=run_time,
            )

        # =================================================================
        # Apertura: solo el motor funcionando
        # =================================================================
        self.play(FadeIn(eng["fixed"]), FadeIn(eng["moving"]), run_time=1.6)
        self.play(theta.animate.set_value(4 * PI), run_time=7, rate_func=linear)

        # =================================================================
        # El motor se reduce y se mueve a la derecha; aparece el encabezado
        # =================================================================
        titulo = Tex("Metodo Speed-Density", color=UMSA_BLUE, font_size=44).to_edge(UP)
        subtitulo = Tex(
            "Estimacion del flujo masico de aire sin sensor MAF",
            color=INK, font_size=26,
        ).next_to(titulo, DOWN)
        linea = Line(LEFT, RIGHT, color=UMSA_BLUE, stroke_width=3).set_width(
            config.frame_width - 1.5
        ).next_to(subtitulo, DOWN, buff=0.25)

        self.play(
            eng["fixed"].animate.scale(ENG_SCALE, about_point=ORIGIN).shift(ENG_SHIFT),
            scale.animate.set_value(ENG_SCALE),
            ox.animate.set_value(ENG_SHIFT[0]),
            oy.animate.set_value(ENG_SHIFT[1]),
            Write(titulo), FadeIn(subtitulo, shift=DOWN * 0.2),
            run_time=2.3,
        )
        self.play(Create(linea), run_time=1.3)

        # Mascara: oculta cualquier parte del motor que, al "acercarse"
        # (crecer in situ), sobrepase la linea del encabezado -- asi el
        # zoom nunca tapa el titulo/subtitulo, quedan siempre encima.
        mask_y = linea.get_y() - 0.05
        mascara = Rectangle(
            width=config.frame_width + 2, height=10,
            fill_color=WHITE, fill_opacity=1, stroke_width=0,
        ).move_to([0, mask_y + 5, 0])
        mascara.set_z_index(2)
        titulo.set_z_index(3)
        subtitulo.set_z_index(3)
        linea.set_z_index(3)
        self.add(mascara)

        # El motor sigue girando de fondo (ritmo lento) mientras se lee el texto.
        theta.add_updater(lambda m, dt: m.increment_value(dt * 0.9))
        self.add(theta)
        self.next_slide()

        # =================================================================
        # Motivacion / datos disponibles
        # =================================================================
        motivo = VGroup(
            Tex(r"El vehiculo \textbf{no} soporta el PID 0x10 (MAF).", font_size=27),
            Tex(r"Se estima $\dot m_{air}$ a partir de tres lecturas OBD-II:", font_size=27),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.18).to_edge(LEFT).shift(UP * 0.2)
        pids = VGroup(
            Tex(r"MAP (0x0B)", font_size=27, color=UMSA_BLUE),
            Tex(r"IAT (0x0F)", font_size=27, color=UMSA_BLUE),
            Tex(r"RPM (0x0C)", font_size=27, color=UMSA_BLUE),
        ).arrange(RIGHT, buff=0.6).next_to(motivo, DOWN, buff=0.5).align_to(motivo, LEFT)

        self.play(FadeIn(motivo, shift=UP * 0.2), run_time=1.3)
        self.play(LaggedStart(*[FadeIn(p, shift=UP * 0.2) for p in pids], lag_ratio=0.25), run_time=1.6)
        self.wait(1.6)
        self.play(FadeOut(motivo), FadeOut(pids), run_time=1.3)
        self.next_slide()

        # =================================================================
        # Partimos de la relacion aire-combustible (AFR) + zoom in situ a
        # la camara de combustion (el motor se agranda en su sitio; la
        # camara de la escena NO se mueve).
        # =================================================================
        afr_txt = Tex(
            "Partimos de la relacion aire-combustible (AFR):", font_size=27,
        ).to_edge(LEFT).shift(UP * 1.7)
        afr_eq = MathTex(
            r"\mathrm{AFR}", "=", r"\frac{\dot m_{air}}{\dot m_{fuel}}"
        ).scale(1.2).next_to(afr_txt, DOWN, buff=0.5).align_to(afr_txt, LEFT)
        afr_nota = Tex(
            r"\footnotesize Gasolina: $\mathrm{AFR}_s \approx 14{,}7$",
            font_size=22, color=GRAY_D,
        ).next_to(afr_eq, DOWN, buff=0.3).align_to(afr_eq, LEFT)

        self.play(FadeIn(afr_txt, shift=RIGHT * 0.2), run_time=1.3)
        self.play(Write(afr_eq), run_time=1.4)
        self.play(FadeIn(afr_nota, shift=UP * 0.1), run_time=1.3)
        self.wait(1.1)

        chamber_state = zoom_in(eng["chamber_point"], CHAMBER_ZOOM, run_time=2.6)
        self.wait(2.0)
        zoom_out(chamber_state, run_time=2.1)

        afr_conclusion = VGroup(
            Tex(r"Basta con estimar $\dot m_{air}$ para", font_size=25, color=UMSA_BLUE),
            Tex(r"obtener el combustible inyectado.", font_size=25, color=UMSA_BLUE),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.12).next_to(afr_nota, DOWN, buff=0.5).align_to(afr_eq, LEFT)
        self.play(FadeIn(afr_conclusion, shift=UP * 0.15), run_time=1.3)
        self.wait(2.0)
        self.play(FadeOut(afr_txt), FadeOut(afr_eq), FadeOut(afr_nota), FadeOut(afr_conclusion), run_time=1.3)
        self.next_slide()

        # =================================================================
        # Eficiencia volumetrica
        # =================================================================
        etav_txt = VGroup(
            Tex(r"La eficiencia volumetrica mide cuanta mezcla", font_size=27),
            Tex(r"realmente llena el cilindro:", font_size=27),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.18).to_edge(LEFT).shift(UP * 1.6)
        etav_eq = MathTex(
            r"\eta_v", "=", r"\frac{m_{air,real}}{\rho_{air}\cdot V_d}"
        ).scale(1.2).next_to(etav_txt, DOWN, buff=0.5).align_to(etav_txt, LEFT)
        etav_nota = Tex(
            r"\footnotesize Tipicamente entre 0,70 y 0,95 en motores atmosfericos.",
            font_size=22, color=GRAY_D,
        ).next_to(etav_eq, DOWN, buff=0.35).align_to(etav_eq, LEFT)

        self.play(FadeIn(etav_txt, shift=RIGHT * 0.2), run_time=1.3)
        self.play(Write(etav_eq), run_time=1.4)
        self.play(FadeIn(etav_nota, shift=UP * 0.1), run_time=1.3)
        self.wait(2.3)
        self.play(FadeOut(etav_txt), FadeOut(etav_eq), FadeOut(etav_nota), run_time=1.3)
        self.next_slide()

        # =================================================================
        # Paso 1: ecuacion de gases ideales -> densidad del aire
        # =================================================================
        paso1_txt = Tex(
            "1. Ecuacion de los gases ideales, forma de densidad:", font_size=27,
        ).to_edge(LEFT).shift(UP * 1.6)

        gas_ideal = MathTex("P", "=", r"\rho", "R", "T").scale(1.2).next_to(
            paso1_txt, DOWN, buff=0.6
        ).align_to(paso1_txt, LEFT)
        self.play(FadeIn(paso1_txt, shift=RIGHT * 0.2), run_time=1.3)
        self.play(Write(gas_ideal), run_time=1.4)
        self.wait(1.3)

        rho_despejada = MathTex(
            r"\rho_{air}", "=", r"\frac{\mathrm{MAP}}{R_{air}\cdot \mathrm{IAT}}"
        ).scale(1.2).move_to(gas_ideal).align_to(gas_ideal, LEFT)
        self.play(TransformMatchingShapes(gas_ideal, rho_despejada), run_time=1.4)
        self.wait(0.7)

        nota1 = Tex(
            r"\footnotesize MAP en Pa, IAT en K, $R_{air}=287$ J/(kg$\cdot$K)",
            font_size=21, color=GRAY_D,
        ).next_to(rho_despejada, DOWN, buff=0.5).align_to(rho_despejada, LEFT)
        self.play(FadeIn(nota1, shift=UP * 0.15), run_time=1.3)
        self.wait(1.6)

        self.play(FadeOut(paso1_txt), FadeOut(nota1), run_time=1.3)
        self.play(rho_despejada.animate.to_edge(LEFT).set_y(1.6), run_time=1.3)
        self.next_slide()

        # =================================================================
        # Paso 2: ciclos de admision -> zoom in situ al piston-biela-
        # ciguenal, luego se agranda de vuelta y se ve por que el factor
        # es 2 (sin mover la camara de la escena).
        # =================================================================
        paso2_txt = Tex(
            "2. Ciclos de admision por segundo:", font_size=27,
        ).next_to(rho_despejada, DOWN, buff=0.75).to_edge(LEFT)
        self.play(FadeIn(paso2_txt, shift=RIGHT * 0.2), run_time=1.3)

        crank_state = zoom_in(eng["crank_point"], CRANK_ZOOM, run_time=2.6)
        self.wait(1.7)

        # Se detiene el giro "de fondo" y se sincroniza a un multiplo
        # limpio de 4*PI (una vuelta completa de admision) antes de la
        # demostracion controlada.
        theta.clear_updaters()
        current = theta.get_value()
        target0 = np.ceil(current / (4 * PI)) * (4 * PI)
        if target0 - current < 0.5:
            target0 += 4 * PI
        if target0 > current:
            self.play(
                theta.animate.set_value(target0),
                run_time=max(0.8, (target0 - current) / (4 * PI) * 6.5),
                rate_func=linear,
            )

        # Se vuelve al tamano normal del motor, donde se ve completo
        # junto con el texto.
        zoom_out(crank_state, run_time=2.1)

        panel_rows = VGroup()
        for k, nom in enumerate(NOMBRES_TIEMPO):
            cuadro = Square(0.22, stroke_width=0).set_fill(COLORES_TIEMPO[k], 0.25)
            txt = Tex(nom, font_size=22, color=GRAY_C)
            panel_rows.add(VGroup(cuadro, txt).arrange(RIGHT, buff=0.18))
        panel_rows.arrange(DOWN, aligned_edge=LEFT, buff=0.15)
        panel_rows.next_to(paso2_txt, DOWN, buff=0.55).align_to(paso2_txt, LEFT)

        def update_panel(mob):
            i, _ = fase(theta.get_value())
            for k in range(4):
                cuadro, txt = mob[k]
                cuadro.set_fill(opacity=1 if k == i else 0.25)
                txt.set_color(UMSA_BLUE if k == i else GRAY_C)

        panel_rows.add_updater(update_panel)

        vuelta_1 = Tex("Vuelta 1 / 2", font_size=22, color=GRAY_D)
        vuelta_2 = Tex("Vuelta 2 / 2", font_size=22, color=GRAY_D)
        vuelta_2.move_to(vuelta_1)
        vuelta_2.set_opacity(0)
        vuelta_group = VGroup(vuelta_1, vuelta_2).next_to(panel_rows, DOWN, buff=0.3).align_to(
            panel_rows, LEFT
        )

        def update_vuelta(mob):
            v1, v2 = mob
            prog = theta.get_value() - target0
            if prog < 2 * PI:
                v1.set_opacity(1)
                v2.set_opacity(0)
            else:
                v1.set_opacity(0)
                v2.set_opacity(1)

        vuelta_group.add_updater(update_vuelta)

        self.play(FadeIn(panel_rows), FadeIn(vuelta_group), run_time=1.3)
        self.play(theta.animate.set_value(target0 + 4 * PI), run_time=7.5, rate_func=linear)
        self.wait(0.4)

        panel_rows.clear_updaters()
        vuelta_group.clear_updaters()

        conclusion_giro = Tex(
            r"2 vueltas completas del ciguenal $\Rightarrow$ 1 admision",
            font_size=24, color=UMSA_BLUE,
        ).next_to(vuelta_group, DOWN, buff=0.35).align_to(panel_rows, LEFT)
        self.play(FadeIn(conclusion_giro, shift=UP * 0.1), run_time=1.3)
        self.wait(1.7)
        self.play(FadeOut(panel_rows), FadeOut(vuelta_group), FadeOut(conclusion_giro), run_time=1.3)

        ciclos_a = MathTex(
            r"n_{ciclos}", "=", r"\frac{\mathrm{RPM}}{2}", r"\cdot", r"\frac{1}{60}"
        ).scale(1.1).next_to(paso2_txt, DOWN, buff=0.5).align_to(paso2_txt, LEFT)
        self.play(Write(ciclos_a), run_time=1.4)
        self.play(Circumscribe(ciclos_a[2][-1], color=UMSA_GOLD, fade_out=True), run_time=1.4)
        self.wait(1.1)

        ciclos_b = MathTex(
            r"n_{ciclos}", "=", r"\frac{\mathrm{RPM}}{2}", r"\cdot", r"\frac{1}{60}",
            "=", r"\frac{\mathrm{RPM}}{120}",
        ).scale(1.1).move_to(ciclos_a).align_to(ciclos_a, LEFT)
        self.play(TransformMatchingTex(ciclos_a, ciclos_b), run_time=1.4)
        self.wait(0.7)

        nota2 = Tex(
            r"\footnotesize factor $120 = 2$ (una admision cada 2 vueltas) "
            r"$\times\,60$ (min $\to$ s). Aplicar \textbf{una sola vez}.",
            font_size=19, color=GRAY_D,
        ).next_to(ciclos_b, DOWN, buff=0.4).align_to(ciclos_b, LEFT)
        self.play(FadeIn(nota2, shift=UP * 0.15), run_time=1.3)
        self.wait(2.0)

        self.play(FadeOut(paso2_txt), FadeOut(nota2), run_time=1.3)
        self.play(ciclos_b.animate.scale(0.9).next_to(rho_despejada, DOWN, buff=0.7).to_edge(LEFT), run_time=1.3)

        # El motor sigue "funcionando" de fondo durante el resto del algebra.
        theta.add_updater(lambda m, dt: m.increment_value(dt * 0.9))
        self.add(theta)
        self.next_slide()

        # =================================================================
        # Paso 3: combinar densidad, cilindrada, ciclos y eficiencia
        # =================================================================
        paso3_txt = Tex(
            r"3. Masa de aire por ciclo $= \rho_{air}\cdot V_d$, corregida por "
            r"$\eta_v$:",
            font_size=25,
        ).next_to(ciclos_b, DOWN, buff=0.9).to_edge(LEFT)

        mdot_1 = MathTex(
            r"\dot m_{air}", "=", r"\eta_v", r"\cdot", r"\rho_{air}", r"\cdot",
            "V_d", r"\cdot", r"\frac{\mathrm{RPM}}{120}",
        ).scale(1.0).next_to(paso3_txt, DOWN, buff=0.5).to_edge(LEFT)

        self.play(FadeIn(paso3_txt, shift=RIGHT * 0.2), run_time=1.3)
        self.play(Write(mdot_1), run_time=1.6)
        self.wait(2.0)

        # =================================================================
        # Paso 4: sustituir rho_air -> ecuacion final
        # =================================================================
        self.play(FadeOut(paso3_txt), FadeOut(rho_despejada), FadeOut(ciclos_b), run_time=1.3)
        self.play(mdot_1.animate.scale(1.1).to_edge(LEFT).shift(UP * 0.8), run_time=1.3)

        paso4_txt = Tex(
            r"4. Sustituyendo $\rho_{air}=\dfrac{\mathrm{MAP}}{R_{air}\cdot \mathrm{IAT}}$:",
            font_size=25,
        ).next_to(mdot_1, DOWN, buff=0.6).to_edge(LEFT)
        self.play(FadeIn(paso4_txt, shift=UP * 0.15), run_time=1.3)
        self.wait(1.3)

        mdot_final = MathTex(
            r"\dot m_{air}", "=", r"\eta_v", r"\cdot",
            r"\frac{\mathrm{MAP}}{R_{air}\cdot \mathrm{IAT}}", r"\cdot",
            "V_d", r"\cdot", r"\frac{\mathrm{RPM}}{120}",
        ).scale(0.85)
        mdot_final.move_to(mdot_1).align_to(mdot_1, LEFT)

        self.play(FadeOut(paso4_txt), run_time=1.3)
        self.play(TransformMatchingTex(mdot_1, mdot_final), run_time=1.5)
        self.wait(0.7)

        etiqueta_caja = Tex(
            r"\footnotesize Ecuacion mas importante del modelo de estimacion",
            font_size=22, color=UMSA_BLUE,
        )
        caja = SurroundingRectangle(mdot_final, color=BLACK, fill_color=GRAY_B,
                                     fill_opacity=0.12, buff=0.35)
        etiqueta_caja.next_to(caja, UP, buff=0.2)

        self.play(Create(caja), FadeIn(etiqueta_caja, shift=DOWN * 0.1), run_time=1.4)
        self.wait(1.3)

        # Aqui se retira el motor: a partir de ahora, solo la ecuacion.
        theta.clear_updaters()
        self.play(FadeOut(eng["fixed"]), FadeOut(eng["moving"]), run_time=1.4)

        # Ahora que el motor ya no esta, se recentra la ecuacion.
        grupo_final = VGroup(mdot_final, caja, etiqueta_caja)
        self.play(grupo_final.animate.move_to(UP * 0.8), run_time=1.3)
        self.wait(0.4)

        # =================================================================
        # Paso 5: leyenda de variables
        # =================================================================
        leyenda = VGroup(
            Tex(r"$\rho_{air}$: densidad del aire [kg/m$^3$]", font_size=22),
            Tex(r"$V_d$: cilindrada total [m$^3$]", font_size=22),
            Tex(r"$\mathrm{MAP}$: presion del multiple [Pa] (0x0B)", font_size=22),
            Tex(r"$\eta_v$: eficiencia volumetrica [adim.]", font_size=22),
            Tex(r"$\mathrm{IAT}$: temperatura de admision [K] (0x0F)", font_size=22),
            Tex(r"$\mathrm{RPM}$: regimen del motor [rev/min] (0x0C)", font_size=22),
        )
        leyenda.arrange_in_grid(rows=3, cols=2, buff=(0.9, 0.3), cell_alignment=LEFT)
        leyenda.next_to(VGroup(caja, etiqueta_caja), DOWN, buff=0.5)

        self.play(LaggedStart(*[FadeIn(l, shift=RIGHT * 0.15) for l in leyenda], lag_ratio=0.15), run_time=1.8)
        self.wait(1.5)
        self.next_slide()

        # =================================================================
        # Cierre
        # =================================================================
        self.play(
            FadeOut(leyenda), FadeOut(caja), FadeOut(etiqueta_caja), FadeOut(mdot_final),
            run_time=1.4,
        )

        cierre = Tex(
            r"Con $\dot m_{air}$ estimado, el flujo de combustible y el consumo\\"
            r"se calculan igual que en el metodo MAF "
            r"(mismas ecuaciones aguas abajo).",
            font_size=30, color=UMSA_BLUE,
        ).move_to(ORIGIN)

        self.play(Write(cierre), run_time=1.8)
        self.wait(3.2)
        self.play(FadeOut(cierre), FadeOut(titulo), FadeOut(subtitulo), FadeOut(linea), run_time=1.4)
        self.wait(0.6)
        self.next_slide()
