from src.doc_sync import contenido_hash, detectar_cambios, fecha_a_iso, normalizar_encabezado, parse_doc, render_markdown, slugify


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


def test_normalizar_encabezado_colapsa_espacios_y_minuscula_sin_tocar_acentos_ni_emoji():
    assert normalizar_encabezado("Acompañantes") == "acompañantes"
    assert normalizar_encabezado("🥚 Huevo") == "🥚 huevo"
    assert normalizar_encabezado("  Jugos   naturales  ") == "jugos naturales"


def test_receta_completa_se_extrae():
    listas = {
        "L1": {"listProperties": {"nestingLevels": [{"glyphType": None}]}},
        "L2": {"listProperties": {"nestingLevels": [{"glyphType": "DECIMAL"}]}},
    }
    parrafos = [
        _parrafo("Postres\n", style="HEADING_1"),
        _parrafo("Huevo\n", style="HEADING_2"),
        _parrafo("Flan\n", style="HEADING_3"),
        _parrafo("Fuente: https://ejemplo.com\n"),
        _parrafo("Última actualización: 5 jul 2026\n"),
        _parrafo("Ingredientes:\n"),
        _parrafo("Huevos — 10\n", list_id="L1"),
        _parrafo("Paso a paso\n"),
        _parrafo("Batir los huevos\n", list_id="L2"),
    ]
    completas, incompletas = parse_doc(_doc([_tab("Recetas", parrafos, listas)]))

    assert incompletas == []
    assert len(completas) == 1
    receta = completas[0]
    assert receta["titulo"] == "Flan"
    assert receta["categorias"] == ["postres"]
    assert receta["tipo_postre"] == "huevo"
    assert receta["fuente"] == "https://ejemplo.com"
    assert receta["fecha_actualizacion"] == "2026-07-05"
    assert receta["ingredientes"] == ["- Huevos — 10"]
    assert receta["paso_a_paso"] == ["1. Batir los huevos"]

    md = render_markdown(receta)
    assert 'titulo: "Flan"' in md
    assert 'categorias: ["postres"]' in md
    assert 'tipo_postre: "huevo"' in md
    assert "## Ingredientes" in md
    assert "## Paso a paso" in md


def test_receta_sin_paso_a_paso_se_reporta_incompleta():
    parrafos = [
        _parrafo("Meriendas\n", style="HEADING_1"),
        _parrafo("Mermelada\n", style="HEADING_3"),
        _parrafo("Agregar receta.\n"),
    ]
    completas, incompletas = parse_doc(_doc([_tab("Recetas", parrafos)]))

    assert completas == []
    assert len(incompletas) == 1
    assert incompletas[0]["titulo"] == "Mermelada"
    assert incompletas[0]["tab"] == "Recetas"


def test_pestana_recetas_ausente_no_corta_el_resto():
    completas, incompletas = parse_doc(_doc([_tab("Otra pestaña", [])]))
    assert completas == []
    assert any("no se encontró" in i["motivo"] for i in incompletas)


def test_otras_pestanas_se_ignoran_en_silencio():
    parrafos_template = [_parrafo("Lo que sea\n", style="HEADING_1")]
    parrafos_recetas = [
        _parrafo("Bebidas\n", style="HEADING_1"),
        _parrafo("Tragos\n", style="HEADING_2"),
        _parrafo("Daiquiri\n", style="HEADING_3"),
        _parrafo("Ingredientes:\n"),
        _parrafo("Ron — 50ml\n", list_id="L1"),
        _parrafo("Paso a paso\n"),
        _parrafo("Licuar\n", list_id="L1"),
    ]
    listas = {"L1": {"listProperties": {"nestingLevels": [{"glyphType": None}]}}}
    completas, incompletas = parse_doc(_doc([
        _tab("Template receta", parrafos_template),
        _tab("Recetas", parrafos_recetas, listas),
    ]))

    assert incompletas == []
    assert [r["titulo"] for r in completas] == ["Daiquiri"]


def test_categoria_sin_subcategoria_no_setea_campo():
    # "Acompañantes" no tiene H2 en el Doc: las recetas van directo bajo
    # el H1, sin subcategoría (no es un dato faltante, es la estructura real).
    parrafos = [
        _parrafo("Acompañantes\n", style="HEADING_1"),
        _parrafo("Papas al horno\n", style="HEADING_3"),
        _parrafo("Ingredientes:\n"),
        _parrafo("Papas — 4\n", list_id="L1"),
        _parrafo("Paso a paso\n"),
        _parrafo("Hornear\n", list_id="L1"),
    ]
    listas = {"L1": {"listProperties": {"nestingLevels": [{"glyphType": None}]}}}
    completas, incompletas = parse_doc(_doc([_tab("Recetas", parrafos, listas)]))

    assert incompletas == []
    receta = completas[0]
    assert receta["categorias"] == ["acompañantes"]
    assert receta["subcategoria"] is None

    md = render_markdown(receta)
    assert 'categorias: ["acompañantes"]' in md
    assert "subcategoria" not in md


def test_categoria_nueva_sin_campo_dedicado_usa_subcategoria_generica():
    parrafos = [
        _parrafo("Salsas\n", style="HEADING_1"),
        _parrafo("Picantes\n", style="HEADING_2"),
        _parrafo("Chimichurri\n", style="HEADING_3"),
        _parrafo("Ingredientes:\n"),
        _parrafo("Perejil — 1 atado\n", list_id="L1"),
        _parrafo("Paso a paso\n"),
        _parrafo("Picar todo\n", list_id="L1"),
    ]
    listas = {"L1": {"listProperties": {"nestingLevels": [{"glyphType": None}]}}}
    completas, _ = parse_doc(_doc([_tab("Recetas", parrafos, listas)]))

    receta = completas[0]
    assert receta["categorias"] == ["salsas"]
    assert receta["subcategoria"] == "picantes"


def test_doc_hash_estable_y_sensible_al_contenido():
    base = {
        "titulo": "Flan", "categorias": ["postres"], "tipo_postre": "huevo",
        "momento": None, "tipo_merienda": None, "tipo_bebida": None, "subcategoria": None,
        "fuente": None, "fecha_actualizacion": None,
        "materiales": [], "ingredientes": ["- Huevos — 10"], "paso_a_paso": ["1. Batir"],
        "cuerpo_libre": [],
    }
    igual = dict(base)
    distinto = dict(base, ingredientes=["- Huevos — 12"])

    assert contenido_hash(base) == contenido_hash(igual)
    assert contenido_hash(base) != contenido_hash(distinto)


def test_detectar_cambios_nueva_cambiada_y_sin_cambios(tmp_path):
    receta_sin_cambios = {
        "slug": "flan", "titulo": "Flan", "categorias": ["postres"],
        "tipo_postre": "huevo", "momento": None, "tipo_merienda": None,
        "tipo_bebida": None, "subcategoria": None,
        "fuente": None, "fecha_actualizacion": None,
        "materiales": [], "ingredientes": ["- a"], "paso_a_paso": ["1. b"],
        "cuerpo_libre": [],
    }
    receta_sin_cambios["doc_hash"] = contenido_hash(receta_sin_cambios)

    receta_cambiada = dict(receta_sin_cambios, slug="budin", ingredientes=["- a", "- b"])
    receta_cambiada["doc_hash"] = contenido_hash(receta_cambiada)

    receta_nueva = dict(receta_sin_cambios, slug="torta")
    receta_nueva["doc_hash"] = contenido_hash(receta_nueva)

    (tmp_path / "flan.md").write_text(
        f'---\ntitulo: "Flan"\ncategorias: ["postres"]\ndoc_hash: "{receta_sin_cambios["doc_hash"]}"\n---\ncuerpo\n',
        encoding="utf-8",
    )
    (tmp_path / "budin.md").write_text(
        '---\ntitulo: "Budín"\ncategorias: ["postres"]\ndoc_hash: "otrohash"\n---\ncuerpo\n',
        encoding="utf-8",
    )
    # "torta" no tiene archivo en recipes/: es nueva.

    cambios = detectar_cambios([receta_sin_cambios, receta_cambiada, receta_nueva], tmp_path)

    assert [r["slug"] for r in cambios["sin_cambios"]] == ["flan"]
    assert [r["slug"] for r in cambios["cambiadas"]] == ["budin"]
    assert [r["slug"] for r in cambios["nuevas"]] == ["torta"]


def test_receta_con_sub_partes_acumula_ingredientes_y_pasos_de_todas():
    # Un H4/H5+ que no matchea Ingredientes/Materiales/Paso a paso (ej. el
    # nombre de una sub-parte como "Masa sablée") no abre receta nueva ni
    # corta nada — sigue perteneciendo a la receta hasta el próximo H1/H2/H3,
    # y sus propias secciones (típicamente un nivel más de heading) se
    # detectan igual, por texto.
    parrafos = [
        _parrafo("Postres\n", style="HEADING_1"),
        _parrafo("Frutal\n", style="HEADING_2"),
        _parrafo("Lemon pie\n", style="HEADING_3"),
        _parrafo("Masa sablée\n", style="HEADING_5"),
        _parrafo("Ingredientes\n", style="HEADING_6"),
        _parrafo("Harina — 200g\n", list_id="L1"),
        _parrafo("Paso a paso\n", style="HEADING_6"),
        _parrafo("Amasar\n", list_id="L1"),
        _parrafo("Curd de limón\n", style="HEADING_5"),
        _parrafo("Ingredientes\n", style="HEADING_6"),
        _parrafo("Limón — 3\n", list_id="L1"),
        _parrafo("Paso a paso\n", style="HEADING_6"),
        _parrafo("Cocinar\n", list_id="L1"),
    ]
    listas = {"L1": {"listProperties": {"nestingLevels": [{"glyphType": None}]}}}
    completas, incompletas = parse_doc(_doc([_tab("Recetas", parrafos, listas)]))

    assert incompletas == []
    receta = completas[0]
    assert receta["ingredientes"] == ["- Harina — 200g", "- Limón — 3"]
    assert receta["paso_a_paso"] == ["- Amasar", "- Cocinar"]


def test_receta_variante_por_referencia_a_otra_se_extrae_con_la_frase_literal():
    # Patrón "Cookies": una receta variante remite a otra por nombre en vez
    # de repetir ingredientes/pasos ("Mismos ingredientes que X, con estos
    # cambios:" / "Igual que X[...]"). El parser no resuelve la referencia
    # (no fusiona los ingredientes de la base) — solo evita descartar la
    # frase literal, para no reportar la receta como incompleta.
    listas = {"L1": {"listProperties": {"nestingLevels": [{"glyphType": None}]}}}
    parrafos = [
        _parrafo("Meriendas\n", style="HEADING_1"),
        _parrafo("Cookies\n", style="HEADING_2"),
        _parrafo("Vainilla\n", style="HEADING_3"),
        _parrafo("Ingredientes:\n"),
        _parrafo("Avena — 2 tazas\n", list_id="L1"),
        _parrafo("Paso a paso\n"),
        _parrafo("Mezclar y hornear\n", list_id="L1"),
        _parrafo("Limón\n", style="HEADING_3"),
        _parrafo("Ingredientes:\n"),
        _parrafo("Mismos ingredientes que Vainilla, con estos cambios:\n"),
        _parrafo("Jugo de limón en lugar del agua\n", list_id="L1"),
        _parrafo("Paso a paso\n"),
        _parrafo("Igual que Vainilla.\n"),
    ]
    completas, incompletas = parse_doc(_doc([_tab("Recetas", parrafos, listas)]))

    assert incompletas == []
    assert [r["titulo"] for r in completas] == ["Vainilla", "Limón"]
    limon = completas[1]
    assert limon["ingredientes"] == [
        "Mismos ingredientes que Vainilla, con estos cambios:",
        "",
        "- Jugo de limón en lugar del agua",
    ]
    assert limon["paso_a_paso"] == ["Igual que Vainilla."]


def test_parrafo_suelto_dentro_de_una_seccion_se_descarta_salvo_referencia():
    # Notas sueltas tipo bitácora ("Duda: ...", "Nota: ...") mezcladas con
    # bullets dentro de una sección activa se siguen descartando a propósito
    # (ver DECISIONS.md) — solo la frase de referencia a otra receta se
    # conserva. Si esto no se cumple, un sync vuelca prosa informal cruda en
    # recetas que ya tienen una versión curada a mano (regresión real vista
    # con `guiso-con-lentejas` al desarrollar este fix).
    listas = {"L1": {"listProperties": {"nestingLevels": [{"glyphType": None}]}}}
    parrafos = [
        _parrafo("Principales\n", style="HEADING_1"),
        _parrafo("Guiso\n", style="HEADING_3"),
        _parrafo("Ingredientes:\n"),
        _parrafo("Lentejas — 1 kg\n", list_id="L1"),
        _parrafo("Paso a paso\n"),
        _parrafo("Cocinar la lenteja\n", list_id="L1"),
        _parrafo("Duda: ¿se puede cortar la verdura antes? Sí, pero no es tan necesario.\n"),
        _parrafo("Servir\n", list_id="L1"),
    ]
    completas, _ = parse_doc(_doc([_tab("Recetas", parrafos, listas)]))

    receta = completas[0]
    assert receta["paso_a_paso"] == ["- Cocinar la lenteja", "- Servir"]
