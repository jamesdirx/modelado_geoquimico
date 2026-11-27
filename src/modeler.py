# -*- coding: utf-8 -*-
"""
Módulo avanzado para el modelado en lote de PHREEQC sobre muestras de la Puna,
integrando reequilibrio de gases (CO2 profundo) y balance de C(4).
"""

import os
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

def build_phreeqc_input(row):
    """
    Construye el archivo de entrada de PHREEQC para cada muestra.
    Reequilibra con CO2(g) para restaurar el pH de reservorio profundo y
    especia elementos mayoritarios, trazas y sulfuros metálicos.
    """
    # Mapeo de presiones parciales de CO2 (P_CO2) de la Tabla 6-5 de la Tesis
    p_co2_mapping = {
        "RE1": 0.032,
        "RE2": 0.020,
        "RE3": 0.020,
        "AC1": 0.018,
        "ACF": 0.027,
        "LC": 0.022,
        "J": 0.0046,
        "CA1": 0.011,
        "CA2": 0.0089,
        "CA3": 0.014,
        "PA1": 0.018,
        "PA2": 0.019,
        "PA3": 0.020,
        "SA": 0.027
    }
    p_co2 = p_co2_mapping.get(row['Muestra'], 0.01)
    log_pco2 = np.log10(p_co2)

    # Conversión segura de trazas de ug/L a mg/L para la entrada de PHREEQC
    fe_mg = row.get("Fe_ugL", 10.0) / 1000.0 if pd.notnull(row.get("Fe_ugL")) else 0.01
    mn_mg = row.get("Mn_ugL", 5.0) / 1000.0 if pd.notnull(row.get("Mn_ugL")) else 0.005
    zn_mg = row.get("Zn_ugL", 5.0) / 1000.0 if pd.notnull(row.get("Zn_ugL")) else 0.005
    as_mg = row.get("As_ugL", 10.0) / 1000.0 if pd.notnull(row.get("As_ugL")) else 0.01
    
    # Especies adicionales (Co, Ni, Cu, Ba, Sb)
    co_mg = row.get("Co_ugL", 1.0) / 1000.0 if pd.notnull(row.get("Co_ugL")) else 0.001
    ni_mg = row.get("Ni_ugL", 1.0) / 1000.0 if pd.notnull(row.get("Ni_ugL")) else 0.001
    cu_ug = row.get("Cu_ugL", 1.0) if pd.notnull(row.get("Cu_ugL")) else 1.0
    cu_mg = cu_ug / 1000.0
    ba_mg = row.get("Ba_ugL", 100.0) / 1000.0 if pd.notnull(row.get("Ba_ugL")) else 0.1
    sb_mg = row.get("Sb_ugL", 5.0) / 1000.0 if pd.notnull(row.get("Sb_ugL")) else 0.005

    solution_template = f"""
    TITLE Reequilibrio Geotérmico Profundo y Metalogénesis - Muestra {row['Muestra']}
    SOLUTION {row.name + 1}
        temp        {row['T_C']}
        pH          {row['pH']}
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
        As          {as_mg:.6f}
        Ba          {ba_mg:.6f}
        S(-2)       0.01                     # Declaración de traza de sulfuro para minerales reductores
    
    EQUILIBRIUM_PHASES {row.name + 1}
        CO2(g)      {log_pco2:.4f}
    
    SELECTED_OUTPUT 1
        -reset          false
        -ph             true
        -charge_balance true
        -ionic_strength true
        -user_punch     true

    USER_PUNCH 1
        -headings si_Calcite si_Aragonite si_Gypsum si_Anhydrite si_Chalcedony si_Quartz si_Halite si_Hematite si_Magnetite si_Sphalerite si_Galena si_Pyrite si_Millerite si_Alabandite si_Covellite
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
        130 PUNCH SI("Millerite")
        140 PUNCH SI("Alabandite")
        150 PUNCH SI("Covellite")
    END
    """
    return solution_template

def run_speciation():
    """Ejecuta la especiación en lote con reequilibrio de gas y mapeo insensible a mayúsculas/minúsculas."""
    ensure_database()
    
    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(f"No se encontró el archivo de datos: {DATA_PATH}. Ejecuta src/loader.py primero.")
        
    df = pd.read_csv(DATA_PATH)
    results = []
    
    with open(DB_PATH, "r", encoding="utf-8", errors="ignore") as f:
        db_string = f.read()
    
    print("[-] Iniciando cálculos de especiación geoquímica con reequilibrio de gases...")
    
    for idx, row in df.iterrows():
        input_string = build_phreeqc_input(row)
        
        phreeqc = IPhreeqc()
        try:
            phreeqc.load_database_string(db_string)
            phreeqc.run_string(input_string)
            
            err = phreeqc.get_error_string()
            if err.strip():
                print(f"[Aviso PHREEQC - {row['Muestra']}]: {err.strip()}")
            
            selected_output = phreeqc.get_selected_output_array()
            
            if selected_output and len(selected_output) > 1:
                raw_headers = selected_output[0]
                # CORRECCIÓN: Usamos [-1] para asegurar la extracción del paso de equilibrio final
                raw_values = selected_output[-1]            
                
                # Crear diccionario en minúsculas para evitar discrepancias de mayúsculas/minúsculas de PHREEQC
                full_dict = {str(k).lower().strip(): v for k, v in zip(raw_headers, raw_values)}
                
                target_headings = ["pH_profundo", "mu", "charge(eq)", "si_Calcite", "si_Aragonite", "si_Gypsum", 
                                   "si_Anhydrite", "si_Chalcedony", "si_Quartz", "si_Halite", "si_Hematite",
                                    "si_Magnetite", "si_Sphalerite", "si_Galena", "si_Pyrite", "si_Millerite", 
                                    "si_Alabandite", "si_Covellite"]
                
                row_results = {
                    "Area": row["Area"],
                    "Muestra": row["Muestra"],
                    "T_C": row["T_C"],
                    "pH_superficie": row["pH"]
                }
                
                # Extraer usando claves en minúsculas
                for h in target_headings:
                    row_results[h] = full_dict.get(h.lower().strip(), np.nan)

                # pH nativo extraído directamente por PHREEQC (etiqueta 'ph')
                row_results["pH_profundo"] = full_dict.get("ph", full_dict.get("ph_profundo", np.nan))    

                results.append(row_results)
            else:
                print(f"[!] No se obtuvieron resultados para {row['Muestra']}")
                
        except Exception as e:
            print(f"[!] Error procesando la muestra {row['Muestra']}: {e}")
        finally:
            phreeqc.destroy_iphreeqc()
            
    res_df = pd.DataFrame(results)
    res_df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8")
    print(f"\n[+] Especiación finalizada. Resultados de reservorio guardados en: {OUTPUT_PATH}")
    print(f"[+] Columnas generadas en el CSV: {list(res_df.columns)}")
    
    preview_cols = ["Area", "Muestra", "pH_profundo", "si_Calcite", "si_Gypsum", "si_Chalcedony"]
    cols_to_show = [c for c in preview_cols if c in res_df.columns]
    print("\n📊 Resumen de los resultados con pH recalculado de reservorio:")
    print(res_df[cols_to_show].head().to_string(index=False))


if __name__ == "__main__":
    run_speciation()
