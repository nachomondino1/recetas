"""Capa cruda: el Google Doc tal cual viene, versionado en `raw/recetas.jsonl`.

Flujo (ver DECISIONS.md, "Capa cruda del Doc"):

    read_doc (conector)  ->  raw/recetas.jsonl  ->  preparación  ->  recipes/ -> sitio
                              ^ este módulo         ^ doc_sync / export_data

Qué hace: reduce el JSON de la Docs API (~1,6 MB, con índices y ids que
cambian en cada lectura) a UN párrafo por línea, solo con lo que tiene
significado para quien lee la receta: estilo (HEADING_n / texto), si es ítem
de lista (ordenada o viñeta), nivel de anidación, y los tramos de texto con
negrita y link. No interpreta nada (no sabe qué es una receta, un ingrediente
o una categoría): eso es trabajo de la capa de preparación.

Por qué una línea por párrafo: `git diff raw/recetas.jsonl` muestra
exactamente qué párrafos se agregaron/cambiaron/borraron desde el último
sync, sin depender de `revisionId` (que no es confiable, ver DECISIONS.md) ni
de comparar hashes de recetas ya parseadas.

Salida determinística: mismo Doc -> mismos bytes.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src import doc_sync

RAW_DEFAULT = Path("raw/recetas.jsonl")


def _tab_recetas(doc_json: dict) -> dict | None:
    tabs = doc_json.get("content", {}).get("tabs", [])
    return next(
        (t for t in tabs if t.get("tabProperties", {}).get("title", "") == doc_sync.TAB_RECETAS),
        None,
    )


def extraer_raw(doc_json: dict) -> list[dict]:
    """JSON de la Docs API -> lista de párrafos crudos (pestaña "Recetas")."""
    tab = _tab_recetas(doc_json)
    if tab is None:
        raise ValueError(f"no se encontró la pestaña '{doc_sync.TAB_RECETAS}' en el Doc")
    doc_tab = tab.get("documentTab", {})
    listas = doc_tab.get("lists", {})

    salida = []
    for elemento in doc_tab.get("body", {}).get("content", []):
        parrafo = elemento.get("paragraph")
        if parrafo is None:
            continue
        runs: list[list] = []
        for e in parrafo.get("elements", []):
            tr = e.get("textRun", {})
            contenido = tr.get("content", "")
            if not contenido:
                continue
            estilo = tr.get("textStyle", {})
            negrita = bool(estilo.get("bold"))
            link = (estilo.get("link") or {}).get("url")
            if runs and runs[-1][1] == negrita and runs[-1][2] == link:
                runs[-1][0] += contenido
            else:
                runs.append([contenido, negrita, link])
        for r in runs:
            r[0] = r[0].rstrip("\n") if r is runs[-1] else r[0]

        bullet = parrafo.get("bullet")
        registro = {
            "style": parrafo.get("paragraphStyle", {}).get("namedStyleType", "NORMAL_TEXT"),
            "runs": runs,
        }
        if bullet is not None:
            registro["lista"] = "ordenada" if doc_sync._es_ordenada(parrafo, listas) else "viñeta"
            registro["nivel"] = bullet.get("nestingLevel", 0)
        salida.append(registro)
    return salida


def escribir_raw(parrafos: list[dict], destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    lineas = [json.dumps(p, ensure_ascii=False, separators=(",", ":")) for p in parrafos]
    destino.write_text("\n".join(lineas) + "\n", encoding="utf-8")


def leer_raw(origen: Path) -> list[dict]:
    return [json.loads(l) for l in origen.read_text(encoding="utf-8").splitlines() if l.strip()]


def parrafos_desde_raw(raw: list[dict]) -> list[dict]:
    """Párrafos crudos -> la forma aplanada que consume `doc_sync.parse_parrafos`."""
    salida = []
    for p in raw:
        runs = p.get("runs", [])
        texto = "".join(r[0] for r in runs).strip()
        texto_md = doc_sync.md_desde_runs([(r[0], bool(r[1])) for r in runs]).strip()
        salida.append({
            "style": p.get("style", "NORMAL_TEXT"),
            "texto": texto,
            "texto_md": texto_md,
            "es_lista": "lista" in p,
            "ordenada": p.get("lista") == "ordenada",
            "nivel": p.get("nivel", 0),
        })
    return salida


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("doc_json", type=Path, help="JSON crudo devuelto por read_doc")
    parser.add_argument("--out", type=Path, default=RAW_DEFAULT)
    args = parser.parse_args()
    doc_json = json.loads(args.doc_json.read_text(encoding="utf-8"))
    parrafos = extraer_raw(doc_json)
    escribir_raw(parrafos, args.out)
    print(f"OK: {len(parrafos)} párrafo(s) escritos en {args.out}")
    print("Ver qué cambió en el Doc: git diff " + str(args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
