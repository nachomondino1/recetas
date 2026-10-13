# Decisiones

## 2026-10-13 — De Word a sitio web filtrable

**Problema:** las recetas vivían en `Recetas.docx`. Encontrar algo para cocinar era difícil: sin foto, tiempo, dificultad ni categoría a la vista, y sin forma de filtrar u ordenar.

**Fuente de datos:** se evaluó seguir usando el Word/Google Doc o pasar a una Google Sheet para los campos estructurados. Se descartaron las dos: el contenido es texto largo (pasos, tips, advertencias), no tabular, y el usuario es el único que edita. Se eligió **un archivo Markdown por receta con YAML frontmatter**, versionado en `recipes/`, siguiendo la decisión #1 del playbook de datos (edita solo el usuario, contenido chico y no tabular → fuente versionada en el repo, no planilla).

**El `.docx` original no se commitea al repo.** Es un binario que deja de ser la fuente de verdad una vez migradas las 5 recetas; vive en `Downloads`. Los `.md` en `recipes/` son la única fuente de verdad desde ahora.

**Carga de datos en el front: `site/data.js` embebido, no `fetch`.** El usuario abre `index.html` como `file://` para revisar antes de commitear, y `fetch` de un JSON local rompe por CORS en ese esquema. `site/recetas.json` se genera igual, como contrato formal para tests/diffs, pero el sitio no lo usa en runtime.

**Enums iniciales** (`src/schema.py`): `categorias = {almuerzo, cena, merienda, postre}`, `dificultad = {baja, media, alta}`. Se incluyeron merienda/postre aunque hoy no haya ninguna receta así, porque el usuario espera agregarlas pronto — es un `set`, extenderlo es una línea.

**Sin fecha de última actualización manual como regla.** Asado la traía del doc original (`fecha_actualizacion: 2026-07-05`) y se preservó, pero no es un campo obligatorio ni con WARNING si falta: el historial de git (`git log -- recipes/<receta>.md`) cumple ese rol de ahora en más.

**Migración de contenido — decisiones puntuales:**
- *Guiso con lentejas* tenía dos versiones del paso a paso en el doc (una detallada y una "original" resumida, que parecía un borrador viejo). El usuario pidió conservar ambas: la detallada queda como pasos principales, la resumida como "Método alternativo" al final.
- *Asado* no tiene ninguna foto de plato servido en el doc (las 20 fotos son todas del proceso de armar el fuego). El usuario eligió no forzar ninguna de esas como portada: la card usa el placeholder (🍲) hasta que haya una mejor.
- *Pastel de papa*, *Tacos* y *Papas al horno* no traían `Tiempo`/`Dificultad` en el doc original. Los valores que quedaron en sus `.md` (90/media, 60/media, 75/baja) son estimaciones del usuario, no del doc.
- Las 5 recetas migradas se etiquetaron `categorias: [almuerzo, cena]` por default (el doc no tenía un campo de categoría); ajustar si alguna no aplica.

**Alcance v1:** sin CI ni deploy a GitHub Pages todavía. El flujo es local: `make update` regenera `site/recetas.json`/`data.js`, y `make open` lo muestra en el navegador antes de commitear. El deploy queda para un paso posterior.
