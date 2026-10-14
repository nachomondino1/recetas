# Recetas

Sitio estático de recetas familiares: cards con foto, tiempo y dificultad, filtrables por categoría y ordenables por tiempo.

## Fuente de los datos: el Google Doc

Las recetas se editan en un Google Doc, en una sola pestaña ("Recetas") con jerarquía de headers: `H1` = categoría (ej. "Principales"), `H2` = subcategoría opcional (ej. "Almuerzo"/"Cena" — algunas categorías no la tienen, ej. "Acompañantes"), `H3` = receta, `H4` = sección (Materiales/Ingredientes/Paso a paso), `H5` = sub-parte cuando una receta tiene varias (ej. *Lemon pie*: masa sablée, curd de limón...). Ese Doc es la fuente de verdad — **no se edita `recipes/*.md` a mano para contenido nuevo.**

**Para sincronizar después de editar el Doc**, pedirle a Claude Code (en una sesión con el conector de Google Docs) que resincronice. El flujo:

1. Claude lee el Doc con el conector (`read_doc`) y guarda el JSON crudo.
2. `python -m src.doc_sync <doc.json> --out recipes_draft/` — parsea la pestaña "Recetas" y escribe un borrador `.md` por receta completa. Categoría y subcategoría son dinámicas (el valor es el texto del H1/H2 tal cual, ver `normalizar_encabezado` en `src/doc_sync.py`) — agregar o renombrar un H1/H2 en el Doc no requiere tocar código. Las recetas sin "Ingredientes"/"Paso a paso" se listan como incompletas y no se escriben (no inventa contenido).
3. **El comando también imprime qué cambió de verdad**: compara el `doc_hash` de cada borrador contra el que ya está guardado en `recipes/<slug>.md` y separa las recetas en nuevas / cambiadas / sin cambios desde el último sync. Las "sin cambios" se pueden ignorar — no hace falta revisarlas a mano cada vez.
4. Para las nuevas/cambiadas: comparar el borrador contra `recipes/` y aplicar los cambios a mano, **preservando los campos que el Doc no tiene** (`foto`, a veces `porciones`, fusiones de contenido duplicado ya resueltas) y **copiando el `doc_hash` del borrador al archivo final** (si no se copia, esa receta va a aparecer como "cambiada" otra vez en el próximo sync aunque no haya cambiado). El sync nunca pisa `recipes/` directamente por esto.
5. `make update && make test`, revisar en el navegador (`make open`) y commitear.

Ver `DECISIONS.md` (entrada "Google Doc como fuente, no Markdown a mano") para el porqué.

## Formato de `recipes/<slug>.md`

1. Frontmatter obligatorio: `titulo` y `categorias` (lista). El valor es el texto del `H1` del Doc tal cual (ej. `principales`, `postres`, `meriendas`, `bebidas`, `acompañantes`) — no hay enum cerrado en `src/schema.py`, cualquier valor no vacío es válido. Clasifican por **qué es el plato**, no por cuándo se come. Una receta puede tener varias (poco común) y aparece en cada pestaña del sitio que le corresponda.
2. Frontmatter opcional: `dificultad` (`baja`/`media`/`alta`), `tiempo_minutos`, `tiempo_minutos_max` (para rangos), `porciones`, `foto`, `fecha_actualizacion`, `fuente`, `doc_hash` (interno — lo escribe `doc_sync.py`, no se edita a mano, ver sección anterior), y el campo de subcategoría de la categoría correspondiente (nombre fijo en `src/schema.py: CAMPO_SUBCATEGORIA`, valor libre — el texto del `H2` del Doc): `tipo_bebida` (ej. `tragos`, `jugos naturales`, solo si `categorias` incluye `bebidas`), `tipo_merienda` (ej. `🍰 budines`, `🍪 cookies`, `🍯 untables`, `otros`, solo si incluye `meriendas`), `tipo_postre` (ej. `frutal`, `🥚 huevo`, `🍫 chocolatoso`, `ddl`, solo si incluye `postres`), `momento` (`almuerzo`/`cena`, solo si incluye `principales`). El sync mecánico siempre lo completa cuando el Doc tiene `H2` para esa categoría — su ausencia en una receta ya sincronizada es un dato faltante (WARNING), no el caso normal. `acompañantes` no tiene `H2` en el Doc, así que no tiene campo de subcategoría.
3. Si hay foto, ponerla en `images/<slug>/<archivo>` (normalmente `images/<slug>/cover.jpg`) y referenciarla en el frontmatter como `foto: <slug>/<archivo>`. Es un campo que se completa a mano — ver abajo de dónde sacarla.
4. El cuerpo sigue un orden fijo de secciones (igual para toda receta):
   1. **Índice** ("En esta receta") — automático, lo genera `docs/app.js` (`crearIndice`) a partir de los `##` del cuerpo; no se escribe a mano.
   2. `## Materiales` — **opcional**, solo si la receta lo necesita (ver *Asado*).
   3. `## Ingredientes` — **obligatorio** en toda receta real (con `### <subgrupo>` si hay varias partes, ver *Lemon pie*/*Tarta de frutillas*). Los stubs "pendiente de completar" (*Empanadas*, *Tarta de espinaca*) son la única excepción.
   4. `## Paso a paso` — **obligatorio**. Incluye una subsección `### Imágenes del paso a paso` con **todas** las fotos del proceso que estén en el Google Doc para esa receta (las mismas que baja `src/extract_doc_images.py` a `images/<slug>/doc-NN.jpg`) — no solo la portada curada (`foto`/`cover.jpg`). Cada imagen lleva un id (`![alt](ruta){: .foto-paso #foto-<algo> }`, extensión `attr_list`) y un caption en cursiva debajo diciendo a qué paso corresponde; el paso correspondiente del texto linkea a esa imagen con `[📷 ver foto](#/receta/<slug>/foto-<algo>){: .ver-foto }` (nunca un `#ancla` suelto — rompe el router hash-based, ver `docs/app.js: route()`). Una foto que no corresponde a ningún paso puntual (resultado final, ingredientes) no lleva link entrante, solo el caption. Ver "Cómo elegir a qué paso corresponde cada foto" más abajo.

   Tips y advertencias como citas: `> ℹ️ ...` / `> ⚠️ ...`.

5. **Sub-recetas que se repiten en más de una receta** (masa sablée, crema pastelera): no se copia el contenido completo en cada archivo — viven una sola vez en `recipes/utils/<fragmento>.md` y se traen con `<!-- incluir: <fragmento>#ingredientes -->` / `#paso-a-paso` en el lugar donde iría ese contenido. Ver `recipes/utils/README.md` para el formato y cuándo vale la pena crear un fragmento nuevo.

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

## Cómo elegir a qué paso corresponde cada foto del paso a paso

`extract_doc_images.py` baja las fotos en el mismo orden en que aparecen en el Doc, pero sin decir a qué paso pertenece cada una. Para asignarlas sin inventar: releer el `doc.json` ya descargado y, para cada imagen, mirar el párrafo de texto que la precede inmediatamente dentro de esa receta (mismo criterio que usa `_agrupar_recetas`: todo lo que cuelga de un `HEADING_3` hasta el próximo `HEADING_1/2/3`). Ese texto casi siempre es el paso que la foto ilustra — el usuario saca la foto y la inserta ahí mismo, en el momento. Confirmar con la foto en sí solo cuando la posición es ambigua (ej. está justo entre dos pasos, o pegada al encabezado antes de cualquier paso — en ese caso suele ser una foto del resultado final o de los ingredientes, sin paso puntual asociado). **No asignar un paso mirando solo el contenido de la foto a ojo** — con pasos visualmente parecidos (ej. "agregar leña" repetido varias veces en *Asado*) es fácil errar el número; la posición en el documento es la señal confiable.

Ojo con un artefacto del Doc: después del primer `HEADING_3` de cada receta suele venir un **segundo heading vacío** (seguido de una tabla) antes del contenido real — si el parseo corta al encontrar cualquier heading, pierde todo lo que viene después de ese vacío. Hay que seguir *después* de ese bloque vacío, no cortar ahí (pasó con *Apple crumble*: un primer intento perdió 7 de sus 10 fotos por esto).

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
