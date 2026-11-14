"""Regras de classificação: categoria, tema, via, bairro, votação e veto."""
import pytest

from classificar import bairro_de, categoria, resultado_veto, tema, via_de, votos
from fontes.base import familia, sem_acento


def doc(tipo, assunto):
    return {"tipo": tipo, "familia": familia(tipo), "assunto": assunto}


@pytest.mark.parametrize("tipo,assunto,esperado", [
    ("Indicação", "Sugerindo determinar à Secretaria Municipal de Obras que realize o serviço de tapa-buracos na Avenida 64", "bairro"),
    ("Requerimento", "Oficiar ao Senhor Prefeito solicitando a poda da árvore localizada na Avenida 3-JN, nº 77", "bairro"),
    ("Requerimento", "Requer informações sobre o cronograma de obras da UPA da Avenida 29", "cobranca"),
    ("Requerimento", "Requer que seja consignado em ata voto de pesar pelo falecimento do Sr. João", "homenagem"),
    ("Requerimento", "Oficiar ao Senhor Prefeito para que estude a criação de um grupo de trabalho", "cobranca"),
    ("Moção", "MOÇÃO DE CONGRATULAÇÕES E LOUVOR - Ao Senhor Pedro Henrique Bisson", "homenagem"),
    ("Moção", "Moção de Repúdio à decisão do Governo do Estado", "outros"),
    ("Moção", "Moção de Apelo ao Governador para a duplicação da rodovia", "outros"),
    ("Projeto de Lei", "Institui a Política Municipal de Proteção ao Nascituro", "lei"),
    ("Projeto de Lei", "Denomina de Rua José da Silva a atual Rua 12 do Jardim Novo", "homenagem"),
    ("Projeto de Lei", "Institui o Dia Municipal do Ciclista no calendário oficial", "homenagem"),
    ("Projeto de Lei Complementar", "Altera o Código Tributário do Município", "lei"),
    ("Projeto de Emenda à Lei Orgânica", "Altera o artigo 12 da Lei Orgânica", "lei"),
    ("Projeto de Decreto Legislativo", "Confere a Medalha de Honra ao Mérito ao Senhor Valter", "homenagem"),
    ("Projeto de Decreto Legislativo", "Confere o Título de Cidadão Rio-Clarense ao Senhor Fulano", "homenagem"),
    ("Projeto de Decreto Legislativo", "Susta parcialmente o Decreto Municipal 13.960", "outros"),
    ("Projeto de Resolução", "Altera o Regimento Interno da Câmara", "outros"),
    # nomes de tipo do SAPL
    ("Moção Aplausos", "AO SENHOR FULANO PELOS SERVIÇOS PRESTADOS", "homenagem"),
    ("Pesar", "PELO FALECIMENTO DO SENHOR FULANO", "homenagem"),
    ("Moção de Protesto", "CONTRA O FECHAMENTO DA AGÊNCIA", "outros"),
    ("Projeto de Lei Ordinária do Legislativo", "DISPÕE SOBRE A CRIAÇÃO DO PROGRAMA", "lei"),
])
def test_categoria(tipo, assunto, esperado):
    assert categoria(doc(tipo, assunto)) == esperado


@pytest.mark.parametrize("nome,esperado", [
    ("Indicações", "indicacao"), ("Requerimento Solicitação", "requerimento"), ("Moção de Congratulação", "mocao"),
    ("Pesar", "mocao"), ("Projetos de Lei Complementar", "plc"), ("Projeto de Lei Complementar do Executivo", "plc"),
    ("Proposta de Emenda à Lei Orgânica Municipal", "pelo"), ("Projetos de Decreto Legislativo", "pdl"),
    ("Projeto de Resolução", "resolucao"), ("Veto Total ou Parcial", "veto"),
    ("Parecer", None), ("Substitutivo", None), ("Mensagem", None), ("Emendas", None), ("Respostas", None),
])
def test_familia(nome, esperado):
    assert familia(nome) == esperado


@pytest.mark.parametrize("texto,esperado", [
    ("realize o serviço de tapa-buracos na Avenida 64, nº 1688", "Buracos e asfalto"),
    ("a poda da árvore localizada na Rua 4", "Poda e mato"),
    ("troca de lâmpada queimada", "Iluminação"),
    ("implantação de lombada na Rua 12", "Trânsito e sinalização"),
    ("conserto do vazamento de água", "Água e esgoto"),
    ("providências quanto ao barulho", None),
])
def test_tema(texto, esperado):
    assert tema(sem_acento(texto)) == esperado


@pytest.mark.parametrize("texto,esperado", [
    ("tapa-buracos na Avenida 64, nº 1688, entre as Ruas 17 e 18-A, no bairro São Miguel.", "Avenida 64"),
    ("poda da árvore localizada na Avenida 3-JN, nº 77, entre as Ruas 1-JN e 2-JN", "Avenida 3-JN"),
    ("limpeza na Rua M-21 esquina com a Avenida M-19", "Rua M-21"),
    ("na Av. 29 com a Rua 9", "Avenida 29"),
    ("iluminação na Avenida Presidente Kennedy em frente ao número 500", "Avenida Presidente Kennedy"),
    ("na Rua Dr. Eloy Chaves, próximo à escola", "Rua Dr. Eloy Chaves"),
    ("REPAROS NA RUA JOSE DE SANTANA EM FRENTE AO NUMERO 470", "Rua Jose de Santana"),
    ("moradores da rua sem saída reclamam", None),
    ("providências sobre os semáforos da cidade", None),
])
def test_via(texto, esperado):
    assert via_de(texto) == esperado


@pytest.mark.parametrize("texto,esperado", [
    ("na Avenida 64, nº 1688, entre as Ruas 17 e 18-A, no bairro São Miguel.", "São Miguel"),
    ("na Avenida 3-JN, nº 77, no bairro Jardim Novo I, cujos galhos", "Jardim Novo I"),
    ("na Rua 12, Jardim das Palmeiras, em frente à praça", "Jardim das Palmeiras"),
    ("na Rua 3 da Vila Alemã.", "Vila Alemã"),
    ("na Rua 6, Pq. Universitário", "Parque Universitário"),
    ("reforma do parque infantil da Rua 9", None),
    ("na Avenida 1, Centro", None),
])
def test_bairro(texto, esperado):
    assert bairro_de(texto) == esperado


def test_votos_das_observacoes():
    obs = ("- Aprovado por 16 votos favoráveis em 1ª Discussão na Sessão Ordinária do dia 03/11/2026 - Maioria Absoluta "
           "- Aprovado por 15 votos favoráveis e 01 contrário em 2ª Discussão na Sessão Ordinária do dia 09/11/2026 - Maioria Absoluta "
           "- Redação Final - Aprovada por Unanimidade.")
    vs = votos(obs)
    assert len(vs) == 2                                   # redação final não entra
    assert (vs[0]["data"], vs[0]["aprovado"], vs[0]["unanime"], vs[0]["favoraveis"], vs[0]["contrarios"]) == ("2026-11-03", True, True, 16, 0)
    assert vs[1]["contrarios"] == 1 and not vs[1]["unanime"] and vs[1]["data"] == "2026-11-09"
    assert votos("") == []
    assert votos("Rejeitado por 10 votos contrários e 8 favoráveis")[0]["aprovado"] is False


@pytest.mark.parametrize("situacao,obs,esperado", [
    ("APROVADA", "VETO APROVADO NA SESSÃO ORDINÁRIA DO DIA 17/08/2026.", "mantido"),
    ("Em Andamento", "Veto Parcial ao Autógrafo nº 5534 - Aprovado por 18 votos favoráveis em Discussão e Votação Única", "mantido"),
    ("Rejeitada", "Veto rejeitado por 14 votos", "derrubado"),
    ("Em Andamento", "", "pendente"),
])
def test_resultado_do_veto(situacao, obs, esperado):
    assert resultado_veto({"situacao": situacao, "obs": obs}) == esperado
