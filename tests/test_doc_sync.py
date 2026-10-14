from src.doc_sync import contenido_hash, detectar_cambios, fecha_a_iso, parse_doc, render_markdown, slugify


def _parrafo(texto, style="NORMAL_TEXT", list_id=None, ordenada=False):
    elementos = [{"textRun": {"content": texto}}]
    bullet = {"listId": list_id} if list_id else None
    return {"paragraph": {
        "paragraphStyle": {"namedStyleType": style},
        "elements": elementos,
        "bullet": bullet,
    }}


def _doc(tabs):
    return {"content": {"tabs": tabs}}


def _tab(titulo, parrafos, listas=None):
    return {
        "tabProperties": {"title": titulo},
        "documentTab": {
            "body": {"content": parrafos},
            "lists": listas or {},
        },
    }


def test_fecha_a_iso():
    assert fecha_a_iso("20 abr 2026") == "2026-04-20"
    assert fecha_a_iso("2 may 2026") == "2026-05-02"
    assert fecha_a_iso("") is None


def test_slugify_saca_emoji_y_acentos():
    assert slugify("🍫 Chocolinas") == "chocolinas"
    assert slugify("Mousse de limón") == "mousse-de-limon"


def test_receta_completa_se_extrae():
    listas = {
        "L1": {"listProperties": {"nestingLevels": [{"glyphType": None}]}},
        "L2": {"listProperties": {"nestingLevels": [{"glyphType": "DECIMAL"}]}},
    }
    parrafos = [
        _parrafo("Flan\n", style="HEADING_2"),
        _parrafo("Fuente: https://ejemplo.com\n"),
        _parrafo("Última actualización: 5 jul 2026\n"),
        _parrafo("Ingredientes:\n"),
        _parrafo("Huevos — 10\n", list_id="L1"),
        _parrafo("Paso a paso\n"),
        _parrafo("Batir los huevos\n", list_id="L2"),
    ]
    completas, incompletas = parse_doc(_doc([_tab("Postres y Tartas", parrafos, listas)]))

    assert incompletas == []
    assert len(completas) == 1
    receta = completas[0]
    assert receta["titulo"] == "Flan"
    assert receta["categorias"] == ["postre"]
    assert receta["fuente"] == "https://ejemplo.com"
    assert receta["fecha_actualizacion"] == "2026-07-05"
    assert receta["ingredientes"] == ["- Huevos — 10"]
    assert receta["paso_a_paso"] == ["1. Batir los huevos"]

    md = render_markdown(receta)
    assert 'titulo: "Flan"' in md
    assert "## Ingredientes" in md
    assert "## Paso a paso" in md


def test_receta_sin_paso_a_paso_se_reporta_incompleta():
    parrafos = [
        _parrafo("Mermelada\n", style="HEADING_2"),
        _parrafo("Agregar receta.\n"),
    ]
    completas, incompletas = parse_doc(_doc([_tab("Meriendas", parrafos)]))

    assert completas == []
    assert len(incompletas) == 1
    assert incompletas[0]["titulo"] == "Mermelada"
    assert incompletas[0]["tab"] == "Meriendas"


def test_pestana_desconocida_no_corta_el_resto():
    completas, incompletas = parse_doc(_doc([_tab("Otra pestaña nueva", [])]))
    assert completas == []
    assert any("no mapeada" in i["motivo"] for i in incompletas)


def test_bebidas_mapea_a_bebidas_sin_tipo_default():
    # "Bebidas" (antes "Jugos naturales") ya no es 100% jugos — ahora mezcla
    # jugos con tragos (ej. Daiquiri) — así que no hay default de tipo_bebida
    # por pestaña: se decide a mano por receta al mergear.
    parrafos = [
        _parrafo("Jugo verde\n", style="HEADING_2"),
        _parrafo("Ingredientes:\n"),
        _parrafo("Pepino — 1\n", list_id="L1"),
        _parrafo("Paso a paso\n"),
        _parrafo("Licuar\n", list_id="L1"),
    ]
    listas = {"L1": {"listProperties": {"nestingLevels": [{"glyphType": None}]}}}
    completas, incompletas = parse_doc(_doc([_tab("Bebidas", parrafos, listas)]))

    assert incompletas == []
    receta = completas[0]
    assert receta["categorias"] == ["bebidas"]
    assert receta["tipo_bebida"] is None

    md = render_markdown(receta)
    assert 'categorias: ["bebidas"]' in md
    assert "tipo_bebida" not in md


def test_doc_hash_estable_y_sensible_al_contenido():
    base = {
        "titulo": "Flan", "categorias": ["postre"], "tipo_bebida": None,
        "fuente": None, "fecha_actualizacion": None,
        "materiales": [], "ingredientes": ["- Huevos — 10"], "paso_a_paso": ["1. Batir"],
        "cuerpo_libre": [],
    }
    igual = dict(base)
    distinto = dict(base, ingredientes=["- Huevos — 12"])

    assert contenido_hash(base) == contenido_hash(igual)
    assert contenido_hash(base) != contenido_hash(distinto)


def test_detectar_cambios_nueva_cambiada_y_sin_cambios(tmp_path):
    receta_sin_cambios = {"slug": "flan", "titulo": "Flan", "categorias": ["postre"],
                           "tipo_bebida": None, "fuente": None, "fecha_actualizacion": None,
                           "materiales": [], "ingredientes": ["- a"], "paso_a_paso": ["1. b"],
                           "cuerpo_libre": []}
    receta_sin_cambios["doc_hash"] = contenido_hash(receta_sin_cambios)

    receta_cambiada = dict(receta_sin_cambios, slug="budin", ingredientes=["- a", "- b"])
    receta_cambiada["doc_hash"] = contenido_hash(receta_cambiada)

    receta_nueva = dict(receta_sin_cambios, slug="torta")
    receta_nueva["doc_hash"] = contenido_hash(receta_nueva)

    (tmp_path / "flan.md").write_text(
        f'---\ntitulo: "Flan"\ncategorias: ["postre"]\ndoc_hash: "{receta_sin_cambios["doc_hash"]}"\n---\ncuerpo\n',
        encoding="utf-8",
    )
    (tmp_path / "budin.md").write_text(
        '---\ntitulo: "Budín"\ncategorias: ["postre"]\ndoc_hash: "otrohash"\n---\ncuerpo\n',
        encoding="utf-8",
    )
    # "torta" no tiene archivo en recipes/: es nueva.

    cambios = detectar_cambios([receta_sin_cambios, receta_cambiada, receta_nueva], tmp_path)

    assert [r["slug"] for r in cambios["sin_cambios"]] == ["flan"]
    assert [r["slug"] for r in cambios["cambiadas"]] == ["budin"]
    assert [r["slug"] for r in cambios["nuevas"]] == ["torta"]


def test_heading_1_no_abre_receta_propia():
    parrafos = [
        _parrafo("Budines\n", style="HEADING_1"),
        _parrafo("Naranja\n", style="HEADING_2"),
        _parrafo("Ingredientes:\n"),
        _parrafo("Naranjas — 2\n", list_id="L1"),
        _parrafo("Paso a paso\n"),
        _parrafo("Exprimir\n", list_id="L1"),
    ]
    listas = {"L1": {"listProperties": {"nestingLevels": [{"glyphType": None}]}}}
    completas, incompletas = parse_doc(_doc([_tab("Meriendas", parrafos, listas)]))

    assert incompletas == []
    assert [r["titulo"] for r in completas] == ["Naranja"]
