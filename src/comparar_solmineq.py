# -*- coding: utf-8 -*-
"""
Caso de comparación PHREEQC (wateq4f.dat / llnl.dat) frente a SOLMINEQ-Py (solmineq_app).

Corre las mismas muestras de la plantilla en los dos programas, con las mismas entradas y condiciones,
y compara pH, fuerza iónica, especies clave (molalidad, gamma, actividad) e índices de saturación (IS).

Escenarios
----------
A_superficie
    T de la muestra, pH medido y carbono como DIC (``C(4) as HCO3`` en PHREEQC, ``dic_mol_kg`` en
    SOLMINEQ-Py). Los dos programas reciben exactamente la misma entrada.
B_profundo
    PHREEQC reequilibra la solución con CO2(g) a la P_CO2 de la plantilla (como ``engine.py``). El pH y
    el carbono total que resultan con wateq4f.dat se pasan a SOLMINEQ-Py, que no tiene esa opción.
    Así los IS de los dos programas se comparan en las mismas condiciones y contra la referencia
    publicada (columnas ``si_<Fase>_Ref`` de la plantilla). Las muestras sin P_CO2 (en la Puna Norte:
    ACF, LC y PA2, sin gases en la Tabla 6-5) no tienen escenario B.

Además compara los geotermómetros de SOLMINEQ-Py con las columnas ``T_*_Ref`` de la plantilla (ADR-002).

Entradas comunes (y solo esas)
------------------------------
SOLMINEQ-Py especia Ca, Mg, Na, K, SO4, Cl, F, SiO2, Fe(II) y el carbonato; Zn, Pb, Cu y H2S entran
solo en los IS de sulfuros. PHREEQC recibe el mismo conjunto, para que las diferencias vengan del
motor y de la base termodinámica, no de solutos distintos. El Fe se declara como Fe(2) y el Cu como
Cu(2), igual que los trata SOLMINEQ-Py; el S(-2) de la plantilla se interpreta como H2S total.

Uso
---
    python src/comparar_solmineq.py                       # Puna_Norte, plantilla por defecto
    python src/comparar_solmineq.py --proyecto Puna_Norte --output reports/Comparacion.xlsx

Requiere solmineq_app instalado en el mismo entorno, por ejemplo:
    pip install -e H:\\Phyton\\SOLMINEQ
"""
from __future__ import annotations

import argparse
import math
import os
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from phreeqpy.iphreeqc.phreeqc_dll import IPhreeqc

from engine import BASE_DIR, DEFAULT_TEMPLATE, ensure_database

DEFAULT_OUTPUT = os.path.join(BASE_DIR, "reports", "Comparacion_PHREEQC_SOLMINEQ.xlsx")
BASES = ("wateq4f.dat", "llnl.dat")
BASE_PROFUNDO = "wateq4f.dat"  # base que fija el pH y el DIC del escenario B para SOLMINEQ-Py
PE = 4.0

# Columna de la plantilla -> (nombre PHREEQC, sufijo "as", clave SOLMINEQ-Py, factor a mg/L)
MAJORS = [
    ("Ca_mgL", "Ca", "", "Ca"),
    ("Mg_mgL", "Mg", "", "Mg"),
    ("Na_mgL", "Na", "", "Na"),
    ("K_mgL", "K", "", "K"),
    ("SO4_mgL", "S(6)", "as SO4", "SO4"),
    ("Cl_mgL", "Cl", "", "Cl"),
    ("F_mgL", "F", "", "F"),
    ("SiO2_mgL", "Si", "as SiO2", "SiO2"),
]
TRACES = [  # columnas *_traza, escaladas con Escala_Trazas
    ("Fe_traza", "Fe(2)", "Fe"),
    ("Zn_traza", "Zn", "Zn"),
    ("Pb_traza", "Pb", "Pb"),
    ("Cu_traza", "Cu(2)", "Cu"),
]

# Mineral -> (fase wateq4f, fase llnl, columna SOLMINEQ-Py). La referencia publicada, si existe, está en la
# columna ``si_<fase llnl>_Ref`` de la plantilla.
MINERALS = {
    "Calcita": ("Calcite", "Calcite", "SI_Calcita"),
    "Aragonito": ("Aragonite", "Aragonite", "SI_Aragonita"),
    "Anhidrita": ("Anhydrite", "Anhydrite", "SI_Anhidrita"),
    "Yeso": ("Gypsum", "Gypsum", None),
    "Cuarzo": ("Quartz", "Quartz", "SI_Cuarzo"),
    "Calcedonia": ("Chalcedony", "Chalcedony", "SI_Calcedonia"),
    "Silice_amorfa": ("SiO2(a)", "SiO2(am)", "SI_Silica_Amorfa"),
    "Halita": ("Halite", "Halite", "SI_Halita"),
    "Fluorita": ("Fluorite", "Fluorite", None),
    "Esfalerita": ("Sphalerite", "Sphalerite", "SI_Esfalerita"),
    "Galena": ("Galena", "Galena", "SI_Galena"),
    "Pirrotita": (None, "Pyrrhotite", "SI_Pirrotita"),
    "Pirita": ("Pyrite", "Pyrite", "SI_Pirita"),
    "Calcopirita": ("Chalcopyrite", "Chalcopyrite", "SI_Calcopirita"),
}

# Geotermómetro -> (función, columna de referencia). SOLMINEQ-Py no tiene la calcedonia de Arnórsson (1983):
# se calcula aquí con su ecuación y se marca en el reporte.
GEOTHERMOMETERS = {
    "Calcedonia (Arnórsson 1983) [ecuación del script]": (
        lambda c: 1112.0 / (4.91 - math.log10(c["SiO2"])) - 273.15, "T_Calcedonia_Arnorsson1983_Ref"),
    "Cuarzo conductivo (Fournier 1977)": (
        lambda c: _geo().quartz_no_steam_loss(c["SiO2"]), "T_Cuarzo_Fournier1977_Ref"),
    "Na/K (Fournier 1979)": (lambda c: _geo().nak_fournier(c["Na"], c["K"]), "T_NaK_Fournier1979_Ref"),
    "Na/K (Truesdell 1976)": (lambda c: _geo().nak_truesdell(c["Na"], c["K"]), "T_NaK_Truesdell1976_Ref"),
    "Na/K (Giggenbach 1988)": (lambda c: _geo().nak_giggenbach(c["Na"], c["K"]), "T_NaK_Giggenbach1988_Ref"),
    "K-Mg (Giggenbach, 13.95)": (lambda c: _geo().kmg_giggenbach_1983(c["K"], c["Mg"]), "T_KMg_Giggenbach_Ref"),
}


def _geo():
    from solmineq_app.models.geothermometers import GeothermometerCalculator

    return GeothermometerCalculator
SULFIDES = ("Esfalerita", "Galena", "Pirrotita", "Pirita", "Calcopirita")

# Especie -> (nombre PHREEQC wateq4f, nombre PHREEQC llnl, clave SOLMINEQ-Py)
SPECIES = {
    "Ca2+": ("Ca+2", "Ca+2", "Ca2+"),
    "Mg2+": ("Mg+2", "Mg+2", "Mg2+"),
    "Na+": ("Na+", "Na+", "Na+"),
    "Cl-": ("Cl-", "Cl-", "Cl-"),
    "SO4--": ("SO4-2", "SO4-2", "SO4_2-"),
    "HCO3-": ("HCO3-", "HCO3-", "HCO3-"),
    "CO3--": ("CO3-2", "CO3-2", "CO3_2-"),
    "CO2(aq)": ("CO2", "CO2", "CO2_aq"),
    "H4SiO4": ("H4SiO4", "SiO2", "SiO2"),
    "F-": ("F-", "F-", "F-"),
    "Fe2+": ("Fe+2", "Fe+2", "Fe+2"),
    "CaSO4°": ("CaSO4", "CaSO4", "CaSO4_0"),
}


def _num(row: pd.Series, col: str) -> Optional[float]:
    """Valor numérico positivo de la fila, o None (no se inventan valores)."""
    val = row.get(col)
    if val is None or pd.isna(val):
        return None
    val = float(val)
    return val if val > 0 else None


def _ref(row: pd.Series, col: str) -> float:
    """Valor de referencia (puede ser negativo o cero), o NaN si falta."""
    if col not in row.index:
        return np.nan
    val = row.get(col)
    try:
        return float(val) if val is not None and not pd.isna(val) else np.nan
    except (TypeError, ValueError):
        return np.nan


def sample_inputs(row: pd.Series) -> Tuple[Dict[str, float], Optional[float], Optional[float]]:
    """Concentraciones comunes en mg/L (clave SOLMINEQ-Py), HCO3 en mg/L y H2S en mg/L."""
    conc: Dict[str, float] = {}
    for col, _, _, key in MAJORS:
        val = _num(row, col)
        if val is not None:
            conc[key] = val
    factor = 0.001 if str(row.get("Escala_Trazas", "MG_L")).upper().strip() == "UG_L" else 1.0
    for col, _, key in TRACES:
        val = _num(row, col)
        if val is not None:
            conc[key] = val * factor
    return conc, _num(row, "HCO3_mgL"), _num(row, "S_2_mgL")


def phreeqc_input(row: pd.Series, base: str, scenario: str) -> str:
    """Bloques SOLUTION / EQUILIBRIUM_PHASES / SELECTED_OUTPUT de una muestra."""
    conc, hco3, h2s = sample_inputs(row)
    lines = [
        f"TITLE Comparacion SOLMINEQ - {row['Muestra']} - {scenario} - {base}",
        "SOLUTION 1",
        f"    temp  {float(row['T_C'])}",
        f"    pH    {float(row['pH_superficie'])}",
        f"    pe    {PE}",
        "    units mg/l",
    ]
    if h2s and "SO4" in conc:
        # El pe de las especies de azufre sale del par SO4--/HS-, como supone SOLMINEQ.88 sin Eh medido
        # (manual, «Oxidation-Reduction Reactions»). Con pe = 4 PHREEQC pasaría el S(-2) a polisulfuros.
        lines.append("    redox S(-2)/S(6)")
    for col, name, suffix, key in MAJORS:
        if key in conc:
            lines.append(f"    {name:<6} {conc[key]:.6g} {suffix}".rstrip())
    for col, name, key in TRACES:
        if key in conc:
            lines.append(f"    {name:<6} {conc[key]:.6g}")
    if hco3:
        lines.append(f"    C(4)   {hco3:.6g} as HCO3")
    if h2s:
        lines.append(f"    S(-2)  {h2s:.6g} as H2S")
    if scenario == "B_profundo":
        pco2 = _num(row, "P_CO2_profunda_bar")
        if pco2:
            lines += ["EQUILIBRIUM_PHASES 1", f"    CO2(g) {math.log10(pco2):.4f}"]
    col = 1 if base == "llnl.dat" else 0
    phases = {m: v[col] for m, v in MINERALS.items() if v[col]}
    species = {s: v[col] for s, v in SPECIES.items()}
    headings = ["DIC"] + [f"si_{m}" for m in phases]
    for s in species:
        headings += [f"lm_{s}", f"lg_{s}"]
    basic = ['10 PUNCH TOT("C(4)")']
    n = 20
    for m, ph in phases.items():
        basic.append(f'{n} PUNCH SI("{ph}")'); n += 10
    for s, name in species.items():
        basic.append(f'{n} PUNCH LM("{name}"), LG("{name}")'); n += 10
    lines += [
        "SELECTED_OUTPUT 1", "    -reset false", "    -ph true", "    -ionic_strength true",
        "    -percent_error true", "    -user_punch true",
        "USER_PUNCH 1", "    -headings " + " ".join(h.replace("°", "0") for h in headings),
    ] + ["    " + b for b in basic] + ["END"]
    return "\n".join(lines)


def run_phreeqc(row: pd.Series, db_text: str, base: str, scenario: str) -> Dict[str, float]:
    """Corre PHREEQC y devuelve pH, mu, DIC (mol/kgw), IS y log m / log gamma de las especies."""
    ip = IPhreeqc()
    try:
        ip.load_database_string(db_text)
        ip.run_string(phreeqc_input(row, base, scenario))
        out = ip.get_selected_output_array()
    finally:
        ip.destroy_iphreeqc()
    vals = dict(zip([str(h).lower() for h in out[0]], out[-1]))
    res: Dict[str, float] = {"pH": vals["ph"], "mu": vals["mu"], "pct_err": vals.get("pct_err", np.nan),
                             "DIC": vals["dic"]}
    for m in MINERALS:
        v = vals.get(f"si_{m}".lower())
        res[f"SI_{m}"] = np.nan if v is None or v < -90 else v
    for s in SPECIES:
        key = s.replace("°", "0").lower()
        lm, lg = vals.get(f"lm_{key}"), vals.get(f"lg_{key}")
        ok = lm is not None and lm > -90
        res[f"m_{s}"] = 10 ** lm if ok else np.nan
        res[f"g_{s}"] = 10 ** lg if ok and lg is not None else np.nan
    return res


def run_solmineq(row: pd.Series, temp_c: float, ph: float, dic_mol_kgw: Optional[float]) -> Dict[str, float]:
    """Especiación B-dot y IS de SOLMINEQ-Py con la misma entrada que PHREEQC."""
    from solmineq_app.reporting.si import SaturationIndexEngine, speciate_for_si

    conc, hco3, h2s = sample_inputs(row)
    tds = sum(conc.values()) + (hco3 or 0.0) + (h2s or 0.0)
    water = 1.0 - tds * 1e-6  # kg de agua por kg de solución (densidad 1, como PHREEQC con mg/L)
    ppm = dict(conc)
    if hco3:
        ppm["HCO3"] = hco3
    if h2s:
        ppm["H2S"] = h2s
    if dic_mol_kgw is None and hco3:
        dic_mol_kgw = hco3 / 1000.0 / 61.0173 / water
    sp = speciate_for_si(ppm, water, temp_c, ph, dic_mol_kg=dic_mol_kgw)
    si = SaturationIndexEngine.compute_si(temp_c, water, ph, ppm, speciation=sp)
    res: Dict[str, float] = {"pH": ph, "mu": sp.ionic_strength, "DIC": dic_mol_kgw or np.nan,
                             "convergio": sp.converged}
    for m, (_, _, col) in MINERALS.items():
        v = si.get(col) if col else None
        res[f"SI_{m}"] = float(v) if isinstance(v, (int, float)) else np.nan
    for s, (_, _, key) in SPECIES.items():
        res[f"m_{s}"] = sp.molalities.get(key, np.nan)
        g = sp.gamma.get(key, np.nan)
        if key == "SiO2":
            g = sp.gamma_silica
        res[f"g_{s}"] = g
    return res


def compare(template: str, proyecto: str) -> Dict[str, pd.DataFrame]:
    """Corre los escenarios y arma las tablas de comparación."""
    data = pd.read_excel(template, sheet_name="Datos_Agua")
    data = data[data["Proyecto"].astype(str).str.strip() == proyecto].reset_index(drop=True)
    if data.empty:
        raise ValueError(f"No hay muestras del proyecto {proyecto!r} en {template}")
    dbs = {}
    for base in BASES:
        with open(ensure_database(base), encoding="utf-8", errors="ignore") as fh:
            dbs[base] = fh.read()

    rows: List[Dict] = []
    for _, row in data.iterrows():
        t, ph = float(row["T_C"]), float(row["pH_superficie"])
        scenarios = ["A_superficie"] + (["B_profundo"] if _num(row, "P_CO2_profunda_bar") else [])
        for scenario in scenarios:
            ph_res = {base: run_phreeqc(row, dbs[base], base, scenario) for base in BASES}
            if scenario == "A_superficie":
                sm = run_solmineq(row, t, ph, None)
            else:
                ref = ph_res[BASE_PROFUNDO]
                sm = run_solmineq(row, t, ref["pH"], ref["DIC"])
            for prog, res in [("PHREEQC-wateq4f", ph_res["wateq4f.dat"]),
                              ("PHREEQC-llnl", ph_res["llnl.dat"]), ("SOLMINEQ-Py", sm)]:
                rows.append({"Muestra": row["Muestra"], "Area": row["Area"], "T_C": t,
                             "Escenario": scenario, "Programa": prog, **res})
    long = pd.DataFrame(rows)

    # IS: una fila por muestra/escenario/mineral, columnas por programa y diferencias contra SOLMINEQ-Py
    si_rows = []
    for (muestra, esc), grp in long.groupby(["Muestra", "Escenario"], sort=False):
        g = grp.set_index("Programa")
        src = data[data["Muestra"] == muestra].iloc[0]
        for m, (_, llnl_phase, _) in MINERALS.items():
            refcol = f"si_{llnl_phase}_Ref"
            rec = {"Muestra": muestra, "Escenario": esc, "Mineral": m,
                   "Grupo": "Sulfuros" if m in SULFIDES else "Mayoritarios",
                   "SOLMINEQ-Py": g.loc["SOLMINEQ-Py", f"SI_{m}"],
                   "PHREEQC-wateq4f": g.loc["PHREEQC-wateq4f", f"SI_{m}"],
                   "PHREEQC-llnl": g.loc["PHREEQC-llnl", f"SI_{m}"],
                   "Ref_Tesis": _ref(src, refcol)}
            rec["Δ wateq4f − SOLMINEQ"] = rec["PHREEQC-wateq4f"] - rec["SOLMINEQ-Py"]
            rec["Δ llnl − SOLMINEQ"] = rec["PHREEQC-llnl"] - rec["SOLMINEQ-Py"]
            rec["Δ SOLMINEQ − Ref"] = rec["SOLMINEQ-Py"] - rec["Ref_Tesis"]
            rec["Δ wateq4f − Ref"] = rec["PHREEQC-wateq4f"] - rec["Ref_Tesis"]
            rec["Δ llnl − Ref"] = rec["PHREEQC-llnl"] - rec["Ref_Tesis"]
            si_rows.append(rec)
    si = pd.DataFrame(si_rows)

    # Especies: log10(actividad), gamma y molalidad por programa (escenario A)
    sp_rows = []
    a = long[long["Escenario"] == "A_superficie"]
    for muestra, grp in a.groupby("Muestra", sort=False):
        g = grp.set_index("Programa")
        for s in SPECIES:
            rec = {"Muestra": muestra, "Especie": s}
            for prog in ("SOLMINEQ-Py", "PHREEQC-wateq4f", "PHREEQC-llnl"):
                m, gm = g.loc[prog, f"m_{s}"], g.loc[prog, f"g_{s}"]
                rec[f"m {prog}"] = m
                rec[f"γ {prog}"] = gm
                rec[f"log a {prog}"] = math.log10(m * gm) if m and gm and m > 0 and gm > 0 else np.nan
            rec["Δ log a wateq4f − SOLMINEQ"] = rec["log a PHREEQC-wateq4f"] - rec["log a SOLMINEQ-Py"]
            rec["Δ log a llnl − SOLMINEQ"] = rec["log a PHREEQC-llnl"] - rec["log a SOLMINEQ-Py"]
            sp_rows.append(rec)
    species = pd.DataFrame(sp_rows)

    # Resumen por mineral y escenario
    def _stats(df: pd.DataFrame, col: str) -> Tuple[float, float, int]:
        v = df[col].dropna()
        return (round(v.mean(), 3), round(v.abs().max(), 3), int(v.size)) if len(v) else (np.nan, np.nan, 0)

    summary = []
    for (esc, m), grp in si.groupby(["Escenario", "Mineral"], sort=False):
        rec = {"Escenario": esc, "Mineral": m}
        for col in ("Δ wateq4f − SOLMINEQ", "Δ llnl − SOLMINEQ", "Δ SOLMINEQ − Ref", "Δ wateq4f − Ref",
                    "Δ llnl − Ref"):
            mean, mx, n = _stats(grp, col)
            rec[f"{col} (media)"], rec[f"{col} (máx |Δ|)"], rec[f"{col} (n)"] = mean, mx, n
        summary.append(rec)

    cond = long[long["Programa"] != "SOLMINEQ-Py"][["Muestra", "Escenario", "Programa", "T_C", "pH", "mu",
                                                     "DIC", "pct_err"]]
    sm = long[long["Programa"] == "SOLMINEQ-Py"][["Muestra", "Escenario", "pH", "mu", "DIC", "convergio"]]
    cond = cond.merge(sm, on=["Muestra", "Escenario"], suffixes=("", " SOLMINEQ-Py"))
    geo_rows = []
    for _, row in data.iterrows():
        conc = {k: _num(row, col) for k, col in (("SiO2", "SiO2_mgL"), ("Na", "Na_mgL"), ("K", "K_mgL"),
                                                  ("Mg", "Mg_mgL"))}
        for name, (fn, refcol) in GEOTHERMOMETERS.items():
            try:
                value = fn(conc)
            except (TypeError, ValueError, ZeroDivisionError):
                value = np.nan
            ref = _ref(row, refcol)
            geo_rows.append({"Muestra": row["Muestra"], "Geotermómetro": name, "SOLMINEQ-Py (°C)": value,
                             "Ref_Tesis (°C)": ref, "Δ (°C)": value - ref})
    return {"Resumen": pd.DataFrame(summary), "IS": si, "Especies_A": species, "Condiciones": cond,
            "Geotermometros": pd.DataFrame(geo_rows), "Datos_largos": long}


NOTES = [
    "Escenario A_superficie: T de la muestra, pH medido, carbono como DIC (C(4) as HCO3). Misma entrada en los tres.",
    "Escenario B_profundo: PHREEQC reequilibra con CO2(g) a P_CO2_profunda_bar; SOLMINEQ-Py usa el pH y el DIC "
    "que resultan con wateq4f.dat. llnl.dat calcula su propio pH profundo (ver hoja Condiciones). Las muestras "
    "sin P_CO2 no tienen escenario B (Puna Norte: ACF, LC y PA2, sin gases en la Tabla 6-5).",
    "Solutos comunes: Ca, Mg, Na, K, SO4, Cl, F, SiO2, Fe(2), Zn, Pb, Cu(2), C(4), S(-2). Li, B, NH4, Mn, Ba, As y Sb "
    "se excluyen porque SOLMINEQ-Py no los especia. Fe y Cu se declaran como Fe(2) y Cu(2).",
    "Redox: con S(-2) y SO4 la solución usa «redox S(-2)/S(6)» (equilibrio SO4--/HS-, la hipótesis de SOLMINEQ.88 sin "
    "Eh). Con el pe = 4 de la plantilla, PHREEQC convierte el S(-2) en polisulfuros (S4-2, S5-2) y el HS- cae hasta 8 "
    "órdenes de magnitud.",
    "S(-2) = S_2_mgL de la plantilla, tomado como H2S total. La tesis de la Puna Norte no informa S(-2) ni Pb: "
    "sin esos datos no hay IS de sulfuros.",
    "SOLMINEQ-Py: Zn y Pb entran como metal total (cota superior, ADR-056c); el Fe es el Fe(II) libre (ADR-056a). "
    "PHREEQC especia los tres metales con sus complejos.",
    "Yeso y fluorita no están en el catálogo de SOLMINEQ-Py; pirrotita no está en wateq4f.dat.",
    "Ref_Tesis: IS publicados (Tabla 6-7 de Peralta Arnold, 2018), calculados con llnl.dat y reequilibrio con "
    "CO2: compárense con el escenario B y la columna PHREEQC-llnl.",
    "Geotermómetros: funciones de SOLMINEQ-Py (models/geothermometers.py) frente a la Tabla 6-8. La columna de la "
    "tesis «Na/Mg (Giggenbach 1986)» es K-Mg con la constante 13.95 (kmg_giggenbach_1983). La calcedonia de "
    "Arnórsson (1983) no está en SOLMINEQ-Py y se calcula con su ecuación en este script.",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Comparación PHREEQC vs SOLMINEQ-Py")
    parser.add_argument("--input", default=DEFAULT_TEMPLATE, help="Plantilla Excel")
    parser.add_argument("--proyecto", default="Puna_Norte", help="Valor de la columna Proyecto")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Reporte Excel de salida")
    args = parser.parse_args()

    import solmineq_app  # noqa: F401  (falla temprano y claro si no está instalado)
    from solmineq_app._version import __version__ as sm_version

    tables = compare(args.input, args.proyecto)
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    notes = pd.DataFrame({"Nota": NOTES + [f"solmineq_app {sm_version}; pe PHREEQC = {PE}."]})
    with pd.ExcelWriter(args.output, engine="openpyxl") as writer:
        notes.to_excel(writer, sheet_name="Notas", index=False)
        for name, df in tables.items():
            df.round(4).to_excel(writer, sheet_name=name, index=False)
        for ws in writer.book.worksheets:  # formato mínimo: encabezado fijo y anchos legibles
            ws.freeze_panes = "A2"
            for col in ws.columns:
                width = max(len(str(c.value)) if c.value is not None else 0 for c in col)
                ws.column_dimensions[col[0].column_letter].width = min(max(10, width + 2), 60)
    print(f"[+] Comparación guardada en: {args.output}")


if __name__ == "__main__":
    main()
