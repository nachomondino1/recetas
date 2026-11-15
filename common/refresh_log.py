"""Bitácora de actualizaciones de datos: cuándo se trajo cada fuente por última vez.

El log vive en `01_data_understanding/refresh_log.md` (REPO_STRUCTURE_PLAYBOOK §6),
una tabla de solo agregar. `collect_doc.py` anota solo cada vez que se trae el
Google Doc; para otras fuentes (lo curado a mano, portadas) se anota con
`make log SOURCE=... NOTE=...`. `make status` dice hace cuánto fue la última vez
de cada fuente y avisa si pasó mucho.

Por qué existe: acá no hay cron que lea el Doc (no hay credenciales posibles, el
Doc se lee con el conector de Claude en una sesión), así que la única forma de
saber si los datos están viejos es que quede escrito cuándo fue la última vez.
"""

from __future__ import annotations

import datetime
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402

ENCABEZADO = """# Bitácora de actualizaciones de datos

Una fila por vez que se trajo o actualizó una fuente. Solo se agrega al final, no se edita.
La fila del Google Doc la escribe `collect_doc.py` sola (`make collect`); las demás, `make log SOURCE=... NOTE=...`.
`make status` dice hace cuánto fue la última vez de cada fuente.

| Fecha | Fuente | Qué pasó |
|---|---|---|
"""

FILA_RE = re.compile(r"^\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*([^|]+?)\s*\|\s*(.*?)\s*\|\s*$")
DIAS_AVISO = 14  # pasado este plazo sin traer el Doc, `make status` avisa


def registrar(fuente: str, detalle: str, fecha: datetime.date | None = None, ruta: Path | None = None) -> None:
    ruta = ruta or config.REFRESH_LOG
    fecha = fecha or datetime.date.today()
    if not ruta.exists():
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(ENCABEZADO, encoding="utf-8")
    detalle = " ".join(detalle.split()).replace("|", "/")
    with ruta.open("a", encoding="utf-8") as f:
        f.write(f"| {fecha.isoformat()} | {fuente} | {detalle} |\n")


def leer(ruta: Path | None = None) -> list[tuple[datetime.date, str, str]]:
    ruta = ruta or config.REFRESH_LOG
    if not ruta.exists():
        return []
    filas = []
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        m = FILA_RE.match(linea)
        if m:
            filas.append((datetime.date.fromisoformat(m.group(1)), m.group(2), m.group(3)))
    return filas


def ultima_por_fuente(filas) -> dict[str, tuple[datetime.date, str]]:
    ultimas: dict[str, tuple[datetime.date, str]] = {}
    for fecha, fuente, detalle in filas:
        if fuente not in ultimas or fecha >= ultimas[fuente][0]:
            ultimas[fuente] = (fecha, detalle)
    return ultimas


def estado(hoy: datetime.date | None = None, ruta: Path | None = None) -> list[str]:
    hoy = hoy or datetime.date.today()
    ultimas = ultima_por_fuente(leer(ruta))
    if not ultimas:
        return ["Sin registros todavía. Traer el Doc con `make collect DOC=<json>`."]
    lineas = []
    for fuente, (fecha, detalle) in sorted(ultimas.items()):
        dias = (hoy - fecha).days
        cuando = "hoy" if dias == 0 else "ayer" if dias == 1 else f"hace {dias} días"
        aviso = "  ⚠ hace mucho: conviene volver a traerlo" if fuente == "Google Doc" and dias > DIAS_AVISO else ""
        lineas.append(f"{fuente}: última vez {fecha.isoformat()} ({cuando}) — {detalle}{aviso}")
    return lineas


def main() -> int:
    args = sys.argv[1:]
    if args[:1] == ["status"] or not args:
        print("\n".join(estado()))
        return 0
    if args[0] == "add" and len(args) >= 3:
        registrar(args[1], " ".join(args[2:]))
        print(f"OK: registrado en {config.REFRESH_LOG}")
        return 0
    print("Uso: refresh_log.py status | refresh_log.py add <fuente> <detalle>", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
