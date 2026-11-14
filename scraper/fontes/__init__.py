"""Adaptadores por sistema legislativo. Todos devolvem o mesmo formato (ver base.py)."""
from .base import Fonte


def criar(cfg, cliente=None):
    if cfg["sistema"] == "siscam":
        from .siscam import Siscam
        return Siscam(cfg, cliente)
    if cfg["sistema"] == "sapl":
        from .sapl import Sapl
        return Sapl(cfg, cliente)
    raise SystemExit(f"sistema desconhecido: {cfg['sistema']}")


__all__ = ["Fonte", "criar"]
