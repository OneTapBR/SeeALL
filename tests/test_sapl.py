"""Adaptador SAPL contra respostas reais salvas da API de sapl.patosdeminas.mg.leg.br."""
import re

from conftest import api
from fontes.base import familia
from fontes.sapl import para_propositura, para_votacao

BASE = "https://sapl.patosdeminas.mg.leg.br"
RX = re.compile(r"prefeit|executivo")


def test_materia_do_executivo():
    m = api("materias")["results"][0]
    autores = {12: ("Executivo Municipal - Prefeito Municipal", None)}
    p = para_propositura(m, "Projeto de Lei Complementar do Executivo", autores, BASE, RX)
    assert p["id"] == 32391 and p["familia"] == "plc" and p["executivo"]
    assert p["titulo"] == "Projeto de Lei Complementar do Executivo nº 1014/2026"
    assert p["data"] == "2026-11-13" and p["autores"] == [] and p["situacao"] == "Em tramitação"
    assert p["url"] == f"{BASE}/materia/32391"


def test_materia_de_vereador_usa_o_id_do_parlamentar():
    m = dict(api("materias")["results"][0], autores=[17, 12])
    autores = {17: ("Abílio Gomes Ferreira", 73), 12: ("Executivo Municipal - Prefeito Municipal", None)}
    p = para_propositura(m, "Indicação", autores, BASE, RX)
    assert p["autores"] == [73] and p["principal"] == 73 and p["autoria"][0] == "Abílio Gomes Ferreira"


def test_tipos_do_sapl_tem_familia():
    nomes = {t["descricao"]: familia(t["descricao"]) for t in api("tipos")["results"]}
    assert nomes["Indicação"] == "indicacao" and nomes["Requerimento Solicitação"] == "requerimento"
    assert nomes["Projeto de Lei Ordinária do Executivo"] == "pl" and nomes["Veto Total ou Parcial"] == "veto"
    assert nomes["Parecer"] is None and nomes["Substitutivo"] is None and nomes["Mensagem"] is None


def test_votacao_com_placar():
    resultados = {r["id"]: (r["nome"], r.get("natureza") or "") for r in api("resultados")["results"]}
    v = para_votacao(api("votacoes")["results"][0], resultados)
    assert v["doc"] == 32221 and v["aprovado"] and v["decisiva"]
    assert (v["favoraveis"], v["contrarios"], v["unanime"]) == (13, 2, False)
    assert v["data"] == "2026-11-05"
