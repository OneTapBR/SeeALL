"""Lê a lista de presença de uma ata de sessão em PDF (quando a ata é pública).

Atas costumam trazer algo como:
  "…com a presença dos Vereadores: Fulano, Beltrano e Sicrano. Ausente o Vereador
   Zutano, com falta justificada."
A leitura é conservadora: se não achar um trecho de presença com pelo menos
metade dos vereadores, devolve None e a sessão fica fora da conta.
"""
import re

from fontes.base import sem_acento

RX_PRESENTES = re.compile(r"(presenca d[oa]s?|presentes?|compareceram|responderam a chamada)")
RX_AUSENTES = re.compile(r"(ausentes?|ausencia|nao compareceu|nao compareceram|faltou|faltaram|deixou de comparecer|deixaram de comparecer)")
RX_JUSTIFICADA = re.compile(r"justificad|licenca|licenciad|atestado|representando")


def texto_pdf(arquivo):
    import pdfplumber
    with pdfplumber.open(arquivo) as pdf:
        return "\n".join(p.extract_text() or "" for p in pdf.pages)


def _chaves(nome):
    """Formas pelas quais um vereador pode aparecer no texto."""
    n = re.sub(r"^(pr|dr|dra|prof|profa|pastor|cabo|sgt)\.?\s+", "", sem_acento(nome))
    partes = n.split()
    chaves = {n}
    if len(partes) >= 3:
        chaves.add(f"{partes[0]} {partes[-1]}")
    return [c for c in chaves if len(c) > 4]


def _quem(trecho, nomes):
    return [vid for vid, nome in nomes.items() if any(c in trecho for c in _chaves(nome))]


def extrair(texto, nomes):
    """{presentes, ausentes, justificadas} com ids de vereador, ou None se não der para ler."""
    t = re.sub(r"\s+", " ", sem_acento(texto))
    frases = re.split(r"(?<=[\.;])\s+", t)
    presentes, ausentes, justificadas = set(), set(), set()
    for f in frases:
        if RX_AUSENTES.search(f):
            # numa frase mista ("presentes A e B; ausente C"), corta no primeiro "ausente"
            ini = RX_AUSENTES.search(f).start()
            achou = _quem(f[ini:], nomes)
            (justificadas if RX_JUSTIFICADA.search(f[ini:]) else ausentes).update(achou)
            if RX_PRESENTES.search(f[:ini]):
                presentes.update(_quem(f[:ini], nomes))
        elif RX_PRESENTES.search(f):
            presentes.update(_quem(f, nomes))
        if presentes and len(presentes) + len(ausentes) + len(justificadas) >= len(nomes):
            break
    presentes -= ausentes | justificadas
    if len(presentes) < max(2, len(nomes) // 2):
        return None
    faltou = set(nomes) - presentes - justificadas
    return {"presentes": sorted(presentes), "ausentes": sorted(faltou), "justificadas": sorted(justificadas)}
