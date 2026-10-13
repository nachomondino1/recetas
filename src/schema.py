"""Contrato de datos de una receta: único punto de verdad.

Lo importan tanto export_data.py (para validar) como los tests (para
construir fixtures) — la lista de campos nunca se duplica.
"""

from typing import NamedTuple

SCHEMA_VERSION = 1

CATEGORIAS = {"principal", "acompañante", "postre", "merienda", "bebidas"}
DIFICULTADES = {"baja", "media", "alta"}


class SubFiltro(NamedTuple):
    campo: str
    valores: set[str]
    avisar_si_falta: bool  # True = WARNING si la categoría está pero el campo no


# Campo opcional condicionado a una categoría ("qué es"), para distinguir
# adentro de ella sin volver a mezclar ejes en CATEGORIAS (ver DECISIONS.md,
# "Un solo eje de clasificación"). `avisar_si_falta` distingue dos casos:
# - bebidas/merienda: el sub-tipo clasifica TODA receta de esa categoría
#   (jugos/tragos, dulce/salado) → falta de dato es un WARNING, igual que
#   dificultad.
# - principal/momento: es una excepción puntual (ej. Asado, que se come solo
#   al mediodía), no algo que toda receta "principal" deba tener → su
#   ausencia es el caso normal, nunca WARNING.
SUBFILTROS: dict[str, SubFiltro] = {
    "bebidas": SubFiltro("tipo_bebida", {"jugos", "tragos"}, True),
    "merienda": SubFiltro("tipo_merienda", {"dulce", "salado"}, True),
    "principal": SubFiltro("momento", {"mediodía", "cena"}, False),
}
SUBFILTRO_CAMPOS = {sf.campo for sf in SUBFILTROS.values()}

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
