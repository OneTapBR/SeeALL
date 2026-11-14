"""Finanças (TCE-SP): leitura de valores, origem da receita e separação de folha, repasse e fornecedor."""
import pytest

from financas import mesmo_orgao, nome_orgao, origem, para_site, resumir, tipo_pagamento, valor

ORGAOS = ["PREFEITURA MUNICIPAL DE RIO CLARO", "FUNDAÇÃO MUNICIPAL DE SAUDE", "CÂMARA MUNICIPAL DE RIO CLARO",
          "DEPARTAMENTO AUTONÔMO DE ÁGUA E ESGOTO", "INSTITUTO DE PREVIDENCIA DO MUNICIPIO DE RIO CLARO"]


def test_valor():
    assert valor("39675,60") == 39675.60 and valor("-0,01") == -0.01 and valor("133,00") == 133.0
    assert valor("1.234,56") == 1234.56 and valor("") == 0.0


@pytest.mark.parametrize("alinea,esperado", [
    ("17215000 - Cota-Parte do ICMS", "estado"),
    ("17215100 - Cota-Parte do IPVA", "estado"),
    ("17115100 - Cota-Parte do Fundo de Participação dos Municípios - FPM", "uniao"),
    ("17145000 - Transferências do Salário-Educação", "uniao"),
    ("24199900 - Outras Transferências De Recursos da União e de suas Entidades", "uniao"),
    ("17515000 - Transferências de Recursos do FUNDEB", "fundeb"),
    ("11125000 - Imposto sobre a Propriedade Predial e Territorial Urbana", "proprio"),
    ("11145100 - Impostos sobre Serviços", "proprio"),
    ("13210100 - Remuneração de Depósitos Bancários", "proprio"),
    ("72150100 - Contribuição Patronal - Intraorçamentária", None),
])
def test_origem_da_receita(alinea, esperado):
    assert origem(alinea) == esperado


def test_mesmo_orgao_tolera_grafia():
    assert mesmo_orgao("DEPARTAMENTO AUTONÔMO DE ÁGUA E ESGOTO", "DEPARTAMENTO AUTONOMO DEAGUA E ESGOTO")
    assert mesmo_orgao("INSTITUTO DE PREVIDENCIA DO MUNICIPIO DE RIO CLARO", "INSTITUTO DE PREVIDENCIA MUN.DE RIO CLARO-SP")
    assert not mesmo_orgao("PREFEITURA MUNICIPAL DE RIO CLARO", "BRK AMBIENTAL - RIO CLARO S/A")
    assert not mesmo_orgao("CÂMARA MUNICIPAL DE RIO CLARO", "PREFEITURA MUNICIPAL DE RIO CLARO")


@pytest.mark.parametrize("orgao,credor,esperado", [
    ("PREFEITURA MUNICIPAL DE RIO CLARO", "PREFEITURA MUNICIPAL DE RIO CLARO", "folha"),
    ("CÂMARA MUNICIPAL DE RIO CLARO", "FOLHAS DE PAGAMENTO CAMARA RIO CLARO", "folha"),
    ("FUNDAÇÃO MUNICIPAL DE SAUDE", "FUNDACAO MUNICIPAL DE SAUDE DE RIO CLARO", "folha"),
    ("PREFEITURA MUNICIPAL DE RIO CLARO", "FUNDACAO MUNICIPAL DE SAUDE DE RIO CLARO", "interno"),
    ("CÂMARA MUNICIPAL DE RIO CLARO", "INSTITUTO DE PREVIDENCIA DO MUNICIPIO DE RIO CLARO", "interno"),
    ("PREFEITURA MUNICIPAL DE RIO CLARO", "SANCETUR - SANTA CECILIA TURISMO LTDA", "fornecedor"),
    ("FUNDAÇÃO MUNICIPAL DE SAUDE", "IRM. STA. CASA DE MISERICORDIA DE RIO CLARO", "fornecedor"),
])
def test_tipo_de_pagamento(orgao, credor, esperado):
    assert tipo_pagamento(orgao, credor, ORGAOS) == esperado


def desp(orgao, credor, v, evento="Valor Pago", doc="CNPJ - PESSOA JURÍDICA - 11111111000111"):
    return {"orgao": orgao, "evento": evento, "nm_fornecedor": credor, "id_fornecedor": doc, "vl_despesa": v}


def test_resumo_do_mes_e_agregado_do_ano():
    pm, cm = ORGAOS[0], ORGAOS[2]
    receitas = [
        {"orgao": pm, "ds_alinea": "17215000 - Cota-Parte do ICMS", "vl_arrecadacao": "1000,00"},
        {"orgao": pm, "ds_alinea": "11125000 - IPTU", "vl_arrecadacao": "500,00"},
        {"orgao": ORGAOS[4], "ds_alinea": "12150100 - Contribuição do Servidor Civil", "vl_arrecadacao": "999,00"},   # previdência: fora
    ]
    despesas = [
        desp(pm, "PREFEITURA MUNICIPAL DE RIO CLARO", "300,00"),
        desp(pm, "EMPRESA A LTDA", "200,00"), desp(cm, "EMPRESA A LTDA", "50,00"),
        desp(pm, "EMPRESA A LTDA", "999,00", evento="Empenhado"),                       # só o pago conta
        desp(pm, "FUNDACAO MUNICIPAL DE SAUDE DE RIO CLARO", "400,00"),                 # repasse interno
        desp(pm, "FULANO DE TAL", "10,00", doc="CPF - PESSOA FÍSICA - 00000000000"),    # fora do ranking
        desp(cm, "FOLHAS DE PAGAMENTO CAMARA RIO CLARO", "80,00"),
    ]
    m = resumir(receitas, despesas + [desp(ORGAOS[1], "X", "0,00")])
    assert m["receita"] == {"proprio": 500.0, "estado": 1000.0, "uniao": 0, "fundeb": 0, "outras": 0}
    assert m["pago"][pm] == 510.0 and m["folha"] == {pm: 300.0, cm: 80.0}
    assert m["repasses_internos"] == 400.0 and m["pessoas_fisicas"] == 10.0
    assert m["credores"][0][1:] == ["EMPRESA A LTDA", 250.0, pm]

    site = para_site({"meses": {"2026-01": m, "2026-02": m}}, {})
    a = site["anos"]["2026"]
    assert a["n_meses"] == 2 and a["receita"]["estado"] == 2000
    assert a["top"][0] == ["EMPRESA A LTDA", 500, "Prefeitura"]
    assert site["folha_mes"] == {"mes": "2026-02", "por_orgao": [["Prefeitura", 300], ["Câmara Municipal", 80]], "total": 380}
    assert para_site(None, {}) is None


def test_nome_curto_do_orgao():
    assert nome_orgao("PREFEITURA MUNICIPAL DE RIO CLARO") == "Prefeitura"
    assert nome_orgao("DEPARTAMENTO AUTONÔMO DE ÁGUA E ESGOTO") == "DAAE (água e esgoto)"
