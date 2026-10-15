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


_SECCION_RE = re.compile(r"^## +(.+?) *$", re.MULTILINE)
_INCLUDE_RE = re.compile(r"<!--\s*incluir:\s*([a-z0-9-]+)#([a-z-]+)\s*-->")


def _slug_seccion(texto: str) -> str:
    return texto.strip().lower().replace(" ", "-")


def _parsear_secciones_utils(texto: str) -> dict[str, str]:
    """De un fragmento en recipes/utils/: {slug de sección '##' -> su contenido}."""
    secciones = {}
    matches = list(_SECCION_RE.finditer(texto))
    for i, m in enumerate(matches):
        inicio = m.end()
        fin = matches[i + 1].start() if i + 1 < len(matches) else len(texto)
        secciones[_slug_seccion(m.group(1))] = texto[inicio:fin].strip()
    return secciones


def cargar_utils(utils_dir: Path) -> dict[str, dict[str, str]]:
    """slug de archivo (sin .md, sin README) -> sus secciones parseadas."""
    fragments: dict[str, dict[str, str]] = {}
    if not utils_dir.exists():
        return fragments
    for path in sorted(utils_dir.glob("*.md")):
        if path.name == "README.md":
            continue
        fragments[path.stem] = _parsear_secciones_utils(path.read_text(encoding="utf-8"))
    return fragments


def resolver_includes(body: str, utils: dict[str, dict[str, str]]) -> tuple[str, list[str]]:
    """Reemplaza <!-- incluir: fragmento#seccion --> por el contenido de
    recipes/utils/<fragmento>.md. Un include a un fragmento o sección
    inexistente es un error (ver recipes/utils/README.md) — nunca se resuelve
    en silencio ni deja el comentario tal cual en el sitio publicado.
    """
    errores: list[str] = []

    def _reemplazar(m: re.Match) -> str:
        fragmento, seccion = m.group(1), m.group(2)
        if fragmento not in utils:
            errores.append(f"incluir '{fragmento}' no existe en recipes/utils/")
            return m.group(0)
        if seccion not in utils[fragmento]:
            errores.append(
                f"incluir '{fragmento}#{seccion}': la sección '{seccion}' no existe en ese fragmento"
            )
            return m.group(0)
        return utils[fragmento][seccion]

    return _INCLUDE_RE.sub(_reemplazar, body), errores


def _as_categorias(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip().lower() for v in value if str(v).strip()]
    return [str(value).strip().lower()]


def normalizar(raws: list[dict], utils: dict[str, dict[str, str]] | None = None) -> list[dict]:
    """raw -> normalizado: trim de strings, categorías/dificultad en minúscula.

    También resuelve los <!-- incluir: ... --> del cuerpo contra `utils`
    (ver resolver_includes) — los errores de include quedan en
    `_include_errors`, para que validar() los convierta en ERROR.
    No valida reglas de negocio (eso es validar()); solo da forma a los datos.
    """
    utils = utils or {}
    records = []
    for raw in raws:
        front = raw["front"] or {}
        dificultad = front.get("dificultad")
        foto = front.get("foto")
        fecha = front.get("fecha_actualizacion")
        fuente = front.get("fuente")
        body, include_errors = resolver_includes(raw["body"], utils)
        record = {
            "id": raw["id"],
            "_parse_error": raw["_parse_error"],
            "_include_errors": include_errors,
            "body": body,
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
        for campo in sorted(schema.SUBFILTRO_CAMPOS):
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

        for include_error in r.get("_include_errors") or []:
            errors.append(f"{rid}: {include_error}")

        if not r["titulo"]:
            errors.append(f"{rid}: falta 'titulo'")

        if not r["categorias"]:
            errors.append(f"{rid}: falta 'categorias' (tiene que tener al menos una)")

        if r["dificultad"] is not None and r["dificultad"] not in schema.DIFICULTADES:
            errors.append(f"{rid}: dificultad desconocida '{r['dificultad']}' (válidas: {sorted(schema.DIFICULTADES)})")
        elif r["dificultad"] is None:
            warnings.append({"recipe": rid, "field": "dificultad", "message": "sin dato"})

        # Sub-filtro condicionado a una categoría (ver schema.CAMPO_SUBCATEGORIA):
        # el valor es libre (viene del H2 del Doc, sin enum que mantener acá);
        # el WARNING por "sin dato" solo se dispara si la receta ya está en esa
        # categoría — el sync mecánico siempre lo completa, así que su
        # ausencia señala una receta agregada a mano todavía sin clasificar.
        for categoria, campo in schema.CAMPO_SUBCATEGORIA.items():
            if r[campo] is None and categoria in r["categorias"]:
                warnings.append({"recipe": rid, "field": campo, "message": "sin dato"})

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
    return md.markdown(_linkificar_urls_sueltas(body_markdown), extensions=["sane_lists", "attr_list"])


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
        for campo in sorted(schema.SUBFILTRO_CAMPOS):
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


def copiar_imagenes(records: list[dict], images_dir: Path, site_images_dir: Path) -> None:
    """Copia todo `images/<slug>/` al sitio, no solo `foto`.

    El cuerpo puede referenciar otras imágenes de esa misma carpeta (ver
    `### Imágenes del paso a paso`, `images/<slug>/doc-NN.jpg`) — si solo se
    copiara `foto`, esas quedarían rotas en el sitio publicado aunque
    rendericen bien al abrir el `.md` crudo.
    """
    for r in records:
        src_dir = images_dir / r["id"]
        if not src_dir.is_dir():
            continue
        dst_dir = site_images_dir / r["id"]
        dst_dir.mkdir(parents=True, exist_ok=True)
        for src in src_dir.iterdir():
            if src.is_file():
                shutil.copyfile(src, dst_dir / src.name)


def run_export(recipes_dir: Path, images_dir: Path, site_dir: Path, utils_dir: Path | None = None) -> int:
    raws = load_recipes(recipes_dir)
    utils = cargar_utils(utils_dir) if utils_dir else {}
    records = normalizar(raws, utils)
    errors, warnings = validar(records, images_dir)

    if errors:
        print("ERROR: el build se corta. No se escribió nada — lo publicado queda intacto.", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    data = construir_json(records, warnings)
    site_images_dir = site_dir / "images"
    copiar_imagenes(records, images_dir, site_images_dir)

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
    return run_export(config.RECIPES_DIR, config.IMAGES_DIR, config.SITE_DIR, config.RECIPES_UTILS_DIR)


if __name__ == "__main__":
    sys.exit(main())
