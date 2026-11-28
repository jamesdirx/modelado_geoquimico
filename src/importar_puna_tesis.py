# -*- coding: utf-8 -*-
"""
Importa los datos de la Puna Norte desde el libro de la tesis a la plantilla del motor (ADR-002).

Fuente: ``data/raw/Caso_Estudio_Puna_Completo.xlsx`` (Peralta Arnold, 2018):

* Hoja ``Base_Completa_T63_T64_T65``: iones mayores e isótopos (Tabla 6-3), metales en µg/L (Tabla 6-4),
  P_CO2 y gases disueltos en mmol/mol (Tabla 6-5).
* Hoja ``ISM_Tabla_6_7``: índices de saturación publicados (21 minerales).
* Hoja ``Geotermometros``: Tabla 6-8.

Reglas (nada se inventa):

* Los valores se copian tal cual. Las celdas vacías, ``n.d.`` y ``<1`` (bajo el límite de detección) quedan
  vacías en la plantilla y se anotan en ``Nota_Datos``.
* La tesis no informa Pb, Al ni S(-2): esas columnas quedan vacías.
* ACF, LC y PA2 no tienen gases en la Tabla 6-5 (ACF y LC no tienen fase vapor; PA2 no figura en la tabla):
  se calculan con el pH de campo, sin reequilibrio con CO2 (``FIJO_CAMPO`` / ``SIN_GAS``).
* Base termodinámica de la Puna Norte: ``llnl.dat`` (la que reproduce la Tabla 6-7).

Uso (desde la raíz del repositorio):
    python src/importar_puna_tesis.py            # actualiza la plantilla
    python src/importar_puna_tesis.py --check    # solo verifica que la plantilla coincide con la tesis
"""
from __future__ import annotations

import argparse
import os
from copy import copy
import sys
from typing import Any, Dict, List, Optional, Tuple

import openpyxl
from openpyxl.styles import Font, PatternFill
from openpyxl.worksheet.cell_range import MultiCellRange

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(BASE_DIR, "data", "raw", "Caso_Estudio_Puna_Completo.xlsx")
TEMPLATE = os.path.join(BASE_DIR, "data", "raw", "Plantilla_Modelado_Geoquimico.xlsx")
PROJECT = "Puna_Norte"
BASE_PUNA = "llnl.dat"
NO_GAS_SAMPLES = {
    "ACF": "Sin gases en la Tabla 6-5 (muestra calentada sin fase vapor): pH de campo, sin reequilibrio con CO2.",
    "LC": "Sin gases en la Tabla 6-5 (muestra de río): pH de campo, sin reequilibrio con CO2.",
    "PA2": "La Tabla 6-5 no incluye PA2 (sin datos de gases ni P_CO2): pH de campo, sin reequilibrio con CO2. "
           "Los IS de la Tabla 6-7 para PA2 no se pueden reproducir con los datos publicados.",
}

# Columna de la tesis -> columna de la plantilla
WATER_COLUMNS: List[Tuple[str, str]] = [
    ("T (°C)", "T_C"), ("pH", "pH_superficie"), ("HCO3- (mg/L)", "HCO3_mgL"), ("F- (mg/L)", "F_mgL"),
    ("Cl- (mg/L)", "Cl_mgL"), ("SO4 2- (mg/L)", "SO4_mgL"), ("Ca2+ (mg/L)", "Ca_mgL"), ("Mg2+ (mg/L)", "Mg_mgL"),
    ("Na+ (mg/L)", "Na_mgL"), ("K+ (mg/L)", "K_mgL"), ("Li+ (mg/L)", "Li_mgL"), ("SiO2 (mg/L)", "SiO2_mgL"),
    ("B (mg/L)", "B_mgL"), ("NH4+ (mg/L)", "NH4_mgL"), ("Fe (µg/L)", "Fe_traza"), ("Mn (µg/L)", "Mn_traza"),
    ("Zn (µg/L)", "Zn_traza"), ("Cu (µg/L)", "Cu_traza"), ("Ni (µg/L)", "Ni_traza"), ("Ba (µg/L)", "Ba_traza"),
    ("As (µg/L)", "As_traza"), ("Sb (µg/L)", "Sb_traza"), ("P_CO2_profunda (bar)", "P_CO2_profunda_bar"),
    ("δ18O (‰)", "O18_permil"), ("δD (‰)", "Deuterio_permil"),
    # columnas nuevas (ADR-002)
    ("Br- (mg/L)", "Br_mgL"), ("NO3- (mg/L)", "NO3_mgL"), ("Co (µg/L)", "Co_traza"), ("TDS (mg/L)", "TDS_mgL"),
]
#: Columnas de la plantilla que la tesis no informa: quedan vacías en la Puna Norte.
NOT_REPORTED = ("Al_traza", "Pb_traza", "S_2_mgL", "pH_Ref")

GAS_COLUMNS = ["CO2 (mmol/mol)", "N2 (mmol/mol)", "CH4 (mmol/mol)", "Ar (mmol/mol)", "O2 (mmol/mol)",
               "Ne (mmol/mol)", "H2 (mmol/mol)", "He (mmol/mol)"]

# Mineral de la Tabla 6-7 -> (fase PHREEQC, nombre, fórmula, grupo)
MINERALS_T67: Dict[str, Tuple[str, str, str]] = {
    "Anhidrita": ("Anhydrite", "CaSO4", "Sulfatos / Evaporitas"),
    "Aragonito": ("Aragonite", "CaCO3", "Carbonatos"),
    "Baritina": ("Barite", "BaSO4", "Sulfatos"),
    "Calcita": ("Calcite", "CaCO3", "Carbonatos"),
    "Calcedonia": ("Chalcedony", "SiO2", "Sílice"),
    "Coesita": ("Coesite", "SiO2", "Sílice"),
    "Dolomita": ("Dolomite", "CaMg(CO3)2", "Carbonatos"),
    "Fayalita": ("Fayalite", "Fe2SiO4", "Silicatos"),
    "Fluorita": ("Fluorite", "CaF2", "Haluros"),
    "Forsterita": ("Forsterite", "Mg2SiO4", "Silicatos"),
    "Goethita": ("Goethite", "FeOOH", "Óxidos / Hidróxidos Fe"),
    "Yeso": ("Gypsum", "CaSO4:2H2O", "Sulfatos / Evaporitas"),
    "Halita": ("Halite", "NaCl", "Haluros / Evaporitas"),
    "Hematita": ("Hematite", "Fe2O3", "Óxidos / Hidróxidos Fe"),
    "Huntita": ("Huntite", "CaMg3(CO3)4", "Carbonatos"),
    "Magnesita": ("Magnesite", "MgCO3", "Carbonatos"),
    "Magnetita": ("Magnetite", "Fe3O4", "Óxidos / Hidróxidos Fe"),
    "Cuarzo": ("Quartz", "SiO2", "Sílice"),
    "Talco": ("Talc", "Mg3Si4O10(OH)2", "Silicatos"),
    "Witherita": ("Witherite", "BaCO3", "Carbonatos"),
    "Zincita": ("Zincite", "ZnO", "Óxidos"),
}

# Columna de la Tabla 6-8 (por posición) -> columna de referencia en la plantilla
GEOTHERMOMETERS_T68 = [
    "T_Calcedonia_Arnorsson1983_Ref", "T_Cuarzo_Fournier1977_Ref", "T_NaK_Fournier1979_Ref",
    "T_NaK_Truesdell1976_Ref", "T_NaK_Giggenbach1988_Ref", "T_KMg_Giggenbach_Ref",
]

NEW_DATA_COLUMNS = ["Br_mgL", "NO3_mgL", "Co_traza", "TDS_mgL", "Base_Datos", "Nota_Datos"]


def _clean(value: Any) -> Tuple[Optional[float], Optional[str]]:
    """Número de la tesis, o (None, motivo) si la celda no es un número utilizable."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None, None
    if isinstance(value, (int, float)):
        return float(value), None
    text = str(value).strip().replace(",", ".")
    if text.startswith("<"):
        return None, f"bajo límite de detección ({text})"
    if text.lower() in ("n.d.", "nd", "n.d"):
        return None, "n.d."
    try:
        return float(text.rstrip("*")), None
    except ValueError:
        return None, f"valor no numérico ({text})"


def _table(ws, first_header: str) -> Tuple[List[str], List[List[Any]]]:
    """Encabezado y filas de datos de una hoja de la tesis (desde la fila cuyo primer valor útil es el dado)."""
    rows = [list(r) for r in ws.iter_rows(values_only=True)]
    for i, row in enumerate(rows):
        if first_header in row:
            header = [str(c).strip() if c is not None else "" for c in row]
            data = []
            for r in rows[i + 1:]:
                key = r[header.index(first_header)]
                if key is None or not str(key).strip() or ":" in str(key):
                    break
                data.append(r)
            return header, data
    raise ValueError(f"No se encontró el encabezado {first_header!r} en la hoja {ws.title!r}")


def read_thesis(path: str = SOURCE) -> Dict[str, Any]:
    """Lee el libro de la tesis: datos por muestra, IS de la Tabla 6-7 y geotermómetros de la Tabla 6-8."""
    wb = openpyxl.load_workbook(path, data_only=True)
    header, rows = _table(wb["Base_Completa_T63_T64_T65"], "Muestra")
    samples: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        rec = dict(zip(header, row))
        samples[str(rec["Muestra"]).strip()] = rec
    h67, r67 = _table(wb["ISM_Tabla_6_7"], "id")
    si = {str(r[0]).strip(): dict(zip(h67, r)) for r in r67}
    ws68 = wb["Geotermometros"]
    _, r68 = _table(ws68, "id")
    geo = {str(r[0]).strip(): list(r[1:1 + len(GEOTHERMOMETERS_T68)]) for r in r68}
    return {"samples": samples, "si": si, "geo": geo, "water_header": header}


def puna_rows(thesis: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Valores de la plantilla para cada muestra de la Puna Norte (clave = columna de la plantilla)."""
    out: Dict[str, Dict[str, Any]] = {}
    for name, rec in thesis["samples"].items():
        notes: List[str] = []
        row: Dict[str, Any] = {
            "Proyecto": PROJECT, "Area": rec["Area"], "Muestra": name, "Tipo_Manantial": rec["Tipo"],
            "Campana": 2018, "Modo_Carbono": "COMO_C4_HCO3", "Escala_Trazas": "UG_L", "pe": 4,
            "Base_Datos": BASE_PUNA,
        }
        for src, dst in WATER_COLUMNS:
            value, why = _clean(rec.get(src))
            row[dst] = value
            if why and why != "n.d.":
                notes.append(f"{dst}: {why}")
        for col in NOT_REPORTED:
            row[col] = None
        if name in NO_GAS_SAMPLES or row["P_CO2_profunda_bar"] is None:
            row["Modo_pH"], row["Modo_Gas"] = "FIJO_CAMPO", "SIN_GAS"
            notes.insert(0, NO_GAS_SAMPLES.get(name, "Sin P_CO2 en la Tabla 6-5: sin reequilibrio con CO2."))
        else:
            row["Modo_pH"], row["Modo_Gas"] = "REEQUILIBRIO_GAS", "CO2_PROFUNDO"
        si = thesis["si"].get(name, {})
        for mineral, (phase, _, _) in MINERALS_T67.items():
            row[f"si_{phase}_Ref"] = _clean(si.get(mineral))[0]
        geo = thesis["geo"].get(name, [None] * len(GEOTHERMOMETERS_T68))
        for col, value in zip(GEOTHERMOMETERS_T68, geo):
            row[col] = _clean(value)[0]
        if name not in thesis["si"]:
            notes.append("Sin IS en la Tabla 6-7.")
        row["Nota_Datos"] = " ".join(notes) if notes else None
        out[name] = row
    return out


def _ensure_columns(ws, names: List[str]) -> Dict[str, int]:
    """Agrega al final las columnas que falten (con el formato del encabezado) y devuelve nombre -> índice."""
    header = {str(c.value).strip(): c.column for c in ws[1] if c.value is not None}
    ref = ws.cell(1, 1)
    for name in names:
        if name not in header:
            col = ws.max_column + 1
            cell = ws.cell(1, col, name)
            cell.font, cell.fill, cell.alignment = Font(**{"b": ref.font.b, "color": ref.font.color}), \
                PatternFill(fill_type=ref.fill.fill_type, fgColor=ref.fill.fgColor), copy(ref.alignment)
            ws.column_dimensions[cell.column_letter].width = max(14, len(name) + 2)
            header[name] = col
    return header


def update_template(template: str = TEMPLATE, source: str = SOURCE) -> List[str]:
    """Reescribe las filas de la Puna Norte, agrega columnas, minerales y la hoja de gases. Devuelve avisos."""
    thesis = read_thesis(source)
    rows = puna_rows(thesis)
    wb = openpyxl.load_workbook(template)
    ws = wb["Datos_Agua"]
    ref_cols = [f"si_{p}_Ref" for p, _, _ in MINERALS_T67.values()]
    header = _ensure_columns(ws, NEW_DATA_COLUMNS + ref_cols + GEOTHERMOMETERS_T68)
    puna_lines = {str(ws.cell(r, header["Muestra"]).value).strip(): r for r in range(2, ws.max_row + 1)
                  if ws.cell(r, header["Proyecto"]).value == PROJECT}
    missing = sorted(set(rows) - set(puna_lines))
    if missing:
        raise ValueError(f"La plantilla no tiene filas de la Puna Norte para: {', '.join(missing)}")
    for name, values in rows.items():
        r = puna_lines[name]
        for col, value in values.items():
            ws.cell(r, header[col]).value = value

    _update_minerals(wb["Minerales_Objetivo"])
    _write_gases(wb, thesis)
    _update_catalog(wb)
    wb.save(template)
    return []


def _update_minerals(ws) -> None:
    """Agrega las fases de la Tabla 6-7 que falten y enlaza su columna de referencia."""
    names = {str(ws.cell(r, 1).value).strip(): r for r in range(2, ws.max_row + 1) if ws.cell(r, 1).value}
    for mineral, (phase, formula, group) in MINERALS_T67.items():
        if phase in names:
            r = names[phase]
        else:
            r = ws.max_row + 1
            for c in range(1, 8):  # copia el formato de la fila anterior
                ws.cell(r, c)._style = ws.cell(r - 1, c)._style
            ws.cell(r, 1, phase), ws.cell(r, 2, mineral), ws.cell(r, 3, formula), ws.cell(r, 4, group)
            ws.cell(r, 5, "Puna Norte"), ws.cell(r, 6, "SI")
            names[phase] = r
        ws.cell(r, 7).value = f"si_{phase}_Ref"
    for dv in ws.data_validations.dataValidation:  # la lista SI/NO cubre las filas nuevas
        if "F2:" in str(dv.sqref):
            dv.sqref = MultiCellRange(f"F2:F{max(ws.max_row, 60)}")


def _write_gases(wb, thesis: Dict[str, Any]) -> None:
    """Hoja con los gases disueltos de la Tabla 6-5 (informativa: el motor no la usa)."""
    if "Gases_Puna_T6_5" in wb.sheetnames:
        del wb["Gases_Puna_T6_5"]
    ws = wb.create_sheet("Gases_Puna_T6_5")
    header = ["Muestra", "P_CO2_profunda_bar"] + [c.replace(" (mmol/mol)", "_mmol_mol") for c in GAS_COLUMNS]
    ws.append(header)
    for name, rec in thesis["samples"].items():
        values = [_clean(rec.get(c)) for c in GAS_COLUMNS]
        if all(v is None and why is None for v, why in values) and _clean(rec.get("P_CO2_profunda (bar)"))[0] is None:
            continue  # la muestra no figura en la Tabla 6-5
        ws.append([name, _clean(rec.get("P_CO2_profunda (bar)"))[0]] +
                  [v if v is not None else ("n.d." if why == "n.d." else None) for v, why in values])
    ws.append([])
    ws.append(["Fuente: Tabla 6-5 de Peralta Arnold (2018), gases disueltos en mmol/mol. ACF, LC y PA2 no figuran."])
    ref = wb["Datos_Agua"].cell(1, 1)
    for cell in ws[1]:
        cell.font, cell.fill = Font(b=True, color=ref.font.color), PatternFill(
            fill_type=ref.fill.fill_type, fgColor=ref.fill.fgColor)
        ws.column_dimensions[cell.column_letter].width = 20


def _update_catalog(wb) -> None:
    """Agrega llnl.dat al catálogo de bases (para la columna Base_Datos) si falta la descripción."""
    ws = wb["Catalogos"]
    for r in range(2, ws.max_row + 1):
        if ws.cell(r, 1).value == "BASE_DATOS" and ws.cell(r, 2).value == "phreeqc.dat":
            ws.cell(r, 4).value = ("Base estándar de PHREEQC. La versión actual de USGS no carga en el IPhreeqc 3.7.3 "
                                   "de phreeqpy 0.6.0 (bloque GAS_BINARY_PARAMETERS): no usar por ahora.")


def check_template(template: str = TEMPLATE, source: str = SOURCE) -> List[str]:
    """Diferencias entre la plantilla y la tesis (lista vacía si coinciden)."""
    rows = puna_rows(read_thesis(source))
    wb = openpyxl.load_workbook(template, data_only=True)
    ws = wb["Datos_Agua"]
    header = {str(c.value).strip(): c.column for c in ws[1] if c.value is not None}
    diffs: List[str] = []
    lines = {str(ws.cell(r, header["Muestra"]).value).strip(): r for r in range(2, ws.max_row + 1)
             if ws.cell(r, header["Proyecto"]).value == PROJECT}
    for name, values in rows.items():
        if name not in lines:
            diffs.append(f"{name}: falta la fila")
            continue
        for col, value in values.items():
            if col not in header:
                diffs.append(f"falta la columna {col}")
                continue
            got = ws.cell(lines[name], header[col]).value
            same = (got in (None, "") and value is None) or got == value or (
                isinstance(got, (int, float)) and isinstance(value, (int, float)) and abs(got - value) < 1e-9)
            if not same:
                diffs.append(f"{name}.{col}: plantilla={got!r} tesis={value!r}")
    return sorted(set(diffs))


def main() -> int:
    parser = argparse.ArgumentParser(description="Importa la Puna Norte desde el libro de la tesis")
    parser.add_argument("--check", action="store_true", help="solo verifica, no escribe")
    args = parser.parse_args()
    if args.check:
        diffs = check_template()
        for d in diffs:
            print("  -", d)
        print("OK: la plantilla coincide con la tesis." if not diffs else f"{len(diffs)} diferencias.")
        return 1 if diffs else 0
    update_template()
    print(f"[+] Puna Norte actualizada en {TEMPLATE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
