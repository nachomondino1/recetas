"""Integración Doc (A) + curado (B): una receta nueva entra sola, lo curado nunca se pisa."""

import integrate_data


def _receta(slug, hash_="h1", titulo=None):
    return {
        "slug": slug, "titulo": titulo or slug.title(), "categorias": ["🍨 postres"],
        "fuente": None, "fecha_actualizacion": None, "materiales": [],
        "ingredientes": ["- harina"], "paso_a_paso": ["1. mezclar"], "cuerpo_libre": [],
        "doc_hash": hash_, "completa": True,
    }


def _curada(dir_, slug, hash_="h1", extra=""):
    (dir_ / f"{slug}.md").write_text(
        f'---\ntitulo: "{slug}"\ncategorias: ["x"]\nfoto: "{slug}/cover.jpg"\ndoc_hash: "{hash_}"\n{extra}---\ncuerpo curado\n',
        encoding="utf-8",
    )


def test_receta_nueva_del_doc_entra_sola(tmp_path):
    cur, out = tmp_path / "cur", tmp_path / "out"
    cur.mkdir()
    rep = integrate_data.integrar([_receta("flan-nuevo")], [], cur, out, {})
    assert rep["nuevas"] == ["flan-nuevo"]
    assert "harina" in (out / "flan-nuevo.md").read_text(encoding="utf-8")


def test_curada_gana_y_conserva_foto(tmp_path):
    cur, out = tmp_path / "cur", tmp_path / "out"
    cur.mkdir()
    _curada(cur, "flan")
    rep = integrate_data.integrar([_receta("flan")], [], cur, out, {})
    assert rep["curadas_iguales"] == ["flan"] and not rep["nuevas"]
    texto = (out / "flan.md").read_text(encoding="utf-8")
    assert "cuerpo curado" in texto and "flan/cover.jpg" in texto


def test_si_el_doc_cambio_se_avisa_pero_no_se_pisa(tmp_path):
    cur, out = tmp_path / "cur", tmp_path / "out"
    cur.mkdir()
    _curada(cur, "flan", hash_="viejo")
    rep = integrate_data.integrar([_receta("flan", hash_="nuevo")], [], cur, out, {})
    assert [r["receta"] for r in rep["revisar"]] == ["flan"]
    assert "cuerpo curado" in (out / "flan.md").read_text(encoding="utf-8")


def test_alias_une_titulo_corto_del_doc_con_receta_curada(tmp_path):
    cur, out = tmp_path / "cur", tmp_path / "out"
    cur.mkdir()
    _curada(cur, "budin-de-banana")
    rep = integrate_data.integrar([_receta("banana")], [], cur, out, {"banana": "budin-de-banana"})
    assert not rep["nuevas"] and rep["curadas_iguales"] == ["budin-de-banana"]
    assert not (out / "banana.md").exists()


def test_alias_utils_no_publica_receta(tmp_path):
    cur, out = tmp_path / "cur", tmp_path / "out"
    cur.mkdir()
    rep = integrate_data.integrar([_receta("sable")], [], cur, out, {"sable": "utils:masa-sablee"})
    assert rep["fragmentos"] == ["sable"] and not list(out.glob("*.md"))


def test_solo_curada_se_conserva(tmp_path):
    cur, out = tmp_path / "cur", tmp_path / "out"
    cur.mkdir()
    _curada(cur, "tacos")
    rep = integrate_data.integrar([], [], cur, out, {})
    assert rep["solo_curadas"] == ["tacos"] and (out / "tacos.md").exists()
