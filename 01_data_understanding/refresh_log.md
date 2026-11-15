# Bitácora de actualizaciones de datos

Una fila por vez que se trajo o actualizó una fuente. Solo se agrega al final, no se edita.
La fila del Google Doc la escribe `collect_doc.py` sola (`make collect`); las demás, `make log SOURCE=... NOTE=...`.
`make status` dice hace cuánto fue la última vez de cada fuente.

| Fecha | Fuente | Qué pasó |
|---|---|---|
| 2026-10-13 | Google Doc | primera lectura del Doc con el conector (se compartió ese día); 5 recetas migradas primero (reconstruido desde DECISIONS.md) |
| 2026-10-14 | Google Doc | varias lecturas en el día (6 vueltas): Doc unificado en una pestaña, sub-categorías, Paella, Empanadas y Cookies (reconstruido desde DECISIONS.md) |
| 2026-10-17 | Google Doc | relectura para preservar la negrita del Doc como **bold** (reconstruido desde DECISIONS.md) |
| 2026-11-15 | Google Doc | traído y guardado crudo: 2011 párrafos, 55 títulos de receta (38 completas, 17 incompletas); 6 recetas nuevas respecto al sync anterior: Beso de dama, Pan integral con semillas, Tarta de limón, Tarta de frutilla con DDL, Galletas para bebés, Galletas de limón sin manteca |
| 2026-11-15 | Curado (fuente B) | portadas agregadas a las 6 recetas nuevas (4 fotos del Doc, 1 miniatura de video, 1 de Bing) y botón/links al Doc |
