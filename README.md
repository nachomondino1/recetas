# Recetas

Sitio estático de recetas familiares: cards con foto, tiempo y dificultad, filtrables por categoría y ordenables por tiempo. Reemplaza al Word/Google Doc donde vivían antes.

## Cómo agregar o editar una receta

1. Crear (o editar) un archivo en `recipes/<slug>.md`. El nombre del archivo es el id de la receta.
2. Frontmatter obligatorio: `titulo` y `categorias` (lista, valores válidos en `src/schema.py`: `almuerzo`, `cena`, `merienda`, `postre`).
3. Frontmatter opcional: `dificultad` (`baja`/`media`/`alta`), `tiempo_minutos`, `tiempo_minutos_max` (para rangos), `porciones`, `foto`, `fecha_actualizacion`, `fuente`.
4. Si hay foto, ponerla en `images/<slug>/<archivo>` y referenciarla en el frontmatter como `foto: <slug>/<archivo>`.
5. El cuerpo es Markdown normal: `## Materiales`, `## Ingredientes` (con `### <subgrupo>` si hace falta agrupar), `## Paso a paso`. Tips y advertencias como citas: `> ℹ️ ...` / `> ⚠️ ...`.
6. Correr `make update` y revisar los warnings que imprime (campos sin dato, foto faltante, etc. — no cortan el build, pero conviene completarlos).
7. `make open` para ver el sitio actualizado en el navegador antes de commitear.

## Comandos

```
make setup   # crea el venv e instala dependencias (una sola vez)
make update  # regenera docs/recetas.json y docs/data.js desde recipes/
make test    # corre los tests de validación
make open    # abre el sitio en el navegador
make clean   # borra el venv y lo generado
```

## Si el export corta con un ERROR

Significa que algún archivo en `recipes/` tiene un dato roto (falta `titulo`, `categorias` vacía, un valor fuera del enum, etc.). El mensaje dice el archivo y el campo. No se escribe nada nuevo — lo publicado en `docs/` queda como estaba hasta corregir la fuente.

Ver `DECISIONS.md` para el porqué de las decisiones de arquitectura, y `src/schema.py` para el contrato completo de campos.
