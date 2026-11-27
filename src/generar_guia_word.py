# -*- coding: utf-8 -*-
"""
Generador del Caso de Estudio en formato Word (.docx) para la materia
de Fluidos Hidrotermales, basado en Peralta Arnold (2018) y PHREEQC.
"""

import os
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
DOCX_OUTPUT = os.path.join(REPORTS_DIR, "Caso_Estudio_Fluidos_Hidrotermales.docx")

def build_word_case_study():
    os.makedirs(REPORTS_DIR, exist_ok=True)
    doc = Document()

    # Configuración de estilo base
    style = doc.styles['Normal']
    style.font.name = 'Calibri'
    style.font.size = Pt(11)

    # Título Principal
    title = doc.add_heading(
        'CASO DE ESTUDIO: ESPECIACIÓN GEOQUÍMICA Y REEQUILIBRIO PROFUNDO DE FLUIDOS HIDROTERMALES', 0
    )
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    p_sub = doc.add_paragraph()
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_sub = p_sub.add_run(
        'Materia: Fluidos Hidrotermales | Herramienta: Python (phreeqpy / IPhreeqc) + Base WATEQ4F\n'
        'Fuente de Datos: Peralta Arnold, Y. (2018) - Sistemas Geotermales de la Puna Norte y Subandinos (Jujuy, Argentina)'
    )
    run_sub.italic = True
    run_sub.font.color.rgb = RGBColor(80, 80, 80)

    # 1. Planteamiento del Problema
    doc.add_heading('1. Contexto y Problema Geoquímico', level=1)
    doc.add_paragraph(
        'Cuando un fluido hidrotermal asciende desde el reservorio hacia la superficie, experimenta una caída de presión '
        'que induce la desgasificación rápida de CO2(g). Esta pérdida de gas ácido desplaza el equilibrio del sistema '
        'carbonato (HCO3- + H+ -> H2O + CO2(g)), elevando artificialmente el pH medido en superficie respecto al pH real '
        'del reservorio profundo.'
    )
    doc.add_paragraph(
        'Si el modelador introduce directamente el pH de superficie en PHREEQC y declara el bicarbonato como alcalinidad '
        'total (Alkalinity) en aguas ricas en boro y sílice, el software calculará una sobresaturación ficticia de calcita '
        '(IS > 0). En esta práctica, el alumno reconstruirá las condiciones termodinámicas profundas utilizando los datos '
        'hidroquímicos y de gases disueltos del archivo adjunto "Datos_Caso_Estudio_Puna.xlsx".'
    )

    # 2. Objetivos e Instrucciones Técnicas
    doc.add_heading('2. Reglas Críticas para la Implementación en PHREEQC y Python', level=1)
    doc.add_paragraph(
        'Para replicar con éxito los Índices de Saturación (IS) publicados en la Tabla 6-7 de la tesis bajo una tolerancia '
        'de control de calidad de +/- 0.30 unidades logarítmicas, el alumno deberá aplicar estrictamente estas 5 reglas:'
    )

    reglas = [
        ('1. Base de Datos Termodinámica:', 'Utilizar exclusivamente wateq4f.dat (USGS), la cual incorpora las constantes de disociación para especies de boro, litio, flúor y sílice a temperaturas hidrotermales.'),
        ('2. Declaración del Carbono Inorgánico Total:', 'Ingresar el bicarbonato como "C(4) <valor> as HCO3" y NO como "Alkalinity". Esto evita que la alcalinidad no carbonatada (aportada por B(OH)4- y H3SiO4-) distorsione la actividad del ion CO3(2-).'),
        ('3. Reequilibrio con Presión Parcial de CO2:', 'Agregar un bloque EQUILIBRIUM_PHASES acoplando CO2(g) con el log10(P_CO2) reportado en la Tabla 6-5 de la tesis. Esto fuerza a PHREEQC a recalcular el pH profundo del reservorio.'),
        ('4. Extracción del Paso de Reacción en IPhreeqc:', 'Al incluir EQUILIBRIUM_PHASES, PHREEQC genera dos filas de resultados en selected_output: la fila [1] corresponde a la solución inicial sin reaccionar y la última fila [-1] corresponde al equilibrio profundo final. Siempre se debe extraer selected_output[-1].'),
        ('5. Captura Nativa del pH y Minúsculas:', 'Activar "-ph true" dentro de SELECTED_OUTPUT en lugar de usar PUNCH PH, y normalizar los encabezados a minúsculas (.lower().strip()) en Python, instanciando y destruyendo IPhreeqc() en cada muestra.')
    ]
    for titulo_regla, desc in reglas:
        p = doc.add_paragraph(style='List Bullet')
        r_bold = p.add_run(titulo_regla + ' ')
        r_bold.bold = True
        p.add_run(desc)

    # 3. Plantilla de Entrada de PHREEQC
    doc.add_heading('3. Estructura del Bloque de Entrada en PHREEQC (Ejemplo Muestra RE1)', level=1)
    code_text = (
        "TITLE Reequilibrio Geotérmico Profundo - Muestra RE1\n"
        "SOLUTION 1\n"
        "    temp        47.9\n"
        "    pH          7.69\n"
        "    units       mg/l\n"
        "    F           0.661\n"
        "    Cl          18.81\n"
        "    S(6)        476.0\n"
        "    Ca          65.2\n"
        "    Mg          8.17\n"
        "    Na          211.0\n"
        "    K           11.0\n"
        "    Li          0.21\n"
        "    C(4)        207.0 as HCO3\n"
        "    Si          52.0 as SiO2\n"
        "    B           0.31\n\n"
        "EQUILIBRIUM_PHASES 1\n"
        "    CO2(g)      -1.4949\n\n"
        "SELECTED_OUTPUT 1\n"
        "    -reset          false\n"
        "    -ph             true\n"
        "    -charge_balance true\n"
        "    -ionic_strength true\n"
        "    -user_punch     true\n\n"
        "USER_PUNCH 1\n"
        "    -headings si_Calcite si_Aragonite si_Gypsum si_Chalcedony si_Quartz\n"
        "    10 PUNCH SI(\"Calcite\")\n"
        "    20 PUNCH SI(\"Aragonite\")\n"
        "    30 PUNCH SI(\"Gypsum\")\n"
        "    40 PUNCH SI(\"Chalcedony\")\n"
        "    50 PUNCH SI(\"Quartz\")\n"
        "END"
    )
    p_code = doc.add_paragraph()
    run_code = p_code.add_run(code_text)
    run_code.font.name = 'Consolas'
    run_code.font.size = Pt(9.5)

    # 4. Guía Resuelta para el Profesor
    doc.add_page_break()
    doc.add_heading('4. Guía Resuelta para el Profesor (Referencia de Calificación)', level=1)
    doc.add_paragraph(
        'Los alumnos deberán reportar la siguiente tabla comparativa (disponible también en la pestaña '
        '"Guia_Resolucion_Profesor" del archivo Excel) aplicando la regla QC (|Delta| <= 0.30 -> PASA):'
    )

    headers = ['Muestra', 'T (°C)', 'pH Sup.', 'pH Prof.', 'IS Calcita (Mod)', 'IS Calcita (Tesis)', 'Delta Calc.', 'QC Calcita', 'IS Yeso (Mod)', 'IS Calced. (Mod)']
    rows_data = [
        ['RE1', '47.9', '7.69', '7.21', '-0.31', '-0.51', '+0.20', 'PASA', '-1.14', '+0.33'],
        ['AC1', '28.5', '7.54', '7.27', '-0.37', '-0.39', '+0.02', 'PASA', '-2.20', '+0.62'],
        ['J',   '28.7', '7.11', '7.11', '+0.79', '+0.67', '+0.12', 'PASA', '-1.05', '+0.57'],
        ['CA1', '49.3', '7.88', '7.35', '-0.45', '-0.71', '+0.26', 'PASA', '-1.67', '+0.64'],
        ['CA2', '43.3', '8.14', '7.45', '-0.39', '-0.62', '+0.23', 'PASA', '-1.65', '+0.70'],
        ['CA3', '49.0', '8.21', '7.39', '-0.40', '-0.68', '+0.28', 'PASA', '-1.65', '+0.65'],
        ['PA1', '41.7', '6.71', '6.71', '+1.20', '+1.13', '+0.07', 'PASA', '-0.77', '+0.83'],
        ['PA3', '42.1', '6.59', '6.59', '+1.10', '+1.10', '0.00',  'PASA', '-0.80', '+0.82'],
        ['SA',  '72.0', '7.49', '7.11', '+0.61', '+0.25', '+0.36', 'REVISAR', '-1.43', '+0.02']
    ]

    table = doc.add_table(rows=1, cols=len(headers))
    table.style = 'Table Grid'
    hdr_cells = table.rows[0].cells
    for i, h_text in enumerate(headers):
        hdr_cells[i].text = h_text
        for paragraph in hdr_cells[i].paragraphs:
            for run in paragraph.runs:
                run.bold = True
                run.font.size = Pt(9)

    for row_vals in rows_data:
        row_cells = table.add_row().cells
        for i, val in enumerate(row_vals):
            row_cells[i].text = val
            for paragraph in row_cells[i].paragraphs:
                for run in paragraph.runs:
                    run.font.size = Pt(9)

    # 5. Rúbrica de Discusión
    doc.add_heading('5. Pauta de Discusión Geoquímica para Evaluación', level=1)
    discusion = [
        ('Independencia del pH en Yeso y Calcedonia:', 'El alumno debe concluir que los IS de yeso y calcedonia coinciden exactamente (Delta < 0.05) con o sin reequilibrio de CO2 porque, en el rango de pH de 6.5 a 8.2, ni el sulfato de calcio ni la sílice disuelta (H4SiO4) sufren disociación ácida significativa.'),
        ('Corrección de la Falsa Sobresaturación en RE1, AC1 y CA1-CA3:', 'El alumno debe demostrar que al reequilibrar el agua con la P_CO2 profunda, el pH desciende de ~7.7-8.2 a ~7.2-7.4, revelando que el fluido en el reservorio está realmente subsaturado en calcita (IS entre -0.31 y -0.45) y no sobresaturado como sugería el pH de campo.'),
        ('Riesgo de Incrustación en Termas del Palmar (PA1, PA3):', 'El alumno debe identificar que las muestras de El Palmar presentan una fuerte sobresaturación genuina en calcita (IS > +1.10) y el mayor acercamiento a la saturación en yeso (-0.77), producto de la disolución de carbonatos y evaporitas (Fm. Yacoraite), lo que implica alto potencial de precipitación de travertinos.'),
        ('Análisis de la Excepción en San Antonio (SA - 72 °C):', 'El alumno debe justificar por qué SA supera levemente el umbral de +/- 0.30 (Delta = +0.36): al ser la manifestación de mayor temperatura (72 °C) y surgir a ~3800 msnm, experimenta separación bifásica y pérdida fraccionada de vapor previa al muestreo, requiriendo un balance entálpico vapor-líquido adicional.')
    ]
    for punto, explicacion in discusion:
        p = doc.add_paragraph(style='List Number')
        r_b = p.add_run(punto + ' ')
        r_b.bold = True
        p.add_run(explicacion)

    doc.save(DOCX_OUTPUT)
    print(f"[+] Caso de estudio en Word generado exitosamente en: {DOCX_OUTPUT}")

if __name__ == "__main__":
    build_word_case_study()
