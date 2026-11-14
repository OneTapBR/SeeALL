#!/usr/bin/env python3
"""Classifica os dados brutos e gera o que o site lê.

  dados/<ano>/bruto.json  →  site/data/<ano>/radar.json   (números, carregado na abertura)
                             site/data/<ano>/docs.json    (lista de documentos, carregada sob demanda)
                             site/data/index.json         (cidade + legislaturas disponíveis)
                             site/og/*.png e site/v/<id>/ (cartões de compartilhamento)
"""
import argparse
import html
import json
import re
import shutil
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date

import config
from classificar import (CATS, TEMA_FRASE, bairro_de, categoria, chave, desfecho, resultado_veto, tema, via_de, votos)
from fontes.base import sem_acento

SISTEMAS = {"siscam": "SISCAM", "sapl": "SAPL"}
FAIXAS = [(15, "até 15 dias"), (30, "16 a 30 dias"), (60, "31 a 60 dias"), (10 ** 6, "mais de 60 dias")]


def meses_entre(inicio, fim):
    out, a, m = [], int(inicio[:4]), int(inicio[5:7])
    while f"{a:04d}-{m:02d}" <= fim[:7]:
        out.append(f"{a:04d}-{m:02d}")
        a, m = (a + 1, 1) if m == 12 else (a, m + 1)
    return out


def media(xs):
    return round(sum(xs) / len(xs), 1) if xs else None


def montar(bruto, cfg):
    """(radar, docs) a partir dos dados brutos. Função pura: não lê nem grava nada."""
    meta = bruto["meta"]
    hoje = min(meta["atualizado"][:10], meta["fim"])
    vs = bruto["vereadores"]
    ids = {v["id"] for v in vs}
    meses = meses_entre(meta["inicio"], hoje)
    idx_mes = {m: i for i, m in enumerate(meses)}
    zeros = lambda: {c: [0] * len(meses) for c in CATS}

    stats = {v["id"]: {"cats": Counter(), "principal": Counter(), "tipos": Counter(), "mensal": zeros(),
                        "temas": Counter(), "bairros": Counter(), "proj": {"total": 0, "aprovados": 0, "abertos": 0}} for v in vs}
    pref = {"mensal": [0] * len(meses), "assuntos": Counter()}
    total, mensal, temas_total = Counter(), zeros(), Counter()
    vias = defaultdict(lambda: {"n": 0, "temas": Counter(), "autores": Counter(), "datas": [], "ids": []})
    repet = defaultdict(lambda: {"n": 0, "autores": Counter(), "datas": [], "ids": []})

    vot_fonte = defaultdict(list)
    for v in bruto.get("votacoes") or []:
        vot_fonte[v["doc"]].append(v)
    tem_vot_fonte = bruto.get("votacoes") is not None

    resp_por_doc = defaultdict(list)
    for r in bruto.get("respostas") or []:
        if r.get("data"):
            resp_por_doc[r["doc"]].append(r["data"])

    docs, votacoes, projetos = [], [], {"executivo": [], "vereadores": []}
    reqs = []
    for p in bruto["proposituras"]:
        if not p.get("data") or sem_acento(p["assunto"]).startswith("excluido"):
            continue
        vts = vot_fonte.get(p["id"], []) if tem_vot_fonte else votos(p["obs"])
        for vt in vts:
            votacoes.append({**vt, "id": p["id"], "titulo": p["titulo"], "assunto": p["assunto"][:160], "data": vt.get("data") or p["data"]})
        cat = categoria(p)
        autores = [a for a in p["autores"] if a in ids]
        if p["familia"] in ("pl", "plc", "pelo") and (p["executivo"] or autores):
            aprovado, quando = desfecho(p, vts)
            aberto = not aprovado and not re.search(r"retirad|arquiv|rejeit|encerrad|prejudic", sem_acento(p["situacao"]))
            if p["executivo"]:
                if p["data"][:7] in idx_mes:
                    pref["mensal"][idx_mes[p["data"][:7]]] += 1
                pref["assuntos"][assunto_executivo(p["assunto"])] += 1
            else:
                for vid in autores:
                    pj = stats[vid]["proj"]
                    pj["total"] += 1
                    pj["aprovados"] += aprovado
                    pj["abertos"] += aberto
            projetos["executivo" if p["executivo"] else "vereadores"].append({
                "id": p["id"], "aprovado": aprovado,
                # data de votação fora do período é erro de digitação da câmara: não entra no tempo
                "dias": config.dias(p["data"], quando) if aprovado and quando and p["data"] <= quando <= hoje else None,
                "aberto": aberto,
            })
        if not autores and not p["executivo"]:
            continue
        tm = None
        if autores:
            total[cat] += 1
            im = idx_mes.get(p["data"][:7])
            if im is not None:
                mensal[cat][im] += 1
            for vid in autores:
                s = stats[vid]
                s["cats"][cat] += 1
                s["tipos"][p["tipo"]] += 1
                if im is not None:
                    s["mensal"][cat][im] += 1
            if p.get("principal") in ids:
                stats[p["principal"]]["principal"][cat] += 1
            if cat == "bairro":
                tm = tema(sem_acento(p["assunto"]))
                temas_total[tm or "Outros pedidos"] += 1
                b_doc = bairro_de(p["assunto"])
                for vid in autores:
                    stats[vid]["temas"][tm or "Outros pedidos"] += 1
                    if b_doc:
                        stats[vid]["bairros"][b_doc] += 1
                via = via_de(p["assunto"])
                if via:
                    bairro = bairro_de(p["assunto"])
                    k = (chave(via), chave(bairro) if bairro else "")
                    for d, extra in ((vias[k], None), (repet[k + (tm,)] if tm else None, tm)):
                        if d is None:
                            continue
                        d.setdefault("nomes", Counter())[(via, bairro)] += 1
                        d["n"] += 1
                        d["datas"].append(p["data"])
                        d["ids"].append(p["id"])
                        for vid in autores:
                            d["autores"][vid] += 1
                        if extra is None:
                            d["temas"][tm or "Outros pedidos"] += 1
                        else:
                            d["tema"] = extra
        doc = {"id": p["id"], "t": p["titulo"], "d": p["data"], "c": cat, "s": p["situacao"], "a": autores, "x": p["assunto"][:400]}
        if tm:
            doc["tm"] = tm
        if p["executivo"]:
            doc["e"] = 1
        if p["familia"] == "requerimento" and cat != "homenagem" and autores:
            rs = sorted(resp_por_doc.get(p["id"], []))
            if rs:
                doc["r"] = rs[0]
            doc["q"] = 1
            reqs.append((p, autores, rs[0] if rs else None))
        docs.append(doc)

    radar = {
        "cidade": {
            "nome": cfg["nome"], "uf": cfg["uf"], "titulo": cfg["titulo_site"], "slug": cfg["slug"],
            "fonte": cfg["url_base"], "sistema": SISTEMAS.get(cfg["sistema"], cfg["sistema"]),
            "repositorio": cfg.get("repositorio", ""),
        },
        "legislatura": {"ano": int(meta["inicio"][:4]), "inicio": meta["inicio"], "fim": meta["fim"], "encerrada": bool(meta.get("fechada"))},
        "atualizado": f"{config.para_br(meta['atualizado'][:10])} {meta['atualizado'][11:16]}",
        "doc_url": cfg["url_base"] + ("/materia/" if cfg["sistema"] == "sapl" else "/Documentos/Documento/"),
        "total": {c: total.get(c, 0) for c in CATS},
        "meses": meses,
        "mensal": [mensal[c] for c in CATS],
        "temas": temas_total.most_common(),
        "vias": _vias(vias),
        "repetidos": _repetidos(repet),
        "votacoes": _votacoes(votacoes),
        "executivo": {
            "respostas": _respostas(reqs, hoje, cfg["prazo_resposta_dias"], stats),
            "vetos": _vetos(bruto.get("vetos")),
            "projetos": {k: _projetos(v) for k, v in projetos.items()} if projetos["executivo"] else None,
        },
        "presenca": _presenca(bruto.get("sessoes"), vs, stats),
        "prefeito": {**{k: (cfg.get("prefeito") or {}).get(k, "") for k in ("nome", "partido", "foto")},
                     "mensal": pref["mensal"], "assuntos": pref["assuntos"].most_common()} if projetos["executivo"] else None,
        "avisos": meta.get("avisos", {}),
    }
    em_exercicio = [v for v in vs if v["situacao"] == "titular"] or vs
    radar["media"] = {c: round(sum(stats[v["id"]]["cats"].get(c, 0) for v in em_exercicio) / max(len(em_exercicio), 1), 1) for c in CATS}
    radar["vereadores"] = []
    for v in vs:
        s = stats[v["id"]]
        o = {**v, "cats": {c: s["cats"].get(c, 0) for c in CATS}, "principal": {c: s["principal"].get(c, 0) for c in CATS},
             "tipos": dict(s["tipos"]), "mensal": [s["mensal"][c] for c in CATS],
             "temas": s["temas"].most_common(8), "bairros": s["bairros"].most_common(8), "proj": s["proj"]}
        for extra in ("resp", "presenca"):
            if extra in s:
                o[extra] = s[extra]
        radar["vereadores"].append(o)
    return radar, docs


ASSUNTOS_EXECUTIVO = [
    ("Orçamento e créditos", r"credito|orcament|diretrizes orcament|plurianual|suplementa"),
    ("Servidores e cargos", r"servidor|cargo|reajuste|subsidio|venciment|quadro de pessoal|gratifica"),
    ("Convênios e repasses", r"convenio|repasse|subvenc|termo de|parceria|consorcio"),
    ("Imóveis e concessões", r"doac|permiss|concess|aliena|desafeta|imovel|area"),
    ("Tributos e taxas", r"tribut|imposto|taxa|tarifa|isenc|iptu|refis|divida"),
]


def assunto_executivo(assunto):
    a = sem_acento(assunto)
    for nome, rx in ASSUNTOS_EXECUTIVO:
        if re.search(rx, a):
            return nome
    return "Outros assuntos"


def _nomes(grupos):
    """Escolhe a grafia mais comum de cada via/bairro ('Rua 8', não 'Rua 08')."""
    for d in grupos:
        d["via"], d["bairro"] = d["nomes"].most_common(1)[0][0]
    return grupos


def _vias(vias):
    _nomes(vias.values())
    top = sorted(vias.values(), key=lambda d: (-d["n"], d["via"]))[:40]
    return [{"via": d["via"], "bairro": d["bairro"], "n": d["n"], "temas": d["temas"].most_common(3),
             "autores": d["autores"].most_common(3), "primeiro": min(d["datas"]), "ultimo": max(d["datas"]),
             "ids": d["ids"][:150]} for d in top]


def _repetidos(repet):
    _nomes(repet.values())
    top = sorted((d for d in repet.values() if d["n"] >= 3), key=lambda d: (-d["n"], d["via"]))[:40]
    return [{"via": d["via"], "bairro": d["bairro"], "tema": d["tema"], "frase": TEMA_FRASE.get(d["tema"], d["tema"].lower()),
             "n": d["n"], "autores": d["autores"].most_common(3), "primeiro": min(d["datas"]), "ultimo": max(d["datas"]),
             "ids": d["ids"][:150]} for d in top]


def _votacoes(votacoes):
    divididas = sorted((v for v in votacoes if not v["unanime"]), key=lambda v: v["data"] or "", reverse=True)
    return {"total": len(votacoes), "unanimes": sum(1 for v in votacoes if v["unanime"]), "divididas": divididas[:300]}


def _respostas(reqs, hoje, prazo, stats):
    """Requerimentos × respostas do Executivo registradas no sistema."""
    respondidos = [(p, a, r) for p, a, r in reqs if r]
    if not respondidos:
        return None
    # só conta a partir do primeiro requerimento que teve resposta registrada: antes disso
    # a câmara não lançava as respostas no sistema, e "sem resposta" seria injusto
    desde = min(p["data"] for p, _, _ in respondidos)
    base = [(p, a, r) for p, a, r in reqs if p["data"] >= desde]
    tempos, faixas = [], Counter()
    n_resp = n_atraso = n_prazo = 0
    por_ver = defaultdict(lambda: {"pedidos": 0, "respondidos": 0, "atrasados": 0, "tempos": []})
    for p, autores, r in base:
        if r:
            n_resp += 1
            d = max(config.dias(p["data"], r), 0)
            tempos.append(d)
            faixas[next(nome for lim, nome in FAIXAS if d <= lim)] += 1
        elif config.dias(p["data"], hoje) > prazo:
            n_atraso += 1
        else:
            n_prazo += 1
        for vid in autores:
            pv = por_ver[vid]
            pv["pedidos"] += 1
            if r:
                pv["respondidos"] += 1
                pv["tempos"].append(d)
            elif config.dias(p["data"], hoje) > prazo:
                pv["atrasados"] += 1
    for vid, pv in por_ver.items():
        stats[vid]["resp"] = {"pedidos": pv["pedidos"], "respondidos": pv["respondidos"], "atrasados": pv["atrasados"],
                              "tempo": media(pv["tempos"])}
    vencidos = n_resp + n_atraso
    return {
        "desde": desde, "prazo": prazo, "total": len(base), "respondidos": n_resp, "atrasados": n_atraso, "no_prazo": n_prazo,
        "taxa": round(n_resp / vencidos * 100) if vencidos else None,
        "tempo_medio": media(tempos), "tempo_mediano": statistics.median(tempos) if tempos else None,
        "faixas": [[nome, faixas.get(nome, 0)] for _, nome in FAIXAS],
        "ranking": sorted(([vid, pv["atrasados"], pv["pedidos"]] for vid, pv in por_ver.items() if pv["atrasados"]),
                          key=lambda x: -x[1]),
    }


def _vetos(vetos):
    if vetos is None:
        return None
    lista = [{"id": v["id"], "titulo": v["titulo"], "data": v["data"], "tipo": v["tipo"].title(), "alvo": v["alvo"],
              "assunto": v["assunto"][:300], "resultado": resultado_veto(v), "url": v["url"]}
             for v in sorted(vetos, key=lambda v: v["data"] or "", reverse=True)]
    c = Counter(v["resultado"] for v in lista)
    return {"total": len(lista), "mantidos": c["mantido"], "derrubados": c["derrubado"], "pendentes": c["pendente"], "lista": lista}


def _projetos(ps):
    ap = [p for p in ps if p["aprovado"]]
    tempos = [p["dias"] for p in ap if p["dias"] is not None]
    return {"total": len(ps), "aprovados": len(ap), "abertos": sum(1 for p in ps if p["aberto"]),
            "tempo_medio": media(tempos), "tempo_mediano": statistics.median(tempos) if tempos else None,
            "ids": [p["id"] for p in ps]}


def _presenca(sessoes, vs, stats):
    if not sessoes:
        return None
    sessoes = sorted(sessoes, key=lambda s: s["data"])
    pres = {s["id"]: set(s["presentes"]) for s in sessoes}
    just = {s["id"]: set(s.get("justificadas") or []) for s in sessoes}
    faltas = defaultdict(list)
    por_ver = []
    for v in vs:
        vid = v["id"]
        minhas = [s for s in sessoes if vid in pres[s["id"]]]
        if not minhas:
            continue
        # titular responde por todas as sessões; quem entrou ou saiu no meio (suplente, ex),
        # só pelas sessões entre a primeira e a última em que esteve presente
        esperadas = sessoes if v["situacao"] == "titular" else [s for s in sessoes if minhas[0]["data"] <= s["data"] <= minhas[-1]["data"]]
        j = sum(1 for s in esperadas if vid in just[s["id"]] and vid not in pres[s["id"]])
        for s in esperadas:
            if vid not in pres[s["id"]]:
                faltas[s["id"]].append([vid, 1 if vid in just[s["id"]] else 0])
        p = sum(1 for s in esperadas if vid in pres[s["id"]])
        stats[vid]["presenca"] = {"p": p, "t": len(esperadas), "j": j}
        por_ver.append([vid, p, len(esperadas), j])
    return {
        "total": len(sessoes),
        "por_vereador": sorted(por_ver, key=lambda x: (-(x[1] / x[2]), x[0])),
        "sessoes": [{"id": s["id"], "nome": s["nome"], "data": s["data"], "tipo": s.get("tipo", ""), "url": s["url"],
                     "faltas": faltas.get(s["id"], [])} for s in sessoes],
    }


# ---------------------------------------------------------------- arquivos do site

def bloco_meta(cfg, radar, site_url):
    t = radar["total"]
    tit = cfg["titulo_site"]
    desc = (f"O que cada vereador de {cfg['nome']}-{cfg['uf']} apresentou desde a posse, contado todo dia a partir "
            f"dos dados oficiais da Câmara.")
    e = html.escape
    linhas = [
        f"<title>{e(tit)} — o que cada vereador fez desde a posse</title>",
        f'<meta name="description" content="{e(desc)}">',
        f'<meta property="og:title" content="{e(tit)}">',
        f'<meta property="og:description" content="{e(desc)}">',
        '<meta property="og:type" content="website">',
        '<meta name="twitter:card" content="summary_large_image">',
    ]
    if site_url:
        linhas += [f'<meta property="og:url" content="{e(site_url)}/">', f'<meta property="og:image" content="{e(site_url)}/og/home.png">']
    return "\n".join(linhas)


def gravar_meta(pasta_site, bloco):
    """Troca o trecho entre os marcadores radar:meta do index.html (título e tags de compartilhamento)."""
    arq = pasta_site / "index.html"
    txt = arq.read_text("utf-8")
    novo = re.sub(r"(<!-- radar:meta -->\n).*?(\n<!-- /radar:meta -->)", lambda m: m.group(1) + bloco + m.group(2), txt, flags=re.S)
    if novo != txt:
        arq.write_text(novo, "utf-8")


def paginas_de_vereador(pasta_site, cfg, radar, site_url):
    """site/v/<id>/index.html: página mínima com as tags de compartilhamento, que redireciona pro perfil."""
    raiz = pasta_site / "v"
    if raiz.exists():
        shutil.rmtree(raiz)
    e = html.escape
    for v in radar["vereadores"]:
        c = v["cats"]
        n = sum(c.values())
        desc = (f"{n} documentos desde a posse: {c['lei']} propostas de lei, {c['homenagem']} homenagens, "
                f"{c['bairro']} pedidos nos bairros, {c['cobranca']} perguntas e cobranças.")
        img = f'<meta property="og:image" content="{e(site_url)}/og/{v["id"]}.png">\n' if site_url else ""
        d = raiz / str(v["id"])
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(v['nome'].title())} — {e(cfg['titulo_site'])}</title>
<meta name="description" content="{e(desc)}">
<meta property="og:title" content="{e(v['nome'].title())} — {e(cfg['titulo_site'])}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:type" content="profile">
{img}<meta name="twitter:card" content="summary_large_image">
<meta http-equiv="refresh" content="0; url=../../#/vereador/{v['id']}">
<script>location.replace("../../#/vereador/{v['id']}")</script>
</head>
<body><p><a href="../../#/vereador/{v['id']}">Ver o mandato de {e(v['nome'].title())} no {e(cfg['titulo_site'])}</a></p></body>
</html>
""", "utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cidade")
    ap.add_argument("--saida")
    ap.add_argument("--sem-cartoes", action="store_true", help="não gera as imagens de compartilhamento")
    a = ap.parse_args(argv)
    cfg = config.carregar(a.cidade)
    pasta_dados, pasta_site = config.pastas(a.saida)
    if a.saida:   # saída alternativa (teste de outra cidade): leva junto os arquivos estáticos
        shutil.copytree(config.RAIZ / "site", pasta_site, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("data", "og", "v", "CNAME"))
    from coletar import ler
    legs, atual = [], None
    saida_dados = pasta_site / "data"
    if saida_dados.exists():
        shutil.rmtree(saida_dados)
    for p in sorted(pasta_dados.iterdir()) if pasta_dados.exists() else []:
        bruto = ler(p / "bruto.json", cfg) if p.name.isdigit() else None
        if not bruto:
            continue
        radar, docs = montar(bruto, cfg)
        d = saida_dados / p.name
        d.mkdir(parents=True, exist_ok=True)
        (d / "radar.json").write_text(json.dumps(radar, ensure_ascii=False, separators=(",", ":")), "utf-8")
        (d / "docs.json").write_text(json.dumps(docs, ensure_ascii=False, separators=(",", ":")), "utf-8")
        legs.append(radar["legislatura"])
        atual = radar
        print(f"legislatura {p.name}: {sum(radar['total'].values())} documentos de vereadores · {dict(radar['total'])}")
    if not atual:
        raise SystemExit("não há dados coletados para esta cidade; rode scraper/coletar.py primeiro")
    (saida_dados / "index.json").write_text(json.dumps(
        {"cidade": atual["cidade"], "atual": atual["legislatura"]["ano"], "legislaturas": legs,
         "financas": (pasta_dados / "financas.json").exists() and bool(cfg.get("tce_sp"))}, ensure_ascii=False), "utf-8")

    import financas
    arq_fin = pasta_dados / "financas.json"
    fin = financas.para_site(json.loads(arq_fin.read_text("utf-8")), cfg) if arq_fin.exists() and cfg.get("tce_sp") else None
    if fin:
        (saida_dados / "financas.json").write_text(json.dumps(fin, ensure_ascii=False, separators=(",", ":")), "utf-8")
        print(f"finanças até {fin['ultimo_mes']}: folha do mês R$ {fin['folha_mes']['total']:,.0f}")
    site_url = config.url_site(cfg)
    gravar_meta(pasta_site, bloco_meta(cfg, atual, site_url))
    paginas_de_vereador(pasta_site, cfg, atual, site_url)
    cname = pasta_site / "CNAME"
    if cfg.get("dominio"):
        cname.write_text(cfg["dominio"].strip("/") + "\n", "utf-8")
    elif cname.exists():
        cname.unlink()
    if not a.sem_cartoes:
        try:
            from cartoes import gerar_cartoes
            n = gerar_cartoes(pasta_site / "og", cfg, atual)
            print(f"{n} cartões de compartilhamento em {pasta_site / 'og'}")
        except Exception as e:   # cartão é enfeite: não derruba a publicação
            print(f"aviso: não gerei os cartões de compartilhamento ({e})", file=sys.stderr)
    r = atual["executivo"]["respostas"]
    if r:
        print(f"respostas do Executivo: {r['respondidos']} de {r['respondidos'] + r['atrasados']} vencidos ({r['taxa']}%), média {r['tempo_medio']} dias")
    print("votações:", atual["votacoes"]["total"], "· unânimes:", atual["votacoes"]["unanimes"])
    print("vias:", [(v["via"], v["bairro"], v["n"]) for v in atual["vias"][:6]])


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
