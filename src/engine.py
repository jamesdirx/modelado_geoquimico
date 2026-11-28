# -*- coding: utf-8 -*-
"""
Motor Geoquímico Universal dirigido por catálogos en Excel (Data-Driven Engine).
Soporta múltiples modelos termodinámicos (Puna Norte, Caldera El Aguajito y nuevos proyectos)
sin modificar el código fuente.
"""

import os
import glob
import shutil
import argparse
import urllib.request
import pandas as pd
import numpy as np
from phreeqpy.iphreeqc.phreeqc_dll import IPhreeqc

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_TEMPLATE = os.path.join(BASE_DIR, "data", "raw", "Plantilla_Modelado_Geoquimico.xlsx")
DEFAULT_OUTPUT_EXCEL = os.path.join(BASE_DIR, "reports", "Reporte_Universal_Geoquimico.xlsx")
DEFAULT_OUTPUT_CSV = os.path.join(BASE_DIR, "data", "processed", "resultados_universales_phreeqc.csv")


def database_for_row(row, config):
    """Base termodinámica de la fila: columna Base_Datos si está llena; si no, BASE_DATOS_ACTIVA (ADR-002)."""
    value = row.get("Base_Datos")
    if value is not None and pd.notnull(value) and str(value).strip():
        return str(value).strip()
    return str(config.get("BASE_DATOS_ACTIVA", "wateq4f.dat")).strip()


def load_database_text(db_name, cache):
    """Texto de la base (con caché) tras comprobar que IPhreeqc la carga sin errores (ADR-002)."""
    if db_name not in cache:
        with open(ensure_database(db_name), "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
        probe = IPhreeqc()
        try:
            probe.load_database_string(text)
            errors = probe.get_error_string().strip()
        finally:
            probe.destroy_iphreeqc()
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


def build_dynamic_phreeqc_input(row, config, active_minerals):
    """Construye el bloque SOLUTION, EQUILIBRIUM_PHASES y USER_PUNCH según los catálogos de la fila."""
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
            print(f"[!] Aviso {muestra}: modo {modo_ph}/{modo_gas} sin P_CO2_profunda_bar; se calcula sin reequilibrio con CO2.")
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


def run_universal_engine(excel_path, output_excel, output_csv):
    """Ejecuta la simulación universal y construye el reporte de auditoría QC."""
    config, active_minerals, df_data = load_excel_configuration(excel_path)
    db_cache = {}
    bases = sorted({database_for_row(r, config) for _, r in df_data.iterrows()})
    for name in bases:  # falla temprano y con un mensaje claro si una base no carga
        load_database_text(name, db_cache)

    export_out = str(config.get("EXPORTAR_REPORTES_OUT", "SI")).upper().strip() == "SI"
    tol_is = float(config.get("TOLERANCIA_QC_IS", 0.30))
    tol_ph = float(config.get("TOLERANCIA_QC_PH", 0.15))

    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    os.makedirs(os.path.dirname(output_excel), exist_ok=True)

    results = []
    print(f"[-] Procesando {len(df_data)} muestras con la(s) base(s): {', '.join(bases)}...")

    for idx, row in df_data.iterrows():
        muestra = str(row["Muestra"]).strip()
        input_string, headings = build_dynamic_phreeqc_input(row, config, active_minerals)
        db_name = database_for_row(row, config)

        phreeqc = IPhreeqc()
        try:
            phreeqc.load_database_string(db_cache[db_name])
            if export_out:
                try:
                    phreeqc.set_output_file_on()
                except Exception:
                    pass

            phreeqc.run_string(input_string)

            if export_out:
                for gen_out in glob.glob("phreeqc*.out"):
                    target_out = os.path.join(BASE_DIR, "data", "processed", f"reporte_nativo_{muestra}.out")
                    shutil.move(gen_out, target_out)

            selected_output = phreeqc.get_selected_output_array()
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

                results.append(row_res)

        except Exception as e:
            print(f"[!] Error en muestra {muestra}: {e}")
        finally:
            phreeqc.destroy_iphreeqc()

    df_res = pd.DataFrame(results).round(4)
    df_res.to_csv(output_csv, index=False, encoding="utf-8")

    with pd.ExcelWriter(output_excel, engine="openpyxl") as writer:
        df_res.to_excel(writer, sheet_name="Resultados_y_QC", index=False)
        df_cfg_out = pd.DataFrame(list(config.items()), columns=["Parametro", "Valor_Usado"])
        df_cfg_out.to_excel(writer, sheet_name="Configuracion_Corrida", index=False)

    print(f"[+] CSV universal guardado en: {output_csv}")
    print(f"[+] Reporte Excel universal guardado en: {output_excel}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Motor Geoquímico Universal PHREEQC")
    parser.add_argument("--input", default=DEFAULT_TEMPLATE, help="Ruta del archivo Excel de entrada")
    parser.add_argument("--output", default=DEFAULT_OUTPUT_EXCEL, help="Ruta del reporte Excel de salida")
    parser.add_argument("--csv", default=DEFAULT_OUTPUT_CSV, help="Ruta del archivo CSV de salida")
    args = parser.parse_args()

    run_universal_engine(args.input, args.output, args.csv)
