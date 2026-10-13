import json
import shutil
from pathlib import Path

from src import schema
from src.export_data import construir_json, load_recipes, normalizar, run_export, validar

FIXTURES = Path(__file__).parent / "fixtures"


def _load_one(tmp_path, filename):
    shutil.copy(FIXTURES / filename, tmp_path / filename)
    if filename == "ok_minimal.md":
        (tmp_path / "cover.jpg").write_text("x", encoding="utf-8")
    raws = load_recipes(tmp_path)
    records = normalizar(raws)
    errors, warnings = validar(records, tmp_path)
    return records, errors, warnings


def test_ok_minimal_no_errors_no_warnings(tmp_path):
    _, errors, warnings = _load_one(tmp_path, "ok_minimal.md")
    assert errors == []
    assert warnings == []


def test_falta_titulo_es_error(tmp_path):
    _, errors, _ = _load_one(tmp_path, "broken_sin_titulo.md")
    assert any("titulo" in e for e in errors)


def test_sin_categorias_es_error(tmp_path):
    _, errors, _ = _load_one(tmp_path, "broken_sin_categorias.md")
    assert any("categorias" in e for e in errors)


def test_categoria_invalida_es_error(tmp_path):
    _, errors, _ = _load_one(tmp_path, "broken_categoria_invalida.md")
    assert any("categoria desconocida" in e for e in errors)


def test_dificultad_invalida_es_error(tmp_path):
    _, errors, _ = _load_one(tmp_path, "broken_dificultad_invalida.md")
    assert any("dificultad desconocida" in e for e in errors)


def test_tipo_bebida_invalido_es_error(tmp_path):
    _, errors, _ = _load_one(tmp_path, "broken_tipo_bebida_invalido.md")
    assert any("tipo_bebida desconocido" in e for e in errors)


def test_bebida_sin_tipo_bebida_es_warning(tmp_path):
    _, errors, warnings = _load_one(tmp_path, "warnings_bebida_sin_tipo.md")
    assert errors == []
    assert any(w["field"] == "tipo_bebida" for w in warnings)


def test_postre_sin_tipo_bebida_no_es_warning(tmp_path):
    _, errors, warnings = _load_one(tmp_path, "ok_minimal.md")
    assert errors == []
    assert not any(w["field"] == "tipo_bebida" for w in warnings)


def test_tipo_merienda_invalido_es_error(tmp_path):
    _, errors, _ = _load_one(tmp_path, "broken_tipo_merienda_invalido.md")
    assert any("tipo_merienda desconocido" in e for e in errors)


def test_merienda_sin_tipo_merienda_es_warning(tmp_path):
    _, errors, warnings = _load_one(tmp_path, "warnings_merienda_sin_tipo.md")
    assert errors == []
    assert any(w["field"] == "tipo_merienda" for w in warnings)


def test_principal_sin_momento_no_es_warning(tmp_path):
    # "momento" es una excepción puntual (ej. Asado), no algo que toda
    # receta "principal" deba tener — su ausencia es el caso normal.
    _, errors, warnings = _load_one(tmp_path, "ok_minimal.md")
    assert errors == []
    assert not any(w["field"] == "momento" for w in warnings)


def test_tiempo_no_numerico_es_error(tmp_path):
    _, errors, _ = _load_one(tmp_path, "broken_tiempo_no_numerico.md")
    assert any("tiempo_minutos" in e for e in errors)


def test_cuerpo_vacio_es_error(tmp_path):
    _, errors, _ = _load_one(tmp_path, "broken_cuerpo_vacio.md")
    assert any("cuerpo" in e for e in errors)


def test_sin_frontmatter_es_error(tmp_path):
    _, errors, _ = _load_one(tmp_path, "broken_sin_frontmatter.md")
    assert any("frontmatter" in e for e in errors)


def test_warnings_varios(tmp_path):
    _, errors, warnings = _load_one(tmp_path, "warnings_varios.md")
    assert errors == []
    fields = {w["field"] for w in warnings}
    assert "dificultad" in fields
    assert "tiempo_minutos" in fields
    assert "foto" in fields
    assert "nota_extra" in fields


def test_build_json_contrato_y_allowlist(tmp_path):
    _, errors, warnings = _load_one(tmp_path, "ok_minimal.md")
    assert errors == []
    raws = load_recipes(tmp_path)
    records = normalizar(raws)
    data = construir_json(records, warnings)

    assert data["meta"]["schema_version"] == schema.SCHEMA_VERSION
    assert data["meta"]["count"] == 1
    receta = data["recetas"][0]
    allowed = {
        "id", "titulo", "categorias", "dificultad", "tiempo_minutos",
        "tiempo_minutos_max", "porciones", "foto", "fecha_actualizacion",
        "fuente", "tipo_bebida", "tipo_merienda", "momento", "body_html",
    }
    assert set(receta.keys()) == allowed
    assert receta["foto"] == "images/cover.jpg"


def test_error_deja_intacto_lo_publicado(tmp_path):
    recipes_dir = tmp_path / "recipes"
    images_dir = tmp_path / "images"
    site_dir = tmp_path / "site"
    recipes_dir.mkdir()
    images_dir.mkdir()
    site_dir.mkdir()
    (site_dir / "recetas.json").write_text('{"previo": true}', encoding="utf-8")
    shutil.copy(FIXTURES / "broken_sin_titulo.md", recipes_dir / "broken.md")

    exit_code = run_export(recipes_dir, images_dir, site_dir)

    assert exit_code != 0
    assert (site_dir / "recetas.json").read_text(encoding="utf-8") == '{"previo": true}'
    assert not (site_dir / "data.js").exists()


def test_rebuild_deterministico(tmp_path):
    recipes_dir = tmp_path / "recipes"
    images_dir = tmp_path / "images"
    site_dir = tmp_path / "site"
    recipes_dir.mkdir()
    images_dir.mkdir()
    shutil.copy(FIXTURES / "ok_minimal.md", recipes_dir / "ok_minimal.md")
    (images_dir / "cover.jpg").write_text("x", encoding="utf-8")

    run_export(recipes_dir, images_dir, site_dir)
    first = json.loads((site_dir / "recetas.json").read_text(encoding="utf-8"))
    run_export(recipes_dir, images_dir, site_dir)
    second = json.loads((site_dir / "recetas.json").read_text(encoding="utf-8"))

    del first["meta"]["generated_at"]
    del second["meta"]["generated_at"]
    assert first == second
