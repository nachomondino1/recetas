# 01 · Data understanding

Recolecta el Google Doc y las imágenes **tal cual vienen**, sin interpretarlos.

| Script | Qué hace | Lee | Escribe |
|---|---|---|---|
| `collect_initial_data/doc/collect_doc.py` | reduce el JSON de `read_doc` a un párrafo por línea (estilo, listas, negrita, links) | JSON de `read_doc` (lo baja Claude con el conector) | `data/01_data_understanding/doc/recetas.jsonl` |
| `collect_initial_data/doc/extract_doc_images.py` | baja las fotos embebidas en el Doc, numeradas por receta | JSON de `read_doc` | `data/01_data_understanding/images/<slug>/doc-NN.jpg` |
| `collect_initial_data/covers/fetch_covers.py` | portada desde la `fuente` enlazada (miniatura de YouTube u `og:image`) | `data/02_data_preparation/recipes/` | `data/01_data_understanding/images/<slug>/cover.jpg` |

`git diff data/01_data_understanding/doc/recetas.jsonl` muestra exactamente qué cambió en el Doc desde el último sync.

Corrida: `make collect DOC=<doc.json>` (los otros dos, por ruta: `python 01_data_understanding/collect_initial_data/<fuente>/<script>.py`).

Nota: `fetch_covers.py` lee `recipes/` (fase 02) solo para saber qué recetas no tienen portada; no importa código de 02.
