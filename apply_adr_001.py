# -*- coding: utf-8 -*-
"""
apply_adr_001.py - modelado_geoquimico

ADR-001: corrige .gitignore y requirements.txt, y agrega README.md.

- .gitignore y requirements.txt contenian comandos de PowerShell en lugar de su
  contenido. Se reemplazan por la lista real de patrones y de dependencias
  (se agregan openpyxl y python-docx, que el codigo usa).
- README.md (vacio) pasa a documentar el proyecto.

Uso (desde la raiz del repositorio):
    python apply_adr_001.py --dry-run   # muestra que cambiaria, sin escribir
    python apply_adr_001.py             # aplica los cambios

Garantias:
- Idempotente: si los archivos ya tienen el contenido nuevo, no hace nada.
- Seguro: solo reemplaza un archivo si tiene el contenido danado conocido
  (o esta vacio, en el caso de README.md). Si encuentra otro contenido, se
  detiene sin escribir nada; --force lo reemplaza igual.
- Atomico: escribe todo o nada (restaura los originales si algo falla).
- Escribe UTF-8 sin BOM y saltos de linea LF.
"""
import argparse
import os
import sys
from pathlib import Path

NEW_CONTENT = {
    ".gitignore": "# Python\n__pycache__/\n*.py[cod]\n.pytest_cache/\n\n# Entornos virtuales\n.venv/\nvenv/\n\n# Jupyter\n.ipynb_checkpoints/\n\n# PHREEQC: archivos temporales que IPhreeqc deja en la carpeta de trabajo\n*.pqo\n*.pqi\n/phreeqc.*.out\n\n# Archivos de bloqueo de Excel/Word mientras están abiertos (Windows)\n~$*\n",
    "requirements.txt": "# Dependencias de modelado_geoquimico\n# Instalar con:  pip install -r requirements.txt\n\n# Núcleo del motor (src/engine.py)\npandas>=1.5.0\nnumpy>=1.20.0\nphreeqpy>=0.5.0          # incluye IPhreeqc para Windows, Linux y macOS\nopenpyxl>=3.0            # lectura de la plantilla y escritura de reportes .xlsx\n\n# Gráficos y documentos\nmatplotlib>=3.5.0        # src/utils.py\npython-docx>=0.8.11      # src/generar_guia_word.py\n\n# Desarrollo\nipykernel                # notebooks/\npytest                   # test/\n",
    "README.md": "# modelado_geoquimico\n\nMotor de especiación acuosa e índices de saturación mineral para aguas geotermales e hidrotermales, basado en **PHREEQC** (vía `phreeqpy`/IPhreeqc) y dirigido por una **plantilla Excel**. Las muestras, los modos de cálculo, los minerales y la base termodinámica se eligen en la plantilla, sin modificar el código. Cada corrida genera un reporte con control de calidad (QC) contra valores publicados.\n\nCasos incluidos en la plantilla:\n\n| Proyecto      | Muestras | Fuente de los datos                                                                 |\n|---------------|---------:|-------------------------------------------------------------------------------------|\n| `Puna_Norte`  | 14       | Peralta Arnold, Y. (2018), sistemas geotermales de la Puna Norte y Subandinos (Jujuy, Argentina). Química: Tabla 6-3; P_CO2: Tabla 6-5; IS de referencia: Tabla 6-7. |\n| `El_Aguajito` | 43       | Caldera El Aguajito. <!-- TODO: completar la referencia bibliográfica -->           |\n\nEl proyecto también servirá para casos de comparación con **SOLMINEQ.88 / SOLMINEQ-Py**.\n\n---\n\n## Contenido\n\n- [Qué hace](#qué-hace)\n- [Estructura del repositorio](#estructura-del-repositorio)\n- [Instalación](#instalación)\n- [Uso](#uso)\n- [Plantilla de entrada](#plantilla-de-entrada)\n- [Bases de datos termodinámicas](#bases-de-datos-termodinámicas)\n- [Salidas](#salidas)\n- [Control de calidad](#control-de-calidad)\n- [Scripts complementarios](#scripts-complementarios)\n- [Limitaciones conocidas](#limitaciones-conocidas)\n- [Referencias](#referencias)\n\n---\n\n## Qué hace\n\nPara cada muestra de la hoja `Datos_Agua`, `src/engine.py`:\n\n1. Arma un bloque `SOLUTION` de PHREEQC con temperatura, pH, pe, iones mayoritarios, sílice, boro, NH4, S(-2) y elementos traza.\n2. Aplica el **modo de pH**, el **modo de carbono** y el **modo de gas** de la fila. Por ejemplo, puede cerrar el balance de carga con el pH o reequilibrar con CO2(g) a una P_CO2 dada para estimar el pH profundo.\n3. Corre PHREEQC con la base termodinámica elegida y extrae el pH calculado, el balance de carga, el error de balance (%), la fuerza iónica y el **índice de saturación (IS = log IAP/K)** de cada mineral activo.\n4. Compara contra los valores de referencia de la plantilla (pH e IS) y marca cada resultado como `PASA`, `REVISAR` o `S/D`.\n5. Escribe un CSV, un reporte Excel y, si se pide, el archivo `.out` nativo de PHREEQC de cada muestra.\n\n## Estructura del repositorio\n\n```\nmodelado_geoquimico/\n├── data/\n│   ├── raw/\n│   │   ├── Plantilla_Modelado_Geoquimico.xlsx   # entrada principal del motor\n│   │   └── punanorte_tabla6_3.csv               # datos crudos Puna Norte (flujo anterior)\n│   └── processed/\n│       ├── resultados_universales_phreeqc.csv   # salida del motor\n│       └── reporte_nativo_<Muestra>.out         # salidas nativas de PHREEQC\n├── database/\n│   └── wateq4f.dat                              # base termodinámica (USGS)\n├── notebooks/\n├── reports/\n│   ├── Reporte_Universal_Geoquimico.xlsx        # reporte del motor\n│   └── figures/\n├── src/\n│   ├── engine.py               # motor principal (punto de entrada)\n│   ├── generar_guia_word.py    # genera la guía del caso de estudio (.docx)\n│   ├── utils.py                # gráfico IS calcita vs. yeso\n│   ├── loader.py               # flujo anterior (en retiro)\n│   ├── modeler.py              # flujo anterior (en retiro)\n│   └── reporter.py             # flujo anterior (en retiro)\n├── test/\n└── requirements.txt\n```\n\n> `loader.py`, `modeler.py` y `reporter.py` son el flujo anterior, solo para la Puna Norte. Su función quedó unificada en `engine.py` y se retirarán.\n\n## Instalación\n\nRequisitos:\n\n- **Python 3.10 o superior, de 64 bits.** Probado con Python 3.13.\n- **Git.**\n- No hace falta instalar PHREEQC aparte: `phreeqpy` incluye la librería IPhreeqc para Windows, Linux y macOS.\n\n### Windows (PowerShell)\n\n```powershell\ngit clone https://github.com/jamesdirx/modelado_geoquimico.git\ncd modelado_geoquimico\n\npython -m venv .venv\n.\\.venv\\Scripts\\Activate.ps1\n\npython -m pip install --upgrade pip\npip install -r requirements.txt\n```\n\nSi PowerShell no deja activar el entorno («running scripts is disabled»), ejecuta una vez:\n\n```powershell\nSet-ExecutionPolicy -Scope CurrentUser RemoteSigned\n```\n\n### Linux / macOS\n\n```bash\ngit clone https://github.com/jamesdirx/modelado_geoquimico.git\ncd modelado_geoquimico\n\npython3 -m venv .venv\nsource .venv/bin/activate\n\npython -m pip install --upgrade pip\npip install -r requirements.txt\n```\n\n## Uso\n\nEjecuta los comandos **desde la carpeta raíz del repositorio** con el entorno virtual activo.\n\nCorrida estándar con la plantilla incluida:\n\n```bash\npython src/engine.py\n```\n\nOpciones de línea de comandos:\n\n```\npython src/engine.py [--input RUTA_XLSX] [--output RUTA_XLSX] [--csv RUTA_CSV]\n```\n\n| Opción     | Valor por defecto                                   | Descripción                    |\n|------------|-----------------------------------------------------|--------------------------------|\n| `--input`  | `data/raw/Plantilla_Modelado_Geoquimico.xlsx`       | Plantilla Excel de entrada     |\n| `--output` | `reports/Reporte_Universal_Geoquimico.xlsx`         | Reporte Excel de salida        |\n| `--csv`    | `data/processed/resultados_universales_phreeqc.csv` | Resultados en CSV              |\n\nEjemplos:\n\n```bash\n# Una plantilla propia, con salidas en otra carpeta\npython src/engine.py --input data/raw/mi_proyecto.xlsx --output reports/mi_proyecto.xlsx --csv data/processed/mi_proyecto.csv\n\n# Ayuda\npython src/engine.py --help\n```\n\nPara correr un solo proyecto, escribe su nombre en `FILTRO_PROYECTO` (hoja `Configuracion`), por ejemplo `Puna_Norte`. Con `TODOS` se procesan todas las filas.\n\n## Plantilla de entrada\n\n`data/raw/Plantilla_Modelado_Geoquimico.xlsx` tiene cuatro hojas.\n\n### `Configuracion`\n\nParámetros globales de la corrida:\n\n| Parámetro               | Ejemplo       | Descripción                                                                    |\n|-------------------------|---------------|--------------------------------------------------------------------------------|\n| `BASE_DATOS_ACTIVA`     | `wateq4f.dat` | Base termodinámica en `database/`. Ver [Bases de datos](#bases-de-datos-termodinámicas). |\n| `FILTRO_PROYECTO`       | `TODOS`       | `TODOS` o el nombre de un proyecto de la columna `Proyecto`.                   |\n| `EXPORTAR_REPORTES_OUT` | `SI`          | Si es `SI`, guarda `reporte_nativo_<Muestra>.out` en `data/processed/`.        |\n| `TOLERANCIA_QC_IS`      | `0.30`        | Diferencia máxima aceptada \\|IS_modelo − IS_ref\\|.                             |\n| `TOLERANCIA_QC_PH`      | `0.15`        | Diferencia máxima aceptada \\|pH_modelo − pH_ref\\|.                             |\n| `PE_DEFECTO`            | `4`           | pe usado cuando la muestra no trae `pe`.                                       |\n\n### `Catalogos`\n\nOpciones válidas para los modos de cada muestra:\n\n| Categoría       | Opción                    | Traducción a PHREEQC                                     |\n|-----------------|---------------------------|----------------------------------------------------------|\n| `MODO_PH`       | `FIJO_CAMPO`              | `pH <valor>`: usa el pH medido.                          |\n|                 | `BALANCE_CARGA_T_INSITU`  | `pH <valor> charge` a la temperatura de la muestra.      |\n|                 | `BALANCE_CARGA_25C`       | `pH <valor> charge` con `temp 25`.                       |\n|                 | `REEQUILIBRIO_GAS`        | pH de partida + `EQUILIBRIUM_PHASES CO2(g)`.             |\n| `MODO_CARBONO`  | `COMO_C4_HCO3`            | `C(4) <valor> as HCO3` (carbono inorgánico total).       |\n|                 | `COMO_ALCALINIDAD_HCO3`   | `Alkalinity <valor> as HCO3`.                            |\n|                 | `COMO_ALCALINIDAD_CACO3`  | `Alkalinity <valor> as CaCO3`.                           |\n|                 | `SIN_CARBONO`             | No declara carbono (aguas hiperácidas).                  |\n| `MODO_GAS`      | `SIN_GAS`                 | Solo fase acuosa.                                        |\n|                 | `CO2_PROFUNDO`            | `CO2(g)` con log10(`P_CO2_profunda_bar`).                |\n| `ESCALA_TRAZAS` | `UG_L`                    | Las columnas `*_traza` vienen en µg/L (se dividen entre 1000). |\n|                 | `MG_L`                    | Las columnas `*_traza` vienen en mg/L.                   |\n\n### `Minerales_Objetivo`\n\nLista de fases de PHREEQC (`Fase_PHREEQC`) con su nombre en español, fórmula y grupo. Solo se calculan las que tienen `Activar = SI`. El nombre debe coincidir exactamente con una fase de la base activa. Si `Columna_Referencia_QC` apunta a una columna de `Datos_Agua` (por ejemplo `si_Calcite_Ref`), el IS se compara contra ella.\n\n### `Datos_Agua`\n\nUna fila por muestra. Columnas principales:\n\n| Grupo                | Columnas                                                                                    | Unidades |\n|----------------------|---------------------------------------------------------------------------------------------|----------|\n| Identificación       | `Proyecto`, `Area`, `Muestra`, `Tipo_Manantial`, `Campana`                                   | —        |\n| Modos                | `Modo_pH`, `Modo_Carbono`, `Modo_Gas`, `Escala_Trazas`                                       | catálogo |\n| Condiciones          | `T_C`, `pH_superficie`, `pe`, `P_CO2_profunda_bar`                                           | °C, —, —, bar |\n| Mayoritarios         | `HCO3_mgL`, `F_mgL`, `Cl_mgL`, `SO4_mgL`, `Ca_mgL`, `Mg_mgL`, `Na_mgL`, `K_mgL`, `Li_mgL`, `SiO2_mgL`, `B_mgL`, `NH4_mgL`, `S_2_mgL` | mg/L |\n| Traza                | `Fe_traza`, `Al_traza`, `Mn_traza`, `Zn_traza`, `Cu_traza`, `Ni_traza`, `Pb_traza`, `Ba_traza`, `As_traza`, `Sb_traza` | según `Escala_Trazas` |\n| Isótopos             | `O18_permil`, `Deuterio_permil`                                                              | ‰        |\n| Referencias para QC  | `pH_Ref`, `si_Calcite_Ref`, `si_Gypsum_Ref`, `si_Chalcedony_Ref`                             | —        |\n\nNotas:\n\n- `SO4_mgL` entra como `S(6)`, `SiO2_mgL` como `Si as SiO2`, `NH4_mgL` como `N(-3) as NH4` y `S_2_mgL` como `S(-2)`.\n- Las celdas vacías o con valor ≤ 0 **no** se declaran en `SOLUTION`.\n- Para agregar un proyecto nuevo, agrega filas en `Datos_Agua` con otro valor en `Proyecto`. No hace falta cambiar el código.\n\n## Bases de datos termodinámicas\n\nLa base se elige con `BASE_DATOS_ACTIVA`. Si el archivo no está en `database/`, el motor lo descarga del repositorio oficial de USGS (`usgs-coupled/iphreeqc`, carpeta `database/`). Esa primera corrida necesita conexión a internet.\n\n| Archivo        | Uso                                                                                         | En el repositorio |\n|----------------|---------------------------------------------------------------------------------------------|:-----------------:|\n| `wateq4f.dat`  | Base por defecto. Derivada de WATEQ4F (Ball y Nordstrom, 1991): aguas naturales, metales traza y fases de Fe, Al y sulfatos ácidos. | Sí |\n| `phreeqc.dat`  | Base estándar de PHREEQC, para aguas subterráneas convencionales.                           | Se descarga |\n| `llnl.dat`     | Base de Lawrence Livermore National Laboratory: amplio rango de temperatura (0–300 °C) y muchas especies. | Se descarga |\n\nLos nombres de las fases cambian entre bases (por ejemplo `Chalcedony`, `Pyrite`, `Jarosite-K`). Al cambiar de base, revisa que las fases activas de `Minerales_Objetivo` existan en ella. Si no existen, PHREEQC no calcula el IS de esa fase.\n\n## Salidas\n\n| Archivo                                             | Contenido                                                                 |\n|-----------------------------------------------------|---------------------------------------------------------------------------|\n| `data/processed/resultados_universales_phreeqc.csv` | Una fila por muestra con los resultados y las columnas de QC.             |\n| `reports/Reporte_Universal_Geoquimico.xlsx`         | Hoja `Resultados_y_QC` (lo mismo que el CSV) y hoja `Configuracion_Corrida` (parámetros usados). |\n| `data/processed/reporte_nativo_<Muestra>.out`       | Salida completa de PHREEQC: distribución de especies, actividades, IS de todas las fases. Solo si `EXPORTAR_REPORTES_OUT = SI`. |\n\nColumnas del resultado:\n\n- **Identificación y modo:** `Proyecto`, `Area`, `Muestra`, `Tipo_Manantial`, `Modo_pH`, `T_C`, `pH_superficie`.\n- **Solución:** `pH_calculado`, `Balance_Carga_eq`, `Error_Balance_%`, `Fuerza_Ionica_mu`.\n- **QC de pH:** `pH_Ref`, `Delta_pH`, `QC_pH`.\n- **Minerales:** `si_<Fase>` para cada fase activa. Si hay referencia: `<columna_ref>`, `Delta_<Fase>` y `QC_<Fase>`.\n\nUn IS sin valor (vacío) indica que a la muestra le falta algún elemento del mineral. PHREEQC devuelve −999 en ese caso y el motor lo convierte en vacío.\n\n## Control de calidad\n\n- **pH:** `QC_pH = PASA` si |pH_calculado − pH_Ref| ≤ `TOLERANCIA_QC_PH`. Si no, `REVISAR`. Si no hay `pH_Ref`, `S/D`.\n- **IS:** `QC_<Fase> = PASA` si |IS_modelo − IS_ref| ≤ `TOLERANCIA_QC_IS`. Si no, `REVISAR`.\n- Revisa también `Error_Balance_%`. Un balance de carga alto indica un análisis incompleto o un error de datos, y le resta confianza a los IS.\n\n## Scripts complementarios\n\n```bash\n# Guía del caso de estudio en Word -> reports/Caso_Estudio_Fluidos_Hidrotermales.docx\npython src/generar_guia_word.py\n\n# Gráfico IS calcita vs. yeso -> reports/figures/calcita_vs_yeso.png\npython src/utils.py\n```\n\n`utils.py` todavía lee `data/processed/puna_speciation_results.csv`, que genera el flujo anterior (`modeler.py`).\n\n## Limitaciones conocidas\n\n- **Redox:** si la muestra no trae `pe`, se usa `PE_DEFECTO` (4, condiciones oxidantes). Eso define cómo se reparten Fe(II)/Fe(III) y otros elementos redox, y afecta el IS de óxidos y sulfuros de Fe. En aguas reducidas con H2S conviene declarar `pe` o `S_2_mgL`.\n- **Valores por defecto:** si falta `T_C` se usa 25 °C, y si falta `pH_superficie` se usa pH 7.0, sin aviso. Revisa que esas columnas estén completas.\n- **pH profundo:** `REEQUILIBRIO_GAS` / `CO2_PROFUNDO` reequilibran con CO2(g) a la **temperatura de la muestra**, no a la temperatura del reservorio.\n- **Sulfuros metálicos:** su IS depende de que existan datos de S(-2) y del metal. Sin esos datos no se calcula.\n- **Modelo de actividad:** el de la base elegida (Debye-Hückel extendido / Davies en `wateq4f.dat` y `phreeqc.dat`, B-dot en `llnl.dat`). No se usa Pitzer, así que en salmueras con fuerza iónica alta los resultados pierden exactitud.\n\n## Referencias\n\n- Parkhurst, D.L., y Appelo, C.A.J. (2013). *Description of input and examples for PHREEQC version 3*. U.S. Geological Survey Techniques and Methods, book 6, chap. A43.\n- Ball, J.W., y Nordstrom, D.K. (1991). *User's manual for WATEQ4F*. U.S. Geological Survey Open-File Report 91-183.\n- Charlton, S.R., y Parkhurst, D.L. (2011). Modules based on the geochemical model PHREEQC for use in scripting and programming languages. *Computers & Geosciences*, 37, 1653–1663. (IPhreeqc)\n- Peralta Arnold, Y. (2018). Sistemas geotermales de la Puna Norte y Subandinos (Jujuy, Argentina). Tesis.\n- Kharaka, Y.K., et al. (1988). *SOLMINEQ.88: A computer program for geochemical modeling of water-rock interactions*. U.S. Geological Survey Water-Resources Investigations Report 88-4227.\n"
}


BOM = "﻿"


def is_expected_old(name: str, text: str) -> bool:
    """True si el archivo tiene el contenido danado conocido (o README vacio)."""
    t = text.lstrip(BOM).strip()
    if name == "README.md":
        return t == ""
    if name == ".gitignore":
        return t == "" or t.startswith("Set-Content") or t.startswith('@"')
    if name == "requirements.txt":
        return t == "" or t.startswith("Set-Content")
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Aplica ADR-001 (gitignore, requirements, README)")
    parser.add_argument("--dry-run", action="store_true", help="no escribe, solo informa")
    parser.add_argument("--force", action="store_true", help="reemplaza aunque el contenido no sea el esperado")
    args = parser.parse_args()

    root = Path.cwd()
    if not (root / "src" / "engine.py").is_file() or not (root / "database").is_dir():
        print("ERROR: ejecuta el script desde la raiz de modelado_geoquimico "
              "(no se encontro src/engine.py o database/).")
        return 2

    plan = []      # (ruta, contenido_nuevo, bytes_originales o None)
    problems = []
    for name, new in NEW_CONTENT.items():
        path = root / name
        old_bytes = path.read_bytes() if path.exists() else None
        old_text = old_bytes.decode("utf-8", errors="replace") if old_bytes is not None else ""
        if old_text.lstrip(BOM).replace("\r\n", "\n") == new:
            print(f"  = {name}: ya aplicado")
            continue
        if old_bytes is not None and not is_expected_old(name, old_text) and not args.force:
            problems.append(name)
            continue
        plan.append((path, new, old_bytes))
        print(f"  ~ {name}: {'se crea' if old_bytes is None else 'se reemplaza'}")

    if problems:
        print("\nERROR: estos archivos tienen un contenido distinto al esperado y no se tocan:")
        for name in problems:
            print(f"  - {name}")
        print("Revisa su contenido; si quieres reemplazarlos igual, usa --force. No se escribio nada.")
        return 1

    if not plan:
        print("\nADR-001 ya estaba aplicado. Nada que hacer.")
        return 0

    if args.dry_run:
        print(f"\n[dry-run] {len(plan)} archivo(s) cambiarian. No se escribio nada.")
        return 0

    written = []
    try:
        for path, new, old_bytes in plan:
            tmp = path.with_name(path.name + ".adr001.tmp")
            with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(new)
            os.replace(tmp, path)
            written.append((path, old_bytes))
    except Exception as exc:
        for path, old_bytes in reversed(written):
            if old_bytes is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(old_bytes)
        for path, _, _ in plan:
            path.with_name(path.name + ".adr001.tmp").unlink(missing_ok=True)
        print(f"ERROR al escribir ({exc}). Se restauraron los archivos originales.")
        return 1

    print(f"\nADR-001 aplicado: {len(written)} archivo(s) actualizados.")
    print("Siguiente: git status  ->  revisa el diff y haz commit.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
