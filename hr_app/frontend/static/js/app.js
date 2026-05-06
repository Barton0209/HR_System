/* ═══════════════════════════════════════════════════════
   HR System — Core App
   ═══════════════════════════════════════════════════════ */
const API = '/api';

// ── Global state ───────────────────────────────────────
const State = {
  mode: 'ALL',
  platform: 'ALL',
  citizenship: 'ALL',
  status: 'ALL',
  org: 'ALL',
  search: '',
  currentTab: 'dashboard',
};

// ── Toast ──────────────────────────────────────────────
const Toast = {
  show(msg, type = 'info', duration = 3500) {
    const icons = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' };
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    // Экранируем сообщение для предотвращения XSS
    const escapeHtml = (text) => {
      const div = document.createElement('div');
      div.textContent = text;
      return div.innerHTML;
    };
    el.innerHTML = `<span class="t-icon">${icons[type]}</span>
      <span class="t-msg">${escapeHtml(String(msg))}</span>
      <span class="t-close" onclick="this.parentElement.remove()">✕</span>`;
    document.getElementById('toast-container').appendChild(el);
    setTimeout(() => el.remove(), duration);
  }
};

// ── API helper ─────────────────────────────────────────
async function api(endpoint, options = {}) {
  try {
    const resp = await fetch(API + endpoint, options);
    if (!resp.ok) {
      const err = await resp.text();
      throw new Error(`HTTP ${resp.status}: ${err}`);
    }
    return await resp.json();
  } catch (e) {
    console.error('API error:', endpoint, e);
    throw e;
  }
}

async function apiDownload(endpoint) {
  const resp = await fetch(API + endpoint);
  if (!resp.ok) throw new Error('Download failed');
  const blob = await resp.blob();
  const cd = resp.headers.get('content-disposition') || '';
  const m = cd.match(/filename="?([^"]+)"?/);
  const fn = m ? m[1] : 'export.xlsx';
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = fn;
  a.click();
  URL.revokeObjectURL(url);
}

async function apiUpload(endpoint, formData) {
  const resp = await fetch(API + endpoint, { method: 'POST', body: formData });
  if (!resp.ok) throw new Error(await resp.text());
  return await resp.json();
}

// ── Navigation ─────────────────────────────────────────
const App = {
  init() {
    // Nav clicks
    document.querySelectorAll('.nav-item').forEach(el => {
      el.addEventListener('click', () => {
        const tab = el.dataset.tab;
        if (tab) this.switchTab(tab);
      });
    });

    // Mode tabs
    document.querySelectorAll('.mode-tab').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.mode-tab').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        State.mode = btn.dataset.mode;
        this.applyFilters();
      });
    });

    // Search enter
    document.getElementById('global-search')?.addEventListener('keydown', e => {
      if (e.key === 'Enter') this.applyFilters();
    });

    this.loadFilters();
    this.switchTab('dashboard');
  },

  switchTab(tab) {
    State.currentTab = tab;
    document.querySelectorAll('.tab-page').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));

    const page = document.getElementById(`tab-${tab}`);
    if (page) page.classList.add('active');

    const navEl = document.querySelector(`[data-tab="${tab}"]`);
    if (navEl) navEl.classList.add('active');

    const titles = {
      'dashboard': '📊 Дашборд',
      'employees': '👥 Сотрудники',
      'reports': '📈 Отчёты',
      'daily-tracking': '📅 Ежедневный учёт',
      'carnet': '🪪 Карнет',
      'tickets-buy': '✈️ Покупка билетов',
      'tickets-costs': '💰 Затраты на билеты',
      'eval-rop': '⭐ Оценки РОП',
      'eval-itr': '🎯 Оценки ИТР',
      'ocr-passport': '🛂 Паспорт OCR',
      'ocr-docs': '🔍 Документы OCR',
      'utilities': '🔧 Утилиты',
      'settings': '⚙️ Настройки',
    };
    document.getElementById('page-title').textContent = titles[tab] || tab;

    // Trigger tab-specific load
    switch(tab) {
      case 'dashboard': Dashboard.load(); break;
      case 'employees': Employees.load(); break;
      case 'reports': Reports.load(); break;
      case 'daily-tracking': DailyTracking.init(); break;
      case 'tickets-buy': Tickets.load(); break;
      case 'tickets-costs': TicketCosts.load(); break;
      case 'carnet': Carnet.init(); break;
      case 'utilities': buildUtilitiesTab(); break;
      case 'settings': Settings.load(); break;
    }
  },

  applyFilters() {
    State.platform = document.getElementById('f-platform')?.value || 'ALL';
    State.citizenship = document.getElementById('f-citizenship')?.value || 'ALL';
    State.status = document.getElementById('f-status')?.value || 'ALL';
    State.org = document.getElementById('f-org')?.value || 'ALL';
    State.search = document.getElementById('global-search')?.value || '';

    // Reload current tab
    switch(State.currentTab) {
      case 'dashboard': Dashboard.load(); break;
      case 'employees': Employees.load(); break;
      case 'reports': Reports.load(); break;
    }
  },

  resetFilters() {
    State.mode = 'ALL';
    State.platform = State.citizenship = State.status = State.org = 'ALL';
    State.search = '';
    document.getElementById('f-platform').value = 'ALL';
    document.getElementById('f-citizenship').value = 'ALL';
    document.getElementById('f-status').value = 'ALL';
    document.getElementById('f-org').value = 'ALL';
    document.getElementById('global-search').value = '';
    document.querySelectorAll('.mode-tab').forEach((b, i) => b.classList.toggle('active', i === 0));
    this.applyFilters();
  },

  async loadFilters() {
    try {
      const data = await api('/dashboard/filters');
      this._populate('f-platform', data.platforms, 'Все площадки');
      this._populate('f-citizenship', data.citizenships, 'Все гражданства');
      this._populate('f-status', data.statuses, 'Все статусы');
      this._populate('f-org', data.orgs, 'Все организации');
    } catch(e) {
      console.warn('Filter load failed:', e);
    }
  },

  _populate(elId, options, allLabel) {
    const sel = document.getElementById(elId);
    if (!sel) return;
    const cur = sel.value;
    // Экранируем HTML для предотвращения XSS
    const escapeHtml = (text) => {
      const div = document.createElement('div');
      div.textContent = text;
      return div.innerHTML;
    };
    sel.innerHTML = `<option value="ALL">${escapeHtml(allLabel)}</option>` +
      options.filter(o => o !== 'ALL').map(o =>
        `<option value="${escapeHtml(String(o))}">${escapeHtml(String(o))}</option>`
      ).join('');
    if (cur && cur !== 'ALL') sel.value = cur;
  },

  updateHeaderStats(counts) {
    if (!counts) return;
    const fmt = n => n?.toLocaleString('ru-RU') ?? '—';
    document.getElementById('hdr-total').textContent = fmt(counts.total);
    document.getElementById('hdr-active').textContent = fmt(counts.active_op);
    document.getElementById('hdr-itr').textContent = fmt(counts.itr);
    document.getElementById('hdr-foreign').textContent = fmt(counts.foreign);
  }
};

// ── Chart helpers ──────────────────────────────────────
const Charts = {
  instances: {},

  PALETTE_PIE: [
    '#58a6ff','#3fb950','#d29922','#f85149','#bc8cff','#39d353',
    '#79c0ff','#56d364','#e3b341','#ff7b72','#d2a8ff','#52e0a7',
    '#2ea043','#1f6feb','#388bfd','#bf4b8a','#ff9b54','#8b1538',
  ],

  PALETTE_BAR: '#58a6ff',

  destroy(id) {
    if (this.instances[id]) {
      this.instances[id].destroy();
      delete this.instances[id];
    }
  },

  pie(canvasId, data, title = '') {
    this.destroy(canvasId);
    const ctx = document.getElementById(canvasId)?.getContext('2d');
    if (!ctx || !data.length) return;
    this.instances[canvasId] = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: data.map(d => d.label),
        datasets: [{
          data: data.map(d => d.value),
          backgroundColor: this.PALETTE_PIE,
          borderWidth: 0,
          hoverOffset: 4,
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: true,
        plugins: {
          legend: {
            position: 'right',
            labels: { color: '#8b949e', font: { size: 11 }, padding: 8, boxWidth: 12 }
          },
          tooltip: {
            callbacks: {
              label: ctx => ` ${ctx.label}: ${ctx.parsed.toLocaleString('ru-RU')}`
            }
          }
        }
      }
    });
  },

  bar(canvasId, data, {horizontal = false, color = null, stacked = false} = {}) {
    this.destroy(canvasId);
    const ctx = document.getElementById(canvasId)?.getContext('2d');
    if (!ctx || !data.length) return;
    const colors = Array.isArray(color) ? color : (color ? data.map(() => color) : this.PALETTE_PIE);
    this.instances[canvasId] = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: data.map(d => d.label),
        datasets: [{
          data: data.map(d => d.value),
          backgroundColor: colors,
          borderRadius: 4,
          borderWidth: 0,
        }]
      },
      options: {
        indexAxis: horizontal ? 'y' : 'x',
        responsive: true, maintainAspectRatio: true,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: ctx => ` ${ctx.parsed[horizontal?'x':'y'].toLocaleString('ru-RU')}`
            }
          }
        },
        scales: {
          x: { grid: { color: '#30363d' }, ticks: { color: '#8b949e', font: { size: 10 } } },
          y: { grid: { color: '#30363d' }, ticks: { color: '#8b949e', font: { size: 10 } } },
          stacked,
        }
      }
    });
  },

  line(canvasId, datasets, labels) {
    this.destroy(canvasId);
    const ctx = document.getElementById(canvasId)?.getContext('2d');
    if (!ctx) return;
    this.instances[canvasId] = new Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: datasets.map((ds, i) => ({
          label: ds.label,
          data: ds.data,
          borderColor: [this.PALETTE_PIE[0], this.PALETTE_PIE[3]][i] || this.PALETTE_PIE[i],
          backgroundColor: 'transparent',
          tension: 0.3,
          pointRadius: 2,
          borderWidth: 2,
        }))
      },
      options: {
        responsive: true, maintainAspectRatio: true,
        plugins: {
          legend: { labels: { color: '#8b949e', font: { size: 11 } } }
        },
        scales: {
          x: { grid: { color: '#30363d' }, ticks: { color: '#8b949e', font: { size: 10 }, maxTicksLimit: 12 } },
          y: { grid: { color: '#30363d' }, ticks: { color: '#8b949e', font: { size: 10 } } }
        }
      }
    });
  }
};

// ── Table helper ───────────────────────────────────────
function renderTable(tbodyId, rows, colKeys, renderers = {}) {
  const tbody = document.getElementById(tbodyId);
  if (!tbody) return;
  if (!rows || !rows.length) {
    tbody.innerHTML = `<tr><td colspan="${colKeys.length}" style="text-align:center;padding:30px;color:var(--text-muted)">Нет данных</td></tr>`;
    return;
  }
  tbody.innerHTML = rows.map((row, i) =>
    `<tr>${colKeys.map(k => {
      const val = row[k] ?? '';
      const r = renderers[k];
      return `<td>${r ? r(val, row) : escHtml(String(val))}</td>`;
    }).join('')}</tr>`
  ).join('');
}

function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function fmtNum(n) {
  return Number(n)?.toLocaleString('ru-RU') ?? '—';
}

function statusBadge(val) {
  if (!val) return '<span class="badge badge-gray">—</span>';
  const v = val.toLowerCase();
  if (v.includes('работ') || v.includes('актив')) return `<span class="badge badge-green">${escHtml(val)}</span>`;
  if (v.includes('уволь') || v.includes('увол')) return `<span class="badge badge-red">${escHtml(val)}</span>`;
  if (v.includes('отпуск') || v.includes('вахт')) return `<span class="badge badge-orange">${escHtml(val)}</span>`;
  return `<span class="badge badge-gray">${escHtml(val)}</span>`;
}

function citizenBadge(val) {
  if (!val) return '—';
  const v = val.toUpperCase();
  if (v === 'РОССИЯ' || v === 'РФ') return `<span class="badge badge-blue">${escHtml(val)}</span>`;
  return `<span class="badge badge-orange">${escHtml(val)}</span>`;
}

// ── Upload helpers ─────────────────────────────────────
function setupDragDrop(zone, inputId) {
  const el = document.getElementById(zone);
  const inp = document.getElementById(inputId);
  if (!el) return;
  el.addEventListener('dragover', e => { e.preventDefault(); el.classList.add('drag-over'); });
  el.addEventListener('dragleave', () => el.classList.remove('drag-over'));
  el.addEventListener('drop', e => {
    e.preventDefault();
    el.classList.remove('drag-over');
    if (inp && e.dataTransfer.files.length) {
      inp.files = e.dataTransfer.files;
      inp.dispatchEvent(new Event('change'));
    }
  });
}

function showLoading(elId, show = true) {
  const el = document.getElementById(elId);
  if (el) el.style.display = show ? 'flex' : 'none';
}

// ── Init ──────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  App.init();
  setupDragDrop('eju-drop-zone', 'eju-files-input');
  setupDragDrop('base-drop', 'base-input');
  setupDragDrop('ocr-drop-zone', 'ocr-input');
});
