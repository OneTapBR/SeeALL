"""Cartões de compartilhamento (1200×630) por vereador, gerados com Pillow no build.

Usam as mesmas fontes e cores do site. A foto vem do sistema da câmara; se não
vier, o cartão sai com as iniciais.
"""
import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from classificar import CATS
from config import para_br
from rede import Cliente

TIPOS = Path(__file__).resolve().parent / "tipos"
L, A = 1200, 630
AZUL, AZUL_FUNDO, AMBAR, BRANCO, CLARO = (31, 79, 216), (16, 39, 110), (245, 183, 0), (255, 255, 255), (190, 205, 245)
CORES = {"bairro": (106, 149, 255), "cobranca": (255, 138, 76), "homenagem": (255, 92, 143), "lei": (60, 203, 142), "outros": (152, 162, 188)}
ROTULOS = {"bairro": "pedidos nos\nbairros", "cobranca": "perguntas e\ncobranças", "homenagem": "homenagens", "lei": "propostas\nde lei", "outros": "outros"}
ORDEM = ["lei", "homenagem", "bairro", "cobranca", "outros"]


def fonte(nome, tamanho, peso=400, largura=100):
    try:
        f = ImageFont.truetype(str(TIPOS / f"{nome}.ttf"), tamanho)
        eixos = []
        for e in f.get_variation_axes():
            tag = (e.get("name") or b"")
            tag = tag.decode() if isinstance(tag, bytes) else str(tag)
            eixos.append(largura if tag.lower().startswith("wid") else peso if tag.lower().startswith("wei") else e["default"])
        f.set_variation_by_axes(eixos)
        return f
    except Exception:
        return ImageFont.load_default(tamanho)


def nome_bonito(nome):
    minusculas = {"da", "de", "do", "dos", "das", "e"}
    return " ".join(p.lower() if p.lower() in minusculas else p if p.endswith(".") else p.capitalize() for p in nome.split())


_FUNDO = None


def fundo():
    """Fundo azul em degradê com os anéis do radar (desenhado uma vez e copiado)."""
    global _FUNDO
    if _FUNDO is None:
        _FUNDO = _desenha_fundo()
    return _FUNDO.copy()


def _desenha_fundo():
    img = Image.new("RGB", (L, A), AZUL_FUNDO)
    d = ImageDraw.Draw(img, "RGBA")
    for y in range(A):
        t = y / A
        d.line((0, y, L, y), fill=tuple(round(AZUL[i] * (1 - t) + AZUL_FUNDO[i] * t) for i in range(3)))
    cx, cy = 1010, 170
    for r in (90, 180, 270, 360):
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(255, 255, 255, 30), width=2)
    d.line((cx - 360, cy, cx + 360, cy), fill=(255, 255, 255, 22), width=2)
    d.line((cx, cy - 360, cx, cy + 360), fill=(255, 255, 255, 22), width=2)
    d.ellipse((cx + 118, cy - 96, cx + 146, cy - 68), fill=AMBAR + (255,))
    return img


def marca(d, titulo, atualizado):
    y = A - 74
    d.ellipse((70, y, 110, y + 40), outline=BRANCO, width=4)
    d.ellipse((81, y + 11, 99, y + 29), outline=BRANCO, width=3)
    d.ellipse((98, y - 2, 112, y + 12), fill=AMBAR)
    d.text((126, y + 20), titulo, font=fonte("Archivo", 30, 800, 112), fill=BRANCO, anchor="lm")
    d.text((L - 70, y + 20), f"dados oficiais da Câmara · {atualizado}", font=fonte("PublicSans", 22, 500), fill=CLARO, anchor="rm")


def quebra(d, texto, f, largura, linhas=2):
    palavras, out, atual = texto.split(), [], ""
    for p in palavras:
        tenta = f"{atual} {p}".strip()
        if d.textlength(tenta, font=f) <= largura or not atual:
            atual = tenta
        else:
            out.append(atual)
            atual = p
    out.append(atual)
    if len(out) > linhas:
        out = out[:linhas]
        out[-1] = out[-1].rstrip(".,") + "…"
    return out


def numeros(d, cats, y):
    total = sum(cats.values()) or 1
    x0, larg, x = 70, L - 140, 70
    for c in CATS:
        w = round(larg * cats[c] / total)
        if w:
            d.rounded_rectangle((x, y, x + max(w - 4, 2), y + 22), radius=11, fill=CORES[c])
            x += w
    col = larg / len(ORDEM)
    for i, c in enumerate(ORDEM):
        cx = x0 + col * i
        d.text((cx, y + 50), f"{cats[c]:,}".replace(",", "."), font=fonte("Archivo", 66, 850, 105), fill=CORES[c])
        d.multiline_text((cx, y + 130), ROTULOS[c], font=fonte("PublicSans", 23, 500), fill=BRANCO, spacing=4)


def foto_redonda(dados, lado):
    im = Image.open(io.BytesIO(dados)).convert("RGB")
    w, h = im.size
    m = min(w, h)
    im = im.crop(((w - m) // 2, 0, (w - m) // 2 + m, m)).resize((lado, lado), Image.LANCZOS)
    masc = Image.new("L", (lado * 2, lado * 2), 0)
    ImageDraw.Draw(masc).ellipse((0, 0, lado * 2, lado * 2), fill=255)
    return im, masc.resize((lado, lado), Image.LANCZOS)


def cartao_vereador(v, cfg, atualizado, foto=None):
    img = fundo()
    d = ImageDraw.Draw(img)
    lado, x, y = 200, 70, 64
    d.ellipse((x - 6, y - 6, x + lado + 6, y + lado + 6), fill=AMBAR)
    posto = False
    if foto:
        try:
            im, masc = foto_redonda(foto, lado)
            img.paste(im, (x, y), masc)
            posto = True
        except Exception:
            pass
    if not posto:
        d.ellipse((x, y, x + lado, y + lado), fill=AZUL_FUNDO)
        partes = [p for p in v["nome"].split() if not p.endswith(".")]
        iniciais = (partes[0][0] + partes[-1][0]).upper() if partes else "?"
        d.text((x + lado / 2, y + lado / 2), iniciais, font=fonte("Archivo", 84, 800), fill=BRANCO, anchor="mm")
    tx = x + lado + 44
    f_nome = fonte("Archivo", 68, 850, 112)
    linhas = quebra(d, nome_bonito(v["nome"]), f_nome, L - tx - 70)
    ty = y + (18 if len(linhas) > 1 else 46)
    for l in linhas:
        d.text((tx, ty), l, font=f_nome, fill=BRANCO)
        ty += 72
    total = sum(v["cats"].values())
    d.text((tx, ty + 10), f"{v['partido']} · {total:,} documentos desde a posse".replace(",", "."), font=fonte("PublicSans", 28, 500), fill=CLARO)
    numeros(d, v["cats"], 318)
    marca(d, cfg["titulo_site"], atualizado)
    return img


def cartao_home(radar, cfg, atualizado):
    img = fundo()
    d = ImageDraw.Draw(img)
    f = fonte("Archivo", 70, 850, 116)
    y = 62
    for l in quebra(d, f"O que os {len(radar['vereadores'])} vereadores de {cfg['nome']} fizeram desde a posse.", f, L - 300, 3):
        d.text((70, y), l, font=f, fill=BRANCO)
        y += 76
    numeros(d, radar["total"], 318)
    marca(d, cfg["titulo_site"], atualizado)
    return img


def gerar_cartoes(pasta, cfg, radar, baixar_fotos=True):
    pasta.mkdir(parents=True, exist_ok=True)
    for velho in pasta.glob("*.png"):
        velho.unlink()
    atualizado = radar["atualizado"].split(" ")[0] or para_br(radar["legislatura"]["inicio"])
    http = Cliente(pausa=0.05, tentativas=1, tempo=20)
    cartao_home(radar, cfg, atualizado).save(pasta / "home.png", optimize=True)
    n = 1
    for v in radar["vereadores"]:
        foto = None
        if baixar_fotos and v.get("foto"):
            try:
                foto = http.bytes(v["foto"])
            except Exception:
                foto = None
        cartao_vereador(v, cfg, atualizado, foto).save(pasta / f"{v['id']}.png", optimize=True)
        n += 1
    return n
