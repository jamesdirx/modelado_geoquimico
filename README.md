# modelado_geoquimico

Motor de especiación acuosa e índices de saturación mineral para aguas geotermales e hidrotermales, basado en **PHREEQC** (vía `phreeqpy`/IPhreeqc) y dirigido por una **plantilla Excel**. Las muestras, los modos de cálculo, los minerales y la base termodinámica se eligen en la plantilla, sin modificar el código. Cada corrida genera un reporte con control de calidad (QC) contra valores publicados.

Casos incluidos en la plantilla:

| Proyecto      | Muestras | Fuente de los datos                                                                 |
|---------------|---------:|-------------------------------------------------------------------------------------|
| `Puna_Norte`  | 14       | Peralta Arnold, Y. (2018), sistemas geotermales de la Puna Norte y Subandinos (Jujuy, Argentina). Química: Tabla 6-3; P_CO2: Tabla 6-5; IS de referencia: Tabla 6-7. |
| `El_Aguajito` | 43       | Caldera El Aguajito. <!-- TODO: completar la referencia bibliográfica -->           |

El proyecto también servirá para casos de comparación con **SOLMINEQ.88 / SOLMINEQ-Py**.

---

## Contenido

- [Qué hace](#qué-hace)
- [Estructura del repositorio](#estructura-del-repositorio)
- [Instalación](#instalación)
- [Uso](#uso)
- [Plantilla de entrada](#plantilla-de-entrada)
- [Bases de datos termodinámicas](#bases-de-datos-termodinámicas)
- [Salidas](#salidas)
- [Control de calidad](#control-de-calidad)
- [Scripts complementarios](#scripts-complementarios)
- [Limitaciones conocidas](#limitaciones-conocidas)
- [Referencias](#referencias)

---

## Qué hace

Para cada muestra de la hoja `Datos_Agua`, `src/engine.py`:

1. Arma un bloque `SOLUTION` de PHREEQC con temperatura, pH, pe, iones mayoritarios, sílice, boro, NH4, S(-2) y elementos traza.
2. Aplica el **modo de pH**, el **modo de carbono** y el **modo de gas** de la fila. Por ejemplo, puede cerrar el balance de carga con el pH o reequilibrar con CO2(g) a una P_CO2 dada para estimar el pH profundo.
3. Corre PHREEQC con la base termodinámica elegida y extrae el pH calculado, el balance de carga, el error de balance (%), la fuerza iónica y el **índice de saturación (IS = log IAP/K)** de cada mineral activo.
4. Compara contra los valores de referencia de la plantilla (pH e IS) y marca cada resultado como `PASA`, `REVISAR` o `S/D`.
5. Escribe un CSV, un reporte Excel y, si se pide, el archivo `.out` nativo de PHREEQC de cada muestra.

## Estructura del repositorio

```
modelado_geoquimico/
├── data/
│   ├── raw/
│   │   ├── Plantilla_Modelado_Geoquimico.xlsx   # entrada principal del motor
│   │   └── punanorte_tabla6_3.csv               # datos crudos Puna Norte (flujo anterior)
│   └── processed/
│       ├── resultados_universales_phreeqc.csv   # salida del motor
│       └── reporte_nativo_<Muestra>.out         # salidas nativas de PHREEQC
├── database/
│   └── wateq4f.dat                              # base termodinámica (USGS)
├── notebooks/
├── reports/
│   ├── Reporte_Universal_Geoquimico.xlsx        # reporte del motor
│   └── figures/
├── src/
│   ├── engine.py               # motor principal (punto de entrada)
│   ├── generar_guia_word.py    # genera la guía del caso de estudio (.docx)
│   ├── utils.py                # gráfico IS calcita vs. yeso
│   ├── loader.py               # flujo anterior (en retiro)
│   ├── modeler.py              # flujo anterior (en retiro)
│   └── reporter.py             # flujo anterior (en retiro)
├── test/
└── requirements.txt
```

> `loader.py`, `modeler.py` y `reporter.py` son el flujo anterior, solo para la Puna Norte. Su función quedó unificada en `engine.py` y se retirarán.

## Instalación

Requisitos:

- **Python 3.10 o superior, de 64 bits.** Probado con Python 3.13.
- **Git.**
- No hace falta instalar PHREEQC aparte: `phreeqpy` incluye la librería IPhreeqc para Windows, Linux y macOS.

### Windows (PowerShell)

```powershell
git clone https://github.com/jamesdirx/modelado_geoquimico.git
cd modelado_geoquimico

python -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
pip install -r requirements.txt
```

Si PowerShell no deja activar el entorno («running scripts is disabled»), ejecuta una vez:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### Linux / macOS

```bash
git clone https://github.com/jamesdirx/modelado_geoquimico.git
cd modelado_geoquimico

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Uso

Ejecuta los comandos **desde la carpeta raíz del repositorio** con el entorno virtual activo.

Corrida estándar con la plantilla incluida:

```bash
python src/engine.py
```

Opciones de línea de comandos:

```
python src/engine.py [--input RUTA_XLSX] [--output RUTA_XLSX] [--csv RUTA_CSV]
```

| Opción     | Valor por defecto                                   | Descripción                    |
|------------|-----------------------------------------------------|--------------------------------|
| `--input`  | `data/raw/Plantilla_Modelado_Geoquimico.xlsx`       | Plantilla Excel de entrada     |
| `--output` | `reports/Reporte_Universal_Geoquimico.xlsx`         | Reporte Excel de salida        |
| `--csv`    | `data/processed/resultados_universales_phreeqc.csv` | Resultados en CSV              |

Ejemplos:

```bash
# Una plantilla propia, con salidas en otra carpeta
python src/engine.py --input data/raw/mi_proyecto.xlsx --output reports/mi_proyecto.xlsx --csv data/processed/mi_proyecto.csv

# Ayuda
python src/engine.py --help
```

Para correr un solo proyecto, escribe su nombre en `FILTRO_PROYECTO` (hoja `Configuracion`), por ejemplo `Puna_Norte`. Con `TODOS` se procesan todas las filas.

## Plantilla de entrada

`data/raw/Plantilla_Modelado_Geoquimico.xlsx` tiene cuatro hojas.

### `Configuracion`

Parámetros globales de la corrida:

| Parámetro               | Ejemplo       | Descripción                                                                    |
|-------------------------|---------------|--------------------------------------------------------------------------------|
| `BASE_DATOS_ACTIVA`     | `wateq4f.dat` | Base termodinámica en `database/`. Ver [Bases de datos](#bases-de-datos-termodinámicas). |
| `FILTRO_PROYECTO`       | `TODOS`       | `TODOS` o el nombre de un proyecto de la columna `Proyecto`.                   |
| `EXPORTAR_REPORTES_OUT` | `SI`          | Si es `SI`, guarda `reporte_nativo_<Muestra>.out` en `data/processed/`.        |
| `TOLERANCIA_QC_IS`      | `0.30`        | Diferencia máxima aceptada \|IS_modelo − IS_ref\|.                             |
| `TOLERANCIA_QC_PH`      | `0.15`        | Diferencia máxima aceptada \|pH_modelo − pH_ref\|.                             |
| `PE_DEFECTO`            | `4`           | pe usado cuando la muestra no trae `pe`.                                       |

### `Catalogos`

Opciones válidas para los modos de cada muestra:

| Categoría       | Opción                    | Traducción a PHREEQC                                     |
|-----------------|---------------------------|----------------------------------------------------------|
| `MODO_PH`       | `FIJO_CAMPO`              | `pH <valor>`: usa el pH medido.                          |
|                 | `BALANCE_CARGA_T_INSITU`  | `pH <valor> charge` a la temperatura de la muestra.      |
|                 | `BALANCE_CARGA_25C`       | `pH <valor> charge` con `temp 25`.                       |
|                 | `REEQUILIBRIO_GAS`        | pH de partida + `EQUILIBRIUM_PHASES CO2(g)`.             |
| `MODO_CARBONO`  | `COMO_C4_HCO3`            | `C(4) <valor> as HCO3` (carbono inorgánico total).       |
|                 | `COMO_ALCALINIDAD_HCO3`   | `Alkalinity <valor> as HCO3`.                            |
|                 | `COMO_ALCALINIDAD_CACO3`  | `Alkalinity <valor> as CaCO3`.                           |
|                 | `SIN_CARBONO`             | No declara carbono (aguas hiperácidas).                  |
| `MODO_GAS`      | `SIN_GAS`                 | Solo fase acuosa.                                        |
|                 | `CO2_PROFUNDO`            | `CO2(g)` con log10(`P_CO2_profunda_bar`).                |
| `ESCALA_TRAZAS` | `UG_L`                    | Las columnas `*_traza` vienen en µg/L (se dividen entre 1000). |
|                 | `MG_L`                    | Las columnas `*_traza` vienen en mg/L.                   |

### `Minerales_Objetivo`

Lista de fases de PHREEQC (`Fase_PHREEQC`) con su nombre en español, fórmula y grupo. Solo se calculan las que tienen `Activar = SI`. El nombre debe coincidir exactamente con una fase de la base activa. Si `Columna_Referencia_QC` apunta a una columna de `Datos_Agua` (por ejemplo `si_Calcite_Ref`), el IS se compara contra ella.

### `Datos_Agua`

Una fila por muestra. Columnas principales:

| Grupo                | Columnas                                                                                    | Unidades |
|----------------------|---------------------------------------------------------------------------------------------|----------|
| Identificación       | `Proyecto`, `Area`, `Muestra`, `Tipo_Manantial`, `Campana`                                   | —        |
| Modos                | `Modo_pH`, `Modo_Carbono`, `Modo_Gas`, `Escala_Trazas`                                       | catálogo |
| Condiciones          | `T_C`, `pH_superficie`, `pe`, `P_CO2_profunda_bar`                                           | °C, —, —, bar |
| Mayoritarios         | `HCO3_mgL`, `F_mgL`, `Cl_mgL`, `SO4_mgL`, `Ca_mgL`, `Mg_mgL`, `Na_mgL`, `K_mgL`, `Li_mgL`, `SiO2_mgL`, `B_mgL`, `NH4_mgL`, `S_2_mgL` | mg/L |
| Traza                | `Fe_traza`, `Al_traza`, `Mn_traza`, `Zn_traza`, `Cu_traza`, `Ni_traza`, `Pb_traza`, `Ba_traza`, `As_traza`, `Sb_traza` | según `Escala_Trazas` |
| Isótopos             | `O18_permil`, `Deuterio_permil`                                                              | ‰        |
| Referencias para QC  | `pH_Ref`, `si_Calcite_Ref`, `si_Gypsum_Ref`, `si_Chalcedony_Ref`                             | —        |

Notas:

- `SO4_mgL` entra como `S(6)`, `SiO2_mgL` como `Si as SiO2`, `NH4_mgL` como `N(-3) as NH4` y `S_2_mgL` como `S(-2)`.
- Las celdas vacías o con valor ≤ 0 **no** se declaran en `SOLUTION`.
- Para agregar un proyecto nuevo, agrega filas en `Datos_Agua` con otro valor en `Proyecto`. No hace falta cambiar el código.

## Bases de datos termodinámicas

La base se elige con `BASE_DATOS_ACTIVA`. Si el archivo no está en `database/`, el motor lo descarga del repositorio oficial de USGS (`usgs-coupled/iphreeqc`, carpeta `database/`). Esa primera corrida necesita conexión a internet.

| Archivo        | Uso                                                                                         | En el repositorio |
|----------------|---------------------------------------------------------------------------------------------|:-----------------:|
| `wateq4f.dat`  | Base por defecto. Derivada de WATEQ4F (Ball y Nordstrom, 1991): aguas naturales, metales traza y fases de Fe, Al y sulfatos ácidos. | Sí |
| `phreeqc.dat`  | Base estándar de PHREEQC, para aguas subterráneas convencionales.                           | Se descarga |
| `llnl.dat`     | Base de Lawrence Livermore National Laboratory: amplio rango de temperatura (0–300 °C) y muchas especies. | Se descarga |

Los nombres de las fases cambian entre bases (por ejemplo `Chalcedony`, `Pyrite`, `Jarosite-K`). Al cambiar de base, revisa que las fases activas de `Minerales_Objetivo` existan en ella. Si no existen, PHREEQC no calcula el IS de esa fase.

## Salidas

| Archivo                                             | Contenido                                                                 |
|-----------------------------------------------------|---------------------------------------------------------------------------|
| `data/processed/resultados_universales_phreeqc.csv` | Una fila por muestra con los resultados y las columnas de QC.             |
| `reports/Reporte_Universal_Geoquimico.xlsx`         | Hoja `Resultados_y_QC` (lo mismo que el CSV) y hoja `Configuracion_Corrida` (parámetros usados). |
| `data/processed/reporte_nativo_<Muestra>.out`       | Salida completa de PHREEQC: distribución de especies, actividades, IS de todas las fases. Solo si `EXPORTAR_REPORTES_OUT = SI`. |

Columnas del resultado:

- **Identificación y modo:** `Proyecto`, `Area`, `Muestra`, `Tipo_Manantial`, `Modo_pH`, `T_C`, `pH_superficie`.
- **Solución:** `pH_calculado`, `Balance_Carga_eq`, `Error_Balance_%`, `Fuerza_Ionica_mu`.
- **QC de pH:** `pH_Ref`, `Delta_pH`, `QC_pH`.
- **Minerales:** `si_<Fase>` para cada fase activa. Si hay referencia: `<columna_ref>`, `Delta_<Fase>` y `QC_<Fase>`.

Un IS sin valor (vacío) indica que a la muestra le falta algún elemento del mineral. PHREEQC devuelve −999 en ese caso y el motor lo convierte en vacío.

## Control de calidad

- **pH:** `QC_pH = PASA` si |pH_calculado − pH_Ref| ≤ `TOLERANCIA_QC_PH`. Si no, `REVISAR`. Si no hay `pH_Ref`, `S/D`.
- **IS:** `QC_<Fase> = PASA` si |IS_modelo − IS_ref| ≤ `TOLERANCIA_QC_IS`. Si no, `REVISAR`.
- Revisa también `Error_Balance_%`. Un balance de carga alto indica un análisis incompleto o un error de datos, y le resta confianza a los IS.

## Scripts complementarios

```bash
# Guía del caso de estudio en Word -> reports/Caso_Estudio_Fluidos_Hidrotermales.docx
python src/generar_guia_word.py

# Gráfico IS calcita vs. yeso -> reports/figures/calcita_vs_yeso.png
python src/utils.py
```

`utils.py` todavía lee `data/processed/puna_speciation_results.csv`, que genera el flujo anterior (`modeler.py`).

## Limitaciones conocidas

- **Redox:** si la muestra no trae `pe`, se usa `PE_DEFECTO` (4, condiciones oxidantes). Eso define cómo se reparten Fe(II)/Fe(III) y otros elementos redox, y afecta el IS de óxidos y sulfuros de Fe. En aguas reducidas con H2S conviene declarar `pe` o `S_2_mgL`.
- **Valores por defecto:** si falta `T_C` se usa 25 °C, y si falta `pH_superficie` se usa pH 7.0, sin aviso. Revisa que esas columnas estén completas.
- **pH profundo:** `REEQUILIBRIO_GAS` / `CO2_PROFUNDO` reequilibran con CO2(g) a la **temperatura de la muestra**, no a la temperatura del reservorio.
- **Sulfuros metálicos:** su IS depende de que existan datos de S(-2) y del metal. Sin esos datos no se calcula.
- **Modelo de actividad:** el de la base elegida (Debye-Hückel extendido / Davies en `wateq4f.dat` y `phreeqc.dat`, B-dot en `llnl.dat`). No se usa Pitzer, así que en salmueras con fuerza iónica alta los resultados pierden exactitud.

## Referencias

- Parkhurst, D.L., y Appelo, C.A.J. (2013). *Description of input and examples for PHREEQC version 3*. U.S. Geological Survey Techniques and Methods, book 6, chap. A43.
- Ball, J.W., y Nordstrom, D.K. (1991). *User's manual for WATEQ4F*. U.S. Geological Survey Open-File Report 91-183.
- Charlton, S.R., y Parkhurst, D.L. (2011). Modules based on the geochemical model PHREEQC for use in scripting and programming languages. *Computers & Geosciences*, 37, 1653–1663. (IPhreeqc)
- Peralta Arnold, Y. (2018). Sistemas geotermales de la Puna Norte y Subandinos (Jujuy, Argentina). Tesis.
- Kharaka, Y.K., et al. (1988). *SOLMINEQ.88: A computer program for geochemical modeling of water-rock interactions*. U.S. Geological Survey Water-Resources Investigations Report 88-4227.
