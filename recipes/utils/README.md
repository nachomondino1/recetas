# Fragmentos reusables (`recipes/utils/`)

Sub-recetas que se repiten en más de una receta real (masa sablée, crema
pastelera) viven acá una sola vez, en vez de copiadas en cada archivo que las
usa. No son recetas publicables: `export_data.py` solo lee `recipes/*.md`
(no recursivo), así que nada de `recipes/utils/` termina en el sitio por sí
solo.

## Formato

Un archivo por fragmento (`<slug>.md`, sin frontmatter), con las mismas
secciones `## Ingredientes` / `## Paso a paso` que usaría si fuera una receta
suelta. El nombre del archivo (sin `.md`) es el slug del fragmento.

## Cómo incluir un fragmento en una receta

En el cuerpo de `recipes/<receta>.md`, en el lugar donde iría el contenido:

```
### Masa sablée
<!-- incluir: masa-sablee#ingredientes -->
```

```
### Masa sablée
<!-- incluir: masa-sablee#paso-a-paso -->
```

`export_data.py` reemplaza ese comentario por el contenido de la sección
correspondiente del fragmento antes de renderizar. El `###` (o cualquier
título que quiera la receta) se escribe en el archivo de la receta, no en el
fragmento — así cada receta conserva su propio orden y nombres de subsección;
el fragmento solo aporta el contenido.

Si el fragmento o la sección (`#ingredientes` / `#paso-a-paso`) no existen,
`export_data.py` lo reporta como ERROR (igual que cualquier otro dato roto en
`recipes/`) — no se resuelve en silencio ni deja el comentario sin
reemplazar en el sitio publicado.

## Cuándo crear un fragmento nuevo

Cuando una sub-receta completa (ingredientes + paso a paso, no solo una
mención de pasada) aparece igual en una segunda receta real. Una mención
breve tipo "variante: usar crema pastelera en vez de curd" no amerita
fragmento — solo cuando el contenido completo se repite.
