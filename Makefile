.PHONY: help setup update serve test clean collect sync

help:
	@echo "setup   - crea el venv e instala dependencias"
	@echo "update  - regenera docs/data/ (recetas.json y data.js) a partir de data/02_data_preparation/recipes/"
	@echo "serve   - sirve el sitio en http://localhost:8778"
	@echo "test    - corre los tests"
	@echo "collect - 01: reduce el JSON de read_doc a data/01_data_understanding/doc/recetas.jsonl (DOC=ruta.json)"
	@echo "sync    - 02: genera borradores desde el raw en data/02_data_preparation/drafts/"
	@echo "clean   - borra el venv y lo generado"

setup:
	python3 -m venv .venv
	.venv/bin/pip install -q -r requirements.txt

update:
	.venv/bin/python 05_deployment/generate_site.py

serve:
	python3 -m http.server 8778 --directory docs

test:
	.venv/bin/python -m pytest tests/ -v

collect:
	.venv/bin/python 01_data_understanding/collect_initial_data/doc/collect_doc.py $(DOC)

sync:
	.venv/bin/python 02_data_preparation/format_data.py data/01_data_understanding/doc/recetas.jsonl

clean:
	rm -rf .venv docs/data docs/images data/02_data_preparation/drafts
