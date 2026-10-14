"""Pipeline de export: load_recipes -> normalizar -> validar -> construir_json.

Cada función es pura y testeable con fixtures sintéticas (ver tests/fixtures/).
ERROR corta el build y no escribe nada; WARNING se acumula en meta.warnings
y el build sigue. Ver DATA_FLOW_PLAYBOOK en la memoria del proyecto.
"""

from __future__ import annotations

import datetime
import json
import re
import shutil
import sys
from pathlib import Path

import markdown as md
import yaml

from src import config, schema

FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n?(.*)", re.DOTALL)


def load_recipes(recipes_dir: Path) -> list[dict]:
    """Lee cada .md y separa frontmatter YAML de cuerpo Markdown. No valida nada."""
    recipes = []
    for path in sorted(recipes_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        match = FRONTMATTER_RE.match(text)
        if not match:
            recipes.append(
                {"id": path.stem, "front": None, "body": "",
                 "_parse_error": "falta el bloque de frontmatter YAML (---...---)"}
            )
            continue
        front_raw, body = match.groups()
        try:
            front = yaml.safe_load(front_raw) or {}
        except yaml.YAMLError as exc:
            recipes.append(
                {"id": path.stem, "front": None, "body": "", "_parse_error": f"YAML inválido: {exc}"}
            )
            continue
        recipes.append({"id": path.stem, "front": front, "body": body.strip(), "_parse_error": None})
    return recipes


def _as_categorias(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip().lower() for v in value if str(v).strip()]
    return [str(value).strip().lower()]


def normalizar(raws: list[dict]) -> list[dict]:
    """raw -> normalizado: trim de strings, categorías/dificultad en minúscula.

    No valida reglas de negocio (eso es validar()); solo da forma a los datos.
    """
    records = []
    for raw in raws:
        front = raw["front"] or {}
        dificultad = front.get("dificultad")
        foto = front.get("foto")
        fecha = front.get("fecha_actualizacion")
        fuente = front.get("fuente")
        record = {
            "id": raw["id"],
            "_parse_error": raw["_parse_error"],
            "body": raw["body"],
            "titulo": str(front.get("titulo") or "").strip(),
            "categorias": _as_categorias(front.get("categorias")),
            "dificultad": str(dificultad).strip().lower() if dificultad else None,
            "tiempo_minutos": front.get("tiempo_minutos"),
            "tiempo_minutos_max": front.get("tiempo_minutos_max"),
            "porciones": front.get("porciones"),
            "foto": str(foto).strip() if foto else None,
            "fecha_actualizacion": str(fecha).strip() if fecha else None,
            "fuente": str(fuente).strip() if fuente else None,
            "_unknown_fields": sorted(set(front.keys()) - schema.KNOWN_FIELDS) if front else [],
        }
        for campo in schema.SUBFILTRO_CAMPOS:
            valor = front.get(campo)
            record[campo] = str(valor).strip().lower() if valor else None
        records.append(record)
    return records


def _es_entero_valido(value) -> bool:
    if value is None:
        return True
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    try:
        int(str(value))
        return True
    except (TypeError, ValueError):
        return False


def validar(records: list[dict], images_dir: Path) -> tuple[list[str], list[dict]]:
    """Devuelve (errors, warnings). No muta records ni escribe nada."""
    errors: list[str] = []
    warnings: list[dict] = []

    for r in records:
        rid = r["id"]

        if r["_parse_error"]:
            errors.append(f"{rid}: {r['_parse_error']}")
            continue

        if not r["titulo"]:
            errors.append(f"{rid}: falta 'titulo'")

        if not r["categorias"]:
            errors.append(f"{rid}: falta 'categorias' (tiene que tener al menos una)")
        else:
            for c in r["categorias"]:
                if c not in schema.CATEGORIAS:
                    errors.append(f"{rid}: categoria desconocida '{c}' (válidas: {sorted(schema.CATEGORIAS)})")

        if r["dificultad"] is not None and r["dificultad"] not in schema.DIFICULTADES:
            errors.append(f"{rid}: dificultad desconocida '{r['dificultad']}' (válidas: {sorted(schema.DIFICULTADES)})")
        elif r["dificultad"] is None:
            warnings.append({"recipe": rid, "field": "dificultad", "message": "sin dato"})

        # Sub-filtro condicionado a una categoría (ver schema.SUBFILTROS): el
        # WARNING por "sin dato" solo se dispara si la receta ya está en esa
        # categoría, y solo para los sub-filtros que avisan_si_falta.
        for categoria, sf in schema.SUBFILTROS.items():
            valor = r[sf.campo]
            if valor is not None and valor not in sf.valores:
                errors.append(f"{rid}: {sf.campo} desconocido '{valor}' (válidos: {sorted(sf.valores)})")
            elif valor is None and sf.avisar_si_falta and categoria in r["categorias"]:
                warnings.append({"recipe": rid, "field": sf.campo, "message": "sin dato"})

        for field in ("tiempo_minutos", "tiempo_minutos_max", "porciones"):
            if not _es_entero_valido(r[field]):
                errors.append(f"{rid}: '{field}' no es un entero válido (valor: {r[field]!r})")

        if r["tiempo_minutos"] is None:
            warnings.append({"recipe": rid, "field": "tiempo_minutos", "message": "sin dato"})
        if r["tiempo_minutos_max"] is not None and r["tiempo_minutos"] is None:
            warnings.append({"recipe": rid, "field": "tiempo_minutos_max", "message": "definido sin 'tiempo_minutos'"})

        if r["foto"] is None:
            warnings.append({"recipe": rid, "field": "foto", "message": "sin foto de portada"})
        elif not (images_dir / r["foto"]).exists():
            warnings.append({"recipe": rid, "field": "foto", "message": f"el archivo 'images/{r['foto']}' no existe"})

        if not r["body"]:
            errors.append(f"{rid}: el cuerpo de la receta está vacío")

        for field in r["_unknown_fields"]:
            warnings.append({"recipe": rid, "field": field, "message": "clave de frontmatter desconocida"})

    return errors, warnings


# URLs sueltas en el cuerpo (ej. "Dos recetas de referencia: https://youtube.com/...",
# pegadas directo del Doc sin armar un link Markdown) no las auto-linkea
# python-markdown por default. Se envuelven en <...> (sintaxis autolink de
# Markdown) antes de renderizar — salvo que ya sean el target de un link
# Markdown (precedidas por "](") o ya estén envueltas en <...>.
URL_SUELTA_RE = re.compile(r"(?<!\]\()(?<!<)(https?://[^\s<>\]\)]+)")


def _linkificar_urls_sueltas(body_markdown: str) -> str:
    return URL_SUELTA_RE.sub(r"<\1>", body_markdown)


def render_body_html(body_markdown: str) -> str:
    return md.markdown(_linkificar_urls_sueltas(body_markdown), extensions=["sane_lists"])


def construir_json(records: list[dict], warnings: list[dict]) -> dict:
    """Asume que validar() no encontró ERRORs — solo se llama en ese caso."""
    recetas = []
    for r in sorted(records, key=lambda r: r["id"]):
        receta = {
            "id": r["id"],
            "titulo": r["titulo"],
            "categorias": sorted(r["categorias"]),
            "dificultad": r["dificultad"],
            "tiempo_minutos": int(r["tiempo_minutos"]) if r["tiempo_minutos"] is not None else None,
            "tiempo_minutos_max": int(r["tiempo_minutos_max"]) if r["tiempo_minutos_max"] is not None else None,
            "porciones": int(r["porciones"]) if r["porciones"] is not None else None,
            "foto": f"images/{r['foto']}" if r["foto"] else None,
            "fecha_actualizacion": r["fecha_actualizacion"],
            "fuente": r["fuente"],
            "body_html": render_body_html(r["body"]),
        }
        for campo in schema.SUBFILTRO_CAMPOS:
            receta[campo] = r[campo]
        recetas.append(receta)
    return {
        "meta": {
            "schema_version": schema.SCHEMA_VERSION,
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
            "count": len(recetas),
            "warnings": warnings,
        },
        "recetas": recetas,
    }


def copiar_fotos(records: list[dict], images_dir: Path, site_images_dir: Path) -> None:
    for r in records:
        if not r["foto"]:
            continue
        src = images_dir / r["foto"]
        if not src.exists():
            continue
        dst = site_images_dir / r["foto"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)


def run_export(recipes_dir: Path, images_dir: Path, site_dir: Path) -> int:
    raws = load_recipes(recipes_dir)
    records = normalizar(raws)
    errors, warnings = validar(records, images_dir)

    if errors:
        print("ERROR: el build se corta. No se escribió nada — lo publicado queda intacto.", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    data = construir_json(records, warnings)
    site_images_dir = site_dir / "images"
    copiar_fotos(records, images_dir, site_images_dir)

    site_dir.mkdir(parents=True, exist_ok=True)
    json_str = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)
    (site_dir / "recetas.json").write_text(json_str + "\n", encoding="utf-8")
    (site_dir / "data.js").write_text(f"window.RECETAS_DATA = {json_str};\n", encoding="utf-8")

    print(f"OK: {data['meta']['count']} receta(s) exportada(s).")
    if warnings:
        print(f"{len(warnings)} warning(s):")
        for w in warnings:
            print(f"  - [{w['recipe']}] {w['field']}: {w['message']}")
    return 0


def main() -> int:
    return run_export(config.RECIPES_DIR, config.IMAGES_DIR, config.SITE_DIR)


if __name__ == "__main__":
    sys.exit(main())
