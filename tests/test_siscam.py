"""Parser do SISCAM contra páginas reais salvas de rioclaro.siscam.com.br."""
import re

from conftest import html
from configurar import codigo, eh_siscam, menu_siscam, nome_da_camara, tipos_do_select
from fontes.base import familia
from fontes.siscam import (autores_vereadores, eh_coletivo, ids_da_lista, ler_formulario, ler_lista, ler_vereadores,
                           para_propositura)

BASE = "https://rioclaro.siscam.com.br"
RX = re.compile(r"prefeit|executivo")


def test_lista_de_projetos():
    itens = ler_lista(html("lista_projetos.html"))
    assert len(itens) == 15
    p = para_propositura(itens[0], "Projeto de Lei", BASE, RX)
    assert p["id"] == 84379 and p["titulo"] == "Projeto de Lei Nº 142/2026"
    assert (p["numero"], p["ano"], p["data"]) == (142, 2026, "2026-11-11")
    assert p["familia"] == "pl" and p["situacao"] == "SECRETARIA"
    assert p["autoria"] == ["TIEMI NEVOEIRO"] and not p["executivo"]
    assert p["assunto"].startswith("Altera a Lei Complementar nº 160")
    assert p["url"] == f"{BASE}/Documentos/Documento/84379"


def test_documentos_relacionados():
    itens = {i["titulo"]: i for i in ler_lista(html("lista_projetos.html"))}
    rel = itens["Projeto de Lei Nº 139/2026"]["relacionados"]
    assert (84330, "Parecer de Comissões Conjunta Nº 1/2026 ao Projeto de Lei Nº 139/2026") in rel
    assert len(rel) == 5


def test_coautoria_vem_em_campo_separado():
    """Autoria e Coautoria são campos diferentes; os dois contam como autores."""
    itens = {i["titulo"]: i for i in ler_lista(html("lista_coautoria.html"))}
    p = para_propositura(itens["Moção Nº 184/2026"], "Moção", BASE, RX)
    assert p["autoria"][0] == "FERNANDO DO NORDESTE"
    assert "SERGIO CARNEVALE" in p["autoria"] and "RAFAEL HENRIQUE ANDREETA" in p["autoria"]
    assert len(p["autoria"]) == 19
    assert not any("Coautoria" in n for n in p["autoria"])


def test_ids_da_lista_bate_com_o_parser_completo():
    for nome in ("lista_projetos.html", "lista_coautoria.html", "lista_requerimentos.html"):
        assert ids_da_lista(html(nome)) == [i["id"] for i in ler_lista(html(nome))]


def test_pagina_sem_resultado():
    assert ler_lista(html("lista_vazia.html")) == []
    assert ids_da_lista(html("lista_vazia.html")) == []


def test_respostas_apontam_para_o_requerimento():
    itens = ler_lista(html("lista_respostas.html"))
    assert len(itens) == 15
    r = itens[0]
    assert r["titulo"] == "Resposta Nº 5 ao Requerimento Nº 1117/2026"
    assert r["principal"] == (79829, "Requerimento Nº 1117/2026")
    assert r["campos"]["Data"] == "13/11/2026"


def test_vetos():
    itens = ler_lista(html("lista_vetos.html"))
    assert len(itens) == 3
    v = itens[0]
    assert v["titulo"].startswith("Veto Nº 1/2026 ao Projeto de Lei Nº 66/2026")
    assert v["campos"]["Tipo"] == "VETO TOTAL" and v["campos"]["Autoria"] == "PREFEITO MUNICIPAL"
    assert v["principal"][1] == "Projeto de Lei Nº 66/2026"


def test_projeto_do_prefeito_e_marcado_como_executivo():
    item = {"id": 1, "titulo": "Projeto de Lei Nº 134/2026", "relacionados": [], "principal": None,
            "campos": {"Tipo": "Executivo", "Data": "19/10/2026", "Autoria": "PREFEITO MUNICIPAL", "Assunto": "Crédito"}}
    assert para_propositura(item, "Projeto de Lei", BASE, RX)["executivo"]


def test_vereadores_atuais():
    vs = ler_vereadores(html("vereadores.html"), BASE)
    assert len(vs) == 19                      # 20 itens na página, 1 é a autoria coletiva "VEREADORES"
    assert not any(eh_coletivo(v["nome"]) for v in vs)
    assert vs[0] == {"id": 13, "nome": "ADRIANO LA TORRE", "partido": "PROGRESSISTAS",
                     "foto": f"{BASE}/Vereadores/Foto/13", "perfil": f"{BASE}/Vereadores/Vereador/13"}


def test_vereadores_anteriores_sem_foto():
    vs = {v["id"]: v for v in ler_vereadores(html("vereadores_anteriores.html"), BASE)}
    assert vs[43]["nome"] == "AGNELO DA SILVA MATOS NETO" and vs[43]["partido"] == "PT" and vs[43]["foto"] == ""
    assert vs[30]["foto"].endswith("/Vereadores/Foto/30")


def test_formulario_de_pesquisa():
    form = ler_formulario(html("pesquisa_proposituras.html"))
    assert form["ocultos"]["Modulo"] == "8" and form["ocultos"]["id"] == "80"
    tipos = tipos_do_select(form)
    assert tipos["141"] == "Indicações" and tipos["135"] == "Projetos de Lei" and len(tipos) == 8
    assert {familia(n) for n in tipos.values()} == {"indicacao", "mocao", "pdl", "pelo", "pl", "plc", "resolucao", "requerimento"}


def test_autores_do_formulario_sao_so_vereadores():
    autores = autores_vereadores(ler_formulario(html("pesquisa_proposituras.html")))
    assert autores[13] == "ADRIANO LA TORRE"          # atual
    assert autores[47] == "DALBERTO CHRISTOFOLETTI"   # anterior, mas apresentou documento nesta legislatura
    assert 74 not in autores                          # "VEREADORES" (coletivo)
    assert 2097 not in autores and 2161 not in autores   # Mesa Diretora e comissões
    assert len(autores) == 55


def test_configurar_detecta_siscam():
    home = html("home.html")
    assert eh_siscam(home)
    assert menu_siscam(home) == {"proposituras": (80, 8), "subdocumentos": (87, 8)}
    assert nome_da_camara("Câmara Municipal de Rio Claro - Consulta") == "Rio Claro"
    sub = ler_formulario(html("pesquisa_subdocumentos.html"))
    assert codigo(sub, r"^respostas?$") == 130 and codigo(sub, r"^vetos?$") == 131
