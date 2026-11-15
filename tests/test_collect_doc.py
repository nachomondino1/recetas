"""Capa cruda: Doc -> recetas.jsonl -> mismo resultado que leer el Doc directo."""

import collect_doc
import format_data


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
    raw = collect_doc.extraer_raw(_doc())
    assert raw[3] == {"style": "NORMAL_TEXT", "runs": [["200 g harina", True, None]],
                      "lista": "viñeta", "nivel": 1}
    assert raw[5]["lista"] == "ordenada"
    assert raw[6]["runs"] == [["ver video", False, "https://youtu.be/x"]]


def test_parsear_desde_raw_equivale_a_parsear_el_doc(tmp_path):
    doc = _doc()
    destino = tmp_path / "recetas.jsonl"
    collect_doc.escribir_raw(collect_doc.extraer_raw(doc), destino)
    desde_raw = format_data.parse_parrafos(format_data.parrafos_desde_raw(format_data.leer_raw(destino)))
    assert desde_raw == format_data.parse_doc(doc)


def test_raw_es_deterministico(tmp_path):
    a, b = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    collect_doc.escribir_raw(collect_doc.extraer_raw(_doc()), a)
    collect_doc.escribir_raw(collect_doc.extraer_raw(_doc()), b)
    assert a.read_bytes() == b.read_bytes()


def test_titulos_de_receta_detecta_las_nuevas_y_las_quitadas():
    import json

    def raw(titulos):
        return [json.dumps({"style": "HEADING_3", "runs": [[t, False, None]]}) for t in titulos] + \
               [json.dumps({"style": "NORMAL_TEXT", "runs": [["texto", False, None]]})]

    antes, ahora = collect_doc.titulos_de_receta(raw(["Flan", "Tacos"])), collect_doc.titulos_de_receta(raw(["Flan", "Pan"]))
    assert [t for t in ahora if t not in antes] == ["Pan"]
    assert [t for t in antes if t not in ahora] == ["Tacos"]
