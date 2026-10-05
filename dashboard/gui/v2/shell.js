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
  V2.toggleTheme = function () {
    const next = V2.getTheme() === 'dark' ? 'light' : 'dark';
    try { localStorage.setItem(KEY_THEME, next); } catch (e) { /* ok */ }
    document.documentElement.dataset.theme = next;
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
    if (g.kind === 'multiplier') return '×' + nf(g.value < 20 ? 1 : 0).format(g.value);
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
    return g ? g.color : 'var(--text-2)';
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

  /** Busca em meta.institutions; onPick(uuid). `skip` = uuids a esconder. */
  V2.openInstitutionPicker = function (anchor, onPick, skip) {
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
      const list = (V2.meta.institutions || [])
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
