# -*- coding: utf-8 -*-
"""Pruebas del ADR-004: salidas legibles y trazables (carpeta aislada, texto UTF-8, avisos, trazabilidad)."""
import json
import os
import shutil

import pandas as pd
import pytest

import engine

DB_DIR = os.path.join(engine.BASE_DIR, "database")
SIMPLE = """TITLE Muestra de prueba ADR-004
SOLUTION 1
    temp 90
    pH 7
    units mg/l
    Na 100
    Cl 150
    Ca 40
    C(4) 100 as HCO3
SELECTED_OUTPUT 1
    -reset false
    -ph true
USER_PUNCH 1
    -headings si_Calcite si_Inexistente
    10 PUNCH SI("Calcite"), SI("Inexistente")
END
"""


def _db(name="wateq4f.dat"):
    return engine.load_database_text(name, {})


# --- nombres de archivo ------------------------------------------------------------------------------

@pytest.mark.parametrize("name, expected", [
    ("RE2", "RE2"), ("ID01_CR01E", "ID01_CR01E"), ("CA1/CA2", "CA1_CA2"), ('a:b*c?"d"<e>|f', "a_b_c__d__e__f"),
    ("muestra. ", "muestra"), ("CON", "_CON"), ("nul.txt", "_nul.txt"), ("", "muestra"), ("   ", "muestra"),
    ("Sañogasta °C", "Sañogasta °C"),
])
def test_safe_filename(name, expected):
    assert engine.safe_filename(name) == expected


def test_safe_filename_avoids_collisions():
    used = set()
    assert [engine.safe_filename(n, used) for n in ("A/1", "A_1", "a_1", "B")] == ["A_1", "A_1_2", "a_1_3", "B"]


# --- texto UTF-8 -------------------------------------------------------------------------------------

def test_copy_as_utf8_mixed_encodings(tmp_path):
    """PHREEQC repite la entrada en UTF-8 y escribe «°C» y «cm³» en Latin-1: el resultado es UTF-8 válido."""
    src = tmp_path / "mixto.out"
    src.write_bytes("Título: CaCl2°\n".encode("utf-8") + b"Temperature (\xb0C) = 90\ncm\xb3/mol\n")
    dst = tmp_path / "salida.txt"
    engine.copy_as_utf8(str(src), str(dst))
    assert dst.read_bytes().decode("utf-8") == "Título: CaCl2°\nTemperature (°C) = 90\ncm³/mol\n"


# --- corrida aislada ---------------------------------------------------------------------------------

def test_run_sample_isolated_from_stale_outputs(tmp_path, monkeypatch):
    """Un phreeqc.0.out viejo en la carpeta de trabajo no se asigna a la muestra ni se mueve (riesgo 1)."""
    workdir = tmp_path / "trabajo"
    workdir.mkdir()
    stale = workdir / "phreeqc.0.out"
    stale.write_text("REPORTE VIEJO DE OTRA CORRIDA\n", encoding="utf-8")
    monkeypatch.chdir(workdir)
    out = tmp_path / "salidas"
    out.mkdir()
    selected, warnings, missing = engine.run_sample(SIMPLE, _db(), str(out), "M1")
    assert os.getcwd() == str(workdir) and stale.read_text(encoding="utf-8").startswith("REPORTE VIEJO")
    salida = (out / "M1_salida.txt").read_text(encoding="utf-8")
    assert "Muestra de prueba ADR-004" in salida and "REPORTE VIEJO" not in salida and "°C" in salida
    assert (out / "M1_entrada.txt").read_text(encoding="utf-8") == SIMPLE
    sel = (out / "M1_selected_output.txt").read_text(encoding="utf-8").splitlines()
    assert sel[0].split("\t") == [str(h) for h in selected[0]] and len(sel) == len(selected)
    assert sorted(os.listdir(out)) == ["M1_entrada.txt", "M1_salida.txt", "M1_selected_output.txt"]


def test_run_sample_without_export_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    selected, _, _ = engine.run_sample(SIMPLE, _db())
    assert len(selected) == 2 and os.listdir(tmp_path) == []


def test_warnings_and_missing_phases():
    """Los avisos de PHREEQC se capturan; las fases inexistentes van aparte (riesgo 5)."""
    text = SIMPLE.replace("    Ca 40\n", "    Ca 40\n    Xx 1\n")
    _, warnings, missing = engine.run_sample(text, _db())
    assert "Could not find element in database, Xx" in warnings
    assert "not found" not in warnings and missing == {"Inexistente"}


# --- rutas en otra unidad (Windows) -------------------------------------------------------------------

def test_display_path_inside_and_outside_repo(tmp_path):
    inside = os.path.join(engine.BASE_DIR, "reports", "phreeqc", "P", "M1")
    assert engine.display_path(inside) == os.path.join("reports", "phreeqc", "P", "M1")
    assert engine.display_path(str(tmp_path / "M1")) == str(tmp_path / "M1")


def test_display_path_other_drive(monkeypatch, tmp_path):
    """En Windows, relpath entre unidades distintas (H: y C:) lanza ValueError: se usa la ruta absoluta."""
    def relpath_other_drive(path, start=None):
        raise ValueError("path is on mount 'C:', start on mount 'H:'")

    monkeypatch.setattr(engine.os.path, "relpath", relpath_other_drive)
    assert engine.display_path(str(tmp_path / "M1")) == str(tmp_path / "M1")
    info, _ = engine.build_traceability(engine.DEFAULT_TEMPLATE, ["wateq4f.dat"])
    assert info["plantilla"] == os.path.abspath(engine.DEFAULT_TEMPLATE)


def test_engine_stops_if_every_sample_fails(tmp_path, monkeypatch):
    """Si fallan todas las muestras, el motor se detiene en vez de escribir un CSV vacío."""
    def broken(*args, **kwargs):
        raise RuntimeError("falla simulada")

    monkeypatch.setattr(engine, "run_sample", broken)
    monkeypatch.setattr(engine, "REPORTS_PHREEQC_DIR", str(tmp_path / "phreeqc"))
    with pytest.raises(RuntimeError, match="Fallaron las 57 muestras"):
        engine.run_universal_engine(engine.DEFAULT_TEMPLATE, str(tmp_path / "r.xlsx"), str(tmp_path / "r.csv"))
    assert not (tmp_path / "r.csv").exists()


# --- trazabilidad ------------------------------------------------------------------------------------

def test_sha256sums_registers_versioned_bases():
    sums = engine.read_sha256sums()
    for name in ("llnl.dat", "wateq4f.dat"):
        assert sums[name] == engine.text_sha256(os.path.join(DB_DIR, name))


def test_text_sha256_ignores_crlf(tmp_path):
    lf, crlf = tmp_path / "lf.dat", tmp_path / "crlf.dat"
    lf.write_bytes(b"PHASES\nCalcite\n")
    crlf.write_bytes(b"PHASES\r\nCalcite\r\n")
    assert engine.text_sha256(str(lf)) == engine.text_sha256(str(crlf))


def test_traceability_ok():
    info, warnings = engine.build_traceability(engine.DEFAULT_TEMPLATE, ["llnl.dat", "wateq4f.dat"])
    assert warnings == []
    assert info["iphreeqc"].startswith("3.") and info["phreeqpy"] != "desconocida"
    assert info["plantilla"].replace("\\", "/") == "data/raw/Plantilla_Modelado_Geoquimico.xlsx"
    for name in ("llnl.dat", "wateq4f.dat"):
        assert info["bases"][name]["estado"] == "coincide con database/SHA256SUMS"
    rows = dict(engine.traceability_rows(info))
    assert rows["base llnl.dat: sha256"] == info["bases"]["llnl.dat"]["sha256"]


def test_traceability_detects_modified_database(tmp_path, monkeypatch):
    """Una base editada (otro SHA-256) produce un aviso (riesgo 6)."""
    edited = tmp_path / "wateq4f.dat"
    shutil.copyfile(os.path.join(DB_DIR, "wateq4f.dat"), edited)
    with open(edited, "a", encoding="utf-8") as fh:
        fh.write("\n# editada\n")
    monkeypatch.setattr(engine, "ensure_database", lambda name: str(edited))
    info, warnings = engine.build_traceability(engine.DEFAULT_TEMPLATE, ["wateq4f.dat"])
    assert info["bases"]["wateq4f.dat"]["estado"].startswith("NO COINCIDE")
    assert len(warnings) == 1 and "no coincide" in warnings[0]


# --- motor completo: los resultados no cambian ---------------------------------------------------------

@pytest.fixture(scope="module")
def engine_run(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("adr004")
    mp = pytest.MonkeyPatch()
    mp.setattr(engine, "REPORTS_PHREEQC_DIR", str(tmp / "phreeqc"))
    real_relpath = os.path.relpath

    def relpath_like_windows(path, start=os.curdir):
        """Como en Windows con el repositorio en otra unidad que la carpeta temporal."""
        if not os.path.abspath(path).startswith(engine.BASE_DIR):
            raise ValueError("path is on mount 'C:', start on mount 'H:'")
        return real_relpath(path, start)

    mp.setattr(engine.os.path, "relpath", relpath_like_windows)
    try:
        engine.run_universal_engine(engine.DEFAULT_TEMPLATE, str(tmp / "rep.xlsx"), str(tmp / "res.csv"))
    finally:
        mp.undo()
    return tmp


def test_results_unchanged(engine_run):
    """Criterio de aceptación: las columnas anteriores del CSV son idénticas a las versionadas."""
    new = pd.read_csv(engine_run / "res.csv")
    old = pd.read_csv(engine.DEFAULT_OUTPUT_CSV)
    cols = [c for c in old.columns if c not in ("Avisos", "Archivos_PHREEQC")]
    assert [c for c in new.columns if c not in ("Avisos", "Archivos_PHREEQC")] == cols
    pd.testing.assert_frame_equal(new[cols], old[cols])
    assert {"Avisos", "Archivos_PHREEQC"} <= set(new.columns)


def test_engine_outputs(engine_run):
    new = pd.read_csv(engine_run / "res.csv")
    files = list((engine_run / "phreeqc").rglob("*.txt"))
    assert len(files) == 3 * len(new)
    for f in files:
        f.read_bytes().decode("utf-8")
    for path in new["Archivos_PHREEQC"]:  # fuera del repositorio: ruta absoluta (ADR-004, rutas en otra unidad)
        assert os.path.isabs(path) and os.path.isfile(path + "_salida.txt")
    sheets = pd.read_excel(engine_run / "rep.xlsx", sheet_name=None)
    assert list(sheets) == ["Resultados_y_QC", "Configuracion_Corrida", "Trazabilidad"]
    trace = json.loads((engine_run / "res_trazabilidad.json").read_text(encoding="utf-8"))
    assert set(trace["bases"]) == set(new["Base_Datos"])


def test_engine_warnings_column(engine_run):
    """Solo las muestras con avisos reales llevan texto; las fases faltantes no se repiten por muestra."""
    new = pd.read_csv(engine_run / "res.csv")
    avisos = new["Avisos"].fillna("")
    assert not avisos.str.contains("not found").any()
    assert avisos.str.contains("alkalinity").sum() >= 1


# --- repositorio --------------------------------------------------------------------------------------

def test_gitignore_and_cleanup():
    with open(os.path.join(engine.BASE_DIR, ".gitignore"), encoding="utf-8") as fh:
        text = fh.read()
    for pattern in ("ADR-*/", "reports/phreeqc/", "data/processed/*_trazabilidad.json",
                    "data/processed/reporte_nativo_*.out"):
        assert pattern in text.splitlines()
    assert not os.path.exists(os.path.join(engine.BASE_DIR, "test", "test_modeler.py"))
