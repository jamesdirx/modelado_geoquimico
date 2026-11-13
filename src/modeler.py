# -*- coding: utf-8 -*-
"""
Módulo para la ejecución del motor PHREEQC sobre los datos de la Puna.
"""

import os
import urllib.request
import pandas as pd
from phreeqpy.iphreeqc.phreeqc_dll import IPhreeqc

# Rutas absolutas para evitar discrepancias de rutas en Windows
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
    Construye la cadena de texto con el formato SOLUTION nativo de PHREEQC
    para una muestra dada de la Tabla 6-3.
    """
    solution_template = f"""
    TITLE Modelado de muestra {row['Muestra']} - {row['Area']}
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
        Alkalinity  {row['HCO3_mgL']} as HCO3
        Si          {row['SiO2_mgL']} as SiO2
        B           {row['B_mgL']}
    
    SELECTED_OUTPUT
        -reset                false
        -charge_balance       true
        -ionic_strength       true
        -saturation_indices   Calcite Aragonite Gypsum Chalcedony Quartz Barite
    END
    """
    return solution_template

def run_speciation():
    """Ejecuta la especiación en lote usando phreeqpy e IPhreeqc."""
    ensure_database()
    
    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(f"No se encontró el archivo de datos: {DATA_PATH}. Ejecuta src/loader.py primero.")
        
    df = pd.read_csv(DATA_PATH)
    results = []
    
    # 1. Leer el archivo wateq4f.dat como texto directo
    with open(DB_PATH, "r", encoding="utf-8", errors="ignore") as f:
        db_string = f.read()

    # 2. Inicializar el motor PHREEQC UNA SOLA VEZ fuera del bucle
    phreeqc = IPhreeqc()
    print("[-] Cargando base de datos termodinámica en memoria...")
    phreeqc.load_database_string(db_string)
    
    print("[-] Iniciando cálculos de especiación geoquímica en lote...")
    
    try:
        for idx, row in df.iterrows():
            input_string = build_phreeqc_input(row)
            
            try:
                phreeqc.run_string(input_string)
                selected_output = phreeqc.get_selected_output_array()
                
                # selected_output[0] contiene los encabezados
                # selected_output contiene los valores numéricos
                headers = selected_output[0]
                values = selected_output
                
                row_results = {
                    "Area": row["Area"],
                    "Muestra": row["Muestra"],
                    "T_C": row["T_C"],
                    "pH": row["pH"]
                }
                
                for h, val in zip(headers, values):
                    row_results[h] = val
                    
                results.append(row_results)
                
            except Exception as e:
                print(f"[!] Error procesando la muestra {row['Muestra']}: {e}")
                
    finally:
        # Destruir la instancia de C al finalizar todo el lote
        phreeqc.destroy_iphreeqc()
            
    # Guardar los resultados consolidados
    res_df = pd.DataFrame(results)
    res_df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8")
    print(f"\n[+] Especiación finalizada. Resultados guardados en: {OUTPUT_PATH}")
    
    # Mostrar resumen con nombres exactos de columnas de PHREEQC
    cols_to_show = [c for c in ["Area", "Muestra", "charge_balance", "si_Calcite", "si_Chalcedony", "si_Gypsum"] if c in res_df.columns]
    print("\n📊 Resumen de los primeros resultados:")
    print(res_df[cols_to_show].head().to_string(index=False))

if __name__ == "__main__":
    run_speciation()
