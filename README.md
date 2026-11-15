# Recetas

Sitio estático de recetas familiares: cards con foto, tiempo y dificultad, filtrables por categoría y ordenables por tiempo.

## Comandos

```bash
make setup                    # crea el venv e instala dependencias (una sola vez)
make serve                    # sirve el sitio en http://localhost:8778
make test                     # corre los tests
make integrate                # 02: integra el Doc (fuente A) y lo curado (fuente B) en un solo conjunto
make update                   # integrate + 05: regenera docs/data/ (recetas.json y data.js)
make collect DOC=<doc.json>   # 01: reduce el JSON de read_doc a data/01_data_understanding/doc/recetas.jsonl
make sync                     # 02: genera borradores del Doc en data/02_data_preparation/drafts/ (para inspeccionar)
make status                   # (bitácora: 01_data_understanding/refresh_log.md) hace cuánto se trajo cada fuente por última vez (avisa si el Doc lleva >14 días)
make log SOURCE="Curado" NOTE="qué se hizo"   # anota a mano una actualización (el Doc se anota solo)
make clean                    # borra el venv y lo generado
```

## Estructura

Sigue `REPO_STRUCTURE_PLAYBOOK.md` §6 (una carpeta por fase CRISP-DM, el dato aparte en `data/`). El sitio se publica desde `docs/` (ya estaba publicado así; ver `DECISIONS.md`).

```
recetas/
├── 00_business_understanding/   # objetivo del proyecto (README.md)
├── 01_data_understanding/       # recolectar el Google Doc crudo, fotos y portadas · refresh_log.md (bitácora)
│   └── collect_initial_data/{doc,covers}/
├── 02_data_preparation/         # format_data.py (Doc -> borradores) · integrate_data.py (A + B -> un conjunto)
├── 03_modeling/                 # no aplica (README.md explica por qué)
├── 04_evaluation/               # no aplica
├── 05_deployment/               # generate_site.py: valida y genera docs/data/
├── common/                      # config.py (todos los paths), schema.py, gdoc.py
├── data/
│   ├── 01_data_understanding/   # fuente A: doc/recetas.jsonl (el Doc tal cual)
│   │                            # fuente B: curated/*.md (a mano) · curated/utils/ · images/
│   └── 02_data_preparation/     # integrated/ y drafts/ (derivados, gitignored)
├── docs/                        # TODO lo que se sirve: index.html, css/, js/, data/, images/
├── tests/
├── Makefile · README.md · DECISIONS.md
```

Los scripts se corren por ruta (las carpetas con número no son paquetes importables) y cada uno arma su `sys.path` hacia `common/`. Una fase solo importa de fases anteriores o de `common/`.

## Fuente de los datos: el Google Doc

Las recetas se editan en un Google Doc, en una sola pestaña ("Recetas") con jerarquía de headers: `H1` = categoría (ej. "Principales"), `H2` = subcategoría opcional (ej. "Almuerzo"/"Cena" — algunas categorías no la tienen, ej. "Acompañantes"), `H3` = receta, `H4` = sección (Materiales/Ingredientes/Paso a paso), `H5` = sub-parte cuando una receta tiene varias (ej. *Lemon pie*: masa sablée, curd de limón...). Ese Doc es la fuente de verdad — **no se edita `recipes/*.md` a mano para contenido nuevo.**

**Dos fuentes de datos** (ver `DECISIONS.md`, "Dos fuentes"):

- **A · el Google Doc**, que se edita a mano y se guarda tal cual en `data/01_data_understanding/doc/recetas.jsonl`.
- **B · lo curado a mano** en `data/01_data_understanding/curated/*.md` (más `images/`): lo que el Doc no tiene (`foto`, `porciones`, `dificultad`, `tiempo`) y la prosa pulida. Es una fuente editable, no un derivado.

`make integrate` las une por receta: una receta **nueva del Doc entra sola**; si existe en las dos gana la curada (se avisa si el Doc cambió desde la última curación); una receta solo curada se conserva. El resultado (`data/02_data_preparation/integrated/`) es derivado, no se edita.

**Para sincronizar después de editar el Doc** (pedirle a Claude Code, en una sesión con el conector de Google Docs):

1. Claude lee el Doc con `read_doc`, guarda el JSON y corre `make collect DOC=<doc.json>`, que además **anota la fecha en `01_data_understanding/refresh_log.md`** (cuándo se trajo y si cambió); `make status` dice hace cuánto fue. Después **`git diff data/01_data_understanding/doc/recetas.jsonl` muestra exactamente qué cambió en el Doc.**
2. `make integrate` (o `make update`, que además regenera el sitio) imprime qué entró nuevo, qué curadas hay que revisar y qué recetas del Doc están incompletas (sin ingredientes o sin paso a paso: no se publican, no se inventa contenido).
3. Para las "a revisar": mirar el diff del raw y, si hay contenido nuevo de verdad, pasarlo a su `.md` curado y **copiar el `doc_hash` del borrador** (`make sync` deja los borradores en `data/02_data_preparation/drafts/`) para que no vuelva a avisar.
4. `make test`, revisar en el navegador (`make serve`) y commitear.

**Link al Doc:** cada receta tiene `doc_url`, un link directo a su título en la **vista simplificada** del Google Doc (`.../mobilebasic?tab=...#h.xxxx`, no el editor: ver `DECISIONS.md`), y el detalle muestra el botón "Abrir en Google Docs". Lo pone `integrate_data.py` desde el raw (que guarda el id de cada título); no se escribe a mano en los `.md` curados. Ojo: el Doc tiene que estar compartido con quien lo abra, si no Google le pide acceso. **En el celular con la app de Google Docs el link abre el Doc desde arriba** (la app ignora el ancla de la receta); en una computadora sí llega exacto. Está decidido dejarlo así: ver `DECISIONS.md`.

**Por ahora la actualización es manual** (le pedís a Claude "traé los datos del Google Doc"); cada vez queda una fila en [`01_data_understanding/refresh_log.md`](01_data_understanding/refresh_log.md) con la fecha, cuántas recetas hay y cuáles son nuevas. Automatizarla con un cronjob está evaluado y documentado, no implementado: [`01_data_understanding/automatizar_actualizacion.md`](01_data_understanding/automatizar_actualizacion.md).

Si el título de una receta en el Doc es más corto que el curado (el Doc la agrupa bajo un H2, ej. "Banana" dentro de "Budines"), se declara en `data/01_data_understanding/curated/doc_aliases.yml`.

Ver `DECISIONS.md` (entrada "Google Doc como fuente, no Markdown a mano") para el porqué.

## Formato de `data/01_data_understanding/curated/<slug>.md`

1. Frontmatter obligatorio: `titulo` y `categorias` (lista). El valor es el texto del `H1` del Doc tal cual (ej. `principales`, `postres`, `meriendas`, `bebidas`, `acompañantes`) — no hay enum cerrado en `common/schema.py`, cualquier valor no vacío es válido. Clasifican por **qué es el plato**, no por cuándo se come. Una receta puede tener varias (poco común) y aparece en cada pestaña del sitio que le corresponda.
2. Frontmatter opcional: `dificultad` (`baja`/`media`/`alta`), `tiempo_minutos`, `tiempo_minutos_max` (para rangos), `porciones`, `foto`, `fecha_actualizacion`, `fuente`, `doc_hash` (interno — lo escribe `doc_sync.py`, no se edita a mano, ver sección anterior), y el campo de subcategoría de la categoría correspondiente (nombre fijo en `common/schema.py: CAMPO_SUBCATEGORIA`, valor libre — el texto del `H2` del Doc): `tipo_bebida` (ej. `tragos`, `jugos naturales`, solo si `categorias` incluye `bebidas`), `tipo_merienda` (ej. `🍰 budines`, `🍪 cookies`, `🍯 untables`, `otros`, solo si incluye `meriendas`), `tipo_postre` (ej. `frutal`, `🥚 huevo`, `🍫 chocolatoso`, `ddl`, solo si incluye `postres`), `momento` (`almuerzo`/`cena`, solo si incluye `principales`). El sync mecánico siempre lo completa cuando el Doc tiene `H2` para esa categoría — su ausencia en una receta ya sincronizada es un dato faltante (WARNING), no el caso normal. `acompañantes` no tiene `H2` en el Doc, así que no tiene campo de subcategoría.
3. Si hay foto, ponerla en `data/01_data_understanding/images/<slug>/<archivo>` (normalmente `data/01_data_understanding/images/<slug>/cover.jpg`) y referenciarla en el frontmatter como `foto: <slug>/<archivo>`. Es un campo que se completa a mano — ver abajo de dónde sacarla.
4. El cuerpo sigue un orden fijo de secciones (igual para toda receta):
   1. **Índice** ("En esta receta") — automático, lo genera `docs/js/app.js` (`crearIndice`) a partir de los `##` del cuerpo; no se escribe a mano.
   2. `## Materiales` — **opcional**, solo si la receta lo necesita (ver *Asado*).
   3. `## Ingredientes` — **obligatorio** en toda receta real (con `### <subgrupo>` si hay varias partes, ver *Lemon pie*/*Tarta de frutillas*). Los stubs "pendiente de completar" (*Empanadas*, *Tarta de espinaca*) son la única excepción.
   4. `## Paso a paso` — **obligatorio**. Incluye una subsección `### Imágenes del paso a paso` con **todas** las fotos del proceso que estén en el Google Doc para esa receta (las mismas que baja `01_data_understanding/collect_initial_data/doc/extract_doc_images.py` a `data/01_data_understanding/images/<slug>/doc-NN.jpg`) — no solo la portada curada (`foto`/`cover.jpg`). Cada imagen lleva un id (`![alt](ruta){: .foto-paso #foto-<algo> }`, extensión `attr_list`) y un caption en cursiva debajo diciendo a qué paso corresponde; el paso correspondiente del texto linkea a esa imagen con `[📷 ver foto](#/receta/<slug>/foto-<algo>){: .ver-foto }` (nunca un `#ancla` suelto — rompe el router hash-based, ver `docs/app.js: route()`). Una foto que no corresponde a ningún paso puntual (resultado final, ingredientes) no lleva link entrante, solo el caption. Ver "Cómo elegir a qué paso corresponde cada foto" más abajo.

   Tips y advertencias como citas: `> ℹ️ ...` / `> ⚠️ ...`.

5. **Sub-recetas que se repiten en más de una receta** (masa sablée, crema pastelera): no se copia el contenido completo en cada archivo — viven una sola vez en `recipes/utils/<fragmento>.md` y se traen con `<!-- incluir: <fragmento>#ingredientes -->` / `#paso-a-paso` en el lugar donde iría ese contenido. Ver `recipes/utils/README.md` para el formato y cuándo vale la pena crear un fragmento nuevo.

## Cómo conseguir la foto de portada (`foto`) de una receta

Orden de prioridad — probar cada paso solo si el anterior no dio una imagen aceptable, nunca saltar al final para ahorrar tiempo:

1. **¿Ya hay `data/01_data_understanding/images/<slug>/cover.jpg`?** Nada que hacer.
2. **Fotos que el usuario ya sacó e insertó en el Google Doc** (son las fotos reales de la receta — siempre la mejor opción si existen):
   ```
   python 01_data_understanding/collect_initial_data/doc/extract_doc_images.py <doc.json>
   ```
   Baja **todas** las fotos de esa receta, numeradas, a `data/01_data_understanding/images/<slug>/doc-NN.jpg` (nunca elige portada sola ni pisa un `cover.jpg` que ya exista). Mirar cada una y copiar a mano la que mejor muestre el plato como `data/01_data_understanding/images/<slug>/cover.jpg` — preferir el plato terminado por sobre fotos de proceso, pero una foto de proceso reconocible es mejor que ninguna foto (caso *Asado*, *Turrón de quaker*).
3. **Si el Doc no tiene fotos de esa receta, pero `fuente` en el frontmatter apunta a algo:**
   ```
   python 01_data_understanding/collect_initial_data/covers/fetch_covers.py
   ```
   Si `fuente` (o un link en el cuerpo) es un video de YouTube, baja su miniatura. Si es una página de recetas, baja su `og:image`. Revisar el resultado antes de aceptarlo: a veces el `og:image` es una foto genérica del sitio o de una persona en vez del plato (pasó con *torta-de-nuez* — se reemplazó a mano por otra foto de la misma página). Instagram bloquea el scraping sin login; no vale la pena insistir ahí.
4. **Si no hay nada propio (ni Doc, ni `fuente` con imagen usable):** buscar una foto representativa del plato en **Bing Images** (no Google — pide CAPTCHA a tráfico automatizado, no se resuelve) usando los ingredientes/pasos reales de la receta como término de búsqueda, no solo el título. Abrir el resultado elegido en el panel de detalle de Bing y extraer la URL real de la imagen con `decodeURIComponent(location.href).match(/mediaurl=([^&]+)/)[1]` (evita el thumbnail recortado de `th.bing.com`). **Mirar la imagen antes de aceptarla**, siempre — esta es una foto genérica, no la receta real del usuario, así que tiene que representar bien el plato o no sirve.
5. **Si ninguna opción anterior da una imagen aceptable**, la receta queda sin `foto`. Es un WARNING de `generate_site.py`, no un ERROR — nunca forzar una imagen que no representa el plato, y nunca generar una imagen (IA, placeholder genérico) en su lugar.

Ninguno de estos pasos está en el `Makefile` ni en CI: bajar fotos de fuentes externas necesita revisión visual humana antes de aceptar cada una, así que es manual por diseño. Detalle completo y el porqué de cada decisión en `DECISIONS.md`.

## Cómo elegir a qué paso corresponde cada foto del paso a paso

`extract_doc_images.py` baja las fotos en el mismo orden en que aparecen en el Doc, pero sin decir a qué paso pertenece cada una. Para asignarlas sin inventar: releer el `doc.json` ya descargado y, para cada imagen, mirar el párrafo de texto que la precede inmediatamente dentro de esa receta (mismo criterio que usa `_agrupar_recetas`: todo lo que cuelga de un `HEADING_3` hasta el próximo `HEADING_1/2/3`). Ese texto casi siempre es el paso que la foto ilustra — el usuario saca la foto y la inserta ahí mismo, en el momento. Confirmar con la foto en sí solo cuando la posición es ambigua (ej. está justo entre dos pasos, o pegada al encabezado antes de cualquier paso — en ese caso suele ser una foto del resultado final o de los ingredientes, sin paso puntual asociado). **No asignar un paso mirando solo el contenido de la foto a ojo** — con pasos visualmente parecidos (ej. "agregar leña" repetido varias veces en *Asado*) es fácil errar el número; la posición en el documento es la señal confiable.

Ojo con un artefacto del Doc: después del primer `HEADING_3` de cada receta suele venir un **segundo heading vacío** (seguido de una tabla) antes del contenido real — si el parseo corta al encontrar cualquier heading, pierde todo lo que viene después de ese vacío. Hay que seguir *después* de ese bloque vacío, no cortar ahí (pasó con *Apple crumble*: un primer intento perdió 7 de sus 10 fotos por esto).

## Si el export corta con un ERROR

Significa que algún archivo en `data/01_data_understanding/curated/` tiene un dato roto (falta `titulo`, `categorias` vacía, un valor fuera del enum, etc.). El mensaje dice el archivo y el campo. No se escribe nada nuevo — lo publicado en `docs/` queda como estaba hasta corregir la fuente.

Ver `DECISIONS.md` para el porqué de las decisiones de arquitectura, y `common/schema.py` para el contrato completo de campos.
