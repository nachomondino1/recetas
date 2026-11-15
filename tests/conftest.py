"""Las carpetas de fase empiezan con número: no son paquetes importables, así que
los tests arman el sys.path igual que los scripts (REPO_STRUCTURE_PLAYBOOK §6)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for d in ("common", "02_data_preparation", "05_deployment",
          "01_data_understanding/collect_initial_data/doc"):
    sys.path.insert(0, str(ROOT / d))
