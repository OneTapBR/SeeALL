#!/usr/bin/env python3
"""Receitas e despesas do município, da API de dados abertos do TCE-SP.

  https://transparencia.tce.sp.gov.br/api/json/receitas/<municipio>/<ano>/<mes>
  https://transparencia.tce.sp.gov.br/api/json/despesas/<municipio>/<ano>/<mes>

Só para municípios paulistas (cidade.json → "tce_sp": "rio-claro"). O TCE publica
com cerca de dois meses de atraso. Cada mês vira um resumo pequeno em
dados/financas.json; os três últimos meses publicados são relidos a cada coleta,
porque o tribunal ainda recebe correções.

O que a API traz e o que não traz:
- receita por órgão, fonte de recurso e alínea (dá para saber o que veio da União,
  do Estado e o que é arrecadação própria);
- despesa por empenho, com órgão, credor e valor (dá para saber quem recebeu, mas
  não a função/secretaria nem o objeto do gasto);
- a folha de pagamento aparece como pagamento do órgão a si mesmo ou a um credor
  chamado "folha de pagamento". Não há remuneração individual.
"""
import argparse
import html
import json
import re
import sys
from collections import defaultdict
from datetime import date, datetime

import config
from fontes.base import limpa, sem_acento
from rede import Cliente

API = "https://transparencia.tce.sp.gov.br/api/json"
ORIGENS = ["proprio", "estado", "uniao", "fundeb", "outras"]
IGNORA = {"de", "do", "da", "dos", "das", "e", "municipal", "municipio", "mun", "sp", "sa", "ltda", "me"}
MESES_RELER = 3


def valor(txt):
    """'39675,60' → 39675.6 (a API não usa separador de milhar)."""
    try:
        return float(str(txt).replace(".", "").replace(",", ".")) if "," in str(txt) else float(txt)
    except ValueError:
        return 0.0


def origem(alinea):
    """De onde veio a receita, pelo código da natureza (alínea)."""
    c = re.sub(r"\D", "", alinea.split(" - ")[0])
    if c[:1] in ("7", "8"):
        return None                      # intraorçamentária: dinheiro que só troca de bolso
    if c[:3] in ("171", "241"):
        return "uniao"
    if c[:3] in ("172", "242"):
        return "estado"
    if c[:3] == "175":
        return "fundeb"
    if c[:2] in ("17", "24"):
        return "outras"
    return "proprio"


def _palavras(nome):
    t = re.sub(r"[^a-z0-9]+", " ", sem_acento(html.unescape(nome)))
    return {p for p in t.split() if p not in IGNORA and len(p) > 1}


def mesmo_orgao(a, b):
    """'DEPARTAMENTO AUTONÔMO DE ÁGUA E ESGOTO' × 'DEPARTAMENTO AUTONOMO DEAGUA E ESGOTO' → True."""
    pa, pb = _palavras(a), _palavras(b)
    return bool(pa and pb) and len(pa & pb) / min(len(pa), len(pb)) >= 0.7


def tipo_pagamento(orgao, credor, orgaos):
    """folha | interno | fornecedor."""
    c = sem_acento(credor)
    if re.search(r"folhas? de pagamento", c) or mesmo_orgao(orgao, credor):
        return "folha"
    if any(mesmo_orgao(o, credor) for o in orgaos):
        return "interno"                 # repasse entre órgãos do próprio município
    return "fornecedor"


def resumir(receitas, despesas):
    """Resumo de um mês a partir das linhas cruas da API."""
    rec = defaultdict(float)
    alineas = defaultdict(float)
    for r in receitas:
        if "previd" in sem_acento(r["orgao"]):
            continue                     # contribuição previdenciária não é receita para gastar
        o = origem(r["ds_alinea"])
        if not o:
            continue
        v = valor(r["vl_arrecadacao"])
        rec[o] += v
        alineas[(o, limpa(html.unescape(r["ds_alinea"].split(" - ", 1)[-1])))] += v
    orgaos = sorted({d["orgao"] for d in despesas})
    pago, folha, credores = defaultdict(float), defaultdict(float), {}
    interno = pf = 0.0
    for d in despesas:
        if d["evento"] != "Valor Pago":
            continue
        v = valor(d["vl_despesa"])
        t = tipo_pagamento(d["orgao"], d["nm_fornecedor"], orgaos)
        if t == "interno":
            interno += v
            continue
        pago[d["orgao"]] += v
        if t == "folha":
            folha[d["orgao"]] += v
        elif "CNPJ" not in d["id_fornecedor"]:
            pf += v                      # pessoa física: entra no total, não no ranking
        else:
            k = re.sub(r"\D", "", d["id_fornecedor"])
            c = credores.setdefault(k, {"nome": limpa(html.unescape(d["nm_fornecedor"])), "v": 0.0, "orgaos": defaultdict(float)})
            c["v"] += v
            c["orgaos"][d["orgao"]] += v
    top = sorted(credores.items(), key=lambda kv: -kv[1]["v"])[:120]
    r2 = lambda x: round(x, 2)
    return {
        "receita": {o: r2(rec.get(o, 0)) for o in ORIGENS},
        "alineas": [[o, n, r2(v)] for (o, n), v in sorted(alineas.items(), key=lambda kv: -kv[1])[:40]],
        "pago": {o: r2(v) for o, v in pago.items()},
        "folha": {o: r2(v) for o, v in folha.items()},
        "pessoas_fisicas": r2(pf), "repasses_internos": r2(interno),
        "credores": [[k, c["nome"], r2(c["v"]), max(c["orgaos"], key=c["orgaos"].get)] for k, c in top],
    }


def coletar(cfg, inicio, hoje, pasta_dados, http=None):
    mun = cfg.get("tce_sp")
    if not mun:
        return None
    http = http or Cliente(pausa=0.3, tempo=180)
    arq = pasta_dados / "financas.json"
    dados = {"municipio": mun, "meses": {}}
    if arq.exists():
        velho = json.loads(arq.read_text("utf-8"))
        if velho.get("municipio") == mun:
            dados = velho
    feitos = sorted(dados["meses"])
    reler = set(feitos[-MESES_RELER:])
    ano, mes, vazios = inicio.year, inicio.month, 0
    while (ano, mes) <= (hoje.year, hoje.month):
        chave = f"{ano:04d}-{mes:02d}"
        if chave not in dados["meses"] or chave in reler:
            rec = http.json(f"{API}/receitas/{mun}/{ano}/{mes}")
            desp = http.json(f"{API}/despesas/{mun}/{ano}/{mes}")
            if rec or desp:
                dados["meses"][chave] = resumir(rec, desp)
                print(f"  finanças {chave}: {len(rec)} receitas, {len(desp)} lançamentos de despesa")
                vazios = 0
            else:
                vazios += 1
                if vazios >= 2 and (ano, mes) >= (hoje.year, hoje.month - 3):
                    break                # ainda não publicado
        ano, mes = (ano + 1, 1) if mes == 12 else (ano, mes + 1)
    dados["meses"] = dict(sorted(dados["meses"].items()))
    dados["atualizado"] = datetime.now().isoformat(timespec="seconds")
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text(json.dumps(dados, ensure_ascii=False, indent=0, separators=(",", ":")), "utf-8")
    return dados


def nome_orgao(o):
    """'PREFEITURA MUNICIPAL DE RIO CLARO' → 'Prefeitura'."""
    s = sem_acento(o)
    for chave, nome in (("prefeitura", "Prefeitura"), ("camara", "Câmara Municipal"), ("saude", "Fundação de Saúde"),
                        ("agua", "DAAE (água e esgoto)"), ("previd", "Instituto de Previdência"), ("arquivo", "Arquivo Público")):
        if chave in s:
            return nome
    return limpa(o).title()


def para_site(dados, cfg):
    """Agrega por ano o que o site mostra (função pura)."""
    if not dados or not dados.get("meses"):
        return None
    anos = {}
    for chave, m in dados["meses"].items():
        a = anos.setdefault(chave[:4], {"meses": [], "receita": defaultdict(float), "alineas": defaultdict(float),
                                        "pago": defaultdict(float), "folha": defaultdict(float), "credores": {}, "pf": 0.0})
        a["meses"].append(chave)
        for o, v in m["receita"].items():
            a["receita"][o] += v
        for o, n, v in m["alineas"]:
            a["alineas"][(o, n)] += v
        for o, v in m["pago"].items():
            a["pago"][nome_orgao(o)] += v
        for o, v in m["folha"].items():
            a["folha"][nome_orgao(o)] += v
        a["pf"] += m["pessoas_fisicas"]
        for k, nome, v, org in m["credores"]:
            c = a["credores"].setdefault(k, {"nome": nome, "v": 0.0, "orgaos": defaultdict(float)})
            c["v"] += v
            c["orgaos"][nome_orgao(org)] += v
    r0 = lambda x: round(x)
    saida = {}
    for ano, a in anos.items():
        top = sorted(a["credores"].values(), key=lambda c: -c["v"])[:30]
        saida[ano] = {
            "de": a["meses"][0], "ate": a["meses"][-1], "n_meses": len(a["meses"]),
            "receita": {o: r0(a["receita"].get(o, 0)) for o in ORIGENS},
            "alineas": [[o, n, r0(v)] for (o, n), v in sorted(a["alineas"].items(), key=lambda kv: -kv[1])[:14]],
            "pago": sorted(([o, r0(v)] for o, v in a["pago"].items()), key=lambda x: -x[1]),
            "folha": sorted(([o, r0(v)] for o, v in a["folha"].items()), key=lambda x: -x[1]),
            "pessoas_fisicas": r0(a["pf"]),
            "top": [[c["nome"], r0(c["v"]), max(c["orgaos"], key=c["orgaos"].get)] for c in top],
        }
    ultimo = sorted(dados["meses"])[-1]
    m = dados["meses"][ultimo]
    folha_mes = sorted(([nome_orgao(o), r0(v)] for o, v in m["folha"].items()), key=lambda x: -x[1])
    return {
        "fonte": "https://transparencia.tce.sp.gov.br/", "ultimo_mes": ultimo, "anos": saida,
        "folha_mes": {"mes": ultimo, "por_orgao": folha_mes, "total": sum(v for _, v in folha_mes)},
        "subsidios": cfg.get("subsidios") or None,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cidade")
    ap.add_argument("--saida")
    a = ap.parse_args(argv)
    cfg = config.carregar(a.cidade)
    pasta_dados, _ = config.pastas(a.saida)
    hoje = date.today()
    if not cfg.get("tce_sp"):
        print("cidade.json sem \"tce_sp\": finanças não coletadas (só há fonte pronta para municípios de SP)")
        return
    inicio, _ = config.legislatura(cfg, hoje)
    d = coletar(cfg, inicio, hoje, pasta_dados)
    print(f"finanças: {len(d['meses'])} meses, até {sorted(d['meses'])[-1]}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
