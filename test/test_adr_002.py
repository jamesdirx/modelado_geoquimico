# -*- coding: utf-8 -*-
"""Pruebas del ADR-002: datos de la Puna Norte desde la tesis, base por fila y comparación con SOLMINEQ-Py."""
import math
import os

import numpy as np
import pandas as pd
import pytest

import engine
import importar_puna_tesis as imp

TEMPLATE = imp.TEMPLATE


@pytest.fixture(scope="module")
def puna():
    return imp.puna_rows(imp.read_thesis())


@pytest.fixture(scope="module")
def template():
    config, minerals, data = engine.load_excel_configuration(TEMPLATE)
    return config, minerals, data


def _row(data, muestra):
    return data[data["Muestra"] == muestra].iloc[0]


# --- datos de la tesis ------------------------------------------------------------------------------

def test_plantilla_coincide_con_la_tesis():
    assert imp.check_template() == []


def test_muestras_sin_gases_no_reequilibran(puna):
    for name in ("ACF", "LC", "PA2"):
        row = puna[name]
        assert row["P_CO2_profunda_bar"] is None
        assert (row["Modo_pH"], row["Modo_Gas"]) == ("FIJO_CAMPO", "SIN_GAS")
        assert "Tabla 6-5" in row["Nota_Datos"]
    assert "no incluye PA2" in puna["PA2"]["Nota_Datos"]


def test_p_co2_corregida_y_columnas_no_informadas(puna):
    assert puna["RE2"]["P_CO2_profunda_bar"] == pytest.approx(0.027)
    assert puna["RE3"]["P_CO2_profunda_bar"] == pytest.approx(0.029)
    for row in puna.values():
        assert row["Pb_traza"] is None and row["S_2_mgL"] is None and row["Al_traza"] is None
        assert row["Base_Datos"] == "llnl.dat"


def test_metales_tal_cual_y_bajo_limite(puna):
    # Ba y Sb como en la Tabla 6-4 (la baritina de la Tabla 6-7 lo confirma)
    assert puna["CA1"]["Ba_traza"] == pytest.approx(57.98)
    assert puna["CA1"]["Sb_traza"] == pytest.approx(919.79)
    assert puna["J"]["Ni_traza"] is None and puna["J"]["Cu_traza"] == pytest.approx(4.38)
    # "<1" no se inventa: queda vacío y se anota
    assert puna["CA3"]["Zn_traza"] is None and "Zn_traza: bajo límite" in puna["CA3"]["Nota_Datos"]


def test_referencias_tabla_6_7_y_6_8(puna):
    assert puna["RE1"]["si_Calcite_Ref"] == pytest.approx(-0.51)
    assert puna["CA1"]["si_Barite_Ref"] == pytest.approx(0.44)
    assert puna["CA3"]["si_Zincite_Ref"] is None  # sin dato en la tesis
    assert puna["CA3"]["T_NaK_Truesdell1976_Ref"] == pytest.approx(-4.0)
    assert puna["PA1"]["T_KMg_Giggenbach_Ref"] == pytest.approx(96.0)
    assert puna["RE2"]["si_Calcite_Ref"] is None


def test_clean_valores_especiales():
    assert imp._clean("<1") == (None, "bajo límite de detección (<1)")
    assert imp._clean("n.d.") == (None, "n.d.")
    assert imp._clean("185*") == (185.0, None)
    assert imp._clean(None) == (None, None)


# --- motor --------------------------------------------------------------------------------------------

def test_base_por_fila(template):
    config, _, data = template
    assert engine.database_for_row(_row(data, "RE1"), config) == "llnl.dat"
    aguajito = data[data["Proyecto"] == "El_Aguajito"].iloc[0]
    assert engine.database_for_row(aguajito, config) == str(config["BASE_DATOS_ACTIVA"]).strip()


def test_entrada_phreeqc_puna(template):
    config, minerals, data = template
    text, _ = engine.build_dynamic_phreeqc_input(_row(data, "RE1"), config, minerals)
    assert f"CO2(g)      {math.log10(0.032):.4f}" in text
    assert "N(5)" in text and "as NO3" in text and "\n    Br " in text and "\n    Co " in text
    assert "Pb " not in text and "S(-2)" not in text
    text_pa2, _ = engine.build_dynamic_phreeqc_input(_row(data, "PA2"), config, minerals)
    assert "EQUILIBRIUM_PHASES" not in text_pa2


def test_aviso_reequilibrio_sin_p_co2(template, capsys):
    config, minerals, data = template
    row = _row(data, "PA2").copy()
    row["Modo_pH"], row["Modo_Gas"] = "REEQUILIBRIO_GAS", "CO2_PROFUNDO"
    text, _ = engine.build_dynamic_phreeqc_input(row, config, minerals)
    assert "EQUILIBRIUM_PHASES" not in text
    assert "sin P_CO2_profunda_bar" in capsys.readouterr().out


def test_base_que_no_carga_da_error_claro(tmp_path, monkeypatch):
    bad = tmp_path / "rota.dat"
    bad.write_text("SOLUTION_MASTER_SPECIES\nH H+ -1. H 1.008\nGAS_BINARY_PARAMETERS\nH2O(g) CO2(g) 0.19\n",
                   encoding="utf-8")
    monkeypatch.setattr(engine, "ensure_database", lambda name: str(bad))
    with pytest.raises(RuntimeError, match="no pudo cargar la base"):
        engine.load_database_text("rota.dat", {})


def test_llnl_reproduce_tabla_6_7(template):
    """Con llnl.dat y reequilibrio con CO2 el motor reproduce las fases no carbonatadas de la tesis."""
    config, minerals, data = template
    from phreeqpy.iphreeqc.phreeqc_dll import IPhreeqc

    db = engine.load_database_text("llnl.dat", {})
    checks = ("Anhydrite", "Gypsum", "Barite", "Halite", "Chalcedony", "Quartz")
    deltas = []
    for _, row in data[(data["Proyecto"] == "Puna_Norte") & data["P_CO2_profunda_bar"].notna()].iterrows():
        text, _ = engine.build_dynamic_phreeqc_input(row, config, minerals)
        ip = IPhreeqc()
        try:
            ip.load_database_string(db)
            ip.run_string(text)
            out = ip.get_selected_output_array()
        finally:
            ip.destroy_iphreeqc()
        values = dict(zip([str(h) for h in out[0]], out[-1]))
        for phase in checks:
            ref = row.get(f"si_{phase}_Ref")
            if pd.notna(ref):
                deltas.append(abs(values[f"si_{phase}"] - float(ref)))
    assert len(deltas) >= 40
    assert np.median(deltas) <= 0.02 and max(deltas) <= 0.10


# --- comparación con SOLMINEQ-Py (opcional) ---------------------------------------------------------

def test_comparacion_solmineq():
    pytest.importorskip("solmineq_app", reason="solmineq_app no está instalado (pip install -e <ruta a SOLMINEQ>)")
    import comparar_solmineq as cmp

    tables = cmp.compare(TEMPLATE, "Puna_Norte")
    geo = tables["Geotermometros"].dropna(subset=["Δ (°C)"])
    assert len(geo) == 66 and geo["Δ (°C)"].abs().max() <= 0.5  # la Tabla 6-8 se publica redondeada al °C
    si = tables["IS"]
    a = si[(si["Escenario"] == "A_superficie") & (si["Mineral"] == "Calcita")]
    assert a["Δ wateq4f − SOLMINEQ"].abs().max() <= 0.05
    assert set(si[si["Escenario"] == "B_profundo"]["Muestra"]).isdisjoint({"ACF", "LC", "PA2"})
