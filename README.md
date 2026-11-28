# modelado_geoquimico

Motor de especiación acuosa e índices de saturación mineral para aguas geotermales e hidrotermales, basado en **PHREEQC** (vía `phreeqpy`/IPhreeqc) y dirigido por una **plantilla Excel**. Las muestras, los modos de cálculo, los minerales y la base termodinámica se eligen en la plantilla, sin modificar el código. Cada corrida genera un reporte con control de calidad (QC) contra valores publicados.

Casos incluidos en la plantilla:

| Proyecto      | Muestras | Fuente de los datos                                                                 |
|---------------|---------:|-------------------------------------------------------------------------------------|
| `Puna_Norte`  | 14       | Peralta Arnold, Y. (2018), sistemas geotermales de la Puna Norte y Subandinos (Jujuy, Argentina). Química e isótopos: Tabla 6-3; metales: Tabla 6-4; P_CO2 y gases: Tabla 6-5; IS de referencia: Tabla 6-7; geotermómetros: Tabla 6-8. Libro fuente: `data/raw/Caso_Estudio_Puna_Completo.xlsx`. |
| `El_Aguajito` | 43       | Caldera El Aguajito. <!-- TODO: completar la referencia bibliográfica -->           |

El proyecto incluye un caso de comparación con **SOLMINEQ-Py** (`src/comparar_solmineq.py`, ver [Comparación con SOLMINEQ-Py](#comparación-con-solmineq-py)).

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
- [Datos de la Puna Norte](#datos-de-la-puna-norte)
- [Comparación con SOLMINEQ-Py](#comparación-con-solmineq-py)
- [Scripts complementarios](#scripts-complementarios)
- [Limitaciones conocidas](#limitaciones-conocidas)
- [Referencias](#referencias)

---

## Qué hace

Para cada muestra de la hoja `Datos_Agua`, `src/engine.py`:

1. Arma un bloque `SOLUTION` de PHREEQC con temperatura, pH, pe, iones mayoritarios, sílice, boro, NH4, S(-2) y elementos traza.
2. Aplica el **modo de pH**, el **modo de carbono** y el **modo de gas** de la fila. Por ejemplo, puede cerrar el balance de carga con el pH o reequilibrar con CO2(g) a una P_CO2 dada para estimar el pH profundo.
3. Corre PHREEQC con la base termodinámica de la fila (`Base_Datos`) o, si está vacía, la global y extrae el pH calculado, el balance de carga, el error de balance (%), la fuerza iónica y el **índice de saturación (IS = log IAP/K)** de cada mineral activo.
4. Compara contra los valores de referencia de la plantilla (pH e IS) y marca cada resultado como `PASA`, `REVISAR` o `S/D`.
5. Escribe un CSV, un reporte Excel y, si se pide, el archivo `.out` nativo de PHREEQC de cada muestra.

## Estructura del repositorio

```
modelado_geoquimico/
├── data/
│   ├── raw/
│   │   ├── Plantilla_Modelado_Geoquimico.xlsx   # entrada principal del motor
│   │   └── Caso_Estudio_Puna_Completo.xlsx      # libro fuente de la Puna Norte (Tablas 6-3 a 6-8)
│   └── processed/
│       ├── resultados_universales_phreeqc.csv   # salida del motor
│       └── reporte_nativo_<Muestra>.out         # salidas nativas de PHREEQC
├── database/
│   ├── wateq4f.dat                              # base termodinámica (USGS)
│   └── llnl.dat                                 # base termodinámica (USGS/LLNL), usada por la Puna Norte
├── notebooks/
├── reports/
│   ├── Reporte_Universal_Geoquimico.xlsx        # reporte del motor
│   └── figures/
├── src/
│   ├── engine.py               # motor principal (punto de entrada)
│   ├── importar_puna_tesis.py  # copia la Puna Norte del libro de la tesis a la plantilla
│   ├── comparar_solmineq.py    # caso de comparación PHREEQC vs SOLMINEQ-Py
│   ├── generar_guia_word.py    # genera la guía del caso de estudio (.docx)
│   └── utils.py                # gráfico IS calcita vs. yeso (pendiente de adaptar, ver abajo)
├── test/                       # pytest
└── requirements.txt
```

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

`data/raw/Plantilla_Modelado_Geoquimico.xlsx` tiene cuatro hojas que lee el motor (`Configuracion`, `Catalogos`, `Minerales_Objetivo`, `Datos_Agua`) y una informativa, `Gases_Puna_T6_5`, con los gases disueltos de la Tabla 6-5 (mmol/mol).

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
| Base termodinámica   | `Base_Datos` (vacía = `BASE_DATOS_ACTIVA`)                                                   | archivo `.dat` |
| Mayoritarios         | `HCO3_mgL`, `F_mgL`, `Cl_mgL`, `SO4_mgL`, `Ca_mgL`, `Mg_mgL`, `Na_mgL`, `K_mgL`, `Li_mgL`, `SiO2_mgL`, `B_mgL`, `NH4_mgL`, `S_2_mgL`, `Br_mgL`, `NO3_mgL`, `TDS_mgL` | mg/L |
| Traza                | `Fe_traza`, `Al_traza`, `Mn_traza`, `Zn_traza`, `Cu_traza`, `Ni_traza`, `Pb_traza`, `Ba_traza`, `As_traza`, `Sb_traza`, `Co_traza` | según `Escala_Trazas` |
| Isótopos             | `O18_permil`, `Deuterio_permil`                                                              | ‰        |
| Referencias para QC  | `pH_Ref` y `si_<Fase>_Ref` (en la Puna Norte, los 21 minerales de la Tabla 6-7)               | —        |
| Geotermómetros (ref.)| `T_Calcedonia_Arnorsson1983_Ref`, `T_Cuarzo_Fournier1977_Ref`, `T_NaK_Fournier1979_Ref`, `T_NaK_Truesdell1976_Ref`, `T_NaK_Giggenbach1988_Ref`, `T_KMg_Giggenbach_Ref` | °C |
| Procedencia          | `Nota_Datos`: datos faltantes, valores bajo el límite de detección y decisiones sobre la muestra | texto |

Notas:

- `SO4_mgL` entra como `S(6)`, `SiO2_mgL` como `Si as SiO2`, `NH4_mgL` como `N(-3) as NH4`, `NO3_mgL` como `N(5) as NO3`, `Br_mgL` como `Br` y `S_2_mgL` como `S(-2)`. `TDS_mgL` es informativo.
- `wateq4f.dat` no tiene Co: con esa base PHREEQC toma `Co_traza` como cero (aviso en el `.out`).
- Las celdas vacías o con valor ≤ 0 **no** se declaran en `SOLUTION`.
- Para agregar un proyecto nuevo, agrega filas en `Datos_Agua` con otro valor en `Proyecto`. No hace falta cambiar el código.

## Bases de datos termodinámicas

La base global se elige con `BASE_DATOS_ACTIVA` (hoja `Configuracion`). Cada muestra puede usar otra con la columna `Base_Datos` de `Datos_Agua`; la Puna Norte usa `llnl.dat`, que es la base con la que se reproduce la Tabla 6-7. Si el archivo no está en `database/`, el motor lo descarga del repositorio de USGS (`usgs-coupled/iphreeqc`, carpeta `database/`). Antes de procesar, el motor comprueba que IPhreeqc carga cada base y, si no, se detiene con un mensaje claro.

| Archivo        | Uso                                                                                         | En el repositorio |
|----------------|---------------------------------------------------------------------------------------------|:-----------------:|
| `wateq4f.dat`  | Base global por defecto. Derivada de WATEQ4F (Ball y Nordstrom, 1991): aguas naturales, metales traza y fases de Fe, Al y sulfatos ácidos. | Sí |
| `llnl.dat`     | Lawrence Livermore National Laboratory: amplio rango de temperatura (0–300 °C), muchas especies, modelo B-dot. Usada por la Puna Norte. | Sí |
| `phreeqc.dat`  | Base estándar de PHREEQC. **No usar por ahora:** la versión actual de USGS trae un bloque `GAS_BINARY_PARAMETERS` que el IPhreeqc 3.7.3 de `phreeqpy` 0.6.0 no reconoce, y no carga. | No |

Las bases se versionan en el repositorio para que los resultados no cambien si USGS actualiza sus archivos.

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

## Datos de la Puna Norte

Las 14 filas de la Puna Norte se copian del libro de la tesis con:

```bash
python src/importar_puna_tesis.py           # reescribe las filas Puna_Norte de la plantilla
python src/importar_puna_tesis.py --check   # solo verifica que la plantilla coincide con el libro
```

Reglas: los valores se copian tal cual; `<1` (bajo el límite de detección) y `n.d.` quedan vacíos y se anotan en `Nota_Datos`; Pb, Al y S(-2) quedan vacíos porque la tesis no los informa.

**Muestras sin gases.** ACF, LC y PA2 no tienen datos en la Tabla 6-5: ACF es un agua calentada sin fase vapor, LC es una muestra de río y PA2 no figura en la tabla. Se calculan con el pH de campo y sin reequilibrio con CO2 (`FIJO_CAMPO` / `SIN_GAS`). Por eso los IS de la Tabla 6-7 para PA2, que la tesis sí publica, no se pueden reproducir con los datos publicados.

## Comparación con SOLMINEQ-Py

`src/comparar_solmineq.py` corre las muestras de un proyecto en PHREEQC (`wateq4f.dat` y `llnl.dat`) y en SOLMINEQ-Py, con las mismas entradas, y compara pH, fuerza iónica, especies clave (molalidad, γ, actividad), IS y geotermómetros contra las referencias de la plantilla.

Requiere `solmineq_app` instalado en el mismo entorno (no está en `requirements.txt`):

```bash
pip install -e H:\Phyton\SOLMINEQ      # ruta a tu copia de SOLMINEQ-Py
python src/comparar_solmineq.py --proyecto Puna_Norte --output reports/Comparacion_PHREEQC_SOLMINEQ.xlsx
```

Escenarios:

- **A_superficie:** T de la muestra, pH medido, carbono como DIC. Entrada idéntica en los tres.
- **B_profundo:** PHREEQC reequilibra con CO2(g) a `P_CO2_profunda_bar`; SOLMINEQ-Py usa el pH y el DIC que resultan con `wateq4f.dat`. Solo para muestras con P_CO2.

Las hojas `Notas`, `Resumen`, `IS`, `Especies_A`, `Condiciones`, `Geotermometros` y `Datos_largos` del reporte explican los supuestos y las diferencias. Sin `solmineq_app`, la prueba correspondiente se omite.

## Pruebas

```bash
python -m pytest test
```

## Scripts complementarios

```bash
# Guía del caso de estudio en Word -> reports/Caso_Estudio_Fluidos_Hidrotermales.docx
python src/generar_guia_word.py

# Gráfico IS calcita vs. yeso -> reports/figures/calcita_vs_yeso.png
python src/utils.py
```

`utils.py` todavía lee `data/processed/puna_speciation_results.csv`, que generaba el flujo anterior (`modeler.py`, ya retirado): hay que adaptarlo a `resultados_universales_phreeqc.csv`.

## Limitaciones conocidas

- **Redox:** si la muestra no trae `pe`, se usa `PE_DEFECTO` (4, condiciones oxidantes). Eso define cómo se reparten Fe(II)/Fe(III) y otros elementos redox, y afecta el IS de óxidos y sulfuros de Fe. En aguas reducidas con H2S conviene declarar `pe` o `S_2_mgL`.
- **Valores por defecto:** si falta `T_C` se usa 25 °C, y si falta `pH_superficie` se usa pH 7.0, sin aviso. Revisa que esas columnas estén completas.
- **pH profundo:** `REEQUILIBRIO_GAS` / `CO2_PROFUNDO` reequilibran con CO2(g) a la **temperatura de la muestra**, no a la temperatura del reservorio. Si falta `P_CO2_profunda_bar`, el motor avisa y calcula sin reequilibrio.
- **Redox en el reequilibrio:** el paso de `EQUILIBRIUM_PHASES` también reequilibra los pares redox (por ejemplo N(-3)/N(5)), así que el pe deja de ser el de la plantilla. En la Puna Norte eso aleja los óxidos de Fe (hematita, magnetita, goethita) de la Tabla 6-7, que es coherente con pe 4 sin reequilibrar.
- **Sulfuros metálicos:** su IS depende de que existan datos de S(-2) y del metal. Sin esos datos no se calcula.
- **Modelo de actividad:** el de la base elegida (Debye-Hückel extendido / Davies en `wateq4f.dat` y `phreeqc.dat`, B-dot en `llnl.dat`). No se usa Pitzer, así que en salmueras con fuerza iónica alta los resultados pierden exactitud.

## Referencias

- Parkhurst, D.L., y Appelo, C.A.J. (2013). *Description of input and examples for PHREEQC version 3*. U.S. Geological Survey Techniques and Methods, book 6, chap. A43.
- Ball, J.W., y Nordstrom, D.K. (1991). *User's manual for WATEQ4F*. U.S. Geological Survey Open-File Report 91-183.
- Charlton, S.R., y Parkhurst, D.L. (2011). Modules based on the geochemical model PHREEQC for use in scripting and programming languages. *Computers & Geosciences*, 37, 1653–1663. (IPhreeqc)
- Peralta Arnold, Y. (2018). Sistemas geotermales de la Puna Norte y Subandinos (Jujuy, Argentina). Tesis.
- Kharaka, Y.K., et al. (1988). *SOLMINEQ.88: A computer program for geochemical modeling of water-rock interactions*. U.S. Geological Survey Water-Resources Investigations Report 88-4227.
