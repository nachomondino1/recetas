"""Todos los paths del proyecto en un solo lugar (REPO_STRUCTURE_PLAYBOOK §3, §6).

Nadie más hardcodea un path: cuando se mueven carpetas se toca este archivo.
El dato vive en `data/<fase>/`, espejando las fases CRISP-DM; lo que se sirve
vive en `SITE_DIR` (`docs/`, porque el sitio ya está publicado desde ahí).
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMMON_DIR = ROOT / "common"

# Fases (código)
DATA_UNDERSTANDING_DIR = ROOT / "01_data_understanding"
DATA_PREPARATION_DIR = ROOT / "02_data_preparation"
DEPLOYMENT_DIR = ROOT / "05_deployment"

# Dato, espejando las fases
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "01_data_understanding" / "doc"
RAW_DOC = RAW_DIR / "recetas.jsonl"  # el Google Doc tal cual (ver collect_doc.py)
IMAGES_DIR = DATA_DIR / "01_data_understanding" / "images"  # portadas y fotos de paso
RECIPES_DIR = DATA_DIR / "02_data_preparation" / "recipes"  # recetas curadas (.md)
RECIPES_UTILS_DIR = RECIPES_DIR / "utils"
DRAFTS_DIR = DATA_DIR / "02_data_preparation" / "drafts"  # borradores del sync (gitignored)

# Lo que se sirve
SITE_DIR = ROOT / "docs"
SITE_DATA_DIR = SITE_DIR / "data"
SITE_IMAGES_DIR = SITE_DIR / "images"


def add_to_path(*dirs: Path) -> None:
    """Las carpetas numeradas no son paquetes importables (`import 02_...` es un
    error de sintaxis): cada script arma su sys.path hacia `common/` y hacia las
    fases anteriores que necesita."""
    for d in dirs:
        if str(d) not in sys.path:
            sys.path.insert(0, str(d))
