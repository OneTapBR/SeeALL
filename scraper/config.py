"""Configuração da cidade (cidade.json) e cálculo das legislaturas."""
import json
import os
import re
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SISTEMAS = ("siscam", "sapl")
OBRIGATORIOS = ("nome", "uf", "sistema", "url_base", "slug", "titulo_site")


def carregar(caminho=None):
    """Lê e valida o cidade.json. `caminho` também pode vir de RADAR_CIDADE."""
    caminho = Path(caminho or os.environ.get("RADAR_CIDADE") or RAIZ / "cidade.json")
    cfg = json.loads(caminho.read_text("utf-8"))
    faltam = [c for c in OBRIGATORIOS if not cfg.get(c)]
    if faltam:
        raise SystemExit(f"{caminho}: faltam os campos {', '.join(faltam)}")
    if cfg["sistema"] not in SISTEMAS:
        raise SystemExit(f"{caminho}: sistema deve ser um de {SISTEMAS}")
    cfg["url_base"] = cfg["url_base"].rstrip("/")
    cfg.setdefault("posse_inicial", "2025-01-01")
    cfg.setdefault("codigos_tipos", {})
    cfg.setdefault("prazo_resposta_dias", 30)
    cfg.setdefault("mesclar_autores", {})
    if not re.fullmatch(r"\d{4}-01-01", cfg["posse_inicial"]):
        raise SystemExit("posse_inicial deve ser 1º de janeiro, no formato AAAA-01-01")
    return cfg


def legislatura(cfg, hoje=None, ano=None):
    """Devolve (início, fim) da legislatura vigente em `hoje`, ou da que tomou posse em `ano`.

    A posse é sempre em 1º de janeiro, a cada 4 anos a partir de posse_inicial.
    """
    base = int(cfg["posse_inicial"][:4])
    if ano is None:
        hoje = hoje or date.today()
        ano = base + 4 * ((hoje.year - base) // 4)
    elif (ano - base) % 4:
        raise SystemExit(f"{ano} não é ano de posse (a base é {base}, de 4 em 4 anos)")
    return date(ano, 1, 1), date(ano + 3, 12, 31)


def pastas(saida=None):
    """(pasta dos dados brutos, pasta do site). `saida` troca a raiz (usado em testes)."""
    raiz = Path(saida) if saida else RAIZ
    return raiz / "dados", raiz / "site"


def url_site(cfg):
    """Endereço público do site, usado só nas imagens de compartilhamento."""
    if os.environ.get("SITE_URL"):
        return os.environ["SITE_URL"].rstrip("/")
    if cfg.get("dominio"):
        return "https://" + cfg["dominio"].strip("/")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if repo and "/" in repo:
        dono, nome = repo.split("/", 1)
        raiz = f"https://{dono.lower()}.github.io"
        return raiz if nome.lower() == f"{dono.lower()}.github.io" else f"{raiz}/{nome}"
    return ""


def de_br(txt):
    """'13/11/2026' → '2026-11-13' (None se não for data válida)."""
    m = re.search(r"(\d{2})/(\d{2})/(\d{4})", txt or "")
    if not m:
        return None
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
    except ValueError:
        return None


def para_br(d):
    return f"{d[8:10]}/{d[5:7]}/{d[:4]}" if d else ""


def dias(a, b):
    """Dias corridos entre duas datas ISO."""
    return (date.fromisoformat(b) - date.fromisoformat(a)).days


def janela(hoje, n):
    return hoje - timedelta(days=n)
