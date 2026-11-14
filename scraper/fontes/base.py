"""Interface comum das fontes de dados.

Cada sistema (SISCAM, SAPL…) implementa esta classe e devolve sempre o mesmo
formato, para que coletar.py, gerar.py e o site não precisem saber de onde veio.

Formatos (datas sempre em ISO, AAAA-MM-DD):

vereador    {id, nome, partido, foto, perfil, situacao}
            situacao: titular | suplente | licenciado | ex | fora
            ("fora" = apresentou documento no período mas não está na lista atual
             e o sistema não diz se é suplente ou ex-vereador)
propositura {id, tipo, familia, titulo, numero, ano, data, situacao, url,
             autoria: [nomes], autores: [ids de vereador] ou None, executivo: bool,
             assunto, obs, relacionados: [títulos]}
            familia: indicacao | requerimento | mocao | pl | plc | pelo | pdl | resolucao
votacao     {doc, data, aprovado, unanime, favoraveis, contrarios, texto}
resposta    {id, doc, data, titulo}          (resposta do Executivo a um requerimento)
veto        {id, titulo, data, tipo, alvo, assunto, obs, situacao, url}
sessao      {id, nome, data, tipo, url, presentes: [ids] ou None, justificadas: [ids]}
"""
import re
import unicodedata

from rede import Cliente

FAMILIAS_TRAMITACAO = ("pl", "plc", "pelo", "pdl", "resolucao")

_REGRAS_FAMILIA = [
    ("veto", r"\bveto"),
    ("indicacao", r"indicac"),
    ("requerimento", r"requerimento"),
    ("mocao", r"\bmocao|\bmocoes|\bpesar\b"),
    ("pdl", r"decreto legislativo"),
    ("resolucao", r"projetos? de resoluc"),
    ("pelo", r"emenda a lei organica"),
    ("plc", r"lei complementar"),
    ("pl", r"projetos? de lei"),
]
_NAO_E_PROPOSITURA = re.compile(r"^(parecer|substitutivo|emenda|subemenda|mensagem|autografo|redac|relatorio|resposta)")


def sem_acento(t):
    return "".join(c for c in unicodedata.normalize("NFD", t or "") if unicodedata.category(c) != "Mn").lower()


def limpa(t):
    return re.sub(r"\s+", " ", t or "").strip()


def familia(nome_tipo):
    """Descobre a família de um tipo de documento pelo nome ('Projetos de Lei' → 'pl')."""
    n = sem_acento(nome_tipo).strip()
    if _NAO_E_PROPOSITURA.match(n):
        return None
    for fam, rx in _REGRAS_FAMILIA:
        if re.search(rx, n):
            return fam
    return None


def ordenar_autores(p, apelidos):
    """Põe o autor principal (primeiro nome da autoria) na frente e resolve autoria sem id.

    `apelidos` = {nome impresso na autoria: id do vereador}.
    """
    if p.get("autores") is None:
        achados = []
        for n in p["autoria"]:
            i = apelidos.get(n)
            if i and i not in achados:
                achados.append(i)
        p["autores"] = achados
    principal = apelidos.get(p["autoria"][0]) if p["autoria"] else None
    if principal in p["autores"]:
        p["autores"].remove(principal)
        p["autores"].insert(0, principal)
        p["principal"] = principal
    else:
        p.setdefault("principal", None)
    return p


class Fonte:
    sistema = ""

    def __init__(self, cfg, cliente=None):
        self.cfg = cfg
        self.base = cfg["url_base"]
        self.http = cliente or Cliente()
        #: frases para o README/site quando algum dado não pôde ser obtido
        self.avisos = {}

    def vereadores(self, inicio, fim):
        raise NotImplementedError

    def proposituras(self, desde, ate, familias=None):
        raise NotImplementedError

    def votacoes(self, desde, ate):
        """None = a fonte não tem registro próprio; gerar.py lê das observações."""
        return None

    def respostas(self, desde, ate):
        return None

    def vetos(self, desde, ate):
        return None

    def sessoes(self, desde, ate, conhecidas=None):
        return None
