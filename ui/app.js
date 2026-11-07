'use strict';

/* ==================================================================== utils */

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

// Build DOM nodes. Strings become text nodes, so data from the network is never parsed as HTML.
function h(tag, props, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (v == null || v === false) continue;
    if (k === 'class') el.className = v;
    else if (k === 'style' && typeof v === 'object') Object.assign(el.style, v);
    else if (k.startsWith('on')) el.addEventListener(k.slice(2).toLowerCase(), v);
    else if (k === 'html') el.innerHTML = v; // trusted constants only (icons)
    else if (k in el && typeof v !== 'string') el[k] = v;
    else el.setAttribute(k, v === true ? '' : v);
  }
  for (const c of children.flat()) {
    if (c == null || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return el;
}

async function api(path, body) {
  const opts = body === undefined ? {} : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  };
  const r = await fetch(path, opts);
  let data = null;
  try { data = await r.json(); } catch { /* empty */ }
  if (!r.ok) throw new Error((data && data.error) || `Request failed (${r.status})`);
  return data;
}

let toastTimer;
function toast(msg, ms = 3500) {
  const t = $('#toast');
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove('show'), ms);
}

const fmtTime = (s) => {
  if (!isFinite(s) || s < 0) return '0:00';
  s = Math.floor(s);
  const mmss = `${String(Math.floor(s / 60) % 60)}:${String(s % 60).padStart(2, '0')}`;
  return s >= 3600 ? `${Math.floor(s / 3600)}:${mmss.padStart(5, '0')}` : mmss;
};

const ICON = {
  check: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5L20 7"/></svg>',
  lock: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>',
  play: '<svg width="52" height="52" viewBox="0 0 24 24" fill="currentColor"><path d="M7 4v16l13-8z"/></svg>',
  pause: '<svg width="52" height="52" viewBox="0 0 24 24" fill="currentColor"><path d="M6 4h4v16H6zM14 4h4v16h-4z"/></svg>',
  prev: '<svg width="40" height="40" viewBox="0 0 24 24" fill="currentColor"><path d="M6 5h2v14H6zM20 5v14L9 12z"/></svg>',
  next: '<svg width="40" height="40" viewBox="0 0 24 24" fill="currentColor"><path d="M16 5h2v14h-2zM4 5v14l11-7z"/></svg>',
  shuffle: '<svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 3h5v5M4 20L21 3M21 16v5h-5M15 15l6 6M4 4l5 5"/></svg>',
  repeat: '<svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 2l4 4-4 4"/><path d="M3 11V9a3 3 0 0 1 3-3h15M7 22l-4-4 4-4"/><path d="M21 13v2a3 3 0 0 1-3 3H3"/></svg>',
  repeatOne: '<svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 2l4 4-4 4"/><path d="M3 11V9a3 3 0 0 1 3-3h15M7 22l-4-4 4-4"/><path d="M21 13v2a3 3 0 0 1-3 3H3"/><path d="M11 10h1v4"/></svg>',
  expand: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/></svg>',
  list: '<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 6h16M4 12h16M4 18h10"/></svg>',
  search: '<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/></svg>',
  wave: '<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12h2l2-6 4 12 3-9 2 3h5"/></svg>',
};

const WEATHER_ICON = {
  clear: '<svg width="84" height="84" viewBox="0 0 24 24" fill="none" stroke-width="1.6" stroke-linecap="round"><circle cx="12" cy="12" r="4.2" stroke="#F5B544"/><path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4" stroke="#F5B544"/></svg>',
  partly: '<svg width="84" height="84" viewBox="0 0 24 24" fill="none" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="8" r="3.2" stroke="#F5B544"/><path d="M9 1.8v1.4M3.6 3.6l1 1M2 8h1.4M14.4 3.6l-1 1" stroke="#F5B544"/><path d="M8 20h9a4 4 0 0 0 .4-8 5.5 5.5 0 0 0-10.6 1.6A3.2 3.2 0 0 0 8 20z" stroke="currentColor" fill="var(--bg)"/></svg>',
  cloudy: '<svg width="84" height="84" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M7 19h10a4.5 4.5 0 0 0 .5-9A6 6 0 0 0 6 11.5 3.8 3.8 0 0 0 7 19z"/></svg>',
  fog: '<svg width="84" height="84" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><path d="M4 9h16M3 13h18M5 17h14"/></svg>',
  rain: '<svg width="84" height="84" viewBox="0 0 24 24" fill="none" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M7 15h10a4 4 0 0 0 .5-8A5.5 5.5 0 0 0 6.6 8.7 3.3 3.3 0 0 0 7 15z" stroke="currentColor"/><path d="M8 18l-1 3M12 18l-1 3M16 18l-1 3" stroke="#60A5FA"/></svg>',
  snow: '<svg width="84" height="84" viewBox="0 0 24 24" fill="none" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M7 15h10a4 4 0 0 0 .5-8A5.5 5.5 0 0 0 6.6 8.7 3.3 3.3 0 0 0 7 15z" stroke="currentColor"/><path d="M8 19h.01M12 20h.01M16 19h.01M10 22h.01M14 22h.01" stroke="#E0F2FE" stroke-width="2.4"/></svg>',
  storm: '<svg width="84" height="84" viewBox="0 0 24 24" fill="none" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M7 15h10a4 4 0 0 0 .5-8A5.5 5.5 0 0 0 6.6 8.7 3.3 3.3 0 0 0 7 15z" stroke="currentColor"/><path d="M12 15l-2 4h3l-2 4" stroke="#F5B544"/></svg>',
};

/* ================================================================== themes */

const THEMES = [
  { id: 'midnight', name: 'Midnight', bg: '#0B0E13', text: '#F2F4F7', sw: ['#8AB4FF', '#E5484D', '#8B5CF6', '#3B6CF6'] },
  { id: 'oled', name: 'OLED Black', bg: '#000000', text: '#FFFFFF', sw: ['#FFFFFF', '#C62828', '#6D3FD1', '#2456D6'] },
  { id: 'ember', name: 'Ember', bg: '#15110E', text: '#FBF3EA', sw: ['#FFB454', '#D9443B', '#B4532A', '#FF6B3D'] },
  { id: 'daylight', name: 'Daylight', bg: '#F4F1EA', text: '#1B1A17', sw: ['#2457D6', '#D93636', '#7C3AED', '#D38B12'] },
  { id: 'ocean', name: 'Ocean', bg: '#061418', text: '#EAF8FA', sw: ['#4FD1C5', '#2B8A9E', '#2E6FD8', '#60A5FA'] },
  { id: 'forest', name: 'Forest', bg: '#0C130E', text: '#EEF6EE', sw: ['#9BE07A', '#4E8A4A', '#D69A34', '#3E7A8C'] },
  { id: 'arctic', name: 'Arctic', bg: '#1E232D', text: '#ECEFF4', sw: ['#88C0D0', '#BF616A', '#8F75A8', '#5E81AC'] },
  { id: 'synthwave', name: 'Synthwave', bg: '#120B1F', text: '#FBF0FF', sw: ['#FF4FD8', '#36F9F6', '#9D4EDD', '#FF9E3D'] },
  { id: 'sakura', name: 'Sakura', bg: '#1A1216', text: '#FFF1F5', sw: ['#FF9EC4', '#C065A0', '#E3A35B', '#7A7FD6'] },
  { id: 'sunset', name: 'Sunset', bg: '#1A0F14', text: '#FFF2EC', sw: ['#FF8A5B', '#E63E5C', '#B23A7A', '#FFD166'] },
  { id: 'royal', name: 'Royal', bg: '#100C1C', text: '#F7F2FF', sw: ['#F4C95D', '#6B46C1', '#C2334D', '#3B4FC4'] },
  { id: 'solar', name: 'Solar', bg: '#002B36', text: '#FDF6E3', sw: ['#B58900', '#DC322F', '#6C71C4', '#268BD2'] },
  { id: 'terminal', name: 'Terminal', bg: '#050A05', text: '#D8FFD8', sw: ['#39FF6A', '#1E5A2A', '#E8FF5A', '#1E4A5A'] },
  { id: 'mono', name: 'Mono', bg: '#121212', text: '#F5F5F5', sw: ['#E0E0E0', '#3A3A3A', '#2E2E2E', '#FFFFFF'] },
];

const state = {
  view: 'home',
  settings: null,
  hostname: 'homebase',
  menuOpen: false,
  dialogOpen: false,
  dialogOnClose: null,
  settingsTab: 'network',
  lastFocus: {},
};

function applyAppearance() {
  const s = state.settings || {};
  document.documentElement.dataset.theme = s.theme || 'midnight';
  document.body.dataset.wallpaper = s.wallpaper || 'ambient';
  const edges = (s.display && s.display.edges) || 0;
  $('#stage').style.transform = edges ? `scale(${1 - edges * 0.02})` : '';
  viz.readColors();
}

async function saveSettings(patch) {
  state.settings = await api('/api/settings', patch);
  applyAppearance();
  return state.settings;
}

/* ============================================================== navigation */

function show(view, opts = {}) {
  const prev = state.view;
  if (prev && document.activeElement && $(`#view-${prev}`).contains(document.activeElement)) {
    state.lastFocus[prev] = document.activeElement;
  }
  closeMenu();
  state.view = view;
  $$('.view').forEach((v) => v.classList.toggle('active', v.id === `view-${view}`));
  if (view === 'settings') renderSettings(opts.tab || state.settingsTab);
  if (view === 'music') music.render();
  if (view === 'plex') plexv.render();
  if (view === 'youtube') yt.render();
  setTimeout(() => {
    const remembered = state.lastFocus[view];
    if (remembered && remembered.isConnected && !opts.tab) remembered.focus();
    else focusFirst();
  }, 60);
}

function focusFirst() {
  const list = focusables();
  if (list.length) list[0].focus();
}

function focusables() {
  let root;
  if (state.dialogOpen) root = $('#dialog');
  else if (state.menuOpen) root = $('#menu');
  else root = $(`#view-${state.view}`);
  return $$('button, a[href], input, [tabindex="0"]', root).filter((el) => {
    if (el.disabled || el.closest('[hidden]')) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  });
}

function moveFocus(dir) {
  const list = focusables();
  const cur = document.activeElement;
  if (!list.includes(cur)) { if (list[0]) list[0].focus(); return; }
  const a = cur.getBoundingClientRect();
  const acx = a.left + a.width / 2, acy = a.top + a.height / 2;
  const gap = (a1, a2, b1, b2) => Math.max(0, b1 - a2, a1 - b2);
  let best = null, bestScore = Infinity;
  for (const el of list) {
    if (el === cur) continue;
    const b = el.getBoundingClientRect();
    const bcx = b.left + b.width / 2, bcy = b.top + b.height / 2;
    let primary, secondary;
    if (dir === 'right') { if (bcx <= acx + 1) continue; primary = Math.max(0, b.left - a.right); secondary = gap(a.top, a.bottom, b.top, b.bottom); }
    else if (dir === 'left') { if (bcx >= acx - 1) continue; primary = Math.max(0, a.left - b.right); secondary = gap(a.top, a.bottom, b.top, b.bottom); }
    else if (dir === 'down') { if (bcy <= acy + 1) continue; primary = Math.max(0, b.top - a.bottom); secondary = gap(a.left, a.right, b.left, b.right); }
    else { if (bcy >= acy - 1) continue; primary = Math.max(0, a.top - b.bottom); secondary = gap(a.left, a.right, b.left, b.right); }
    const align = dir === 'left' || dir === 'right' ? Math.abs(bcy - acy) : Math.abs(bcx - acx);
    const score = primary + secondary * 3 + align * 0.15;
    if (score < bestScore) { bestScore = score; best = el; }
  }
  if (best) {
    best.focus({ preventScroll: true });
    best.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: 'smooth' });
  }
}

function back() {
  if (viz.fullOpen) return viz.closeFull();
  if (state.dialogOpen) return closeDialog();
  if (state.menuOpen) return closeMenu(true);
  if (state.view === 'music' && music.back()) return;
  if (state.view === 'plex' && plexv.back()) return;
  if (state.view === 'youtube' && yt.back()) return;
  if (state.view === 'setup') { if (setup.step > 0) setup.go(setup.step - 1); return; }
  if (state.view !== 'home') show('home');
}

function goHome() {
  if (state.view === 'setup') return;
  if (viz.fullOpen) viz.closeFull();
  if (state.dialogOpen) closeDialog();
  show('home');
}

// A held OK (or Space) repeats its press: only the first counts, so one press starts one thing
document.addEventListener('keydown', (e) => {
  if (e.repeat && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); e.stopImmediatePropagation(); }
}, true);

document.addEventListener('keydown', (e) => {
  const inInput = e.target instanceof HTMLInputElement;
  const k = e.key;
  if (k === 'BrowserHome' || k === 'GoHome' || (k === 'Home' && !inInput)) { e.preventDefault(); return goHome(); }
  if (k === 'Escape' || k === 'BrowserBack' || k === 'GoBack' || (k === 'Backspace' && !inInput)) { e.preventDefault(); return back(); }
  // (media keys arrive from the remote through the backend: see pollEvents)
  if (k === ' ' && !inInput && state.view === 'music') { e.preventDefault(); return music.toggle(); }
  if (k === 'MediaStop') return music.stop();
  const dirs = { ArrowUp: 'up', ArrowDown: 'down', ArrowLeft: 'left', ArrowRight: 'right' };
  if (dirs[k]) {
    if (inInput && (k === 'ArrowLeft' || k === 'ArrowRight')) return;
    if (viz.fullOpen) return;
    e.preventDefault();
    moveFocus(dirs[k]);
    return;
  }
  if (k === 'Enter' && inInput && e.target.dataset.enter) {
    e.preventDefault();
    const target = document.getElementById(e.target.dataset.enter);
    if (target) target.click();
  }
  if (k === 'Enter' && !inInput && e.target.getAttribute && e.target.getAttribute('tabindex') === '0') {
    e.preventDefault();
    e.target.click();
  }
}, true);

// Hide the pointer when the trackpad has been idle.
let cursorTimer;
document.addEventListener('mousemove', () => {
  document.body.classList.remove('hide-cursor');
  clearTimeout(cursorTimer);
  cursorTimer = setTimeout(() => document.body.classList.add('hide-cursor'), 3000);
});

/* ================================================================== dialog */

function openDialog({ title, body = [], actions = [], onClose }) {
  const d = $('#dialog');
  d.replaceChildren(
    h('h2', null, title),
    ...[].concat(body),
    h('div', { class: 'actions' }, actions.map((a) => h('button', {
      class: a.primary ? 'primary' : 'pill', id: a.id, onclick: a.onClick,
    }, a.label))),
  );
  state.dialogOpen = true;
  state.dialogOnClose = onClose || null;
  state.dialogReturn = document.activeElement;
  $('#dialog-backdrop').classList.add('open');
  setTimeout(() => {
    const first = $('input', d) || $('.primary', d) || $('button', d);
    if (first) first.focus();
  }, 50);
}

function closeDialog() {
  if (!state.dialogOpen) return;
  state.dialogOpen = false;
  $('#dialog-backdrop').classList.remove('open');
  const cb = state.dialogOnClose;
  state.dialogOnClose = null;
  if (cb) cb();
  if (state.dialogReturn && state.dialogReturn.isConnected) state.dialogReturn.focus();
}

function confirmDialog(title, text, label, fn) {
  openDialog({
    title, body: h('p', null, text),
    actions: [{ label: 'Cancel', onClick: closeDialog }, { label, primary: true, onClick: () => { closeDialog(); fn(); } }],
  });
}

/* ==================================================================== home */

function tickClock() {
  const now = new Date();
  const hour12 = !state.settings || state.settings.clock_resolved !== '24';
  const parts = new Intl.DateTimeFormat('en-US', { hour: 'numeric', minute: '2-digit', hour12 }).formatToParts(now);
  $('#clock-time').textContent = parts.filter((p) => p.type === 'hour' || p.type === 'minute' || p.type === 'literal')
    .map((p) => p.value).join('').trim();
  $('#clock-ampm').textContent = (parts.find((p) => p.type === 'dayPeriod') || {}).value || '';
  $('#clock-date').textContent = now.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' });
}

async function refreshWeather() {
  const box = $('#weather');
  try {
    const w = await api('/api/weather');
    if (!w.configured) {
      box.replaceChildren(h('span', { class: 'hint' }, 'Set your weather location in Settings'));
      return;
    }
    if (w.error) {
      box.replaceChildren(h('span', { class: 'hint' }, `Weather unavailable · ${w.place || ''}`));
      return;
    }
    box.replaceChildren(
      h('span', { html: WEATHER_ICON[w.icon] || WEATHER_ICON.cloudy, style: { color: 'var(--text-2)', display: 'flex' } }),
      h('div', { class: 'temp' }, `${w.temp}°`),
      h('div', { class: 'cond' },
        h('span', { class: 'c1' }, w.conditions),
        h('span', { class: 'c2' }, `H ${w.high}°  L ${w.low}° · ${w.place.split(',')[0]}`)),
    );
  } catch {
    box.replaceChildren(h('span', { class: 'hint' }, 'Weather unavailable'));
  }
}

async function refreshNetworkChip() {
  try {
    const n = await api('/api/network');
    state.network = n;
    const online = (n.wifi && n.wifi.connected) || (n.ethernet && n.ethernet.connected);
    showOffline(!online);
  } catch {
    showOffline(true);
  }
}

// The home screen shows the connection only when there is none (in red): otherwise it is just clutter
function showOffline(offline) {
  $('#chip-net-text').textContent = 'Offline';
  $('#chip-net').style.color = 'var(--hot)';
  $('#chip-net').hidden = !offline;
}

let newsData = null;
async function refreshNews() {
  const ticker = $('#ticker');
  if (!state.settings || !state.settings.ticker) { ticker.hidden = true; return; }
  try {
    newsData = await api('/api/news');
  } catch { /* keep the previous headlines */ }
  if (!newsData || !newsData.items.length) { ticker.hidden = true; return; }
  const run = $('#ticker-run');
  const item = (i) => h('span', null, i.title, h('span', { class: 't' }, ago(i.ts)));
  const items = newsData.items.slice(0, 20);
  run.replaceChildren(...items.map(item), ...items.map(item));
  ticker.hidden = false;
  requestAnimationFrame(() => { tickerMotion.half = run.scrollWidth / 2; tickerMotion.start(); });
}

// The ticker moves a whole number of pixels per tick at a modest frame rate rather than as a CSS animation, which
// redraws at the display's full 60 Hz: on a Raspberry Pi 4 every redraw of the 1080p screen costs GPU time.
const TICKER_FPS = 30, TICKER_STEP = 4;   // 120 px/s
const tickerMotion = {
  x: 0, half: 0, timer: null,
  start() {
    if (this.timer) return;
    this.timer = setInterval(() => this.step(), 1000 / TICKER_FPS);
  },
  step() {
    if (!this.half || document.hidden || state.view !== 'home' || document.body.classList.contains('busy')) return;
    this.x = (this.x + TICKER_STEP) % this.half;
    $('#ticker-run').style.transform = `translate3d(${-this.x}px, 0, 0)`;
  },
};

function ago(ts) {
  if (!ts) return '';
  const m = Math.round((Date.now() / 1000 - ts) / 60);
  if (m < 60) return `${Math.max(1, m)}m ago`;
  const hrs = Math.round(m / 60);
  return `${hrs}h ago`;
}

async function refreshCast() {
  try {
    const c = await api('/api/cast');
    $('#cast-badge').hidden = !c.ready;
  } catch { $('#cast-badge').hidden = true; }
}

function openMenu() {
  state.menuOpen = true;
  const btn = $('#menu-btn');
  const r = btn.getBoundingClientRect();
  const stage = $('#view-home').getBoundingClientRect();
  const menu = $('#menu');
  menu.style.top = 'auto';   // (the button is at the bottom right: the menu opens upwards)
  menu.style.bottom = `${stage.bottom - r.top + 16}px`;
  menu.style.right = `${stage.right - r.right}px`;
  menu.classList.add('open');
  btn.setAttribute('aria-expanded', 'true');
  setTimeout(() => $('#menu button').focus(), 30);
}

function closeMenu(refocus) {
  if (!state.menuOpen) return;
  state.menuOpen = false;
  $('#menu').classList.remove('open');
  $('#menu-btn').setAttribute('aria-expanded', 'false');
  if (refocus) $('#menu-btn').focus();
}

const ACTIONS = {
  youtube: () => show('youtube'),
  plex: () => show('plex'),
  music: () => show('music'),
  cast: () => openDialog({
    title: 'Cast to TV',
    body: [
      h('p', null, `Open the Plex app on your phone, start something, tap the cast icon and choose “${state.hostname}”. It plays here on the TV.`),
      h('p', { class: 'note' }, $('#cast-badge').hidden ? 'The cast receiver is not running right now.' : 'The cast receiver is running and ready.'),
    ],
    actions: [{ label: 'OK', primary: true, onClick: closeDialog }],
  }),
  settings: () => show('settings'),
  home: () => show('home'),
  reboot: () => confirmDialog('Restart?', 'Home Base restarts and is back in about a minute.', 'Restart',
    () => api('/api/power', { action: 'reboot' }).then(() => toast('Restarting…'))),
  poweroff: () => confirmDialog('Power off?', 'Unplug and plug the power back in to turn it on again.', 'Power off',
    () => api('/api/power', { action: 'poweroff' }).then(() => toast('Shutting down…'))),
};

document.addEventListener('click', (e) => {
  const el = e.target.closest('[data-action]');
  if (el && ACTIONS[el.dataset.action]) {
    closeMenu();
    ACTIONS[el.dataset.action]();
  }
  if (state.menuOpen && !e.target.closest('#menu') && !e.target.closest('#menu-btn')) closeMenu();
});
$('#menu-btn').addEventListener('click', () => (state.menuOpen ? closeMenu(true) : openMenu()));
$('#dialog-backdrop').addEventListener('click', (e) => { if (e.target.id === 'dialog-backdrop') closeDialog(); });

/* ================================================================ settings */

$$('#settings-nav button').forEach((b) => b.addEventListener('click', () => renderSettings(b.dataset.tab)));

function opts(list, selected, onPick, n) {
  return h('div', { class: 'options', style: { '--n': n || list.length } },
    list.map((o) => h('button', {
      class: `opt${o.id === selected ? ' selected' : ''}`, 'aria-pressed': String(o.id === selected),
      onclick: () => onPick(o.id),
    }, o.label, o.sub ? h('small', null, o.sub) : null)));
}

function switchBtn(label, on, onToggle) {
  return h('button', { class: 'switch', 'aria-label': label, 'aria-pressed': String(!!on), onclick: onToggle });
}

function card(title, ...children) {
  return h('div', { class: 'card' }, title ? h('h2', null, title) : null, ...children);
}

function row(k, v) {
  return h('div', { class: 'row' }, h('span', { class: 'k' }, k), h('span', null, v));
}

async function renderSettings(tab) {
  state.settingsTab = tab;
  $$('#settings-nav button').forEach((b) => b.classList.toggle('current', b.dataset.tab === tab));
  const panel = $('#settings-panel');
  panel.replaceChildren(h('div', { class: 'note' }, 'Loading…'));
  try {
    if (tab === 'network') await renderNetwork(panel);
    else if (tab === 'display') await renderDisplay(panel);
    else if (tab === 'appearance') renderAppearance(panel);
    else if (tab === 'system') await renderSystem(panel);
    else await renderHomeSettings(panel);
  } catch (err) {
    panel.replaceChildren(h('div', { class: 'note err' }, err.message));
  }
}

// ---------------------------------------------------------------- system monitor

async function renderSystem(panel) {
  const meter = (label) => {
    const value = h('span', { class: 'sys-value' }, '—');
    const sub = h('span', { class: 'note' }, '');
    const fill = h('i');
    return { el: h('div', { class: 'sys-meter' }, h('div', { class: 'sys-head' }, h('span', null, label), value), h('div', { class: 'sys-bar' }, fill), sub),
      set(pct, text, note, warn) {
        fill.style.width = `${Math.max(0, Math.min(100, pct || 0))}%`;
        fill.classList.toggle('warn', !!warn);
        value.textContent = text;
        sub.textContent = note || '';
      } };
  };
  const temp = meter('Temperature');
  const cpu = meter('CPU');
  const gpu = meter('GPU');
  const mem = meter('Memory');
  const gmem = meter('Video memory');
  const cores = h('div', { class: 'sys-cores' });
  const status = h('div', { class: 'note' }, '');
  const facts = h('div', { class: 'note' }, '');
  panel.replaceChildren(h('div', { class: 'cols' },
    h('div', { class: 'col' }, card('Live', temp.el, cpu.el, cores, gpu.el), card(null, status)),
    h('div', { class: 'col' }, card('Memory', mem.el, gmem.el), card(null, facts))));
  const gb = (b) => `${(b / 1073741824).toFixed(1)} GB`;
  const mb = (b) => `${Math.round(b / 1048576)} MB`;
  const tick = async () => {
    if (state.view !== 'settings' || state.settingsTab !== 'system' || !panel.isConnected) return false;
    let s;
    try { s = await api('/api/system'); } catch { return true; }
    const t = `${Math.round(s.temp)}°C`;   // (always Celsius: the chip's limits are given in it)
    temp.set(s.temp / 85 * 100, t, s.temp >= 80 ? 'Hot: the Pi slows itself down at 80–85°C' : s.temp >= 70 ? 'Warm' : 'Normal', s.temp >= 75);
    cpu.set(s.cpu.total, `${Math.round(s.cpu.total)}%`, s.cpu.mhz ? `${s.cpu.mhz} MHz${s.cpu.max_mhz ? ` of ${s.cpu.max_mhz}` : ''} · load ${s.load.map((x) => x.toFixed(2)).join(' ')}` : '', s.cpu.total > 90);
    cores.replaceChildren(...s.cpu.cores.map((c, i) => h('div', { class: 'sys-core', title: `Core ${i + 1}` }, h('i', { style: { height: `${Math.max(2, c)}%` } }), h('span', null, String(i + 1)))));
    gpu.set(s.gpu.busy ?? 0, s.gpu.busy == null ? '—' : `${Math.round(s.gpu.busy)}%`, s.gpu.mhz ? `${s.gpu.mhz} MHz` : '', (s.gpu.busy ?? 0) > 90);
    mem.set(s.mem.used / s.mem.total * 100, `${gb(s.mem.used)} of ${gb(s.mem.total)}`, s.mem.swap_total ? `Swap ${mb(s.mem.swap_used)} of ${gb(s.mem.swap_total)}` : '', s.mem.used / s.mem.total > 0.9);
    gmem.set(s.mem.gpu_total ? s.mem.gpu_used / s.mem.gpu_total * 100 : 0, s.mem.gpu_total ? `${mb(s.mem.gpu_used)} of ${mb(s.mem.gpu_total)}` : '—', 'Shared with the GPU for video and graphics');
    const now = s.throttle.now, past = s.throttle.since_boot.filter((x) => !now.includes(x));
    status.replaceChildren(...[
      h('div', { class: 'row' }, h('span', { class: 'k' }, 'Power and heat'),
        h('span', { class: now.length ? 'err' : '' }, now.length ? `Now: ${now.join(', ')}` : 'All good')),
      past.length ? h('p', { class: 'note' }, `Since start-up: ${past.join(', ')}. ${past.includes('under-voltage') ? 'Under-voltage means the power supply is too weak. ' : ''}${past.some((x) => x !== 'under-voltage') ? 'Heat limits mean it needs better cooling (a heatsink or fan).' : ''}`) : null].filter(Boolean));
    const up = s.uptime, d = Math.floor(up / 86400), hr = Math.floor(up % 86400 / 3600), mi = Math.floor(up % 3600 / 60);
    facts.textContent = `Running for ${d ? `${d} d ` : ''}${hr} h ${mi} min`;
    return true;
  };
  if (await tick()) {
    const loop = async () => { await new Promise((r) => setTimeout(r, 2000)); if (await tick()) loop(); };
    loop();
  }
}

// ---------------------------------------------------------------- network

async function renderNetwork(panel) {
  const [n, ssh] = await Promise.all([api('/api/network'), api('/api/ssh')]);
  const wifiList = h('div', { style: { display: 'flex', flexDirection: 'column', gap: '12px' } },
    h('div', { class: 'note' }, 'Looking for networks…'));
  const ipMode = { value: n.method === 'manual' ? 'manual' : 'auto' };

  const status = card('Status',
    row('Connection', n.wifi.connected ? h('span', null, h('i', { class: 'dot' }), `Wi-Fi · ${n.wifi.ssid}`)
      : n.ethernet.connected ? h('span', null, h('i', { class: 'dot' }), 'Ethernet') : 'Not connected'),
    n.wifi.connected ? row('Adapter', n.wifi.adapter === 'usb' ? 'USB Wi-Fi adapter' : 'Built-in Wi-Fi') : null,
    n.wifi.connected ? row('Signal', n.wifi.signal_word || '—') : null,
    n.wifi.backup ? row('Backup', `${n.wifi.backup.adapter === 'usb' ? 'USB Wi-Fi adapter' : 'Built-in Wi-Fi'}, connected`)
      : null,
    row('IP address', n.ip || '—'),
    row('Router', n.gateway || '—'),
    row('Name on network', `${n.hostname}.local`),
    row('Ethernet', n.ethernet.connected ? 'Connected' : 'No cable connected'),
  );

  const scanBtn = h('button', { class: 'pill', style: { height: '52px', fontSize: '22px' }, onclick: () => scan() }, 'Scan again');
  const wifiCard = card(null,
    h('div', { class: 'row' }, h('h2', null, 'Wi-Fi networks'), scanBtn),
    wifiList,
    h('button', { class: 'list-btn dashed', onclick: () => joinDialog(null) }, 'Join a hidden network…'),
  );

  async function scan() {
    wifiList.replaceChildren(h('div', { class: 'note' }, 'Looking for networks…'));
    try {
      const nets = await api('/api/wifi/scan');
      wifiList.replaceChildren(...nets.slice(0, 8).map((w) => h('button', {
        class: `list-btn${w.in_use ? ' ok' : ''}`, onclick: () => (w.in_use ? null : joinDialog(w)),
      }, h('span', null, w.ssid), h('span', { class: 'r', html: w.in_use ? `${ICON.check} Connected` : w.secure ? `${ICON.lock}` : 'Open' }))));
      if (!nets.length) wifiList.replaceChildren(h('div', { class: 'note' }, 'No networks found.'));
    } catch (err) {
      wifiList.replaceChildren(h('div', { class: 'note err' }, err.message));
    }
  }

  const fields = h('div', { class: 'fields' });
  const fAddr = h('input', { value: n.ip || '', 'aria-label': 'IP address' });
  const fMask = h('input', { value: prefixToMask(n.prefix || 24), 'aria-label': 'Subnet mask' });
  const fGw = h('input', { value: n.gateway || '', 'aria-label': 'Router' });
  const fDns = h('input', { value: (n.dns || []).join(', ') || '1.1.1.1', 'aria-label': 'DNS' });
  fields.append(
    h('label', { class: 'field' }, 'IP address', fAddr), h('label', { class: 'field' }, 'Subnet mask', fMask),
    h('label', { class: 'field' }, 'Router', fGw), h('label', { class: 'field' }, 'DNS', fDns));
  const ipNote = h('p', { class: 'note' });
  const ipBody = h('div', { style: { display: 'flex', flexDirection: 'column', gap: '18px' } });
  const ipOptsHolder = h('div');
  function drawIp() {
    ipOptsHolder.replaceChildren(opts([{ id: 'auto', label: 'Automatic' }, { id: 'manual', label: 'Manual' }], ipMode.value, (v) => { ipMode.value = v; drawIp(); }));
    ipNote.textContent = ipMode.value === 'auto'
      ? `Your router picks the address. You can always reach this box at ${n.hostname}.local.`
      : 'The connection drops for a few seconds when you save.';
    ipBody.replaceChildren(ipMode.value === 'manual' ? fields : '', ipNote);
  }
  drawIp();
  const ipCard = card('IP address', ipOptsHolder, ipBody,
    h('div', { style: { display: 'flex', justifyContent: 'flex-end' } },
      h('button', { class: 'primary', onclick: async () => {
        try {
          await api('/api/network/ip', ipMode.value === 'auto' ? { mode: 'auto' }
            : { mode: 'manual', address: fAddr.value, netmask: fMask.value, gateway: fGw.value, dns: fDns.value });
          toast('Network settings saved. Reconnecting…');
          setTimeout(refreshNetworkChip, 6000);
        } catch (err) { toast(err.message); }
      } }, 'Save network settings')));

  const sshLogin = `ssh ${ssh.user}@${n.hostname}.local`;
  const sshCmd = h('div', { class: 'mono' }, sshLogin);
  let sshOn = ssh.enabled;
  const sshSwitch = switchBtn('Remote access (SSH)', sshOn, () => {
    const apply = async (val, password) => {
      try {
        const r = await api('/api/ssh', { enabled: val, password });
        sshOn = r.enabled;
        sshSwitch.setAttribute('aria-pressed', String(sshOn));
        sshCmd.textContent = sshOn ? sshLogin : 'Off. Nobody can log in over the network.';
        return true;
      } catch (err) { toast(err.message); return false; }
    };
    if (sshOn) confirmDialog('Turn off remote access?', 'You will no longer be able to log in to this box from another computer until you turn it back on here.', 'Turn off', () => apply(false));
    else if (ssh.has_password) apply(true);
    else passwordDialog(ssh.user, async (pw) => { if (await apply(true, pw)) ssh.has_password = true; });
  });
  if (!sshOn) sshCmd.textContent = 'Off. Nobody can log in over the network.';
  const pwNote = h('span', { class: 'note' }, ssh.has_password ? 'Set' : 'Not set. Needed for maintenance and remote access.');
  const pwBtn = h('button', { class: 'pill', onclick: () => changePasswordDialog(ssh.has_password, () => {
    ssh.has_password = true;
    pwNote.textContent = 'Set';
    pwBtn.textContent = 'Change';
  }) }, ssh.has_password ? 'Change' : 'Set password');
  const sshCard = card(null,
    h('div', { class: 'row' },
      h('div', { style: { display: 'flex', flexDirection: 'column', gap: '6px' } },
        h('span', null, 'Remote access (SSH)'),
        h('span', { class: 'note' }, 'Log in from another computer on your network')),
      sshSwitch),
    sshCmd,
    h('div', { class: 'row' },
      h('div', { style: { display: 'flex', flexDirection: 'column', gap: '6px' } }, h('span', null, 'Password'), pwNote),
      pwBtn));

  const cc = state.settings.country;
  const countryCard = card(null,
    h('div', { class: 'row' },
      h('div', { style: { display: 'flex', flexDirection: 'column', gap: '6px' } },
        h('span', null, 'Wi-Fi country'),
        h('span', { class: 'note' }, cc ? countryName(cc) : 'Not set. Wi-Fi stays off until you choose.')),
      h('button', { class: 'pill', onclick: () => openDialog({
        title: 'Wi-Fi country',
        body: [h('p', null, 'Wi-Fi channels and power limits depend on the country you are in.'), ...countryPicker(async (code) => {
          state.settings = await api('/api/country', { country: code });
          closeDialog();
          toast(`Wi-Fi country set to ${countryName(code)}`);
          renderSettings('network');
        }, cc)],
        actions: [{ label: 'Cancel', onClick: closeDialog }],
      }) }, 'Change')));

  panel.replaceChildren(h('div', { class: 'cols' },
    h('div', { class: 'col' }, status, wifiCard),
    h('div', { class: 'col' }, ipCard, sshCard, countryCard)));
  scan();
}

function passwordDialog(user, onSet) {
  const pw = h('input', { class: 'text-input', type: 'password', placeholder: 'Password (at least 8 characters)' });
  const pw2 = h('input', { class: 'text-input', type: 'password', placeholder: 'Type it again', 'data-enter': 'pw-set' });
  const err = h('p', { class: 'note err' });
  openDialog({
    title: 'Set a login password',
    body: [h('p', null, `Remote access needs a password for the user “${user}”. You'll use it to log in from another computer.`), pw, pw2, err],
    actions: [
      { label: 'Cancel', onClick: closeDialog },
      { label: 'Turn on', primary: true, id: 'pw-set', onClick: () => {
        if (pw.value.length < 8) { err.textContent = 'Use at least 8 characters.'; return; }
        if (pw.value !== pw2.value) { err.textContent = 'The two passwords don’t match.'; return; }
        closeDialog();
        onSet(pw.value);
      } },
    ],
  });
}

// The box's own password (setup and Settings): new twice, and the current one when changing it
function passwordFields(hasPassword) {
  const cur = hasPassword ? h('input', { class: 'text-input', type: 'password', placeholder: 'Current password' }) : null;
  const pw = h('input', { class: 'text-input', type: 'password', placeholder: 'New password (at least 8 characters)' });
  const pw2 = h('input', { class: 'text-input', type: 'password', placeholder: 'Type it again' });
  const err = h('p', { class: 'note err' });
  const submit = async () => {
    if (pw.value.length < 8) { err.textContent = 'Use at least 8 characters.'; return false; }
    if (pw.value !== pw2.value) { err.textContent = 'The two passwords don’t match.'; return false; }
    try {
      await api('/api/password', { password: pw.value, current: cur ? cur.value : '' });
      return true;
    } catch (e) { err.textContent = e.message; return false; }
  };
  return { inputs: [cur, pw, pw2, err].filter(Boolean), submit, last: pw2 };
}

function changePasswordDialog(hasPassword, onDone) {
  const f = passwordFields(hasPassword);
  f.last.dataset.enter = 'pw-save';
  openDialog({
    title: hasPassword ? 'Change password' : 'Set a password',
    body: [h('p', null, 'This box’s password, for maintenance such as installing system updates over SSH. Watching TV never needs it.'), ...f.inputs],
    actions: [
      { label: 'Cancel', onClick: closeDialog },
      { label: 'Save', primary: true, id: 'pw-save', onClick: async () => {
        if (await f.submit()) { closeDialog(); toast('Password saved'); if (onDone) onDone(); }
      } },
    ],
  });
}

const COUNTRY_CODES = ('AD AE AF AG AI AL AM AO AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL BM BN BO BQ BR BS BT BW BY BZ '
  + 'CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV CW CX CY CZ DE DJ DK DM DO DZ EC EE EG EH ER ES ET FI FJ FK FM FO FR GA GB GD '
  + 'GE GF GG GH GI GL GM GN GP GQ GR GT GU GW GY HK HN HR HT HU ID IE IL IM IN IQ IR IS IT JE JM JO JP KE KG KH KI KM KN KP KR '
  + 'KW KY KZ LA LB LC LI LK LR LS LT LU LV LY MA MC MD ME MF MG MH MK ML MM MN MO MP MQ MR MS MT MU MV MW MX MY MZ NA NC NE NF '
  + 'NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL PM PN PR PS PT PW PY QA RE RO RS RU RW SA SB SC SD SE SG SH SI SK SL SM SN '
  + 'SO SR SS ST SV SX SY SZ TC TD TG TH TJ TK TL TM TN TO TR TT TV TW TZ UA UG US UY UZ VA VC VE VG VI VN VU WF WS YE YT ZA ZM ZW').split(' ');
const regionNames = new Intl.DisplayNames(['en'], { type: 'region' });
const countryName = (cc) => { try { return regionNames.of(cc) || cc; } catch { return cc; } };

// A filterable country list. Calls onPick(code) when one is chosen.
function countryPicker(onPick, current) {
  const guess = (navigator.language.split('-')[1] || '').toUpperCase();
  const all = COUNTRY_CODES.map((cc) => ({ cc, name: countryName(cc) })).sort((a, b) => a.name.localeCompare(b.name));
  const list = h('div', { class: 'list' });
  const q = h('input', { class: 'text-input', placeholder: 'Type to search countries' });
  const draw = () => {
    const term = q.value.trim().toLowerCase();
    let items = term ? all.filter((c) => c.name.toLowerCase().includes(term) || c.cc.toLowerCase() === term) : [];
    if (!term) items = [current, guess, 'US', 'GB', 'CA', 'AU', 'DE', 'FR'].filter((cc, i, arr) => cc && COUNTRY_CODES.includes(cc) && arr.indexOf(cc) === i).map((cc) => ({ cc, name: countryName(cc) }));
    list.replaceChildren(...items.slice(0, 8).map((c) => h('button', {
      class: `list-btn${c.cc === current ? ' ok' : ''}`, onclick: () => onPick(c.cc),
    }, h('span', null, c.name), h('span', { class: 'r', html: c.cc === current ? ICON.check : '' }))));
    if (!items.length) list.replaceChildren(h('div', { class: 'note' }, 'No matching country.'));
  };
  q.addEventListener('input', draw);
  draw();
  return [q, list];
}

// City or postcode search that calls onPicked(place) after saving it.
function locationSearch(onPicked) {
  const results = h('div', { style: { display: 'flex', flexDirection: 'column', gap: '10px' } });
  const id = `geo-${Math.random().toString(36).slice(2, 8)}`;
  const q = h('input', { class: 'text-input', placeholder: 'City or ZIP / postcode', 'data-enter': id, style: { flexGrow: 1 } });
  const search = async () => {
    results.replaceChildren(h('div', { class: 'note' }, 'Searching…'));
    try {
      const found = await api(`/api/geocode?q=${encodeURIComponent(q.value)}`);
      results.replaceChildren(...(found.length ? found.slice(0, 6).map((p) => h('button', {
        class: 'list-btn', onclick: async () => {
          state.settings = await api('/api/weather/location', p);
          refreshWeather();
          onPicked(p);
        },
      }, h('span', null, p.name), h('span', { class: 'r' }, 'Use this'))) : [h('div', { class: 'note' }, 'No matching places. Try a nearby city or a different spelling.')]));
    } catch (err) { results.replaceChildren(h('div', { class: 'note err' }, err.message)); }
  };
  return [h('div', { style: { display: 'flex', gap: '12px' } }, q, h('button', { class: 'pill', id, onclick: search }, 'Search')), results];
}

function prefixToMask(p) {
  const m = p === 0 ? 0 : (0xffffffff << (32 - p)) >>> 0;
  return [24, 16, 8, 0].map((s) => (m >>> s) & 255).join('.');
}

function joinDialog(net, onJoined) {
  const ssid = h('input', { class: 'text-input', placeholder: 'Network name', value: net ? net.ssid : '' });
  const pw = h('input', { class: 'text-input', type: 'password', placeholder: 'Password', 'data-enter': 'join-btn' });
  const err = h('p', { class: 'note err' });
  openDialog({
    title: net ? `Join ${net.ssid}` : 'Join a hidden network',
    body: [net ? null : ssid, (!net || net.secure) ? pw : null, err],
    actions: [
      { label: 'Cancel', onClick: closeDialog },
      { label: 'Join', primary: true, id: 'join-btn', onClick: async () => {
        err.textContent = 'Connecting…';
        try {
          await api('/api/wifi/connect', { ssid: ssid.value, password: pw.value, hidden: !net });
          closeDialog();
          toast(`Connected to ${ssid.value}`);
          refreshNetworkChip();
          if (onJoined) onJoined(); else renderSettings('network');
        } catch (e) { err.textContent = e.message; }
      } },
    ],
  });
}

// ---------------------------------------------------------------- display

const SCALES = [{ id: 1, label: '100%', sub: 'Smallest' }, { id: 1.5, label: '150%' }, { id: 2, label: '200%', sub: 'Standard at 4K' }, { id: 2.5, label: '250%', sub: 'Largest' }];
const RES_ORDER = ['3840x2160', '2560x1440', '1920x1080', '1280x720'];
const RES_LABEL = { '3840x2160': '4K', '2560x1440': '1440p', '1920x1080': '1080p', '1280x720': '720p' };

async function renderDisplay(panel) {
  const d = await api('/api/display');
  if (!d.connected) {
    panel.replaceChildren(card('Display', h('p', { class: 'note err' }, d.error || 'No TV detected on the HDMI port.')));
    return;
  }
  const cur = d.current || { width: 1920, height: 1080, refresh: 60 };
  const sel = { res: `${cur.width}x${cur.height}`, refresh: Math.round(cur.refresh), scale: d.scale || 1 };
  const resolutions = RES_ORDER.filter((r) => d.modes.some((m) => `${m.width}x${m.height}` === r));
  const resBox = h('div'), rateBox = h('div'), scaleBox = h('div');

  function rates() {
    const [w, hgt] = sel.res.split('x').map(Number);
    return [...new Set(d.modes.filter((m) => m.width === w && m.height === hgt).map((m) => Math.round(m.refresh)))].sort((a, b) => a - b);
  }
  function draw() {
    resBox.replaceChildren(opts(resolutions.map((r) => ({ id: r, label: r.replace('x', '×'), sub: RES_LABEL[r] })), sel.res, (v) => {
      sel.res = v;
      const rs = rates();
      if (!rs.includes(sel.refresh)) sel.refresh = rs.includes(30) ? 30 : rs[rs.length - 1];
      draw();
    }, Math.min(3, resolutions.length) || 1));
    const rs = rates();
    rateBox.replaceChildren(opts(rs.map((r) => ({
      id: r, label: `${r} Hz`, sub: r === 24 ? 'Matches films' : r === 60 && sel.res === '3840x2160' ? 'Needs high-speed cable' : null,
    })), sel.refresh, (v) => { sel.refresh = v; draw(); }, Math.min(4, rs.length) || 1));
    scaleBox.replaceChildren(opts(SCALES, sel.scale, (v) => { sel.scale = v; draw(); }, 4));
  }
  draw();

  let edges = (state.settings.display && state.settings.display.edges) || 0;
  const bar = h('i', { style: { width: `${100 - edges * 10}%` } });
  const edgesLbl = h('span', { style: { width: '110px', textAlign: 'right' } });
  const setEdges = async (v) => {
    edges = Math.max(0, Math.min(5, v));
    bar.style.width = `${100 - edges * 10}%`;
    edgesLbl.textContent = edges ? `−${edges * 2}%` : 'Full';
    await saveSettings({ edges });
  };
  edgesLbl.textContent = edges ? `−${edges * 2}%` : 'Full';

  panel.replaceChildren(h('div', { class: 'cols' },
    h('div', { class: 'col' },
      card('Connected TV',
        h('div', { style: { fontSize: '34px', fontWeight: 500 } }, d.tv || 'Unknown TV'),
        h('div', { class: 'note' }, `Output ${d.output} · now ${cur.width}×${cur.height} at ${Math.round(cur.refresh)} Hz`)),
      card('Resolution', resBox),
      card('Refresh rate', rateBox)),
    h('div', { class: 'col' },
      card('Menu size', scaleBox),
      card('Screen edges',
        h('p', { class: 'note' }, 'If the edges of the picture are cut off, shrink the picture until everything fits.'),
        h('div', { class: 'stepper' },
          h('button', { class: 'round', 'aria-label': 'Shrink picture', onclick: () => setEdges(edges + 1) }, '−'),
          h('div', { class: 'bar' }, bar),
          h('button', { class: 'round', 'aria-label': 'Enlarge picture', onclick: () => setEdges(edges - 1) }, '+'),
          edgesLbl)),
      card(null,
        h('p', { class: 'note', style: { color: 'var(--text-2)' } }, 'New modes are tried first. If the screen goes blank, it switches back by itself after 15 seconds unless you press Keep.'),
        h('div', { style: { display: 'flex', justifyContent: 'flex-end' } },
          h('button', { class: 'primary', onclick: () => tryMode(sel) }, 'Try this mode'))))));
}

async function tryMode(sel) {
  const [width, height] = sel.res.split('x').map(Number);
  try {
    await api('/api/display/try', { width, height, refresh: sel.refresh, scale: sel.scale });
  } catch (err) { return toast(err.message); }
  let left = 15;
  const count = h('p', null, `Switching back in ${left} seconds.`);
  const timer = setInterval(() => {
    left -= 1;
    count.textContent = `Switching back in ${left} seconds.`;
    if (left <= 0) { clearInterval(timer); closeDialog(); toast('Switched back to the previous mode'); renderSettings('display'); }
  }, 1000);
  openDialog({
    title: 'Keep this mode?',
    body: count,
    onClose: () => clearInterval(timer),
    actions: [
      { label: 'Switch back', onClick: async () => { clearInterval(timer); closeDialog(); await api('/api/display/revert', {}); renderSettings('display'); } },
      { label: 'Keep', primary: true, onClick: async () => { clearInterval(timer); closeDialog(); await api('/api/display/keep', {}); toast('Display mode saved'); renderSettings('display'); } },
    ],
  });
}

// ---------------------------------------------------------------- appearance

function renderAppearance(panel) {
  const s = state.settings;
  const grid = h('div', { class: 'theme-grid' }, THEMES.map((t) => h('button', {
    class: `theme-card${t.id === s.theme ? ' selected' : ''}`, 'aria-pressed': String(t.id === s.theme),
    style: { '--p-bg': t.bg, '--p-text': t.text },
    onclick: async () => { await saveSettings({ theme: t.id }); renderAppearance(panel); focusTheme(t.id); },
  }, h('span', { class: 'sw' }, t.sw.map((c) => h('i', { style: { background: c } }))), h('span', { class: 'nm' }, t.name))));
  grid.querySelectorAll('.theme-card').forEach((el, i) => { el.dataset.theme = THEMES[i].id; });

  const wp = opts([
    { id: 'none', label: 'Plain', sub: 'Solid background' },
    { id: 'ambient', label: 'Ambient', sub: 'Slow moving color' },
    { id: 'art', label: 'Album art', sub: 'From what is playing' },
  ], s.wallpaper, async (v) => { await saveSettings({ wallpaper: v }); renderAppearance(panel); }, 3);

  panel.replaceChildren(h('div', { class: 'col' },
    card('Theme', grid),
    card('Wallpaper', wp)));
}

function focusTheme(id) {
  const el = $(`.theme-card[data-theme="${id}"]`);
  if (el) el.focus();
}

// ---------------------------------------------------------------- home screen

async function renderHomeSettings(panel) {
  const s = state.settings;
  const [plex] = await Promise.all([api('/api/plex/status').catch(() => ({ linked: false }))]);

  const [searchRow, results] = locationSearch((p) => { toast(`Location set to ${p.name}`); renderSettings('home'); });

  const clock = opts([{ id: 'auto', label: 'Automatic' }, { id: '12', label: '12-hour', sub: '8:42 PM' }, { id: '24', label: '24-hour', sub: '20:42' }], s.clock,
    async (v) => { await saveSettings({ clock: v }); tickClock(); renderSettings('home'); }, 3);

  const units = opts([{ id: 'auto', label: 'Automatic' }, { id: 'f', label: '°F' }, { id: 'c', label: '°C' }], s.units,
    async (v) => { await saveSettings({ units: v }); refreshWeather(); renderSettings('home'); }, 3);

  const tickerSwitch = switchBtn('News ticker', s.ticker, async () => {
    await saveSettings({ ticker: !state.settings.ticker });
    tickerSwitch.setAttribute('aria-pressed', String(state.settings.ticker));
    refreshNews();
  });

  const plexCard = card('Plex',
    row('Account', plex.linked ? 'Linked' : 'Not linked'),
    plex.linked ? row('Server', plex.server ? `${plex.server}${plex.reachable ? '' : ' (not reachable)'}` : 'None found') : null,
    h('div', { style: { display: 'flex', justifyContent: 'flex-end', gap: '14px' } },
      plex.linked ? h('button', { class: 'pill', onclick: () => chooseServer() }, 'Change server') : null,
      plex.linked
        ? h('button', { class: 'pill', onclick: () => confirmDialog('Unlink Plex?', 'Music stops working until you link again.', 'Unlink', async () => { await api('/api/plex/unlink', {}); music.status = null; music.sections = null; renderSettings('home'); }) }, 'Unlink')
        : h('button', { class: 'primary', onclick: () => music.link() }, 'Link Plex account')));

  async function chooseServer() {
    const list = h('div', { style: { display: 'flex', flexDirection: 'column', gap: '10px' } }, h('div', { class: 'note' }, 'Finding your servers…'));
    openDialog({ title: 'Choose a Plex server', body: list, actions: [{ label: 'Cancel', onClick: closeDialog }] });
    try {
      const servers = await api('/api/plex/servers');
      list.replaceChildren(...(servers.length ? servers.map((sv) => h('button', {
        class: `list-btn${sv.current ? ' ok' : ''}`, onclick: async () => {
          list.replaceChildren(h('div', { class: 'note' }, `Connecting to ${sv.name}…`));
          try {
            await api('/api/plex/server', { id: sv.id });
            closeDialog();
            music.status = null; music.sections = null;
            toast(`Using ${sv.name}`);
            renderSettings('home');
          } catch (err) { list.replaceChildren(h('div', { class: 'note err' }, err.message)); }
        },
      }, h('span', null, sv.name), h('span', { class: 'r', html: sv.current ? `${ICON.check} In use` : sv.owned ? 'Yours' : 'Shared with you' }))) : [h('div', { class: 'note' }, 'No servers on this Plex account.')]));
    } catch (err) { list.replaceChildren(h('div', { class: 'note err' }, err.message)); }
  }

  panel.replaceChildren(h('div', { class: 'cols' },
    h('div', { class: 'col' },
      card('Location',
        row('Current', s.weather.name || 'Not set'),
        searchRow,
        results,
        h('p', { class: 'note' }, 'Used for the weather and the clock’s time zone. Set here only: nothing is looked up from your internet connection.')),
      card('Temperature', units,
        s.units === 'auto' ? h('p', { class: 'note' }, 'Follows your location: °F in the US, °C in most other countries.') : null),
      card('Clock', clock)),
    h('div', { class: 'col' },
      card(null,
        h('div', { class: 'row' },
          h('div', { style: { display: 'flex', flexDirection: 'column', gap: '6px' } },
            h('span', null, 'News ticker'),
            h('span', { class: 'note' }, 'Scrolling headlines along the bottom of the home screen')),
          tickerSwitch),
        row('Source', 'AP News only'),
        row('Last updated', newsData && newsData.updated ? new Date(newsData.updated * 1000).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' }) : '—')),
      plexCard)));
}

/* =============================================================== visualizer */

const viz = {
  mode: 'spectrum',
  fullOpen: false,
  analyser: null,
  freq: null,
  time: null,
  peaks: new Float32Array(64),
  colors: { accent: '#8AB4FF', hot: '#A78BFA', base: '#1E2530' },

  readColors() {
    const cs = getComputedStyle(document.documentElement);
    this.colors = {
      accent: cs.getPropertyValue('--accent').trim() || '#8AB4FF',
      hot: cs.getPropertyValue('--hot').trim() || '#A78BFA',
      base: cs.getPropertyValue('--surface-3').trim() || '#262E3A',
    };
  },

  attach(analyser) {
    this.analyser = analyser;
    this.freq = new Uint8Array(analyser.frequencyBinCount);
    this.time = new Uint8Array(analyser.fftSize);
  },

  openFull() {
    this.fullOpen = true;
    $('#viz-full').classList.add('open');
    music.updateCaption();
  },

  closeFull() {
    this.fullOpen = false;
    $('#viz-full').classList.remove('open');
  },

  frame() {
    requestAnimationFrame(() => this.frame());
    if (document.body.classList.contains('busy')) return;
    const canvases = [];
    if (this.fullOpen) canvases.push($('#viz-full canvas'));
    const inline = $('#viz-canvas');
    if (inline && state.view === 'music' && inline.isConnected) canvases.push(inline);
    if (!canvases.length) return;
    const playing = music.isPlaying();
    if (this.analyser && playing) {
      this.analyser.getByteFrequencyData(this.freq);
      this.analyser.getByteTimeDomainData(this.time);
    }
    for (const c of canvases) this.draw(c, playing);
  },

  draw(canvas, playing) {
    const dpr = 1;
    const w = Math.floor(canvas.clientWidth * dpr), hgt = Math.floor(canvas.clientHeight * dpr);
    if (!w || !hgt) return;
    if (canvas.width !== w || canvas.height !== hgt) { canvas.width = w; canvas.height = hgt; }
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, w, hgt);
    if (this.mode === 'wave') return this.drawWave(ctx, w, hgt, playing);
    this.drawBars(ctx, w, hgt, playing, this.mode === 'mirror');
  },

  levels(playing) {
    const n = this.peaks.length;
    const out = new Float32Array(n);
    if (!this.analyser || !playing) {
      for (let i = 0; i < n; i++) { this.peaks[i] *= 0.9; out[i] = Math.max(0.03, this.peaks[i]); }
      return out;
    }
    const nyquist = this.analyser.context.sampleRate / 2;
    const bins = this.freq.length;
    const fLo = 40, fHi = 16000;
    for (let i = 0; i < n; i++) {
      const f1 = fLo * Math.pow(fHi / fLo, i / n), f2 = fLo * Math.pow(fHi / fLo, (i + 1) / n);
      const b1 = Math.floor((f1 / nyquist) * bins), b2 = Math.max(b1 + 1, Math.floor((f2 / nyquist) * bins));
      let m = 0;
      for (let b = b1; b < b2 && b < bins; b++) m = Math.max(m, this.freq[b]);
      const v = Math.pow(m / 255, 1.4);
      this.peaks[i] = Math.max(v, this.peaks[i] * 0.9);
      out[i] = Math.max(0.03, this.peaks[i]);
    }
    return out;
  },

  drawBars(ctx, w, hgt, playing, mirror) {
    const lv = this.levels(playing);
    const n = lv.length, gapPx = Math.max(4, w / n * 0.18), bw = (w - gapPx * (n - 1)) / n;
    for (let i = 0; i < n; i++) {
      const v = lv[i];
      const bh = Math.max(6, v * (hgt - 24));
      const x = i * (bw + gapPx);
      const y = mirror ? (hgt - bh) / 2 : hgt - bh;
      ctx.fillStyle = v > 0.78 ? this.colors.hot : this.colors.accent;
      ctx.globalAlpha = 0.35 + 0.65 * Math.min(1, v * 1.4);
      roundRect(ctx, x, y, bw, bh, Math.min(bw / 2, 8));
      ctx.fill();
    }
    ctx.globalAlpha = 1;
  },

  drawWave(ctx, w, hgt, playing) {
    const mid = hgt / 2;
    const draw = (color, width, amp, alpha) => {
      ctx.beginPath();
      ctx.lineWidth = width;
      ctx.strokeStyle = color;
      ctx.globalAlpha = alpha;
      const n = this.time ? this.time.length : 0;
      const steps = 400;
      for (let s = 0; s <= steps; s++) {
        const x = (s / steps) * w;
        let v = 0;
        if (this.analyser && playing && n) v = (this.time[Math.floor((s / steps) * (n - 1))] - 128) / 128;
        const y = mid + v * amp;
        if (s === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }
      ctx.stroke();
    };
    draw(this.colors.hot, 10, hgt * 0.42, 0.25);
    draw(this.colors.accent, 4, hgt * 0.42, 1);
    ctx.globalAlpha = 1;
  },
};

function roundRect(ctx, x, y, w, hgt, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + hgt, r);
  ctx.arcTo(x + w, y + hgt, x, y + hgt, r);
  ctx.arcTo(x, y + hgt, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

/* ==================================================================== music */

const audio = $('#player');

const music = {
  status: null,
  mode: 'library',
  stack: [],
  tab: 'recent',
  filters: {},   // the search text typed into each category (Albums, Artists...)
  sections: null,
  queue: [],
  index: -1,
  shuffle: false,
  repeat: 'off',
  ctx: null,
  linkPoll: null,

  async plex(path) {
    const r = await fetch(`/plex${path}`, { headers: { Accept: 'application/json' } });
    if (!r.ok) {
      let msg = `Plex error ${r.status}`;
      try { msg = (await r.json()).error || msg; } catch { /* not json */ }
      throw new Error(msg);
    }
    return (await r.json()).MediaContainer || {};
  },

  thumb(path, size = 400) {
    if (!path) return '';
    return `/plex/photo/:/transcode?width=${size}&height=${size}&minSize=1&upscale=1&url=${encodeURIComponent(path)}`;
  },

  isPlaying() { return !audio.paused && !audio.ended && this.index >= 0; },

  async render() {
    const body = $('#music-body');
    const modeBtn = $('#music-mode-btn');
    if (!this.status) {
      body.replaceChildren(h('div', { class: 'empty' }, 'Connecting to Plex…'));
      try { this.status = await api('/api/plex/status'); } catch (err) { this.status = { linked: false, error: err.message }; }
    }
    if (!this.status.linked) {
      modeBtn.hidden = true;
      $('#music-server').hidden = true;
      body.replaceChildren(h('div', { class: 'card', style: { maxWidth: '1000px' } },
        h('h2', null, 'Link your Plex account'),
        h('p', { style: { fontSize: '30px', lineHeight: 1.45 } }, 'Music comes from your Plex server. Link this box to your Plex account once and your library shows up here.'),
        h('div', null, h('button', { class: 'primary', onclick: () => this.link() }, 'Link Plex account'))));
      return;
    }
    $('#music-server').hidden = !this.status.server;
    $('#music-server-name').textContent = this.status.server || '';
    modeBtn.hidden = false;
    modeBtn.replaceChildren(h('span', { html: this.mode === 'library' ? ICON.wave : ICON.list }), this.mode === 'library' ? 'Now playing' : 'Library');
    modeBtn.onclick = () => { this.mode = this.mode === 'library' ? 'now' : 'library'; this.render(); setTimeout(focusFirstContent, 50); };
    if (this.mode === 'now') this.renderNow(body);
    else await this.renderLibrary(body);
  },

  link(onLinked) {
    const code = h('div', { class: 'big-code' }, '····');
    const msg = h('p', null, 'Getting a code…');
    openDialog({
      title: 'Link Plex',
      body: [msg, code],
      onClose: () => clearInterval(this.linkPoll),
      actions: [{ label: 'Cancel', onClick: closeDialog }],
    });
    api('/api/plex/link', {}).then((pin) => {
      code.textContent = pin.code;
      msg.textContent = 'On your phone or computer, go to plex.tv/link, sign in, and enter this code:';
      const started = Date.now();
      clearInterval(this.linkPoll);
      this.linkPoll = setInterval(async () => {
        if (Date.now() - started > 10 * 60 * 1000) { clearInterval(this.linkPoll); msg.textContent = 'The code expired. Close this and try again.'; return; }
        try {
          const r = await api(`/api/plex/link/${pin.id}`);
          if (r.linked) {
            clearInterval(this.linkPoll);
            closeDialog();
            toast(r.server ? `Linked to ${r.server}` : 'Linked, but no Plex server answered on your network');
            this.status = null;
            this.sections = null;
            if (onLinked) onLinked();
            else if (state.view === 'music') this.render();
            else if (state.view === 'settings') renderSettings('home');
          }
        } catch { /* keep polling */ }
      }, 2000);
    }).catch((err) => { msg.textContent = err.message; });
  },

  async musicSections() {
    if (!this.sections) {
      const mc = await this.plex('/library/sections');
      this.sections = (mc.Directory || []).filter((d) => d.type === 'artist');
    }
    return this.sections;
  },

  back() {
    if (this.mode === 'now') { this.mode = 'library'; this.render(); return true; }
    if (this.stack.length) { this.stack.pop(); this.render(); return true; }
    return false;
  },

  async renderLibrary(body) {
    const tabs = [['search', 'Search'], ['recent', 'Recently added'], ['albums', 'Albums'], ['artists', 'Artists'], ['playlists', 'Playlists']];
    const top = this.stack[this.stack.length - 1];
    const bar = h('div', { class: 'lib-tabs' },
      top ? h('button', { class: 'pill', onclick: () => this.back() }, h('span', { html: '<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg>' }), 'Back') : null,
      top ? h('span', { class: 'crumb' }, top.title)
        : tabs.map(([id, label]) => h('button', {
          class: `pill${this.tab === id ? ' selected' : ''}`,
          onclick: () => { this.tab = id; this.render(); },
        }, label)));
    const content = h('div', { class: 'grid' }, h('div', { class: 'empty' }, 'Loading…'));
    body.replaceChildren(bar, content);
    try {
      const sections = await this.musicSections();
      if (!sections.length) { content.replaceChildren(h('div', { class: 'empty' }, 'No music library found on this Plex server.')); return; }
      const key = sections[0].key;
      if (!top && this.tab === 'search') return this.renderSearch(body, bar, key);
      if (top && top.kind === 'artist') return this.fillGrid(content, (await this.plex(`/library/metadata/${top.key}/children`)).Metadata, 'album');
      if (top && (top.kind === 'album' || top.kind === 'playlist')) {
        const path = top.kind === 'album' ? `/library/metadata/${top.key}/children` : `/playlists/${top.key}/items`;
        return this.fillTracks(body, content, (await this.plex(path)).Metadata || [], top);
      }
      const lists = {
        recent: [`/library/sections/${key}/all?type=9&sort=addedAt:desc&X-Plex-Container-Start=0&X-Plex-Container-Size=60`, 'album'],
        albums: [`/library/sections/${key}/all?type=9&sort=titleSort&X-Plex-Container-Start=0&X-Plex-Container-Size=2000`, 'album'],
        artists: [`/library/sections/${key}/all?type=8&sort=titleSort&X-Plex-Container-Start=0&X-Plex-Container-Size=2000`, 'artist'],
        playlists: ['/playlists?playlistType=audio', 'playlist'],
      };
      const [path, kind] = lists[this.tab] || lists.recent;
      const items = (await this.plex(path)).Metadata || [];
      this.fillGrid(content, items, kind);
      if (items.length) this.addCategorySearch(bar, content, items);
    } catch (err) {
      content.replaceChildren(h('div', { class: 'empty' }, err.message));
    }
  },

  // Search within the open category (Search artists, Search albums...): a button at the end of the tabs opens a box
  // that narrows the list already on screen as you type.
  addCategorySearch(bar, grid, items) {
    const tab = this.tab;
    const label = { recent: 'Search recently added', albums: 'Search albums', artists: 'Search artists', playlists: 'Search playlists' }[tab];
    const cards = [...grid.querySelectorAll('.card-item')];
    // (matched at the start of a word: "ta" finds Tame Impala and Talking Heads, not Massive Attack)
    const text = items.map((it) => ` ${it.title || ''} ${it.parentTitle || ''}`.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, ' '));
    const none = h('div', { class: 'empty', hidden: true });
    grid.after(none);
    let box = null;
    const apply = () => {
      const want = (this.filters[tab] || '').toLowerCase().replace(/[^\p{L}\p{N}]+/gu, ' ').trim();
      let shown = 0;
      cards.forEach((c, i) => { const ok = !want || text[i].includes(` ${want}`); c.hidden = !ok; if (ok) shown++; });
      none.hidden = shown > 0;
      none.textContent = `Nothing matches “${this.filters[tab] || ''}”.`;
    };
    const open = () => {
      if (!box) {
        box = h('input', { class: 'text-input category-search', placeholder: label, value: this.filters[tab] || '' });
        box.addEventListener('input', () => { this.filters[tab] = box.value; apply(); });
        box.addEventListener('keydown', (e) => {   // (Enter goes to the first match)
          if (e.key !== 'Enter') return;
          e.preventDefault();
          e.stopPropagation();   // (the press only moves to the first match; it does not also open it)
          const first = cards.find((c) => !c.hidden);
          if (first) first.focus();
        });
        bar.after(box);
      }
      box.focus();
    };
    bar.append(h('button', { class: 'pill category-search-btn', onclick: open }, h('span', { html: ICON.search }), label));
    if (this.filters[tab]) { open(); apply(); grid.querySelector('.card-item:not([hidden])')?.focus(); }
  },

  // Search, as you type (after a pause): artists, albums and songs in the music library
  renderSearch(body, bar, sectionKey) {
    const q = h('input', { class: 'text-input', placeholder: 'Search artists, albums and songs', value: this.query || '', style: { flexGrow: 1 } });
    const results = h('div', { class: 'music-results' });
    let timer = null, seq = 0;
    const group = (title, el) => h('div', { class: 'music-group' }, h('h2', null, title), el);
    const run = async () => {
      const query = q.value.trim();
      this.query = query;
      if (query.length < 2) { results.replaceChildren(); return; }
      const mine = ++seq;
      results.replaceChildren(h('div', { class: 'grid' }, ...skeletonCards(7)));
      try {
        const mc = await this.plex(`/hubs/search?query=${encodeURIComponent(query)}&sectionId=${sectionKey}&limit=30`);
        if (mine !== seq) return;   // (a newer search has started)
        const found = { artist: [], album: [], track: [] };
        for (const hub of mc.Hub || []) if (found[hub.type]) found[hub.type].push(...(hub.Metadata || []));
        const parts = [];
        if (found.artist.length) { const g = h('div', { class: 'grid' }); this.fillGrid(g, found.artist, 'artist'); parts.push(group('Artists', g)); }
        if (found.album.length) { const g = h('div', { class: 'grid' }); this.fillGrid(g, found.album, 'album'); parts.push(group('Albums', g)); }
        if (found.track.length) {
          const songs = found.track;
          parts.push(group('Songs', h('div', { class: 'tracks' }, songs.map((t, i) => h('button', {
            class: `track${this.current() && this.current().ratingKey === t.ratingKey ? ' playing' : ''}`,
            onclick: () => this.playQueue(songs, i),   // (then on through the other songs found)
          }, h('span', { class: 'n' }, i + 1),
          h('span', null, t.title, h('span', { class: 's' }, `${t.grandparentTitle || ''} · ${t.parentTitle || ''}`)),
          h('span', { class: 'd' }, fmtTime((t.duration || 0) / 1000)))))));
        }
        results.replaceChildren(...(parts.length ? parts : [h('div', { class: 'empty' }, `Nothing found for “${query}”.`)]));
      } catch (err) { if (mine === seq) results.replaceChildren(h('div', { class: 'empty' }, err.message)); }
    };
    q.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(run, 450); });
    q.addEventListener('keydown', (e) => { if (e.key === 'Enter') { clearTimeout(timer); run(); } });
    body.replaceChildren(bar, h('div', { style: { display: 'flex', gap: '16px', marginBottom: '24px' } }, q), results);
    if (this.query) run();
    setTimeout(() => q.focus(), 60);
  },

  fillGrid(content, items, kind) {
    items = items || [];
    if (!items.length) { content.replaceChildren(h('div', { class: 'empty' }, 'Nothing here yet.')); return; }
    content.replaceChildren(...items.map((it) => {
      const img = h('div', { class: 'img' });
      const src = this.thumb(it.thumb || it.composite || it.parentThumb, 360);
      if (src) img.style.backgroundImage = `url("${src}")`;
      const sub = kind === 'album' ? (it.parentTitle || '') : kind === 'playlist' ? `${it.leafCount || 0} tracks` : '';
      return h('button', {
        class: `card-item${kind === 'artist' ? ' round-img' : ''}`,
        onclick: () => { this.stack.push({ kind, key: it.ratingKey, title: it.title, thumb: it.thumb || it.composite }); this.render(); setTimeout(focusFirstContent, 80); },
      }, img, h('div', { class: 't1' }, it.title), sub ? h('div', { class: 't2' }, sub) : null);
    }));
  },

  fillTracks(body, content, tracks, top) {
    const list = h('div', { class: 'tracks' });
    const header = h('div', { style: { display: 'flex', gap: '16px', marginBottom: '18px' } },
      h('button', { class: 'primary', onclick: () => this.playQueue(tracks, 0) }, 'Play'),
      h('button', { class: 'pill', style: { height: '80px' }, onclick: () => { this.shuffle = true; this.playQueue(tracks, Math.floor(Math.random() * tracks.length)); } },
        h('span', { html: ICON.shuffle }), 'Shuffle'));
    list.append(...tracks.map((t, i) => h('button', {
      class: `track${this.current() && this.current().ratingKey === t.ratingKey ? ' playing' : ''}`,
      onclick: () => this.playQueue(tracks, i),
    }, h('span', { class: 'n' }, t.index || i + 1),
    h('span', null, t.title, top.kind === 'playlist' ? h('span', { class: 's' }, `${t.grandparentTitle || ''} · ${t.parentTitle || ''}`) : null),
    h('span', { class: 'd' }, fmtTime((t.duration || 0) / 1000)))));
    content.replaceWith(h('div', { style: { display: 'flex', flexDirection: 'column', minHeight: 0, flexGrow: 1 } }, header, list));
  },

  current() { return this.queue[this.index]; },

  ensureGraph() {
    if (this.ctx) { if (this.ctx.state === 'suspended') this.ctx.resume(); return; }
    try {
      this.ctx = new AudioContext();
      const src = this.ctx.createMediaElementSource(audio);
      const an = this.ctx.createAnalyser();
      an.fftSize = 2048;
      an.smoothingTimeConstant = 0.78;
      src.connect(an);
      an.connect(this.ctx.destination);
      viz.attach(an);
    } catch (err) { console.warn('visualizer unavailable', err); }
  },

  srcFor(t) {
    const media = (t.Media || [])[0] || {};
    const part = (media.Part || [])[0] || {};
    const codec = (media.audioCodec || '').toLowerCase();
    const types = { flac: 'audio/flac', mp3: 'audio/mpeg', aac: 'audio/mp4; codecs="mp4a.40.2"', opus: 'audio/ogg; codecs="opus"', vorbis: 'audio/ogg; codecs="vorbis"', pcm: 'audio/wav' };
    if (part.key && types[codec] && audio.canPlayType(types[codec])) return `/plex${part.key}`;
    const q = new URLSearchParams({
      path: `/library/metadata/${t.ratingKey}`, protocol: 'http', mediaIndex: '0', partIndex: '0',
      directPlay: '0', directStream: '0', musicBitrate: '320', session: `hb-${Date.now()}`,
    });
    return `/plex/music/:/transcode/universal/start.mp3?${q}`;
  },

  playQueue(tracks, start) {
    this.queue = tracks.slice();
    this.index = start;
    this.playCurrent();
    this.mode = 'now';
    this.render();
    setTimeout(() => { const p = $('#ctl-play'); if (p) p.focus(); }, 80);
  },

  playCurrent() {
    const t = this.current();
    if (!t) return;
    this.ensureGraph();
    audio.src = this.srcFor(t);
    audio.play().catch((err) => toast(`Can't play this track: ${err.message}`));
    const art = this.thumb(t.parentThumb || t.thumb, 48);   // (tiny: stretched, it is the blurred backdrop)
    const wp = $('#wallpaper .art');
    if (art) { wp.style.backgroundImage = `url("${art}")`; wp.classList.add('on'); }
    $('#tile-music-sub').textContent = `Playing: ${t.title} · ${t.grandparentTitle || ''}`;
    this.updateCaption();
  },

  pickNext(step) {
    if (!this.queue.length) return -1;
    if (this.repeat === 'one' && step === 0) return this.index;
    if (this.shuffle && this.queue.length > 1) {
      let i;
      do { i = Math.floor(Math.random() * this.queue.length); } while (i === this.index);
      return i;
    }
    const i = this.index + (step || 1);
    if (i >= this.queue.length) return this.repeat === 'all' ? 0 : -1;
    if (i < 0) return 0;
    return i;
  },

  next() { const i = this.pickNext(1); if (i >= 0) { this.index = i; this.playCurrent(); this.refreshNow(); } },
  prev() {
    if (audio.currentTime > 4) { audio.currentTime = 0; return; }
    if (this.index > 0) { this.index -= 1; this.playCurrent(); this.refreshNow(); }
  },
  toggle() {
    if (this.index < 0) return;
    if (audio.paused) { this.ensureGraph(); audio.play(); } else audio.pause();
  },
  stop() { audio.pause(); },
  seek(by) {
    if (this.index < 0 || !isFinite(audio.duration)) return;
    audio.currentTime = Math.max(0, Math.min(audio.duration - 0.5, audio.currentTime + by));
  },

  ended() {
    const i = this.pickNext(this.repeat === 'one' ? 0 : 1);
    if (i >= 0) { this.index = i; this.playCurrent(); this.refreshNow(); }
    else { $('#tile-music-sub').textContent = 'Your music, with visualizers'; $('#wallpaper .art').classList.remove('on'); }
  },

  updateCaption() {
    const t = this.current();
    const cap = $('#viz-caption');
    if (!t) { cap.replaceChildren(); return; }
    cap.replaceChildren(t.title, h('small', null, `${t.grandparentTitle || ''} · ${t.parentTitle || ''}`));
  },

  refreshNow() {
    if (state.view === 'music' && this.mode === 'now') {
      const had = document.activeElement && document.activeElement.id;
      this.renderNow($('#music-body'));
      if (had && document.getElementById(had)) document.getElementById(had).focus();
    }
  },

  renderNow(body) {
    const t = this.current();
    if (!t) {
      body.replaceChildren(h('div', { class: 'empty' }, 'Nothing playing. Pick an album or playlist from the library.'));
      return;
    }
    const cover = h('div', { class: 'cover' });
    const art = this.thumb(t.parentThumb || t.thumb, 600);
    if (art) cover.style.backgroundImage = `url("${art}")`;
    const nextIdx = this.shuffle ? -1 : this.index + 1;
    const upnext = this.queue[nextIdx];
    const playBtn = h('button', { class: 'ctl play', id: 'ctl-play', 'aria-label': 'Play or pause', html: audio.paused ? ICON.play : ICON.pause, onclick: () => this.toggle() });
    const modes = [['spectrum', 'Spectrum'], ['mirror', 'Mirror'], ['wave', 'Wave']];
    const backBar = h('div', { class: 'lib-tabs', style: { marginBottom: '20px' } },
      h('button', { class: 'pill', id: 'np-back', onclick: () => { this.mode = 'library'; this.render(); setTimeout(focusFirstContent, 80); } },
        h('span', { html: '<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg>' }),
        'Back'),
      h('span', { class: 'crumb' }, this.stack.length ? this.stack[this.stack.length - 1].title : 'Library'));
    body.replaceChildren(backBar,
      h('div', { class: 'music-top' },
        cover,
        h('div', { class: 'np' },
          h('div', { style: { display: 'flex', flexDirection: 'column', gap: '14px' } },
            h('span', { class: 'eyebrow' }, 'NOW PLAYING'),
            h('span', { class: 'title' }, t.title),
            h('span', { class: 'meta' }, `${t.grandparentTitle || ''} · ${t.parentTitle || ''}`)),
          h('div', null,
            h('div', { class: 'progress' }, h('i', { id: 'np-bar' })),
            h('div', { class: 'times' }, h('span', { id: 'np-pos' }, '0:00'), h('span', { id: 'np-dur' }, fmtTime((t.duration || 0) / 1000)))),
          h('div', { class: 'controls' },
            h('button', { class: `ctl sm${this.shuffle ? ' on' : ''}`, id: 'ctl-shuffle', 'aria-label': 'Shuffle', 'aria-pressed': String(this.shuffle), html: ICON.shuffle, onclick: () => { this.shuffle = !this.shuffle; this.refreshNow(); } }),
            h('button', { class: 'ctl', id: 'ctl-prev', 'aria-label': 'Previous track', html: ICON.prev, onclick: () => this.prev() }),
            playBtn,
            h('button', { class: 'ctl', id: 'ctl-next', 'aria-label': 'Next track', html: ICON.next, onclick: () => this.next() }),
            h('button', { class: `ctl sm${this.repeat !== 'off' ? ' on' : ''}`, id: 'ctl-repeat', 'aria-label': `Repeat: ${this.repeat}`, html: this.repeat === 'one' ? ICON.repeatOne : ICON.repeat, onclick: () => { this.repeat = { off: 'all', all: 'one', one: 'off' }[this.repeat]; this.refreshNow(); } }),
            h('div', { class: 'upnext' }, h('span', null, this.shuffle ? 'Shuffle is on' : 'Up next'), h('b', null, upnext ? `${upnext.title} · ${upnext.grandparentTitle || ''}` : this.shuffle ? 'Random from this list' : 'End of list'))))),
      h('div', { class: 'viz-wrap' },
        h('div', { class: 'viz-bar' },
          h('span', { class: 'lbl' }, 'Visualizer'),
          modes.map(([id, label]) => h('button', {
            class: `pill${viz.mode === id ? ' selected' : ''}`, id: `viz-${id}`,
            onclick: () => { viz.mode = id; this.refreshNow(); },
          }, label)),
          h('span', { style: { flexGrow: 1 } }),
          h('button', { class: 'pill', id: 'viz-full-btn', onclick: () => viz.openFull() }, h('span', { html: ICON.expand }), 'Full screen')),
        h('div', { class: 'viz' }, h('canvas', { id: 'viz-canvas' }))),
    );
    this.updateProgress();
  },

  updateProgress() {
    const bar = $('#np-bar');
    if (!bar) return;
    const dur = audio.duration || ((this.current() || {}).duration || 0) / 1000;
    bar.style.width = dur ? `${Math.min(100, (audio.currentTime / dur) * 100)}%` : '0%';
    $('#np-pos').textContent = fmtTime(audio.currentTime);
    if (audio.duration) $('#np-dur').textContent = fmtTime(audio.duration);
  },
};

function focusFirstContent() {
  const el = $('#music-body button');
  if (el) el.focus();
}

audio.addEventListener('timeupdate', () => music.updateProgress());
audio.addEventListener('ended', () => music.ended());
audio.addEventListener('play', () => { const p = $('#ctl-play'); if (p) p.innerHTML = ICON.pause; });
audio.addEventListener('pause', () => { const p = $('#ctl-play'); if (p) p.innerHTML = ICON.play; });
audio.addEventListener('error', () => {
  if (music.index < 0) return;
  toast('This track could not be played. Skipping.');
  setTimeout(() => music.next(), 1500);
});

/* ==================================================================== setup */

const setup = {
  step: 0,
  steps: ['welcome', 'country', 'network', 'password', 'location', 'theme', 'plex', 'done'],
  netTimer: null,

  go(i) {
    this.step = Math.max(0, Math.min(this.steps.length - 1, i));
    this.render();
  },

  frame(title, lead, body, { next, nextLabel = 'Continue', skip, back = true } = {}) {
    const dots = h('div', { class: 'steps' }, this.steps.slice(1, -1).map((_, i) => h('i', { class: i < this.step ? 'on' : '' })));
    $('#setup-body').replaceChildren(
      h('div', { class: 'brand' }, h('b', null, 'Home Base'), this.step > 0 && this.step < this.steps.length - 1 ? dots : null),
      h('h1', null, title),
      lead ? h('p', { class: 'lead' }, lead) : null,
      h('div', { class: 'body' }, body),
      h('div', { class: 'foot' },
        back && this.step > 0 ? h('button', { class: 'pill', onclick: () => this.go(this.step - 1) }, 'Back') : h('span'),
        h('div', { class: 'right' },
          skip ? h('button', { class: 'pill', style: { height: '80px' }, onclick: skip }, 'Skip for now') : null,
          next ? h('button', { class: 'primary', id: 'setup-next', onclick: next }, nextLabel) : null)),
    );
    setTimeout(() => { const el = $('#setup-body input') || $('#setup-next') || $('#setup-body .list-btn'); if (el) el.focus(); }, 80);
  },

  render() {
    clearInterval(this.netTimer);
    const name = this.steps[this.step];
    const advance = () => this.go(this.step + 1);
    if (name === 'welcome') {
      return this.frame('Welcome', 'Let’s get your TV set up. It takes about two minutes. Use the arrow keys and Enter on your remote, or the trackpad.', [], { next: advance, nextLabel: 'Start', back: false });
    }
    if (name === 'country') {
      return this.frame('Where are you?', 'Wi-Fi rules depend on your country, so Wi-Fi stays off until you pick one.',
        countryPicker(async (cc) => {
          try { state.settings = await api('/api/country', { country: cc }); advance(); } catch (err) { toast(err.message); }
        }, state.settings.country), { next: state.settings.country ? advance : null });
    }
    if (name === 'network') return this.renderNetwork(advance);
    if (name === 'password') {
      this.frame('Choose a password', 'This box’s own password, for maintenance such as remote access and system updates. Watching TV never asks for it.',
        [h('div', { class: 'empty' }, 'Checking…')], { skip: advance });
      api('/api/ssh').then((s) => {
        if (this.steps[this.step] !== 'password') return;
        if (s.has_password) {
          return this.frame('Password', 'This box already has a password. You can change it any time in Settings.', [], { next: advance });
        }
        const f = passwordFields(false);
        f.last.dataset.enter = 'setup-next';
        this.frame('Choose a password', 'This box’s own password, for maintenance such as remote access and system updates. Watching TV never asks for it.',
          f.inputs, { next: async () => { if (await f.submit()) { toast('Password saved'); advance(); } }, skip: advance });
      }).catch(() => advance());
      return undefined;
    }
    if (name === 'location') {
      const current = state.settings.weather.name;
      return this.frame('Your location', 'Used for the weather and to set the clock. Type your city or ZIP / postcode.',
        [...locationSearch(() => advance()), current ? h('p', { class: 'note' }, `Currently: ${current}`) : null],
        { skip: advance, next: current ? advance : null });
    }
    if (name === 'theme') {
      const grid = h('div', { class: 'theme-grid' }, THEMES.map((t) => h('button', {
        class: `theme-card${t.id === state.settings.theme ? ' selected' : ''}`, 'data-theme': t.id,
        style: { '--p-bg': t.bg, '--p-text': t.text },
        onclick: async () => { await saveSettings({ theme: t.id }); this.render(); const el = $(`#setup-body .theme-card[data-theme="${t.id}"]`); if (el) el.focus(); },
      }, h('span', { class: 'sw' }, t.sw.map((c) => h('i', { style: { background: c } }))), h('span', { class: 'nm' }, t.name))));
      return this.frame('Pick a look', 'You can change this any time in Settings.', grid, { next: advance });
    }
    if (name === 'plex') {
      return this.frame('Plex', 'Link your Plex account to play your music here with visualizers. You can also do this later in Settings.',
        h('div', null, h('button', { class: 'primary', onclick: () => music.link(() => advance()) }, 'Link Plex account')),
        { skip: advance });
    }
    return this.frame('You’re all set', 'Your home screen is ready. Settings, restart and power off live under the ⋯ button in the top corner.', [],
      { next: async () => { state.settings = await api('/api/setup/done', {}); show('home'); }, nextLabel: 'Go to home screen' });
  },

  async renderNetwork(advance) {
    let n;
    try { n = await api('/api/network'); } catch (err) { n = { wifi: {}, ethernet: {} }; }
    if ((n.wifi && n.wifi.connected) || (n.ethernet && n.ethernet.connected)) {
      const via = n.wifi.connected ? `Wi-Fi network “${n.wifi.ssid}”` : 'Ethernet';
      return this.frame('You’re online', `Connected using ${via}.`, [], { next: advance });
    }
    const list = h('div', { class: 'list' }, h('div', { class: 'note' }, 'Looking for networks…'));
    this.frame('Connect to the internet', 'Choose your Wi-Fi network. If you plug in a network cable instead, this moves on by itself.',
      [list, h('button', { class: 'list-btn dashed', onclick: () => joinDialog(null, () => this.render()) }, 'Join a hidden network…')],
      { skip: advance });
    try {
      const nets = await api('/api/wifi/scan');
      list.replaceChildren(...(nets.length ? nets.slice(0, 8).map((w) => h('button', {
        class: 'list-btn', onclick: () => joinDialog(w, () => this.render()),
      }, h('span', null, w.ssid), h('span', { class: 'r', html: w.secure ? ICON.lock : 'Open' }))) : [h('div', { class: 'note' }, 'No Wi-Fi networks found. Check the Wi-Fi country, or plug in a network cable.')]));
      const first = $('#setup-body .list-btn');
      if (first && !state.dialogOpen) first.focus();
    } catch (err) { list.replaceChildren(h('div', { class: 'note err' }, err.message)); }
    // Move on automatically when a cable is plugged in.
    this.netTimer = setInterval(async () => {
      try {
        const now = await api('/api/network');
        if (now.ethernet && now.ethernet.connected && !state.dialogOpen) { clearInterval(this.netTimer); this.render(); }
      } catch { /* ignore */ }
    }, 4000);
  },
};

/* ==================================================================== plex video */

const plexv = {
  tab: 'continue',
  stack: [],
  sections: null,
  playing: false,

  async render() {
    const body = $('#plex-body');
    if (!music.status) {
      body.replaceChildren(h('div', { class: 'empty' }, 'Connecting to Plex…'));
      try { music.status = await api('/api/plex/status'); } catch (err) { music.status = { linked: false }; }
    }
    if (!music.status.linked) {
      $('#plex-server').hidden = true;
      body.replaceChildren(h('div', { class: 'card', style: { maxWidth: '1000px' } },
        h('h2', null, 'Link your Plex account'),
        h('p', { style: { fontSize: '30px', lineHeight: 1.45 } }, 'Movies and shows come from your Plex server. Link this box to your Plex account once, with a code.'),
        h('div', null, h('button', { class: 'primary', onclick: () => music.link(() => { this.sections = null; this.render(); }) }, 'Link Plex account'))));
      return;
    }
    $('#plex-server').hidden = !music.status.server;
    $('#plex-server-name').textContent = music.status.server || '';
    const top = this.stack[this.stack.length - 1];
    if (top && top.kind === 'item') return this.renderItem(body, top);
    await this.renderBrowse(body, top);
  },

  back() {
    if (this.stack.length) { this.stack.pop(); this.render(); setTimeout(focusFirstPlex, 80); return true; }
    return false;
  },

  open(entry) { this.stack.push(entry); this.render(); setTimeout(focusFirstPlex, 120); },

  async videoSections() {
    if (!this.sections) {
      const mc = await music.plex('/library/sections');
      this.sections = (mc.Directory || []).filter((d) => d.type === 'movie' || d.type === 'show');
    }
    return this.sections;
  },

  poster(it) {
    if (it.type === 'episode') return it.grandparentThumb || it.parentThumb || it.thumb;
    if (it.type === 'season') return it.thumb || it.parentThumb;
    return it.thumb;
  },

  async renderBrowse(body, top) {
    const content = h('div', { class: 'grid posters' }, h('div', { class: 'empty' }, 'Loading…'));
    let bar;
    if (top) {
      bar = h('div', { class: 'lib-tabs' },
        h('button', { class: 'pill', onclick: () => this.back() }, h('span', { html: '<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg>' }), 'Back'),
        h('span', { class: 'crumb' }, top.title));
    } else {
      let sections = [];
      try { sections = await this.videoSections(); } catch (err) { body.replaceChildren(h('div', { class: 'empty' }, err.message)); return; }
      const tabs = [['search', 'Search'], ['continue', 'Continue watching'], ['recent', 'Recently added'], ...sections.map((s) => [s.key, s.title])];
      bar = h('div', { class: 'lib-tabs' }, tabs.map(([id, label]) => h('button', {
        class: `pill${this.tab === id ? ' selected' : ''}`, onclick: () => { this.tab = id; this.render(); },
      }, label)));
    }
    if (!top && this.tab === 'search') return this.renderSearch(body, bar);
    body.replaceChildren(bar, content);
    try {
      let items;
      if (top && top.kind === 'show') items = (await music.plex(`/library/metadata/${top.key}/children`)).Metadata;
      else if (top && top.kind === 'season') return this.renderEpisodes(content, top);
      else if (this.tab === 'continue') items = (await music.plex('/library/onDeck?X-Plex-Container-Start=0&X-Plex-Container-Size=40')).Metadata;
      else if (this.tab === 'recent') {
        items = (await music.plex('/library/recentlyAdded?X-Plex-Container-Start=0&X-Plex-Container-Size=60')).Metadata || [];
        items = items.filter((i) => ['movie', 'show', 'season', 'episode'].includes(i.type));
      } else {
        items = (await music.plex(`/library/sections/${this.tab}/all?sort=titleSort&X-Plex-Container-Start=0&X-Plex-Container-Size=2000`)).Metadata || [];
        this.fillGrid(content, items);
        this.addLetterBar(body, content, items);
        return;
      }
      this.fillGrid(content, items || []);
    } catch (err) { content.replaceChildren(h('div', { class: 'empty' }, err.message)); }
  },

  fillGrid(content, items) {
    if (!items.length) { content.replaceChildren(h('div', { class: 'empty' }, this.tab === 'continue' ? 'Nothing in progress.' : 'Nothing here yet.')); return; }
    content.replaceChildren(...items.map((it) => {
      const img = h('div', { class: 'img' });
      const src = music.thumb(this.poster(it), 360);
      if (src) img.style.backgroundImage = `url("${src}")`;
      let sub = it.year ? String(it.year) : '';
      if (it.type === 'episode') sub = `S${it.parentIndex}·E${it.index} · ${it.title}`;
      if (it.type === 'season') sub = it.parentTitle || '';
      if (it.type === 'show') sub = `${it.childCount || ''} season${it.childCount === 1 ? '' : 's'}`;
      const name = it.type === 'episode' ? it.grandparentTitle : it.title;
      const prog = it.viewOffset && it.duration ? h('div', { class: 'prog' }, h('i', { style: { width: `${Math.min(100, it.viewOffset / it.duration * 100)}%` } })) : null;
      const watched = !it.viewOffset && it.viewCount && (it.type === 'movie' || it.type === 'episode');
      return h('button', {
        class: 'card-item', onclick: () => {
          if (it.type === 'show') this.open({ kind: 'show', key: it.ratingKey, title: it.title });
          else if (it.type === 'season') this.open({ kind: 'season', key: it.ratingKey, title: `${it.parentTitle || ''} · ${it.title}` });
          else this.open({ kind: 'item', key: it.ratingKey, title: name });
        },
      }, h('div', { class: 'poster-wrap' }, img, prog, watched ? h('span', { class: 'seen', html: ICON.check }) : null),
      h('div', { class: 't1' }, name), sub ? h('div', { class: 't2' }, sub) : null);
    }));
  },

  // Search, as you type (after a pause): movies, shows and episodes on the server
  renderSearch(body, bar) {
    const q = h('input', { class: 'text-input', placeholder: 'Search movies and shows', value: this.query || '', style: { flexGrow: 1 } });
    const results = h('div', { class: 'grid posters' });
    let timer = null, seq = 0;
    const run = async () => {
      const query = q.value.trim();
      this.query = query;
      if (query.length < 2) { results.replaceChildren(); return; }
      const mine = ++seq;
      results.replaceChildren(...skeletonCards(7));
      try {
        const mc = await music.plex(`/hubs/search?query=${encodeURIComponent(query)}&limit=30`);
        if (mine !== seq) return;   // (a newer search has started)
        const items = [];
        for (const hub of mc.Hub || []) {
          if (['movie', 'show', 'season', 'episode'].includes(hub.type)) items.push(...(hub.Metadata || []));
        }
        if (!items.length) { results.replaceChildren(h('div', { class: 'empty' }, `Nothing found for “${query}”.`)); return; }
        this.fillGrid(results, items);
      } catch (err) { if (mine === seq) results.replaceChildren(h('div', { class: 'empty' }, err.message)); }
    };
    q.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(run, 450); });
    q.addEventListener('keydown', (e) => { if (e.key === 'Enter') { clearTimeout(timer); run(); } });
    body.replaceChildren(bar, h('div', { style: { display: 'flex', gap: '16px', marginBottom: '24px' } }, q), results);
    if (this.query) run();
    setTimeout(() => q.focus(), 60);
  },

  // A–Z down the right of a library: OK on a letter jumps to its first title; the letter of the focused title lights
  addLetterBar(body, grid, items) {
    if (items.length < 20) return;   // (a short list needs no index)
    const letterOf = (it) => {
      const c = String(it.titleSort || it.title || '').trim().charAt(0).toUpperCase();
      return c >= 'A' && c <= 'Z' ? c : '#';
    };
    const cards = [...grid.querySelectorAll('.card-item')];
    const first = new Map();
    items.forEach((it, i) => { const l = letterOf(it); if (!first.has(l) && cards[i]) first.set(l, cards[i]); cards[i].dataset.letter = l; });
    const letters = ['#', ...'ABCDEFGHIJKLMNOPQRSTUVWXYZ'];
    const buttons = new Map();
    const strip = h('div', { class: 'alpha-bar', role: 'navigation', 'aria-label': 'Jump to letter' }, letters.map((l) => {
      const target = first.get(l);
      const b = h('button', { class: `alpha${target ? '' : ' none'}`, disabled: !target, onclick: () => {
        if (!target) return;
        target.focus();
        target.scrollIntoView({ block: 'start', behavior: 'smooth' });
      } }, l);
      buttons.set(l, b);
      return b;
    }));
    grid.addEventListener('focusin', (e) => {
      const l = e.target.dataset && e.target.dataset.letter;
      if (!l) return;
      buttons.forEach((b, k) => b.classList.toggle('here', k === l));
    });
    const wrap = h('div', { class: 'lib-with-index' });
    grid.replaceWith(wrap);   // (in the grid's place first; then the grid moves inside)
    wrap.append(grid, strip);
  },

  async renderEpisodes(content, top) {
    const eps = (await music.plex(`/library/metadata/${top.key}/children`)).Metadata || [];
    const list = h('div', { class: 'tracks' }, eps.map((ep) => h('button', {
      class: 'track', 'data-key': ep.ratingKey, onclick: () => { top.focus = ep.ratingKey; this.open({ kind: 'item', key: ep.ratingKey, title: ep.title }); },
    }, h('span', { class: 'n' }, ep.index), h('span', null, ep.title,
      h('span', { class: 's' }, [ep.viewOffset ? 'In progress' : ep.viewCount ? 'Watched' : '', (ep.summary || '').slice(0, 110)].filter(Boolean).join(' · '))),
    h('span', { class: 'd' }, fmtTime((ep.duration || 0) / 1000)))));
    content.replaceWith(list);
    // start on the episode that led here, else the first (after open()'s own focus, which may have found only Back)
    setTimeout(() => {
      const want = (top.focus && list.querySelector(`[data-key="${top.focus}"]`)) || list.querySelector('.track');
      if (want && (!list.contains(document.activeElement) || top.focus)) { want.focus(); want.scrollIntoView({ block: 'center' }); }
    }, 150);
  },

  async renderItem(body, top) {
    body.replaceChildren(h('div', { class: 'empty' }, 'Loading…'));
    let it;
    try { it = ((await music.plex(`/library/metadata/${top.key}`)).Metadata || [])[0]; } catch (err) { body.replaceChildren(h('div', { class: 'empty' }, err.message)); return; }
    if (!it) { body.replaceChildren(h('div', { class: 'empty' }, 'Not found.')); return; }
    const poster = h('div', { class: 'detail-poster' });
    const src = music.thumb(this.poster(it), 600);
    if (src) poster.style.backgroundImage = `url("${src}")`;
    const art = it.art || it.grandparentArt;
    const wp = $('#wallpaper .art');
    if (art && state.settings.wallpaper === 'art') { wp.style.backgroundImage = `url("${music.thumb(art, 48)}")`; wp.classList.add('on'); }
    const mins = it.duration ? Math.round(it.duration / 60000) : 0;
    const meta = [it.type === 'episode' ? `S${it.parentIndex}·E${it.index}` : null, it.year, mins ? `${Math.floor(mins / 60) ? `${Math.floor(mins / 60)} h ` : ''}${mins % 60} min` : null,
      it.contentRating, it.Media && it.Media[0] && it.Media[0].videoResolution ? `${String(it.Media[0].videoResolution).toUpperCase()}` : null].filter(Boolean).join(' · ');
    const play = async (resume) => {
      upNext.chain = 0;
      starting.show(it.title, src, null);
      try { await api('/api/plex/play', { key: it.ratingKey, resume }); starting.untilPlaying(); this.watchPlayer(); }
      catch (err) { starting.hide(); toast(err.message); }
    };
    const actions = h('div', { class: 'detail-actions' },
      it.viewOffset ? h('button', { class: 'primary', id: 'plex-resume', onclick: () => play(true) }, `Resume from ${fmtTime(it.viewOffset / 1000)}`) : null,
      h('button', { class: it.viewOffset ? 'pill' : 'primary', id: 'plex-play', style: it.viewOffset ? { height: '80px' } : null, onclick: () => play(false) }, it.viewOffset ? 'Play from start' : 'Play'),
      // an episode (from Continue watching, Recently added or Search): on to the rest of its show
      it.type === 'episode' && it.parentRatingKey ? h('button', { class: 'pill', style: { height: '80px' }, onclick: () => this.open({
        kind: 'season', key: it.parentRatingKey, focus: it.ratingKey,
        title: `${it.grandparentTitle || ''} · ${it.parentTitle || `Season ${it.parentIndex}`}` }) }, 'Episodes') : null,
      it.type === 'episode' && it.grandparentRatingKey ? h('button', { class: 'pill', style: { height: '80px' }, onclick: () => this.open({
        kind: 'show', key: it.grandparentRatingKey, title: it.grandparentTitle || '' }) }, 'Seasons') : null);
    body.replaceChildren(h('div', { class: 'detail' }, poster,
      h('div', { class: 'detail-info' },
        it.type === 'episode' ? h('div', { class: 'eyebrow' }, it.grandparentTitle) : null,
        h('h2', null, it.title),
        meta ? h('div', { class: 'detail-meta' }, meta) : null,
        it.tagline ? h('p', { class: 'detail-tagline' }, it.tagline) : null,
        h('p', { class: 'detail-summary' }, it.summary || ''),
        actions)));
    setTimeout(() => { const b = $('#plex-resume') || $('#plex-play'); if (b) b.focus(); }, 60);
  },

  // Refresh the details (resume point, watched) once the player closes.
  watchPlayer() {
    clearInterval(this.playerTimer);
    this.playerTimer = setInterval(async () => {
      let p;
      try { p = await api('/api/player'); } catch { return; }
      if (!p.playing) { clearInterval(this.playerTimer); if (state.view === 'plex') this.render(); }
    }, 2000);
  },
};

// An episode played to its end (or Next episode taken in its credits): the next one, in 10 s unless Cancel or Back.
// After three in a row with nobody pressing anything it waits for Play now, rather than playing on all night.
const upNext = {
  timer: null,
  chain: 0,
  show(n) {
    if (!n || !n.key) return;
    if (n.pressed) this.chain = 0;
    clearInterval(this.timer);
    const auto = this.chain < 3;
    let left = 10;
    const count = h('p', { class: 'up-next-count' }, auto ? `Playing in ${left} s` : 'Still watching?');
    const img = h('div', { class: 'up-next-img' });
    const src = music.thumb(n.thumb, 480);
    if (src) img.style.backgroundImage = `url("${src}")`;
    openDialog({
      title: 'Up next',
      body: h('div', { class: 'up-next' }, img, h('div', null,
        h('div', { class: 'eyebrow' }, n.show),
        h('h3', null, n.title),
        h('div', { class: 'detail-meta' }, `S${n.season}·E${n.episode}`),
        count)),
      actions: [{ label: 'Cancel', onClick: closeDialog },
        { label: 'Play now', primary: true, onClick: () => { this.chain = 0; closeDialog(); this.play(n); } }],
      onClose: () => clearInterval(this.timer),
    });
    if (!auto) return;
    this.timer = setInterval(() => {
      left -= 1;
      count.textContent = `Playing in ${left} s`;
      if (left > 0) return;
      clearInterval(this.timer);
      this.chain += 1;
      closeDialog();
      this.play(n);
    }, 1000);
  },
  async play(n) {
    if (state.view === 'plex') {   // (the details behind the player become the new episode's)
      const top = plexv.stack[plexv.stack.length - 1];
      const entry = { kind: 'item', key: n.key, title: n.title };
      if (top && top.kind === 'item') plexv.stack[plexv.stack.length - 1] = entry; else plexv.stack.push(entry);
      plexv.render();
    }
    starting.show(n.title, music.thumb(n.thumb, 600), null);
    try { await api('/api/plex/play', { key: n.key, resume: true }); starting.untilPlaying(); plexv.watchPlayer(); }
    catch (err) { starting.hide(); toast(err.message); }
  },
};

function focusFirstPlex() {
  const el = $('#plex-body .card-item') || $('#plex-body .track') || $('#plex-body button');
  if (el) el.focus();
}

/* ==================================================================== loading */

// Placeholder cards while a row or page loads: the shape of what is coming, gently pulsing (opacity only: cheap)
function skeletonCards(n) {
  return Array.from({ length: n }, () => h('div', { class: 'card-item skel-card', 'aria-hidden': 'true' },
    h('div', { class: 'img skel' }), h('div', { class: 'skel skel-line' }), h('div', { class: 'skel skel-line short' })));
}

// "Starting" over the whole screen from Play until the video is on screen (the player opens over it)
const starting = {
  timer: null,
  show(title, img, fallback) {
    const el = $('#starting');
    $('#starting-title').textContent = title || '';
    const bg = $('#starting .bg');
    bg.style.backgroundImage = img ? (fallback ? `url("${img}"), url("${fallback}")` : `url("${img}")`) : '';
    el.hidden = false;
    requestAnimationFrame(() => el.classList.add('on'));
  },
  hide() {
    clearInterval(this.timer);
    const el = $('#starting');
    el.classList.remove('on');
    setTimeout(() => { if (!el.classList.contains('on')) el.hidden = true; }, 300);
  },
  // the player reports a position once frames are out; give up after 40 s (the player shows its own errors)
  untilPlaying() {
    clearInterval(this.timer);
    const t0 = Date.now();
    this.timer = setInterval(async () => {
      let p = null;
      try { p = await api('/api/player'); } catch { /* try again */ }
      if ((p && p.playing && p.position > 0) || (p && !p.playing && Date.now() - t0 > 4000) || Date.now() - t0 > 40000) this.hide();
    }, 500);
  },
};

/* ==================================================================== youtube */

const yt = {
  tab: 'home',
  stack: [],
  query: '',
  results: null,

  back() {
    if (this.stack.length) { this.stack.pop(); this.render(); setTimeout(() => focusIn('#youtube-body'), 80); return true; }
    return false;
  },
  open(entry) { this.stack.push(entry); this.render(); setTimeout(() => focusIn('#youtube-body'), 120); },

  async render() {
    const body = $('#youtube-body');
    const top = this.stack[this.stack.length - 1];
    if (top && top.kind === 'video') return this.renderVideo(body, top.video);
    if (top && top.kind === 'channel') return this.renderChannel(body, top.id);
    const tabs = [['home', 'For you'], ['search', 'Search'], ['subs', 'Subscriptions'], ['history', 'History']];   // (the back button above says Home)
    const onTab = document.activeElement && document.activeElement.dataset.ytTab;
    const bar = h('div', { class: 'lib-tabs' }, tabs.map(([id, label]) => h('button', {
      class: `pill${this.tab === id ? ' selected' : ''}`, 'data-yt-tab': id, onclick: () => { this.tab = id; this.render(); },
    }, label)));
    const account = h('button', { class: 'pill', style: { marginLeft: 'auto' }, onclick: () => this.signIn(account.dataset.signedIn === '1') }, '…');
    bar.append(account);
    api('/api/yt/account').then((a) => {
      account.dataset.signedIn = a.signed_in ? '1' : '0';
      account.textContent = a.signed_in ? 'Sign out' : 'Sign in';
    }).catch(() => account.remove());
    if (onTab) setTimeout(() => { const t = body.querySelector(`[data-yt-tab="${onTab}"]`); if (t) t.focus(); }, 0);
    const content = h('div', { class: 'grid videos' }, ...skeletonCards(8));
    if (this.tab === 'search') {
      const q = h('input', { class: 'text-input', placeholder: 'Search YouTube', value: this.query, 'data-enter': 'yt-go', style: { flexGrow: 1 } });
      const go = h('button', { class: 'primary', id: 'yt-go', onclick: async () => {
        this.query = q.value.trim();
        if (!this.query) return;
        content.className = 'grid videos';
        content.replaceChildren(...skeletonCards(8));
        try { this.results = await api(`/api/yt/search?q=${encodeURIComponent(this.query)}`); this.fillVideos(content, this.results); }
        catch (err) { content.replaceChildren(h('div', { class: 'empty' }, err.message)); }
      } }, 'Search');
      body.replaceChildren(bar, h('div', { style: { display: 'flex', gap: '16px', marginBottom: '24px' } }, q, go), content);
      if (this.results) this.fillVideos(content, this.results); else content.replaceChildren();
      setTimeout(() => (this.results ? null : q.focus()), 60);
      return;
    }
    body.replaceChildren(bar, content);
    try {
      if (this.tab === 'home') {
        const r = await api('/api/yt/home');
        content.className = 'yt-rows';
        const rows = [];
        if (r.continue.length) rows.push(this.row('Continue watching', r.continue));
        if (r.videos.length) rows.push(this.row('From your subscriptions', r.videos));
        r.rows.forEach(({ id, title }) => {
          const strip = h('div', { class: 'yt-strip' }, ...skeletonCards(5));
          const section = h('section', { class: 'yt-row' }, h('h3', null, title), strip);
          rows.push(section);
          api(`/api/yt/row?id=${id}`).then((t) => {
            // (the account's recommendations come as YouTube's own shelves, each its own row)
            const shelves = (t.shelves || [{ title, videos: t.videos }]).filter((s) => s.videos.length);
            if (!shelves.length) { section.remove(); return; }
            section.replaceWith(...shelves.map((s) => this.row(s.title, s.videos)));
            this.focusStart();
          }).catch(() => section.remove());
        });
        content.replaceChildren(...rows);
        this.focusStart();
      } else if (this.tab === 'subs') {
        const subs = await api('/api/yt/subs');
        if (!subs.length) { content.replaceChildren(h('div', { class: 'empty' }, 'No subscriptions yet.')); return; }
        content.className = 'grid';
        content.replaceChildren(...subs.map((c) => {
          const img = h('div', { class: 'img' });
          if (c.avatar) img.style.backgroundImage = `url("${c.avatar}")`;
          return h('button', { class: 'card-item round-img', onclick: () => this.open({ kind: 'channel', id: c.id }) },
            img, h('div', { class: 't1' }, c.name));
        }));
      } else {
        const hist = await api('/api/yt/history');
        if (!hist.length) { content.replaceChildren(h('div', { class: 'empty' }, 'Nothing watched yet.')); return; }
        this.fillVideos(content, hist);
      }
    } catch (err) { content.replaceChildren(h('div', { class: 'empty' }, err.message)); }
  },

  // As YouTube's TV apps sign in: a code (and QR code) on the TV, approved on a phone; this waits for the approval
  async signIn(out) {
    if (out) {
      try { await api('/api/yt/signin', { out: true }); toast('Signed out of YouTube'); this.render(); }
      catch (err) { toast(err.message); }
      return;
    }
    let r;
    try { r = await api('/api/yt/signin', {}); } catch (err) { toast(err.message); return; }
    const qr = h('div', { class: 'yt-qr' });
    if (r.qr) {   // (an SVG made on this box from the sign-in address; scaled to fit whole, not cropped)
      qr.innerHTML = r.qr;
      const svg = qr.querySelector('svg');
      if (svg && !svg.getAttribute('viewBox')) {
        svg.setAttribute('viewBox', `0 0 ${parseFloat(svg.getAttribute('width'))} ${parseFloat(svg.getAttribute('height'))}`);
      }
      if (svg) { svg.removeAttribute('width'); svg.removeAttribute('height'); }
    }
    const status = h('p', { class: 'yt-signin-status' }, 'Waiting for you to approve…');
    let polling = true;
    openDialog({
      title: 'Sign in to YouTube',
      body: h('div', { class: 'yt-signin' }, qr, h('div', null,
        h('p', null, 'Scan the code with your phone, or go to'),
        h('p', { class: 'yt-signin-url' }, r.url),
        h('p', null, 'and enter'),
        h('p', { class: 'yt-signin-code' }, r.code),
        status)),
      actions: [{ label: 'Cancel', onClick: () => closeDialog() }],
      onClose: () => { polling = false; },
    });
    while (polling) {
      await new Promise((res) => setTimeout(res, 3000));
      if (!polling) break;
      const a = await api('/api/yt/account').catch(() => null);
      if (!a) continue;
      if (a.signed_in && a.pending === 'done') {
        polling = false;
        closeDialog();
        toast('Signed in to YouTube');
        this.tab = 'home';
        this.render();
      } else if (a.pending === 'denied' || a.pending === 'expired') {
        polling = false;
        status.textContent = a.pending === 'denied' ? 'Sign-in was declined.' : 'The code expired. Close and try again.';
      }
    }
  },

  fillVideos(content, videos) {
    content.className = 'grid videos';
    if (!videos.length) { content.replaceChildren(h('div', { class: 'empty' }, 'No videos.')); return; }
    this.focusStart();
    content.replaceChildren(...videos.map((v) => this.card(v)));
  },

  // arriving at the screen (focus still on Home or nowhere): start on the first video
  focusStart() {
    setTimeout(() => {   // (after show()'s own focus)
      if ($('#youtube-body').contains(document.activeElement)) return;
      const first = $('#youtube-body .card-item');
      if (first) first.focus();
    }, 100);
  },

  row(title, videos) {
    return h('section', { class: 'yt-row' }, h('h3', null, title), h('div', { class: 'yt-strip' }, videos.map((v) => this.card(v))));
  },

  card(v) {
    const img = h('div', { class: 'img' });
    img.style.backgroundImage = `url("${v.thumb}")`;
    const dur = v.live ? 'LIVE' : v.duration ? fmtTime(v.duration) : '';
    const prog = v.position && v.duration ? h('div', { class: 'prog' }, h('i', { style: { width: `${Math.min(100, v.position / v.duration * 100)}%` } })) : null;
    return h('button', { class: 'card-item', onclick: () => this.open({ kind: 'video', video: v }) },
      h('div', { class: 'poster-wrap' }, img, dur ? h('span', { class: 'dur' }, dur) : null, prog),
      h('div', { class: 't1' }, v.title), h('div', { class: 't2' }, [v.channel, ytAgo(v.published)].filter(Boolean).join(' · ')));
  },

  async renderVideo(body, v) {
    api('/api/yt/prepare', { id: v.id }).catch(() => {});   // look up the streams now: Play then starts at once
    const hist = await api('/api/yt/history').catch(() => []);
    const seen = hist.find((x) => x.id === v.id);
    const canResume = seen && seen.duration && seen.position > 30 && seen.position < 0.95 * seen.duration;
    const play = async (resume) => {
      starting.show(v.title, v.thumb.replace('hqdefault', 'maxresdefault'), v.thumb);
      try { await api('/api/yt/play', { ...v, resume }); starting.untilPlaying(); plexv.watchPlayer(); }
      catch (err) { starting.hide(); toast(err.message); }
    };
    const thumb = h('div', { class: 'yt-hero' });
    thumb.style.backgroundImage = `url("${v.thumb.replace('hqdefault', 'maxresdefault')}"), url("${v.thumb}")`;
    const meta = [v.duration ? fmtTime(v.duration) : null, v.views ? `${Number(v.views).toLocaleString('en-US')} views` : null, ytAgo(v.published)].filter(Boolean).join(' · ');
    body.replaceChildren(h('div', { class: 'detail' }, thumb,
      h('div', { class: 'detail-info' },
        h('div', { class: 'eyebrow' }, v.channel || 'YouTube'),
        h('h2', { style: { fontSize: '56px' } }, v.title),
        meta ? h('div', { class: 'detail-meta' }, meta) : null,
        h('div', { class: 'detail-actions' },
          canResume ? h('button', { class: 'primary', id: 'yt-resume', onclick: () => play(true) }, `Resume from ${fmtTime(seen.position)}`) : null,
          h('button', { class: canResume ? 'pill' : 'primary', id: 'yt-play', style: canResume ? { height: '80px' } : null, onclick: () => play(false) }, canResume ? 'Play from start' : 'Play'),
          v.channel_id ? this.channelButton(v.channel_id) : null))));
    setTimeout(() => { const b = $('#yt-resume') || $('#yt-play'); if (b) b.focus(); }, 60);
    // the channel and a Subscribe button (signed in: the account's subscription)
    const owner = await api(`/api/yt/owner?id=${encodeURIComponent(v.id)}`).catch(() => null);
    const actions = body.querySelector('.detail-actions');
    if (!owner || !owner.channel_id || !actions || !actions.isConnected) return;
    if (!v.channel_id) { v.channel_id = owner.channel_id; actions.append(this.channelButton(owner.channel_id)); }
    actions.append(this.subscribeButton({ id: owner.channel_id, name: v.channel, subscribed: owner.subscribed }));
  },

  channelButton(id) {
    return h('button', { class: 'pill', style: { height: '80px' }, onclick: () => this.open({ kind: 'channel', id }) }, 'Channel');
  },

  // c: { id, name, avatar, subscribed }; flips the subscription (the account's when signed in)
  subscribeButton(c) {
    const label = () => (c.subscribed ? 'Subscribed ✓' : 'Subscribe');
    const btn = h('button', { class: c.subscribed ? 'pill' : 'primary', style: { height: '80px' }, onclick: async () => {
      try {
        const r = await api('/api/yt/subscribe', { id: c.id, name: c.name, avatar: c.avatar, subscribe: !c.subscribed });
        c.subscribed = r.subscribed;
        btn.className = c.subscribed ? 'pill' : 'primary';
        btn.textContent = label();
        toast(c.subscribed ? `Subscribed to ${c.name || 'the channel'}` : `Unsubscribed from ${c.name || 'the channel'}`);
      } catch (err) { toast(err.message); }
    } }, label());
    return btn;
  },

  async renderChannel(body, id) {
    body.replaceChildren(h('div', { class: 'lib-tabs', style: { gap: '24px' } }, h('div', { class: 'yt-avatar skel' }), h('div', { class: 'skel skel-line', style: { width: '320px', height: '44px' } })),
      h('div', { class: 'grid videos' }, ...skeletonCards(8)));
    let c;
    try { c = await api(`/api/yt/channel?id=${encodeURIComponent(id)}`); } catch (err) { body.replaceChildren(h('div', { class: 'empty' }, err.message)); return; }
    const sub = this.subscribeButton(c);
    const avatar = h('div', { class: 'yt-avatar' });
    if (c.avatar) avatar.style.backgroundImage = `url("${c.avatar}")`;
    const grid = h('div', { class: 'grid videos' });
    body.replaceChildren(h('div', { class: 'lib-tabs', style: { gap: '24px' } }, avatar, h('h2', { style: { fontSize: '44px', fontWeight: 600 } }, c.name), sub), grid);
    this.fillVideos(grid, c.videos);
  },
};

function ytAgo(ts) {
  if (!ts) return '';
  const d = (Date.now() / 1000 - ts) / 86400;
  if (d < 1) return 'today';
  if (d < 2) return 'yesterday';
  if (d < 30) return `${Math.floor(d)} days ago`;
  if (d < 365) return `${Math.floor(d / 30)} months ago`;
  return `${Math.floor(d / 365)} years ago`;
}

function focusIn(sel) {
  const el = $(`${sel} .card-item`) || $(`${sel} .primary`) || $(`${sel} button`);
  if (el) el.focus();
}

/* ==================================================================== ambient wallpaper */

// Three soft blobs of the theme's ambient colours drifting slowly (as the old blurred CSS blobs did), drawn into a
// 160 x 90 canvas ten times a second; the browser stretches it smoothly to the screen.
const ambient = {
  start() {
    const c = $('#wallpaper canvas.ambient');
    if (!c) return;
    const ctx = c.getContext('2d');
    const W = c.width, H = c.height, vw = W / 100, vh = H / 100;
    const blobs = [   // centre, drift, scale at the far end, period (s)
      { v: '--amb-1', x: 15 * vw, y: 5 * vw, dx: 18 * vw, dy: 14 * vh, s: 1.15, p: 48 },
      { v: '--amb-2', x: 90 * vw, y: 10 * vh + 35 * vw, dx: -16 * vw, dy: 20 * vh, s: 0.9, p: 62 },
      { v: '--amb-3', x: 55 * vw, y: H + 10 * vw, dx: 12 * vw, dy: -18 * vh, s: 1.1, p: 55 },
    ];
    const rgba = (css, a) => {
      ctx.fillStyle = '#000';
      ctx.fillStyle = css || '#000';
      const f = ctx.fillStyle;
      if (f[0] === '#') { const n = parseInt(f.slice(1), 16); return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`; }
      const m = f.match(/[\d.]+/g);
      return `rgba(${m[0]},${m[1]},${m[2]},${a * (m[3] === undefined ? 1 : Number(m[3]))})`;
    };
    const draw = () => {
      const off = document.hidden || document.body.classList.contains('busy') || document.body.dataset.wallpaper === 'none';
      if (!off) {
        const t = performance.now() / 1000;
        const css = getComputedStyle(document.body);
        ctx.clearRect(0, 0, W, H);
        for (const b of blobs) {
          const ph = (t / b.p) % 2, x = ph < 1 ? ph : 2 - ph, e = (1 - Math.cos(Math.PI * x)) / 2;   // ease in-out, back and forth
          const cx = b.x + b.dx * e, cy = b.y + b.dy * e, r = 44 * vw * (1 + (b.s - 1) * e);
          const col = css.getPropertyValue(b.v).trim();
          const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, r);
          g.addColorStop(0, rgba(col, 0.55));
          g.addColorStop(0.5, rgba(col, 0.4));
          g.addColorStop(1, rgba(col, 0));
          ctx.fillStyle = g;
          ctx.fillRect(0, 0, W, H);
        }
      }
      setTimeout(draw, off ? 1000 : 100);
    };
    draw();
  },
};

/* ==================================================================== volume */

// The backend changes the volume when a remote's volume keys are pressed; show it briefly.
let volumeSeen = 0, osdTimer;
async function pollVolume() {
  let v;
  try { v = await api('/api/volume'); } catch { return; }
  if (!v.changed || v.changed <= volumeSeen) return;
  const first = volumeSeen === 0;
  volumeSeen = v.changed;
  if (first && Date.now() / 1000 - v.changed > 3) return;
  const osd = $('#volume-osd');
  const pct = v.volume == null ? 0 : Math.round(v.volume * 100);
  $('#volume-osd i').style.width = v.muted ? '0%' : `${pct}%`;
  $('#volume-osd span').textContent = v.muted ? 'Muted' : `${pct}%`;
  osd.classList.add('show');
  clearTimeout(osdTimer);
  osdTimer = setTimeout(() => osd.classList.remove('show'), 1800);
}

// Home and media keys from the remote, read by the backend (the browser keeps them to itself).
let eventSeq = null;
const REMOTE = {
  home: () => goHome(),
  // a video or game has the screen: stop the wallpaper, ticker and visualizer drawing behind it
  busy: () => document.body.classList.add('busy'),
  idle: () => document.body.classList.remove('busy'),
  // a video closed by itself without playing (or with an error): say why, long enough to read
  'player-error': (ev) => { starting.hide(); toast(ev.message, 12000); },
  'up-next': (ev) => upNext.show(ev.data),
  // Media keys work the music player in the Music app. Elsewhere they only pause music playing in the background:
  // a paused song never starts again from YouTube or Plex.
  playpause: () => { if (musicKeys()) music.toggle(); else if (music.isPlaying()) audio.pause(); },
  play: () => { if (musicKeys() && music.index >= 0 && audio.paused) music.toggle(); },
  pause: () => { if (music.isPlaying()) audio.pause(); },
  stop: () => { if (music.isPlaying()) audio.pause(); },
  next: () => { if (musicKeys()) music.next(); },
  previous: () => { if (musicKeys()) music.prev(); },
  forward: () => { if (musicKeys()) music.seek(10); },
  rewind: () => { if (musicKeys()) music.seek(-10); },
};
function musicKeys() { return state.view === 'music' && !document.body.classList.contains('busy'); }
async function pollEvents() {
  let r;
  try { r = await api(`/api/events?since=${eventSeq ?? 0}`); } catch { return; }
  if (eventSeq === null) { eventSeq = r.seq; return; }   // (presses from before this page loaded)
  for (const ev of r.events) if (REMOTE[ev.name]) REMOTE[ev.name](ev);
  eventSeq = r.seq;
}

/* ==================================================================== start */

async function start() {
  try {
    state.settings = await api('/api/settings');
    const sess = await api('/api/session');
    state.hostname = sess.hostname;
  } catch {
    state.settings = { setup_done: true, theme: 'midnight', wallpaper: 'ambient', ticker: true, display: { edges: 0 }, weather: {} };
  }
  applyAppearance();
  tickClock();
  setInterval(tickClock, 1000);
  ambient.start();
  if (state.settings.setup_done) show('home');
  else { show('setup'); setup.go(0); }
  refreshWeather();
  refreshNetworkChip();
  refreshNews();
  refreshCast();
  api('/api/plex/status').then((p) => {
    if (p.server) {
      $('#tile-plex-sub').textContent = `Movies and shows on ${p.server}`;
      music.status = p;
      if (!music.isPlaying()) $('#tile-music-sub').textContent = `Your music on ${p.server}, with visualizers`;
    }
  }).catch(() => {});
  setInterval(refreshWeather, 10 * 60 * 1000);
  setInterval(refreshNews, 15 * 60 * 1000);
  setInterval(refreshNetworkChip, 30 * 1000);
  setInterval(refreshCast, 60 * 1000);
  setInterval(() => { if (!document.hidden) pollVolume(); }, 700);
  setInterval(() => { if (!document.hidden) pollEvents(); }, 400);
  viz.frame();
}

start();
