"""Integra las dos fuentes de datos en un solo conjunto (CRISP-DM: integrate data).

  Fuente A  data/01_data_understanding/doc/recetas.jsonl   el Google Doc, tal cual
  Fuente B  data/01_data_understanding/curated/*.md         lo curado a mano: foto,
            porciones, dificultad, tiempo, prosa pulida, fusiones ya resueltas
            ->  data/02_data_preparation/integrated/*.md    un .md por receta

Reglas (por receta, unidas por slug; `doc_aliases.yml` resuelve los títulos que
en el Doc son más cortos que el nombre curado):

  - Solo en A  -> NUEVA: se arma del Doc (format_data.render_markdown). Entra al
                  sitio sola. Si no tiene foto, el export avisa (WARNING).
  - En A y B   -> gana B (lo curado), porque tiene lo que el Doc no tiene. Se
                  compara `doc_hash`: si el Doc cambió desde la última curación se
                  reporta "revisar" (no se pisa nada, no se pierde nada).
  - Solo en B  -> se conserva (ej. recetas que el Doc todavía no tiene completas).
  - Receta del Doc incompleta (sin ingredientes o sin paso a paso) -> no se
                  publica por A, se reporta; si existe en B, B la sostiene.

El dato integrado es derivado y regenerable (gitignored): nunca se edita a mano.
Para cambiar una receta: cambiar el Doc (fuente A) o su .md curado (fuente B).
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402
import format_data  # noqa: E402


def cargar_aliases(ruta: Path) -> dict[str, str]:
    if not ruta.exists():
        return {}
    return yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}


def integrar(
    completas: list[dict],
    incompletas: list[dict],
    curated_dir: Path,
    out_dir: Path,
    aliases: dict[str, str],
) -> dict[str, list]:
    """Escribe el conjunto integrado en `out_dir` y devuelve el reporte.

    `completas`/`incompletas` vienen de `format_data.parse_parrafos` (fuente A).
    """
    curadas = {p.stem: p for p in sorted(curated_dir.glob("*.md"))}
    reporte: dict[str, list] = {
        "nuevas": [], "curadas_iguales": [], "revisar": [], "solo_curadas": [], "fragmentos": [],
    }

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    cubiertas: set[str] = set()
    for receta in completas:
        slug_doc = receta["slug"]
        destino = aliases.get(slug_doc, slug_doc)
        if destino.startswith("utils:"):
            reporte["fragmentos"].append(slug_doc)
            continue
        if destino in curadas:
            cubiertas.add(destino)
            guardado = format_data._doc_hash_guardado(curadas[destino])
            if guardado != receta["doc_hash"]:
                reporte["revisar"].append({"receta": destino, "slug_doc": slug_doc})
            else:
                reporte["curadas_iguales"].append(destino)
        else:
            (out_dir / f"{destino}.md").write_text(format_data.render_markdown(receta), encoding="utf-8")
            reporte["nuevas"].append(destino)

    for slug, ruta in curadas.items():
        shutil.copyfile(ruta, out_dir / f"{slug}.md")
        if slug not in cubiertas:
            reporte["solo_curadas"].append(slug)

    reporte["incompletas"] = incompletas
    return reporte


def imprimir(reporte: dict[str, list]) -> None:
    total = len(list((config.INTEGRATED_DIR).glob("*.md"))) if config.INTEGRATED_DIR.exists() else 0
    print(f"OK: {total} receta(s) integradas en {config.INTEGRATED_DIR}")
    print(f"  {len(reporte['curadas_iguales'])} curadas al día con el Doc")
    if reporte["nuevas"]:
        print(f"  {len(reporte['nuevas'])} NUEVA(S) del Doc, entran solas: " + ", ".join(reporte["nuevas"]))
    if reporte["revisar"]:
        print(f"  {len(reporte['revisar'])} curada(s) cuyo texto cambió en el Doc desde la última curación (revisar):")
        for r in reporte["revisar"]:
            print(f"    - {r['receta']}")
    if reporte["solo_curadas"]:
        print(f"  {len(reporte['solo_curadas'])} solo curada(s), sin par completo en el Doc: " + ", ".join(reporte["solo_curadas"]))
    if reporte["incompletas"]:
        print(f"  {len(reporte['incompletas'])} receta(s) del Doc incompletas (no se publican desde el Doc):")
        for i in reporte["incompletas"]:
            print(f"    - {i['titulo'] or '(pestaña completa)'}: {i['motivo']}")


def main() -> int:
    if not config.RAW_DOC.exists():
        print(f"ERROR: falta {config.RAW_DOC}. Correr primero `make collect DOC=<json de read_doc>`.", file=sys.stderr)
        return 1
    parrafos = format_data.parrafos_desde_raw(format_data.leer_raw(config.RAW_DOC))
    completas, incompletas = format_data.parse_parrafos(parrafos)
    reporte = integrar(completas, incompletas, config.CURATED_DIR, config.INTEGRATED_DIR,
                       cargar_aliases(config.ALIASES_FILE))
    imprimir(reporte)
    return 0


if __name__ == "__main__":
    sys.exit(main())
