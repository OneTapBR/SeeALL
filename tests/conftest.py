import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scraper"))
FIX = Path(__file__).resolve().parent / "fixtures"


def html(nome):
    return (FIX / "siscam" / nome).read_text("utf-8")


def api(nome):
    return json.loads((FIX / "sapl" / f"{nome}.json").read_text("utf-8"))
