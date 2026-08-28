#!/usr/bin/env python3
"""
Refinamiento INDIRECTO de la curva de eficiencia volumetrica (VE) para
vehiculos SIN PID 0x10 (MAF) -- caso del Changan Honor. Documentado en
el Capitulo 3, Diseno de software, subseccion "Caso sin MAF: el Changan
Honor" (dentro de la Seccion "Calculo general de la eficiencia
volumetrica").

DIFERENCIA DE FONDO con ve_curve_calibrator.py (que SI requiere MAF):
    Aquel invierte la ecuacion de speed-density y despeja la VE de forma
    DIRECTA y ABSOLUTA a partir de un flujo de aire real (PID 0x10) --
    no necesita saber nada de antemano sobre la VE del motor.

    Este script NO tiene ninguna referencia real de flujo de aire para
    el Changan (no soporta 0x10). En su lugar usa el ajuste de mezcla
    que la propia ECU ya reporta -- STFT (PID 0x06) y LTFT (PID 0x07),
    confirmados soportados en el Changan segun Apendice O /
    DATASHEET/CHANGAN.pdf -- como señal INDIRECTA y RELATIVA de que la
    VE asumida esta mal: si el ECU esta añadiendo combustible de forma
    sostenida en cierto regimen (STFT+LTFT > 0), es porque el modelo
    (con la VE que se le dio) esta subestimando el aire admitido ahi, y
    viceversa. Es la misma logica del Algoritmo de identificacion de la
    curva eta_v(N) del lazo cerrado (Capitulo 3, alg:etav), aplicada
    aqui de forma offline en vez de en linea dentro del firmware:

        eta_v_estimada(N) = eta_v_semilla(N) * (1 + (STFT% + LTFT%) / 100)

    Esta corriente algebraica NO involucra la cilindrada, el MAP ni el
    IAT -- es un ajuste multiplicativo relativo, no una inversion de la
    ecuacion de gas ideal. Por eso este script no pide Vd como
    parametro.

ADVERTENCIA EPISTEMOLOGICA (leer antes de usar los resultados):
    Este metodo NO calibra la VE del Changan desde cero -- la CORRIGE a
    partir de una curva semilla asumida (por defecto, la misma curva
    generica de literatura con la que arranco este proyecto antes de
    calibrar la del Vanette). Si la curva semilla esta muy alejada de la
    realidad de este motor en particular, la correccion multiplicativa
    tambien lo estara: no hay forma de saber, sin una referencia real de
    aire o combustible, si el resultado final es correcto en terminos
    absolutos -- solo que es *mas consistente* con los STFT/LTFT
    observados que la curva semilla de partida. A diferencia de la curva
    del Vanette (Figura ve_curve_fit_vanette.png), esta NO debe
    reportarse como "calibrada" sino como "refinada a partir de una
    curva semilla generica".

    Ademas, solo se aceptan muestras con el motor en lazo cerrado
    (lambda comandado, PID 0x44, cercano a 1) -- fuera de esa condicion
    el ECU esta enriqueciendo deliberadamente y el STFT/LTFT no reflejan
    un error de VE, sino una estrategia distinta de la ECU.

Uso:
    python ve_curve_calibrator_indirect.py <csv> [--bin-width 250]
                                            [--min-samples 5]
                                            [--lambda-tol 0.05]
                                            [--vehiculo "Nombre"]

    <csv>: columnas rpm, stft_pct, ltft_pct, lambda_cmd (formato de
    changan_trim_logger.py).

Requisitos:
    pip install numpy matplotlib
"""
import argparse
import csv

# Curva semilla generica (misma tabla de literatura con la que arranco
# el proyecto, antes de calibrar la del Vanette con datos reales) --
# punto de partida documentado, no un dato de este motor en particular.
SEED_VE_TABLE = [
    (700,  60.0),
    (1500, 74.0),
    (2500, 85.0),
    (4000, 88.0),
    (5500, 83.0),
    (7000, 74.0),
]


def seed_ve_for_rpm(rpm, table=SEED_VE_TABLE):
    if rpm <= table[0][0]:
        return table[0][1]
    if rpm >= table[-1][0]:
        return table[-1][1]
    for (rpm_a, ve_a), (rpm_b, ve_b) in zip(table, table[1:]):
        if rpm_a <= rpm <= rpm_b:
            t = (rpm - rpm_a) / (rpm_b - rpm_a)
            return ve_a + t * (ve_b - ve_a)
    return table[-1][1]


def load_samples(csv_path, lambda_tol):
    samples = []       # (rpm, ve_estimada) -- aceptadas (lazo cerrado)
    rejected_n = 0      # descartadas por enriquecimiento (lambda lejos de 1)
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            try:
                rpm = float(row["rpm"])
                stft = float(row["stft_pct"])
                ltft = float(row["ltft_pct"])
                lambda_cmd = float(row["lambda_cmd"])
            except (KeyError, ValueError):
                continue
            if abs(lambda_cmd - 1.0) > lambda_tol:
                rejected_n += 1
                continue
            ve_seed = seed_ve_for_rpm(rpm)
            ve_est = ve_seed * (1.0 + (stft + ltft) / 100.0)
            if ve_est > 0:
                samples.append((rpm, ve_est))
    return samples, rejected_n


def bin_samples(samples, bin_width, min_samples):
    bins = {}
    for rpm, ve in samples:
        k = int(rpm // bin_width)
        bins.setdefault(k, []).append((rpm, ve))

    confident, low_confidence = [], []
    for k in sorted(bins):
        pts = bins[k]
        n = len(pts)
        rpm_center = sum(p[0] for p in pts) / n
        ve_avg = sum(p[1] for p in pts) / n
        entry = (rpm_center, ve_avg, n)
        (confident if n >= min_samples else low_confidence).append(entry)
    return confident, low_confidence


def fit_cubic(confident):
    import numpy as np
    rpms = np.array([p[0] for p in confident])
    ves = np.array([p[1] for p in confident])
    weights = np.array([p[2] for p in confident])
    coeffs = np.polyfit(rpms, ves, deg=3, w=weights)
    fitted = np.polyval(coeffs, rpms)
    ss_res = float(np.sum(weights * (ves - fitted) ** 2))
    ss_tot = float(np.sum(weights * (ves - np.average(ves, weights=weights)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    c3, c2, c1, c0 = coeffs
    return (c0, c1, c2, c3), r2


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv_path", help="CSV con columnas rpm, stft_pct, ltft_pct, lambda_cmd")
    ap.add_argument("--bin-width", type=float, default=250.0)
    ap.add_argument("--min-samples", type=int, default=5)
    ap.add_argument("--lambda-tol", type=float, default=0.05,
                     help="tolerancia |lambda_cmd - 1| para aceptar la muestra (lazo cerrado)")
    ap.add_argument("--vehiculo", default="Changan Honor")
    args = ap.parse_args()

    samples, rejected_n = load_samples(args.csv_path, args.lambda_tol)
    print(f"Muestras aceptadas (lazo cerrado, |lambda-1|<={args.lambda_tol}): {len(samples)}")
    print(f"Muestras descartadas (enriquecimiento/empobrecimiento): {rejected_n}")

    if not samples:
        print("Sin muestras validas, no se puede refinar la curva.")
        return

    confident, low_confidence = bin_samples(samples, args.bin_width, args.min_samples)

    print("\n================================================")
    print(f"VE refinada por bin (curva semilla generica + STFT/LTFT)")
    print("================================================")
    for rpm_c, ve_avg, n in confident:
        ve_seed = seed_ve_for_rpm(rpm_c)
        print(f"  rpm~{rpm_c:7.1f}  VE_semilla={ve_seed:5.1f}%  VE_refinada={ve_avg:5.1f}%  (n={n})")

    if low_confidence:
        print("\nBins de baja confianza (excluidos):")
        for rpm_c, ve_avg, n in low_confidence:
            print(f"  rpm~{rpm_c:7.1f}  VE_refinada={ve_avg:5.1f}%  (n={n} < {args.min_samples})")

    if len(confident) < 4:
        print(f"\nSe necesitan al menos 4 bins de confianza para el ajuste cubico "
              f"(hay {len(confident)}). Recolecta mas datos.")
        return

    (c0, c1, c2, c3), r2 = fit_cubic(confident)
    print("\n================================================")
    print("Curva refinada: eta_v(N) = c0 + c1*N + c2*N^2 + c3*N^3")
    print("(RELATIVA a la curva semilla generica -- ver advertencia en el docstring)")
    print("================================================")
    print(f"  c0 = {c0:.6e}")
    print(f"  c1 = {c1:.6e}")
    print(f"  c2 = {c2:.6e}")
    print(f"  c3 = {c3:.6e}")
    print(f"  R^2 = {r2:.4f}")

    plot_curve(confident, low_confidence, (c0, c1, c2, c3), args.vehiculo)


def plot_curve(confident, low_confidence, coeffs, vehiculo):
    try:
        import matplotlib.pyplot as plt
    except ModuleNotFoundError:
        print("\nFalta matplotlib para graficar. Instala con: pip install matplotlib")
        return

    c0, c1, c2, c3 = coeffs
    color_points = "#2a78d6"
    color_seed = "#898781"
    color_curve = "#eb6834"
    color_low = "#898781"
    color_grid = "#e1e0d9"
    color_ink = "#0b0b0b"
    color_muted = "#52514e"

    fig, ax = plt.subplots(figsize=(7, 4.5), dpi=150)
    fig.patch.set_facecolor("#fcfcfb")
    ax.set_facecolor("#fcfcfb")

    all_pts = confident + low_confidence
    rpm_min = min(p[0] for p in all_pts)
    rpm_max = max(p[0] for p in all_pts)

    xs_seed = [rpm_min + i * (rpm_max - rpm_min) / 100.0 for i in range(101)]
    ys_seed = [seed_ve_for_rpm(x) for x in xs_seed]
    ax.plot(xs_seed, ys_seed, color=color_seed, linewidth=1.5, linestyle="--",
            label="Curva semilla (genérica)", zorder=2)

    xs = [p[0] for p in confident]
    ys = [p[1] for p in confident]
    ns = [p[2] for p in confident]
    ax.scatter(xs, ys, s=[20 + 4 * n for n in ns], color=color_points,
               label="VE refinada por bin (tamaño = n muestras)", zorder=3)

    if low_confidence:
        xs_lo = [p[0] for p in low_confidence]
        ys_lo = [p[1] for p in low_confidence]
        ax.scatter(xs_lo, ys_lo, s=20, color=color_low, marker="x",
                   label="Baja confianza (excluido)", zorder=2)

    xs_fit = [rpm_min + i * (rpm_max - rpm_min) / 200.0 for i in range(201)]
    ys_fit = [c0 + c1 * x + c2 * x ** 2 + c3 * x ** 3 for x in xs_fit]
    ax.plot(xs_fit, ys_fit, color=color_curve, linewidth=2,
            label="Ajuste cúbico refinado", zorder=4)

    ax.set_xlabel("RPM", color=color_ink)
    ax.set_ylabel("Eficiencia volumétrica VE (%)", color=color_ink)
    ax.set_title(f"VE refinada vía STFT/LTFT, curva semilla genérica ({vehiculo})",
                 color=color_ink, fontsize=10)

    ax.grid(color=color_grid, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color(color_muted)
    ax.spines["left"].set_color(color_muted)
    ax.tick_params(colors=color_muted)
    ax.legend(frameon=False, loc="best", fontsize=8, labelcolor=color_ink)

    fig.tight_layout()
    png_path = "ve_curve_fit_indirect.png"
    fig.savefig(png_path, facecolor=fig.get_facecolor())
    print(f"\nGrafica guardada: {png_path}")


if __name__ == "__main__":
    main()
