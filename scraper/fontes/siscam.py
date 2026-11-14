"""Adaptador SISCAM (SINO Informática), o sistema usado pela Câmara de Rio Claro-SP.

O SISCAM não tem API: tudo é lido das páginas públicas de pesquisa avançada
(/Documentos/Pesquisa/<id>?Pesquisa=Avancada…), 15 itens por página.

Duas passadas:
1. por tipo de documento, para ter o conteúdo de cada propositura;
2. por autor (campo AutoriaId), só para saber de quem é cada documento. O nome
   impresso na autoria muda com o tempo (nome civil × nome parlamentar), então
   casar por texto perde documentos; o id do autor não muda.
"""
import io
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date

from bs4 import BeautifulSoup

from config import de_br
from .base import Fonte, familia, limpa, ordenar_autores, sem_acento

POR_PAGINA = 15
RX_ID_LISTA = re.compile(r'<h4>\s*<a href="/Documentos/Documento/(\d+)"')


# ---------------------------------------------------------------- leitura de HTML (funções puras)

def _campos(item):
    """{rótulo: texto} de um item da lista ('Data', 'Situação', 'Autoria'…)."""
    out = {}
    for st in item.find_all("strong"):
        rotulo = limpa(st.get_text()).rstrip(":")
        if not rotulo or rotulo in out:
            continue
        txt = limpa(st.parent.get_text(" "))
        cab = limpa(st.get_text())
        out[rotulo] = txt.split(cab, 1)[1].strip() if cab in txt else txt
    return out


def _links(item, rotulo):
    """[(id, título)] dos documentos ligados a um rótulo ('Documentos Relacionados')."""
    for st in item.find_all("strong"):
        if limpa(st.get_text()).rstrip(":") == rotulo:
            return [(int(a["href"].rsplit("/", 1)[1]), limpa(a.get_text()))
                    for a in st.parent.find_all("a", href=re.compile(r"/Documentos/Documento/\d+$"))]
    return []


def _nomes(txt):
    return [n.strip() for n in (txt or "").split(",") if n.strip()]


def ler_lista(html):
    """Itens de uma página de resultado, ainda sem interpretação."""
    soup = BeautifulSoup(html, "lxml")
    itens = []
    for it in soup.select("div.data-list-item"):
        a = it.find("h4").find("a", href=re.compile(r"/Documentos/Documento/\d+$")) if it.find("h4") else None
        if not a:
            continue
        itens.append({
            "id": int(a["href"].rsplit("/", 1)[1]),
            "titulo": limpa(a.get_text()),
            "campos": _campos(it),
            "relacionados": _links(it, "Documentos Relacionados"),
            "principal": (_links(it, "Documento Principal") or [None])[0],
        })
    return itens


def ids_da_lista(html):
    return [int(i) for i in RX_ID_LISTA.findall(html)]


def para_propositura(item, tipo, base, rx_executivo):
    c = item["campos"]
    m = re.search(r"N[ºo°]\s*(\d+)\s*/\s*(\d{4})", item["titulo"])
    autoria = _nomes(c.get("Autoria")) + _nomes(c.get("Coautoria"))
    return {
        "id": item["id"],
        "tipo": tipo,
        "familia": familia(tipo),
        "titulo": item["titulo"],
        "numero": int(m.group(1)) if m else None,
        "ano": int(m.group(2)) if m else None,
        "data": de_br(c.get("Data")),
        "situacao": c.get("Situação", ""),
        "url": f"{base}/Documentos/Documento/{item['id']}",
        "autoria": autoria,
        "autores": None,
        "executivo": any(rx_executivo.search(sem_acento(n)) for n in autoria) or sem_acento(c.get("Tipo", "")) == "executivo",
        "assunto": c.get("Assunto", ""),
        "obs": c.get("Observações", ""),
        "relacionados": [t for _, t in item["relacionados"]],
    }


def ler_vereadores(html, base):
    """Vereadores de /vereadores ou /vereadores/Anteriores: [{id, nome, partido}]."""
    soup = BeautifulSoup(html, "lxml")
    out, vistos = [], set()
    for it in soup.select("#content div.data-list-item"):
        a = it.find("h4").find("a", href=re.compile(r"/Vereadores/Vereador/\d+$")) if it.find("h4") else None
        if not a:
            continue
        vid = int(a["href"].rsplit("/", 1)[1])
        nome = limpa(a.get_text())
        if vid in vistos or not nome or eh_coletivo(nome):
            continue
        vistos.add(vid)
        out.append({
            "id": vid, "nome": nome, "partido": _campos(it).get("Partido", ""),
            "foto": f"{base}/Vereadores/Foto/{vid}" if it.find("img") else "",
            "perfil": f"{base}/Vereadores/Vereador/{vid}",
        })
    return out


def eh_coletivo(nome):
    """'VEREADORES' é uma autoria coletiva cadastrada como se fosse pessoa."""
    return sem_acento(nome).strip() in ("vereadores", "vereador", "todos os vereadores")


def ler_formulario(html):
    """Campos do formulário de pesquisa avançada.

    Devolve {"ocultos": {nome: valor}, "selects": {nome: [(valor, texto, grupo)]}}.
    """
    soup = BeautifulSoup(html, "lxml")
    for form in soup.find_all("form"):
        p = form.find("input", attrs={"name": "Pesquisa"})
        if not p or p.get("value") != "Avancada":
            continue
        ocultos = {i.get("name"): i.get("value") for i in form.find_all("input", type="hidden") if i.get("name")}
        selects = {}
        for sel in form.find_all("select"):
            ops = []
            for o in sel.find_all("option"):
                g = o.find_parent("optgroup")
                ops.append((o.get("value", ""), limpa(o.get_text()), g.get("label", "") if g else ""))
            selects[sel.get("name")] = ops
        return {"ocultos": ocultos, "selects": selects}
    return None


def autores_vereadores(form):
    """{id: nome} dos autores do tipo vereador no select AutoriaId (atuais e anteriores)."""
    out = {}
    for valor, texto, grupo in form["selects"].get("AutoriaId", []):
        if valor.isdigit() and int(valor) and "vereador" in sem_acento(grupo) and not eh_coletivo(texto):
            out[int(valor)] = texto
    return out


# ---------------------------------------------------------------- adaptador

def _br(d):
    return d.strftime("%d/%m/%Y")


def _por_ano(desde, ate):
    """Quebra o período em pedaços de um ano, para paginar em paralelo."""
    return [(max(desde, date(a, 1, 1)), min(ate, date(a, 12, 31))) for a in range(desde.year, ate.year + 1)]


class Siscam(Fonte):
    sistema = "siscam"

    def __init__(self, cfg, cliente=None):
        super().__init__(cfg, cliente)
        s = cfg.get("siscam", {})
        self.modulo = s.get("modulo", 8)
        self.id_prop = s.get("id_proposituras", 80)
        self.id_sub = s.get("id_subdocumentos", 87)
        self.tipo_resposta = s.get("tipo_resposta")
        self.tipo_veto = s.get("tipo_veto")
        self.tipo_ata = s.get("tipo_ata")
        self.tipos = {int(k): v for k, v in cfg["codigos_tipos"].items()}
        self.rx_exec = re.compile(cfg.get("executivo", r"prefeit|executivo"))
        self.mesclar = {int(k): int(v) for k, v in cfg["mesclar_autores"].items()}
        self.paralelo = s.get("paralelo", 4)
        self._form = None
        #: nome impresso → id do vereador, aprendido nos documentos de autor único
        self.apelidos = {}

    # -- acesso
    def _url(self, idm, tipo, desde, ate, pagina, autor=None):
        u = (f"{self.base}/Documentos/Pesquisa/{idm}?Pesquisa=Avancada&id={idm}&Modulo={self.modulo}"
             f"&Documento={tipo}&Numeracao=Documento&DataInicial={_br(desde)}&DataFinal={_br(ate)}")
        if autor:
            u += f"&AutoriaId={autor}"
        return u + f"&Pagina={pagina}"

    def _paginas(self, idm, tipo, desde, ate, autor=None, ler=ler_lista):
        """Percorre as páginas até vir uma sem item novo."""
        todos, vistos, n = [], set(), 1
        while True:
            itens = ler(self.http.html(self._url(idm, tipo, desde, ate, n, autor)))
            novos = [i for i in itens if (i if isinstance(i, int) else i["id"]) not in vistos]
            if not novos:
                return todos
            vistos.update(i if isinstance(i, int) else i["id"] for i in novos)
            todos += novos
            if len(itens) < POR_PAGINA:
                return todos
            n += 1

    def _em_paralelo(self, tarefas):
        with ThreadPoolExecutor(max_workers=self.paralelo) as ex:
            return list(ex.map(lambda t: t(), tarefas))

    def formulario(self):
        if self._form is None:
            self._form = ler_formulario(self.http.html(f"{self.base}/index/{self.id_prop}/{self.modulo}"))
            if not self._form:
                raise RuntimeError("não achei o formulário de pesquisa avançada do SISCAM")
        return self._form

    # -- interface
    def proposituras(self, desde, ate, familias=None):
        tipos = {c: n for c, n in self.tipos.items() if familia(n) and (not familias or familia(n) in familias)}
        tarefas, rotulos = [], []
        for cod, nome in tipos.items():
            for a, b in _por_ano(desde, ate):
                tarefas.append(lambda cod=cod, a=a, b=b: self._paginas(self.id_prop, cod, a, b))
                rotulos.append(nome)
        props, vistos = [], set()
        for nome, itens in zip(rotulos, self._em_paralelo(tarefas)):
            for it in itens:
                if it["id"] not in vistos:
                    vistos.add(it["id"])
                    props.append(para_propositura(it, nome, self.base, self.rx_exec))
        print(f"  {len(props)} proposituras de {_br(desde)} a {_br(ate)}" + (f" ({', '.join(familias)})" if familias else ""))
        if not familias:
            self._atribuir_autores(props, desde, ate)
        return props

    def _atribuir_autores(self, props, desde, ate):
        """Segunda passada: uma pesquisa por autor, só para pegar os ids dos documentos."""
        candidatos = autores_vereadores(self.formulario())
        ids = list(candidatos)
        listas = self._em_paralelo([
            (lambda i=i: self._paginas(self.id_prop, 0, desde, ate, autor=i, ler=ids_da_lista)) for i in ids])
        por_doc = {}
        for aid, docs in zip(ids, listas):
            alvo = self.mesclar.get(aid, aid)
            for d in docs:
                if alvo not in por_doc.setdefault(d, []):
                    por_doc[d].append(alvo)
        for p in props:
            p["autores"] = por_doc.get(p["id"], [])
            if len(p["autores"]) == 1 and len(p["autoria"]) == 1:
                self.apelidos[p["autoria"][0]] = p["autores"][0]
        for aid, nome in candidatos.items():
            self.apelidos.setdefault(nome, self.mesclar.get(aid, aid))
        for p in props:
            ordenar_autores(p, self.apelidos)
        print(f"  autoria conferida para {len(ids)} autores ({sum(1 for p in props if p['autores'])} documentos de vereadores)")

    def vereadores(self, inicio, fim, ativos=()):
        atuais = ler_vereadores(self.http.html(f"{self.base}/vereadores"), self.base)
        ids = {v["id"] for v in atuais}
        for v in atuais:
            v["situacao"] = "titular"
        faltam = [i for i in ativos if i not in ids]
        if faltam:
            antigos = {v["id"]: v for v in ler_vereadores(self.http.html(f"{self.base}/vereadores/Anteriores"), self.base)}
            nomes = autores_vereadores(self.formulario())
            for i in faltam:
                v = antigos.get(i) or {"id": i, "nome": nomes.get(i, f"Autor {i}"), "partido": "", "foto": "",
                                       "perfil": f"{self.base}/Vereadores/Vereador/{i}"}
                v["situacao"] = "fora"
                atuais.append(v)
        return atuais

    def _subdocumentos(self, tipo, desde, ate):
        listas = self._em_paralelo([(lambda a=a, b=b: self._paginas(self.id_sub, tipo, a, b)) for a, b in _por_ano(desde, ate)])
        vistos, out = set(), []
        for itens in listas:
            for it in itens:
                if it["id"] not in vistos:
                    vistos.add(it["id"])
                    out.append(it)
        return out

    def respostas(self, desde, ate):
        if not self.tipo_resposta:
            return None
        out = []
        for it in self._subdocumentos(self.tipo_resposta, desde, ate):
            if it["principal"]:
                out.append({"id": it["id"], "doc": it["principal"][0], "data": de_br(it["campos"].get("Data")), "titulo": it["titulo"]})
        print(f"  {len(out)} respostas do Executivo")
        return out

    def vetos(self, desde, ate):
        if not self.tipo_veto:
            return None
        out = []
        for it in self._subdocumentos(self.tipo_veto, desde, ate):
            c = it["campos"]
            out.append({
                "id": it["id"], "titulo": it["titulo"], "data": de_br(c.get("Data")), "tipo": c.get("Tipo", ""),
                "alvo": it["principal"][1] if it["principal"] else "", "alvo_id": it["principal"][0] if it["principal"] else None,
                "assunto": c.get("Assunto", ""), "obs": c.get("Observações", ""), "situacao": c.get("Situação", ""),
                "url": f"{self.base}/Documentos/Documento/{it['id']}",
            })
        print(f"  {len(out)} vetos")
        return out

    def sessoes(self, desde, ate, conhecidas=None, vereadores=()):
        """Presença: só existe se as atas forem públicas e tiverem a lista de presentes.

        As atas aparecem como documento do tipo `tipo_ata` na página de cada membro da
        Mesa (/Vereadores/Proposituras/<id>?documento=<tipo>). O arquivo fica em
        /Documentos/ListarArquivosPdf/<id> → /Documentos/Arquivo/<arquivo>.
        """
        if not self.tipo_ata:
            self.avisos["presenca"] = "A câmara não tem um tipo de documento para as atas das sessões no sistema."
            return None
        atas = {}
        for v in vereadores:
            if v.get("situacao") != "titular":
                continue
            soup = BeautifulSoup(self.http.html(f"{self.base}/Vereadores/Proposituras/{v['id']}?documento={self.tipo_ata}"), "lxml")
            for p in soup.select("#content p.data-list-item"):
                a = p.find("a", href=re.compile(r"/Documentos/Documento/\d+$"))
                data = de_br(p.get_text())
                if a and data and desde.isoformat() <= data <= ate.isoformat():
                    atas[int(a["href"].rsplit("/", 1)[1])] = {"data": data, "nome": limpa(p.get_text().split(" - ", 2)[-1])}
            if len(atas) > 3:
                break   # a Mesa assina todas: um secretário já lista o conjunto
        if not atas:
            self.avisos["presenca"] = "Nenhuma ata de sessão desta legislatura está publicada no sistema."
            return None
        from presenca_ata import extrair, texto_pdf
        nomes = {v["id"]: v["nome"] for v in vereadores if v.get("situacao") == "titular"}
        sessoes, bloqueadas, sem_lista = [], 0, 0
        feitas = {s["id"]: s for s in (conhecidas or [])}
        for aid, meta in sorted(atas.items(), key=lambda kv: kv[1]["data"]):
            if aid in feitas:
                sessoes.append(feitas[aid])
                continue
            pagina = self.http.html(f"{self.base}/Documentos/ListarArquivosPdf/{aid}")
            arquivos = re.findall(r'name="ArquivosSelecionados" value="(\d+)"', pagina)
            pdf = self.http.bytes(f"{self.base}/Documentos/Arquivo/{arquivos[0]}") if arquivos else None
            if not pdf or not pdf.startswith(b"%PDF"):
                bloqueadas += 1
                if bloqueadas >= 3 and not sessoes:
                    break   # acesso controlado: não insiste
                continue
            r = extrair(texto_pdf(io.BytesIO(pdf)), nomes)
            if not r:
                sem_lista += 1
                continue
            sessoes.append({"id": aid, "nome": meta["nome"], "data": meta["data"], "tipo": "Sessão",
                            "url": f"{self.base}/Documentos/ListarArquivosPdf/{aid}", **r})
        if not sessoes:
            self.avisos["presenca"] = (
                f"As {len(atas)} atas desta legislatura estão listadas no sistema, mas o arquivo de cada uma está em "
                "acesso controlado (pede chave e senha): a página do documento e o PDF devolvem erro 404 para o público."
                if bloqueadas else
                f"As {len(atas)} atas publicadas não trazem uma lista de presença que dê para ler automaticamente.")
            return None
        return sessoes

