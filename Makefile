.PHONY: help setup update test open clean

help:
	@echo "setup  - crea el venv e instala dependencias"
	@echo "update - regenera site/recetas.json y site/data.js a partir de recipes/"
	@echo "test   - corre los tests (el mismo comando que el CI, si lo hay)"
	@echo "open   - abre el sitio en el navegador"
	@echo "clean  - borra el venv y lo generado"

setup:
	python3 -m venv .venv
	.venv/bin/pip install -q -r requirements.txt

update:
	.venv/bin/python -m src.export_data

test:
	.venv/bin/python -m pytest tests/ -v

open:
	open site/index.html

clean:
	rm -rf .venv site/recetas.json site/data.js site/images
