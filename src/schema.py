"""Contrato de datos de una receta: único punto de verdad.

Lo importan tanto export_data.py (para validar) como los tests (para
construir fixtures) — la lista de campos nunca se duplica.
"""

SCHEMA_VERSION = 1

CATEGORIAS = {"almuerzo", "cena", "merienda", "postre"}
DIFICULTADES = {"baja", "media", "alta"}

REQUIRED_FIELDS = {"titulo", "categorias"}
OPTIONAL_FIELDS = {
    "dificultad",
    "tiempo_minutos",
    "tiempo_minutos_max",
    "porciones",
    "foto",
    "fecha_actualizacion",
    "fuente",
}
KNOWN_FIELDS = REQUIRED_FIELDS | OPTIONAL_FIELDS
