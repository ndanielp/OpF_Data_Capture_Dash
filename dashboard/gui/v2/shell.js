/* Dashboard 2.0 — casca compartilhada (Constituição §6.8).
   Header, abas, estado entre abas, preferências do ranking, tema, formatação e CSV.
   JS puro, sem bundler: expõe tudo em window.V2. */
(function () {
  'use strict';

  const V2 = (window.V2 = {});

  const TABS = [
    { id: 'lidera', label: 'Quem lidera?', href: '/v2' },
    { id: 'evolucao', label: 'Como evolui?', href: '/v2/evolucao' },
    { id: 'mudancas', label: 'O que mudou?', href: '/v2/mudancas' },
    { id: 'instituicao', label: 'Como opera uma instituição?', href: '/v2/instituicao' },
  ];
  const KEY_FILTERS = 'opf:v2:filters';
  const KEY_PREFS = 'opf:v2:ranking';
  const KEY_THEME = 'opf:v2:theme';

  // ── Armazenamento tolerante a falhas ─────────────────────────────────────
  function readJSON(store, key) {
    try { return JSON.parse(window[store].getItem(key) || 'null'); } catch (e) { return null; }
  }
  function writeJSON(store, key, value) {
    try { window[store].setItem(key, JSON.stringify(value)); } catch (e) { /* storage indisponível */ }
  }

  V2.getFilters = function () { return readJSON('sessionStorage', KEY_FILTERS) || {}; };
  V2.setFilters = function (partial) {
    writeJSON('sessionStorage', KEY_FILTERS, Object.assign({}, V2.getFilters(), partial));
  };

  /** Períodos do filtro, comuns às abas que o têm: [rótulo, dias, rótulo curto]. Dias nulo =
      toda a base; 'ytd' = desde 1º de janeiro do ano da semana mais recente com dados. */
  V2.PERIODS = {
    '12m': ['Últimos 12 meses', 364, '12 meses'],
    '6m': ['Últimos 6 meses', 182, '6 meses'],
    '3m': ['Últimos 3 meses', 91, '3 meses'],
    'ytd': ['Desde o começo do ano', 'ytd', null],
    'all': ['Desde o início', null, 'no período'],
  };
  /** Data inicial (AAAA-MM-DD) do período. O ano de 'ytd' vem do dado, não do relógio: com a
      base ainda em dezembro, "começo do ano" continua sendo o do ano anterior. */
  V2.periodStart = function (key) {
    const days = V2.PERIODS[key][1];
    if (days == null) return '2000-01-01';
    if (!V2.meta || !V2.meta.data_through) return null;
    if (days === 'ytd') return V2.meta.data_through.slice(0, 4) + '-01-01';
    const d = new Date(V2.meta.data_through + 'T00:00:00Z');
    d.setUTCDate(d.getUTCDate() - days);
    return d.toISOString().slice(0, 10);
  };
  /** Rótulo curto para frases como "crescimento em …" (o ano, no período anual). */
  V2.periodShort = function (key) {
    return key === 'ytd' ? ((V2.meta && V2.meta.data_through) || '').slice(0, 4) : V2.PERIODS[key][2];
  };

  /** Preferências do ranking. Primeiro acesso: Bradesco em "Sempre mostrar". */
  V2.getPrefs = function () {
    const p = readJSON('localStorage', KEY_PREFS);
    if (p && p.initialized) return p;
    const brad = (V2.meta && V2.meta.institutions || []).find(i => /bradesco/i.test(i.name));
    return { pinned: brad ? [brad.uuid] : [], excluded: [], sort: 'total', initialized: true };
  };
  V2.setPrefs = function (prefs) {
    writeJSON('localStorage', KEY_PREFS, Object.assign({}, prefs, { initialized: true }));
  };
  /** Fixar e excluir são exclusivos: entrar numa lista tira da outra. */
  V2.pin = function (uuid) {
    const p = V2.getPrefs();
    p.excluded = p.excluded.filter(u => u !== uuid);
    if (!p.pinned.includes(uuid)) p.pinned.push(uuid);
    V2.setPrefs(p);
  };
  V2.exclude = function (uuid) {
    const p = V2.getPrefs();
    p.pinned = p.pinned.filter(u => u !== uuid);
    if (!p.excluded.includes(uuid)) p.excluded.push(uuid);
    V2.setPrefs(p);
  };
  V2.unpin = function (uuid) { const p = V2.getPrefs(); p.pinned = p.pinned.filter(u => u !== uuid); V2.setPrefs(p); };
  V2.unexclude = function (uuid) { const p = V2.getPrefs(); p.excluded = p.excluded.filter(u => u !== uuid); V2.setPrefs(p); };

  // ── Tema ─────────────────────────────────────────────────────────────────
  V2.getTheme = function () {
    try { return localStorage.getItem(KEY_THEME) || 'light'; } catch (e) { return 'light'; }
  };
  const themeListeners = [];
  /** As páginas redesenham o que foi pintado por JS (gráficos, cores de grupo) quando o tema muda. */
  V2.onThemeChange = function (fn) { themeListeners.push(fn); };
  V2.toggleTheme = function () {
    const next = V2.getTheme() === 'dark' ? 'light' : 'dark';
    try { localStorage.setItem(KEY_THEME, next); } catch (e) { /* ok */ }
    document.documentElement.dataset.theme = next;
    themeListeners.forEach(fn => { try { fn(); } catch (e) { console.error(e); } });
  };

  // ── Rede e estados ───────────────────────────────────────────────────────
  V2.fetchJSON = async function (url) {
    let res;
    try { res = await fetch(url); } catch (e) {
      throw new Error('Não foi possível falar com o servidor. Verifique a conexão e recarregue a página.');
    }
    if (!res.ok) {
      let detail = '';
      try { detail = (await res.json()).detail || ''; } catch (e) { /* sem corpo */ }
      throw new Error(detail || 'O servidor não conseguiu montar estes dados agora. Tente de novo em instantes.');
    }
    return res.json();
  };
  V2.setLoading = function (el, on) { if (el) el.classList.toggle('loading', !!on); };
  V2.errorBox = function (msg) { return '<div class="v2-error" role="alert">' + V2.esc(msg) + '</div>'; };

  // ── Formatação (pt-BR) ───────────────────────────────────────────────────
  const nf = (d) => new Intl.NumberFormat('pt-BR', { minimumFractionDigits: d, maximumFractionDigits: d });
  V2.esc = function (s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  };
  V2.fmtInt = function (v) { return v == null ? '—' : nf(0).format(Math.round(v)); };
  /** 22,04 mi · 145,9 mi · 4,51 bi · 409,0 mil · 9.324 */
  V2.fmtCompact = function (v) {
    if (v == null || isNaN(v)) return '—';
    const a = Math.abs(v);
    if (a >= 1e9) return nf(a >= 100e9 ? 1 : 2).format(v / 1e9) + ' bi';
    if (a >= 1e6) return nf(a >= 100e6 ? 1 : 2).format(v / 1e6) + ' mi';
    if (a >= 1e4) return nf(1).format(v / 1e3) + ' mil';
    return nf(0).format(Math.round(v));
  };
  V2.fmtShare = function (s) { return s == null ? '—' : nf(1).format(s * 100) + '%'; };
  /** Número com `digits` casas decimais (vírgula decimal, separador de milhar). */
  V2.fmtDec = function (v, digits) { return v == null || isNaN(v) ? '—' : nf(digits).format(v); };
  /** Variação em pontos percentuais; `v` já vem em pp (para fração, use fmtPp(v * 100)). */
  V2.fmtPp = function (v) { return v == null ? '—' : (v > 0 ? '+' : v < 0 ? '−' : '') + nf(1).format(Math.abs(v)) + ' pp'; };
  /** Eixo de gráfico: 25 mi · 2,5 mi · 800 mil — sem casas decimais sobrando. */
  V2.fmtAxis = function (v) {
    const f = dd => new Intl.NumberFormat('pt-BR', { maximumFractionDigits: dd });
    if (Math.abs(v) >= 1e9) return f(1).format(v / 1e9) + ' bi';
    if (Math.abs(v) >= 1e6) return f(1).format(v / 1e6) + ' mi';
    if (Math.abs(v) >= 1e3) return f(0).format(v / 1e3) + ' mil';
    return f(0).format(v);
  };
  V2.cssVar = function (name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); };
  /** Controle segmentado (escolha única): `options` = { valor: rótulo }. */
  V2.seg = function (name, options, current) {
    return '<div class="v2-seg" data-seg="' + name + '">' + Object.entries(options).map(([k, l]) =>
      '<button type="button" data-v="' + k + '" aria-pressed="' + (k === current) + '">' + l + '</button>').join('') + '</div>';
  };
  V2.allGroups = function () { return V2.meta.groups.map(g => g.slug); };
  /** Grupos em uso: os escolhidos, ou todos quando nenhum foi escolhido. */
  V2.activeGroups = function (selected) { return selected.length ? selected : V2.allGroups(); };
  V2.fmtPct = function (p, digits) {
    if (p == null) return '—';
    const sign = p > 0 ? '+' : p < 0 ? '−' : '';
    return sign + nf(digits || 0).format(Math.abs(p) * 100) + '%';
  };
  V2.fmtSigned = function (v) {
    if (v == null) return '—';
    const sign = v > 0 ? '+' : v < 0 ? '−' : '';
    return sign + V2.fmtCompact(Math.abs(v));
  };
  const MONTHS = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'];
  V2.fmtMonth = function (ym) { // "2025-10" → "out/25"
    if (!ym) return '';
    const [y, m] = ym.split('-');
    return MONTHS[Number(m) - 1] + '/' + y.slice(2);
  };
  V2.fmtDate = function (iso) { // "2026-08-28" → "28/08/2026"
    if (!iso) return '—';
    const [y, m, d] = iso.slice(0, 10).split('-');
    return d + '/' + m + '/' + y;
  };
  /** +49% · ×5,0 · estreou out/25 · sem base */
  V2.fmtGrowth = function (g) {
    if (!g) return '—';
    if (g.kind === 'pct') return V2.fmtPct(g.value);
    if (g.kind === 'multiplier') return g.value > 100 ? '×100+' : '×' + nf(g.value < 20 ? 1 : 0).format(g.value);
    if (g.kind === 'debut') return 'estreou ' + V2.fmtMonth(g.debut_month);
    return 'sem base';
  };
  /** neutral: seta sem cor de bom/ruim (ex.: erros, onde cair é bom). */
  V2.trendArrow = function (trend, neutral) {
    const cls = c => neutral ? 'v2-flat' : c;
    if (trend === 'up') return '<span class="' + cls('v2-up') + '" aria-label="acelerando">↑</span>';
    if (trend === 'down') return '<span class="' + cls('v2-down') + '" aria-label="desacelerando">↓</span>';
    return '<span class="v2-flat" aria-label="estável">→</span>';
  };

  // ── Ícones (traço, sem emoji) ────────────────────────────────────────────
  const SVG = {
    image: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="9" cy="10" r="1.6"/><path d="M21 16l-5-5-8 8"/></svg>',
    download: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 4v11"/><path d="M7 10l5 5 5-5"/><path d="M5 20h14"/></svg>',
    pin: '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 17v5"/><path d="M9 3h6l-1 6 3 3v2H7v-2l3-3z"/></svg>',
    theme: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>',
  };
  V2.icon = function (name) { return SVG[name] || ''; };

  // ── Header ───────────────────────────────────────────────────────────────
  V2.groupColor = function (slug) {
    const g = (V2.meta && V2.meta.groups || []).find(x => x.slug === slug);
    if (!g) return 'var(--text-2)';
    return document.documentElement.dataset.theme === 'dark' && g.color_dark ? g.color_dark : g.color;
  };
  V2.groupLabel = function (slug) {
    const g = (V2.meta && V2.meta.groups || []).find(x => x.slug === slug);
    return g ? g.label : slug;
  };

  function renderHeader(tabId) {
    const el = document.getElementById('v2-header');
    const m = V2.meta || {};
    const tabs = TABS.map(t => '<a href="' + t.href + '"' + (t.id === tabId ? ' aria-current="page"' : '') + '>' + t.label + '</a>').join('');
    const dates = m.data_through
      ? 'Dados até ' + V2.fmtDate(m.data_through) + (m.updated_at ? ' · atualizado em ' + V2.fmtDate(m.updated_at).slice(0, 5) : '')
      : '';
    el.className = 'v2-header';
    el.innerHTML =
      '<div class="v2-header-inner">' +
        '<div class="v2-header-left"><span class="v2-brand">Open Finance · Ecossistema</span>' +
        '<nav class="v2-tabs" aria-label="Perguntas">' + tabs + '</nav></div>' +
        '<div class="v2-header-right"><span>' + dates + '</span>' +
        '<button type="button" class="v2-icon-btn" id="v2-theme" aria-label="Alternar tema claro/escuro">' + SVG.theme + '</button>' +
        '<a href="/" title="Painel atual (legado)">Painel legado</a></div>' +
      '</div>';
    document.getElementById('v2-theme').addEventListener('click', V2.toggleTheme);
  }

  /** Monta o header e carrega o catálogo. Devolve meta. */
  V2.initShell = async function (tabId) {
    document.documentElement.dataset.theme = V2.getTheme();
    try {
      V2.meta = await V2.fetchJSON('/api/v2/meta');
    } catch (e) {
      V2.meta = { groups: [], api_groups: [], institutions: [] };
      renderHeader(tabId);
      throw e;
    }
    renderHeader(tabId);
    return V2.meta;
  };

  // ── Popover de busca de instituição ──────────────────────────────────────
  V2.closePopover = function () {
    const p = document.querySelector('.v2-popover');
    if (p) p.remove();
    document.removeEventListener('mousedown', outsideClose, true);
  };
  function outsideClose(ev) {
    const p = document.querySelector('.v2-popover');
    if (p && !p.contains(ev.target)) V2.closePopover();
  }
  function placePopover(pop, anchor) {
    const r = anchor.getBoundingClientRect();
    pop.style.top = (window.scrollY + r.bottom + 6) + 'px';
    pop.style.left = Math.max(8, Math.min(window.scrollX + r.left, window.scrollX + document.documentElement.clientWidth - 300)) + 'px';
    document.body.appendChild(pop);
    setTimeout(() => document.addEventListener('mousedown', outsideClose, true), 0);
    pop.addEventListener('keydown', ev => { if (ev.key === 'Escape') { V2.closePopover(); anchor.focus(); } });
  }

  /** Busca em meta.institutions; onPick(uuid). `skip` = uuids a esconder.
   *  opts.list troca o catálogo (ex.: transmissores); opts.first = uuids sugeridos no topo. */
  V2.openInstitutionPicker = function (anchor, onPick, skip, opts) {
    opts = opts || {};
    V2.closePopover();
    const pop = document.createElement('div');
    pop.className = 'v2-popover';
    pop.setAttribute('role', 'dialog');
    pop.setAttribute('aria-label', 'Buscar instituição');
    pop.innerHTML = '<input type="search" placeholder="Buscar instituição…" aria-label="Buscar instituição"><div class="v2-results"></div>';
    const input = pop.querySelector('input');
    const results = pop.querySelector('.v2-results');
    const norm = s => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
    function draw() {
      const q = norm(input.value.trim());
      const first = opts.first || [];
      const rank = i => { const k = first.indexOf(i.uuid); return k < 0 ? first.length : k; };
      const list = (opts.list || V2.meta.institutions || []).slice()
        .sort((a, b) => q ? 0 : rank(a) - rank(b))
        .filter(i => !(skip || []).includes(i.uuid))
        .filter(i => !q || norm(i.short).includes(q) || norm(i.name).includes(q))
        .slice(0, 8);
      results.innerHTML = list.length
        ? list.map(i => '<button type="button" data-uuid="' + i.uuid + '"><span class="v2-dot" style="background:' + V2.groupColor(i.group) + '"></span>' + V2.esc(i.short) + '</button>').join('')
        : '<div class="v2-empty">Nenhuma instituição encontrada</div>';
    }
    results.addEventListener('click', ev => {
      const b = ev.target.closest('button[data-uuid]');
      if (b) { V2.closePopover(); onPick(b.dataset.uuid); }
    });
    input.addEventListener('input', draw);
    draw();
    placePopover(pop, anchor);
    input.focus();
  };

  /** Menu simples: items = [{label, onClick, link}] */
  V2.openMenu = function (anchor, label, items) {
    V2.closePopover();
    const pop = document.createElement('div');
    pop.className = 'v2-popover';
    pop.setAttribute('role', 'menu');
    pop.setAttribute('aria-label', label);
    items.forEach(it => {
      const b = document.createElement('button');
      b.type = 'button';
      b.setAttribute('role', 'menuitem');
      b.textContent = it.label;
      if (it.link) b.className = 'v2-menu-link';
      b.addEventListener('click', () => { V2.closePopover(); it.onClick(); });
      pop.appendChild(b);
    });
    pop.addEventListener('keydown', ev => {
      const btns = Array.from(pop.querySelectorAll('button'));
      const i = btns.indexOf(document.activeElement);
      if (ev.key === 'ArrowDown') { ev.preventDefault(); btns[(i + 1) % btns.length].focus(); }
      if (ev.key === 'ArrowUp') { ev.preventDefault(); btns[(i - 1 + btns.length) % btns.length].focus(); }
    });
    placePopover(pop, anchor);
    pop.querySelector('button').focus();
  };

  // ── Alertas: rótulos e descrição curta ───────────────────────────────────
  V2.KIND_LABEL = { decrease: 'Queda', increase: 'Alta', mixed: 'Quedas e altas', oscillation: 'Oscilação', new_entrant: 'Novo entrante' };
  V2.KIND_CLASS = { decrease: 'decrease', increase: 'increase', mixed: 'decrease', oscillation: 'oscillation', new_entrant: 'new_entrant' };
  V2.ordinalStreak = function (n) { return n >= 2 ? n + 'º mês seguido' : ''; };
  /** Valor de alerta: API em mi/bi; consentimentos inteiros abaixo de 1 mi. */
  V2.fmtAlertValue = function (v, metric) {
    if (v == null) return '—';
    return metric === 'api_group' || Math.abs(v) >= 1e6 ? V2.fmtCompact(v) : V2.fmtInt(v);
  };
  /** Frase curta para o resumo da aba 1 (uma linha por instituição). */
  V2.describeEvent = function (e) {
    const items = e.items;
    if (e.kind === 'new_entrant') {
      const it = items.find(i => i.signal_type === 'new_entrant');
      return 'Passou de 30 mil consentimentos únicos em ' + V2.fmtDate(it.week).slice(0, 5) + ' (' + V2.fmtInt(it.value_curr) + ')';
    }
    if (e.kind === 'oscillation') {
      return items[0].metric_label + ' ' + (items[0].signal_type === 'decrease' ? 'caíram e voltaram' : 'subiram e voltaram') + ' em uma semana';
    }
    const api = items.filter(i => i.metric === 'api_group');
    const cons = items.filter(i => i.metric !== 'api_group');
    const parts = [];
    if (api.length > 1) parts.push('API em ' + (e.kind === 'increase' ? 'alta' : 'queda') + ' em ' + api.length + ' grupos (' + api.map(i => i.api_group_label).join(', ') + ')');
    else if (api.length === 1) parts.push('API de ' + api[0].api_group_label);
    cons.forEach(i => parts.push(i.metric_label + ' ' + V2.fmtPct(i.change_pct)));
    if (e.streak_months >= 2) parts.push(V2.ordinalStreak(e.streak_months));
    return parts.join(' · ');
  };
  /** Número em destaque do evento. */
  V2.eventHeadline = function (e) {
    if (e.kind === 'new_entrant') {
      const it = e.items.find(i => i.signal_type === 'new_entrant');
      return V2.fmtCompact(it.value_curr);
    }
    if (e.kind === 'oscillation') return e.items.map(i => V2.fmtPct(i.change_pct)).join(' → ');
    const top = e.items.reduce((a, i) => (i.change_pct != null && (a == null || Math.abs(i.change_pct) > Math.abs(a.change_pct))) ? i : a, null);
    return top ? V2.fmtPct(top.change_pct) : '';
  };

  // ── Exportação de imagem 16:9 (html-to-image, carregado só quando usado) ──
  let h2iLoading = null;
  function loadHtmlToImage() {
    if (window.htmlToImage) return Promise.resolve();
    if (!h2iLoading) {
      h2iLoading = new Promise((resolve, reject) => {
        const s = document.createElement('script');
        s.src = 'https://cdn.jsdelivr.net/npm/html-to-image@1.11.11/dist/html-to-image.js';
        s.onload = resolve;
        s.onerror = () => { h2iLoading = null; reject(new Error('Não foi possível carregar o exportador de imagem. Verifique a conexão; o CSV continua disponível.')); };
        document.head.appendChild(s);
      });
    }
    return h2iLoading;
  }

  const FRAME_W = 1600, FRAME_H = 900, FRAME_PAD = 56;

  /** Quadro 1600×900 das imagens exportadas: subtítulo e título no alto, `body` no meio (quem
   *  chama preenche) e rodapé de fonte. Fica fora da tela até virar PNG. */
  function newFrame(opts) {
    const css = getComputedStyle(document.documentElement);
    const frame = document.createElement('div');
    frame.style.cssText = 'position:fixed;left:-20000px;top:0;width:' + FRAME_W + 'px;height:' + FRAME_H + 'px;box-sizing:border-box;' +
      'padding:' + FRAME_PAD + 'px ' + FRAME_PAD + 'px 40px;display:flex;flex-direction:column;gap:18px;overflow:hidden;' +
      'background:' + css.getPropertyValue('--surface') + ';color:' + css.getPropertyValue('--text') + ';' +
      "font-family:'IBM Plex Sans','Segoe UI',system-ui,sans-serif;font-variant-numeric:tabular-nums;";
    const head = document.createElement('div');
    head.innerHTML = '<div style="font-size:var(--text-body-lg);font-weight:600;letter-spacing:.04em;text-transform:uppercase;color:' +
      css.getPropertyValue('--text-2') + '">' + V2.esc(opts.subtitle || '') + '</div>' +
      '<div style="font-size:var(--text-kpi-lg);font-weight:700;letter-spacing:-.01em;margin-top:var(--sp-1h)">' + V2.esc(opts.title || '') + '</div>';
    const body = document.createElement('div');
    body.style.cssText = 'flex:1;min-height:0;position:relative;';
    const foot = document.createElement('div');
    foot.style.cssText = 'font-size:var(--text-body);color:' + css.getPropertyValue('--text-2') + ';border-top:1px solid ' +
      css.getPropertyValue('--border') + ';padding-top:var(--sp-3);display:flex;justify-content:space-between;gap:var(--sp-4)';
    foot.innerHTML = '<span>' + V2.esc(opts.note || '') + '</span><span>Fonte: dashboard Open Finance Brasil · dados até ' +
      V2.fmtDate(V2.meta && V2.meta.data_through) + '</span>';
    frame.append(head, body, foot);
    return { frame, body };
  }

  /** Transforma o quadro em PNG e baixa; o quadro sai da página no fim. */
  async function downloadFrame(frame, filename) {
    try {
      await loadHtmlToImage();
      // O quadro fica fora da tela; no clone que vira imagem ele volta para a origem.
      const base = { width: FRAME_W, height: FRAME_H, pixelRatio: 1, style: { position: 'static', left: '0', top: '0' } };
      let url;
      try { url = await window.htmlToImage.toPng(frame, base); }
      catch (e) { url = await window.htmlToImage.toPng(frame, Object.assign({ skipFonts: true }, base)); }
      const a = document.createElement('a');
      a.href = url;
      a.download = filename || 'opf-bloco.png';
      document.body.appendChild(a);
      a.click();
      a.remove();
    } finally {
      frame.remove();
    }
  }

  /** Clona o bloco num quadro 1600×900 com título (com filtro), subtítulo,
   *  conteúdo ajustado ao espaço e rodapé de fonte, e baixa um PNG. */
  V2.exportImage = async function (card, opts) {
    const W = FRAME_W, PAD = FRAME_PAD;
    const { frame, body } = newFrame(opts);
    const inner = card.cloneNode(true);
    inner.querySelectorAll('.v2-card-head, .v2-card-actions, .v2-row-menu, button, .v2-card-foot, .v2-noexport').forEach(n => n.remove());
    inner.style.cssText = 'border:0;padding:0;background:transparent;box-shadow:none;';
    const origCanvases = card.querySelectorAll('canvas');
    inner.querySelectorAll('canvas').forEach((c, i) => {
      const img = document.createElement('img');
      img.src = origCanvases[i].toDataURL('image/png');
      img.style.width = origCanvases[i].clientWidth + 'px';
      c.replaceWith(img);
    });
    body.appendChild(inner);
    document.body.appendChild(frame);

    // Conteúdo maior que o espaço: reduz por escala, preenchendo a largura.
    const availW = W - 2 * PAD, availH = body.clientHeight;
    inner.style.width = availW + 'px';
    const s = Math.min(1, availH / inner.scrollHeight);
    if (s < 1) {
      inner.style.width = (availW / s) + 'px';
      inner.style.transform = 'scale(' + s + ')';
      inner.style.transformOrigin = 'top left';
    }
    await downloadFrame(frame, opts.filename);
  };

  /** Slide 16:9 de uma página: blocos no quadro das imagens exportadas.
   *  opts = { title, subtitle, note, filename, rows: [{ weight, cells: [cell] }] }, cell = { el, weight, title, more, chart }
   *  ou { weight, stack: [cell, …] } (células empilhadas numa coluna; weight = altura relativa dentro dela).
   *  - rows[].weight: altura relativa da linha (0 = a do conteúdo); cell.weight: largura relativa.
   *  - cell.el: bloco da página (clonado, sem cabeçalho, ações, seletores nem rodapé).
   *  - cell.title: true = título e subtítulo do bloco no alto da célula.
   *  - cell.chart: (largura, altura) => URL do PNG; o gráfico é redesenhado no tamanho da célula.
   *  - cell.more: nome dos itens ("transmissores"); o que não cabe sai da lista (do fim para o início) e a
   *    célula diz "+N transmissores" — o texto nunca é reduzido. Sem `more`, o bloco sai completo: se não
   *    couber, a exportação falha em vez de cortar. */
  V2.exportSlide = async function (opts) {
    const { frame, body } = newFrame(opts);
    frame.classList.add('v2-slide');
    body.style.cssText += ';display:flex;flex-direction:column;gap:var(--sp-4);';
    const cells = [];
    const makeCell = def => {
      const c = def.el.cloneNode(true);
      c.querySelectorAll('.v2-card-head, .v2-card-actions, .v2-row-menu, button, .v2-card-foot, .v2-noexport, .v2-noslide, .v2-field, .v2-seg, select').forEach(n => n.remove());
      c.querySelectorAll(':scope > div:empty').forEach(n => n.remove());
      c.removeAttribute('id');
      c.classList.remove('loading');
      c.style.cssText = 'box-sizing:border-box;min-width:0;min-height:0;overflow:hidden;';
      if (def.title) {
        const h = document.createElement('div');
        h.className = 'v2-card-head';
        h.innerHTML = '<div><h2></h2><span class="v2-sub" style="display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden"></span></div>';
        h.querySelector('h2').textContent = def.el.querySelector('h2').textContent;
        h.querySelector('.v2-sub').textContent = def.el.querySelector('.v2-sub').textContent;
        c.prepend(h);
      }
      cells.push({ def, c });
      return c;
    };
    opts.rows.forEach(row => {
      const r = document.createElement('div');
      // Grade com minmax(0, Nfr): larguras proporcionais ao peso mesmo com borda e padding nas células.
      const fr = list => list.map(x => 'minmax(0,' + (x.weight || 1) + 'fr)').join(' ');
      r.style.cssText = 'display:grid;grid-template-columns:' + fr(row.cells) + ';gap:var(--sp-4);min-height:0;' + (row.weight ? 'flex:' + row.weight + ' 1 0;' : 'flex:0 0 auto;');
      row.cells.forEach(def => {
        if (!def.stack) return r.appendChild(makeCell(def));
        const col = document.createElement('div');
        col.style.cssText = 'display:grid;grid-template-rows:' + fr(def.stack) + ';gap:var(--sp-4);min-width:0;min-height:0;';
        def.stack.forEach(s => col.appendChild(makeCell(s)));
        r.appendChild(col);
      });
      body.appendChild(r);
    });
    document.body.appendChild(frame);

    try {
      for (const { def, c } of cells) {
        if (def.chart) {
          const host = c.querySelector('.in-chart');
          const canvas = host.querySelector('canvas');
          host.style.cssText = 'flex:1 1 0;min-height:0;height:auto;position:relative;';
          canvas.remove();
          const w = host.clientWidth, h = host.clientHeight;
          const img = document.createElement('img');
          img.src = await def.chart(w, h);
          img.style.cssText = 'display:block;width:' + w + 'px;height:' + h + 'px;';
          host.appendChild(img);
        }
        const over = () => c.scrollHeight > c.clientHeight;
        const lists = c.querySelectorAll('ul.in-list');
        const list = lists[lists.length - 1];
        if (list && def.more) {
          const note = document.createElement('div');
          note.className = 'v2-small v2-muted';
          note.style.display = 'none';
          list.after(note);
          let hidden = 0;
          while (over() && list.lastElementChild) {
            list.lastElementChild.remove();
            hidden++;
            note.textContent = '+' + hidden + ' ' + def.more;
            note.style.display = '';
          }
        } else if (!def.chart && over()) {
          const h2 = def.el.querySelector('h2');
          throw new Error('O bloco "' + (h2 ? h2.textContent : 'sem título') + '" não cabe no slide.');
        }
      }
      await downloadFrame(frame, opts.filename);
    } catch (e) {
      frame.remove();
      throw e;
    }
  };

  // ── Exportação CSV ───────────────────────────────────────────────────────
  /** columns: [{label, value: row => string|number}] — números saem com vírgula decimal. */
  V2.exportCSV = function (filename, columns, rows) {
    const cell = v => {
      if (v == null) return '';
      if (typeof v === 'number') return String(v).replace('.', ',');
      const s = String(v);
      return /[;"\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
    };
    const lines = [columns.map(c => cell(c.label)).join(';')]
      .concat(rows.map(r => columns.map(c => cell(c.value(r))).join(';')));
    const blob = new Blob(['﻿' + lines.join('\r\n')], { type: 'text/csv;charset=utf-8' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 0);
  };
})();
