"""Convierte el JSON crudo de la Google Docs API (una pestaña por categoría)
en borradores de receta (.md con frontmatter), para no tener que transcribir
el Google Doc a mano cada vez que cambia.

No hay credenciales propias para leer el Doc en este script: Claude lo lee
con el conector de Google Docs (`read_doc`) y guarda ese JSON en un archivo;
este módulo solo lo parsea. Ver DECISIONS.md.

Principio del playbook de datos: no inventar contenido ambiguo. Una receta
sin Ingredientes ni Paso a paso se reporta como incompleta y no se escribe.

Escribe a un directorio de BORRADORES (`recipes_draft/` por default), nunca
pisa `recipes/` directamente: varias recetas tienen campos curados a mano
(`foto`, `porciones`, fusiones de contenido duplicado) que este parser
mecánico no puede reconstruir, y pisarlas en silencio sería peor que no
sincronizar.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

TAB_CATEGORIAS: dict[str, list[str]] = {
    "Comidas Saladas": ["principal"],
    "Postres y Tartas": ["postre"],
    "Meriendas": ["merienda"],
    "Jugos naturales": ["bebidas"],
}
# Default de tipo_bebida por pestaña, igual de determinístico que TAB_CATEGORIAS
# (ver schema.SUBFILTROS). Pestañas no listadas acá no setean tipo_bebida.
TAB_TIPO_BEBIDA: dict[str, str] = {
    "Jugos naturales": "jugos",
}
TABS_IGNORADAS = {"Template receta"}

MESES = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dic": 12,
}

FUENTE_RE = re.compile(r"^\s*fuentes?\s*:\s*(.*)$", re.IGNORECASE)
FECHA_RE = re.compile(r"^\s*(?:última|ultima)\s+actualizaci[oó]n\s*:\s*(.*)$", re.IGNORECASE)
FECHA_VALOR_RE = re.compile(r"(\d{1,2})\s+([a-zA-Zñ]+)\.?\s+(\d{4})")
SECCION_RE = re.compile(r"^(ingredientes|materiales|paso a paso)\b", re.IGNORECASE)
SECCION_MAX_LEN = 60
CAMPO_VACIO_RE = re.compile(r"^\s*(tiempo|dificultad)\s*:\s*$", re.IGNORECASE)
ORDERED_GLYPHS = {"DECIMAL", "ALPHA", "ROMAN", "UPPER_ALPHA", "UPPER_ROMAN"}


def fecha_a_iso(texto: str) -> str | None:
    m = FECHA_VALOR_RE.search(texto)
    if not m:
        return None
    dia, mes_txt, anio = m.groups()
    mes = MESES.get(mes_txt.lower().rstrip("."))
    if not mes:
        return None
    return f"{anio}-{mes:02d}-{int(dia):02d}"


def slugify(titulo: str) -> str:
    sin_emoji = "".join(c for c in titulo if not unicodedata.category(c).startswith("So"))
    sin_acentos = unicodedata.normalize("NFKD", sin_emoji).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", sin_acentos).strip("-").lower()
    return slug or "receta"


def _texto_parrafo(elemento: dict) -> str:
    parrafo = elemento.get("paragraph")
    if not parrafo:
        return ""
    partes = [e.get("textRun", {}).get("content", "") for e in parrafo.get("elements", [])]
    return "".join(partes).rstrip("\n")


def _es_ordenada(parrafo: dict, listas: dict) -> bool:
    list_id = (parrafo.get("bullet") or {}).get("listId")
    if not list_id:
        return False
    niveles = listas.get(list_id, {}).get("listProperties", {}).get("nestingLevels", [])
    if not niveles:
        return False
    return niveles[0].get("glyphType") in ORDERED_GLYPHS


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
            "es_lista": parrafo.get("bullet") is not None,
            "ordenada": _es_ordenada(parrafo, listas),
        })
    return salida


def _agrupar_recetas(parrafos: list[dict]) -> list[dict]:
    """HEADING_1 agrupa visualmente (ej. 'Postres') pero no abre receta nueva.
    HEADING_2 es el título de cada receta; todo lo que sigue (incluidos
    HEADING_3+ de subrecetas como 'Masa sablée') pertenece a esa receta
    hasta el próximo HEADING_2.
    """
    recetas = []
    actual = None
    for p in parrafos:
        if p["style"] == "HEADING_2":
            if not p["texto"]:
                continue
            actual = {"titulo": p["texto"], "parrafos": []}
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

    for p in parrafos:
        texto = p["texto"]
        if not texto:
            continue

        if p["es_lista"]:
            marca = "1." if p["ordenada"] else "-"
            linea = f"{marca} {texto}"
            if seccion == "materiales":
                materiales.append(linea)
            elif seccion == "ingredientes":
                ingredientes.append(linea)
            elif seccion == "paso a paso":
                pasos.append(linea)
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
            cuerpo_libre.append(f"{'#' * (nivel + 1)} {texto}")
            seccion = None
            continue

        if seccion is None:
            cuerpo_libre.append(texto)

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
    para reportar sin cortar el resto del sync.
    """
    completas, incompletas = [], []
    for tab in doc_json.get("content", {}).get("tabs", []):
        titulo_tab = tab.get("tabProperties", {}).get("title", "")
        if titulo_tab in TABS_IGNORADAS:
            continue
        categorias = TAB_CATEGORIAS.get(titulo_tab)
        if categorias is None:
            incompletas.append({"tab": titulo_tab, "titulo": None,
                                 "motivo": f"pestaña desconocida, no mapeada en TAB_CATEGORIAS"})
            continue

        parrafos = _parrafos_de_tab(tab)
        for bloque in _agrupar_recetas(parrafos):
            receta = _parsear_receta(bloque["titulo"], bloque["parrafos"])
            receta["categorias"] = categorias
            receta["tipo_bebida"] = TAB_TIPO_BEBIDA.get(titulo_tab)
            receta["tab"] = titulo_tab
            if receta["completa"]:
                completas.append(receta)
            else:
                incompletas.append({
                    "tab": titulo_tab,
                    "titulo": receta["titulo"],
                    "motivo": "sin ingredientes/materiales" if not (receta["ingredientes"] or receta["materiales"])
                              else "sin paso a paso",
                })
    return completas, incompletas


def render_markdown(receta: dict) -> str:
    front = [
        "---",
        f'titulo: "{receta["titulo"]}"',
        "categorias: [" + ", ".join(f'"{c}"' for c in receta["categorias"]) + "]",
    ]
    if receta.get("tipo_bebida"):
        front.append(f'tipo_bebida: "{receta["tipo_bebida"]}"')
    if receta["fuente"]:
        front.append(f'fuente: "{receta["fuente"]}"')
    if receta["fecha_actualizacion"]:
        front.append(f'fecha_actualizacion: "{receta["fecha_actualizacion"]}"')
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


def run_sync(doc_json_path: Path, out_dir: Path) -> int:
    doc_json = json.loads(doc_json_path.read_text(encoding="utf-8"))
    completas, incompletas = parse_doc(doc_json)

    out_dir.mkdir(parents=True, exist_ok=True)
    for receta in completas:
        (out_dir / f'{receta["slug"]}.md').write_text(render_markdown(receta), encoding="utf-8")

    print(f"OK: {len(completas)} borrador(es) escrito(s) en {out_dir}/")
    print("No se tocó recipes/ — comparar a mano y mergear preservando foto/porciones curados.")
    if incompletas:
        print(f"{len(incompletas)} receta(s) del Doc NO se generaron (faltan datos):")
        for i in incompletas:
            nombre = i["titulo"] or "(pestaña completa)"
            print(f"  - [{i['tab']}] {nombre}: {i['motivo']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("doc_json", type=Path, help="JSON crudo devuelto por read_doc")
    parser.add_argument("--out", type=Path, default=Path("recipes_draft"))
    args = parser.parse_args()
    return run_sync(args.doc_json, args.out)


if __name__ == "__main__":
    sys.exit(main())
