# Registro de decisiones (ADR) — modelado_geoquimico

Cada decisión de diseño se registra aquí con su contexto, lo que se decidió y sus consecuencias. Un ADR se aplica con
su script `apply_adr_NNN.py` (atómico, idempotente, con `--dry-run`) y se acepta cuando pasan las pruebas.

| ADR | Tema | Estado | Commit |
|---|---|---|---|
| [001](#adr-001) | `.gitignore`, `requirements.txt` y README | Aceptado | dc04f7a |
| [002](#adr-002) | Puna Norte desde la tesis, base por muestra y comparación con SOLMINEQ-Py | Aceptado | eea7208 |
| [003](#adr-003) | Bases de USGS con bloques nuevos, gráfico de IS y script de aplicación | Aceptado | c16defd |
| [004](#adr-004) | Salidas legibles y trazables | Propuesto | — |

<a id="adr-001"></a>
## ADR-001 — corrección de .gitignore y requirements.txt; README

**Estado:** Aceptado. Aplicado el 27/11/2026, commit dc04f7a.

### Contexto

- .gitignore y requirements.txt contenían comandos de PowerShell (Set-Content ...) en lugar de su contenido:
  pip install -r fallaba y git no ignoraba .venv/ (VS Code: "too many active changes").
- README.md estaba vacío.

### Decisiones

1. .gitignore con los patrones reales (`__pycache__`, `.venv`, `.pytest_cache`, `*.pqo`/`*.pqi`, `/phreeqc.*.out`, `~$*`).
2. requirements.txt con las dependencias reales; se agregan openpyxl (lectura de la plantilla) y python-docx
   (generar_guia_word.py), que el código usaba y no estaban.
3. README con descripción, instalación (Windows y Linux/macOS), línea de comandos, plantilla, bases, salidas y QC.

---

<a id="adr-002"></a>
## ADR-002 — Puna Norte desde la tesis, base termodinámica por muestra y comparación con SOLMINEQ-Py

**Estado:** Aceptado. Aplicado el 27/11/2026, commit eea7208 (12 passed con solmineq_app; 11 passed, 1 skipped sin él).

### Contexto

- Las filas Puna_Norte de la plantilla no coincidían con la tesis (Peralta Arnold, 2018) en 138 valores: iones
  mayores de RE2, RE3, LC, ACF y PA2; isótopos y NH4 de las 14 muestras; Pb sin fuente (la tesis trae Co);
  Ba y Sb intercambiados en CA1-CA3 y PA1-PA3; Cu/Zn/Ba/Sb corridos donde Ni está en blanco (J, CA2, SA);
  S(-2) = 0.01 mg/L sin fuente; P_CO2 de RE2/RE3 incorrecta y P_CO2 inventada en ACF, LC y PA2.
- Verificación: con los metales del libro de la tesis, la baritina de la Tabla 6-7 se reproduce con mediana
  |dIS| = 0.01 (máx. 0.06); con los de la plantilla anterior, 1.2.
- La Tabla 6-7 se reproduce con llnl.dat y reequilibrio con CO2(g) a la P_CO2 de la Tabla 6-5 (anhidrita, yeso,
  baritina, halita, fluorita, calcedonia, cuarzo y coesita: mediana |dIS| <= 0.02).

### Decisiones (datos)

1. Fuente única: data/raw/Caso_Estudio_Puna_Completo.xlsx (Tablas 6-3, 6-4, 6-5, 6-7 y 6-8), con P_CO2 verificada
   por el usuario contra la Tabla 6-5 (RE2 0.027, RE3 0.029).
2. src/importar_puna_tesis.py copia las 14 muestras tal cual; --check verifica que la plantilla coincide.
3. Nada se inventa: "<1" y "n.d." quedan vacíos y se anotan en Nota_Datos; Pb, Al y S(-2) vacíos (la tesis no
   los informa).
4. ACF, LC y PA2 sin gases ni P_CO2 (Tabla 6-5): FIJO_CAMPO / SIN_GAS. ACF: agua calentada sin fase vapor; LC:
   río; PA2: no figura en la Tabla 6-5 (decisión del usuario: dejarla sin P_CO2 y documentarlo). Los IS que la
   tesis publica para PA2 no se pueden reproducir con los datos publicados.
5. Columnas nuevas en Datos_Agua: Br_mgL, NO3_mgL, Co_traza, TDS_mgL, Base_Datos, Nota_Datos, si_<Fase>_Ref de
   los 21 minerales de la Tabla 6-7 y T_*_Ref de los 6 geotermómetros de la Tabla 6-8. Diez fases nuevas en
   Minerales_Objetivo (Barite, Coesite, Dolomite, Fayalite, Forsterite, Huntite, Magnesite, Talc, Witherite,
   Zincite). Hoja informativa Gases_Puna_T6_5.

### Decisiones (código)

6. engine.py: base termodinámica por muestra (columna Base_Datos; vacía = BASE_DATOS_ACTIVA). Puna Norte:
   llnl.dat; El Aguajito sigue con wateq4f.dat (resultados sin cambios, verificado).
7. llnl.dat se versiona en database/ (como wateq4f.dat) para que los resultados no dependan de la versión que
   publique USGS.
8. engine.py comprueba que IPhreeqc carga cada base antes de procesar y se detiene con mensaje claro. Motivo:
   phreeqc.dat actual de USGS trae GAS_BINARY_PARAMETERS, que el IPhreeqc 3.7.3 de phreeqpy 0.6.0 no reconoce.
9. engine.py avisa si se pide reequilibrio con CO2 sin P_CO2_profunda_bar (antes lo omitía en silencio).
10. Br -> Br, NO3 -> N(5) as NO3, Co -> Co (wateq4f.dat no tiene Co: PHREEQC lo toma como cero).
11. src/comparar_solmineq.py: PHREEQC (wateq4f, llnl) vs SOLMINEQ-Py con entradas idénticas; escenarios
    A_superficie y B_profundo (solo con P_CO2); IS, especies clave y geotermómetros contra la tesis.
    solmineq_app es opcional (no está en requirements.txt); su prueba se omite si falta.

### Efecto (QC del motor contra la Tabla 6-7, 11 muestras)

- PASA en las 11: anhidrita, yeso, baritina, halita, fluorita, calcedonia, cuarzo, coesita.
- Calcita y aragonito 7/11; magnesita 7/11; witherita 6/11; dolomita 3/11.
- Óxidos de Fe 1/11: EQUILIBRIUM_PHASES reequilibra el par N(-3)/N(5) y baja el pe; la tesis es coherente con pe 4
  sin reequilibrar. Documentado en el README; pendiente de un ADR propio.
- Comparación con SOLMINEQ-Py: calcita/anhidrita/halita |dIS| <= 0.08 con wateq4f; calcedonia de SOLMINEQ-Py
  0.09-0.22 mayor (gamma(H4SiO4) de Marshall y log K de la Tabla IC); geotermómetros de la Tabla 6-8 con
  +/-0.5 °C (redondeo de la tesis). La calcedonia de Arnórsson (1983) no está en SOLMINEQ-Py y se calcula con
  su ecuación en el script. Reporte: reports/Comparacion_PHREEQC_SOLMINEQ.xlsx (idéntico en Windows y Linux).

### Pendientes

- utils.py todavía lee puna_speciation_results.csv (flujo anterior, retirado).
- Redox en el reequilibrio con CO2 (óxidos de Fe).
- Desfase de +0.06 a +0.42 en carbonatos frente a la tesis (a(CO3), pH profundo).
- Referencia bibliográfica de El Aguajito en el README.

---

<a id="adr-003"></a>
## ADR-003 — Arreglos de código: bases de USGS con bloques nuevos, gráfico de IS y script de aplicación (27/11/2026)

**Estado:** Aceptado. Aplicado el 27/11/2026, commit c16defd (23 passed).

**Contexto.**
- `src/utils.py` leía `data/processed/puna_speciation_results.csv`. Ese archivo lo generaba `modeler.py`, que ya se
  retiró, así que el gráfico no se podía generar.
- El phreeqc.dat actual de USGS trae los bloques `GAS_BINARY_PARAMETERS` y `MEAN_GAMMAS`. El IPhreeqc 3.7.3 de
  phreeqpy 0.6.0 no los reconoce y la base no carga.
- El script de aplicación de ADR-002 daba el mismo mensaje («incompleto o alterado») para causas distintas.

**Decisión.**
1. `engine.load_database_text`: si una base no carga y contiene esos bloques, los quita hasta la palabra clave
   siguiente, vuelve a probar la carga y avisa. Los bloques omitidos quedan anotados en `DATABASE_NOTES` y en la hoja
   `Configuracion_Corrida` (`BLOQUES_OMITIDOS_<base>`). Si la base sigue sin cargar, el motor se detiene como antes.
   Ninguno de los dos bloques interviene en la especiación ni en los IS: el primero solo afecta a GAS_PHASE con
   Peng-Robinson, y el segundo, a la salida de coeficientes de actividad medios. Verificado: el IS de calcita y de
   yeso es el mismo con y sin esos bloques.
2. `comparar_solmineq.py` carga las bases con esa misma función.
3. `utils.py`:
   - Lee `resultados_universales_phreeqc.csv` y genera un gráfico por proyecto, con un marcador por área. Antes, el
     área SA de la Puna Norte y la de El Aguajito se mezclaban.
   - Las fases se eligen con `--x` y `--y`; con `--proyecto` se grafica uno solo.
   - Usa el backend Agg, así que no abre ventanas.
   - Los límites de los ejes siempre incluyen IS = 0.
   - Las muestras sin alguno de los dos IS se omiten y se informan.
4. Scripts de aplicación. Primero revisan el paquete y separan «falta en el paquete» de «cambió en el paquete».
   Después informan el estado de cada archivo del repositorio: ya aplicado, versión base (se reemplaza), no existe
   (se crea), FALTA (debía existir) o CAMBIÓ (ni base ni nueva). Aceptan `--repo` y restauran lo escrito si una
   copia falla. Este es el patrón para los próximos ADR.

**Consecuencias.**
- Las salidas de la Puna Norte y de El Aguajito no cambian: el CSV regenerado es idéntico al de eea7208.
- phreeqc.dat queda utilizable. Se descarga la primera vez que se usa y no se versiona; si se adopta para algún
  proyecto, conviene versionarla como llnl.dat y wateq4f.dat.
- Pendiente menor: `test/test_modeler.py` está vacío (resto del flujo retirado). Se borra en ADR-004.

---

<a id="adr-004"></a>
## ADR-004 — Salidas legibles y trazables (28/11/2026)

**Estado:** Propuesto. Se acepta cuando pytest dé 49 passed.

### Contexto

En ADR-072 de SOLMINEQ, las entradas y salidas de PHREEQC no se pudieron subir como documentos: no tenían una
extensión de texto y mezclaban UTF-8 con Latin-1. Al revisar `engine.py` aparecieron seis riesgos:

1. Después de cada corrida, el motor movía *todo* `phreeqc*.out` de la carpeta de trabajo a
   `reporte_nativo_<Muestra>.out`. Un `.out` viejo o ajeno quedaba asignado a la muestra, y si había varios, el
   último pisaba a los demás.
2. Los `.out` mezclan UTF-8 (la entrada que PHREEQC repite) y Latin-1 (sus rótulos «°C», «cm³/mol»).
3. No se guardaba la entrada de PHREEQC de cada muestra, así que la corrida no se podía repetir fuera del motor.
4. El nombre de la muestra se usaba tal cual como nombre de archivo: `/`, `:` o un nombre reservado de Windows lo
   rompían.
5. Los avisos de PHREEQC no se capturaban; phreeqpy no los expone.
6. El reporte no registraba la versión de IPhreeqc ni el SHA-256 de las bases, así que un cambio de base pasaba
   inadvertido.

### Decisiones

1. **Carpeta aislada.** `run_sample` corre cada muestra en una carpeta temporal propia y recoge solo el `.out` que
   produjo esa corrida. Las rutas de entrada y salida se vuelven absolutas al empezar.
2. **Texto UTF-8.** Con `EXPORTAR_REPORTES_OUT = SI`, cada muestra deja en `reports/phreeqc/<Proyecto>/` tres
   archivos: `<Muestra>_entrada.txt` (equivale a un `.pqi`), `<Muestra>_salida.txt` (a un `.pqo`, convertida a
   UTF-8 con `copy_as_utf8`) y `<Muestra>_selected_output.txt` (separado por tabuladores). La columna
   `Archivos_PHREEQC` indica dónde quedaron. Ya no se escribe `data/processed/reporte_nativo_<Muestra>.out`.
3. **Nombres seguros.** `safe_filename` cambia `< > : " / \ | ? *` y los caracteres de control por `_`, quita puntos
   y espacios finales, evita CON, NUL, COM1 y los demás nombres reservados, y agrega `_2`, `_3`... si dos muestras
   de un proyecto dan el mismo nombre.
4. **Avisos.** Se leen de la librería IPhreeqc con ctypes (`GetWarningString`). La columna `Avisos` reúne los avisos
   del motor (por ejemplo, reequilibrio pedido sin P_CO2) y los de PHREEQC. Las fases del catálogo que no existen
   en una base («Mineral X, not found») aparecían en las 57 muestras: se sacan de `Avisos` y se informan una vez por
   base en la trazabilidad. Con ese cambio, solo 2 muestras de El Aguajito llevan aviso, por el peso equivalente de
   la alcalinidad «as CaCO3» (PHREEQC usa 50.0455 g/eq, que es el valor correcto).
5. **Trazabilidad.** Hoja `Trazabilidad` en el reporte y `<csv>_trazabilidad.json`, con:
   - la fecha, el commit, la versión de Python y el sistema;
   - las versiones de phreeqpy y de IPhreeqc, que se leen de la librería (3.7.3-15968);
   - la ruta y el SHA-256 de la plantilla;
   - de cada base: su SHA-256 (con finales de línea LF), su estado frente a `database/SHA256SUMS`, los bloques
     omitidos y las fases que no existen en ella.
   Si una base no coincide, el motor avisa en la consola.
6. **`database/SHA256SUMS`** registra llnl.dat y wateq4f.dat. Los valores son los mismos que exige la guía de
   ADR-072 de SOLMINEQ.
7. **Repositorio.**
   - `.gitignore` agrega `ADR-*/`, `reports/phreeqc/`, `data/processed/*_trazabilidad.json` y
     `data/processed/reporte_nativo_*.out`.
   - Se borra `test/test_modeler.py`, que estaba vacío.
   - Se crea este `DECISIONS.md`.
8. **`build_dynamic_phreeqc_input`** acepta una lista opcional `notices` para devolver sus avisos. Si no se pasa, se
   comporta igual que antes.
9. **Rutas en otra unidad (corrección de la primera entrega).** En Windows, `os.path.relpath` lanza ValueError cuando
   las dos rutas están en unidades distintas. Con el repositorio en H: y la carpeta temporal de pytest en C:, fallaba
   cada muestra y quedaba un CSV vacío (3 pruebas fallidas). `display_path` devuelve la ruta relativa si está dentro
   del repositorio y la absoluta si no. Además, si fallan todas las muestras, el motor se detiene con un error en
   lugar de escribir un CSV vacío, y al final lista las muestras que fallaron.

### Verificación

- Las columnas anteriores del CSV son idénticas a las de c16defd en las 57 muestras. Lo comprueba pytest, corriendo
  el motor completo en una carpeta temporal.
- Con un `phreeqc.0.out` viejo en la carpeta de trabajo, la salida de la muestra solo contiene su propia corrida, y
  el archivo viejo queda intacto.
- Todos los `.txt` se leen como UTF-8, y una base editada a propósito produce el aviso de SHA-256.
- La corrida completa de las pruebas simula un repositorio en otra unidad. Con el `engine.py` de la primera entrega,
  esas pruebas reproducen en Linux los 3 fallos observados en Windows; con la corrección, pasan.

### Consecuencias

- Los IS, el pH y el QC no cambian. Hay dos columnas nuevas, `Avisos` y `Archivos_PHREEQC`, y una hoja nueva,
  `Trazabilidad`.
- Los `reporte_nativo_<Muestra>.out` que ya existan en `data/processed/` dejan de actualizarse y se pueden borrar.
- Estos archivos de texto son la base del exportador de paquetes de referencia (ADR-008).
- Siguiente: ADR-005, con el `redox S(-2)/S(6)` y el aviso de temperatura con phreeqc.dat o wateq4f.dat, que sí
  cambia resultados.
