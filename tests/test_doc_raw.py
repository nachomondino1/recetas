"""Capa cruda: Doc -> raw/recetas.jsonl -> mismo resultado que leer el Doc directo."""

from src import doc_raw, doc_sync


def _p(texto, style="NORMAL_TEXT", bold=False, link=None, bullet=None):
    estilo = {"bold": True} if bold else {}
    if link:
        estilo["link"] = {"url": link}
    p = {
        "paragraph": {
            "paragraphStyle": {"namedStyleType": style},
            "elements": [{"textRun": {"content": texto + "\n", "textStyle": estilo}}],
        }
    }
    if bullet:
        p["paragraph"]["bullet"] = bullet
    return p


def _doc():
    body = [
        _p("Principales", "HEADING_1"),
        _p("Tarta", "HEADING_3"),
        _p("Ingredientes:"),
        _p("200 g harina", bold=True, bullet={"listId": "L1", "nestingLevel": 1}),
        _p("Paso a paso"),
        _p("Mezclar", bullet={"listId": "L2"}),
        _p("ver video", link="https://youtu.be/x"),
    ]
    listas = {
        "L1": {"listProperties": {"nestingLevels": [{"glyphType": "GLYPH_TYPE_UNSPECIFIED"}]}},
        "L2": {"listProperties": {"nestingLevels": [{"glyphType": "DECIMAL"}]}},
    }
    return {"content": {"tabs": [{
        "tabProperties": {"title": "Recetas"},
        "documentTab": {"body": {"content": body}, "lists": listas},
    }]}}


def test_raw_conserva_estructura_que_el_parser_pierde():
    raw = doc_raw.extraer_raw(_doc())
    assert raw[3] == {"style": "NORMAL_TEXT", "runs": [["200 g harina", True, None]],
                      "lista": "viñeta", "nivel": 1}
    assert raw[5]["lista"] == "ordenada"
    assert raw[6]["runs"] == [["ver video", False, "https://youtu.be/x"]]


def test_parsear_desde_raw_equivale_a_parsear_el_doc(tmp_path):
    doc = _doc()
    destino = tmp_path / "recetas.jsonl"
    doc_raw.escribir_raw(doc_raw.extraer_raw(doc), destino)
    desde_raw = doc_sync.parse_parrafos(doc_raw.parrafos_desde_raw(doc_raw.leer_raw(destino)))
    assert desde_raw == doc_sync.parse_doc(doc)


def test_raw_es_deterministico(tmp_path):
    a, b = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    doc_raw.escribir_raw(doc_raw.extraer_raw(_doc()), a)
    doc_raw.escribir_raw(doc_raw.extraer_raw(_doc()), b)
    assert a.read_bytes() == b.read_bytes()
