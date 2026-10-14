import json
import shutil
from pathlib import Path

from src import schema
from src.export_data import (
    cargar_utils,
    construir_json,
    load_recipes,
    normalizar,
    resolver_includes,
    run_export,
    validar,
)

FIXTURES = Path(__file__).parent / "fixtures"
UTILS_FIXTURES = FIXTURES / "utils"


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


def test_dificultad_invalida_es_error(tmp_path):
    _, errors, _ = _load_one(tmp_path, "broken_dificultad_invalida.md")
    assert any("dificultad desconocida" in e for e in errors)


def test_categoria_y_subcategoria_son_libres_no_hay_enum_que_validar(tmp_path):
    # Categoría/subcategoría son dinámicas (vienen del H1/H2 del Doc, ver
    # doc_sync.normalizar_encabezado): cualquier valor no vacío es válido,
    # no hay lista cerrada que mantener acá.
    _, errors, _ = _load_one(tmp_path, "warnings_bebida_sin_tipo.md")
    assert errors == []


def test_bebida_sin_tipo_bebida_es_warning(tmp_path):
    _, errors, warnings = _load_one(tmp_path, "warnings_bebida_sin_tipo.md")
    assert errors == []
    assert any(w["field"] == "tipo_bebida" for w in warnings)


def test_acompanante_sin_tipo_bebida_no_es_warning(tmp_path):
    # "acompañantes" no tiene subcategoría en el Doc (no hay H2 ahí) — no es
    # un campo que deba avisar si falta.
    _, errors, warnings = _load_one(tmp_path, "ok_minimal.md")
    assert errors == []
    assert not any(w["field"] == "tipo_bebida" for w in warnings)


def test_merienda_sin_tipo_merienda_es_warning(tmp_path):
    _, errors, warnings = _load_one(tmp_path, "warnings_merienda_sin_tipo.md")
    assert errors == []
    assert any(w["field"] == "tipo_merienda" for w in warnings)


def test_principal_sin_momento_es_warning(tmp_path):
    # A diferencia del esquema viejo (momento era una excepción puntual),
    # el Doc unificado ahora pone SIEMPRE las recetas de "Principales" bajo
    # un H2 "Almuerzo"/"Cena" — el sync mecánico siempre completa `momento`,
    # así que su ausencia señala una receta agregada a mano sin clasificar.
    _, errors, warnings = _load_one(tmp_path, "warnings_principal_sin_momento.md")
    assert errors == []
    assert any(w["field"] == "momento" for w in warnings)


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
        "fuente", "tipo_bebida", "tipo_merienda", "momento", "tipo_postre",
        "subcategoria", "body_html",
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


def test_run_export_copia_toda_la_carpeta_de_imagenes_no_solo_foto(tmp_path):
    recipes_dir = tmp_path / "recipes"
    images_dir = tmp_path / "images"
    site_dir = tmp_path / "site"
    recipes_dir.mkdir()
    site_dir.mkdir()
    (recipes_dir / "con-fotos.md").write_text(
        '---\ntitulo: "Con fotos"\ncategorias: ["principal"]\n'
        'foto: "con-fotos/cover.jpg"\n---\n## Paso a paso\n1. Un paso.\n',
        encoding="utf-8",
    )
    (images_dir / "con-fotos").mkdir(parents=True)
    (images_dir / "con-fotos" / "cover.jpg").write_text("portada", encoding="utf-8")
    (images_dir / "con-fotos" / "doc-01.jpg").write_text("paso 1", encoding="utf-8")

    exit_code = run_export(recipes_dir, images_dir, site_dir)

    assert exit_code == 0
    assert (site_dir / "images" / "con-fotos" / "cover.jpg").read_text(encoding="utf-8") == "portada"
    assert (site_dir / "images" / "con-fotos" / "doc-01.jpg").read_text(encoding="utf-8") == "paso 1"


def test_cargar_utils_parsea_secciones():
    utils = cargar_utils(UTILS_FIXTURES)
    assert set(utils.keys()) == {"fragmento-prueba"}
    assert "Item de prueba" in utils["fragmento-prueba"]["ingredientes"]
    assert "Paso de prueba" in utils["fragmento-prueba"]["paso-a-paso"]


def test_cargar_utils_ignora_readme():
    utils = cargar_utils(Path(__file__).parent.parent / "recipes" / "utils")
    assert "README" not in utils


def test_resolver_includes_reemplaza_contenido():
    utils = cargar_utils(UTILS_FIXTURES)
    body, errores = resolver_includes(
        "### Parte\n<!-- incluir: fragmento-prueba#ingredientes -->", utils
    )
    assert errores == []
    assert "Item de prueba" in body
    assert "incluir:" not in body


def test_resolver_includes_fragmento_inexistente_es_error():
    body, errores = resolver_includes("<!-- incluir: no-existe#ingredientes -->", {})
    assert len(errores) == 1
    assert "no-existe" in errores[0]
    assert "incluir:" in body  # no se resuelve en silencio, queda visible


def test_resolver_includes_seccion_inexistente_es_error():
    utils = cargar_utils(UTILS_FIXTURES)
    body, errores = resolver_includes("<!-- incluir: fragmento-prueba#no-existe -->", utils)
    assert len(errores) == 1
    assert "no-existe" in errores[0]


def test_normalizar_resuelve_includes_antes_de_validar(tmp_path):
    shutil.copy(FIXTURES / "ok_con_include.md", tmp_path / "ok_con_include.md")
    utils = cargar_utils(UTILS_FIXTURES)
    raws = load_recipes(tmp_path)
    records = normalizar(raws, utils)
    errors, _ = validar(records, tmp_path)
    assert errors == []
    assert "Item de prueba" in records[0]["body"]


def test_include_inexistente_es_error(tmp_path):
    shutil.copy(FIXTURES / "broken_include_inexistente.md", tmp_path / "broken_include_inexistente.md")
    raws = load_recipes(tmp_path)
    records = normalizar(raws, {})
    errors, _ = validar(records, tmp_path)
    assert any("no-existe" in e for e in errors)


def test_run_export_con_utils_dir(tmp_path):
    recipes_dir = tmp_path / "recipes"
    images_dir = tmp_path / "images"
    site_dir = tmp_path / "site"
    recipes_dir.mkdir()
    images_dir.mkdir()
    shutil.copy(FIXTURES / "ok_con_include.md", recipes_dir / "ok_con_include.md")

    exit_code = run_export(recipes_dir, images_dir, site_dir, UTILS_FIXTURES)

    assert exit_code == 0
    data = json.loads((site_dir / "recetas.json").read_text(encoding="utf-8"))
    assert "Item de prueba" in data["recetas"][0]["body_html"]


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
