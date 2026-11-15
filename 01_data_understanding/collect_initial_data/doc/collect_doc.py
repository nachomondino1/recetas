"""Capa cruda: el Google Doc tal cual viene, versionado en `data/01_data_understanding/doc/recetas.jsonl`.

Flujo (ver DECISIONS.md, "Capa cruda del Doc"), en fases CRISP-DM:

    01 collect_doc (este módulo)  ->  02 format_data  ->  recipes/  ->  05 generate_site -> docs/

Qué hace: reduce el JSON de la Docs API (~1,6 MB, con índices y ids que
cambian en cada lectura) a UN párrafo por línea, solo con lo que tiene
significado para quien lee la receta: estilo (HEADING_n / texto), si es ítem
de lista (ordenada o viñeta), nivel de anidación, y los tramos de texto con
negrita y link. No interpreta nada (no sabe qué es una receta, un ingrediente
o una categoría): eso es trabajo de la capa de preparación.

Por qué una línea por párrafo: `git diff data/01_data_understanding/doc/recetas.jsonl` muestra
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


sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "common"))
import config  # noqa: E402
import gdoc  # noqa: E402
import refresh_log  # noqa: E402



def _tab_recetas(doc_json: dict) -> dict | None:
    tabs = doc_json.get("content", {}).get("tabs", [])
    return next(
        (t for t in tabs if t.get("tabProperties", {}).get("title", "") == gdoc.TAB_RECETAS),
        None,
    )


def extraer_raw(doc_json: dict) -> list[dict]:
    """JSON de la Docs API -> lista de párrafos crudos (pestaña "Recetas")."""
    tab = _tab_recetas(doc_json)
    if tab is None:
        raise ValueError(f"no se encontró la pestaña '{gdoc.TAB_RECETAS}' en el Doc")
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
        heading_id = parrafo.get("paragraphStyle", {}).get("headingId")
        if heading_id:
            registro["headingId"] = heading_id  # para linkear directo al título en el Doc
        if bullet is not None:
            registro["lista"] = "ordenada" if gdoc.es_ordenada(parrafo, listas) else "viñeta"
            registro["nivel"] = bullet.get("nestingLevel", 0)
        salida.append(registro)
    return salida


def extraer_meta(doc_json: dict) -> dict:
    """Ids que hacen falta para armar el link a una receta dentro del Doc."""
    tab = _tab_recetas(doc_json) or {}
    return {"documentId": doc_json.get("content", {}).get("documentId"),
            "tabId": tab.get("tabProperties", {}).get("tabId")}


def leer_lineas(origen: Path) -> list[str]:
    """Líneas del raw anterior (para saber si el Doc cambió desde la última vez)."""
    return origen.read_text(encoding="utf-8").splitlines() if origen.exists() else []


def titulos_de_receta(lineas: list[str]) -> list[str]:
    """Títulos de receta (HEADING_3) de un raw ya guardado, en orden y sin repetir."""
    titulos: list[str] = []
    for linea in lineas:
        try:
            p = json.loads(linea)
        except ValueError:
            continue
        if p.get("style") == "HEADING_3":
            t = "".join(r[0] for r in p.get("runs", [])).strip()
            if t and t not in titulos:
                titulos.append(t)
    return titulos


def escribir_raw(parrafos: list[dict], destino: Path, meta: dict | None = None) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    registros = ([{"_doc": meta}] if meta else []) + parrafos
    lineas = [json.dumps(p, ensure_ascii=False, separators=(",", ":")) for p in registros]
    destino.write_text("\n".join(lineas) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("doc_json", type=Path, help="JSON crudo devuelto por read_doc")
    parser.add_argument("--out", type=Path, default=config.RAW_DOC)
    args = parser.parse_args()
    doc_json = json.loads(args.doc_json.read_text(encoding="utf-8"))
    parrafos = extraer_raw(doc_json)
    anterior = leer_lineas(args.out)
    escribir_raw(parrafos, args.out, extraer_meta(doc_json))
    nuevas = leer_lineas(args.out)
    agregados, quitados = len(set(nuevas) - set(anterior)), len(set(anterior) - set(nuevas))
    titulos_antes = titulos_de_receta(anterior)
    titulos_ahora = titulos_de_receta(nuevas)
    nuevos = [t for t in titulos_ahora if t not in titulos_antes]
    borrados = [t for t in titulos_antes if t not in titulos_ahora]
    partes = [f"{len(titulos_ahora)} recetas en el Doc"]
    if not anterior:
        partes.append("primera lectura")
    else:
        partes.append(f"nuevas ({len(nuevos)}): {', '.join(nuevos)}" if nuevos else "sin recetas nuevas")
        if borrados:
            partes.append(f"quitadas ({len(borrados)}): {', '.join(borrados)}")
        partes.append("el texto no cambió" if not (agregados or quitados)
                      else f"texto: +{agregados} / -{quitados} párrafos")
    refresh_log.registrar("Google Doc", "; ".join(partes), recetas=len(titulos_ahora))
    try:
        destino = args.out.resolve().relative_to(config.ROOT)
    except ValueError:  # --out fuera del repo
        destino = args.out
    print(f"Ver qué cambió en el Doc: git diff {destino}")
    print(f"Anotado en {config.REFRESH_LOG.relative_to(config.ROOT) if config.ROOT in config.REFRESH_LOG.parents else config.REFRESH_LOG}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
