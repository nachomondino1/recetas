"""Convierte el JSON crudo de la Google Docs API (una sola pestaña "Recetas"
con jerarquía de headers H1-H5) en borradores de receta (.md con
frontmatter), para no tener que transcribir el Google Doc a mano cada vez
que cambia.

Jerarquía de headers en el Doc (ver DECISIONS.md):
  H1 = categoría (ej. "Principales")
  H2 = subcategoría, opcional — algunas categorías no la tienen y sus
       recetas van directo bajo el H1 (ej. "Acompañantes")
  H3 = receta
  H4 = sección dentro de la receta (Materiales/Ingredientes/Paso a paso)
  H5 = sub-parte cuando una receta tiene partes (ej. Lemon pie: masa sablée,
       curd de limón...), con sus propias secciones (típicamente H6)

Categoría y subcategoría son dinámicas: el valor es el texto del heading tal
cual lo escribe el usuario (ver `normalizar_encabezado`), nunca un enum
cerrado en código — agregar o renombrar un H1/H2 en el Doc no requiere tocar
este módulo. El nombre del CAMPO de subcategoría por categoría sí es fijo
(`schema.CAMPO_SUBCATEGORIA`), porque es una decisión de código estable.

No hay credenciales propias para leer el Doc en este script: Claude lo lee
con el conector de Google Docs (`read_doc`) y guarda ese JSON en un archivo;
este módulo solo lo parsea. Ver DECISIONS.md.

Principio del playbook de datos: no inventar contenido ambiguo. Una receta
sin Ingredientes ni Paso a paso se reporta como incompleta y no se escribe.

Escribe a un directorio de BORRADORES (`data/02_data_preparation/drafts/` por default), nunca
pisa `recipes/` directamente: varias recetas tienen campos curados a mano
(`foto`, `porciones`, fusiones de contenido duplicado) que este parser
mecánico no puede reconstruir, y pisarlas en silencio sería peor que no
sincronizar.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path

import yaml


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
import config  # noqa: E402
import schema  # noqa: E402
from gdoc import ORDERED_GLYPHS, TAB_RECETAS, es_ordenada as _es_ordenada, slugify, texto_parrafo as _texto_parrafo  # noqa: E402,F401

FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n?", re.DOTALL)


MESES = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dic": 12,
}

FUENTE_RE = re.compile(r"^\s*fuentes?\s*:\s*(.*)$", re.IGNORECASE)
FECHA_RE = re.compile(r"^\s*(?:última|ultima)\s+actualizaci[oó]n\s*:\s*(.*)$", re.IGNORECASE)
FECHA_VALOR_RE = re.compile(r"(\d{1,2})\s+([a-zA-Zñ]+)\.?\s+(\d{4})")
SECCION_RE = re.compile(r"^(ingredientes|materiales|paso a paso)\b", re.IGNORECASE)
# Receta-variante que remite a otra por nombre (ej. "Mismos ingredientes que
# Dulces: Vainilla con membrillo, con estos cambios:" / "Igual que Dulces:
# Vainilla con membrillo."). Se captura la frase literal, sin resolver la
# referencia ni intentar fusionar los ingredientes/pasos de la base: eso
# requeriría interpretar texto libre ("en lugar de X", "sin Y"), que es
# justamente el tipo de invención que el playbook de datos prohíbe.
REFERENCIA_VARIANTE_RE = re.compile(r"^(mismos ingredientes que|igual que)\b", re.IGNORECASE)
SECCION_MAX_LEN = 60
CAMPO_VACIO_RE = re.compile(r"^\s*(tiempo|dificultad)\s*:\s*$", re.IGNORECASE)


def fecha_a_iso(texto: str) -> str | None:
    m = FECHA_VALOR_RE.search(texto)
    if not m:
        return None
    dia, mes_txt, anio = m.groups()
    mes = MESES.get(mes_txt.lower().rstrip("."))
    if not mes:
        return None
    return f"{anio}-{mes:02d}-{int(dia):02d}"


def contenido_hash(receta: dict) -> str:
    """Hash determinístico del contenido parseado de una receta (no de metadata
    de archivo ni de `completa`/`tab`). Mismo contenido en el Doc -> mismo
    hash; se guarda como `doc_hash` en el frontmatter para poder detectar, en
    la próxima lectura del Doc, qué recetas cambiaron de verdad desde el
    último sync (ver `detectar_cambios`).
    """
    campos = {
        "titulo": receta["titulo"],
        "categorias": receta["categorias"],
        "subfiltro": {c: receta[c] for c in schema.SUBFILTRO_CAMPOS if receta.get(c)},
        "fuente": receta["fuente"],
        "fecha_actualizacion": receta["fecha_actualizacion"],
        "materiales": receta["materiales"],
        "ingredientes": receta["ingredientes"],
        "paso_a_paso": receta["paso_a_paso"],
        "cuerpo_libre": receta["cuerpo_libre"],
    }
    canon = json.dumps(campos, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()[:12]



def normalizar_encabezado(texto: str) -> str:
    """Valor estable para categoria/subcategoria: el texto del heading tal
    cual lo escribió el usuario (emoji incluido), solo colapsando espacios y
    pasando a minúscula. A diferencia de `slugify` (pensado para nombres de
    archivo) nunca se fuerza a ASCII, para no perder tildes/ñ ni los emoji
    que el usuario ya elige a mano por subcategoría (ej. "🍰 Budines").
    """
    return " ".join(texto.split()).lower()



def _texto_parrafo_md(elemento: dict) -> str:
    """Igual que `_texto_parrafo`, pero envuelve en `**negrita**` los tramos
    que el usuario puso en negrita en el Doc (`textRun.textStyle.bold`) — para
    poder identificar de un vistazo qué palabras importan en cada paso. Fusiona
    `textRun`s contiguos del mismo valor de `bold` (la Docs API puede partir
    una misma frase en negrita en varios `textRun`) y recorta los espacios en
    los bordes de cada tramo en negrita hacia afuera de los `**`, porque
    Markdown no reconoce `** texto **` con espacio pegado al marcador.
    """
    parrafo = elemento.get("paragraph")
    if not parrafo:
        return ""
    runs = []
    for e in parrafo.get("elements", []):
        text_run = e.get("textRun", {})
        runs.append((text_run.get("content", ""), bool(text_run.get("textStyle", {}).get("bold"))))
    return md_desde_runs(runs)


def md_desde_runs(runs: list[tuple[str, bool]]) -> str:
    """[(texto, negrita)] -> texto con `**negrita**` (ver `_texto_parrafo_md`)."""
    fusionados: list[tuple[str, bool]] = []
    for contenido, negrita in runs:
        if not contenido:
            continue
        if fusionados and fusionados[-1][1] == negrita:
            fusionados[-1] = (fusionados[-1][0] + contenido, negrita)
        else:
            fusionados.append((contenido, negrita))

    partes = []
    for contenido, negrita in fusionados:
        if not negrita or not contenido.strip():
            partes.append(contenido)
            continue
        inicio = contenido[: len(contenido) - len(contenido.lstrip())]
        fin = contenido[len(contenido.rstrip()):]
        nucleo = contenido.strip()
        partes.append(f"{inicio}**{nucleo}**{fin}")
    return "".join(partes).rstrip("\n")



def _parrafos_de_tab(tab: dict) -> list[dict]:
    """Aplana el body de una pestaña a una lista de {style, texto, lista, ordenada}."""
    doc_tab = tab.get("documentTab", {})
    listas = doc_tab.get("lists", {})
    salida = []
    for elemento in doc_tab.get("body", {}).get("content", []):
        parrafo = elemento.get("paragraph")
        if parrafo is None:
            continue
        texto = _texto_parrafo(elemento).strip()
        salida.append({
            "style": parrafo.get("paragraphStyle", {}).get("namedStyleType", "NORMAL_TEXT"),
            "texto": texto,
            "texto_md": _texto_parrafo_md(elemento).strip(),
            "es_lista": parrafo.get("bullet") is not None,
            "ordenada": _es_ordenada(parrafo, listas),
            "heading_id": parrafo.get("paragraphStyle", {}).get("headingId"),
        })
    return salida


def _agrupar_recetas(parrafos: list[dict]) -> list[dict]:
    """HEADING_1 = categoría, HEADING_2 = subcategoría (opcional, puede no
    haber ninguno entre un H1 y el primer H3), HEADING_3 = receta. Todo lo
    que sigue a un H3 (incluidos HEADING_4+ de secciones y sub-partes como
    'Masa sablée') pertenece a esa receta hasta el próximo H1/H2/H3.
    Un H1 nuevo resetea la subcategoría (no se "hereda" entre categorías).
    """
    recetas = []
    categoria_actual = None
    subcategoria_actual = None
    actual = None
    for p in parrafos:
        if p["style"] == "HEADING_1":
            categoria_actual = p["texto"] or None
            subcategoria_actual = None
            actual = None
        elif p["style"] == "HEADING_2":
            subcategoria_actual = p["texto"] or None
            actual = None
        elif p["style"] == "HEADING_3":
            if not p["texto"]:
                continue
            actual = {
                "titulo": p["texto"],
                "categoria_texto": categoria_actual,
                "subcategoria_texto": subcategoria_actual,
                "heading_id": p.get("heading_id"),
                "parrafos": [],
            }
            recetas.append(actual)
        elif actual is not None:
            actual["parrafos"].append(p)
    return recetas


def _parsear_receta(titulo: str, parrafos: list[dict]) -> dict:
    fuente = None
    fecha = None
    seccion = None
    materiales, ingredientes, pasos = [], [], []
    cuerpo_libre = []
    destinos = {"materiales": materiales, "ingredientes": ingredientes, "paso a paso": pasos}
    # Para cada sección, si el último elemento agregado era lista o texto plano —
    # permite intercalar un párrafo (ej. "Mismos ingredientes que X, con estos
    # cambios:") con bullets dentro de la misma sección sin que Markdown funda
    # ambos en un solo párrafo (necesita línea en blanco antes/después de una lista).
    ultimo_es_lista: dict[str, bool | None] = {k: None for k in destinos}

    def _agregar(seccion_actual: str, texto_linea: str, es_lista: bool) -> None:
        destino = destinos[seccion_actual]
        anterior = ultimo_es_lista[seccion_actual]
        if anterior is not None and anterior != es_lista:
            destino.append("")
        destino.append(texto_linea)
        ultimo_es_lista[seccion_actual] = es_lista

    for p in parrafos:
        texto = p["texto"]
        if not texto:
            continue
        texto_md = p.get("texto_md") or texto

        if p["es_lista"]:
            marca = "1." if p["ordenada"] else "-"
            linea = f"{marca} {texto_md}"
            if seccion in destinos:
                _agregar(seccion, linea, True)
            else:
                cuerpo_libre.append(linea)
            continue

        m = FUENTE_RE.match(texto)
        if m and not fuente:
            valor = m.group(1).strip()
            if valor:
                fuente = valor
            continue

        m = FECHA_RE.match(texto)
        if m:
            fecha = fecha_a_iso(m.group(1))
            continue

        if CAMPO_VACIO_RE.match(texto):
            # "Tiempo:" / "Dificultad:" sin valor: no hay nada que extraer,
            # y dejarlos como texto suelto en el cuerpo es puro ruido.
            continue

        # Encabezado de sección: puede venir como texto plano ("Ingredientes:")
        # o como heading ("### Paso a paso (con fotos)") — se chequea antes
        # de tratarlo como heading genérico.
        m = SECCION_RE.match(texto)
        if m and len(texto) <= SECCION_MAX_LEN:
            seccion = m.group(1).lower()
            continue

        if p["style"].startswith("HEADING"):
            nivel = int(p["style"][-1]) if p["style"][-1].isdigit() else 2
            cuerpo_libre.append(f"{'#' * (nivel + 1)} {texto_md}")
            seccion = None
            continue

        if seccion in destinos and REFERENCIA_VARIANTE_RE.match(texto):
            _agregar(seccion, texto_md, False)
        elif seccion is None:
            cuerpo_libre.append(texto_md)
        # Cualquier otro párrafo suelto dentro de una sección activa (notas al
        # paso, comentarios personales, etc.) se sigue descartando a propósito:
        # son prosa informal que un curador humano resume, no texto a migrar
        # literalmente (ver DECISIONS.md, "recetas tipo bitácora").

    completa = bool(ingredientes or materiales) and bool(pasos)
    return {
        "titulo": titulo,
        "slug": slugify(titulo),
        "fuente": fuente,
        "fecha_actualizacion": fecha,
        "materiales": materiales,
        "ingredientes": ingredientes,
        "paso_a_paso": pasos,
        "cuerpo_libre": cuerpo_libre,
        "completa": completa,
    }


def parse_doc(doc_json: dict) -> tuple[list[dict], list[dict]]:
    """doc_json -> (recetas_completas, incompletas_o_ignoradas).

    Pura: no toca disco. `recetas_completas` trae todo lo necesario para
    escribir un .md; `incompletas_o_ignoradas` trae {tab, titulo, motivo}
    para reportar sin cortar el resto del sync. Solo se procesa la pestaña
    `TAB_RECETAS` ("Recetas"); cualquier otra (ej. "Template receta") se
    ignora en silencio — ya no hay una pestaña por categoría.
    """
    completas, incompletas = [], []
    tabs = doc_json.get("content", {}).get("tabs", [])
    tab = next((t for t in tabs if t.get("tabProperties", {}).get("title", "") == TAB_RECETAS), None)
    if tab is None:
        incompletas.append({"tab": None, "titulo": None,
                             "motivo": f"no se encontró la pestaña '{TAB_RECETAS}' en el Doc"})
        return completas, incompletas

    return parse_parrafos(_parrafos_de_tab(tab))


def _registros_raw(origen: Path) -> list[dict]:
    return [json.loads(l) for l in origen.read_text(encoding="utf-8").splitlines() if l.strip()]


def leer_raw(origen: Path) -> list[dict]:
    """Párrafos del raw (sin la línea de metadatos `_doc`)."""
    return [r for r in _registros_raw(origen) if "_doc" not in r]


def leer_doc_meta(origen: Path) -> dict:
    """{"documentId", "tabId"} del Doc, o {} si el raw no los trae."""
    return next((r["_doc"] for r in _registros_raw(origen) if "_doc" in r), {})


def url_receta(meta: dict, heading_id: str | None) -> str | None:
    """Link directo al título de una receta dentro del Google Doc.

    Usa la vista simplificada (`/mobilebasic`) y no el editor (`/edit#heading=`): en
    un Doc largo el editor calcula mal el scroll al título y cae en otro lugar, y
    distinto en cada carga (comprobado). En `/mobilebasic` cada título es un ancla
    HTML real (`id="h.xxxx"`), así que el navegador llega exacto. Además no depende
    de si el usuario tiene secciones plegadas, y carga más rápido en el celular.
    """
    if not (meta.get("documentId") and meta.get("tabId") and heading_id):
        return None
    return f"https://docs.google.com/document/d/{meta['documentId']}/mobilebasic?tab={meta['tabId']}#{heading_id}"


def parrafos_desde_raw(raw: list[dict]) -> list[dict]:
    """Párrafos crudos (data/01_data_understanding/doc/recetas.jsonl) -> la forma
    aplanada que consume `parse_parrafos`."""
    salida = []
    for p in raw:
        runs = p.get("runs", [])
        texto = "".join(r[0] for r in runs).strip()
        texto_md = md_desde_runs([(r[0], bool(r[1])) for r in runs]).strip()
        salida.append({
            "style": p.get("style", "NORMAL_TEXT"),
            "texto": texto,
            "texto_md": texto_md,
            "es_lista": "lista" in p,
            "ordenada": p.get("lista") == "ordenada",
            "nivel": p.get("nivel", 0),
            "heading_id": p.get("headingId"),
        })
    return salida


def parse_parrafos(parrafos: list[dict]) -> tuple[list[dict], list[dict]]:
    """Lista aplanada de párrafos -> (completas, incompletas). Es el paso común
    a las dos entradas: el JSON crudo de la Docs API (`parse_doc`) y la capa
    cruda versionada `data/01_data_understanding/doc/recetas.jsonl` (`parrafos_desde_raw`)."""
    completas, incompletas = [], []
    for bloque in _agrupar_recetas(parrafos):
        if not bloque["categoria_texto"]:
            incompletas.append({"tab": TAB_RECETAS, "titulo": bloque["titulo"],
                                 "motivo": "receta sin categoría (falta un HEADING_1 que la contenga)"})
            continue

        receta = _parsear_receta(bloque["titulo"], bloque["parrafos"])
        categoria = normalizar_encabezado(bloque["categoria_texto"])
        subcategoria = normalizar_encabezado(bloque["subcategoria_texto"]) if bloque["subcategoria_texto"] else None
        campo_subcategoria = schema.CAMPO_SUBCATEGORIA.get(
            schema.clave_categoria(categoria), schema.CAMPO_SUBCATEGORIA_DEFAULT
        )

        receta["categorias"] = [categoria]
        for campo in schema.SUBFILTRO_CAMPOS:
            receta[campo] = None
        if subcategoria:
            receta[campo_subcategoria] = subcategoria
        receta["tab"] = TAB_RECETAS
        receta["doc_heading_id"] = bloque.get("heading_id")  # no entra al doc_hash: no es contenido
        receta["doc_hash"] = contenido_hash(receta)
        if receta["completa"]:
            completas.append(receta)
        else:
            incompletas.append({
                "tab": TAB_RECETAS,
                "titulo": receta["titulo"],
                "slug": receta["slug"],
                "doc_heading_id": receta["doc_heading_id"],
                "motivo": "sin ingredientes/materiales" if not (receta["ingredientes"] or receta["materiales"])
                          else "sin paso a paso",
            })
    return completas, incompletas


def _doc_hash_guardado(md_path: Path) -> str | None:
    """Lee el `doc_hash` del frontmatter de un `recipes/<slug>.md` ya mergeado,
    si lo tiene. Un archivo sin ese campo (ej. migrado antes de que existiera)
    se trata como "sin hash guardado", nunca como error.
    """
    match = FRONTMATTER_RE.match(md_path.read_text(encoding="utf-8"))
    if not match:
        return None
    front = yaml.safe_load(match.group(1)) or {}
    return front.get("doc_hash")


def detectar_cambios(completas: list[dict], recipes_dir: Path) -> dict[str, list[dict]]:
    """Compara el `doc_hash` de cada receta recién leída del Doc contra el que
    quedó guardado en `recipes/<slug>.md` la última vez que se mergeó. Pura:
    solo lee `recipes_dir`, no escribe nada. Para que esto siga siendo preciso,
    el merge a mano tiene que copiar el `doc_hash` del borrador al archivo
    final (ver README, sección del sync).
    """
    nuevas, cambiadas, sin_cambios = [], [], []
    for receta in completas:
        md_path = recipes_dir / f'{receta["slug"]}.md'
        if not md_path.exists():
            nuevas.append(receta)
        elif _doc_hash_guardado(md_path) != receta["doc_hash"]:
            cambiadas.append(receta)
        else:
            sin_cambios.append(receta)
    return {"nuevas": nuevas, "cambiadas": cambiadas, "sin_cambios": sin_cambios}


def render_markdown(receta: dict) -> str:
    front = [
        "---",
        f'titulo: "{receta["titulo"]}"',
        "categorias: [" + ", ".join(f'"{c}"' for c in receta["categorias"]) + "]",
    ]
    for campo in sorted(schema.SUBFILTRO_CAMPOS):
        if receta.get(campo):
            front.append(f'{campo}: "{receta[campo]}"')
    if receta["fuente"]:
        front.append(f'fuente: "{receta["fuente"]}"')
    if receta["fecha_actualizacion"]:
        front.append(f'fecha_actualizacion: "{receta["fecha_actualizacion"]}"')
    if receta.get("doc_url"):
        front.append(f'doc_url: "{receta["doc_url"]}"')
    front.append(f'doc_hash: "{receta["doc_hash"]}"')
    front.append("---")

    cuerpo = []
    if receta["cuerpo_libre"]:
        cuerpo.append("\n".join(receta["cuerpo_libre"]))
    if receta["materiales"]:
        cuerpo.append("## Materiales\n" + "\n".join(receta["materiales"]))
    if receta["ingredientes"]:
        cuerpo.append("## Ingredientes\n" + "\n".join(receta["ingredientes"]))
    if receta["paso_a_paso"]:
        cuerpo.append("## Paso a paso\n" + "\n".join(receta["paso_a_paso"]))

    return "\n".join(front) + "\n" + "\n\n".join(cuerpo) + "\n"


def run_sync(doc_json_path: Path, out_dir: Path, recipes_dir: Path = config.CURATED_DIR) -> int:
    if doc_json_path.suffix == ".jsonl":
        # Capa cruda versionada (data/01_data_understanding/doc/recetas.jsonl), ver collect_doc.py.
        completas, incompletas = parse_parrafos(parrafos_desde_raw(leer_raw(doc_json_path)))
    else:
        doc_json = json.loads(doc_json_path.read_text(encoding="utf-8"))
        completas, incompletas = parse_doc(doc_json)

    out_dir.mkdir(parents=True, exist_ok=True)
    for receta in completas:
        (out_dir / f'{receta["slug"]}.md').write_text(render_markdown(receta), encoding="utf-8")

    cambios = detectar_cambios(completas, recipes_dir)
    print(f"OK: {len(completas)} borrador(es) escrito(s) en {out_dir}/")
    print("No se tocó recipes/ — comparar a mano y mergear preservando foto/porciones curados.")
    print(
        f"Del Doc: {len(cambios['nuevas'])} nueva(s), {len(cambios['cambiadas'])} cambiada(s) "
        f"respecto al último sync, {len(cambios['sin_cambios'])} sin cambios (se pueden ignorar)."
    )
    if cambios["nuevas"]:
        print("  Nuevas: " + ", ".join(r["slug"] for r in cambios["nuevas"]))
    if cambios["cambiadas"]:
        print("  Cambiadas: " + ", ".join(r["slug"] for r in cambios["cambiadas"]))
    if incompletas:
        print(f"{len(incompletas)} receta(s) del Doc NO se generaron (faltan datos):")
        for i in incompletas:
            nombre = i["titulo"] or "(pestaña completa)"
            print(f"  - [{i['tab']}] {nombre}: {i['motivo']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("doc_json", type=Path, help="JSON crudo devuelto por read_doc, o data/01_data_understanding/doc/recetas.jsonl")
    parser.add_argument("--out", type=Path, default=config.DRAFTS_DIR)
    parser.add_argument("--recipes", type=Path, default=config.CURATED_DIR,
                         help="Directorio con las recetas ya mergeadas, para detectar qué cambió")
    args = parser.parse_args()
    return run_sync(args.doc_json, args.out, args.recipes)


if __name__ == "__main__":
    sys.exit(main())
