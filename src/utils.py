# -*- coding: utf-8 -*-
"""Gráfico de covariación de índices de saturación (por defecto, calcita frente a yeso) (ADR-003).

Lee el CSV del motor (``data/processed/resultados_universales_phreeqc.csv``, columnas ``si_<Fase>``) y escribe
un gráfico por proyecto en ``reports/figures/<x>_vs_<y>_<Proyecto>.png``. Cada área del proyecto lleva su marcador.
Las muestras sin alguno de los dos IS se omiten y se informan.

Uso::

    python src/utils.py
    python src/utils.py --proyecto Puna_Norte
    python src/utils.py --x Calcite --y Anhydrite --csv otra_salida.csv --outdir otra_carpeta
"""
import argparse
import os

import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_PATH = os.path.join(BASE_DIR, "data", "processed", "resultados_universales_phreeqc.csv")
FIGURES_DIR = os.path.join(BASE_DIR, "reports", "figures")

#: Nombre en español de las fases más usadas (para títulos y ejes).
PHASE_LABELS = {"Calcite": "Calcita", "Gypsum": "Yeso", "Anhydrite": "Anhidrita", "Chalcedony": "Calcedonia",
                "Quartz": "Cuarzo", "Aragonite": "Aragonito", "Barite": "Baritina", "Fluorite": "Fluorita"}
MARKERS = ["o", "s", "^", "D", "v", "*", "p", "X"]
COLORS = ["#e74c3c", "#3498db", "#2ecc71", "#9b59b6", "#f1c40f", "#1abc9c", "#e67e22", "#34495e"]


def load_results(csv_path=INPUT_PATH):
    """Lee el CSV de resultados del motor.

    Raises
    ------
    FileNotFoundError
        Si el CSV no existe (hay que correr antes ``src/engine.py``).
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(
            f"No se encontró el archivo de resultados: {csv_path}. Ejecuta primero 'python src/engine.py'."
        )
    return pd.read_csv(csv_path)


def si_column(df, phase):
    """Columna ``si_<Fase>`` del CSV (sin distinguir mayúsculas).

    Raises
    ------
    KeyError
        Si la fase no está en el CSV, con la lista de fases disponibles.
    """
    target = f"si_{phase}".lower()
    for col in df.columns:
        if col.lower() == target:
            return col
    available = sorted(c[3:] for c in df.columns if c.lower().startswith("si_") and not c.endswith("_Ref"))
    raise KeyError(f"El CSV no tiene la columna si_{phase}. Fases disponibles: {', '.join(available)}")


def plot_si_covariation(df, x_phase="Calcite", y_phase="Gypsum", title=None, output_path=None):
    """Grafica IS de ``y_phase`` frente a IS de ``x_phase``, con un marcador por área.

    Parameters
    ----------
    df : pandas.DataFrame
        Filas del CSV del motor (un solo proyecto, idealmente).
    x_phase, y_phase : str
        Fases de PHREEQC (``si_<Fase>`` en el CSV).
    title : str, optional
        Título del gráfico.
    output_path : str
        Ruta del PNG.

    Returns
    -------
    dict
        ``path`` (PNG escrito o None si no hay puntos), ``plotted`` (muestras graficadas) y ``skipped``
        (muestras sin alguno de los dos IS).
    """
    import matplotlib

    matplotlib.use("Agg")  # sin ventana: funciona en servidores y en pruebas
    import matplotlib.pyplot as plt

    x_col, y_col = si_column(df, x_phase), si_column(df, y_phase)
    valid = df[x_col].notna() & df[y_col].notna()
    skipped = df.loc[~valid, "Muestra"].astype(str).tolist() if "Muestra" in df else []
    data = df[valid]
    if data.empty:
        return {"path": None, "plotted": 0, "skipped": skipped}

    x_name, y_name = PHASE_LABELS.get(x_phase, x_phase), PHASE_LABELS.get(y_phase, y_phase)
    fig, ax = plt.subplots(figsize=(10, 7))
    areas = data["Area"].fillna("sin área").astype(str) if "Area" in data else pd.Series("—", index=data.index)
    for idx, area in enumerate(dict.fromkeys(areas)):
        sub = data[areas == area]
        ax.scatter(sub[x_col], sub[y_col], label=f"Zona {area}", s=120, edgecolors="black", linewidths=1.2,
                   alpha=0.85, marker=MARKERS[idx % len(MARKERS)], color=COLORS[idx % len(COLORS)])

    ax.axhline(0, color="#2c3e50", linestyle="--", linewidth=1.5, label=f"Equilibrio {y_name.lower()}")
    ax.axvline(0, color="#d35400", linestyle="--", linewidth=1.5, label=f"Equilibrio {x_name.lower()}")
    # Los cuatro cuadrantes siempre visibles: los límites incluyen el 0 con margen en ambos ejes.
    (x0, x1), (y0, y1) = ax.get_xlim(), ax.get_ylim()
    span = max(x1 - x0, y1 - y0, 1.0)
    x0, x1 = min(x0, -0.15 * span), max(x1, 0.15 * span)
    y0, y1 = min(y0, -0.15 * span), max(y1, 0.15 * span)
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    box = {"facecolor": "white", "alpha": 0.7, "edgecolor": "none"}
    pad_x, pad_y = 0.02 * (x1 - x0), 0.02 * (y1 - y0)
    ax.text(x1 - pad_x, y1 - pad_y, "Sobresaturado en ambos", ha="right", va="top", fontsize=10,
            color="green", weight="bold", bbox=box)
    ax.text(x0 + pad_x, y0 + pad_y, "Subsaturado en ambos", ha="left", va="bottom", fontsize=10,
            color="red", weight="bold", bbox=box)
    ax.grid(True, alpha=0.3)
    ax.set_title(title or f"Índices de saturación: {x_name} frente a {y_name}", fontsize=14, weight="bold", pad=15)
    ax.set_xlabel(f"IS de {x_name} [log(IAP/K)]", fontsize=12)
    ax.set_ylabel(f"IS de {y_name} [log(IAP/K)]", fontsize=12)
    ax.legend(loc="lower right", frameon=True, facecolor="white", edgecolor="gray")
    fig.tight_layout()
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    fig.savefig(output_path, dpi=300)
    plt.close(fig)
    return {"path": output_path, "plotted": int(valid.sum()), "skipped": skipped}


def generate_saturation_index_plots(csv_path=INPUT_PATH, outdir=FIGURES_DIR, x_phase="Calcite",
                                    y_phase="Gypsum", proyecto=None):
    """Un gráfico por proyecto (o solo ``proyecto``) a partir del CSV del motor.

    Returns
    -------
    dict
        {proyecto: resultado de ``plot_si_covariation``}.
    """
    df = load_results(csv_path)
    si_column(df, x_phase), si_column(df, y_phase)  # falla temprano si falta una fase
    projects = df["Proyecto"].astype(str) if "Proyecto" in df else pd.Series("todos", index=df.index)
    names = [proyecto] if proyecto else list(dict.fromkeys(projects))
    results = {}
    for name in names:
        sub = df[projects == name]
        if sub.empty:
            raise ValueError(f"No hay filas del proyecto {name!r} en {csv_path}")
        path = os.path.join(outdir, f"{x_phase}_vs_{y_phase}_{name}.png".replace("/", "-"))
        res = plot_si_covariation(sub, x_phase, y_phase, output_path=path,
                                  title=f"{PHASE_LABELS.get(x_phase, x_phase)} frente a "
                                        f"{PHASE_LABELS.get(y_phase, y_phase)}: {name.replace('_', ' ')}")
        results[name] = res
        if res["path"]:
            print(f"[+] {name}: {res['plotted']} muestras -> {res['path']}")
        else:
            print(f"[!] {name}: ninguna muestra tiene los dos IS; no se genera gráfico.")
        if res["skipped"]:
            shown = ", ".join(res["skipped"][:8]) + (" ..." if len(res["skipped"]) > 8 else "")
            print(f"    {len(res['skipped'])} muestra(s) sin IS de {x_phase} o {y_phase}: {shown}")
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description="Gráfico de covariación de IS por proyecto")
    parser.add_argument("--csv", default=INPUT_PATH, help="CSV de resultados del motor")
    parser.add_argument("--outdir", default=FIGURES_DIR, help="carpeta de los PNG")
    parser.add_argument("--x", default="Calcite", help="fase del eje x (nombre de PHREEQC)")
    parser.add_argument("--y", default="Gypsum", help="fase del eje y (nombre de PHREEQC)")
    parser.add_argument("--proyecto", default=None, help="solo este proyecto")
    args = parser.parse_args(argv)
    generate_saturation_index_plots(args.csv, args.outdir, args.x, args.y, args.proyecto)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
