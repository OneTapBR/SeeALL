"""Regras de classificação: categoria, tema, via/bairro e resultado de votação.

Tudo aqui é função pura sobre o texto do documento, para ser fácil de testar e de
ajustar. A classificação é automática e pode errar; o site sempre mostra o link
do documento original.
"""
import re

from config import de_br
from fontes.base import sem_acento

CATS = ["bairro", "cobranca", "homenagem", "lei", "outros"]

HOMENAGEM = re.compile(
    r"congratula|louvor|aplauso|pesar|homenage|reconhecimento|parabeniza|felicita|"
    r"titulo de cidad|cidadao [a-z\-]+ense|cidada [a-z\-]+ense|cidadania [a-z\-]+ense|cidadao honorari|cidadao benemerit|"
    r"medalha|comenda|honra ao merito|diploma de|denomina|da (o )?nome|dia municipal|semana municipal|mes municipal|"
    r"calendario oficial|voto de")

PEDE_INFORMACAO = re.compile(
    r"inform|esclarec|explica|\bquais\b|\bqual\b|quantos|quantas|por que|motivo|justifi|copia|relatorio|cronograma|"
    r"prazo|planilha|demonstrativo|encaminhe")
PEDE_SERVICO = re.compile(
    r"providenci|realiz|proced|instal|implant|reparo|manutenc|vistoria|construc|reform|substitu|troca|pintura|retirada|"
    r"remoc|colocac|nivel|canaleta|tapar|cortar|limpar")

TEMAS = [
    ("Buracos e asfalto", r"tapa.?buraco|buraco|recape|asfalt|pavimenta|cascalh"),
    ("Poda e mato", r"poda|arvore|mato|capina|rocada|rocagem|galho|corte de grama"),
    ("Limpeza", r"limpeza|entulho|lixo|varri|descarte|terreno"),
    ("Iluminação", r"lampada|ilumina|poste|luminaria"),
    ("Trânsito e sinalização", r"lombada|redutor|sinaliza|faixa de pedestre|semaforo|placa|estacionamento"),
    ("Calçadas e guias", r"calcada|guia|sarjeta|meio.?fio"),
    ("Água e esgoto", r"esgoto|bueiro|boca de lobo|galeria|vazamento|agua|drenagem"),
]
#: como o tema entra numa frase ("pediram poda 24 vezes na Rua X")
TEMA_FRASE = {
    "Buracos e asfalto": "conserto de buraco ou asfalto", "Poda e mato": "poda ou corte de mato", "Limpeza": "limpeza",
    "Iluminação": "iluminação", "Trânsito e sinalização": "sinalização de trânsito",
    "Calçadas e guias": "conserto de calçada ou guia", "Água e esgoto": "reparo de água ou esgoto",
}


def categoria(p):
    """bairro | cobranca | homenagem | lei | outros, a partir da família e do assunto."""
    fam = p["familia"]
    a = sem_acento(p["assunto"])
    tipo = sem_acento(p["tipo"])
    if fam == "indicacao":
        return "bairro"
    if fam == "requerimento":
        if re.search(r"pesar|minuto de silencio|congratula|louvor", a):
            return "homenagem"
        if PEDE_INFORMACAO.search(a):
            return "cobranca"
        if tema(a) or PEDE_SERVICO.search(a):
            return "bairro"
        return "cobranca"
    if fam == "mocao":
        if re.search(r"repudio|apelo|protesto|apoio", tipo):
            return "outros"
        if re.search(r"aplauso|congratula|louvor|pesar|homenag", tipo):
            return "homenagem"
        if re.match(r"mocao de (congratula|aplauso|louvor|pesar|reconhecimento|homenage|honra)", a):
            return "homenagem"
        return "homenagem" if HOMENAGEM.search(a) and not re.search(r"repudio|apelo|apoio a|apoio ao|apoio as|apoio aos", a) else "outros"
    if fam in ("resolucao", "pdl"):
        return "homenagem" if HOMENAGEM.search(a) else "outros"
    return "homenagem" if HOMENAGEM.search(a) else "lei"


def tema(assunto_sem_acento):
    for nome, rx in TEMAS:
        if re.search(rx, assunto_sem_acento):
            return nome
    return None


# ---------------------------------------------------------------- via e bairro

RX_VIA = re.compile(r"\b(Avenida|Av\.|Av\b|Rua|R\.|Estrada|Rodovia|Rod\.|Praça|Alameda|Travessa|Viela)\s+", re.I)
RX_BAIRRO = re.compile(
    r"\b(bairro|Jardim|Jd\.|Vila|Parque|Pq\.|Residencial|Conjunto Habitacional|Conjunto|Distrito de|Distrito|Núcleo|Chácara|Recanto)\s+", re.I)
TIPO_VIA = {"av.": "Avenida", "av": "Avenida", "r.": "Rua", "rod.": "Rodovia"}
TIPO_BAIRRO = {"jd.": "Jardim", "pq.": "Parque"}
LIGA = {"de", "da", "do", "dos", "das", "e"}
PARA = {"em", "no", "na", "nos", "nas", "entre", "esquina", "altura", "proximo", "proxima", "com", "ao", "a", "aos", "as",
        "n", "no.", "numero", "bairro", "defronte", "frente", "sentido", "ate", "que", "onde", "cujo", "cuja", "neste",
        "nesta", "deste", "desta", "pois", "para", "por", "sem", "sob", "sobre", "tendo", "visto", "bem", "como", "local",
        "trecho", "cruzamento", "lado", "s/n", "sn", "cep", "municipio", "cidade", "rua", "avenida", "ruas", "avenidas",
        "jardim", "vila", "parque", "residencial", "conjunto", "distrito", "o", "os", "um", "uma", "e/ou", "ou"}
ABREVIA = re.compile(r"^(dr|dra|prof|profa|pe|cel|cap|ten|sgt|cb|gen|mal|eng|sen|dep|ver|pres|gov|sta|sto|s|d|jr|cons|des|com|brig|maj|alm|[a-z])\.$", re.I)
NUMERADA = re.compile(r"^(?:[A-Z]{1,3}-?\d+[A-Z]?|\d+(?:-?[A-Z]{1,3}\d*)?)$")
ROMANO = re.compile(r"^[IVX]{1,4}$")


def _nome_apos(texto, max_palavras, liga_inicio=False):
    """Lê o nome próprio que vem logo depois do tipo de via/bairro."""
    partes = []
    for bruto in texto.split()[: max_palavras + 3]:
        termina = bool(re.search(r"[,;:\)\(]$", bruto)) or (bruto.endswith(".") and not ABREVIA.match(bruto))
        tok = bruto.strip(",;:()\"'“”").rstrip(".") if not ABREVIA.match(bruto.strip(",;:()")) else bruto.strip(",;:()")
        chave = sem_acento(tok)
        if not tok or re.match(r"^n[º°]", tok, re.I):
            break
        if chave in LIGA:
            if not partes and not (liga_inicio and chave != "e"):
                break
            partes.append(chave)
        elif chave in PARA and not (partes and NUMERADA.match(tok)):
            break
        elif tok[0].isupper() or tok[0].isdigit():
            partes.append(tok)
        else:
            break
        if termina or len(partes) >= max_palavras or (NUMERADA.match(tok) and len(partes) == 1):
            break
    while partes and partes[-1] in LIGA:
        partes.pop()
    if partes and partes[0] in LIGA and len(partes) < 2:
        return []
    return partes


def _apresenta(partes):
    out = []
    for p in partes:
        if p in LIGA:
            out.append(p)
        elif NUMERADA.match(p.upper()) or ROMANO.match(p):
            out.append(p.upper())
        elif p.isupper() and len(p) > 2:
            out.append(p.capitalize())
        else:
            out.append(p)
    return " ".join(out)


def via_de(assunto):
    """Primeira via citada no texto, normalizada ('Av. 64' → 'Avenida 64'). None se não houver."""
    for m in RX_VIA.finditer(assunto):
        partes = _nome_apos(assunto[m.end():], 6)
        if partes:
            tipo = TIPO_VIA.get(m.group(1).lower(), m.group(1).capitalize())
            return f"{tipo} {_apresenta(partes)}"
    return None


def bairro_de(assunto):
    """Bairro citado no texto ('no bairro São Miguel', 'Jardim Novo I'). None se não houver."""
    for m in RX_BAIRRO.finditer(assunto):
        prefixo = m.group(1)
        resto = assunto[m.end():]
        if prefixo.lower() == "bairro":
            m2 = RX_BAIRRO.match(resto)
            if m2 and m2.group(1).lower() != "bairro":
                prefixo, resto = m2.group(1), resto[m2.end():]
        partes = _nome_apos(resto, 5, liga_inicio=True)
        if not partes:
            continue
        nome = _apresenta(partes)
        if prefixo.lower() == "bairro":
            return nome
        if not prefixo[0].isupper():
            continue   # "parque infantil", "conjunto de…": substantivo comum, não bairro
        return f"{TIPO_BAIRRO.get(prefixo.lower(), prefixo.title())} {nome}"
    return None


def chave(texto):
    """Chave de agrupamento: 'Rua 08' = 'Rua 8', 'Rua M 22' = 'Rua M-22', 'Rua 6 A' = 'Rua 6-A'."""
    t = re.sub(r"[^a-z0-9]+", " ", sem_acento(texto)).strip()
    t = re.sub(r"\b0+(\d)", r"\1", t)
    t = re.sub(r"\b([a-z]{1,3}) (\d+)\b", r"\1\2", t)
    return re.sub(r"\b(\d+) ([a-z]{1,2})$", r"\1\2", t)


# ---------------------------------------------------------------- votações e vetos

RX_VOTO = re.compile(r"(Aprovad[oa]s?|Rejeitad[oa]s?)\b.*?(?=\s-\s(?:Aprovad|Rejeitad|Reda|Emenda|Substitutivo|Of[ií]cio)|$)", re.I | re.S)


def votos(obs):
    """Resultados de votação escritos no campo Observações (ignora redação final)."""
    out = []
    for m in RX_VOTO.finditer(obs or ""):
        antes = sem_acento(obs[max(0, m.start() - 30):m.start()])
        if "redacao final" in antes:
            continue
        l = sem_acento(m.group(0))
        contra = re.search(r"(\d+)\s+(?:votos?\s+)?contrario", l)
        fav = re.search(r"(\d+)\s+(?:votos?\s+)?favorave", l)
        n_contra = int(contra.group(1)) if contra else 0
        out.append({
            "data": de_br(m.group(0)),
            "aprovado": l.startswith("aprovad"),
            "unanime": "unanimidade" in l or n_contra == 0,
            "favoraveis": int(fav.group(1)) if fav else None,
            "contrarios": n_contra,
            "texto": m.group(0).strip()[:220],
        })
    return out


def resultado_veto(v):
    """mantido | derrubado | pendente, pelo que a câmara escreveu na situação e nas observações."""
    t = sem_acento(f"{v.get('situacao', '')} {v.get('obs', '')}")
    if re.search(r"rejeitad|derrubad", t):
        return "derrubado"
    if re.search(r"aprovad|mantid|acolhid", t):
        return "mantido"
    return "pendente"


RX_VIROU_LEI = re.compile(r"^(lei ordinaria|lei complementar|autografo|decreto legislativo|resolucao|emenda a lei organica)\b")


def desfecho(p, votacoes):
    """(aprovado?, data da última votação) de um projeto."""
    vs = [v for v in votacoes if v.get("data")]
    aprovado = any(RX_VIROU_LEI.match(sem_acento(r)) for r in p.get("relacionados", []))
    if votacoes and not aprovado:
        aprovado = all(v["aprovado"] for v in votacoes) and bool(re.search(r"public|promulg|sancion|arquivo permanente|encerrad", sem_acento(p.get("situacao", ""))))
    if any(not v["aprovado"] for v in votacoes):
        aprovado = False
    return aprovado, (max(v["data"] for v in vs) if vs else None)
