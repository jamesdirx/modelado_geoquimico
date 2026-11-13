# -*- coding: utf-8 -*-
"""
Módulo para la carga y preprocesamiento de datos geoquímicos de la Puna.
"""

import os
import pandas as pd
import numpy as np

def create_raw_data_directories():
    """Asegura la existencia de las carpetas de datos."""
    os.makedirs("data/raw", exist_ok=True)
    os.makedirs("data/processed", exist_ok=True)

def generate_raw_puna_csv():
    """Genera de forma local el archivo de datos crudos de la Tabla 6-3 de la Puna Norte."""
    csv_path = "data/raw/punanorte_tabla6_3.csv"
    if os.path.exists(csv_path):
        print(f"[-] El archivo {csv_path} ya existe.")
        return

    # Datos estructurados extraídos de la Tesis 2018 (Tabla 6-3, página 159)
    # Reemplazamos los 'N.D.' por NaN de numpy para facilitar la limpieza posterior
    data = {
        "Area": ["TR", "TR", "TR", "TAC", "TAC", "TAC", "TJ", "TCA", "TCA", "TCA", "TPA", "TPA", "TPA", "SA"],
        "Muestra": ["RE1", "RE2", "RE3", "AC1", "ACF", "LC", "J", "CA1", "CA2", "CA3", "PA1", "PA2", "PA3", "SA"],
        "Tipo": ["MT", "MF", "MF", "MT", "MT", "Rio", "MT", "MT", "MT", "MT", "MT", "MT", "MT", "Pozo"],
        "Zona": ["CO", "CO", "CO", "SS", "SS", "SS", "SS", "SS", "SS", "SS", "SB", "SB", "SB", "SB"],
        "Altitud_msnm": [1766, 1794, 1794, 650, 598, 635, 786, 310, 310, 393, 842, 844, 846, 556],
        "T_C": [47.9, 22.3, 21.3, 28.5, 29.0, 22.1, 28.7, 49.3, 43.3, 49.0, 41.7, 47.9, 42.1, 72.0],
        "pH": [7.69, 8.32, 8.35, 7.54, 7.74, 6.95, 7.11, 7.88, 8.14, 8.21, 6.71, 6.66, 6.59, 7.49],
        "HCO3_mgL": [207, 46, 44, 208, 177, 332, 467.26, 177, 187, 213, 1114, 1232, 1104, 316],
        "F_mgL": [0.661, 0.401, 0.254, 0.311, 0.218, 0.677, 1.306, 2.9, 2.9, 3.7, 2.7, 2.6, 2.4, 1.3],
        "Cl_mgL": [18.81, 2.96, 5.3, 10.47, 3.57, 8.48, 749.7, 221, 225, 235, 502, 594, 465, 137],
        "SO4_mgL": [476, 10.48, 13.9, 34.5, 22.3, 30.29, 701.2, 459, 476, 532, 1058, 1108, 988, 210],
        "Ca_mgL": [65.2, 8.0, 9.0, 46.7, 32.73, 64.7, 104.3, 21.0, 22.0, 21.0, 163.0, 191.0, 158.0, 62.0],
        "Mg_mgL": [8.17, 4.84, 5.0, 7.6, 4.6, 17.42, 34.15, 0.64, 0.84, 0.72, 38.3, 42.8, 36.2, 18.0],
        "Na_mgL": [211, 5.76, 5.4, 31, 31.8, 26.64, 860, 389, 414, 480, 910, 1054, 887, 171],
        "K_mgL": [11.0, 2.75, 2.4, 4.31, 3.066, 4.7, 21.26, 3.7, 3.3, 2.3, 61.5, 62.3, 53.6, 20.0],
        "Li_mgL": [0.21, 0.18, 0.08, 0.15, 0.09, 0.11, 1.62, 0.17, 0.27, 0.25, 3.5, 3.8, 3.3, 0.31],
        "SiO2_mgL": [52.0, 42.0, 43.0, 51.0, 48.0, 41.0, 46.0, 112.0, 107.0, 115.0, 136.0, 131.0, 135.0, 51.0],
        "B_mgL": [0.31, 0.25, 0.12, 0.41, 0.35, 0.51, 0.88, 0.85, 0.77, 0.93, 1.6, 1.7, 1.5, 0.31],
        "TDS_mgL": [1054, 131, 135, 397, 326, 527, 2995, 1392, 1443, 1610, 3999, 4432, 3841, 992]
    }
    
    df = pd.DataFrame(data)
    df.to_csv(csv_path, index=False, encoding="utf-8")
    print(f"[+] Archivo crudo generado exitosamente en: {csv_path}")

def clean_and_prepare_data():
    """Lee el archivo crudo, aplica limpieza de datos y lo guarda para PHREEQC."""
    generate_raw_puna_csv()
    csv_path = "data/raw/punanorte_tabla6_3.csv"
    
    df = pd.read_csv(csv_path)
    
    # En caso de datos vacíos, los rellenamos con valores pequeños de detección estándar (p. ej. 1e-5)
    # para evitar que PHREEQC detenga los cálculos numéricos.
    df = df.fillna(1e-5)
    
    output_path = "data/processed/puna_clean.csv"
    df.to_csv(output_path, index=False, encoding="utf-8")
    print(f"[+] Archivo procesado y limpio guardado en: {output_path}")
    return df

if __name__ == "__main__":
    create_raw_data_directories()
    clean_and_prepare_data()
