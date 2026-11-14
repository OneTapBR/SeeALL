#!/usr/bin/env python3
"""Descobre o sistema da câmara e grava o cidade.json.

  python scraper/configurar.py https://suacidade.siscam.com.br --uf SP
  python scraper/configurar.py https://sapl.suacidade.uf.leg.br

Detecta SISCAM (rodapé "SINO Informática" ou links /Documentos/Pesquisa) e SAPL
(/api/ respondendo em JSON), lê os códigos dos tipos de documento, testa uma
página de resultados e escreve o arquivo. Confira o resultado antes de publicar.
"""
import argparse
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

import config
from fontes.base import familia, limpa, sem_acento
from fontes.siscam import ler_formulario, ler_lista, ler_vereadores
from rede import Cliente


def slug(nome, uf):
    return re.sub(r"[^a-z0-9]+", "-", sem_acento(f"{nome} {uf}")).strip("-")


def nome_da_camara(texto):
    """'Câmara Municipal de Rio Claro - Consulta' → 'Rio Claro'."""
    m = re.search(r"C[âa]mara\s+(?:Municipal\s+)?(?:de\s+Vereadores\s+)?d[eoa]s?\s+([^-–|/]+)", texto or "", re.I)
    return limpa(m.group(1)) if m else ""


def eh_siscam(html):
    return bool(re.search(r"SINO\s+Inform[áa]tica|/Documentos/Pesquisa|siscam", html, re.I))


def menu_siscam(html):
    """Ids dos módulos no menu: {'proposituras': (80, 8), 'subdocumentos': (87, 8)}."""
    out = {}
    for a in BeautifulSoup(html, "lxml").find_all("a", href=re.compile(r"^/index/\d+/\d+$", re.I)):
        t = sem_acento(a.get_text())
        idm, mod = (int(x) for x in a["href"].split("/")[2:4])
        if re.search(r"propositura|materia|projeto", t) and "proposituras" not in out:
            out["proposituras"] = (idm, mod)
        elif re.search(r"sub-?documento", t):
            out["subdocumentos"] = (idm, mod)
    return out


def tipos_do_select(form):
    """{código: nome} dos tipos do select Documento que o radar sabe classificar."""
    return {v: t for v, t, _ in form["selects"].get("Documento", []) if v.isdigit() and int(v) and familia(t)}


def codigo(form, padrao):
    for v, t, _ in (form or {"selects": {}})["selects"].get("Documento", []):
        if v.isdigit() and re.search(padrao, sem_acento(t)):
            return int(v)
    return None


def configurar_siscam(base, http, home):
    menu = menu_siscam(home)
    if "proposituras" not in menu:
        raise SystemExit("é um SISCAM, mas não achei o módulo de proposituras no menu")
    idp, mod = menu["proposituras"]
    form = ler_formulario(http.html(f"{base}/index/{idp}/{mod}"))
    if not form:
        raise SystemExit("não achei o formulário de pesquisa avançada")
    tipos = tipos_do_select(form)
    if not tipos:
        raise SystemExit("o formulário não tem tipos de documento que eu reconheça")
    s = {"modulo": int(form["ocultos"].get("Modulo") or mod), "id_proposituras": idp}
    if "subdocumentos" in menu:
        ids = menu["subdocumentos"][0]
        sub = ler_formulario(http.html(f"{base}/index/{ids}/{mod}"))
        s["id_subdocumentos"] = ids
        for chave, rx in (("tipo_resposta", r"^respostas?$"), ("tipo_veto", r"^vetos?$")):
            c = codigo(sub, rx)
            if c:
                s[chave] = c
    vs = ler_vereadores(http.html(f"{base}/vereadores"), base)
    if vs:   # o tipo "Ata da Sessão" só aparece na página de contagem de um vereador
        cont = BeautifulSoup(http.html(f"{base}/Vereadores/Contagem/{vs[0]['id']}"), "lxml").find("select", attrs={"name": "Documento"})
        for o in cont.find_all("option") if cont else []:
            if re.search(r"^atas? da sessao", sem_acento(o.get_text())) and o.get("value", "").isdigit():
                s["tipo_ata"] = int(o["value"])
    # teste: uma página de resultados dos últimos 90 dias
    hoje = date.today()
    cod = next(iter(tipos))
    url = (f"{base}/Documentos/Pesquisa/{idp}?Pesquisa=Avancada&id={idp}&Modulo={s['modulo']}&Documento={cod}&Numeracao=Documento"
           f"&DataInicial={(hoje - timedelta(days=90)).strftime('%d/%m/%Y')}&DataFinal={hoje.strftime('%d/%m/%Y')}&Pagina=1")
    itens = ler_lista(http.html(url))
    print(f"  teste: {len(itens)} itens de '{tipos[cod]}' nos últimos 90 dias" + (f" (ex.: {itens[0]['titulo']})" if itens else ""))
    print(f"  {len(vs)} vereadores na lista atual")
    return {"sistema": "siscam", "codigos_tipos": tipos, "siscam": s}


def configurar_sapl(base, http):
    casa = (http.json(f"{base}/api/base/casalegislativa/").get("results") or [{}])[0]
    tipos = http.json(f"{base}/api/materia/tipomaterialegislativa/", {"page_size": 100}).get("results", [])
    cods = {str(t["id"]): t["descricao"] for t in tipos if familia(t["descricao"])}
    if not cods:
        raise SystemExit("o SAPL respondeu, mas sem tipos de matéria que eu reconheça")
    d = http.json(f"{base}/api/materia/materialegislativa/", {"page_size": 1, "o": "-data_apresentacao"})
    n = (d.get("pagination") or {}).get("total_entries")
    print(f"  teste: {n} matérias no SAPL" + (f" (a mais recente: {d['results'][0]['__str__']})" if d.get("results") else ""))
    return {"sistema": "sapl", "codigos_tipos": cods, "_nome": casa.get("municipio", ""), "_uf": casa.get("uf", "")}


def detectar(url, http=None):
    """Devolve o dicionário do cidade.json (sem gravar)."""
    http = http or Cliente()
    p = urlsplit(url if "//" in url else "https://" + url)
    base = f"{p.scheme}://{p.netloc}"
    home = http.html(base + "/")
    if eh_siscam(home):
        print(f"SISCAM detectado em {base}")
        cfg = configurar_siscam(base, http, home)
        soup = BeautifulSoup(home, "lxml")
        cfg["_nome"] = nome_da_camara(soup.title.get_text() if soup.title else "") or nome_da_camara(soup.get_text(" "))
    else:
        try:
            cfg = configurar_sapl(base, http)
            print(f"SAPL detectado em {base}")
        except SystemExit:
            raise
        except Exception:
            raise SystemExit(f"não reconheci o sistema de {base}: não é SISCAM (rodapé SINO Informática) nem SAPL (/api/). "
                             "Se a câmara usa outro sistema, é preciso escrever um adaptador em scraper/fontes/.")
    cfg["url_base"] = base
    return cfg


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url", help="endereço do sistema legislativo da câmara")
    ap.add_argument("--nome", help="nome da cidade (se não der para descobrir sozinho)")
    ap.add_argument("--uf", help="sigla do estado")
    ap.add_argument("--dominio", default="", help="domínio próprio do site, se tiver (ex.: radarminhacidade.com.br)")
    ap.add_argument("--saida", default=str(config.RAIZ / "cidade.json"))
    a = ap.parse_args(argv)
    d = detectar(a.url)
    nome = a.nome or d.pop("_nome", "")
    uf = (a.uf or d.pop("_uf", "")).upper()
    d.pop("_nome", None), d.pop("_uf", None)
    if not nome or not uf:
        raise SystemExit("não consegui descobrir o nome da cidade ou o estado: rode de novo com --nome \"Sua Cidade\" --uf UF")
    cfg = {
        "nome": nome, "uf": uf, "slug": slug(nome, uf), "titulo_site": f"Radar {nome}",
        "sistema": d["sistema"], "url_base": d["url_base"], "posse_inicial": "2025-01-01", "dominio": a.dominio,
        "codigos_tipos": d["codigos_tipos"],
    }
    if "siscam" in d:
        cfg["siscam"] = d["siscam"]
    cfg.update({"mesclar_autores": {}, "prazo_resposta_dias": 30, "repositorio": ""})
    Path(a.saida).write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(f"\n{a.saida} gravado:")
    print(f"  {nome}-{uf} · {cfg['sistema']} · {len(cfg['codigos_tipos'])} tipos de documento: {', '.join(cfg['codigos_tipos'].values())}")
    print("Confira o arquivo, faça o commit e rode o workflow \"Atualizar dados e publicar\".")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
