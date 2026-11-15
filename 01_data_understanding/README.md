# 01 · Data understanding

Recolecta las **dos fuentes** de datos, sin interpretarlas:

- **A · Google Doc** (`data/01_data_understanding/doc/`): el Doc tal cual, editado a mano.
- **B · lo curado a mano** (`data/01_data_understanding/curated/` e `images/`): las recetas `.md` con lo que el Doc no tiene (foto, porciones, dificultad, tiempo), la prosa pulida y las portadas conseguidas por otros medios. También se edita a mano; no es un derivado. `curated/doc_aliases.yml` dice qué receta del Doc corresponde a cuál curada cuando los títulos difieren.

| Script | Qué hace | Lee | Escribe |
|---|---|---|---|
| `collect_initial_data/doc/collect_doc.py` | reduce el JSON de `read_doc` a un párrafo por línea (estilo, listas, negrita, links) | JSON de `read_doc` (lo baja Claude con el conector) | `data/01_data_understanding/doc/recetas.jsonl` |
| `collect_initial_data/doc/extract_doc_images.py` | baja las fotos embebidas en el Doc, numeradas por receta | JSON de `read_doc` | `data/01_data_understanding/images/<slug>/doc-NN.jpg` |
| `collect_initial_data/covers/fetch_covers.py` | portada desde la `fuente` enlazada (miniatura de YouTube u `og:image`) | `data/01_data_understanding/curated/` | `data/01_data_understanding/images/<slug>/cover.jpg` |

`git diff data/01_data_understanding/doc/recetas.jsonl` muestra exactamente qué cambió en el Doc desde el último sync.

Corrida: `make collect DOC=<doc.json>` (los otros dos, por ruta: `python 01_data_understanding/collect_initial_data/<fuente>/<script>.py`).

Nota: `fetch_covers.py` lee `curated/` (la fuente B, de esta misma fase) para saber qué recetas no tienen portada.
