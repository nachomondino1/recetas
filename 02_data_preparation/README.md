# 02 · Data preparation

`format_data.py` lee el raw (`data/01_data_understanding/doc/recetas.jsonl`, o el JSON de la API) y arma un borrador `.md` por receta: agrupa por `H1` categoría / `H2` subcategoría / `H3` receta, separa Materiales / Ingredientes / Paso a paso, pasa la negrita a `**...**` y calcula `doc_hash`. No inventa contenido: una receta sin ingredientes o sin paso a paso se lista como incompleta y no se escribe.

- **Lee:** `data/01_data_understanding/doc/recetas.jsonl`
- **Escribe:** `data/02_data_preparation/drafts/*.md` (gitignored; nunca pisa `recipes/`)
- **Corrida:** `make sync`

Las recetas curadas (`data/02_data_preparation/recipes/*.md`) y los fragmentos reusables (`recipes/utils/`) son el resultado versionado de esta fase. Hoy el merge de borrador a receta curada es manual; automatizarlo es la etapa 2 (ver `DECISIONS.md`, "Capa cruda del Doc").
