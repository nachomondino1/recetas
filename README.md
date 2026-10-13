# Recetas

Sitio estático de recetas familiares: cards con foto, tiempo y dificultad, filtrables por categoría y ordenables por tiempo.

## Fuente de los datos: el Google Doc

Las recetas se editan en un Google Doc (una pestaña por categoría: Comidas Saladas, Postres y Tartas, Meriendas, Jugos naturales). Ese Doc es la fuente de verdad — **no se edita `recipes/*.md` a mano para contenido nuevo.**

**Para sincronizar después de editar el Doc**, pedirle a Claude Code (en una sesión con el conector de Google Docs) que resincronice. El flujo:

1. Claude lee el Doc con el conector (`read_doc`) y guarda el JSON crudo.
2. `python -m src.doc_sync <doc.json> --out recipes_draft/` — parsea cada pestaña (mapeo pestaña → categoría en `TAB_CATEGORIAS`, `src/doc_sync.py`) y escribe un borrador `.md` por receta completa. Las recetas sin "Ingredientes"/"Paso a paso" se listan como incompletas y no se escriben (no inventa contenido).
3. Comparar `recipes_draft/` contra `recipes/` y aplicar los cambios a mano, **preservando los campos que el Doc no tiene** (`foto`, a veces `porciones`, fusiones de contenido duplicado ya resueltas). El sync nunca pisa `recipes/` directamente por esto.
4. `make update && make test`, revisar en el navegador (`make open`) y commitear.

Ver `DECISIONS.md` (entrada "Google Doc como fuente, no Markdown a mano") para el porqué.

## Formato de `recipes/<slug>.md`

1. Frontmatter obligatorio: `titulo` y `categorias` (lista, valores válidos en `src/schema.py`: `almuerzo`, `cena`, `merienda`, `postre`, `jugos`).
2. Frontmatter opcional: `dificultad` (`baja`/`media`/`alta`), `tiempo_minutos`, `tiempo_minutos_max` (para rangos), `porciones`, `foto`, `fecha_actualizacion`, `fuente`.
3. Si hay foto, ponerla en `images/<slug>/<archivo>` y referenciarla en el frontmatter como `foto: <slug>/<archivo>`. El Doc no trae fotos de portada utilizables todavía — es un campo que se completa a mano.
4. El cuerpo es Markdown normal: `## Materiales`, `## Ingredientes` (con `### <subgrupo>` si hace falta agrupar), `## Paso a paso`. Tips y advertencias como citas: `> ℹ️ ...` / `> ⚠️ ...`.

## Comandos

```
make setup   # crea el venv e instala dependencias (una sola vez)
make update  # regenera docs/recetas.json y docs/data.js desde recipes/
make test    # corre los tests de validación
make open    # abre el sitio en el navegador
make clean   # borra el venv y lo generado
```

```
python -m src.doc_sync <doc.json> --out recipes_draft/   # borradores desde el Google Doc (ver arriba)
```

## Si el export corta con un ERROR

Significa que algún archivo en `recipes/` tiene un dato roto (falta `titulo`, `categorias` vacía, un valor fuera del enum, etc.). El mensaje dice el archivo y el campo. No se escribe nada nuevo — lo publicado en `docs/` queda como estaba hasta corregir la fuente.

Ver `DECISIONS.md` para el porqué de las decisiones de arquitectura, y `src/schema.py` para el contrato completo de campos.
