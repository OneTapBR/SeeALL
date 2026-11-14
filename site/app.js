(() => {
  "use strict";
  const CATS = {
    bairro:    { nome: "Pedidos de melhoria nos bairros", curto: "pedidos nos bairros", desc: "Tapar buraco, podar árvore, trocar lâmpada, limpar terreno. Indicações e requerimentos pedindo serviço: a Prefeitura decide se faz." },
    cobranca:  { nome: "Perguntas e cobranças", curto: "perguntas e cobranças", desc: "Requerimentos pedindo informação ou explicação à Prefeitura e a outros órgãos." },
    homenagem: { nome: "Homenagens", curto: "homenagens", desc: "Congratulações, votos de pesar, título de cidadão, medalhas, nome de rua e datas comemorativas." },
    lei:       { nome: "Propostas de lei", curto: "propostas de lei", desc: "Projetos que criam regra, programa ou obrigação na cidade." },
    outros:    { nome: "Outros", curto: "outros", desc: "Moções de apoio ou repúdio, decretos legislativos e regras internas da Câmara." },
  };
  const ORDEM = ["bairro", "cobranca", "homenagem", "lei", "outros"];
  const SITUACAO = { suplente: "Suplente", licenciado: "Licenciado", ex: "Ex-vereador", fora: "Suplente ou ex-vereador" };
  const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
  const $ = (s, el = document) => el.querySelector(s);
  const fmt = n => Number(n).toLocaleString("pt-BR");
  const dec = n => Number(n).toLocaleString("pt-BR", { maximumFractionDigits: 1 });
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const cor = c => `var(--c-${c})`;
  const total = o => ORDEM.reduce((s, c) => s + (o[c] || 0), 0);
  const dt = iso => iso ? `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(0, 4)}` : "";
  const mesNome = m => `${MESES[+m.slice(5, 7) - 1]}/${m.slice(0, 4)}`;
  const diasEntre = (a, b) => Math.round((Date.parse(b) - Date.parse(a)) / 864e5);
  const pl = (n, um, varios) => `${fmt(n)} ${n === 1 ? um : varios}`;
  const titulo = s => s.toLowerCase().replace(/(^|\s|-)(\p{L})/gu, (m, a, b) => a + b.toUpperCase()).replace(/\b(Da|De|Do|Dos|Das|E)\b/g, w => w.toLowerCase());

  /* animações de entrada: só com JS ativo e se a pessoa não pediu menos movimento */
  const semMovimento = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const RX_INTEIRO = /^\d{1,3}(\.\d{3})*%?$/;
  function contar(raiz) {
    raiz.querySelectorAll(".n, .votos-num strong, .rep-n, .trio b, .qt, .prefeito .nums b").forEach(el => {
      const no = el.firstChild;
      if (!no || no.nodeType !== 3 || !RX_INTEIRO.test(no.nodeValue.trim())) return;
      const txt = no.nodeValue.trim(), pct = txt.endsWith("%") ? "%" : "", alvo = +txt.replace(/\D/g, ""), t0 = performance.now(), dur = 900;
      const passo = t => {
        const p = Math.min((t - t0) / dur, 1);
        no.nodeValue = fmt(Math.round(alvo * (1 - Math.pow(1 - p, 3)))) + pct;
        if (p < 1) requestAnimationFrame(passo); else no.nodeValue = txt;
      };
      requestAnimationFrame(passo);
    });
  }
  const olho = !semMovimento && "IntersectionObserver" in window
    ? new IntersectionObserver(es => es.forEach(e => {
        if (!e.isIntersecting) return;
        e.target.classList.add("visto");
        contar(e.target);
        olho.unobserve(e.target);
        setTimeout(() => e.target.classList.add("pronto"), 1400);   // depois da entrada, some o atraso em cascata
      }), { rootMargin: "0px 0px -6% 0px" })
    : null;
  function revelar(seletor) {
    if (!olho) return;
    const porPai = new Map();
    document.querySelectorAll(seletor).forEach(el => {
      if (el.classList.contains("revela") || el.closest(".folha")) return;
      const i = porPai.get(el.parentElement) || 0;
      porPai.set(el.parentElement, i + 1);
      el.style.setProperty("--i", Math.min(i, 10));
      el.classList.add("revela");
      olho.observe(el);
    });
    setTimeout(conferir, 300);
  }
  // rede de segurança: se o observador não disparar (aba em segundo plano, navegador antigo),
  // a rolagem revela pelo cálculo de posição, para nada ficar invisível
  let conferindo = false;
  const conferir = () => {
    conferindo = false;
    document.querySelectorAll(".revela:not(.visto)").forEach(el => {
      const r = el.getBoundingClientRect();
      if (r.width && r.top < innerHeight * 0.96) {   // na tela ou já acima dela
        el.classList.add("visto");
        contar(el);
        olho.unobserve(el);
        setTimeout(() => el.classList.add("pronto"), 1400);
      }
    });
  };
  if (olho) ["scroll", "resize"].forEach(ev => addEventListener(ev, () => { if (!conferindo) { conferindo = true; setTimeout(conferir, 80); } }, { passive: true }));
  const REVELAVEIS =".bloco-cab, .barra, .cat, .lt, .legenda, .painel, .rep, .ver, .contador, .prefeito, #temas .tema-l, .frase";

  let R, F = null, temFinancas = false, porId, ANO, HOJE, promDocs = null;
  const reais = v => v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
  const curto = v => v >= 1e9 ? `R$ ${dec(v / 1e9)} bi` : v >= 1e6 ? `R$ ${dec(v / 1e6)} mi` : v >= 1e3 ? `R$ ${fmt(Math.round(v / 1e3))} mil` : reais(v);
  const ORIGENS = {
    proprio: ["Arrecadado na cidade", "IPTU, ISS, taxas, água e esgoto e outras receitas próprias", "var(--c-bairro)"],
    estado: ["Veio do Estado", "ICMS, IPVA e convênios estaduais", "var(--c-lei)"],
    uniao: ["Veio do governo federal", "FPM, SUS, merenda e convênios federais", "var(--c-cobranca)"],
    fundeb: ["Fundeb", "fundo da educação básica, com dinheiro de União, Estado e municípios", "var(--c-homenagem)"],
    outras: ["Outras transferências", "", "var(--c-outros)"],
  };
  const docsTodos = () => promDocs ||= fetch(`data/${ANO}/docs.json`).then(r => r.json());

  /* tema */
  const raiz = document.documentElement;
  const salvo = (() => { try { return localStorage.getItem("tema"); } catch { return null; } })();
  const aplicaTema = t => { raiz.dataset.theme = t; };
  aplicaTema(salvo || (matchMedia("(prefers-color-scheme: dark)").matches ? "escuro" : "claro"));
  $("#tema").addEventListener("click", () => {
    const t = raiz.dataset.theme === "escuro" ? "claro" : "escuro";
    aplicaTema(t);
    try { localStorage.setItem("tema", t); } catch {}
  });

  /* carga: índice (cidade + legislaturas) → números da legislatura escolhida */
  fetch("data/index.json", { cache: "no-cache" }).then(r => r.json()).then(idx => {
    temFinancas = !!idx.financas;
    const pedido = +new URLSearchParams(location.search).get("l");
    ANO = idx.legislaturas.some(l => l.ano === pedido) ? pedido : idx.atual;
    if (idx.legislaturas.length > 1) {
      const sel = $("#leg");
      sel.innerHTML = [...idx.legislaturas].reverse().map(l => `<option value="${l.ano}"${l.ano === ANO ? " selected" : ""}>${l.ano}–${l.fim.slice(0, 4)}${l.ano === idx.atual ? " (atual)" : ""}</option>`).join("");
      sel.addEventListener("change", () => { location.href = (+sel.value === idx.atual ? "./" : `?l=${sel.value}`) + "#/"; });
      $("#leg-caixa").hidden = false;
    }
    return fetch(`data/${ANO}/radar.json`, { cache: "no-cache" }).then(r => r.json());
  }).then(d => {
    R = d;
    HOJE = R.legislatura.encerrada ? R.legislatura.fim : R.atualizado.split(" ")[0].split("/").reverse().join("-");
    porId = Object.fromEntries(R.vereadores.map(v => [v.id, v]));
    R.vereadores.forEach(v => { v.total = total(v.cats); v.apelido = titulo(v.nome); });
    cidade(); hero(); categorias(); tempo(); votacoes(); ruas(); repetidos(); temas(); prefeitura(); presenca(); grade(); rota();
    revelar(REVELAVEIS);
    if (temFinancas && !R.legislatura.encerrada) fetch("data/financas.json", { cache: "no-cache" }).then(r => r.json()).then(f => { F = f; contador(); dinheiro(); revelar(REVELAVEIS); rota(); }).catch(() => {});
  }).catch(e => {
    console.error(e);
    $("#atualizado").textContent = "Não foi possível carregar os dados";
  });

  const periodo = () => R.legislatura.encerrada ? `na legislatura ${R.legislatura.ano}–${R.legislatura.fim.slice(0, 4)}` : "desde a posse";

  function cidade() {
    const c = R.cidade;
    document.querySelectorAll("[data-cidade=titulo]").forEach(e => e.textContent = c.titulo);
    $(".marca").setAttribute("aria-label", `${c.titulo}, início`);
    $("#atualizado").textContent = R.legislatura.encerrada ? `Legislatura ${R.legislatura.ano}–${R.legislatura.fim.slice(0, 4)}` : `Atualizado em ${R.atualizado}`;
    const f = $("#link-fonte");
    f.href = c.fonte; f.textContent = c.fonte.replace(/^https?:\/\//, "");
    if (c.repositorio) $("#link-repo").innerHTML = ` ou <a href="${esc(c.repositorio)}" rel="noopener">abra o código no GitHub</a>`;
    if (R.legislatura.encerrada) {
      const a = $("#arquivo");
      a.hidden = false;
      a.innerHTML = `Você está vendo o arquivo da legislatura ${R.legislatura.ano}–${R.legislatura.fim.slice(0, 4)}, já encerrada. <a href="./">Voltar para a atual</a>`;
    }
    $("#sub-propostas").textContent = `Tudo o que os vereadores apresentaram ${R.legislatura.encerrada ? periodo() : "desde " + dt(R.legislatura.inicio)}, separado pelo que cada documento faz.`;
    if (R.avisos?.presenca) {
      const p = $("#aviso-presenca");
      p.hidden = false;
      p.innerHTML = `<strong>Por que não tem presença nas sessões.</strong> ${esc(R.avisos.presenca)}`;
    }
  }

  function hero() {
    const t = R.total;
    const ativos = R.vereadores.filter(v => v.situacao === "titular");
    const vsRadar = (ativos.length ? ativos : R.vereadores).filter(v => v.total);
    $("#h1").textContent = `O que os ${vsRadar.length} vereadores de ${R.cidade.nome} fizeram ${periodo()}.`;
    if (t.lei) {
      const r = t.homenagem / t.lei;
      $("#frase").innerHTML = r >= 1
        ? `Pra cada proposta de lei, <b>${dec(r)} homenagens</b>.`
        : `${fmt(t.lei)} propostas de lei e ${fmt(t.homenagem)} homenagens ${periodo()}.`;
    }
    // radar: ângulo = posição, distância = fatia de homenagens
    const g = $("#blips");
    const estreito = matchMedia("(max-width: 560px)").matches;
    if (estreito) $("#radar svg").setAttribute("viewBox", "-170 -122 340 244");
    const vs = [...vsRadar].sort((a, b) => a.nome.localeCompare(b.nome));
    const max = Math.max(...vs.map(v => v.cats.homenagem / v.total), .01);
    const dir = Math.ceil(vs.length / 2), esq = vs.length - dir;
    g.innerHTML = vs.map((v, i) => {
      const f = v.cats.homenagem / v.total;
      const raio = 14 + (f / max) * 86;
      const ang = i < dir ? (-75 + (150 * i) / Math.max(dir - 1, 1)) * Math.PI / 180
        : (255 - (150 * (i - dir)) / Math.max(esq - 1, 1)) * Math.PI / 180;
      const x = Math.cos(ang) * raio, y = Math.sin(ang) * raio;
      const pct = Math.round(f * 100);
      const ws = v.apelido.split(" ");
      const dup = vs.filter(o => o.apelido.split(" ")[0] === ws[0]).length > 1;
      const nome = estreito
        ? (dup || ws[0].endsWith(".") ? ws[0] + " " + ws[ws.length - 1] : ws[0])
        : ws.length <= 2 ? v.apelido : (/^(do|da|de|dos|das|la)$/i.test(ws[1]) ? ws.slice(0, 3).join(" ") : ws[0] + " " + ws[ws.length - 1]);
      const lx = Math.cos(ang) * 112, ly = Math.sin(ang) * 112;
      return `<g class="blip" style="--i:${i}" tabindex="0" role="link" data-id="${v.id}" aria-label="${esc(v.apelido)}: ${pct}% homenagens">
        <line x1="${x.toFixed(1)}" y1="${y.toFixed(1)}" x2="${(Math.cos(ang) * 106).toFixed(1)}" y2="${(Math.sin(ang) * 106).toFixed(1)}"/>
        <circle class="halo" cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="8"/>
        <circle class="pt" cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="3.6"/>
        <text x="${(lx + (lx > 0 ? 2 : -2)).toFixed(1)}" y="${(ly + 3).toFixed(1)}" text-anchor="${lx > 0 ? "start" : "end"}">${esc(nome)} <tspan>${pct}%</tspan></text>
        <title>${esc(v.apelido)} — ${pct}% do que apresentou são homenagens</title></g>`;
    }).join("");
    const abre = e => { const b = e.target.closest(".blip"); if (b) location.hash = `#/vereador/${b.dataset.id}`; };
    g.addEventListener("click", abre);
    g.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); abre(e); } });
  }

  function categorias() {
    const t = R.total, soma = total(t) || 1;
    $("#barra").innerHTML = ORDEM.map(c => `<span style="flex:${t[c]};background:${cor(c)}" title="${CATS[c].nome}: ${fmt(t[c])}"></span>`).join("");
    $("#barra").setAttribute("aria-label", ORDEM.map(c => `${CATS[c].nome}: ${fmt(t[c])}`).join("; "));
    $("#cats").innerHTML = ORDEM.map(c => `
      <button class="cat" style="--cor:${cor(c)}" data-cat="${c}">
        <span class="n">${fmt(t[c])}</span>
        <span class="nome">${CATS[c].nome}</span>
        <span class="desc">${CATS[c].desc}</span>
        <span class="abrir">Ver todos (${Math.round(t[c] / soma * 100)}%)</span>
      </button>`).join("");
    $("#cats").addEventListener("click", e => { const b = e.target.closest(".cat"); if (b) location.hash = `#/categoria/${b.dataset.cat}`; });
  }

  /* linha do tempo mensal: barras empilhadas por categoria */
  function linhaTempo(series, { clicavel = false, referencia = null } = {}) {
    const meses = R.meses;
    const somas = meses.map((_, i) => series.reduce((s, a) => s + a[i], 0));
    const teto = Math.max(...somas, ...(referencia || []), 1);
    const passo = meses.length > 30 ? 6 : meses.length > 14 ? 3 : 1;
    const tag = clicavel ? "button" : "div";
    return `<div class="lt-barras" style="--n:${meses.length}">` + meses.map((m, i) => {
      const partes = ORDEM.map((c, k) => series[k][i] ? `<i style="height:${(series[k][i] / teto * 100).toFixed(2)}%;background:${cor(c)}"></i>` : "").join("");
      const ref = referencia ? `<b class="lt-ref" style="bottom:${(referencia[i] / teto * 100).toFixed(2)}%"></b>` : "";
      const det = ORDEM.map((c, k) => series[k][i] ? `${CATS[c].curto}: ${series[k][i]}` : "").filter(Boolean).join(", ");
      const rot = +m.slice(5, 7) === 1 ? m.slice(0, 4) : (+m.slice(5, 7) - 1) % passo === 0 ? MESES[+m.slice(5, 7) - 1] : "";
      return `<${tag} class="lt-col${+m.slice(5, 7) === 1 ? " ano" : ""}" style="--k:${i}" ${clicavel ? `type="button" data-m="${m}"` : ""} title="${mesNome(m)}: ${fmt(somas[i])} documentos${det ? ` (${det})` : ""}${referencia ? `. Média da Câmara: ${dec(referencia[i])}` : ""}" aria-label="${mesNome(m)}: ${fmt(somas[i])} documentos">
        <span class="lt-pilha">${partes}${ref}</span><span class="lt-rot">${rot}</span></${tag}>`;
    }).join("") + `</div>`;
  }

  function tempo() {
    const el = $("#lt-geral");
    el.innerHTML = linhaTempo(R.mensal, { clicavel: true });
    el.addEventListener("click", e => { const b = e.target.closest(".lt-col"); if (b) location.hash = `#/mes/${b.dataset.m}`; });
    $("#lt-legenda").innerHTML = ORDEM.map(c => `<span><i style="background:${cor(c)}"></i>${CATS[c].nome}</span>`).join("");
  }

  function votacoes() {
    const v = R.votacoes;
    $("#nota-votos").textContent = R.cidade.sistema === "SAPL"
      ? "Conta cada votação registrada no sistema da Câmara, com o placar de votos a favor e contra."
      : "Conta os resultados registrados nas observações de cada projeto (projetos de lei, decretos legislativos, resoluções). Votação nominal por vereador não é publicada pela Câmara.";
    if (!v.total) { $("#txt-unan").textContent = "Sem votações registradas ainda."; $("#ver-divididas").hidden = true; return; }
    $("#pct-unan").textContent = `${Math.round(v.unanimes / v.total * 100)}%`;
    $("#txt-unan").textContent = `das ${fmt(v.total)} votações registradas foram unânimes ou sem nenhum voto contrário.`;
    $("#ver-divididas").addEventListener("click", () => location.hash = "#/votacoes");
  }

  const nomeVia = r => esc(r.via) + (r.bairro ? ` <span class="bairro">${esc(r.bairro)}</span>` : "");
  const quemPediu = r => r.autores.map(([id, n]) => `${porId[id]?.apelido ?? "?"} (${n})`).join(", ");

  function ruas() {
    const lista = $("#lista-ruas");
    if (!R.vias.length) { $("#ruas").hidden = true; return; }
    const render = n => {
      lista.innerHTML = R.vias.slice(0, n).map((r, i) => `
        <li><button data-i="${i}">
          <span><span class="rua">${nomeVia(r)}</span>
          <span class="det">${r.temas.map(t => `${esc(t[0].toLowerCase())} (${t[1]})`).join(", ")}. De ${dt(r.primeiro)} a ${dt(r.ultimo)}</span></span>
          <span class="qt">${r.n}</span></button></li>`).join("");
    };
    let n = 6; render(n);
    $("#mais-ruas").addEventListener("click", e => { n = n === 6 ? 20 : 6; render(n); e.target.textContent = n === 6 ? "Ver mais ruas" : "Ver menos"; });
    lista.addEventListener("click", e => { const b = e.target.closest("button"); if (b) location.hash = `#/rua/${b.dataset.i}`; });
  }

  function repetidos() {
    const rs = R.repetidos || [];
    if (!rs.length) return;
    $("#repetidos-bloco").hidden = false;
    const el = $("#repetidos");
    const render = n => {
      el.innerHTML = rs.slice(0, n).map((r, i) => `
        <button class="rep" data-i="${i}">
          <span class="rep-n">${r.n}<small>vezes</small></span>
          <span><span class="rep-t">Pediram ${esc(r.frase)} ${r.n} vezes na ${nomeVia(r)}</span>
          <span class="det">De ${dt(r.primeiro)} a ${dt(r.ultimo)}. Quem mais pediu: ${esc(quemPediu(r))}</span></span>
        </button>`).join("");
    };
    let n = 6; render(n);
    $("#mais-rep").hidden = rs.length <= 6;
    $("#mais-rep").addEventListener("click", e => { n = n === 6 ? 40 : 6; render(n); e.target.textContent = n === 6 ? "Ver mais pedidos repetidos" : "Ver menos"; });
    el.addEventListener("click", e => { const b = e.target.closest(".rep"); if (b) location.hash = `#/repetido/${b.dataset.i}`; });
  }

  function temas() {
    if (!R.temas.length) { $("#temas-bloco").hidden = true; return; }
    const max = R.temas[0][1] || 1;
    $("#temas").innerHTML = R.temas.map(([t, n]) => `
      <button class="tema-l" data-t="${esc(t)}"><span>${esc(t)}</span><span class="tr"><i style="width:${(n / max * 100).toFixed(1)}%"></i></span><b>${fmt(n)}</b></button>`).join("");
    $("#temas").addEventListener("click", e => { const b = e.target.closest(".tema-l"); if (b) location.hash = `#/tema/${encodeURIComponent(b.dataset.t)}`; });
  }

  /* contador: reparte a folha do último mês publicado ao longo do mês atual */
  function contador() {
    const fm = F.folha_mes;
    if (!fm || !fm.total) return;
    const el = $("#contador"), n = $("#cont-n");
    el.hidden = false;
    $("#cont-det").textContent = `Prefeitura, Câmara e autarquias. Estimativa pela folha de ${mesNome(fm.mes)} (${curto(fm.total)}), o último mês publicado. Toque para ver o detalhe.`;
    const tique = () => {
      const a = new Date(), ini = new Date(a.getFullYear(), a.getMonth(), 1), fim = new Date(a.getFullYear(), a.getMonth() + 1, 1);
      n.textContent = reais(fm.total * (a - ini) / (fim - ini));
    };
    tique();
    if (!matchMedia("(prefers-reduced-motion: reduce)").matches) setInterval(tique, 90);
    el.addEventListener("click", () => location.hash = "#/folha");
  }

  function dinheiro() {
    const anos = Object.keys(F.anos).sort().reverse();
    if (!anos.length) return;
    $("#dinheiro").hidden = false;
    $("#aviso-dinheiro").hidden = false;
    const sel = $("#din-ano");
    sel.innerHTML = anos.map(a => `<option value="${a}">${a}${F.anos[a].n_meses < 12 ? ` (até ${mesNome(F.anos[a].ate)})` : ""}</option>`).join("");
    const el = $("#din");
    let n = 10;
    const render = () => {
      const a = F.anos[sel.value];
      const rec = Object.keys(ORIGENS).filter(o => a.receita[o] > 0), totR = rec.reduce((s, o) => s + a.receita[o], 0);
      const totP = a.pago.reduce((s, x) => s + x[1], 0), totF = a.folha.reduce((s, x) => s + x[1], 0), mxP = a.pago[0]?.[1] || 1, mxT = a.top[0]?.[1] || 1;
      const fora = a.receita.estado + a.receita.uniao + a.receita.fundeb + a.receita.outras;
      el.innerHTML = `
        <div class="painel">
          <h3>De onde veio</h3>
          <div class="votos-num"><strong style="color:var(--azul)">${curto(totR)}</strong><span>entraram nos cofres do município em ${sel.value}. ${Math.round(fora / totR * 100)}% vieram de fora da cidade.</span></div>
          <div class="origens" role="img" aria-label="Receita por origem">${rec.map(o => `<span style="flex:${a.receita[o]};background:${ORIGENS[o][2]}" title="${ORIGENS[o][0]}: ${curto(a.receita[o])}"></span>`).join("")}</div>
          <div class="leg-din">${rec.map(o => `<div><i style="background:${ORIGENS[o][2]}"></i><span>${ORIGENS[o][0]} <small>${ORIGENS[o][1]}</small></span><b>${curto(a.receita[o])} <small>${Math.round(a.receita[o] / totR * 100)}%</small></b></div>`).join("")}</div>
          <button class="link" data-ir="#/receitas/${sel.value}" style="margin-top:1rem">Ver as maiores fontes de receita</button>
        </div>
        <div class="painel">
          <h3>Para onde foi</h3>
          <div class="votos-num"><strong style="color:var(--azul)">${curto(totP)}</strong><span>pagos em ${sel.value}. ${Math.round(totF / totP * 100)}% foram folha de pagamento, aposentadorias e pensões.</span></div>
          <div class="temas" style="margin-top:1rem">${a.pago.map(([o, v]) => `<div class="tema-l est"><span>${esc(o)}</span><span class="tr"><i style="width:${(v / mxP * 100).toFixed(1)}%;background:var(--azul)"></i></span><b>${curto(v)}</b></div>`).join("")}</div>
          <button class="link" data-ir="#/folha" style="margin-top:1rem">Ver quanto vai para salários</button>
        </div>
        <div class="painel larga">
          <h3>Quem mais recebeu</h3>
          <p class="nota" style="margin-top:0">As ${n} empresas e entidades que mais receberam pagamentos do município em ${sel.value}. Não entram salários, pagamentos a pessoas físicas nem repasses entre órgãos da própria Prefeitura.</p>
          <ol class="gastos">${a.top.slice(0, n).map(([nome, v, org]) => `<li><span><span class="nm">${esc(nome)}</span><span class="det">pago principalmente por: ${esc(org)}</span><span class="tr"><i style="width:${(v / mxT * 100).toFixed(1)}%"></i></span></span><b>${curto(v)}</b></li>`).join("")}</ol>
          ${a.top.length > 10 ? `<button class="link" id="mais-gastos">${n === 10 ? `Ver os ${Math.min(30, a.top.length)} maiores` : "Ver só os 10 maiores"}</button>` : ""}
          <p class="nota">O Tribunal de Contas informa quem recebeu, não o que foi comprado. Para ver o contrato de cada empresa, procure o nome no Portal da Transparência da Prefeitura.</p>
        </div>`;
    };
    sel.addEventListener("change", () => { n = 10; render(); });
    el.addEventListener("click", e => {
      if (e.target.closest("#mais-gastos")) { n = n === 10 ? 30 : 10; render(); return; }
      const b = e.target.closest("[data-ir]"); if (b) location.hash = b.dataset.ir;
    });
    render();
  }

  const fotoPrefeito = p => p.foto ? `<img src="${esc(p.foto)}" alt="">` : `<span class="foto-vazia"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="8" r="4"/><path d="M4 21c0-4.4 3.6-8 8-8s8 3.6 8 8"/></svg></span>`;
  function cardPrefeito() {
    const p = R.prefeito, x = R.executivo, pr = x.projetos?.executivo;
    if (!p || !pr) return;
    const el = $("#card-prefeito");
    el.innerHTML = `<button class="prefeito" type="button">
      ${fotoPrefeito(p)}
      <span><span class="nm">${esc(p.nome || `Prefeito de ${R.cidade.nome}`)}</span><span class="pt">${p.nome ? `Prefeito${p.partido ? ` · ${esc(p.partido)}` : ""}` : "Poder Executivo"}</span>
        <span class="nums"><span><b>${fmt(pr.total)}</b>projetos de lei enviados</span><span><b>${fmt(pr.aprovados)}</b>aprovados pela Câmara</span><span><b>${fmt(pr.abertos)}</b>em tramitação</span>${x.vetos ? `<span><b>${x.vetos.total}</b>${x.vetos.total === 1 ? "veto" : "vetos"}</span>` : ""}${x.respostas ? `<span><b>${x.respostas.taxa}%</b>dos requerimentos respondidos</span>` : ""}</span></span>
      <span class="ir">Ver tudo o que fez ›</span></button>`;
    el.firstElementChild.addEventListener("click", () => location.hash = "#/prefeito");
  }

  function perfilPrefeito() {
    const p = R.prefeito, x = R.executivo, pr = x.projetos.executivo, pv = x.projetos.vereadores, r = x.respostas, v = x.vetos;
    const ids = new Set(pr.ids), mxA = p.assuntos[0]?.[1] || 1;
    const serie = ORDEM.map(c => c === "lei" ? p.mensal : R.meses.map(() => 0));
    const pct = d => d.total ? Math.round(d.aprovados / d.total * 100) : 0;
    abre(p.nome || `Prefeito de ${R.cidade.nome}`, `
      <div class="perfil-topo">${fotoPrefeito(p).replace('class="foto-vazia"', 'class="foto-vazia g" style="display:grid;place-items:center"')}
        <div><div class="pt">${p.nome ? `Prefeito${p.partido ? ` · ${esc(p.partido)}` : ""}` : "Poder Executivo"}</div><div style="font:800 1.1rem var(--f-display)">${fmt(pr.total)} projetos de lei enviados à Câmara ${periodo()}</div></div></div>
      <div class="trio">
        <div><b>${fmt(pr.aprovados)} <small style="font:500 .8rem var(--f-texto);color:var(--tinta-2)">(${pct(pr)}%)</small></b><span>aprovados pelos vereadores</span></div>
        <div><b>${fmt(pr.abertos)}</b><span>ainda em tramitação</span></div>
        <div><b>${pr.tempo_mediano == null ? "–" : fmt(pr.tempo_mediano) + " dias"}</b><span>tempo típico até a aprovação</span></div>
      </div>
      <p class="razao">Os projetos do prefeito são aprovados em ${pct(pr)}% dos casos${pr.tempo_mediano != null && pv.tempo_mediano != null ? `, metade deles em até ${fmt(pr.tempo_mediano)} dias. Os dos vereadores, em ${pct(pv)}%, metade em até ${fmt(pv.tempo_mediano)} dias` : ""}.</p>
      ${v && v.total ? `<button class="fato" data-ir="#/vetos"><b>${pl(v.total, "veto", "vetos")}</b> a projetos aprovados pela Câmara: ${v.mantidos} ${v.mantidos === 1 ? "mantido" : "mantidos"}, ${v.derrubados} ${v.derrubados === 1 ? "derrubado" : "derrubados"}, ${v.pendentes} sem decisão. <u>Ver os vetos</u></button>` : ""}
      ${r ? `<button class="fato" data-ir="#/sem-resposta"><b>${r.taxa}% dos requerimentos</b> dos vereadores com mais de ${r.prazo} dias tiveram resposta registrada, em ${dec(r.tempo_medio)} dias na média. <u>${fmt(r.atrasados)} estão sem resposta</u></button>` : ""}
      <h3 class="sub">Sobre o que são os projetos</h3>
      <div class="temas">${p.assuntos.map(([a, n]) => `<div class="tema-l fx"><span>${esc(a)}</span><span class="tr"><i style="width:${(n / mxA * 100).toFixed(1)}%;background:var(--c-lei)"></i></span><b>${n}</b></div>`).join("")}</div>
      <p class="nota">Assunto lido da ementa de cada projeto; a separação é automática e pode errar.</p>
      <h3 class="sub">Mês a mês</h3>
      <div class="lt pequena">${linhaTempo(serie)}</div>
      <h3 class="sub">Todos os projetos enviados</h3>` + listaDocs(d => ids.has(d.id), { comSituacao: true, semAutor: true }));
  }

  function folhaDetalhe() {
    const fm = F.folha_mes, mx = fm.por_orgao[0]?.[1] || 1, s = F.subsidios;
    const ano = Object.keys(F.anos).sort().pop(), a = F.anos[ano];
    const cargos = { vereador: "Vereador", presidente_camara: "Presidente da Câmara", prefeito: "Prefeito", vice_prefeito: "Vice-prefeito", secretario: "Secretário municipal" };
    abre("Quanto vai para salários", `
      <p class="razao">${curto(fm.total)} em ${mesNome(fm.mes)}, o último mês publicado. O contador da página inicial reparte esse valor ao longo do mês atual.</p>
      <h3 class="sub">Por órgão, em ${mesNome(fm.mes)}</h3>
      <div class="temas">${fm.por_orgao.map(([o, v]) => `<div class="tema-l est"><span>${esc(o)}</span><span class="tr"><i style="width:${(v / mx * 100).toFixed(1)}%;background:var(--azul)"></i></span><b>${curto(v)}</b></div>`).join("")}</div>
      <p class="nota">Prefeitura, Fundação de Saúde, DAAE, Arquivo e Câmara: salários dos servidores. Câmara: inclui os subsídios dos vereadores e os salários dos funcionários e assessores. Instituto de Previdência: aposentadorias e pensões.</p>
      <h3 class="sub">No ano de ${ano}${a.n_meses < 12 ? `, até ${mesNome(a.ate)}` : ""}</h3>
      <div class="temas">${a.folha.map(([o, v]) => `<div class="tema-l est"><span>${esc(o)}</span><span class="tr"><i style="width:${(v / a.folha[0][1] * 100).toFixed(1)}%;background:var(--azul)"></i></span><b>${curto(v)}</b></div>`).join("")}</div>
      <h3 class="sub">Vereadores e prefeito</h3>
      ${s && Object.keys(s).some(k => cargos[k]) ? `<div class="leg-din">${Object.keys(cargos).filter(k => s[k]).map(k => `<div><i style="background:var(--ambar)"></i><span>${cargos[k]}</span><b>${reais(s[k])} <small>por mês</small></b></div>`).join("")}</div>${s.fonte ? `<p class="nota">Fonte: ${esc(s.fonte)}</p>` : ""}`
        : `<p class="sem-dado"><strong>O valor individual não está nos dados abertos.</strong> O Tribunal de Contas publica a folha de cada órgão inteira, sem separar por pessoa. O subsídio dos vereadores, do prefeito e do vice é fixado por lei municipal; o valor pago a cada um está no Portal da Transparência da Câmara e da Prefeitura.</p>`}
      <p class="nota">Fonte: dados abertos do Tribunal de Contas do Estado de São Paulo. A folha é o que cada órgão pagou a si mesmo ou a um credor chamado "folha de pagamento"; pode não incluir encargos e benefícios pagos a terceiros, como INSS e vale-alimentação.</p>`);
  }

  function receitasDetalhe(ano) {
    const a = F.anos[ano], mx = a.alineas[0]?.[2] || 1;
    abre(`Maiores fontes de receita em ${ano}`, `<p class="nota">${a.n_meses < 12 ? `De ${mesNome(a.de)} a ${mesNome(a.ate)}. ` : ""}Nome de cada receita como aparece na prestação de contas ao Tribunal de Contas.</p>
      <ol class="gastos">${a.alineas.map(([o, n, v]) => `<li><span><span class="nm">${esc(n)}</span><span class="det">${ORIGENS[o][0]}</span><span class="tr"><i style="width:${(v / mx * 100).toFixed(1)}%;background:${ORIGENS[o][2]}"></i></span></span><b>${curto(v)}</b></li>`).join("")}</ol>`);
  }
  $("#folha-conteudo").addEventListener("click", e => { const b = e.target.closest("[data-ir]"); if (b) location.hash = b.dataset.ir; });

  function prefeitura() {
    const x = R.executivo || {};
    const r = x.respostas, v = x.vetos, p = x.projetos;
    if (!r && !(v && v.total) && !p) return;
    $("#prefeitura").hidden = false;
    cardPrefeito();
    let h = "";
    if (r) {
      const vencidos = r.respondidos + r.atrasados, maxF = Math.max(...r.faixas.map(f => f[1]), 1);
      h += `<div class="painel pref-resp">
        <h3>Requerimentos dos vereadores</h3>
        <div class="votos-num"><strong>${r.taxa}%</strong><span>dos ${fmt(vencidos)} requerimentos com mais de ${r.prazo} dias tiveram resposta registrada.</span></div>
        <div class="trio">
          <div><b>${dec(r.tempo_medio)} dias</b><span>tempo médio até a resposta</span></div>
          <div><b>${fmt(r.atrasados)}</b><span>sem resposta há mais de ${r.prazo} dias</span></div>
          <div><b>${fmt(r.no_prazo)}</b><span>ainda dentro de ${r.prazo} dias</span></div>
        </div>
        <h4>Quanto tempo a resposta levou</h4>
        <div class="faixas">${r.faixas.map(([n, q]) => `<div class="tema-l fx"><span>${n}</span><span class="tr"><i style="width:${(q / maxF * 100).toFixed(1)}%;background:var(--c-cobranca)"></i></span><b>${fmt(q)}</b></div>`).join("")}</div>
        <p class="nota">Conta os requerimentos apresentados desde ${dt(r.desde)}, quando a Câmara passou a lançar as respostas no sistema; os anteriores não têm resposta registrada, mesmo que tenham sido respondidos. Resposta registrada não quer dizer problema resolvido. Não entram votos de pesar e congratulações.</p>
        <button class="link" data-ir="#/sem-resposta">Ver os requerimentos sem resposta</button>
      </div>`;
      if (r.ranking.length) {
        const top = r.ranking.slice(0, 10), mx = top[0][1];
        h += `<div class="painel">
          <h3>Quem mais espera resposta</h3>
          <p class="nota" style="margin-top:0">Vereadores com mais requerimentos sem resposta há mais de ${r.prazo} dias.</p>
          <div class="temas">${top.map(([id, n, tot]) => `<button class="tema-l" data-ir="#/sem-resposta/${id}"><span>${esc(porId[id]?.apelido ?? id)}</span><span class="tr"><i style="width:${(n / mx * 100).toFixed(1)}%;background:var(--c-cobranca)"></i></span><b title="de ${tot} requerimentos">${fmt(n)}</b></button>`).join("")}</div>
        </div>`;
      }
    }
    if (v && v.total) {
      h += `<div class="painel">
        <h3>Vetos do prefeito</h3>
        <div class="votos-num"><strong>${v.total}</strong><span>${v.total === 1 ? "veto a projeto aprovado" : "vetos a projetos aprovados"} pela Câmara.</span></div>
        <div class="trio">
          <div><b>${v.mantidos}</b><span>${v.mantidos === 1 ? "mantido" : "mantidos"} pelos vereadores</span></div>
          <div><b>${v.derrubados}</b><span>${v.derrubados === 1 ? "derrubado" : "derrubados"}</span></div>
          <div><b>${v.pendentes}</b><span>sem decisão registrada</span></div>
        </div>
        <button class="link" data-ir="#/vetos">Ver os vetos</button>
      </div>`;
    }
    if (p) {
      const lin = (rot, d, rota) => `<tr><th scope="row">${rot}</th><td>${fmt(d.total)}</td><td>${fmt(d.aprovados)} <small>(${d.total ? Math.round(d.aprovados / d.total * 100) : 0}%)</small></td><td>${d.tempo_medio == null ? "–" : dec(d.tempo_medio) + " dias"}</td><td><button class="link" data-ir="${rota}">ver</button></td></tr>`;
      h += `<div class="painel">
        <h3>Projetos de lei: prefeito × vereadores</h3>
        <div class="tabela"><table>
          <thead><tr><th></th><th>Apresentados</th><th>Aprovados</th><th>Tempo médio</th><th><span class="sr">Lista</span></th></tr></thead>
          <tbody>${lin("Do prefeito", p.executivo, "#/projetos/executivo")}${lin("Dos vereadores", p.vereadores, "#/projetos/vereadores")}</tbody>
        </table></div>
        <p class="nota">Projetos de lei, de lei complementar e de emenda à Lei Orgânica. O tempo vai da apresentação até a última votação registrada, só para os aprovados.</p>
      </div>`;
    }
    const el = $("#pref");
    el.innerHTML = h;
    el.addEventListener("click", e => { const b = e.target.closest("[data-ir]"); if (b) location.hash = b.dataset.ir; });
  }

  function presenca() {
    const p = R.presenca;
    if (!p) return;
    $("#presenca").hidden = false;
    $("#sub-pres").textContent = `${pl(p.total, "sessão", "sessões")} com lista de presença publicada ${periodo()}. Falta justificada conta à parte.`;
    $("#pres-lista").innerHTML = p.por_vereador.map(([id, pres, tot, just]) => {
      const pct = Math.round(pres / tot * 100);
      return `<button class="tema-l" data-id="${id}" title="${pres} de ${tot} sessões${just ? `, ${just} com falta justificada` : ""}"><span>${esc(porId[id]?.apelido ?? id)}</span><span class="tr"><i style="width:${pct}%;background:var(--c-lei)"></i></span><b>${pct}%</b></button>`;
    }).join("");
    $("#pres-lista").addEventListener("click", e => { const b = e.target.closest(".tema-l"); if (b) location.hash = `#/vereador/${b.dataset.id}`; });
    const mx = Math.max(...p.sessoes.map(s => s.faltas.length), 1);
    $("#pres-cal").innerHTML = p.sessoes.map((s, i) => `<button data-i="${i}" style="--f:${(s.faltas.length / mx).toFixed(2)}" title="${dt(s.data)} · ${esc(s.nome)}: ${pl(s.faltas.length, "falta", "faltas")}" aria-label="${dt(s.data)}: ${pl(s.faltas.length, "falta", "faltas")}">${s.faltas.length || ""}</button>`).join("");
    $("#pres-cal").addEventListener("click", e => { const b = e.target.closest("button"); if (b) location.hash = `#/sessao/${b.dataset.i}`; });
  }

  function grade() {
    const desenha = () => {
      const q = $("#busca-ver").value.trim().toLowerCase();
      const o = $("#ordem").value;
      const razao = v => v.cats.lei ? v.cats.homenagem / v.cats.lei : v.cats.homenagem * 2;
      let vs = R.vereadores.filter(v => !q || (v.nome + " " + v.partido).toLowerCase().includes(q));
      vs.sort((a, b) => o === "nome" ? a.nome.localeCompare(b.nome)
        : o === "total" ? b.total - a.total
        : o === "razao" ? razao(b) - razao(a)
        : b.cats[o] - a.cats[o]);
      $("#grade").innerHTML = vs.length ? vs.map(v => `
        <button class="ver" data-id="${v.id}">
          ${v.foto ? `<img src="${esc(v.foto)}" alt="" loading="lazy" onerror="this.replaceWith(Object.assign(document.createElement('span'),{className:'foto-vazia'}))">` : `<span class="foto-vazia"></span>`}
          <span>
            <span class="nm">${esc(v.apelido)}</span><br><span class="pt">${esc(v.partido)}</span>${SITUACAO[v.situacao] && !R.legislatura.encerrada ? ` <span class="sit">${SITUACAO[v.situacao]}</span>` : ""}
            <span class="mini">${ORDEM.map(c => `<span style="flex:${v.cats[c]};background:${cor(c)}"></span>`).join("")}</span>
            <span class="nums"><b>${fmt(v.cats.lei)}</b> leis, <b>${fmt(v.cats.homenagem)}</b> homenagens, <b>${fmt(v.cats.bairro)}</b> pedidos</span>
          </span>
        </button>`).join("") : `<p class="vazio">Nenhum vereador com esse nome ou partido.</p>`;
    };
    $("#busca-ver").addEventListener("input", desenha);
    $("#ordem").addEventListener("change", desenha);
    $("#grade").addEventListener("click", e => { const b = e.target.closest(".ver"); if (b) location.hash = `#/vereador/${b.dataset.id}`; });
    desenha();
  }

  /* folha lateral */
  const folha = $("#folha");
  let voltarFoco = null;
  function abre(tit, html) {
    if (folha.hidden) voltarFoco = document.activeElement;
    $("#folha-titulo").textContent = tit;
    $("#folha-conteudo").innerHTML = html;
    $("#folha-conteudo").scrollTop = 0;
    folha.hidden = false;
    document.body.style.overflow = "hidden";
    $(".fechar", folha).focus();
  }
  function fecha() {
    folha.hidden = true;
    document.body.style.overflow = "";
    voltarFoco?.focus?.();
  }
  folha.addEventListener("click", e => { if (e.target.closest("[data-fechar]")) location.hash.length > 2 ? (location.hash = "#/") : fecha(); });
  document.addEventListener("keydown", e => { if (e.key === "Escape" && !folha.hidden) location.hash = "#/"; });

  /* lista de documentos (carregada sob demanda) */
  function listaDocs(filtro, opts = {}) {
    const id = "l" + Math.random().toString(36).slice(2);
    docsTodos().then(todos => {
      const el = document.getElementById(id);
      if (!el) return;
      const docs = todos.filter(filtro);
      if (opts.ordenar) docs.sort(opts.ordenar);
      let n = 40, q = "";
      el.innerHTML = `<input type="search" placeholder="Buscar nesta lista (rua, bairro, nome…)" aria-label="Buscar nesta lista"><div class="corpo"></div>`;
      const busca = el.querySelector("input"), corpo = el.querySelector(".corpo");
      const render = () => {
        const f = q ? docs.filter(d => (d.t + " " + d.x).toLowerCase().includes(q)) : docs;
        corpo.innerHTML = `<p class="contagem">${pl(f.length, "documento", "documentos")}</p>` +
          (f.length ? f.slice(0, n).map(d => doc(d, opts)).join("") : `<p class="vazio">${q ? "Nada encontrado com esse termo." : "Nenhum documento aqui."}</p>`) +
          (f.length > n ? `<button class="mais" type="button">Mostrar mais ${Math.min(40, f.length - n)}</button>` : "");
      };
      busca.addEventListener("input", () => { q = busca.value.trim().toLowerCase(); n = 40; render(); });
      corpo.addEventListener("click", e => { if (e.target.closest(".mais")) { n += 40; render(); } });
      render();
    }).catch(() => { const el = document.getElementById(id); if (el) el.innerHTML = `<p class="vazio">Não foi possível carregar os documentos.</p>`; });
    return `<div id="${id}"><p class="vazio">Carregando documentos…</p></div>`;
  }
  const respInfo = d => {
    const r = R.executivo?.respostas;
    if (!r || !d.q || d.d < r.desde) return "";
    if (d.r) return `<span class="pill" style="--cor:var(--c-lei)">respondido em ${Math.max(diasEntre(d.d, d.r), 0)} dias</span>`;
    const idade = diasEntre(d.d, HOJE);
    return idade > r.prazo ? `<span class="pill" style="--cor:var(--c-cobranca)">sem resposta há ${idade} dias</span>` : "";
  };
  function doc(d, opts) {
    const autores = d.e && !d.a.length ? ["Prefeito"] : d.a.map(i => porId[i]?.apelido).filter(Boolean);
    return `<article class="doc">
      <div class="cab"><a href="${R.doc_url}${d.id}" target="_blank" rel="noopener">${esc(d.t)}</a><span>${dt(d.d)}</span></div>
      <p>${esc(d.x)}</p>
      <div class="cab" style="margin-top:.35rem"><span>${opts.semAutor ? "" : esc(autores.join(", "))}${opts.comSituacao && d.s ? `${opts.semAutor ? "" : " · "}${esc(d.s)}` : ""}</span><span class="pills">${respInfo(d)}${opts.comCat ? `<span class="pill" style="--cor:${cor(d.c)}">${CATS[d.c].curto}</span>` : ""}</span></div>
    </article>`;
  }

  function perfil(v) {
    const r = v.cats.lei ? (v.cats.homenagem / v.cats.lei) : null;
    const frase = r === null
      ? `${fmt(v.cats.homenagem)} homenagens e nenhuma proposta de lei ${periodo()}.`
      : `Pra cada proposta de lei, ${dec(r)} homenage${r === 1 ? "m" : "ns"}.`;
    const link = new URL(`v/${v.id}/`, location.href.split(/[?#]/)[0]).href;
    const mx = Math.max(...ORDEM.map(c => Math.max(v.cats[c], R.media[c])), 1);
    const mediaMes = R.meses.map((_, i) => R.mensal.reduce((s, a) => s + a[i], 0) / Math.max(R.vereadores.filter(o => o.situacao === "titular").length || R.vereadores.length, 1));
    let extras = "";
    if (v.resp) extras += `<button class="fato" data-ir="#/sem-resposta/${v.id}"><b>${v.resp.respondidos} de ${v.resp.pedidos}</b> requerimentos com resposta da Prefeitura registrada${v.resp.tempo != null ? `, em ${dec(v.resp.tempo)} dias na média` : ""}. <u>${pl(v.resp.atrasados, "está", "estão")} sem resposta há mais de ${R.executivo.respostas.prazo} dias</u></button>`;
    if (v.presenca) extras += `<p class="fato"><b>${Math.round(v.presenca.p / v.presenca.t * 100)}% de presença</b>: esteve em ${v.presenca.p} de ${pl(v.presenca.t, "sessão", "sessões")}${v.presenca.j ? `, ${pl(v.presenca.j, "falta justificada", "faltas justificadas")}` : ""}.</p>`;
    const html = `<div class="perfil-topo">${v.foto ? `<img src="${esc(v.foto)}" alt="Foto de ${esc(v.apelido)}" onerror="this.style.visibility='hidden'">` : `<span class="foto-vazia g"></span>`}
      <div><div class="pt">${esc(v.partido)}${SITUACAO[v.situacao] && !R.legislatura.encerrada ? ` · <span class="sit">${SITUACAO[v.situacao]}</span>` : ""}</div><div style="font:800 1.1rem var(--f-display)">${fmt(v.total)} documentos ${periodo()}</div>
      <a href="${esc(v.perfil)}" target="_blank" rel="noopener">Perfil na Câmara</a></div></div>
      <div class="compartilhar">
        <button type="button" class="botao" id="copiar" data-link="${esc(link)}">Copiar link</button>
        <a class="botao" href="og/${v.id}.png" target="_blank" rel="noopener">Ver cartão para compartilhar</a>
      </div>
      <div class="mini" style="height:12px">${ORDEM.map(c => `<span style="flex:${v.cats[c]};background:${cor(c)}"></span>`).join("")}</div>
      <div class="linhas-cat">${ORDEM.map(c => `<button class="linha-cat" style="--cor:${cor(c)}" data-c="${c}"><i></i><span>${CATS[c].nome}</span><b>${fmt(v.cats[c])}</b><span aria-hidden="true">›</span></button>`).join("")}</div>
      <p class="razao">${frase}</p>
      ${extras}
      ${v.proj && v.proj.total ? `<h3 class="sub">O que aconteceu com os projetos de lei</h3>
      <div class="trio">
        <div><b>${v.proj.aprovados}</b><span>aprovados, de ${pl(v.proj.total, "apresentado", "apresentados")}</span></div>
        <div><b>${v.proj.abertos}</b><span>ainda em tramitação</span></div>
        <div><b>${v.proj.total - v.proj.aprovados - v.proj.abertos}</b><span>retirados, arquivados ou rejeitados</span></div>
      </div><p class="nota">Projetos de lei, de lei complementar e de emenda à Lei Orgânica, incluindo os que são homenagem e os assinados em coautoria.</p>` : ""}
      ${v.temas && v.temas.length ? `<h3 class="sub">O que mais pede nos bairros</h3>
      <div class="temas">${v.temas.map(([t, n]) => `<div class="tema-l fx"><span>${esc(t)}</span><span class="tr"><i style="width:${(n / v.temas[0][1] * 100).toFixed(1)}%"></i></span><b>${fmt(n)}</b></div>`).join("")}</div>` : ""}
      ${v.bairros && v.bairros.length ? `<h3 class="sub">Bairros que mais aparecem nos pedidos</h3><div class="chips">${v.bairros.map(([b, n]) => `<span>${esc(b)} <b>${n}</b></span>`).join("")}</div>` : ""}
      <h3 class="sub">Presença e votos</h3>
      ${v.presenca ? "" : `<p class="sem-dado"><strong>Sem dado público.</strong> ${R.avisos?.presenca ? esc(R.avisos.presenca) : "A Câmara não publica a lista de presença das sessões em formato que dê para ler."} ${R.cidade.sistema === "SISCAM" ? "O sistema também não registra como cada vereador votou (a favor, contra ou abstenção): só o placar final de cada votação." : ""} Quando a Câmara publicar, os gráficos aparecem aqui sozinhos.</p>`}
      ${v.presenca ? `<div class="origens" role="img" aria-label="Presença"><span style="flex:${v.presenca.p};background:var(--c-lei)" title="Presente: ${v.presenca.p}"></span>${v.presenca.j ? `<span style="flex:${v.presenca.j};background:var(--ambar)" title="Falta justificada: ${v.presenca.j}"></span>` : ""}${v.presenca.t - v.presenca.p - v.presenca.j ? `<span style="flex:${v.presenca.t - v.presenca.p - v.presenca.j};background:var(--c-homenagem)" title="Falta: ${v.presenca.t - v.presenca.p - v.presenca.j}"></span>` : ""}</div>
      <div class="leg-din"><div><i style="background:var(--c-lei)"></i><span>Presente</span><b>${v.presenca.p}</b></div><div><i style="background:var(--ambar)"></i><span>Falta justificada</span><b>${v.presenca.j}</b></div><div><i style="background:var(--c-homenagem)"></i><span>Falta sem justificativa</span><b>${v.presenca.t - v.presenca.p - v.presenca.j}</b></div></div>` : ""}
      <h3 class="sub">Comparado com a média da Câmara</h3>
      <div class="comp">${ORDEM.map(c => {
        const dif = R.media[c] ? Math.round((v.cats[c] / R.media[c] - 1) * 100) : null;
        return `<div class="comp-l"><span>${CATS[c].nome}</span>
          <span class="comp-b"><i style="width:${(v.cats[c] / mx * 100).toFixed(1)}%;background:${cor(c)}"></i><i class="m" style="width:${(R.media[c] / mx * 100).toFixed(1)}%"></i></span>
          <span class="comp-n"><b>${fmt(v.cats[c])}</b> × ${dec(R.media[c])}${dif === null || !isFinite(dif) ? "" : ` <em class="${dif >= 0 ? "ac" : "ab"}">${dif >= 0 ? "+" : ""}${dif}%</em>`}</span></div>`;
      }).join("")}</div>
      <p class="nota">Barra colorida: ${esc(v.apelido.split(" ")[0])}. Barra cinza: média dos vereadores em exercício.</p>
      <h3 class="sub">Mês a mês</h3>
      <div class="lt pequena">${linhaTempo(v.mensal, { referencia: mediaMes })}</div>
      <p class="nota">O traço escuro em cada mês é a média da Câmara.</p>
      <h3 class="sub">Tudo o que apresentou</h3>` + listaDocs(d => d.a.includes(v.id), { comCat: true });
    abre(v.apelido, html);
    const c = $("#folha-conteudo");
    c.querySelector(".linhas-cat").addEventListener("click", e => {
      const b = e.target.closest(".linha-cat");
      if (b) location.hash = `#/vereador/${v.id}/${b.dataset.c}`;
    });
    c.querySelector("[data-ir]")?.addEventListener("click", e => location.hash = e.currentTarget.dataset.ir);
    c.querySelector("#copiar").addEventListener("click", async e => {
      const b = e.currentTarget;
      try {
        if (navigator.share && matchMedia("(pointer: coarse)").matches) await navigator.share({ title: `${v.apelido} — ${R.cidade.titulo}`, url: b.dataset.link });
        else { await navigator.clipboard.writeText(b.dataset.link); b.textContent = "Link copiado"; setTimeout(() => b.textContent = "Copiar link", 2000); }
      } catch { prompt("Copie o link:", b.dataset.link); }
    });
  }

  const maisAntigo = (a, b) => a.d < b.d ? -1 : 1;
  function rota() {
    if (!R) return;
    const p = location.hash.replace(/^#\/?/, "").split("/").map(decodeURIComponent);
    const resp = R.executivo?.respostas;
    if (p[0] === "vereador" && porId[p[1]]) {
      const v = porId[p[1]];
      if (p[2] && CATS[p[2]]) return abre(`${v.apelido}: ${CATS[p[2]].nome.toLowerCase()}`, listaDocs(d => d.a.includes(v.id) && d.c === p[2]));
      return perfil(v);
    }
    if (p[0] === "prefeito" && R.prefeito && R.executivo?.projetos) return perfilPrefeito();
    if (p[0] === "folha" && temFinancas) return F ? folhaDetalhe() : null;
    if (p[0] === "receitas" && temFinancas) return F && F.anos[p[1]] ? receitasDetalhe(p[1]) : null;
    if (p[0] === "categoria" && CATS[p[1]]) return abre(CATS[p[1]].nome, `<p class="nota">${CATS[p[1]].desc}</p>` + listaDocs(d => d.c === p[1] && d.a.length));
    if (p[0] === "mes" && R.meses.includes(p[1])) return abre(`Apresentado em ${mesNome(p[1])}`, listaDocs(d => d.d.startsWith(p[1]) && d.a.length, { comCat: true }));
    if (p[0] === "tema") return abre(`Pedidos: ${p[1].toLowerCase()}`, listaDocs(d => d.c === "bairro" && d.a.length && (d.tm || "Outros pedidos") === p[1]));
    if ((p[0] === "rua" && R.vias[p[1]]) || (p[0] === "repetido" && R.repetidos[p[1]])) {
      const r = (p[0] === "rua" ? R.vias : R.repetidos)[p[1]], ids = new Set(r.ids);
      const tit = r.via + (r.bairro ? ` · ${r.bairro}` : "");
      const oque = p[0] === "rua" ? `${r.n} pedidos` : `${r.n} pedidos de ${r.frase}`;
      return abre(tit, `<p class="razao">${oque} entre ${dt(r.primeiro)} e ${dt(r.ultimo)}. Quem mais pediu: ${esc(quemPediu(r))}.</p><p class="nota">${r.bairro ? "O nome da via e do bairro são lidos" : "O nome da via é lido"} do texto do pedido${r.bairro ? "" : ", e este grupo junta os pedidos que não dizem o bairro"}. Confira em cada documento.</p>` + listaDocs(d => ids.has(d.id)));
    }
    if (p[0] === "votacoes") {
      const vs = R.votacoes.divididas;
      return abre("Votações com voto contrário", `<p class="nota">Resultado copiado do registro de cada documento no sistema da Câmara.</p>` + (vs.length ? vs.map(v => `
        <article class="doc"><div class="cab"><a href="${R.doc_url}${v.id}" target="_blank" rel="noopener">${esc(v.titulo)}</a><span>${v.aprovado ? "Aprovado" : "Rejeitado"}${v.contrarios ? ` · ${pl(v.contrarios, "contra", "contra")}` : ""}</span></div>
        <p>${esc(v.assunto)}</p><div class="cab" style="margin-top:.35rem"><span>${esc(v.texto)}</span></div></article>`).join("") : `<p class="vazio">Nenhuma votação com voto contrário registrada.</p>`));
    }
    if (p[0] === "sem-resposta" && resp) {
      const v = porId[p[1]];
      const f = d => d.q && !d.r && d.d >= resp.desde && diasEntre(d.d, HOJE) > resp.prazo && (!v || d.a.includes(v.id));
      return abre(v ? `${v.apelido}: sem resposta` : "Requerimentos sem resposta", `<p class="nota">Requerimentos apresentados desde ${dt(resp.desde)} que estão há mais de ${resp.prazo} dias sem resposta registrada no sistema da Câmara. Os mais antigos vêm primeiro.</p>` + listaDocs(f, { ordenar: maisAntigo, comCat: true }));
    }
    if (p[0] === "vetos" && R.executivo?.vetos) {
      const rot = { mantido: "Veto mantido", derrubado: "Veto derrubado", pendente: "Sem decisão registrada" };
      return abre("Vetos do prefeito", `<p class="nota">Quando o prefeito veta um projeto aprovado, os vereadores votam se mantêm ou derrubam o veto.</p>` + R.executivo.vetos.lista.map(v => `
        <article class="doc"><div class="cab"><a href="${esc(v.url)}" target="_blank" rel="noopener">${esc(v.titulo)}</a><span>${dt(v.data)}</span></div>
        <p>${esc(v.assunto)}</p><div class="cab" style="margin-top:.35rem"><span>${esc(v.tipo)}</span><span class="pill" style="--cor:${v.resultado === "derrubado" ? "var(--c-lei)" : v.resultado === "mantido" ? "var(--c-homenagem)" : "var(--c-outros)"}">${rot[v.resultado]}</span></div></article>`).join(""));
    }
    if (p[0] === "projetos" && R.executivo?.projetos?.[p[1]]) {
      const ids = new Set(R.executivo.projetos[p[1]].ids);
      return abre(p[1] === "executivo" ? "Projetos de lei do prefeito" : "Projetos de lei dos vereadores", listaDocs(d => ids.has(d.id), { comSituacao: true, semAutor: p[1] === "executivo" }));
    }
    if (p[0] === "sessao" && R.presenca?.sessoes[p[1]]) {
      const s = R.presenca.sessoes[p[1]];
      const nomes = j => s.faltas.filter(f => f[1] === j).map(f => esc(porId[f[0]]?.apelido ?? f[0]));
      const a = nomes(0), j = nomes(1);
      return abre(dt(s.data), `<p class="razao">${esc(s.nome)}</p>
        ${a.length ? `<h3 class="sub">Faltaram</h3><p>${a.join(", ")}</p>` : `<p>Nenhuma falta sem justificativa.</p>`}
        ${j.length ? `<h3 class="sub">Falta justificada</h3><p>${j.join(", ")}</p>` : ""}
        <p><a href="${esc(s.url)}" target="_blank" rel="noopener">Ver a sessão no sistema da Câmara</a></p>`);
    }
    if (!folha.hidden) fecha();
  }
  addEventListener("hashchange", rota);
})();
