"""Helpers sobre el JSON del Google Doc que usan 2+ fases (01 recolecta, 02 prepara).

Viven en `common/` para que una fase nunca importe de una posterior.
"""

import re
import unicodedata

TAB_RECETAS = "Recetas"
ORDERED_GLYPHS = {"DECIMAL", "ALPHA", "ROMAN", "UPPER_ALPHA", "UPPER_ROMAN"}


def texto_parrafo(elemento: dict) -> str:
    parrafo = elemento.get("paragraph")
    if not parrafo:
        return ""
    partes = [e.get("textRun", {}).get("content", "") for e in parrafo.get("elements", [])]
    return "".join(partes).rstrip("\n")


def es_ordenada(parrafo: dict, listas: dict) -> bool:
    list_id = (parrafo.get("bullet") or {}).get("listId")
    if not list_id:
        return False
    niveles = listas.get(list_id, {}).get("listProperties", {}).get("nestingLevels", [])
    if not niveles:
        return False
    return niveles[0].get("glyphType") in ORDERED_GLYPHS


def slugify(titulo: str) -> str:
    sin_emoji = "".join(c for c in titulo if not unicodedata.category(c).startswith("So"))
    sin_acentos = unicodedata.normalize("NFKD", sin_emoji).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", sin_acentos).strip("-").lower()
    return slug or "receta"
