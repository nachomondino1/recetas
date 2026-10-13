from src.doc_sync import fecha_a_iso, parse_doc, render_markdown, slugify


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
