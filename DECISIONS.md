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

## 2026-10-13 — Extraer las fotos que ya están embebidas en el Doc

**Problema:** `fetch_covers.py` solo cubre recetas con un link externo (`fuente`) a YouTube o a una página con `og:image`. La mayoría de las recetas no tiene ese link — tiene fotos propias, sacadas por el usuario con el celular e insertadas directo en el texto del Doc. Esas fotos no se podían usar en el sitio sin que el usuario las subiera a mano una por una.

**Decisión:** nuevo script `src/extract_doc_images.py` que baja esas fotos directamente del JSON de la Docs API (mismo `doc_json` que ya usa `doc_sync.py`, el mismo `read_doc`). Dos formas de anclaje encontradas en el doc real, resueltas ambas vía `contentUri` (URL firmada de Google, vence en minutos — por eso parseo y descarga van en la misma corrida):
- `inlineObjectElement` (fotos "en línea" dentro de un párrafo) → `documentTab["inlineObjects"]`.
- `positionedObjectIds` (fotos "flotantes", frecuentes cuando se pegan desde el celular) → `documentTab["positionedObjects"]`.

Ambos diccionarios viven adentro de cada `documentTab`, no en la raíz del JSON (la hipótesis inicial asumía la raíz). La pestaña "Comidas Saladas" no tenía ningún `inlineObjects` pero sí 22 `positionedObjects` — si el script solo hubiera mirado el primer tipo, se habrían perdido todas esas fotos en silencio.

El script agrupa las fotos por receta reusando el mismo criterio que `_agrupar_recetas` (todo lo que cuelga de un `HEADING_2` hasta el próximo) y las baja **todas, numeradas**, a `images/<slug>/doc-NN.jpg` — nunca pisa un `cover.jpg` ya curado, y nunca elige automáticamente cuál es "la" foto de portada: esa curación visual la hace un humano/Claude después (ver Arquetipo C del `DATA_FLOW_PLAYBOOK_unificado.md`, mismo principio que la imagen derivada de un link externo).

**Primera corrida (2026-10-13):** 73 fotos bajadas, 12 recetas con al menos una. 4 títulos del Doc no matchearon ningún slug de `recipes/*.md` tal cual (p. ej. `"🍋Limón"` en vez de `budin-de-limon`, porque esos sabores son `HEADING_2` hijos de un `HEADING_1` agrupador como "Budines" que no abre receta nueva) — se reconciliaron a mano moviendo las fotos a la carpeta correcta; una (`"Dulces"`, 1 foto) quedó sin reconciliar porque corresponde a una de las variantes de cookies que el Doc todavía tiene incompletas (sin Ingredientes/Paso a paso) y por lo tanto no tiene receta publicada en `recipes/`.

**Pendiente:** elegir a mano, de las fotos bajadas en `images/<slug>/doc-NN.jpg`, cuál va en el frontmatter `foto` de cada receta que todavía no tiene portada.

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

## 2026-10-13 — Las últimas 11 fotos: fotos del Doc ya extraídas + búsqueda web genérica

**Problema:** después de `fetch_covers.py` (fuente enlazada) y `extract_doc_images.py` (fotos embebidas en el Doc), quedaban 11 recetas sin `foto`: 2 con fotos del Doc ya bajadas pero sin curar (`budin-de-manzana`, `turron-de-quaker`, ver corrida de `extract_doc_images.py` arriba) y 9 sin ninguna imagen propia disponible por ningún método anterior (`chocolinas`, `galletitas-saladas`, los 4 `jugo-*`, `papas-al-horno`, `pastel-de-papa`, `tacos`). El usuario pidió explícitamente "buscá imágenes donde sea" para estas últimas.

**Decisión — las 2 con foto del Doc:** se revisaron a mano los `doc-NN.jpg` ya bajados y se eligió la mejor como `cover.jpg` (mismo criterio manual que *Asado*, sin script nuevo): *Budín de manzana* → `doc-01.jpg` (el budín horneado entero, dorado, recién salido del horno — las otras 6 fotos eran la fuente vacía o las manzanas crudas sin hornear). *Turrón de quaker* → `doc-01.jpg` (única foto disponible: el postre a medio armar, capas de galletitas y mezcla de cacao en la fuente de vidrio — no hay foto del postre terminado/cortado en el Doc, pero es identificable).

**Decisión — las 9 sin ninguna fuente propia:** cuando ni el Doc ni un link propio tienen una imagen, se usa una foto genérica de internet que representa el plato (no la receta específica del usuario, una foto de stock/blog de ese tipo de comida) — es la opción menos mala frente a dejarlas con el emoji placeholder, mientras quede claro que no es "la" foto de la receta real. Método: búsqueda de imágenes en Bing (Google Images pide CAPTCHA a tráfico automatizado — no se intenta resolver, ver regla de seguridad), clic en el resultado visualmente correcto para abrir el panel de detalle, extracción de la URL real de la imagen con `decodeURIComponent(location.href).match(/mediaurl=([^&]+)/)[1]` (evita servir el thumbnail recortado/letterboxed de `th.bing.com`), descarga directa de esa URL. Revisión visual de cada imagen antes de aceptarla (mismo principio que `torta-de-nuez` en la decisión anterior) — en ningún caso se aceptó el primer resultado sin mirarlo.

**Búsquedas usadas (texto exacto, elegido a partir de los ingredientes/pasos de cada receta, no del título solo):** `torta chocolinas dulce de leche`, `galletitas de harina de lino y avena saladas caseras`, `jugo de naranja y zanahoria casero vaso`, `jugo detox apio pepino manzana verde menta vaso`, `jugo de zanahoria manzana verde y jengibre vaso`, `jugo de naranja ananá y limón antioxidante vaso`, `papas al horno doradas fuente`, `pastel de papa con carne casero fuente`, `tacos caseros tortilla integral con carne`.

**No se integra a ningún script.** Es manual y puntual por naturaleza (cada imagen se elige con criterio visual humano, no hay regla determinística "buscar X para la receta Y"); si se agregan recetas nuevas sin fuente propia en el futuro, se repite el proceso a mano.

## 2026-10-13 — Consolidar el orden de prioridad de fotos como playbook del repo

**Pedido del usuario:** las 4 decisiones de arriba sobre `foto` quedaron como narrativa cronológica, no como un procedimiento claro para la próxima vez que falte una foto.

**Decisión:** el orden de prioridad (1. `cover.jpg` ya curada → 2. fotos embebidas en el Doc → 3. derivarla de `fuente` enlazada → 4. búsqueda genérica en Bing como último recurso → 5. queda sin foto, nunca se inventa) se escribió como procedimiento en `README.md` ("Cómo conseguir la foto de portada"), que es el playbook operativo de este repo — las entradas de arriba quedan como el registro histórico de por qué se llegó a ese orden. Mismo patrón propuesto en `DATA_FLOW_PLAYBOOK_unificado.md` (sección Arquetipo C) para que aplique a cualquier proyecto futuro con el mismo problema (campo de imagen curado faltante, pero la entidad tiene más de una fuente posible de la cual derivarlo).

## 2026-10-13 — Recategorización (almuerzo-solo, acompañante, bebidas) y navbar de categorías

**Problema:** el esquema de categorías original (`almuerzo`, `cena`, `merienda`, `postre`, `jugos`) no distinguía bien tres casos reales: *Guiso con lentejas* y *Asado* son platos de mediodía únicamente (no se comen de cena en esta casa); *Papas al horno* nunca es un plato principal, es un acompañante; y "bebidas" iba a crecer más allá de jugos (el usuario planea agregar tragos). Además, la UI de filtros (chips multi-select dentro de un panel colapsable) escondía la categoría como un filtro más, cuando en los hechos es la forma principal en que se navega el sitio.

**Decisión — categorías:** `jugos` se reemplaza por `bebidas` en `src/schema.py` (`CATEGORIAS`), y se agrega `acompañante`. Se agrega un campo opcional nuevo, `tipo_bebida` (`src/schema.py: TIPOS_BEBIDA = {"jugos", "tragos"}`), que **solo tiene sentido si `categorias` incluye `bebidas`**: `export_data.py` lo valida igual que `dificultad` (ERROR si el valor no está en el enum), pero el WARNING por "sin dato" solo se dispara cuando la receta ya es de categoría `bebidas` — no en todas las recetas, a diferencia de `dificultad`. `src/doc_sync.py` deriva el default de `tipo_bebida` igual que ya hacía con `categorias` por pestaña: la pestaña "Jugos naturales" del Doc sigue mapeando directo a `categorias: ["bebidas"]` + `tipo_bebida: "jugos"` (`TAB_TIPO_BEBIDA`), sin que el usuario tenga que completarlo a mano para recetas nuevas.

**Ajustes puntuales de datos** (`recipes/*.md`): *Asado* y *Guiso con lentejas* pasan de `["almuerzo", "cena"]` a `["almuerzo"]`. *Papas al horno* pasa de `["almuerzo", "cena"]` a `["acompañante"]` exclusivo (no queda también en almuerzo/cena). *Pastel de papa* y *Tacos* no se tocaron — siguen en `["almuerzo", "cena"]`, el usuario no los mencionó como excepción. Las 4 recetas de `jugo-*` pasan de `categorias: ["jugos"]` a `categorias: ["bebidas"]` + `tipo_bebida: "jugos"`.

**Decisión — navegación:** la categoría deja de ser un filtro más (chip multi-select dentro del panel "Filtros") y pasa a ser la navegación primaria del sitio: un navbar de pills (`Todas` + las 6 categorías) arriba de la grilla, selección única (no combinable entre sí — una receta con varias categorías simplemente aparece en cada pestaña que le corresponda). Con 6 categorías (más de las 2–4 de un segmented control), se usa el patrón ya documentado en `DESIGN_PLAYBOOK_unificado.md` §6 ("Varias páginas → pills con scroll horizontal, nunca wrap a 2 líneas"), no tab bar fija abajo — con 6 ítems no entran cómodos en un ancho de 375px como tabs de igual ancho, pero sí como pills que scrollean. `tipo_bebida` se muestra como filtro secundario (mismo lugar que `dificultad`) solo cuando la pestaña activa es `Bebidas` y hay valores presentes — progressive disclosure, no aparece en el resto de las categorías. "Limpiar filtros" ahora solo limpia los filtros secundarios (`dificultad`, `tipo_bebida`), no la pestaña activa — la pestaña es navegación, no algo que se "limpia".

**No se hizo sticky.** El navbar nuevo no es `position: sticky` — ya hay un header sticky arriba, y sumar una segunda barra fija exige sacarle el sticky al header (regla del playbook de diseño §10) o convivir con dos barras fijas, ninguna de las dos pedida acá. Si se quiere en el futuro, tratarlo como un cambio aparte.

**Bug encontrado al implementar:** el atributo HTML `hidden` en un elemento con clase `.filtro-grupo` no lo ocultaba, porque `.filtro-grupo { display: flex }` (origen *author*, en `style.css`) le gana en cascada a la regla `[hidden] { display: none }` del user-agent, sin importar el orden o la especificidad del selector — un origen de hoja de estilos de mayor prioridad siempre gana sobre uno de menor prioridad en declaraciones normales. Se agregó `.filtro-grupo[hidden] { display: none; }` explícito. Ver el nuevo apunte en `DATA_FLOW_PLAYBOOK_unificado.md`/`DESIGN_PLAYBOOK_unificado.md` sobre este patrón general (atributo `hidden` + una clase con `display` propio).

## 2026-10-13 — Un solo eje de clasificación: "qué es", no "cuándo se come"

**Problema:** la recategorización de arriba (misma fecha) dejó `CATEGORIAS` como una lista plana de 6 valores, pero mezclaba dos ejes distintos sin un criterio consistente — `almuerzo`/`cena`/`merienda` clasifican por **cuándo se come**, mientras que `postre`/`bebidas`/`acompañante` clasifican por **qué es el plato**. En la práctica ninguna receta combinaba ambos ejes (nadie tenía `["almuerzo", "postre"]`), pero la mezcla conceptual generaba inconsistencias arbitrarias — un budín es "merienda" pero un flan es "postre", aunque los dos podrían comerse en cualquier momento — y esa fue la "doble clasificación" que le hacía ruido al usuario al navegar el sitio.

**Decisión:** `CATEGORIAS` pasa a tener un solo eje, por tipo de plato: `principal`, `acompañante`, `postre`, `merienda`, `bebidas`. `almuerzo` y `cena` se fusionan en `principal` — es el criterio que ya usaban de hecho `postre`/`bebidas`/`acompañante`, y responde mejor a "qué puedo cocinar" que a "qué hora es". La excepción puntual de *Asado* y *Guiso con lentejas* (se comen solo al mediodía, no de cena) deja de ser una categoría separada y pasa a ser una nota en el cuerpo de la receta (`> 🕐 Se come solo al mediodía, nunca de cena.`), justo debajo del frontmatter — se preserva el dato sin forzarlo de vuelta a un eje temporal en el modelo de datos.

**Alcance del cambio:** `src/schema.py` (`CATEGORIAS`), `src/doc_sync.py` (`TAB_CATEGORIAS["Comidas Saladas"]` → `["principal"]`), `docs/app.js` (`CATEGORIA_ORDEN`), `README.md`, y `recipes/*.md` de las 4 recetas afectadas (`asado`, `guiso-con-lentejas`, `pastel-de-papa`, `tacos`). Los fixtures de test que usaban `"almuerzo"` como valor de ejemplo (no relacionados con el eje tiempo/tipo) se actualizaron a `"principal"` para seguir siendo válidos contra el schema nuevo.

**Lección generalizable:** al diseñar un campo de categorización con valores "a ojo", chequear que todos los valores respondan a la misma pregunta (un solo eje) — mezclar "cuándo" y "qué es" (o cualquier par de ejes ortogonales) en un enum produce una taxonomía que parece simple pero no lo es, porque cada valor nuevo exige decidir primero a qué eje pertenece. Una excepción real de un eje descartado (ej. "esto solo se come a tal hora") se documenta como dato/nota sobre la entidad, no se vuelve a colar como categoría. Agregado a `DATA_FLOW_PLAYBOOK_unificado.md` (Arquetipo C) y `DESIGN_PLAYBOOK_unificado.md`.

## 2026-10-13 — Generalizar el sub-filtro condicionado a más categorías (momento, tipo de merienda)

**Problema:** la fusión de arriba (misma fecha) dejó `merienda` sin forma de distinguir las 2 recetas saladas (`galletitas-saladas`, `mayonesa-de-zanahoria`) de las 6 dulces, y la nota de texto `> 🕐 Se come solo al mediodía` en *Asado*/*Guiso con lentejas* no era filtrable ni consistente con cómo ya se resolvía el mismo problema en `bebidas` (`tipo_bebida`, condicionado a la categoría — ver §12.5 de `DATA_FLOW_PLAYBOOK_unificado.md`).

**Decisión:** generalizar el patrón de `tipo_bebida` a 3 sub-filtros, todos condicionados a una categoría de `CATEGORIAS` y ocultos fuera de su pestaña (progressive disclosure, igual que antes):
- `bebidas` → `tipo_bebida`: `jugos`/`tragos` (sin cambios).
- `merienda` → `tipo_merienda`: `dulce`/`salado`.
- `principal` → `momento`: `mediodía`/`cena`.

`src/schema.py` pasa a tener `SUBFILTROS: dict[categoria, SubFiltro(campo, valores, avisar_si_falta)]` en vez de la constante `TIPOS_BEBIDA` suelta. `avisar_si_falta` distingue dos semánticas distintas que antes solo existían para un caso: `tipo_bebida`/`tipo_merienda` clasifican a **toda** receta de esa categoría (como `dificultad`) → `False` en dato faltante es WARNING; `momento` es una **excepción puntual** (la mayoría de los platos principales no tienen horario fijo) → su ausencia es el caso normal, nunca WARNING. `export_data.py` (`normalizar`/`validar`/`construir_json`) y `docs/app.js` (`SUBFILTROS`, `renderGrupoSubfiltro`, `valoresSubfiltro`) se generalizaron para iterar sobre esta tabla en vez de tener 3 bloques casi idénticos copiados — con 3 instancias del mismo patrón, la abstracción ya paga su costo (regla de 3).

**No se le cambió el nombre a "Merienda".** Se evaluó buscarle un nombre de "qué es" (como las demás categorías), pero ninguna palabra única cubre bien 6 recetas dulces + 2 saladas sin forzarlo. Con el sub-filtro `tipo_merienda` adentro, "Merienda" deja de depender de esa palabra única — funciona como género de comida (budines, tortas caseras, algo salado para acompañar) con una excepción interna ya resuelta por el sub-filtro, igual que "Bebidas" no necesitó renombrarse para distinguir jugos de tragos.

**Dato reestructurado:** *Asado* y *Guiso con lentejas* pierden la nota de texto `> 🕐 ...` (quedaba sin filtrar ni mostrarse como badge) y ganan `momento: "mediodía"` en el frontmatter — mismo dato, ahora estructurado, filtrable y visible como chip en la card/detalle (igual que ya pasaba con `tipo_bebida`). Las 8 recetas de `merienda` ganan `tipo_merienda` (`dulce`: los 5 budines + nutella casera; `salado`: galletitas saladas, mayonesa de zanahoria).

**Lección generalizable:** ya estaba anotada en la entrada de arriba y en `DATA_FLOW_PLAYBOOK_unificado.md` §12.6 — acá es la segunda aplicación concreta (merienda, además de principal) del mismo principio: una excepción real de un eje descartado de la categoría primaria se preserva como campo/sub-filtro condicionado, no como categoría nueva ni como nota de texto suelta sin estructura.

## 2026-10-13 — Primeras 2 recetas con `momento: "cena"`: Empanadas y Tarta de espinaca

**Contexto:** el sub-filtro `momento` (entrada de arriba) quedó con el valor `cena` sin ninguna receta real detrás — las únicas 4 recetas `principal` con `momento` (Asado, Guiso con lentejas, Pastel de papa, Tacos) son `mediodía`. El usuario agregó dos nombres nuevos al Google Doc (pestaña "Principales", antes "Comidas Saladas" — ver nota de renombre de pestañas más abajo) — *Empanadas* y *Tarta de espinaca* — y pidió crearlas en el sitio **vacías, solo con foto**, aclarando que van en `cena`.

**Decisión:** se crearon `recipes/empanadas.md` y `recipes/tarta-de-espinaca.md` como placeholders deliberados — rompe la regla histórica de este repo ("una receta sin Ingredientes/Paso a paso no se migra", ver entrada "Google Doc como fuente"), pero acá es un pedido explícito del usuario, no una decisión de Claude. El cuerpo no puede quedar literalmente vacío (`export_data.py` lo rechaza con ERROR), así que lleva una nota `> ℹ️ Receta pendiente de completar — el Google Doc todavía no tiene ingredientes ni paso a paso.` en vez de contenido inventado. `categorias: ["principal"]`, `momento: "cena"`.

**Fotos:** el Doc no tiene nada bajo esos dos títulos (ni texto ni imágenes embebidas, solo el heading vacío) y no hay `fuente` para derivar una miniatura — se fue directo al último recurso del playbook (`README.md`, "Cómo conseguir la foto de portada", paso 4: búsqueda genérica en Bing Images, con revisión visual antes de aceptar). Búsquedas: `empanadas argentinas horno doradas fuente` → `images/empanadas/cover.jpg` (empanadas criollas clásicas, repulgue a la vista, una cortada mostrando relleno de carne/aceituna/huevo). `tarta de espinaca casera fuente porcion` → `images/tarta-de-espinaca/cover.webp` (gratinada, porción cortada mostrando el relleno).

**Nota — el Google Doc renombró sus pestañas, `doc_sync.py` quedó desactualizado:** al leer el Doc para esto se vio que las 5 pestañas pasaron de `Comidas Saladas/Postres y Tartas/Meriendas/Jugos naturales/Template receta` a `Principales/Postres y Tartas/Meriendas/Bebidas/Acompañantes/Template receta` — el usuario reorganizó el Doc para que calce con las categorías nuevas del sitio (`CATEGORIAS`), y "Bebidas" ahora mezcla jugos con al menos un trago (`Daiquiri`). **No se tocó `src/doc_sync.py`** (`TAB_CATEGORIAS`/`TAB_TIPO_BEBIDA` siguen con los nombres de pestaña viejos) porque no era parte de este pedido — si se corre `doc_sync` tal cual hoy, todas las pestañas van a salir como "desconocidas". Queda pendiente actualizarlo la próxima vez que se sincronice el Doc completo (y decidir qué hacer con el default de `tipo_bebida` ahora que "Bebidas" ya no es 100% jugos).

## 2026-10-13 — Detectar qué recetas cambiaron en el Doc desde el último sync (`doc_hash`)

**Problema:** cada sync requería releer las ~35 recetas del Doc a ojo para notar cuáles se habían tocado de verdad — con el Doc reorganizado seguido (pestañas, categorías) era fácil pasar por alto una edición real o, al revés, revisar a mano recetas que no habían cambiado.

**Decisión:** `src/doc_sync.py` ahora calcula un hash determinístico del contenido parseado de cada receta (`contenido_hash`: título, categorías, tipo_bebida, fuente, fecha, materiales, ingredientes, paso a paso y cuerpo libre — nunca el JSON crudo, que trae metadata volátil sin relación con el contenido) y lo guarda como `doc_hash` en el frontmatter del borrador. `detectar_cambios` compara ese hash contra el que ya está guardado en `recipes/<slug>.md` (si lo tiene) y clasifica cada receta leída del Doc en **nueva** (no existe el archivo todavía), **cambiada** (existe pero el hash no coincide o nunca tuvo `doc_hash`) o **sin cambios** (mismo hash) — `run_sync` imprime ese resumen antes de la lista de incompletas.

**Por qué el hash vive en `recipes/<slug>.md` y no en un archivo de estado separado:** así queda versionado junto con el contenido que representa (coherente con "un único punto de verdad", playbook de datos) — no hay un segundo archivo para mantener sincronizado a mano, y sobrevive a clonar el repo en otra máquina. El costo: el merge a mano tiene que copiar el `doc_hash` del borrador al archivo final (documentado en `README.md`), si no la receta va a aparecer como "cambiada" de nuevo en el próximo sync sin haber cambiado.

**Costo aceptado:** la primera corrida después de este cambio va a marcar como "cambiadas" todas las recetas que todavía no tienen `doc_hash` en su frontmatter (es decir, todas las migradas antes de hoy) — es el baseline inicial, se resuelve solo la primera vez que se corra un sync completo y se copien los hashes.

**Campo nuevo en el schema:** `doc_hash` se agregó a `OPTIONAL_FIELDS` (`src/schema.py`) para que `export_data.py` no lo marque como "clave de frontmatter desconocida". No se expone en `docs/recetas.json` — es bookkeeping interno del sync, no un dato para mostrar en el sitio.

**Generalizable:** ver `DATA_FLOW_PLAYBOOK_unificado.md`, Arquetipo C — se agregó esto como patrón reusable para detectar cambios reales en una fuente de prosa larga sin backend propio.

## 2026-10-14 — Toda receta debe tener una sección `## Ingredientes`

**Problema:** *Lemon pie* tiene 3 sub-recetas (masa sablée, curd de limón, merengue italiano) y en vez de una sección `## Ingredientes` como el resto de las recetas con partes (ver *Tarta de frutillas*, que sí tiene `## Ingredientes` con un `###` por parte), los ingredientes de cada parte estaban como una línea de texto suelta ("Ingredientes: harina 0000 200 g, ...") al principio de cada subsección de `## Paso a paso`. El resultado: el índice de la receta ("En esta receta") no mostraba nunca un ítem "Ingredientes", a diferencia de las demás.

**Decisión:** toda receta real (no los stubs "pendiente de completar" como *Empanadas*/*Tarta de espinaca*, que no tienen ninguna sección todavía) tiene que tener un `## Ingredientes` de nivel 2, aunque tenga varias partes — en ese caso, igual que en `## Paso a paso`, se usa un `### <nombre de la parte>` por cada una, con la misma lista de ingredientes en formato `- Item — cantidad`. Se corrigió *Lemon pie* siguiendo este patrón (`recipes/lemon-pie.md`) y se sacó el texto de ingredientes suelto de cada paso.

**Por qué:** consistencia con el resto de las recetas multi-parte y con cómo arma el índice `docs/app.js` (`crearIndice`): una receta sin `## Ingredientes` pierde ese ítem del índice sin que se note a simple vista, ya que el resto del contenido se ve igual de completo.

## 2026-10-14 — Estructura fija de secciones de una receta, con galería de imágenes del proceso en Paso a paso

**Pedido del usuario:** fijar el orden y el set de secciones que toda receta debe tener, en vez de que varíe página a página.

**Decisión:** toda receta sigue este orden: Índice (automático) → `## Materiales` (opcional) → `## Ingredientes` (obligatorio, ya era regla desde la entrada anterior) → `## Paso a paso` (obligatorio). Se agrega una subsección nueva dentro de Paso a paso, `### Imágenes del paso a paso`, con **todas** las fotos del proceso que estén en el Google Doc para esa receta — las mismas que ya baja `src/extract_doc_images.py` a `images/<slug>/doc-NN.jpg`, no solo la portada curada a mano (`foto`/`cover.jpg`). Documentado como procedimiento en `README.md` ("Formato de `recipes/<slug>.md`"), igual que ya se hizo con el orden de prioridad de fotos de portada.

**Pendiente de implementar:** por ahora es la convención a seguir hacia adelante, no hay código nuevo todavía. Falta decidir, cuando se aplique a la primera receta real: (a) cómo referenciar esas imágenes en el Markdown (ruta directa a `doc-NN.jpg` o copiarlas/renombrarlas primero), (b) si `docs/app.js` debe renderizar esa subsección distinto de un `### <subgrupo>` normal (galería en grid vs. lista de imágenes sueltas), y (c) si `export_data.py` necesita validar algo sobre ella. No es generalizable a otros proyectos (es específico del formato de receta de este repo), así que no se propone en los playbooks unificados de `utils/`.

## 2026-10-14 — Sub-recetas compartidas (`recipes/utils/`), vía include en vez de copiar el contenido

**Problema:** *Lemon pie* y *Tarta de frutillas* tienen cada una su propia "Masa sablée" completa (ingredientes + paso a paso) copiada a mano — mismo video fuente, texto reformulado de forma independiente al migrarlas del Doc. Dos copias significan que corregir la técnica (o la cantidad de harina, ver abajo) hay que acordarse de tocarlo en los dos archivos; con *Crema pastelera* a punto de reaparecer en más tartas, el problema iba a crecer.

**Decisión:** nuevo directorio `recipes/utils/` con un `.md` por fragmento reusable (`masa-sablee.md`, `crema-pastelera.md`), sin frontmatter, con las mismas secciones `## Ingredientes`/`## Paso a paso` que tendría una receta. `export_data.py` (`cargar_utils`, `resolver_includes`) reemplaza un comentario `<!-- incluir: <fragmento>#ingredientes -->` (o `#paso-a-paso`) en el cuerpo de cualquier `recipes/<receta>.md` por el contenido de esa sección, antes de renderizar — el `###` de la subsección lo sigue escribiendo cada receta (así cada una conserva su propio título/orden), el fragmento solo aporta el contenido. `recipes_dir.glob("*.md")` (no recursivo) ya no incluía `recipes/utils/*.md` como recetas sueltas, así que no hizo falta cambiar ese loader.

**Es ERROR, no WARNING, si el include no resuelve** (fragmento o sección inexistente): mismo criterio que cualquier otro dato roto en `recipes/` (ver `validar()`) — nunca se publica un comentario sin reemplazar ni un pedazo de receta en blanco.

**Cantidad de harina — discrepancia real entre las dos copias:** *Lemon pie* usaba 200 g de harina y *Tarta de frutillas* 250 g, mismo resto de ingredientes (70 g manteca, 70 g azúcar, 1 huevo) y mismo video fuente — señal de que era una divergencia de transcripción, no una variación intencional por tamaño de tartera. Consultado con el usuario: se usan 200 g (el valor de *Lemon pie*) como cantidad única del fragmento compartido; si *Tarta de frutillas* necesita más masa por ser una tartera de 30 cm, ya tenía su propia nota de variante (`> ℹ️ Variante que también funcionó: 300 g harina...`) que cubre ese caso sin reintroducir una segunda copia del dato base.

**Cuándo crear un fragmento nuevo:** solo cuando una sub-receta completa (no una mención de pasada, como el "variante: crema pastelera de limón" de *Lemon pie*, que sigue siendo texto suelto) se repite en una segunda receta real — documentado en `recipes/utils/README.md`, que es el lugar a actualizar si esta regla cambia.

**Generalizable:** el patrón (contenido reusable en archivos fuente de prosa larga, resuelto con un include mecánico que falla fuerte si la referencia está rota) se propone en `DATA_FLOW_PLAYBOOK_unificado.md`, Arquetipo C, para cualquier proyecto futuro con el mismo problema de sub-contenido repetido entre entradas.
