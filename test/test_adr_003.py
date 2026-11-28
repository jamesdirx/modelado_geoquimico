# -*- coding: utf-8 -*-
"""Pruebas del ADR-003: bases de USGS con bloques que IPhreeqc 3.7.3 no reconoce y gráfico de IS (utils.py)."""
import os

import numpy as np
import pandas as pd
import pytest

import engine
import utils

DB_DIR = os.path.join(engine.BASE_DIR, "database")

#: Bloques como los de la versión actual de phreeqc.dat de USGS (master, 2024-2026).
NEW_BLOCKS = (
    "GAS_BINARY_PARAMETERS\n"
    "H2O(g)  CO2(g)           0.19\n"
    "H2O(g)  H2S(g)           0.19\n"
    "MEAN_GAMMAS\n"
    "CaCl2    Ca+2  1  Cl-    2\n"
    "CaSO4    Ca+2  1  SO4-2  1\n"
)


@pytest.fixture
def notes_clean():
    engine.DATABASE_NOTES.clear()
    yield
    engine.DATABASE_NOTES.clear()


def _wateq4f():
    with open(os.path.join(DB_DIR, "wateq4f.dat"), encoding="utf-8", errors="ignore") as fh:
        return fh.read()


def _wateq4f_with(extra):
    """wateq4f.dat con ``extra`` antes del primer PHASES (al final no sirve: la base termina en END)."""
    text = _wateq4f()
    assert text.count("\nPHASES\n") >= 1
    return text.replace("\nPHASES\n", "\n" + extra + "PHASES\n", 1)


# --- 5. bases con bloques no reconocidos ------------------------------------------------------------

def test_strip_removes_blocks_until_next_keyword():
    text = "PHASES\nCalcite\n    CaCO3 = Ca+2 + CO3-2\n" + NEW_BLOCKS + "SURFACE_MASTER_SPECIES\nHfo_s Hfo_sOH\n"
    out, removed = engine.strip_unsupported_blocks(text)
    assert removed == ["GAS_BINARY_PARAMETERS", "MEAN_GAMMAS"]
    assert "H2O(g)" not in out and "CaCl2" not in out
    assert out == "PHASES\nCalcite\n    CaCO3 = Ca+2 + CO3-2\nSURFACE_MASTER_SPECIES\nHfo_s Hfo_sOH\n"


def test_formulas_are_not_keywords():
    """H2O(g), CaCl2 o CO2 empiezan con mayúscula pero no cierran el bloque."""
    for line in ("H2O(g)  N2(g) 0.49", "CaCl2    Ca+2  1", "CO2(g)", "NaCl", "PHASES2"):
        assert engine._KEYWORD.match(line) is None or engine._KEYWORD.match(line).group(1) == "PHASES2"
    for line in ("PHASES", "MEAN_GAMMAS", "SOLUTION_SPECIES # comentario", "RATES  "):
        assert engine._KEYWORD.match(line) is not None


@pytest.mark.parametrize("db", ["llnl.dat", "wateq4f.dat"])
def test_versioned_databases_untouched(db, notes_clean):
    with open(os.path.join(DB_DIR, db), encoding="utf-8", errors="ignore") as fh:
        text = fh.read()
    assert engine.strip_unsupported_blocks(text) == (text, [])
    cache = {}
    assert engine.load_database_text(db, cache) == text
    assert db not in engine.DATABASE_NOTES


def test_database_with_new_blocks_loads(tmp_path, monkeypatch, notes_clean, capsys):
    """Una base con GAS_BINARY_PARAMETERS y MEAN_GAMMAS (como phreeqc.dat de USGS) carga sin esos bloques."""
    path = tmp_path / "con_bloques.dat"
    path.write_text(_wateq4f_with(NEW_BLOCKS), encoding="utf-8")
    assert engine._load_errors(path.read_text(encoding="utf-8"))  # tal cual, IPhreeqc 3.7.3 no la carga
    monkeypatch.setattr(engine, "ensure_database", lambda name: str(path))
    text = engine.load_database_text("con_bloques.dat", {})
    assert "GAS_BINARY_PARAMETERS" not in text and "MEAN_GAMMAS" not in text
    assert engine.DATABASE_NOTES["con_bloques.dat"] == ["GAS_BINARY_PARAMETERS", "MEAN_GAMMAS"]
    assert "se omitieron los bloques GAS_BINARY_PARAMETERS, MEAN_GAMMAS" in capsys.readouterr().out


def test_stripped_database_gives_same_si(tmp_path, monkeypatch, notes_clean):
    """Quitar los bloques no cambia la especiación: mismo IS que la base sin ellos."""
    from phreeqpy.iphreeqc.phreeqc_dll import IPhreeqc

    path = tmp_path / "con_bloques.dat"
    path.write_text(_wateq4f_with(NEW_BLOCKS), encoding="utf-8")
    monkeypatch.setattr(engine, "ensure_database", lambda name: str(path))
    results = []
    for text in (engine.load_database_text("con_bloques.dat", {}), _wateq4f()):
        ip = IPhreeqc()
        try:
            ip.load_database_string(text)
            ip.run_string("SOLUTION 1\n temp 90\n pH 7\n Na 10\n Cl 10\n Ca 40\n C(4) 100 as HCO3\n"
                          "SELECTED_OUTPUT\n -reset false\n -si Calcite Gypsum\nEND\n")
            results.append(ip.get_selected_output_array()[1])
        finally:
            ip.destroy_iphreeqc()
    assert results[0] == pytest.approx(results[1])


def test_database_that_still_fails_raises(tmp_path, monkeypatch, notes_clean):
    path = tmp_path / "rota.dat"
    path.write_text(_wateq4f_with(NEW_BLOCKS + "PHASES\nFaseRota\n    log_k -1\n"), encoding="utf-8")
    monkeypatch.setattr(engine, "ensure_database", lambda name: str(path))
    with pytest.raises(RuntimeError, match="no pudo cargar la base 'rota.dat'"):
        engine.load_database_text("rota.dat", {})
    assert "rota.dat" not in engine.DATABASE_NOTES


# --- 4. utils.py: gráfico de IS ---------------------------------------------------------------------

@pytest.fixture
def results_csv(tmp_path):
    df = pd.DataFrame({
        "Proyecto": ["P1", "P1", "P1", "P2", "P2"],
        "Area": ["A", "B", "A", "C", "C"],
        "Muestra": ["m1", "m2", "m3", "m4", "m5"],
        "si_Calcite": [0.5, -1.2, np.nan, np.nan, np.nan],
        "si_Gypsum": [-1.0, -2.0, -0.5, -0.3, -0.4],
        "si_Calcite_Ref": [0.4, -1.0, np.nan, np.nan, np.nan],
    })
    path = tmp_path / "resultados.csv"
    df.to_csv(path, index=False)
    return path


def test_utils_reads_current_engine_csv():
    assert utils.INPUT_PATH == engine.DEFAULT_OUTPUT_CSV
    if os.path.exists(utils.INPUT_PATH):
        df = utils.load_results()
        assert utils.si_column(df, "calcite") == "si_Calcite"


def test_plots_one_file_per_project(results_csv, tmp_path):
    out = tmp_path / "figs"
    res = utils.generate_saturation_index_plots(str(results_csv), str(out))
    assert res["P1"]["plotted"] == 2 and res["P1"]["skipped"] == ["m3"]
    assert os.path.getsize(res["P1"]["path"]) > 10_000
    assert os.path.basename(res["P1"]["path"]) == "Calcite_vs_Gypsum_P1.png"
    assert res["P2"]["path"] is None and res["P2"]["skipped"] == ["m4", "m5"]
    assert sorted(os.listdir(out)) == ["Calcite_vs_Gypsum_P1.png"]


def test_project_filter_and_other_phases(results_csv, tmp_path):
    res = utils.generate_saturation_index_plots(str(results_csv), str(tmp_path), "Gypsum", "Calcite", proyecto="P1")
    assert list(res) == ["P1"] and res["P1"]["plotted"] == 2
    with pytest.raises(ValueError, match="No hay filas del proyecto"):
        utils.generate_saturation_index_plots(str(results_csv), str(tmp_path), proyecto="NoExiste")


def test_missing_phase_and_missing_csv(results_csv, tmp_path):
    with pytest.raises(KeyError, match="Fases disponibles: Calcite, Gypsum"):
        utils.generate_saturation_index_plots(str(results_csv), str(tmp_path), "Calcite", "Barite")
    with pytest.raises(FileNotFoundError, match="src/engine.py"):
        utils.load_results(str(tmp_path / "no_existe.csv"))
