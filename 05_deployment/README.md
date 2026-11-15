# 05 · Deployment

`generate_site.py` valida las recetas curadas (ERROR corta el build y no escribe nada; WARNING no), resuelve los fragmentos `<!-- incluir: ... -->`, renderiza el cuerpo a HTML y genera lo que consume el navegador.

- **Lee:** `data/02_data_preparation/recipes/` e `images/`
- **Escribe:** `docs/data/recetas.json`, `docs/data/data.js` y `docs/images/`
- **Corrida:** `make update`

El sitio se publica desde `docs/` (GitHub Pages "desde rama"), no desde `site/`: el repo ya estaba publicado así y el playbook permite `docs/` en ese caso.

Pendiente (etapa 2): separar la validación y la resolución de includes (hoy acá) hacia `02_data_preparation/`, dejando acá solo la generación del sitio.
