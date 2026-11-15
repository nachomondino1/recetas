# 02 · Data preparation

Une las dos fuentes de la fase 01 en un solo conjunto de datos y lo deja listo para el sitio.

| Script | Tarea CRISP | Qué hace |
|---|---|---|
| `format_data.py` | formatear | Lee el Doc crudo (fuente A) y arma un borrador `.md` por receta: agrupa por `H1` categoría / `H2` subcategoría / `H3` receta, separa Materiales / Ingredientes / Paso a paso, pasa la negrita a `**...**` y calcula `doc_hash`. No inventa contenido: una receta sin ingredientes o sin paso a paso se reporta como incompleta |
| `integrate_data.py` | integrar | Une A (Doc) con B (curado) por receta |

**Reglas de `integrate_data.py`:**
- Solo en el Doc → **nueva**, entra sola al sitio (el export avisa si no tiene foto).
- En el Doc y en lo curado → **gana lo curado** (tiene lo que el Doc no tiene). Se compara `doc_hash`: si el Doc cambió desde la última curación se reporta "revisar", sin pisar nada.
- Solo curada → se conserva.

- **Lee:** `data/01_data_understanding/doc/recetas.jsonl` y `data/01_data_understanding/curated/`
- **Escribe:** `data/02_data_preparation/integrated/*.md` y `drafts/*.md` (ambos derivados y gitignored: nunca se editan a mano)
- **Corrida:** `make integrate` · `make sync` (borradores)
