"""Contrato de datos de una receta: único punto de verdad.

Lo importan tanto export_data.py (para validar) como los tests (para
construir fixtures) — la lista de campos nunca se duplica.
"""

import re

SCHEMA_VERSION = 2

DIFICULTADES = {"baja", "media", "alta"}

# Categoría y subcategoría son dinámicas: su VALOR es el texto del heading
# H1/H2 del Google Doc (ver doc_sync.normalizar_encabezado), no un enum
# cerrado — agregar/renombrar un H1 o H2 en el Doc no requiere tocar este
# archivo. Lo único que sigue siendo código (estable, no viaja en el Doc) es
# el NOMBRE del campo de subcategoría de cada categoría — para no volver a
# mezclar ejes en un solo campo "subcategoria" cuando ya tenemos un nombre
# con sentido semántico (ver DECISIONS.md, "Un solo eje de clasificación").
# Una categoría nueva que todavía no tiene entrada acá usa
# CAMPO_SUBCATEGORIA_DEFAULT hasta que se le ponga nombre.
CAMPO_SUBCATEGORIA_DEFAULT = "subcategoria"
CAMPO_SUBCATEGORIA: dict[str, str] = {
    "principales": "momento",
    "postres": "tipo_postre",
    "meriendas": "tipo_merienda",
    "bebidas": "tipo_bebida",
}
SUBFILTRO_CAMPOS = set(CAMPO_SUBCATEGORIA.values()) | {CAMPO_SUBCATEGORIA_DEFAULT}

_LETRA_RE = re.compile(r"[a-zA-ZÀ-ÿ]")


def clave_categoria(categoria: str) -> str:
    """Texto de categoría sin emoji/símbolos decorativos al inicio, usado
    como clave de CAMPO_SUBCATEGORIA. El usuario decora los H1 del Doc con
    emoji libremente (ej. "🍰 meriendas") y puede cambiarlo cuando quiera —
    la clave de lookup no debe depender de qué emoji eligió hoy (ver
    DECISIONS.md, "Emoji decorativo en categoría no rompe CAMPO_SUBCATEGORIA").
    """
    m = _LETRA_RE.search(categoria)
    return categoria[m.start():] if m else categoria


REQUIRED_FIELDS = {"titulo", "categorias"}
OPTIONAL_FIELDS = {
    "dificultad",
    "tiempo_minutos",
    "tiempo_minutos_max",
    "porciones",
    "foto",
    "fecha_actualizacion",
    "fuente",
    "doc_hash",
} | SUBFILTRO_CAMPOS
KNOWN_FIELDS = REQUIRED_FIELDS | OPTIONAL_FIELDS
