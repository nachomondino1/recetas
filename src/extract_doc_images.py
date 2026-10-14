"""Extrae las fotos embebidas en el Google Doc y las baja a `images/<slug>/doc-NN.jpg`.

El usuario escribe el Doc desde el celu y va insertando fotos de comida
sueltas entre el texto de cada receta (no son "fotos de portada", son fotos
de paso a paso o del resultado, mezcladas). Este script no decide cuál de
esas fotos es la mejor ni toca el frontmatter — esa curación la hace un
humano después, a mano (ver DATA_FLOW_PLAYBOOK). Acá solo se bajan todas,
en orden, a una carpeta por receta, para poder mirarlas y elegir.

Las fotos quedan representadas en el Doc de dos formas distintas según cómo
se insertaron (confirmado contra el JSON real, no es solo la hipótesis
inicial):
  - ancladas "en línea" dentro del texto: el párrafo tiene un elemento
    `inlineObjectElement.inlineObjectId`, que resuelve en
    `documentTab["inlineObjects"][id]`.
  - "flotantes"/con ajuste de texto: el párrafo tiene un
    `positionedObjectIds` (lista, a nivel párrafo, no de elemento), que
    resuelve en `documentTab["positionedObjects"][id]`.
En ambos casos la imagen real cuelga de
`[...]Properties"]["embeddedObject"]["imageProperties"]["contentUri"]`, una
URL firmada de Google que vence a los tolerantes minutos — por eso todo pasa
en una sola corrida de este script (parsear + bajar), nunca en dos.

Nota importante: `inlineObjects`/`positionedObjects` viven DENTRO de cada
`documentTab` (una pestaña puede tener fotos ancladas distinto que otra),
no en la raíz del `doc_json` como sugería la hipótesis original.

Uso: .venv/bin/python -m src.extract_doc_images <path-al-doc_json>
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

from src import config
from src.doc_sync import TAB_CATEGORIAS, TABS_IGNORADAS, _texto_parrafo, slugify

UA = "Mozilla/5.0 (compatible; recetas-image-extract/1.0)"


def _fetch(url: str) -> bytes | None:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            if resp.status != 200:
                return None
            return resp.read()
    except Exception:
        return None


def _content_uri_inline(doc_tab: dict, object_id: str) -> str | None:
    objeto = doc_tab.get("inlineObjects", {}).get(object_id, {})
    return (
        objeto.get("inlineObjectProperties", {})
        .get("embeddedObject", {})
        .get("imageProperties", {})
        .get("contentUri")
    )


def _content_uri_positioned(doc_tab: dict, object_id: str) -> str | None:
    objeto = doc_tab.get("positionedObjects", {}).get(object_id, {})
    return (
        objeto.get("positionedObjectProperties", {})
        .get("embeddedObject", {})
        .get("imageProperties", {})
        .get("contentUri")
    )


def _imagenes_de_parrafo(parrafo: dict, doc_tab: dict) -> list[str]:
    """contentUri de todas las fotos ancladas a este párrafo, inline + flotantes."""
    uris = []
    for elemento in parrafo.get("elements", []):
        inline = elemento.get("inlineObjectElement")
        if not inline:
            continue
        uri = _content_uri_inline(doc_tab, inline.get("inlineObjectId", ""))
        if uri:
            uris.append(uri)
    for object_id in parrafo.get("positionedObjectIds", []):
        uri = _content_uri_positioned(doc_tab, object_id)
        if uri:
            uris.append(uri)
    return uris


def _recorrer_tab(tab: dict) -> tuple[dict[str, list[str]], list[str]]:
    """Misma lógica de agrupamiento que doc_sync._agrupar_recetas (HEADING_2
    abre receta nueva, HEADING_1+ no), pero sobre los párrafos crudos — acá
    hace falta `elements`/`positionedObjectIds`, que _parrafos_de_tab no
    conserva porque los aplana a texto plano.

    Devuelve (fotos_por_titulo, fotos_de_front_matter). `fotos_por_titulo`
    usa el título tal cual aparece en el Doc (sin slugify todavía) como
    clave, en orden de aparición; `fotos_de_front_matter` son las fotos
    encontradas antes del primer HEADING_2 de la pestaña (no pertenecen a
    ninguna receta).
    """
    doc_tab = tab.get("documentTab", {})
    fotos_por_titulo: dict[str, list[str]] = {}
    front_matter: list[str] = []
    titulo_actual = None

    for elemento in doc_tab.get("body", {}).get("content", []):
        parrafo = elemento.get("paragraph")
        if parrafo is None:
            continue
        style = parrafo.get("paragraphStyle", {}).get("namedStyleType", "NORMAL_TEXT")
        texto = _texto_parrafo(elemento).strip()
        if style == "HEADING_2" and texto:
            titulo_actual = texto
            fotos_por_titulo.setdefault(titulo_actual, [])

        uris = _imagenes_de_parrafo(parrafo, doc_tab)
        if not uris:
            continue
        if titulo_actual is None:
            front_matter.extend(uris)
        else:
            fotos_por_titulo[titulo_actual].extend(uris)

    return fotos_por_titulo, front_matter


def extraer_imagenes(doc_json: dict) -> dict:
    """doc_json -> estructura intermedia, pura (no toca disco ni red):

    {
      "recetas": {slug: [contentUri, ...]},       # ya con slugify aplicado
      "titulos_por_slug": {slug: titulo_original},
      "front_matter": {titulo_tab: [contentUri, ...]},
    }
    """
    recetas: dict[str, list[str]] = {}
    titulos_por_slug: dict[str, str] = {}
    front_matter: dict[str, list[str]] = {}

    for tab in doc_json.get("content", {}).get("tabs", []):
        titulo_tab = tab.get("tabProperties", {}).get("title", "")
        if titulo_tab in TABS_IGNORADAS or titulo_tab not in TAB_CATEGORIAS:
            continue

        fotos_por_titulo, fotos_front = _recorrer_tab(tab)
        if fotos_front:
            front_matter.setdefault(titulo_tab, []).extend(fotos_front)

        for titulo, uris in fotos_por_titulo.items():
            if not uris:
                continue
            slug = slugify(titulo)
            recetas.setdefault(slug, []).extend(uris)
            titulos_por_slug[slug] = titulo

    return {"recetas": recetas, "titulos_por_slug": titulos_por_slug, "front_matter": front_matter}


def descargar_imagenes(extraido: dict, recipes_dir: Path, images_dir: Path) -> dict:
    """Baja todas las imágenes en `extraido['recetas']` a images/<slug>/doc-NN.jpg.

    Nunca toca cover.jpg. Devuelve un reporte: descargas por slug, slugs que
    no matchean ningún recipes/*.md existente, y fallos de descarga.
    """
    existentes = {p.stem for p in recipes_dir.glob("*.md")}
    descargas_por_slug: dict[str, int] = {}
    mismatches: list[tuple[str, str, int]] = []
    fallos: list[tuple[str, str]] = []

    for slug, uris in sorted(extraido["recetas"].items()):
        destino_dir = images_dir / slug
        descargadas = 0
        for i, uri in enumerate(uris, start=1):
            data = _fetch(uri)
            if data is None:
                fallos.append((slug, uri))
                continue
            destino_dir.mkdir(parents=True, exist_ok=True)
            destino = destino_dir / f"doc-{i:02d}.jpg"
            destino.write_bytes(data)
            descargadas += 1
        descargas_por_slug[slug] = descargadas
        if slug not in existentes:
            mismatches.append((extraido["titulos_por_slug"][slug], slug, descargadas))

    return {"descargas_por_slug": descargas_por_slug, "mismatches": mismatches, "fallos": fallos}


def run(doc_json_path: Path) -> int:
    doc_json = json.loads(doc_json_path.read_text(encoding="utf-8"))
    extraido = extraer_imagenes(doc_json)
    reporte = descargar_imagenes(extraido, config.RECIPES_DIR, config.IMAGES_DIR)

    total = sum(reporte["descargas_por_slug"].values())
    print(f"OK: {total} imagen(es) descargada(s) en {len(reporte['descargas_por_slug'])} receta(s).")
    for slug, n in sorted(reporte["descargas_por_slug"].items()):
        print(f"  - {slug}: {n}")

    if reporte["mismatches"]:
        print(f"\n{len(reporte['mismatches'])} slug(s) SIN receta existente en {config.RECIPES_DIR}/ "
              "(se bajaron igual, revisar a mano — puede ser un nombre distinto o un subtítulo):")
        for titulo, slug, n in reporte["mismatches"]:
            print(f"  - {titulo!r} -> images/{slug}/ ({n} img)")

    if extraido["front_matter"]:
        print("\nFotos antes del primer HEADING_2 de la pestaña (no asignadas a ninguna receta):")
        for tab_titulo, uris in extraido["front_matter"].items():
            print(f"  - [{tab_titulo}]: {len(uris)} imagen(es) sin asignar")

    if reporte["fallos"]:
        print(f"\n{len(reporte['fallos'])} descarga(s) fallida(s) (URL firmada vencida o error de red):")
        for slug, uri in reporte["fallos"]:
            print(f"  - {slug}: {uri}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("doc_json", type=Path, help="JSON crudo devuelto por read_doc")
    args = parser.parse_args()
    return run(args.doc_json)


if __name__ == "__main__":
    sys.exit(main())
