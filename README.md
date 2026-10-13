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
3. Si hay foto, ponerla en `images/<slug>/<archivo>` (normalmente `images/<slug>/cover.jpg`) y referenciarla en el frontmatter como `foto: <slug>/<archivo>`. Es un campo que se completa a mano — ver abajo de dónde sacarla.
4. El cuerpo es Markdown normal: `## Materiales`, `## Ingredientes` (con `### <subgrupo>` si hace falta agrupar), `## Paso a paso`. Tips y advertencias como citas: `> ℹ️ ...` / `> ⚠️ ...`.

## Cómo conseguir la foto de portada (`foto`) de una receta

Orden de prioridad — probar cada paso solo si el anterior no dio una imagen aceptable, nunca saltar al final para ahorrar tiempo:

1. **¿Ya hay `images/<slug>/cover.jpg`?** Nada que hacer.
2. **Fotos que el usuario ya sacó e insertó en el Google Doc** (son las fotos reales de la receta — siempre la mejor opción si existen):
   ```
   python -m src.extract_doc_images <doc.json>
   ```
   Baja **todas** las fotos de esa receta, numeradas, a `images/<slug>/doc-NN.jpg` (nunca elige portada sola ni pisa un `cover.jpg` que ya exista). Mirar cada una y copiar a mano la que mejor muestre el plato como `images/<slug>/cover.jpg` — preferir el plato terminado por sobre fotos de proceso, pero una foto de proceso reconocible es mejor que ninguna foto (caso *Asado*, *Turrón de quaker*).
3. **Si el Doc no tiene fotos de esa receta, pero `fuente` en el frontmatter apunta a algo:**
   ```
   python -m src.fetch_covers
   ```
   Si `fuente` (o un link en el cuerpo) es un video de YouTube, baja su miniatura. Si es una página de recetas, baja su `og:image`. Revisar el resultado antes de aceptarlo: a veces el `og:image` es una foto genérica del sitio o de una persona en vez del plato (pasó con *torta-de-nuez* — se reemplazó a mano por otra foto de la misma página). Instagram bloquea el scraping sin login; no vale la pena insistir ahí.
4. **Si no hay nada propio (ni Doc, ni `fuente` con imagen usable):** buscar una foto representativa del plato en **Bing Images** (no Google — pide CAPTCHA a tráfico automatizado, no se resuelve) usando los ingredientes/pasos reales de la receta como término de búsqueda, no solo el título. Abrir el resultado elegido en el panel de detalle de Bing y extraer la URL real de la imagen con `decodeURIComponent(location.href).match(/mediaurl=([^&]+)/)[1]` (evita el thumbnail recortado de `th.bing.com`). **Mirar la imagen antes de aceptarla**, siempre — esta es una foto genérica, no la receta real del usuario, así que tiene que representar bien el plato o no sirve.
5. **Si ninguna opción anterior da una imagen aceptable**, la receta queda sin `foto`. Es un WARNING de `export_data.py`, no un ERROR — nunca forzar una imagen que no representa el plato, y nunca generar una imagen (IA, placeholder genérico) en su lugar.

Ninguno de estos pasos está en el `Makefile` ni en CI: bajar fotos de fuentes externas necesita revisión visual humana antes de aceptar cada una, así que es manual por diseño. Detalle completo y el porqué de cada decisión en `DECISIONS.md`.

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
