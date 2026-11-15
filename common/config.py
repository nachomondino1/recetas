"""Todos los paths del proyecto en un solo lugar (REPO_STRUCTURE_PLAYBOOK §3, §6).

Nadie más hardcodea un path: cuando se mueven carpetas se toca este archivo.
El dato vive en `data/<fase>/`, espejando las fases CRISP-DM; lo que se sirve
vive en `SITE_DIR` (`docs/`, porque el sitio ya está publicado desde ahí).
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Dato, espejando las fases
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "01_data_understanding" / "doc"
RAW_DOC = RAW_DIR / "recetas.jsonl"  # el Google Doc tal cual (ver collect_doc.py)
IMAGES_DIR = DATA_DIR / "01_data_understanding" / "images"  # portadas y fotos de paso
# Fuente B: lo curado a mano (recetas .md con foto, porciones, prosa pulida...).
CURATED_DIR = DATA_DIR / "01_data_understanding" / "curated"
CURATED_UTILS_DIR = CURATED_DIR / "utils"  # fragmentos reusables (masa sablée, crema pastelera)
ALIASES_FILE = CURATED_DIR / "doc_aliases.yml"  # slug en el Doc -> slug curado
DRAFTS_DIR = DATA_DIR / "02_data_preparation" / "drafts"  # borradores del Doc (gitignored)
INTEGRATED_DIR = DATA_DIR / "02_data_preparation" / "integrated"  # A + B integradas (gitignored)

# Lo que se sirve
SITE_DIR = ROOT / "docs"

