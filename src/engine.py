# -*- coding: utf-8 -*-
"""
Motor Geoquímico Universal dirigido por catálogos en Excel (Data-Driven Engine).
Soporta múltiples modelos termodinámicos (Puna Norte, Caldera El Aguajito y nuevos proyectos)
sin modificar el código fuente.
"""

import os
import re
import sys
import glob
import json
import shutil
import ctypes
import hashlib
import argparse
import platform
import tempfile
import contextlib
import subprocess
import urllib.request
from datetime import datetime, timezone
import pandas as pd
import numpy as np
from phreeqpy.iphreeqc.phreeqc_dll import IPhreeqc

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_TEMPLATE = os.path.join(BASE_DIR, "data", "raw", "Plantilla_Modelado_Geoquimico.xlsx")
DEFAULT_OUTPUT_EXCEL = os.path.join(BASE_DIR, "reports", "Reporte_Universal_Geoquimico.xlsx")
DEFAULT_OUTPUT_CSV = os.path.join(BASE_DIR, "data", "processed", "resultados_universales_phreeqc.csv")
#: Entradas y salidas de PHREEQC por muestra, en texto UTF-8 (ADR-004).
REPORTS_PHREEQC_DIR = os.path.join(BASE_DIR, "reports", "phreeqc")
#: SHA-256 registrado de las bases versionadas (ADR-004).
SHA256SUMS = os.path.join(BASE_DIR, "database", "SHA256SUMS")


# ------------------------------------------------------------------------------------------------
# Archivos y trazabilidad (ADR-004)
# ------------------------------------------------------------------------------------------------
_WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def safe_filename(name, used=None):
    """Nombre de archivo válido en Windows, Linux y macOS a partir de un nombre de muestra o proyecto (ADR-004).

    Reemplaza ``< > : " / \\ | ? *`` y los caracteres de control por ``_``, quita puntos y espacios del final, evita
    los nombres reservados de Windows (CON, NUL, COM1...) y, si se pasa ``used`` (conjunto de nombres ya usados, sin
    distinguir mayúsculas), agrega ``_2``, ``_3``... para no pisar otro archivo.
    """
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(name)).strip().rstrip(". ")
    if not text:
        text = "muestra"
    if text.split(".")[0].upper() in _WINDOWS_RESERVED:
        text = "_" + text
    if used is not None:
        base, n = text, 2
        while text.lower() in used:
            text = f"{base}_{n}"
            n += 1
        used.add(text.lower())
    return text


def copy_as_utf8(src, dst):
    """Copia una salida de PHREEQC como texto UTF-8 (ADR-004).

    PHREEQC mezcla codificaciones: repite la entrada tal cual (UTF-8) y escribe sus propios rótulos en Latin-1
    («°C», «cm³/mol»). Los bytes que no son UTF-8 válido se leen como Latin-1, así el archivo queda en una sola
    codificación y se puede abrir o subir como texto.
    """
    with open(src, "rb") as fh:
        text = fh.read().decode("utf-8", errors="surrogateescape")
    text = "".join(chr(ord(c) - 0xDC00) if 0xDC80 <= ord(c) <= 0xDCFF else c for c in text)
    with open(dst, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def text_sha256(path):
    """SHA-256 de un archivo de texto con finales de línea LF (git en Windows puede convertirlos a CRLF)."""
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read().replace(b"\r\n", b"\n")).hexdigest()


def read_sha256sums(path=SHA256SUMS):
    """{nombre de base: SHA-256} de ``database/SHA256SUMS`` (formato «<hash>  <archivo>»; # = comentario)."""
    sums = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                parts = line.split()
                if len(parts) == 2 and not line.startswith("#"):
                    sums[parts[1].lstrip("*")] = parts[0].lower()
    return sums


_IPHREEQC_LIB = []


def _iphreeqc_lib():
    """La librería IPhreeqc que usa phreeqpy, cargada con ctypes (para lo que phreeqpy no expone)."""
    if not _IPHREEQC_LIB:
        import phreeqpy.iphreeqc.phreeqc_dll as dll

        for path in sorted(glob.glob(os.path.join(os.path.dirname(dll.__file__), "phreeqc3", "*"))):
            try:
                lib = ctypes.cdll.LoadLibrary(path)
                lib.GetVersionString, lib.GetWarningString  # noqa: B018 (comprueba que existen)
            except (OSError, AttributeError):
                continue
            lib.GetVersionString.restype = ctypes.c_char_p
            lib.GetWarningString.restype = ctypes.c_char_p
            lib.GetWarningString.argtypes = [ctypes.c_int]
            _IPHREEQC_LIB.append(lib)
            break
        else:
            _IPHREEQC_LIB.append(None)
    return _IPHREEQC_LIB[0]


def iphreeqc_version():
    """Versión que informa la librería IPhreeqc (p. ej. «3.7.3-15968»), o «desconocida»."""
    lib = _iphreeqc_lib()
    return lib.GetVersionString().decode() if lib else "desconocida"


_MISSING_PHASE = re.compile(r"^Mineral (.+), not found\.?$")


def phreeqc_warnings(ip):
    """Avisos de PHREEQC de la última corrida (ADR-004).

    Returns
    -------
    tuple
        (avisos en una línea, «aviso 1 | aviso 2», o '' si no hay; conjunto de fases del catálogo que no existen
        en la base). Las fases faltantes se separan porque se repiten igual en todas las muestras de una base: van
        una sola vez a la trazabilidad, no a cada muestra.
    """
    lib = _iphreeqc_lib()
    if lib is None:
        return "", set()
    raw = (lib.GetWarningString(ip.id_) or b"").decode("utf-8", errors="replace")
    parts = [" ".join(p.split()) for p in raw.split("WARNING:") if p.strip()]
    missing = {m.group(1) for m in map(_MISSING_PHASE.match, parts) if m}
    other = [p for p in dict.fromkeys(parts) if not _MISSING_PHASE.match(p)]
    return " | ".join(other), missing


@contextlib.contextmanager
def isolated_workdir():
    """Carpeta temporal vacía como carpeta de trabajo (ADR-004).

    IPhreeqc escribe ``phreeqc.<id>.out`` en la carpeta de trabajo. Con una carpeta propia por corrida, el reporte
    que se recoge es solo el de esa muestra, aunque haya ``.out`` viejos en la carpeta desde la que se ejecuta.
    """
    old = os.getcwd()
    tmp = tempfile.mkdtemp(prefix="phreeqc_")
    os.chdir(tmp)
    try:
        yield tmp
    finally:
        os.chdir(old)
        shutil.rmtree(tmp, ignore_errors=True)


def display_path(path):
    """Ruta relativa a la raíz del repositorio si está dentro de él; si no, la ruta absoluta (ADR-004).

    ``os.path.relpath`` lanza ValueError en Windows cuando las dos rutas están en unidades distintas (por ejemplo,
    el repositorio en H: y una carpeta temporal en C:).
    """
    path = os.path.abspath(path)
    try:
        rel = os.path.relpath(path, BASE_DIR)
    except ValueError:
        return path
    return path if rel == os.pardir or rel.startswith(os.pardir + os.sep) else rel


def git_commit():
    """Commit del repositorio («c16defd», con «+cambios» si hay archivos modificados), o «desconocido»."""
    try:
        head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=BASE_DIR, capture_output=True,
                              text=True, timeout=10)
        if head.returncode != 0:
            return "desconocido"
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=BASE_DIR,
                               capture_output=True, text=True, timeout=10)
        return head.stdout.strip() + ("+cambios" if dirty.stdout.strip() else "")
    except (OSError, subprocess.SubprocessError):
        return "desconocido"


def build_traceability(excel_path, bases):
    """Datos de trazabilidad de la corrida y avisos de bases que no coinciden con SHA256SUMS (ADR-004).

    Returns
    -------
    tuple
        (dict ordenado con la trazabilidad, lista de avisos).
    """
    from importlib.metadata import PackageNotFoundError, version

    try:
        phreeqpy_version = version("phreeqpy")
    except PackageNotFoundError:
        phreeqpy_version = "desconocida"
    registered = read_sha256sums()
    info = {
        "fecha_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "commit": git_commit(),
        "python": platform.python_version(),
        "sistema": f"{platform.system()} {platform.release()}",
        "phreeqpy": phreeqpy_version,
        "iphreeqc": iphreeqc_version(),
        "plantilla": display_path(excel_path),
        "plantilla_sha256": hashlib.sha256(open(excel_path, "rb").read()).hexdigest(),
        "bases": {},
    }
    warnings = []
    for name in bases:
        path = ensure_database(name)
        sha = text_sha256(path)
        expected = registered.get(name)
        if expected is None:
            state = "no registrada en database/SHA256SUMS"
        elif expected == sha:
            state = "coincide con database/SHA256SUMS"
        else:
            state = f"NO COINCIDE con database/SHA256SUMS ({expected})"
            warnings.append(f"{name}: el SHA-256 {sha} no coincide con el registrado en database/SHA256SUMS. "
                            "La base cambió: los resultados pueden no ser comparables con corridas anteriores.")
        info["bases"][name] = {"sha256": sha, "estado": state,
                               "bloques_omitidos": ", ".join(DATABASE_NOTES.get(name, [])) or "—"}
    return info, warnings


def traceability_rows(info):
    """Filas (Parametro, Valor) de la hoja Trazabilidad."""
    rows = [(k, v) for k, v in info.items() if k != "bases"]
    for name, data in info["bases"].items():
        rows += [(f"base {name}: sha256", data["sha256"]), (f"base {name}: estado", data["estado"]),
                 (f"base {name}: bloques omitidos", data["bloques_omitidos"]),
                 (f"base {name}: fases del catálogo no encontradas (IS vacío)", data.get("fases_no_encontradas", "—"))]
    return rows


def database_for_row(row, config):
    """Base termodinámica de la fila: columna Base_Datos si está llena; si no, BASE_DATOS_ACTIVA (ADR-002)."""
    value = row.get("Base_Datos")
    if value is not None and pd.notnull(value) and str(value).strip():
        return str(value).strip()
    return str(config.get("BASE_DATOS_ACTIVA", "wateq4f.dat")).strip()


#: Bloques de las bases de USGS que el IPhreeqc 3.7.3 de phreeqpy 0.6.0 no reconoce (ADR-003). Ninguno interviene
#: en la especiación ni en los IS: GAS_BINARY_PARAMETERS solo afecta a GAS_PHASE con Peng-Robinson y MEAN_GAMMAS
#: solo a la salida de coeficientes de actividad medios.
UNSUPPORTED_DB_BLOCKS = ("GAS_BINARY_PARAMETERS", "MEAN_GAMMAS")
#: Bloques omitidos al cargar cada base: {nombre de la base: [bloques]} (ADR-003).
DATABASE_NOTES = {}
_KEYWORD = re.compile(r"^([A-Z][A-Z_]{3,})(?=\s|#|$)")


def strip_unsupported_blocks(text, keywords=UNSUPPORTED_DB_BLOCKS):
    """Quita de una base los bloques de las palabras clave dadas, hasta la palabra clave siguiente (ADR-003).

    Una palabra clave es una línea que empieza en la columna 0 con mayúsculas y guiones bajos (``PHASES``,
    ``MEAN_GAMMAS``). Las fórmulas como ``H2O(g)`` o ``CaCl2`` no lo son.

    Returns
    -------
    tuple
        (texto sin los bloques, lista de bloques quitados en orden de aparición).
    """
    keywords = set(keywords)
    out, removed, skip = [], [], False
    for line in text.splitlines(keepends=True):
        match = _KEYWORD.match(line)
        if match:
            skip = match.group(1) in keywords
            if skip and match.group(1) not in removed:
                removed.append(match.group(1))
        if not skip:
            out.append(line)
    return "".join(out), removed


def _load_errors(text):
    """Errores de IPhreeqc al cargar el texto de una base ('' si carga)."""
    probe = IPhreeqc()
    try:
        probe.load_database_string(text)
        return probe.get_error_string().strip()
    finally:
        probe.destroy_iphreeqc()


def load_database_text(db_name, cache):
    """Texto de la base (con caché) tras comprobar que IPhreeqc la carga sin errores (ADR-002).

    Si no carga y tiene bloques que esta versión de IPhreeqc no reconoce (``UNSUPPORTED_DB_BLOCKS``), los quita,
    avisa y lo anota en ``DATABASE_NOTES`` (ADR-003). Si sigue sin cargar, se detiene con los primeros errores.
    """
    if db_name not in cache:
        with open(ensure_database(db_name), "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
        errors = _load_errors(text)
        if errors:
            stripped, removed = strip_unsupported_blocks(text)
            if removed and not _load_errors(stripped):
                print(f"[!] {db_name}: se omitieron los bloques {', '.join(removed)}, que IPhreeqc 3.7.3 no "
                      "reconoce (no intervienen en la especiación ni en los IS).")
                DATABASE_NOTES[db_name] = removed
                text, errors = stripped, ""
        if errors:
            raise RuntimeError(
                f"IPhreeqc no pudo cargar la base '{db_name}' (versión incompatible con la librería de phreeqpy):\n"
                + "\n".join(errors.splitlines()[:4])
            )
        cache[db_name] = text
    return cache[db_name]


def ensure_database(db_name):
    """Verifica que la base de datos seleccionada en el catálogo exista localmente."""
    db_path = os.path.join(BASE_DIR, "database", db_name)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    if not os.path.exists(db_path) or os.path.getsize(db_path) == 0:
        url = f"https://raw.githubusercontent.com/usgs-coupled/iphreeqc/master/database/{db_name}"
        print(f"[-] Descargando base de datos {db_name} desde USGS...")
        urllib.request.urlretrieve(url, db_path)
        print(f"[+] Base de datos guardada en: {db_path}")
    return db_path


def load_excel_configuration(excel_path):
    """Lee las 4 pestañas de la plantilla Excel universal."""
    if not os.path.exists(excel_path):
        raise FileNotFoundError(f"No se encontró la plantilla en: {excel_path}")

    df_cfg = pd.read_excel(excel_path, sheet_name="Configuracion")
    config = dict(zip(df_cfg["Parametro_Global"].str.strip(), df_cfg["Valor_Seleccionado"]))

    df_min = pd.read_excel(excel_path, sheet_name="Minerales_Objetivo")
    active_minerals = df_min[df_min["Activar"].astype(str).str.upper().str.strip() == "SI"].copy()

    df_data = pd.read_excel(excel_path, sheet_name="Datos_Agua")
    filtro = str(config.get("FILTRO_PROYECTO", "TODOS")).strip()
    if filtro.upper() != "TODOS":
        df_data = df_data[df_data["Proyecto"].astype(str).str.strip() == filtro].copy()

    return config, active_minerals, df_data


def build_dynamic_phreeqc_input(row, config, active_minerals, notices=None):
    """Construye el bloque SOLUTION, EQUILIBRIUM_PHASES y USER_PUNCH según los catálogos de la fila.

    Si se pasa ``notices`` (lista), se le agregan los avisos del motor sobre esta muestra (ADR-004), además de
    imprimirlos.
    """
    muestra = str(row["Muestra"]).strip()
    modo_ph = str(row.get("Modo_pH", "FIJO_CAMPO")).upper().strip()
    modo_carbono = str(row.get("Modo_Carbono", "SIN_CARBONO")).upper().strip()
    modo_gas = str(row.get("Modo_Gas", "SIN_GAS")).upper().strip()
    escala_trazas = str(row.get("Escala_Trazas", "MG_L")).upper().strip()

    # 1. Temperatura y modo de pH
    t_c = float(row["T_C"]) if pd.notnull(row.get("T_C")) else 25.0
    if modo_ph == "BALANCE_CARGA_25C":
        t_c = 25.0

    ph_sup = float(row["pH_superficie"]) if pd.notnull(row.get("pH_superficie")) else 7.0
    if modo_ph in ["BALANCE_CARGA_T_INSITU", "BALANCE_CARGA_25C"]:
        ph_line = f"pH          {ph_sup} charge"
    else:
        ph_line = f"pH          {ph_sup}"

    pe_val = float(row["pe"]) if pd.notnull(row.get("pe")) else float(config.get("PE_DEFECTO", 4.0))

    lines = [
        f"TITLE Simulacion Universal - Proyecto {row.get('Proyecto')} - Muestra {muestra}",
        "SOLUTION 1",
        f"    temp        {t_c}",
        f"    {ph_line}",
        f"    pe          {pe_val}",
        "    units       mg/l"
    ]

    # 2. Especies mayoritarias y menores en mg/L
    major_map = [
        ("F_mgL", "F", ""),
        ("Cl_mgL", "Cl", ""),
        ("SO4_mgL", "S(6)", ""),
        ("Ca_mgL", "Ca", ""),
        ("Mg_mgL", "Mg", ""),
        ("Na_mgL", "Na", ""),
        ("K_mgL", "K", ""),
        ("Li_mgL", "Li", ""),
        ("SiO2_mgL", "Si", "as SiO2"),
        ("B_mgL", "B", ""),
        ("NH4_mgL", "N(-3)", "as NH4"),
        ("S_2_mgL", "S(-2)", ""),
        ("Br_mgL", "Br", ""),           # ADR-002
        ("NO3_mgL", "N(5)", "as NO3"),  # ADR-002
    ]
    for col_name, phreeqc_elem, suffix in major_map:
        if col_name in row and pd.notnull(row[col_name]):
            val = float(row[col_name])
            if val > 0:
                lines.append(f"    {phreeqc_elem:<11} {val:.6f} {suffix}".rstrip())

    # 3. Modo de Carbono / Alcalinidad
    if pd.notnull(row.get("HCO3_mgL")) and float(row["HCO3_mgL"]) > 0:
        c_val = float(row["HCO3_mgL"])
        if modo_carbono == "COMO_C4_HCO3":
            lines.append(f"    C(4)        {c_val:.4f} as HCO3")
        elif modo_carbono == "COMO_ALCALINIDAD_HCO3":
            lines.append(f"    Alkalinity  {c_val:.4f} as HCO3")
        elif modo_carbono == "COMO_ALCALINIDAD_CACO3":
            lines.append(f"    Alkalinity  {c_val:.4f} as CaCO3")

    # 4. Escala de Elementos Traza (UG_L divide entre 1000, MG_L pasa directo)
    factor_traza = 0.001 if escala_trazas == "UG_L" else 1.0
    trace_map = [
        ("Fe_traza", "Fe"),
        ("Al_traza", "Al"),
        ("Mn_traza", "Mn"),
        ("Zn_traza", "Zn"),
        ("Cu_traza", "Cu"),
        ("Ni_traza", "Ni"),
        ("Pb_traza", "Pb"),
        ("Ba_traza", "Ba"),
        ("As_traza", "As"),
        ("Sb_traza", "Sb"),
        ("Co_traza", "Co"),  # ADR-002 (wateq4f.dat no tiene Co: PHREEQC lo toma como cero)
    ]
    for col_name, phreeqc_elem in trace_map:
        if col_name in row and pd.notnull(row[col_name]):
            val = float(row[col_name]) * factor_traza
            if val > 0:
                lines.append(f"    {phreeqc_elem:<11} {val:.6f}")

    # 5. Bloque de Gases (EQUILIBRIUM_PHASES)
    if modo_gas == "CO2_PROFUNDO" or modo_ph == "REEQUILIBRIO_GAS":
        if not (pd.notnull(row.get("P_CO2_profunda_bar")) and float(row["P_CO2_profunda_bar"]) > 0):
            # ADR-002: no se omite en silencio el reequilibrio pedido
            msg = f"modo {modo_ph}/{modo_gas} sin P_CO2_profunda_bar; se calcula sin reequilibrio con CO2."
            print(f"[!] Aviso {muestra}: {msg}")
            if notices is not None:
                notices.append(msg)
        else:
            log_pco2 = np.log10(float(row["P_CO2_profunda_bar"]))
            lines.extend([
                "",
                "EQUILIBRIUM_PHASES 1",
                f"    CO2(g)      {log_pco2:.4f}"
            ])

    # 6. Salida Seleccionada y Minerales Dinámicos desde Hoja 'Minerales_Objetivo'
    min_phases = list(active_minerals["Fase_PHREEQC"].astype(str).str.strip())
    headings = [f"si_{m}" for m in min_phases]

    lines.extend([
        "",
        "SELECTED_OUTPUT 1",
        "    -reset          false",
        "    -ph             true",
        "    -charge_balance true",
        "    -percent_error  true",
        "    -ionic_strength true",
        "    -user_punch     true",
        "",
        "USER_PUNCH 1",
        f"    -headings {' '.join(headings)}"
    ])

    for i, m_phase in enumerate(min_phases, start=1):
        lines.append(f"    {i * 10} PUNCH SI(\"{m_phase}\")")

    lines.append("END\n")
    return "\n".join(lines), headings


def write_selected_output(array, path):
    """SELECTED_OUTPUT como texto UTF-8 separado por tabuladores (encabezados + filas) (ADR-004)."""
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for line in array or []:
            fh.write("\t".join("" if v is None else str(v) for v in line) + "\n")


def run_sample(input_string, db_text, export_dir=None, stem=None):
    """Corre una entrada de PHREEQC en una carpeta temporal propia (ADR-004).

    Parameters
    ----------
    input_string : str
        Entrada de PHREEQC.
    db_text : str
        Texto de la base, ya comprobado por ``load_database_text``.
    export_dir, stem : str, optional
        Si se dan, escribe en ``export_dir`` ``<stem>_entrada.txt``, ``<stem>_salida.txt`` y
        ``<stem>_selected_output.txt`` (texto UTF-8).

    Returns
    -------
    tuple
        (arreglo de SELECTED_OUTPUT, avisos de PHREEQC en una línea, fases del catálogo que no están en la base).
    """
    export = bool(export_dir and stem)
    with isolated_workdir() as tmp:
        phreeqc = IPhreeqc()
        try:
            phreeqc.load_database_string(db_text)
            if export:
                phreeqc.set_output_file_on()
                with open(os.path.join(export_dir, f"{stem}_entrada.txt"), "w", encoding="utf-8", newline="\n") as fh:
                    fh.write(input_string)
            phreeqc.run_string(input_string)
            warnings, missing = phreeqc_warnings(phreeqc)
            selected = phreeqc.get_selected_output_array()
        finally:
            phreeqc.destroy_iphreeqc()
        if export:
            outs = sorted(glob.glob(os.path.join(tmp, "phreeqc*.out")))
            if outs:
                copy_as_utf8(outs[-1], os.path.join(export_dir, f"{stem}_salida.txt"))
            write_selected_output(selected, os.path.join(export_dir, f"{stem}_selected_output.txt"))
    return selected, warnings, missing


def run_universal_engine(excel_path, output_excel, output_csv):
    """Ejecuta la simulación universal y construye el reporte de auditoría QC."""
    # Rutas absolutas: cada muestra corre en su carpeta temporal (ADR-004).
    excel_path, output_excel, output_csv = (os.path.abspath(p) for p in (excel_path, output_excel, output_csv))
    config, active_minerals, df_data = load_excel_configuration(excel_path)
    db_cache = {}
    bases = sorted({database_for_row(r, config) for _, r in df_data.iterrows()})
    for name in bases:  # falla temprano y con un mensaje claro si una base no carga
        load_database_text(name, db_cache)
    trace, trace_warnings = build_traceability(excel_path, bases)
    for msg in trace_warnings:
        print(f"[!] {msg}")

    export_out = str(config.get("EXPORTAR_REPORTES_OUT", "SI")).upper().strip() == "SI"
    tol_is = float(config.get("TOLERANCIA_QC_IS", 0.30))
    tol_ph = float(config.get("TOLERANCIA_QC_PH", 0.15))

    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    os.makedirs(os.path.dirname(output_excel), exist_ok=True)

    results = []
    used_names = {}
    missing_phases = {}  # {base: fases del catálogo que no existen en ella} (ADR-004)
    errors = []
    print(f"[-] Procesando {len(df_data)} muestras con la(s) base(s): {', '.join(bases)}...")

    for idx, row in df_data.iterrows():
        muestra = str(row["Muestra"]).strip()
        notices = []
        input_string, headings = build_dynamic_phreeqc_input(row, config, active_minerals, notices)
        db_name = database_for_row(row, config)

        export_dir = stem = None
        if export_out:
            project = safe_filename(row.get("Proyecto") if pd.notnull(row.get("Proyecto")) else "sin_proyecto")
            export_dir = os.path.join(REPORTS_PHREEQC_DIR, project)
            os.makedirs(export_dir, exist_ok=True)
            stem = safe_filename(muestra, used_names.setdefault(project.lower(), set()))

        try:
            selected_output, warnings, missing = run_sample(input_string, db_cache[db_name], export_dir, stem)
            missing_phases.setdefault(db_name, set()).update(missing)
            if warnings:
                notices.append(f"PHREEQC: {warnings}")
            if selected_output and len(selected_output) > 1:
                raw_headers = selected_output[0]
                raw_values = selected_output[-1]
                full_dict = {str(k).lower().strip(): v for k, v in zip(raw_headers, raw_values)}

                row_res = {
                    "Proyecto": row.get("Proyecto"),
                    "Area": row.get("Area"),
                    "Muestra": muestra,
                    "Tipo_Manantial": row.get("Tipo_Manantial"),
                    "Modo_pH": row.get("Modo_pH"),
                    "T_C": row.get("T_C"),
                    "pH_superficie": row.get("pH_superficie"),
                    "pH_calculado": full_dict.get("ph", np.nan),
                    "pH_Ref": row.get("pH_Ref", np.nan),
                    "Balance_Carga_eq": full_dict.get("charge(eq)", full_dict.get("cb", np.nan)),
                    "Error_Balance_%": full_dict.get("pct_err", np.nan),
                    "Fuerza_Ionica_mu": full_dict.get("mu", np.nan),
                    "Base_Datos": db_name,  # ADR-002
                    "Nota_Datos": row.get("Nota_Datos"),
                }

                # Evaluar QC de pH si existe pH_Ref (ej. Tabla 7 de Agua Agria - El Aguajito)
                if pd.notnull(row_res["pH_Ref"]) and pd.notnull(row_res["pH_calculado"]):
                    delta_ph = row_res["pH_calculado"] - float(row_res["pH_Ref"])
                    row_res["Delta_pH"] = round(delta_ph, 4)
                    row_res["QC_pH"] = "PASA" if abs(delta_ph) <= tol_ph else "REVISAR"
                else:
                    row_res["Delta_pH"] = np.nan
                    row_res["QC_pH"] = "S/D"

                # Extraer minerales activos y evaluar QC contra columnas de referencia si existen
                for _, min_row in active_minerals.iterrows():
                    m_phase = str(min_row["Fase_PHREEQC"]).strip()
                    col_si = f"si_{m_phase}"
                    col_ref = str(min_row.get("Columna_Referencia_QC", "")).strip()

                    val_si = full_dict.get(col_si.lower(), np.nan)
                    # En PHREEQC, -999 o <-90 significa que falta un elemento para formar el mineral
                    if pd.notnull(val_si) and float(val_si) < -90.0:
                        val_si = np.nan
                    row_res[col_si] = val_si

                    if col_ref and col_ref in row and pd.notnull(row[col_ref]) and pd.notnull(val_si):
                        ref_val = float(row[col_ref])
                        delta_si = val_si - ref_val
                        row_res[col_ref] = ref_val
                        row_res[f"Delta_{m_phase}"] = round(delta_si, 4)
                        row_res[f"QC_{m_phase}"] = "PASA" if abs(delta_si) <= tol_is else "REVISAR"

                row_res["Avisos"] = " || ".join(notices)  # ADR-004: avisos del motor y de PHREEQC
                if export_out:
                    row_res["Archivos_PHREEQC"] = display_path(os.path.join(export_dir, stem))
                results.append(row_res)

        except Exception as e:
            print(f"[!] Error en muestra {muestra}: {e}")
            errors.append(muestra)

    # ADR-004: si fallan todas las muestras no se escribe un CSV vacío en silencio.
    if len(df_data) and not results:
        raise RuntimeError(f"Fallaron las {len(df_data)} muestras (ver los mensajes «Error en muestra»). "
                           "No se escribieron resultados.")
    if errors:
        print(f"[!] {len(errors)} muestra(s) con error y sin resultados: {', '.join(errors)}")

    df_res = pd.DataFrame(results).round(4)
    df_res.to_csv(output_csv, index=False, encoding="utf-8")
    for name, phases in missing_phases.items():
        trace["bases"][name]["fases_no_encontradas"] = ", ".join(sorted(phases)) or "—"
    trace_json = os.path.splitext(output_csv)[0] + "_trazabilidad.json"
    with open(trace_json, "w", encoding="utf-8") as fh:
        json.dump(trace, fh, ensure_ascii=False, indent=1)

    with pd.ExcelWriter(output_excel, engine="openpyxl") as writer:
        df_res.to_excel(writer, sheet_name="Resultados_y_QC", index=False)
        items = list(config.items())
        items += [(f"BLOQUES_OMITIDOS_{name}", ", ".join(DATABASE_NOTES[name])) for name in bases if name in DATABASE_NOTES]
        df_cfg_out = pd.DataFrame(items, columns=["Parametro", "Valor_Usado"])
        df_cfg_out.to_excel(writer, sheet_name="Configuracion_Corrida", index=False)
        pd.DataFrame(traceability_rows(trace), columns=["Parametro", "Valor"]).to_excel(
            writer, sheet_name="Trazabilidad", index=False)

    print(f"[+] CSV universal guardado en: {output_csv}")
    print(f"[+] Trazabilidad guardada en: {trace_json}")
    print(f"[+] Reporte Excel universal guardado en: {output_excel}")
    if export_out:
        print(f"[+] Entradas y salidas de PHREEQC (texto UTF-8) en: {REPORTS_PHREEQC_DIR}")
    n_avisos = sum(bool(r.get("Avisos")) for r in results)
    if n_avisos:
        print(f"[!] {n_avisos} muestra(s) con avisos: ver la columna Avisos.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Motor Geoquímico Universal PHREEQC")
    parser.add_argument("--input", default=DEFAULT_TEMPLATE, help="Ruta del archivo Excel de entrada")
    parser.add_argument("--output", default=DEFAULT_OUTPUT_EXCEL, help="Ruta del reporte Excel de salida")
    parser.add_argument("--csv", default=DEFAULT_OUTPUT_CSV, help="Ruta del archivo CSV de salida")
    args = parser.parse_args()

    run_universal_engine(args.input, args.output, args.csv)
