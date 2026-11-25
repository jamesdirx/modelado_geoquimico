# -*- coding: utf-8 -*-
"""
Módulo de utilidades para análisis visual y gráficos geoquímicos del proyecto.
"""

import os
import pandas as pd
import matplotlib.pyplot as plt

# Definición de rutas absolutas
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_PATH = os.path.join(BASE_DIR, "data", "processed", "puna_speciation_results.csv")
FIGURES_DIR = os.path.join(BASE_DIR, "reports", "figures")

def ensure_directories():
    """Asegura la existencia de la carpeta para guardar los reportes gráficos."""
    os.makedirs(FIGURES_DIR, exist_ok=True)

def generate_saturation_index_plots():
    """Carga los resultados de PHREEQC y genera gráficos de índices de saturación."""
    ensure_directories()
    
    if not os.path.exists(INPUT_PATH):
        raise FileNotFoundError(
            f"No se encontró el archivo de resultados: {INPUT_PATH}. "
            "Por favor, ejecuta primero 'python src/modeler.py' para generarlo."
        )
        
    df = pd.read_csv(INPUT_PATH)
    
    # Identificar nombres reales de columnas en la salida de PHREEQC
    # El motor genera columnas con formato "si_NombreMineral"
    calcita_col = [c for c in df.columns if "calcite" in c.lower()]
    yeso_col = [c for c in df.columns if "gypsum" in c.lower()]
    calcedonia_col = [c for c in df.columns if "chalcedony" in c.lower()]
    
    if not calcita_col or not yeso_col:
        print("[!] Advertencia: No se encontraron las columnas de índices de saturación en el CSV.")
        print(f"Columnas disponibles: {list(df.columns)}")
        return

    # Usamos el primer match encontrado para cada mineral
    si_calcita = calcita_col[0]
    si_yeso = yeso_col[0]
    si_calcedonia = calcedonia_col[0] if calcedonia_col else None

    # Configuración de estilo del gráfico
    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
    fig, ax = plt.subplots(figsize=(10, 7))

    # Mapeo de colores y marcadores por área geográfica de la Puna
    areas = df["Area"].unique()
    markers = ["o", "s", "^", "D", "v", "*", "p", "X"]
    colors = ["#e74c3c", "#3498db", "#2ecc71", "#9b59b6", "#f1c40f", "#1abc9c", "#e67e22", "#34495e"]

    for idx, area in enumerate(areas):
        sub_df = df[df["Area"] == area]
        ax.scatter(
            sub_df[si_calcita],
            sub_df[si_yeso],
            label=f"Zona {area}",
            s=120,
            edgecolors="black",
            linewidths=1.2,
            alpha=0.85,
            marker=markers[idx % len(markers)],
            color=colors[idx % len(colors)]
        )

    # Líneas de referencia de equilibrio termodinámico (IS = 0)
    ax.axhline(0, color="#2c3e50", linestyle="--", linewidth=1.5, label="Equilibrio Yeso")
    ax.axvline(0, color="#d35400", linestyle="--", linewidth=1.5, label="Equilibrio Calcita")

    # Anotaciones de las zonas de saturación
    ax.text(1.2, 0.5, "Sobresaturado en ambos\n(Precipitación activa)", fontsize=10, color="green", weight="bold")
    ax.text(-2.5, -2.5, "Subsataturo en ambos\n(Disolución/Sin depósitos)", fontsize=10, color="red", weight="bold")

    # Configuración de límites y etiquetas
    ax.set_title("Gráfico de Co-variación de Índices de Saturación: Calcita vs. Yeso\n(Sistemas Hidrotermales de la Puna)", fontsize=14, weight="bold", pad=15)
    ax.set_xlabel("Índice de Saturación de Calcita [log(IAP/K)]", fontsize=12)
    ax.set_ylabel("Índice de Saturación de Yeso [log(IAP/K)]", fontsize=12)
    
    ax.legend(loc="lower right", frameon=True, facecolor="white", edgecolor="gray")
    
    # Ajustar márgenes y guardar
    plt.tight_layout()
    plot_path = os.path.join(FIGURES_DIR, "calcita_vs_yeso.png")
    plt.savefig(plot_path, dpi=300)
    plt.close()
    
    print(f"[+] Gráfico generado exitosamente en: {plot_path}")

if __name__ == "__main__":
    generate_saturation_index_plots()
