#!/usr/bin/env python3
"""Coleta os dados da câmara definida em cidade.json e grava dados/<ano-da-posse>/bruto.json.

  python scraper/coletar.py                  incremental (últimos 60 dias + projetos em tramitação)
  python scraper/coletar.py --completa       tudo desde a posse
  python scraper/coletar.py --se-necessario  só coleta se ainda não houver dados desta cidade
  python scraper/coletar.py --legislatura 2021   coleta uma legislatura passada (arquivo histórico)

A legislatura vigente é calculada pela data: posse em 1º de janeiro, a cada 4 anos.
Uma vez por semana a coleta incremental vira completa sozinha, para corrigir o que
tiver mudado em documentos antigos.
"""
import argparse
import json
import sys
import time
from datetime import date, datetime, timedelta, timezone

import config
from fontes import criar
from fontes.base import FAMILIAS_TRAMITACAO, ordenar_autores

DIAS_INCREMENTAL = 60
DIAS_ENTRE_COMPLETAS = 7
BRASILIA = timezone(timedelta(hours=-3))


def agora_br():
    """Hora de Brasília, sem fuso no texto (o servidor do GitHub roda em UTC)."""
    return datetime.now(BRASILIA).replace(tzinfo=None)


def ler(arq, cfg):
    """Dados já coletados, se forem desta mesma cidade."""
    if not arq.exists():
        return None
    try:
        d = json.loads(arq.read_text("utf-8"))
    except ValueError:
        return None
    m = d.get("meta", {})
    if m.get("slug") != cfg["slug"] or m.get("url_base") != cfg["url_base"] or m.get("formato") != 2:
        return None
    return d


def mesclar(antigas, janela, tramitacao, desde, apelidos):
    """Junta a coleta incremental com o que já existia.

    - `janela`: tudo o que foi apresentado desde `desde` (substitui o período inteiro,
      então documento excluído pela câmara some daqui também);
    - `tramitacao`: projetos de toda a legislatura (a situação deles muda com o tempo);
    - o resto vem de `antigas` como estava.
    """
    corte = desde.isoformat()
    novas = {p["id"]: p for p in janela}
    velhas = {p["id"]: p for p in antigas}
    out = dict(novas)
    for p in tramitacao:
        if p["id"] in out:
            continue
        if p["autores"] is None:
            v = velhas.get(p["id"])
            if v:
                p["autores"], p["principal"] = v["autores"], v.get("principal")
            else:
                ordenar_autores(p, apelidos)
        out[p["id"]] = p
    for p in antigas:
        if p["id"] not in out and p["data"] < corte and p["familia"] not in FAMILIAS_TRAMITACAO:
            out[p["id"]] = p
    return list(out.values())


def por_id(antigos, novos):
    d = {x["id"]: x for x in antigos or []}
    d.update({x["id"]: x for x in novos or []})
    return list(d.values())


def serializar(bruto):
    """JSON com um item por linha nas listas, para o histórico do git mostrar o que mudou a cada dia."""
    def j(x):
        return json.dumps(x, ensure_ascii=False, separators=(",", ":"))
    partes = []
    for k, v in bruto.items():
        if isinstance(v, list) and v:
            partes.append(f"{j(k)}:[\n" + ",\n".join(j(i) for i in v) + "\n]")
        else:
            partes.append(f"{j(k)}:{j(v)}")
    return "{\n" + ",\n".join(partes) + "\n}\n"


def coletar(cfg, ano, hoje, pasta_dados, completa=False, dias=DIAS_INCREMENTAL):
    inicio, fim = config.legislatura(cfg, hoje, ano)
    ate = min(hoje, fim)
    arq = pasta_dados / str(inicio.year) / "bruto.json"
    antigo = ler(arq, cfg)
    if antigo:
        ultima = datetime.fromisoformat(antigo["meta"]["coleta_completa"])
        if (agora_br() - ultima).days >= DIAS_ENTRE_COMPLETAS:
            completa = True
    completa = completa or not antigo or fim < hoje
    t0 = time.time()
    fonte = criar(cfg)
    if antigo:
        fonte.apelidos.update(antigo["meta"].get("apelidos", {}))
    print(f"{cfg['nome']}-{cfg['uf']} ({cfg['sistema']}) · legislatura {inicio.year}–{fim.year} · "
          f"coleta {'completa' if completa else f'incremental ({dias} dias)'}")

    if completa:
        props = fonte.proposituras(inicio, ate)
        respostas = fonte.respostas(inicio, ate)
    else:
        desde = max(inicio, hoje - timedelta(days=dias))
        janela = fonte.proposituras(desde, ate)
        tram = fonte.proposituras(inicio, ate, familias=FAMILIAS_TRAMITACAO)
        props = mesclar(antigo["proposituras"], janela, tram, desde, fonte.apelidos)
        novas = fonte.respostas(desde, ate)
        respostas = None if novas is None else por_id(antigo.get("respostas"), novas)
    vetos = fonte.vetos(inicio, ate)
    votacoes = fonte.votacoes(inicio, ate)

    ativos = sorted({a for p in props for a in p["autores"]})
    vereadores = fonte.vereadores(inicio, fim, ativos)
    print(f"  {len(vereadores)} vereadores ({sum(1 for v in vereadores if v['situacao'] != 'titular')} fora da lista de titulares)")

    if completa or cfg["sistema"] != "siscam":
        sessoes = fonte.sessoes(inicio, ate, conhecidas=(antigo or {}).get("sessoes"), vereadores=vereadores)
        avisos = fonte.avisos
    else:   # no SISCAM a presença depende de baixar atas: só na coleta completa
        sessoes, avisos = antigo.get("sessoes"), antigo["meta"].get("avisos", {})

    props.sort(key=lambda p: (p["data"] or "", p["id"]), reverse=True)
    agora = agora_br().isoformat(timespec="seconds")
    bruto = {
        "meta": {
            "formato": 2, "slug": cfg["slug"], "url_base": cfg["url_base"], "sistema": cfg["sistema"],
            "inicio": inicio.isoformat(), "fim": fim.isoformat(), "fechada": fim < hoje,
            "atualizado": agora, "coleta_completa": agora if completa else antigo["meta"]["coleta_completa"],
            "apelidos": fonte.apelidos, "avisos": avisos,
        },
        "vereadores": vereadores, "proposituras": props, "respostas": respostas,
        "vetos": vetos, "votacoes": votacoes, "sessoes": sessoes,
    }
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text(serializar(bruto), "utf-8")
    print(f"  {len(props)} proposituras salvas em {arq} · {fonte.http.pedidos} pedidos em {time.time() - t0:.0f}s")
    for a in avisos.values():
        print(f"  aviso: {a}")
    return bruto


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cidade", help="caminho de um cidade.json (padrão: o da raiz)")
    ap.add_argument("--saida", help="pasta raiz de saída (padrão: o repositório)")
    ap.add_argument("--completa", action="store_true")
    ap.add_argument("--se-necessario", action="store_true")
    ap.add_argument("--legislatura", type=int, metavar="ANO")
    ap.add_argument("--dias", type=int, default=DIAS_INCREMENTAL)
    a = ap.parse_args(argv)
    cfg = config.carregar(a.cidade)
    pasta_dados, _ = config.pastas(a.saida)
    hoje = agora_br().date()
    ano = a.legislatura or config.legislatura(cfg, hoje)[0].year

    if a.se_necessario and ler(pasta_dados / str(ano) / "bruto.json", cfg):
        print("já existem dados desta cidade; nada a coletar")
        return
    # virada de legislatura: a anterior recebe uma última coleta completa e vira arquivo
    if not a.legislatura and pasta_dados.exists():
        for p in sorted(pasta_dados.iterdir()):
            if p.name.isdigit() and int(p.name) < ano:
                velho = ler(p / "bruto.json", cfg)
                if velho and not velho["meta"].get("fechada"):
                    print(f"fechando a legislatura {p.name}")
                    coletar(cfg, int(p.name), hoje, pasta_dados, completa=True)
    coletar(cfg, ano, hoje, pasta_dados, completa=a.completa, dias=a.dias)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
