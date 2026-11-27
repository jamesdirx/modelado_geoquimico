# -*- coding: utf-8 -*-
"""
Módulo para el modelado en lote de PHREEQC sobre muestras de la Puna,
integrando reequilibrio de gases (CO2 profundo), balance de C(4) y metales traza.
"""

import os
import shutil
import glob
import urllib.request
import pandas as pd
import numpy as np
from phreeqpy.iphreeqc.phreeqc_dll import IPhreeqc

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_URL = "https://raw.githubusercontent.com/usgs-coupled/iphreeqc/master/database/wateq4f.dat"
DB_PATH = os.path.join(BASE_DIR, "database", "wateq4f.dat")
DATA_PATH = os.path.join(BASE_DIR, "data", "processed", "puna_clean.csv")
OUTPUT_PATH = os.path.join(BASE_DIR, "data", "processed", "puna_speciation_results.csv")


def ensure_database():
    """Descarga la base de datos termodinámica wateq4f si no está localmente."""
    db_dir = os.path.dirname(DB_PATH)
    if not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

    if not os.path.exists(DB_PATH) or os.path.getsize(DB_PATH) == 0:
        print("[-] Descargando la base de datos termodinámica wateq4f.dat de USGS...")
        urllib.request.urlretrieve(DB_URL, DB_PATH)
        print(f"[+] Base de datos guardada exitosamente en {DB_PATH}")
    else:
        print("[+] Base de datos wateq4f.dat detectada de manera local.")


def get_safe_val(row, col_names, default_val):
    """Obtiene un valor numérico seguro probando múltiples nombres de columna."""
    for c in col_names:
        if c in row and pd.notnull(row[c]):
            return float(row[c])
    return default_val


def build_phreeqc_input(row):
    """Construye el archivo de entrada de PHREEQC para cada muestra."""
    p_co2_mapping = {
        "RE1": 0.032, "RE2": 0.020, "RE3": 0.020,
        "AC1": 0.018, "ACF": 0.027, "LC": 0.022,
        "J": 0.0046, "CA1": 0.011, "CA2": 0.0089, "CA3": 0.014,
        "PA1": 0.018, "PA2": 0.019, "PA3": 0.020, "SA": 0.027
    }
    muestra = str(row["Muestra"]).strip()
    p_co2 = p_co2_mapping.get(muestra, 0.01)
    log_pco2 = np.log10(p_co2)

    ph_val = get_safe_val(row, ["pH", "pH_superficie"], 7.0)

    # Conversión de trazas de ug/L a mg/L
    fe_mg = get_safe_val(row, ["Fe_ugL"], 50.0) / 1000.0
    mn_mg = get_safe_val(row, ["Mn_ugL"], 5.0) / 1000.0
    zn_mg = get_safe_val(row, ["Zn_ugL"], 10.0) / 1000.0
    cu_mg = get_safe_val(row, ["Cu_ugL"], 2.0) / 1000.0
    ni_mg = get_safe_val(row, ["Ni_ugL"], 1.0) / 1000.0
    pb_mg = get_safe_val(row, ["Pb_ugL"], 2.0) / 1000.0
    ba_mg = get_safe_val(row, ["Ba_ugL"], 100.0) / 1000.0
    as_mg = get_safe_val(row, ["As_ugL"], 50.0) / 1000.0

    solution_template = f"""
    TITLE Reequilibrio Geotérmico Profundo y Metalogénesis - Muestra {muestra}
    SOLUTION 1
        temp        {row['T_C']}
        pH          {ph_val}
        units       mg/l
        F           {row['F_mgL']}
        Cl          {row['Cl_mgL']}
        S(6)        {row['SO4_mgL']}
        Ca          {row['Ca_mgL']}
        Mg          {row['Mg_mgL']}
        Na          {row['Na_mgL']}
        K           {row['K_mgL']}
        Li          {row['Li_mgL']}
        C(4)        {row['HCO3_mgL']} as HCO3
        Si          {row['SiO2_mgL']} as SiO2
        B           {row['B_mgL']}
        Fe          {fe_mg:.6f}
        Mn          {mn_mg:.6f}
        Zn          {zn_mg:.6f}
        Cu          {cu_mg:.6f}
        Ni          {ni_mg:.6f}
        Pb          {pb_mg:.6f}
        Ba          {ba_mg:.6f}
        As          {as_mg:.6f}
        S(-2)       0.01

    EQUILIBRIUM_PHASES 1
        CO2(g)      {log_pco2:.4f}

    PRINT
        -reset      true
        -species    true
        -saturation_indices true

    SELECTED_OUTPUT 1
        -reset          false
        -ph             true
        -charge_balance true
        -ionic_strength true
        -user_punch     true

    USER_PUNCH 1
        -headings si_Calcite si_Aragonite si_Gypsum si_Anhydrite si_Chalcedony si_Quartz si_Halite si_Hematite si_Magnetite si_Sphalerite si_Galena si_Pyrite si_Covellite
        10 PUNCH SI("Calcite")
        20 PUNCH SI("Aragonite")
        30 PUNCH SI("Gypsum")
        40 PUNCH SI("Anhydrite")
        50 PUNCH SI("Chalcedony")
        60 PUNCH SI("Quartz")
        70 PUNCH SI("Halite")
        80 PUNCH SI("Hematite")
        90 PUNCH SI("Magnetite")
        100 PUNCH SI("Sphalerite")
        110 PUNCH SI("Galena")
        120 PUNCH SI("Pyrite")
        130 PUNCH SI("Covellite")
    END
    """
    return solution_template


def run_speciation():
    """Ejecuta la especiación en lote y prueba la exportación de reportes .out."""
    ensure_database()

    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(f"No se encontró el archivo de datos: {DATA_PATH}. Ejecuta src/loader.py primero.")

    df = pd.read_csv(DATA_PATH)
    results = []

    with open(DB_PATH, "r", encoding="utf-8", errors="ignore") as f:
        db_string = f.read()

    print("[-] Iniciando cálculos de especiación geoquímica...")

    for idx, row in df.iterrows():
        muestra = str(row["Muestra"]).strip()
        input_string = build_phreeqc_input(row)

        phreeqc = IPhreeqc()
        try:
            if idx == 0:
                metodos = [m for m in dir(phreeqc) if not m.startswith("_")]
                print(f"[*] Métodos disponibles en IPhreeqc: {metodos}")

            phreeqc.load_database_string(db_string)

            # Activar escritura de archivo .out sin argumentos (según API phreeqpy)
            try:
                phreeqc.set_output_file_on()
            except Exception as e_out:
                if idx == 0:
                    print(f"[!] Aviso al activar set_output_file_on: {e_out}")

            phreeqc.run_string(input_string)

            # Mover archivo phreeqc.*.out generado en la raíz hacia data/processed/
            for generated_out in glob.glob("phreeqc*.out"):
                target_out = os.path.join(BASE_DIR, "data", "processed", f"reporte_nativo_{muestra}.out")
                shutil.move(generated_out, target_out)

            selected_output = phreeqc.get_selected_output_array()

            if selected_output and len(selected_output) > 1:
                raw_headers = selected_output[0]
                raw_values = selected_output[-1]

                full_dict = {str(k).lower().strip(): v for k, v in zip(raw_headers, raw_values)}

                target_headings = [
                    "si_Calcite", "si_Aragonite", "si_Gypsum", "si_Anhydrite",
                    "si_Chalcedony", "si_Quartz", "si_Halite", "si_Hematite",
                    "si_Magnetite", "si_Sphalerite", "si_Galena", "si_Pyrite",
                    "si_Covellite"
                ]

                ph_sup = get_safe_val(row, ["pH", "pH_superficie"], 7.0)

                row_results = {
                    "Area": row["Area"],
                    "Muestra": muestra,
                    "T_C": row["T_C"],
                    "pH_superficie": ph_sup,
                    "pH_profundo": full_dict.get("ph", np.nan),
                    "Balance_Carga_eq": full_dict.get("charge(eq)", full_dict.get("cb", np.nan)),
                    "mu": full_dict.get("mu", np.nan)
                }

                for h in target_headings:
                    row_results[h] = full_dict.get(h.lower().strip(), np.nan)

                results.append(row_results)
            else:
                print(f"[!] No se obtuvieron resultados en selected_output para {muestra}")

        except Exception as e:
            print(f"[!] Error procesando la muestra {muestra}: {e}")
        finally:
            phreeqc.destroy_iphreeqc()

    res_df = pd.DataFrame(results)
    res_df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8")
    print(f"\n[+] Especiación finalizada. {len(res_df)} muestras guardadas en: {OUTPUT_PATH}")

    preview_cols = ["Area", "Muestra", "pH_profundo", "si_Calcite", "si_Gypsum", "si_Pyrite"]
    cols_to_show = [c for c in preview_cols if c in res_df.columns]
    if not res_df.empty:
        print("\n📊 Resumen de los resultados con pH recalculado de reservorio:")
        print(res_df[cols_to_show].head().to_string(index=False))


if __name__ == "__main__":
    run_speciation()
