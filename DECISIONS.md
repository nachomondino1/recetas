# Decisiones

## 2026-10-13 — De Word a sitio web filtrable

**Problema:** las recetas vivían en `Recetas.docx`. Encontrar algo para cocinar era difícil: sin foto, tiempo, dificultad ni categoría a la vista, y sin forma de filtrar u ordenar.

**Fuente de datos:** se evaluó seguir usando el Word/Google Doc o pasar a una Google Sheet para los campos estructurados. Se descartaron las dos: el contenido es texto largo (pasos, tips, advertencias), no tabular, y el usuario es el único que edita. Se eligió **un archivo Markdown por receta con YAML frontmatter**, versionado en `recipes/`, siguiendo la decisión #1 del playbook de datos (edita solo el usuario, contenido chico y no tabular → fuente versionada en el repo, no planilla).

**El `.docx` original no se commitea al repo.** Es un binario que deja de ser la fuente de verdad una vez migradas las 5 recetas; vive en `Downloads`. Los `.md` en `recipes/` son la única fuente de verdad desde ahora.

**Carga de datos en el front: `docs/data.js` embebido, no `fetch`.** El usuario abre `index.html` como `file://` para revisar antes de commitear, y `fetch` de un JSON local rompe por CORS en ese esquema. `docs/recetas.json` se genera igual, como contrato formal para tests/diffs, pero el sitio no lo usa en runtime.

**Enums iniciales** (`src/schema.py`): `categorias = {almuerzo, cena, merienda, postre}`, `dificultad = {baja, media, alta}`. Se incluyeron merienda/postre aunque hoy no haya ninguna receta así, porque el usuario espera agregarlas pronto — es un `set`, extenderlo es una línea.

**Sin fecha de última actualización manual como regla.** Asado la traía del doc original (`fecha_actualizacion: 2026-07-05`) y se preservó, pero no es un campo obligatorio ni con WARNING si falta: el historial de git (`git log -- recipes/<receta>.md`) cumple ese rol de ahora en más.

**Migración de contenido — decisiones puntuales:**
- *Guiso con lentejas* tenía dos versiones del paso a paso en el doc (una detallada y una "original" resumida, que parecía un borrador viejo). El usuario pidió conservar ambas: la detallada queda como pasos principales, la resumida como "Método alternativo" al final.
- *Asado* no tiene ninguna foto de plato servido en el doc (las 20 fotos son todas del proceso de armar el fuego). El usuario eligió no forzar ninguna de esas como portada: la card usa el placeholder (🍲) hasta que haya una mejor.
- *Pastel de papa*, *Tacos* y *Papas al horno* no traían `Tiempo`/`Dificultad` en el doc original. Los valores que quedaron en sus `.md` (90/media, 60/media, 75/baja) son estimaciones del usuario, no del doc.
- Las 5 recetas migradas se etiquetaron `categorias: [almuerzo, cena]` por default (el doc no tenía un campo de categoría); ajustar si alguna no aplica.

**Alcance v1:** sin CI todavía. El flujo es local: `make update` regenera `docs/recetas.json`/`data.js`, y `make open` lo muestra en el navegador antes de commitear.

## 2026-10-13 — Deploy a GitHub Pages: carpeta `docs/`, modo simple sin CI

**Problema:** GitHub Pages estaba configurado con fuente `main` / `/` (root), así que servía `README.md` en vez del sitio — el sitio real vivía en `site/`, una carpeta que Pages (modo legacy) no puede apuntar a directamente (solo soporta `/` o `/docs`).

**Decisión:** renombrar `site/` → `docs/` (sin tocar su contenido ni estructura) y apuntar GitHub Pages a `/docs` en la rama `main`. Sigue la decisión #3 del playbook de datos unificado (modo simple: artefacto versionado en `docs/`, sin Actions ni build en CI) — coherente con que este proyecto no tiene CI (ver arriba). `make update` + commit + push es el único paso de "deploy".

## 2026-10-13 — Google Doc como fuente, no Markdown a mano

**Problema:** la decisión anterior ("Markdown a mano, `.docx` no se commitea") no escalaba. El usuario mandó el Google Doc completo (5 pestañas: Comidas Saladas, Postres y Tartas, Meriendas, Jugos naturales, Template receta) y resultó tener ~35 recetas, no 5. Hand-editear YAML + Markdown en el repo para cada edición futura era más fricción que el Word original que se quería reemplazar.

**Decisión:** el Google Doc sigue siendo la fuente de verdad y el usuario lo sigue editando ahí (texto rico, fotos, desde el celular). Lo que cambia es que `recipes/*.md` ya no se edita a mano para contenido nuevo: se resincroniza desde el Doc cuando el usuario se lo pide a Claude. Esto es una variante del Arquetipo A del playbook de datos unificado (Planilla → export → sitio) con dos diferencias deliberadas, documentadas acá porque el playbook asume una fuente tabular:

1. **La "lectura de la fuente" no es un backend con credenciales propias** (a diferencia de `csv_export`/`sheets_api`, §3.2 del playbook). No hay service account para este proyecto chico; Claude lee el Doc en vivo con el conector de Google Docs de la sesión (`read_doc`) cuando el usuario lo pide. El disparo es manual por definición (no hay cron posible sin credenciales).
2. **El "export" no es un script puro de punta a punta.** El contenido es prosa larga, no filas tabulares, así que no hay un mapeo determinístico 1:1 Doc→JSON. Se partió en dos pasos: `src/doc_sync.py` (determinístico, testeado) hace el parsing *mecánico* del JSON de la Docs API — título por `HEADING_2`, categoría por pestaña (`TAB_CATEGORIAS`), `Fuente:`/`Última actualización:` por regex, listas de Ingredientes/Materiales/Paso a paso por los encabezados que el usuario ya usa de forma consistente — y escribe a `recipes_draft/` (gitignored), nunca a `recipes/` directamente. El merge final a `recipes/` lo hace Claude (o el usuario) a mano, porque esa es la parte no-determinística: decidir si una receta está lista para publicar, preservar `foto`/`porciones` curados a mano, fusionar contenido duplicado (ver "Migración de contenido" más abajo).

**Validación, igual que el playbook pide:** una receta sin `Ingredientes`/`Materiales` o sin `Paso a paso` no se inventa — `doc_sync.py` la reporta como incompleta (tab + título + motivo) y no escribe el archivo. La validación ERROR/WARNING existente de `export_data.py` sobre `recipes/*.md` no cambió.

**Limitaciones conocidas de `doc_sync.py` (aceptadas, no bloqueantes):** listas anidadas (sub-bullets dentro de un bullet, ej. "Carnes:" como subtítulo con hijos) se aplanan a un solo nivel; texto con viñetas tipeadas a mano (`•⁠` literal, no una lista real de Docs) no se reconoce como lista; pasos numerados con texto en negrita en vez de una lista ordenada real de Docs (ej. *Pastel de papa*) no se detectan. En todos esos casos la receta queda afuera del borrador automático y se completa a mano, nunca se inventa.

**Categoría nueva:** `jugos` se agregó a `CATEGORIAS` (`src/schema.py`) para la pestaña "Jugos naturales" — no encajaba en `almuerzo/cena/merienda/postre`.

**Migración de contenido — 21 recetas nuevas (Postres y Tartas, Meriendas, Jugos naturales), además de las 5 ya migradas:**
- Se migraron a mano (antes de que existiera `doc_sync.py`) leyendo el `.docx` + el Doc en vivo.
- **Sin foto de portada** para ninguna de las 21: el Doc no tiene una "foto de portada" identificable por receta (son fotos de pasos intermedios, sin curar) — mismo criterio que *Asado* en la migración anterior. Pendiente completar a mano.
- **Se excluyeron por estar incompletas en el Doc** (placeholder sin ingredientes/pasos, o solo un link sin receta escrita): *Budín de pan*, *Crema de chocolate*, las 4 variantes de "Cookies > Dulces" (Vainilla con membrillo, Limón, Nuez y coco, Chocolate), *Pancakes*, *Mermelada* (Manzana, Naranja). Quedan pendientes de completar en el Doc — `doc_sync.py` las va a seguir reportando como incompletas hasta que tengan Ingredientes + Paso a paso.
- *Apple crumble*: el Doc tenía el paso a paso duplicado (un "resumen ejecutivo" y una versión "con fotos", mismo contenido). Se conservó uno solo.
- Fechas ("Última actualización: 20 abr 2026") se parsean a ISO (`2026-04-20`) al migrar, igual que ya pedía el playbook para fechas puras.

**`docs/.nojekyll` obligatorio.** Sin ese archivo, GitHub Pages corre Jekyll sobre `docs/`: como `index.html` no tiene front matter YAML, Jekyll no lo reconoce como página y arma la home a partir del `README.md` de la raíz del repo (y no copia `style.css`/`app.js` tal cual, por eso daban 404). `.nojekyll` desactiva ese pipeline y sirve `docs/` como estático plano.

## 2026-10-13 — Fotos de portada: desde la fuente enlazada, no inventadas

**Problema:** de las 26 recetas, solo *Guiso con lentejas* tenía `foto` propia. El resto no tiene fotos curadas del plato terminado (ver migraciones anteriores arriba), pero sí tienen `fuente` (YouTube, blogs de recetas) con una imagen identificable del plato.

**Decisión:** nuevo script `src/fetch_covers.py` (no integrado al `Makefile`, se corre a mano cuando hace falta) que, para cada receta sin `foto`, intenta en orden: (1) miniatura de YouTube si `fuente` o el cuerpo linkean un video (`img.youtube.com/vi/<id>/maxresdefault.jpg`, con fallback a `sddefault`/`hqdefault` si el video no tiene esa resolución), (2) `og:image` de la página si `fuente` es un sitio web. Nunca genera ni elige una imagen no vinculada a la fuente real de la receta — si no hay fuente con imagen usable, la receta queda sin foto (warning existente de `export_data.py`, no error).

**Resultado:** 13 recetas nuevas con portada (YouTube: apple-crumble, budin-de-banana, budin-de-limon, lemon-pie, tarta-de-frutillas, torta-tofi, nutella-casera; `og:image`: budin-de-chocolate, budin-de-naranja, flan, mayonesa-de-zanahoria, mousse-de-limon, torta-de-nuez). *Torta de nuez*: el `og:image` del blog era una foto de la autora sosteniendo la torta — se reemplazó a mano por otra foto del mismo posteo (`DSC_0078-1`) que muestra la torta sola, mejor portada para una card. *Galletitas saladas* quedó sin foto: Instagram bloquea el scraping sin login. Las 10 recetas sin ningún link en `fuente` (asado quedó aparte, ver abajo; resto: budin-de-manzana, chocolinas, jugo-clasico, jugo-detox-digestivo, jugo-energetico, jugo-inmunologico, papas-al-horno, pastel-de-papa, tacos, turron-de-quaker) también quedan sin foto — no hay de dónde sacarla sin inventar.

**Asado — reemplaza la decisión del 2026-10-13 de arriba ("la card usa el placeholder hasta que haya una mejor").** El usuario pidió explícitamente usar una de las ~20 fotos de proceso del Google Doc (ninguna es "plato servido", son todas de armar el fuego/poner la carne). Se eligió a mano `kix.9mw08risqls1` (carne ya puesta en la parrilla con el fuego de fondo) por ser la más reconocible como "asado" de las disponibles — no hay ninguna del plato ya cortado/servido en el Doc. Las imágenes de Google Docs se leen vía `positionedObjects` del tab (no `inlineObjects` — Comidas Saladas las ancla como objetos posicionados, no inline) y se bajan de su `contentUri` temporal (`lh7-rt.googleusercontent.com`, firmada, no reusable después).

**Por qué no se integró al `Makefile`/CI:** es una acción puntual y manual (bajar archivos de fuentes externas requiere ver cada imagen antes de aceptarla — ver el caso de torta-de-nuez), no parte del rebuild determinístico de `export_data.py`. Si en el futuro hace falta re-correrlo (nuevas recetas sin foto), se invoca a mano: `.venv/bin/python -m src.fetch_covers`.

## 2026-10-13 — Emoji fijo por tipo de sección (Ingredientes, Paso a paso, etc.)

**Pedido del usuario:** que cada tipo de sección tenga siempre el mismo emoji ("ingredientes" con tal emoji, "paso a paso" con tal otro).

**Decisión:** el emoji se agrega en `docs/app.js` (`EMOJI_SECCIONES`), no en los `.md` de `recipes/`. Es una tabla de reglas `[regex sobre texto normalizado, emoji]` que se evalúa cuando se arma cada `<details>` de sección (`agruparSecciones`), antepuesto al `<h2>` antes de que el índice ("En esta receta") lo lea — así el emoji aparece también ahí. Mapeo actual: Ingredientes 🥕, Paso a paso 👩‍🍳, Materiales 🧰, "¿Dónde comprarlo?" 🛒, "¿Dónde NO comprarlo?" 🚫 (la regla de "NO" va primero para no perderla contra la de "comprarlo"). Encabezados que no matchean ninguna regla (ej. *Partes del lemon pie*) quedan sin emoji — no se fuerza uno arbitrario en un título puntual de una sola receta.

**Por qué en el render y no en los `.md`:** hacerlo a mano en cada archivo es frágil (25+ recetas, variantes como "Ingredientes (versión a probar, más rica)") y el Doc en vivo sigue siendo la fuente — si se migra contenido nuevo desde ahí, el emoji se aplicaría solo si alguien se acuerda de agregarlo a mano. Centralizarlo en una tabla del render lo hace automático y consistente para toda receta presente y futura, sin tocar la fuente de contenido. No pisa los emojis que el usuario ya puso a mano en pasos individuales (`### 🔥 P1) ...` en *Asado*): esos son `<h3>`, la regla nueva solo mira `<h2>`.
