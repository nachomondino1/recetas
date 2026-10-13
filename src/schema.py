"""Contrato de datos de una receta: único punto de verdad.

Lo importan tanto export_data.py (para validar) como los tests (para
construir fixtures) — la lista de campos nunca se duplica.
"""

SCHEMA_VERSION = 1

CATEGORIAS = {"principal", "acompañante", "postre", "merienda", "bebidas"}
DIFICULTADES = {"baja", "media", "alta"}

# Sub-tipo opcional, solo tiene sentido cuando "bebidas" está en categorias
# (ver validar() en export_data.py). Set abierto a crecer (ej. "tragos")
# sin tocar la validación.
TIPOS_BEBIDA = {"jugos", "tragos"}

REQUIRED_FIELDS = {"titulo", "categorias"}
OPTIONAL_FIELDS = {
    "dificultad",
    "tiempo_minutos",
    "tiempo_minutos_max",
    "porciones",
    "foto",
    "fecha_actualizacion",
    "fuente",
    "tipo_bebida",
}
KNOWN_FIELDS = REQUIRED_FIELDS | OPTIONAL_FIELDS
