"""Legislaturas, coleta incremental, geração dos números e leitura de presença em ata."""
from datetime import date

import config
from coletar import mesclar
from gerar import meses_entre, montar
from presenca_ata import extrair

CFG = {"nome": "Rio Claro", "uf": "SP", "titulo_site": "Radar Rio Claro", "slug": "rio-claro-sp", "sistema": "siscam",
       "url_base": "https://x.siscam.com.br", "posse_inicial": "2025-01-01", "prazo_resposta_dias": 30}


def test_legislatura_vigente():
    assert config.legislatura(CFG, date(2025, 1, 1)) == (date(2025, 1, 1), date(2028, 12, 31))
    assert config.legislatura(CFG, date(2026, 11, 14))[0].year == 2025
    assert config.legislatura(CFG, date(2028, 12, 31))[0].year == 2025
    assert config.legislatura(CFG, date(2029, 1, 1)) == (date(2029, 1, 1), date(2032, 12, 31))
    assert config.legislatura(CFG, date(2024, 6, 1))[0].year == 2021      # antes da base também funciona
    assert config.legislatura(CFG, ano=2021) == (date(2021, 1, 1), date(2024, 12, 31))


def test_datas():
    assert config.de_br("Data: 13/11/2026") == "2026-11-13"
    assert config.de_br("31/02/2026") is None and config.de_br("") is None
    assert config.para_br("2026-11-13") == "13/11/2026" and config.dias("2026-01-01", "2026-01-31") == 30
    assert meses_entre("2025-11-01", "2026-02-10") == ["2025-11", "2025-12", "2026-01", "2026-02"]


def prop(i, data, fam="indicacao", tipo="Indicação", assunto="tapa-buracos na Rua 4, no bairro Centro", autores=(1,), **k):
    return {"id": i, "tipo": tipo, "familia": fam, "titulo": f"{tipo} Nº {i}/2026", "numero": i, "ano": 2026, "data": data,
            "situacao": "Em Andamento", "url": "", "autoria": ["A"], "autores": list(autores),
            "principal": autores[0] if autores else None, "executivo": False, "assunto": assunto, "obs": "",
            "relacionados": [], **k}


def test_mesclar_incremental():
    antigas = [prop(1, "2026-01-10"), prop(2, "2026-10-20"), prop(3, "2026-10-25"),
               prop(4, "2026-02-01", "pl", "Projeto de Lei", "Institui", situacao="Em Andamento na C. Finanças")]
    janela = [prop(3, "2026-10-25", assunto="texto corrigido"), prop(5, "2026-11-01")]     # o 2 foi excluído pela câmara
    tram = [dict(prop(4, "2026-02-01", "pl", "Projeto de Lei", "Institui", situacao="Arquivo Permanente"), autores=None)]
    out = {p["id"]: p for p in mesclar(antigas, janela, tram, date(2026, 9, 15), {})}
    assert sorted(out) == [1, 3, 4, 5]
    assert out[3]["assunto"] == "texto corrigido"
    assert out[4]["situacao"] == "Arquivo Permanente" and out[4]["autores"] == [1]   # autoria preservada


def bruto(props, **extra):
    return {"meta": {"inicio": "2025-01-01", "fim": "2028-12-31", "atualizado": "2026-11-14T07:00:00", "avisos": {}},
            "vereadores": [{"id": 1, "nome": "ANA SILVA", "partido": "X", "foto": "", "perfil": "", "situacao": "titular"},
                           {"id": 2, "nome": "BETO SOUZA", "partido": "Y", "foto": "", "perfil": "", "situacao": "fora"}],
            "proposituras": props, "respostas": None, "vetos": None, "votacoes": None, "sessoes": None, **extra}


def test_montar_totais_ruas_e_repetidos():
    props = [prop(i, f"2026-0{i}-05") for i in (1, 2, 3)]
    props += [prop(4, "2026-03-10", assunto="troca de lâmpada na Rua 4, no bairro Centro", autores=(1, 2)),
              prop(5, "2026-03-11", "mocao", "Moção", "MOÇÃO DE CONGRATULAÇÕES ao Sr. Fulano", autores=(2,)),
              prop(6, "2026-03-12", "pl", "Projeto de Lei", "Institui programa", autores=(), executivo=True),
              prop(7, "2026-03-13", assunto="Excluído")]
    radar, docs = montar(bruto(props), CFG)
    assert radar["total"] == {"bairro": 4, "cobranca": 0, "homenagem": 1, "lei": 0, "outros": 0}
    v1, v2 = radar["vereadores"]
    assert v1["cats"]["bairro"] == 4 and v2["cats"] == {"bairro": 1, "cobranca": 0, "homenagem": 1, "lei": 0, "outros": 0}
    assert radar["media"]["bairro"] == 4.0                       # média só dos titulares
    via = radar["vias"][0]
    assert (via["via"], via["bairro"], via["n"]) == ("Rua 4", "Centro", 4)
    rep = radar["repetidos"]
    assert len(rep) == 1 and (rep[0]["tema"], rep[0]["n"]) == ("Buracos e asfalto", 3)
    assert radar["meses"][0] == "2025-01" and radar["meses"][-1] == "2026-11"
    assert radar["mensal"][0][radar["meses"].index("2026-03")] == 2
    assert {d["id"] for d in docs} == {1, 2, 3, 4, 5, 6}          # excluído fica fora; o do prefeito entra na lista
    assert radar["executivo"]["projetos"]["executivo"]["total"] == 1
    assert radar["executivo"]["respostas"] is None and radar["presenca"] is None


def test_montar_respostas_do_executivo():
    def req(i, data):
        return prop(i, data, "requerimento", "Requerimento", "Requer informações sobre a obra")
    props = [req(1, "2025-06-01"),            # antes de a câmara registrar respostas: fora da conta
             req(2, "2026-03-01"), req(3, "2026-03-10"), req(4, "2026-04-01"), req(5, "2026-11-01")]
    respostas = [{"id": 90, "doc": 2, "data": "2026-03-11", "titulo": ""}, {"id": 91, "doc": 3, "data": "2026-04-19", "titulo": ""},
                 {"id": 92, "doc": 3, "data": "2026-05-30", "titulo": ""}]
    radar, docs = montar(bruto(props, respostas=respostas), CFG)
    r = radar["executivo"]["respostas"]
    assert r["desde"] == "2026-03-01" and r["total"] == 4
    assert (r["respondidos"], r["atrasados"], r["no_prazo"]) == (2, 1, 1)
    assert r["taxa"] == 67 and r["tempo_medio"] == 25.0           # 10 e 40 dias (vale a primeira resposta)
    assert r["ranking"] == [[1, 1, 4]]
    assert radar["vereadores"][0]["resp"] == {"pedidos": 4, "respondidos": 2, "atrasados": 1, "tempo": 25.0}
    assert {d["id"]: d.get("r") for d in docs}[3] == "2026-04-19"


def test_montar_presenca():
    def s(i, data, presentes, justificadas=()):
        return {"id": i, "nome": f"{i}ª", "data": data, "tipo": "Ordinária", "url": "", "presentes": presentes, "justificadas": list(justificadas)}
    sessoes = [s(1, "2026-02-02", [1]), s(2, "2026-02-09", [1, 2]), s(3, "2026-02-16", [2], [1]), s(4, "2026-02-23", [1])]
    radar, _ = montar(bruto([prop(1, "2026-02-01")], sessoes=sessoes), CFG)
    p = radar["presenca"]
    assert p["total"] == 4
    assert [1, 3, 4, 1] in p["por_vereador"]        # titular: 3 de 4, 1 justificada
    assert [2, 2, 2, 0] in p["por_vereador"]        # suplente: só conta entre a 1ª e a última em que esteve
    assert p["sessoes"][2]["faltas"] == [[1, 1]] and p["sessoes"][3]["faltas"] == []


def test_presenca_em_ata():
    nomes = {1: "ADRIANO LA TORRE", 2: "Pr. DIEGO GONZALEZ", 3: "JOSÉ PEREIRA DOS SANTOS", 4: "NÉIA GARCIA"}
    ata = ("Aos nove dias do mês de novembro, reuniu-se a Câmara, com a presença dos Vereadores: Adriano La Torre, "
           "Diego Gonzalez e José Pereira dos Santos. Ausente a Vereadora Néia Garcia, com falta justificada por atestado. "
           "Em seguida passou-se ao Expediente.")
    assert extrair(ata, nomes) == {"presentes": [1, 2, 3], "ausentes": [], "justificadas": [4]}
    assert extrair("Ata sem lista de nomes. Foram aprovados os requerimentos.", nomes) is None
