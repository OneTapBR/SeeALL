"""Adaptador SAPL (Interlegis), usado por centenas de câmaras. Lê a API REST pública (/api/).

Diferenças para o SISCAM: o SAPL publica presença por sessão e o resultado numérico
de cada votação, mas não registra resposta do Executivo a requerimento.
"""
import re
from datetime import date

from .base import Fonte, familia, limpa, sem_acento


def para_propositura(m, tipo_nome, autores, base, rx_executivo):
    """Converte uma matéria da API. `autores` = {id do autor: (nome, id do parlamentar ou None)}."""
    nomes, ids = [], []
    for a in m.get("autores") or []:
        nome, parl = autores.get(a, (f"Autor {a}", None))
        nomes.append(nome)
        if parl and parl not in ids:
            ids.append(parl)
    executivo = any(rx_executivo.search(sem_acento(n)) for n in nomes) or "executivo" in sem_acento(tipo_nome)
    return {
        "id": m["id"],
        "tipo": tipo_nome,
        "familia": familia(tipo_nome),
        "titulo": f"{tipo_nome} nº {m['numero']}/{m['ano']}",
        "numero": m["numero"],
        "ano": m["ano"],
        "data": m["data_apresentacao"],
        "situacao": "Em tramitação" if m.get("em_tramitacao") else "Tramitação encerrada",
        "url": f"{base}/materia/{m['id']}",
        "autoria": nomes,
        "autores": ids,
        "principal": ids[0] if ids and autores.get((m.get("autores") or [None])[0], (None, None))[1] == ids[0] else None,
        "executivo": executivo,
        "assunto": limpa(m.get("ementa")),
        "obs": limpa(m.get("observacao")),
        "relacionados": [],
    }


def para_votacao(v, resultados):
    nome, natureza = resultados.get(v["tipo_resultado_votacao"], ("", ""))
    nao = v.get("numero_votos_nao") or 0
    return {
        "doc": v["materia"],
        "data": (v.get("data_hora") or "")[:10] or None,
        "aprovado": natureza == "A",
        "unanime": nao == 0,
        "favoraveis": v.get("numero_votos_sim"),
        "contrarios": nao,
        "texto": limpa(f"{nome}. {v.get('observacao') or ''}")[:220],
        "decisiva": natureza in ("A", "R"),
    }


class Sapl(Fonte):
    sistema = "sapl"

    def __init__(self, cfg, cliente=None):
        super().__init__(cfg, cliente)
        self.rx_exec = re.compile(cfg.get("executivo", r"prefeit|executivo"))
        self._autores = None
        self._tipos = None
        self.apelidos = {}

    def _todos(self, caminho, **params):
        """Todas as páginas de um endpoint (100 por página)."""
        params = {"page_size": 100, **params}
        out, pagina = [], 1
        while pagina:
            d = self.http.json(f"{self.base}/api/{caminho}", {**params, "page": pagina})
            out += d.get("results", [])
            pagina = (d.get("pagination") or {}).get("next_page")
        return out

    def tipos(self):
        """{id: nome} dos tipos de matéria. Com codigos_tipos no cidade.json, só esses."""
        if self._tipos is None:
            if self.cfg["codigos_tipos"]:
                self._tipos = {int(k): v for k, v in self.cfg["codigos_tipos"].items()}
            else:
                self._tipos = {t["id"]: t["descricao"] for t in self._todos("materia/tipomaterialegislativa/")}
        return self._tipos

    def autores(self):
        if self._autores is None:
            tipos_parl = {t["id"] for t in self._todos("base/tipoautor/") if sem_acento(t["descricao"]).strip() == "parlamentar"}
            self._autores = {}
            for a in self._todos("base/autor/"):
                rel = a.get("autor_related") or {}
                parl = rel.get("value") if a.get("tipo") in tipos_parl else None
                self._autores[a["id"]] = (limpa(a.get("__str__") or a.get("nome")), parl)
        return self._autores

    def _legislatura(self, inicio):
        for l in self._todos("parlamentares/legislatura/"):
            if l["data_inicio"][:4] == str(inicio.year):
                return l["id"]
        raise RuntimeError(f"o SAPL não tem legislatura começando em {inicio.year}")

    def proposituras(self, desde, ate, familias=None):
        autores = self.autores()
        props = []
        for tid, nome in self.tipos().items():
            fam = familia(nome)
            if not fam or fam == "veto" or (familias and fam not in familias):
                continue
            for m in self._todos("materia/materialegislativa/", tipo=tid,
                                 data_apresentacao__range=f"{desde.isoformat()},{ate.isoformat()}"):
                props.append(para_propositura(m, nome, autores, self.base, self.rx_exec))
        print(f"  {len(props)} matérias de {desde} a {ate}" + (f" ({', '.join(familias)})" if familias else ""))
        return props

    def vereadores(self, inicio, fim, ativos=()):
        leg = self._legislatura(inicio)
        mandatos = {}
        for m in self._todos("parlamentares/mandato/", legislatura=leg):
            mandatos.setdefault(m["parlamentar"], []).append(m)
        hoje = date.today().isoformat()
        out = []
        for p in self._todos(f"parlamentares/legislatura/{leg}/parlamentares/"):
            ms = sorted(mandatos.get(p["id"], []), key=lambda m: m.get("data_inicio_mandato") or "")
            ultimo = ms[-1] if ms else {}
            if ultimo.get("data_fim_mandato") and ultimo["data_fim_mandato"] < min(hoje, fim.isoformat()):
                situacao = "ex"
            elif ultimo.get("tipo_afastamento"):
                situacao = "licenciado"
            elif ms and not any(m.get("titular") for m in ms):
                situacao = "suplente"
            else:
                situacao = "titular"
            out.append({
                "id": p["id"], "nome": limpa(p["nome_parlamentar"]), "partido": p.get("partido") or "",
                "foto": p.get("fotografia") or "", "perfil": f"{self.base}/parlamentar/{p['id']}", "situacao": situacao,
            })
        return out

    def votacoes(self, desde, ate):
        resultados = {r["id"]: (r["nome"], r.get("natureza") or "") for r in self._todos("sessao/tiporesultadovotacao/")}
        vs = self._todos("sessao/registrovotacao/", data_hora__gte=desde.isoformat())
        out = [para_votacao(v, resultados) for v in vs if v.get("materia")]
        return [v for v in out if v.pop("decisiva")]

    def vetos(self, desde, ate):
        autores = self.autores()
        out = []
        for tid, nome in self.tipos().items():
            if familia(nome) != "veto":
                continue
            for m in self._todos("materia/materialegislativa/", tipo=tid,
                                 data_apresentacao__range=f"{desde.isoformat()},{ate.isoformat()}"):
                ementa = limpa(m.get("ementa"))
                out.append({
                    "id": m["id"], "titulo": f"{nome} nº {m['numero']}/{m['ano']}", "data": m["data_apresentacao"],
                    "tipo": "VETO PARCIAL" if "parcial" in sem_acento(ementa) else "VETO TOTAL" if "total" in sem_acento(ementa) else "",
                    "alvo": "", "alvo_id": None, "assunto": ementa, "obs": limpa(m.get("observacao") or m.get("resultado")),
                    "situacao": "Em tramitação" if m.get("em_tramitacao") else "Tramitação encerrada",
                    "url": f"{self.base}/materia/{m['id']}",
                })
        return out

    def sessoes(self, desde, ate, conhecidas=None, vereadores=()):
        tipos = {t["id"]: t["nome"] for t in self._todos("sessao/tiposessaoplenaria/")}
        feitas = {s["id"]: s for s in (conhecidas or [])}
        titulares = {v["id"] for v in vereadores if v["situacao"] in ("titular", "suplente", "licenciado")}
        out = []
        for s in self._todos("sessao/sessaoplenaria/", data_inicio__range=f"{desde.isoformat()},{ate.isoformat()}"):
            antiga = feitas.get(s["id"])
            if antiga and antiga["data"] < (date.today().replace(day=1)).isoformat():
                out.append(antiga)
                continue
            presentes = sorted({p["parlamentar"] for p in self._todos("sessao/sessaoplenariapresenca/", sessao_plenaria=s["id"])})
            if not presentes:
                continue   # sessão sem lista de presença lançada não entra na conta
            just = sorted({j["parlamentar"] for j in self._todos("sessao/justificativaausencia/", sessao_plenaria=s["id"])} - set(presentes))
            out.append({
                "id": s["id"], "nome": limpa(s["__str__"]), "data": s["data_inicio"], "tipo": tipos.get(s["tipo"], "Sessão"),
                "url": f"{self.base}/sessao/{s['id']}", "presentes": presentes, "justificadas": just,
                "ausentes": sorted(titulares - set(presentes) - set(just)),
            })
        print(f"  {len(out)} sessões com lista de presença")
        return out
