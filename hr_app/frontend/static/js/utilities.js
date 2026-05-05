/* ═══════════════════════════════════════════════════════════════════════
   Utilities Module — HR System
   Транслит (23 страны), Парсер билетов PDF, Переименование, Стаж
   ═══════════════════════════════════════════════════════════════════════ */

/* ─── Client-side transliteration maps (mirrors backend) ─── */
const TRANSLIT_MAPS = {
  CIS: {
    'А':'A','Б':'B','В':'V','Г':'G','Д':'D','Е':'E','Ё':'Yo',
    'Ж':'Zh','З':'Z','И':'I','Й':'Y','К':'K','Л':'L','М':'M',
    'Н':'N','О':'O','П':'P','Р':'R','С':'S','Т':'T','У':'U',
    'Ф':'F','Х':'Kh','Ц':'Ts','Ч':'Ch','Ш':'Sh','Щ':'Shch',
    'Ъ':'','Ы':'Y','Ь':'','Э':'E','Ю':'Yu','Я':'Ya',
    'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'yo',
    'ж':'zh','з':'z','и':'i','й':'y','к':'k','л':'l','м':'m',
    'н':'n','о':'o','п':'p','р':'r','с':'s','т':'t','у':'u',
    'ф':'f','х':'kh','ц':'ts','ч':'ch','ш':'sh','щ':'shch',
    'ъ':'','ы':'y','ь':'','э':'e','ю':'yu','я':'ya',
  },
  BELARUS: {
    'А':'A','Б':'B','В':'V','Г':'H','Д':'D','Е':'E','Ё':'Yo',
    'Ж':'Zh','З':'Z','І':'I','Й':'J','К':'K','Л':'L','М':'M',
    'Н':'N','О':'O','П':'P','Р':'R','С':'S','Т':'T','У':'U',
    'Ў':'U','Ф':'F','Х':'Kh','Ц':'Ts','Ч':'C','Ш':'S','Щ':'S',
    'Ь':'','Ы':'Y','Э':'E','Ю':'Ju','Я':'Ja','И':'I',
    'а':'a','б':'b','в':'v','г':'h','д':'d','е':'e','ё':'yo',
    'ж':'zh','з':'z','і':'i','й':'j','к':'k','л':'l','м':'m',
    'н':'n','о':'o','п':'p','р':'r','с':'s','т':'t','у':'u',
    'ў':'u','ф':'f','х':'kh','ц':'ts','ч':'c','ш':'s','щ':'s',
    'ь':'','ы':'y','э':'e','ю':'ju','я':'ja','и':'i',
  },
  SERBIAN: {
    'А':'A','Б':'B','В':'V','Г':'G','Д':'D','Е':'E','Ё':'E',
    'Ж':'Z','З':'Z','И':'I','Й':'J','К':'K','Л':'L','М':'M',
    'Н':'N','О':'O','П':'P','Р':'R','С':'S','Т':'T','У':'U',
    'Ф':'F','Х':'H','Ц':'C','Ч':'C','Ш':'S','Щ':'S',
    'Ъ':'','Ы':'Y','Ь':'','Э':'E','Ю':'Ju','Я':'Ja',
    'а':'a','б':'b','в':'v','г':'h','д':'d','е':'e','ё':'e',
    'ж':'z','з':'z','и':'i','й':'j','к':'k','л':'l','м':'m',
    'н':'n','о':'o','п':'p','р':'r','с':'s','т':'t','у':'u',
    'ф':'f','х':'h','ц':'c','ч':'c','ш':'s','щ':'s',
    'ъ':'','ы':'y','ь':'','э':'e','ю':'ju','я':'ja',
  },
  BOSNIAN: {
    'А':'A','Б':'B','В':'V','Г':'G','Д':'D','Е':'E','Ж':'Zh',
    'З':'Z','И':'I','К':'K','Л':'L','М':'M','Н':'N','О':'O',
    'П':'P','Р':'R','С':'S','Т':'T','У':'U','Ф':'F','Х':'H',
    'Ц':'C','Ч':'Cs','Ш':'S','Ё':'E','Й':'J','Ы':'Y','Ь':'',
    'Ъ':'','Э':'E','Ю':'Yu','Я':'Ya',
    'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ж':'zh',
    'з':'z','и':'i','к':'k','л':'l','м':'m','н':'n','о':'o',
    'п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f','х':'h',
    'ц':'c','ч':'cs','ш':'s','ё':'e','й':'j','ы':'y','ь':'',
    'ъ':'','э':'e','ю':'yu','я':'ya',
  },
  AZERBAIJAN: {
    'А':'A','а':'a','Б':'B','б':'b','В':'V','в':'v','Г':'G','г':'g',
    'Д':'D','д':'d','Е':'E','е':'e','Ё':'Yo','ё':'yo','Ж':'J','ж':'j',
    'З':'Z','з':'z','И':'I','и':'i','Й':'Y','й':'y','К':'K','к':'k',
    'Л':'L','л':'l','М':'M','м':'m','Н':'N','н':'n','О':'O','о':'o',
    'П':'P','п':'p','Р':'R','р':'r','С':'S','с':'s','Т':'T','т':'t',
    'У':'U','у':'u','Ф':'F','ф':'f','Х':'X','х':'x','Ц':'Ts','ц':'ts',
    'Ч':'Ch','ч':'ch','Ш':'Sh','ш':'sh','Щ':'Shch','щ':'shch',
    'Ы':'I','ы':'i','Ь':'','ь':'','Э':'E','э':'e','Ю':'Yu','ю':'yu',
    'Я':'Ya','я':'ya','Ъ':'','ъ':'',
  },
  UKRAINE: {
    'А':'A','Б':'B','В':'V','Г':'H','Ґ':'G','Д':'D','Е':'E','Є':'Ye',
    'Ж':'Zh','З':'Z','И':'Y','І':'I','Ї':'Yi','Й':'Y','К':'K','Л':'L',
    'М':'M','Н':'N','О':'O','П':'P','Р':'R','С':'S','Т':'T','У':'U',
    'Ф':'F','Х':'Kh','Ц':'Ts','Ч':'Ch','Ш':'Sh','Щ':'Shch','Ю':'Yu','Я':'Ya',
    'Ы':'Y','Э':'E','Ь':'','Ъ':'',
    'а':'a','б':'b','в':'v','г':'h','ґ':'g','д':'d','е':'e','є':'ye',
    'ж':'zh','з':'z','и':'y','і':'i','ї':'yi','й':'y','к':'k','л':'l',
    'м':'m','н':'n','о':'o','п':'p','р':'r','с':'s','т':'t','у':'u',
    'ф':'f','х':'kh','ц':'ts','ч':'ch','ш':'sh','щ':'shch','ю':'yu','я':'ya',
    'ы':'y','э':'e','ь':'','ъ':'',
  },
  MACEDONIA: {
    'А':'A','Б':'B','В':'V','Г':'G','Д':'D','Е':'E','Ж':'Zh',
    'З':'Z','И':'I','К':'K','Л':'L','М':'M','Н':'N','О':'O',
    'П':'P','Р':'R','С':'S','Т':'T','У':'U','Ф':'F','Х':'H',
    'Ц':'C','Ч':'Ch','Ш':'Sh','Ё':'E','Й':'Y','Ы':'Y','Ь':'',
    'Ъ':'','Э':'E','Ю':'Yu','Я':'Ya',
    'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ж':'zh',
    'з':'z','и':'i','к':'k','л':'l','м':'m','н':'n','о':'o',
    'п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f','х':'h',
    'ц':'c','ч':'ch','ш':'sh','ё':'e','й':'y','ы':'y','ь':'',
    'ъ':'','э':'e','ю':'yu','я':'ya',
  },
};

const COUNTRY_MAP_KEY = {
  'Азербайджан':'AZERBAIJAN','Azerbaijan':'AZERBAIJAN',
  'Армения':'CIS','Armenia':'CIS',
  'Беларусь':'BELARUS','Belarus':'BELARUS',
  'Босния':'BOSNIAN','Bosnia':'BOSNIAN',
  'Герцеговина':'BOSNIAN',
  'Хорватия':'BOSNIAN','Croatia':'BOSNIAN',
  'Черногория':'BOSNIAN','Montenegro':'BOSNIAN',
  'Казахстан':'CIS','Kazakhstan':'CIS',
  'Киргизия':'CIS','Kyrgyzstan':'CIS',
  'Молдова':'CIS','Moldova':'CIS',
  'Россия':'CIS','Russia':'CIS','РФ':'CIS','РОССИЯ':'CIS',
  'Российская Федерация':'CIS',
  'Северная Корея':'CIS','North Korea':'CIS',
  'Северная Македония':'MACEDONIA','North Macedonia':'MACEDONIA',
  'Сербия':'SERBIAN','Serbia':'SERBIAN',
  'Сирия':'CIS','Syria':'CIS',
  'Таджикистан':'CIS','Tajikistan':'CIS',
  'Туркмения':'CIS','Turkmenistan':'CIS',
  'Турция':'CIS','Turkey':'CIS',
  'Узбекистан':'CIS','Uzbekistan':'CIS',
  'Украина':'UKRAINE','Ukraine':'UKRAINE',
  'Гана':'CIS','Ghana':'CIS',
  'Индия':'CIS','India':'CIS',
  'Китай':'CIS','China':'CIS',
  'Пакистан':'CIS','Pakistan':'CIS',
};

function getTranslitMap(citizenship) {
  const key = COUNTRY_MAP_KEY[citizenship?.trim()] || 'CIS';
  return TRANSLIT_MAPS[key] || TRANSLIT_MAPS.CIS;
}

function transliterateWord(text, map, uppercase) {
  let res = '';
  for (const ch of text) {
    if (map[ch] !== undefined) res += map[ch];
    else if (/[A-Za-z0-9\s\-.]/.test(ch)) res += ch;
  }
  if (uppercase) return res.toUpperCase();
  return res.replace(/\b\w/g, c => c.toUpperCase());
}

/* ─── All supported countries for dropdown ─── */
const ALL_COUNTRIES = [
  'Азербайджан','Армения','Беларусь','Босния и Герцеговина',
  'Гана','Индия','Казахстан','Киргизия','Китай','Молдова',
  'Пакистан','Россия','Северная Корея','Северная Македония',
  'Сербия','Сирия','Таджикистан','Туркмения','Турция',
  'Узбекистан','Украина','Хорватия','Черногория',
];

/* ═══════════════════════════════════════════════════════════════════════
   TRANSLIT MODULE
   ═══════════════════════════════════════════════════════════════════════ */
const TranslitModule = {
  rows: [],   // [{citizenship, fio, result}]
  uppercase: true,

  init() {
    this.rows = Array.from({length: 20}, () => ({citizenship:'Россия', fio:'', result:''}));
    this.render();
  },

  addRows(n = 10) {
    for (let i = 0; i < n; i++)
      this.rows.push({citizenship:'Россия', fio:'', result:''});
    this.render();
  },

  render() {
    const tbody = document.getElementById('translit-tbody');
    if (!tbody) return;

    const countryOpts = ALL_COUNTRIES.map(c =>
      `<option value="${c}">${c}</option>`).join('');

    tbody.innerHTML = this.rows.map((row, i) => `
      <tr>
        <td style="padding:2px 4px;color:var(--text-muted);font-size:11px;text-align:center">${i+1}</td>
        <td style="padding:2px 4px">
          <select class="form-control" style="width:100%;font-size:11px;padding:2px 4px"
            onchange="TranslitModule.setCell(${i},'citizenship',this.value)">
            ${ALL_COUNTRIES.map(c => `<option value="${c}" ${c===row.citizenship?'selected':''}>${c}</option>`).join('')}
          </select>
        </td>
        <td style="padding:2px 4px">
          <input class="form-control" style="width:100%;font-size:11px;padding:2px 4px"
            value="${escHtml(row.fio)}" placeholder="Фамилия Имя Отчество"
            oninput="TranslitModule.setCell(${i},'fio',this.value)">
        </td>
        <td style="padding:2px 4px">
          <input class="form-control" style="width:100%;font-size:11px;padding:2px 4px;background:var(--bg-tertiary);color:var(--accent-green)"
            value="${escHtml(row.result)}" readonly
            onclick="this.select()">
        </td>
      </tr>`).join('');
  },

  setCell(i, field, value) {
    this.rows[i][field] = value;
  },

  transliterateAll() {
    let processed = 0;
    this.rows.forEach((row, i) => {
      if (!row.fio.trim()) { row.result = ''; return; }
      const map = getTranslitMap(row.citizenship);
      row.result = transliterateWord(row.fio.trim(), map, this.uppercase);
      processed++;
    });
    this.render();
    Toast.show(`Транслитерировано ${processed} записей`, 'success', 2000);
  },

  clearAll() {
    this.rows.forEach(r => { r.fio = ''; r.result = ''; });
    this.render();
  },

  copyResults() {
    const txt = this.rows.filter(r => r.result).map(r => r.result).join('\n');
    if (!txt) return Toast.show('Нет результатов', 'warning');
    navigator.clipboard.writeText(txt);
    Toast.show('Скопировано в буфер', 'success', 1500);
  },

  async exportExcel() {
    const rows = this.rows.filter(r => r.fio || r.result).map(r =>
      [r.citizenship, r.fio, r.result]);
    if (!rows.length) return Toast.show('Нет данных для экспорта', 'warning');
    try {
      const resp = await apiPost('/api/utilities/translit/export', {rows});
      if (!resp.ok) throw new Error('Ошибка экспорта');
      const blob = await resp.blob();
      downloadBlob(blob, 'translit_result.xlsx');
      Toast.show('Excel сохранён', 'success');
    } catch(e) {
      Toast.show('Ошибка экспорта: ' + e.message, 'error');
    }
  },

  pasteFromClipboard() {
    navigator.clipboard.readText().then(text => {
      if (!text) return;
      const lines = text.split('\n').filter(l => l.trim());
      lines.forEach((line, i) => {
        const parts = line.split('\t');
        if (i >= this.rows.length) this.rows.push({citizenship:'Россия', fio:'', result:''});
        if (parts.length >= 2) {
          this.rows[i].citizenship = parts[0].trim() || 'Россия';
          this.rows[i].fio = parts[1].trim();
        } else {
          this.rows[i].fio = parts[0].trim();
        }
      });
      this.render();
      Toast.show(`Вставлено ${lines.length} строк`, 'success', 2000);
    }).catch(() => Toast.show('Нет доступа к буферу обмена', 'warning'));
  },
};

/* ═══════════════════════════════════════════════════════════════════════
   TICKET PARSER MODULE
   ═══════════════════════════════════════════════════════════════════════ */
const TicketParserModule = {
  tickets: [],

  async parseFiles(files) {
    if (!files?.length) return;
    const fd = new FormData();
    for (const f of files) fd.append('files', f);

    const statusEl = document.getElementById('ticket-status');
    if (statusEl) statusEl.textContent = `Обработка ${files.length} файлов...`;

    Toast.show(`Загрузка ${files.length} PDF...`, 'info', 2000);

    try {
      const resp = await fetch('/api/utilities/parse-tickets-pdf', {method:'POST', body:fd});
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      this.tickets = data.results.filter(r => r.ok).map(r => r.data);
      this.renderTable();
      Toast.show(`Обработано ${data.results.length}, распознано ${this.tickets.length}`, 'success');
      if (statusEl) statusEl.textContent = `Обработано: ${data.results.length} файлов`;
    } catch(e) {
      Toast.show('Ошибка парсинга: ' + e.message, 'error');
      if (statusEl) statusEl.textContent = 'Ошибка: ' + e.message;
    }
  },

  renderTable() {
    const tbody = document.getElementById('tickets-parsed-tbody');
    if (!tbody) return;
    if (!this.tickets.length) {
      tbody.innerHTML = '<tr><td colspan="13" style="text-align:center;color:var(--text-muted);padding:20px">Нет данных</td></tr>';
      return;
    }
    tbody.innerHTML = this.tickets.map((t, i) => `
      <tr style="font-size:11px">
        <td style="padding:3px 6px">${escHtml(t.passenger||'')}</td>
        <td style="padding:3px 6px">${escHtml(t.ticket_number||'')}</td>
        <td style="padding:3px 6px">${escHtml(t.order_number||'')}</td>
        <td style="padding:3px 6px">${escHtml(t.issue_date||'')}</td>
        <td style="padding:3px 6px">${escHtml(t.carrier||'')}</td>
        <td style="padding:3px 6px">${escHtml(t.flight_number||'')}</td>
        <td style="padding:3px 6px">${escHtml(t.departure_time||'')}</td>
        <td style="padding:3px 6px">${escHtml(t.departure_date||'')}</td>
        <td style="padding:3px 6px">${escHtml(t.route||'')}</td>
        <td style="padding:3px 6px">${escHtml(t.arrival_time||'')}</td>
        <td style="padding:3px 6px">${escHtml(t.arrival_date||'')}</td>
        <td style="padding:3px 6px">${escHtml(t.total_price||'')} ${escHtml(t.currency||'')}</td>
        <td style="padding:3px 6px;color:var(--text-muted)">${escHtml(t.source_file||'')}</td>
      </tr>`).join('');
  },

  async exportExcel() {
    if (!this.tickets.length) return Toast.show('Нет данных', 'warning');
    try {
      const resp = await apiPost('/api/utilities/parse-tickets-pdf/export', {tickets: this.tickets});
      if (!resp.ok) throw new Error('Ошибка экспорта');
      const blob = await resp.blob();
      downloadBlob(blob, 'tickets_parsed.xlsx');
      Toast.show('Экспорт выполнен', 'success');
    } catch(e) {
      Toast.show('Ошибка: ' + e.message, 'error');
    }
  },

  clearData() {
    this.tickets = [];
    this.renderTable();
    const inp = document.getElementById('ticket-files-input');
    if (inp) inp.value = '';
    const statusEl = document.getElementById('ticket-status');
    if (statusEl) statusEl.textContent = '';
    Toast.show('Данные очищены', 'info', 1500);
  },
};

/* ═══════════════════════════════════════════════════════════════════════
   FILE RENAMER MODULE
   ═══════════════════════════════════════════════════════════════════════ */
const RenamerModule = {
  files: [],
  preview: [],

  loadFiles(files) {
    this.files = Array.from(files).map(f => f.name);
    this.preview = this.files.map(n => ({old: n, new: n}));
    this.updatePreview();
  },

  updatePreview() {
    const mode = document.getElementById('rename-mode')?.value || 'prefix_suffix';
    const prefix = document.getElementById('rename-prefix')?.value || '';
    const suffix = document.getElementById('rename-suffix')?.value || '';
    const find   = document.getElementById('rename-find')?.value || '';
    const replace= document.getElementById('rename-replace')?.value || '';
    const pattern= document.getElementById('rename-pattern')?.value || '{n}_{name}';
    const start  = parseInt(document.getElementById('rename-start')?.value) || 1;
    const caseM  = document.getElementById('rename-case')?.value || 'title';

    this.preview = this.files.map((oldName, i) => {
      const stem = oldName.includes('.') ? oldName.slice(0, oldName.lastIndexOf('.')) : oldName;
      const ext  = oldName.includes('.') ? oldName.slice(oldName.lastIndexOf('.')) : '';
      let newStem = stem;

      if (mode === 'prefix_suffix') {
        newStem = prefix + stem + suffix;
      } else if (mode === 'replace') {
        newStem = find ? stem.split(find).join(replace) : stem;
      } else if (mode === 'pattern') {
        newStem = pattern
          .replace('{n}', String(start + i).padStart(3,'0'))
          .replace('{i}', String(i+1))
          .replace('{name}', stem);
      } else if (mode === 'case') {
        if (caseM === 'upper') newStem = stem.toUpperCase();
        else if (caseM === 'lower') newStem = stem.toLowerCase();
        else newStem = stem.replace(/\b\w/g, c => c.toUpperCase());
      }

      return {old: oldName, new: newStem + ext};
    });

    this.renderPreview();
  },

  renderPreview() {
    const el = document.getElementById('rename-preview-list');
    if (!el) return;
    if (!this.preview.length) {
      el.innerHTML = '<div style="color:var(--text-muted);font-size:12px;padding:8px">Загрузите файлы для предпросмотра</div>';
      return;
    }
    el.innerHTML = this.preview.map(p => `
      <div style="display:flex;gap:8px;padding:3px 0;font-size:11px;border-bottom:1px solid var(--border-color)">
        <span style="color:var(--text-muted);flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${escHtml(p.old)}">${escHtml(p.old)}</span>
        <span style="color:var(--text-muted)">→</span>
        <span style="color:${p.old===p.new?'var(--text-muted)':'var(--accent-green)'};flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${escHtml(p.new)}">${escHtml(p.new)}</span>
      </div>`).join('');
  },
};

/* ═══════════════════════════════════════════════════════════════════════
   STAZH MODULE (Стаж сотрудников)
   ═══════════════════════════════════════════════════════════════════════ */
const StazhModule = {
  data: [],

  async load() {
    const statusEl = document.getElementById('stazh-status');
    if (statusEl) statusEl.textContent = 'Загрузка...';
    try {
      const resp = await apiPost('/api/utilities/stazh', {});
      const json = await resp.json();
      this.data = json.results || [];
      const avg = json.avg_years || 0;
      if (statusEl) statusEl.textContent =
        `Всего: ${this.data.length} сотрудников | Средний стаж: ${avg} лет`;
      this.render();
    } catch(e) {
      if (statusEl) statusEl.textContent = 'Ошибка: ' + e.message;
    }
  },

  render() {
    const tbody = document.getElementById('stazh-tbody');
    if (!tbody) return;
    if (!this.data.length) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--text-muted);padding:20px">Нет данных</td></tr>';
      return;
    }
    const min = parseFloat(document.getElementById('stazh-min')?.value) || 0;
    const max = parseFloat(document.getElementById('stazh-max')?.value) || 9999;
    const filt = document.getElementById('stazh-filter')?.value?.toLowerCase() || '';
    const dept = document.getElementById('stazh-dept')?.value || '';

    const filtered = this.data.filter(r => {
      if (r.years < min || r.years > max) return false;
      if (filt && !r.fio.toLowerCase().includes(filt)) return false;
      if (dept && r.department !== dept) return false;
      return true;
    });

    tbody.innerHTML = filtered.map((r, i) => {
      const yr = r.years;
      const color = yr >= 10 ? 'var(--accent-green)' : yr >= 5 ? 'var(--accent-blue)' : 'var(--text-primary)';
      return `<tr style="font-size:11px">
        <td style="padding:3px 6px;text-align:center">${i+1}</td>
        <td style="padding:3px 6px">${escHtml(r.fio)}</td>
        <td style="padding:3px 6px">${escHtml(r.tab_num||'')}</td>
        <td style="padding:3px 6px">${escHtml(r.hire_date||'')}</td>
        <td style="padding:3px 6px">${escHtml(r.fire_date||'—')}</td>
        <td style="padding:3px 6px">${escHtml(r.status||'')}</td>
        <td style="padding:3px 6px">${escHtml(r.department||'')}</td>
        <td style="padding:3px 6px;text-align:right;font-weight:600;color:${color}">${yr.toFixed(2)}</td>
      </tr>`;
    }).join('');
  },

  async exportExcel() {
    if (!this.data.length) return Toast.show('Нет данных', 'warning');
    try {
      const resp = await apiPost('/api/utilities/stazh/export', {rows: this.data});
      if (!resp.ok) throw new Error('Ошибка');
      const blob = await resp.blob();
      downloadBlob(blob, 'stazh.xlsx');
      Toast.show('Экспорт выполнен', 'success');
    } catch(e) {
      Toast.show('Ошибка: ' + e.message, 'error');
    }
  },
};

/* ═══════════════════════════════════════════════════════════════════════
   MAIN RENDER — buildUtilitiesTab()
   ═══════════════════════════════════════════════════════════════════════ */
function buildUtilitiesTab() {
  const el = document.getElementById('tab-utilities');
  if (!el) return;

  el.innerHTML = `
  <div style="display:flex;gap:0;height:calc(100vh - 110px)">

    <!-- Left sidebar: sub-tabs -->
    <div id="util-sidebar" style="width:180px;min-width:180px;background:var(--bg-secondary);border-right:1px solid var(--border-color);display:flex;flex-direction:column;padding:8px 0">
      ${[
        ['translit',   '🌍 Транслитератор'],
        ['tickets',    '✈️ Парсер билетов'],
        ['renamer',    '📝 Переименование'],
        ['stazh',      '📅 Стаж сотрудников'],
      ].map(([id, label]) => `
        <button class="util-tab-btn" data-tab="${id}" onclick="switchUtilTab('${id}')"
          style="text-align:left;padding:10px 14px;border:none;background:none;color:var(--text-primary);
          cursor:pointer;font-size:12px;border-left:3px solid transparent;transition:all .15s">
          ${label}
        </button>`).join('')}
    </div>

    <!-- Right content area -->
    <div id="util-content" style="flex:1;overflow-y:auto;padding:12px">

      <!-- ─── ТРАНСЛИТЕРАТОР ─── -->
      <div id="util-translit" class="util-panel">
        <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:8px">
          <span style="font-weight:600;font-size:14px">🌍 Транслитератор ФИО (RU → EN)</span>
          <label style="display:flex;align-items:center;gap:4px;font-size:12px;cursor:pointer">
            <input type="checkbox" id="translit-uppercase" checked onchange="TranslitModule.uppercase=this.checked">
            ЗАГЛАВНЫЕ
          </label>
        </div>
        <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px">
          <button class="btn btn-primary btn-sm" onclick="TranslitModule.transliterateAll()">🔄 Транслит</button>
          <button class="btn btn-secondary btn-sm" onclick="TranslitModule.addRows(10)">➕ +10 строк</button>
          <button class="btn btn-secondary btn-sm" onclick="TranslitModule.pasteFromClipboard()">📋 Вставить</button>
          <button class="btn btn-secondary btn-sm" onclick="TranslitModule.copyResults()">🔤 Копировать EN</button>
          <button class="btn btn-secondary btn-sm" onclick="TranslitModule.exportExcel()">📊 Excel</button>
          <button class="btn btn-danger btn-sm" onclick="TranslitModule.clearAll()">🗑️ Очистить</button>
        </div>
        <div style="overflow-x:auto">
          <table style="width:100%;border-collapse:collapse;font-size:12px">
            <thead>
              <tr style="background:var(--bg-tertiary)">
                <th style="padding:4px 6px;width:40px;text-align:center">#</th>
                <th style="padding:4px 6px;width:180px">Гражданство</th>
                <th style="padding:4px 6px">ФИО (RU)</th>
                <th style="padding:4px 6px">ФИО (EN) — результат</th>
              </tr>
            </thead>
            <tbody id="translit-tbody"></tbody>
          </table>
        </div>
        <div style="margin-top:6px;font-size:11px;color:var(--text-muted)">
          Поддерживаемые страны: ${ALL_COUNTRIES.join(', ')}
        </div>
      </div>

      <!-- ─── ПАРСЕР БИЛЕТОВ ─── -->
      <div id="util-tickets" class="util-panel" style="display:none">
        <span style="font-weight:600;font-size:14px">✈️ Парсер авиабилетов PDF</span>
        <div style="margin:10px 0;padding:10px;background:var(--bg-secondary);border-radius:6px;border:1px solid var(--border-color)">
          <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
            <label style="font-size:12px;cursor:pointer">
              <input type="file" id="ticket-files-input" multiple accept=".pdf,.jpg,.jpeg,.png"
                onchange="TicketParserModule.parseFiles(this.files)" style="display:none">
              <button class="btn btn-primary btn-sm" onclick="document.getElementById('ticket-files-input').click()">
                📁 Выбрать PDF
              </button>
            </label>
            <button class="btn btn-secondary btn-sm" onclick="TicketParserModule.exportExcel()">📊 Экспорт Excel</button>
            <button class="btn btn-danger btn-sm" onclick="TicketParserModule.clearData()">🗑️ Очистить</button>
            <span id="ticket-status" style="font-size:12px;color:var(--text-muted)"></span>
          </div>
        </div>
        <div style="overflow-x:auto">
          <table style="width:100%;border-collapse:collapse;font-size:11px;min-width:900px">
            <thead>
              <tr style="background:var(--bg-tertiary)">
                <th style="padding:4px 6px">Пассажир</th>
                <th style="padding:4px 6px">№ билета</th>
                <th style="padding:4px 6px">№ заказа</th>
                <th style="padding:4px 6px">Дата выдачи</th>
                <th style="padding:4px 6px">Перевозчик</th>
                <th style="padding:4px 6px">Рейс</th>
                <th style="padding:4px 6px">Вылет время</th>
                <th style="padding:4px 6px">Вылет дата</th>
                <th style="padding:4px 6px">Маршрут</th>
                <th style="padding:4px 6px">Прилёт время</th>
                <th style="padding:4px 6px">Прилёт дата</th>
                <th style="padding:4px 6px">Стоимость</th>
                <th style="padding:4px 6px">Файл</th>
              </tr>
            </thead>
            <tbody id="tickets-parsed-tbody">
              <tr><td colspan="13" style="text-align:center;color:var(--text-muted);padding:20px">
                Загрузите PDF файлы авиабилетов
              </td></tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- ─── ПЕРЕИМЕНОВАНИЕ ─── -->
      <div id="util-renamer" class="util-panel" style="display:none">
        <span style="font-weight:600;font-size:14px">📝 Переименование файлов</span>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:10px 0">
          <!-- Controls -->
          <div style="background:var(--bg-secondary);border-radius:6px;padding:10px;border:1px solid var(--border-color)">
            <div style="margin-bottom:8px">
              <label style="font-size:12px;color:var(--text-muted);display:block;margin-bottom:3px">Режим</label>
              <select id="rename-mode" class="form-control" style="font-size:12px"
                onchange="RenamerModule.updatePreview()">
                <option value="prefix_suffix">Префикс / Суффикс</option>
                <option value="replace">Найти и заменить</option>
                <option value="pattern">Шаблон нумерации</option>
                <option value="case">Регистр</option>
              </select>
            </div>

            <div id="rename-opts-prefix_suffix">
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px">
                <div>
                  <label style="font-size:11px;color:var(--text-muted)">Префикс</label>
                  <input id="rename-prefix" class="form-control" style="font-size:12px"
                    placeholder="2024_" oninput="RenamerModule.updatePreview()">
                </div>
                <div>
                  <label style="font-size:11px;color:var(--text-muted)">Суффикс</label>
                  <input id="rename-suffix" class="form-control" style="font-size:12px"
                    placeholder="_final" oninput="RenamerModule.updatePreview()">
                </div>
              </div>
            </div>

            <div id="rename-opts-replace" style="display:grid;grid-template-columns:1fr 1fr;gap:6px">
              <div>
                <label style="font-size:11px;color:var(--text-muted)">Найти</label>
                <input id="rename-find" class="form-control" style="font-size:12px"
                  oninput="RenamerModule.updatePreview()">
              </div>
              <div>
                <label style="font-size:11px;color:var(--text-muted)">Заменить на</label>
                <input id="rename-replace" class="form-control" style="font-size:12px"
                  oninput="RenamerModule.updatePreview()">
              </div>
            </div>

            <div id="rename-opts-pattern" style="display:none">
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px">
                <div>
                  <label style="font-size:11px;color:var(--text-muted)">Шаблон ({n},{name},{i})</label>
                  <input id="rename-pattern" class="form-control" style="font-size:12px"
                    value="{n}_{name}" oninput="RenamerModule.updatePreview()">
                </div>
                <div>
                  <label style="font-size:11px;color:var(--text-muted)">Начать с</label>
                  <input id="rename-start" class="form-control" style="font-size:12px"
                    type="number" value="1" oninput="RenamerModule.updatePreview()">
                </div>
              </div>
            </div>

            <div id="rename-opts-case" style="display:none">
              <select id="rename-case" class="form-control" style="font-size:12px"
                onchange="RenamerModule.updatePreview()">
                <option value="title">Title Case</option>
                <option value="upper">ВЕРХНИЙ</option>
                <option value="lower">нижний</option>
              </select>
            </div>

            <div style="margin-top:10px;display:flex;gap:6px;flex-wrap:wrap">
              <label style="cursor:pointer">
                <input type="file" multiple onchange="RenamerModule.loadFiles(this.files)" style="display:none">
                <button class="btn btn-primary btn-sm" onclick="this.previousElementSibling.click()">📁 Файлы</button>
              </label>
              <button class="btn btn-secondary btn-sm" onclick="RenamerModule.updatePreview()">🔄 Обновить</button>
            </div>
          </div>

          <!-- Preview -->
          <div style="background:var(--bg-secondary);border-radius:6px;padding:10px;border:1px solid var(--border-color)">
            <div style="font-size:12px;color:var(--text-muted);margin-bottom:6px;font-weight:600">
              Предпросмотр (${'{'}0{'}'} файлов):
            </div>
            <div id="rename-preview-list" style="max-height:300px;overflow-y:auto">
              <div style="color:var(--text-muted);font-size:12px;padding:8px">Загрузите файлы для предпросмотра</div>
            </div>
          </div>
        </div>

        <div style="padding:10px;background:var(--bg-secondary);border-radius:6px;border:1px solid var(--border-color);font-size:12px;color:var(--text-muted)">
          ℹ️ Переименование выполняется через файловый менеджер или BAT-скрипт.
          Предпросмотр показывает итоговые имена до операции.
        </div>
      </div>

      <!-- ─── СТАЖ ─── -->
      <div id="util-stazh" class="util-panel" style="display:none">
        <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:8px">
          <span style="font-weight:600;font-size:14px">📅 Стаж сотрудников</span>
          <button class="btn btn-primary btn-sm" onclick="StazhModule.load()">🔄 Рассчитать</button>
          <button class="btn btn-secondary btn-sm" onclick="StazhModule.exportExcel()">📊 Excel</button>
          <span id="stazh-status" style="font-size:12px;color:var(--text-muted)"></span>
        </div>

        <!-- Filters -->
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px;padding:8px;background:var(--bg-secondary);border-radius:6px;border:1px solid var(--border-color)">
          <div>
            <label style="font-size:11px;color:var(--text-muted)">Поиск ФИО</label>
            <input id="stazh-filter" class="form-control" style="font-size:12px;width:160px"
              placeholder="Поиск..." oninput="StazhModule.render()">
          </div>
          <div>
            <label style="font-size:11px;color:var(--text-muted)">Стаж от (лет)</label>
            <input id="stazh-min" class="form-control" style="font-size:12px;width:80px"
              type="number" value="0" step="0.5" oninput="StazhModule.render()">
          </div>
          <div>
            <label style="font-size:11px;color:var(--text-muted)">До (лет)</label>
            <input id="stazh-max" class="form-control" style="font-size:12px;width:80px"
              type="number" value="50" step="0.5" oninput="StazhModule.render()">
          </div>
        </div>

        <div style="overflow-x:auto">
          <table style="width:100%;border-collapse:collapse;font-size:12px">
            <thead>
              <tr style="background:var(--bg-tertiary)">
                <th style="padding:4px 6px;width:40px">#</th>
                <th style="padding:4px 6px">ФИО</th>
                <th style="padding:4px 6px">Табном</th>
                <th style="padding:4px 6px">Приём</th>
                <th style="padding:4px 6px">Увольнение</th>
                <th style="padding:4px 6px">Статус</th>
                <th style="padding:4px 6px">Подразделение</th>
                <th style="padding:4px 6px;text-align:right">Стаж (лет)</th>
              </tr>
            </thead>
            <tbody id="stazh-tbody">
              <tr><td colspan="8" style="text-align:center;color:var(--text-muted);padding:20px">
                Нажмите «Рассчитать» для расчёта стажа сотрудников
              </td></tr>
            </tbody>
          </table>
        </div>
      </div>

    </div><!-- /util-content -->
  </div>
  `;

  /* Style active sidebar button */
  document.querySelectorAll('.util-tab-btn').forEach(btn => {
    btn.addEventListener('mouseenter', () => { btn.style.background = 'var(--bg-tertiary)'; });
    btn.addEventListener('mouseleave', () => {
      if (!btn.classList.contains('active')) btn.style.background = 'none';
    });
  });

  /* Init rename-mode dynamic fields */
  const renameMode = document.getElementById('rename-mode');
  if (renameMode) {
    renameMode.addEventListener('change', function() {
      ['prefix_suffix','replace','pattern','case'].forEach(m => {
        const el = document.getElementById('rename-opts-' + m);
        if (el) el.style.display = m === this.value ? '' : 'none';
      });
      RenamerModule.updatePreview();
    });
    // Init show/hide
    ['replace','pattern','case'].forEach(m => {
      const el = document.getElementById('rename-opts-' + m);
      if (el) el.style.display = 'none';
    });
  }

  switchUtilTab('translit');
  TranslitModule.init();
}

function switchUtilTab(tab) {
  document.querySelectorAll('.util-panel').forEach(p => p.style.display = 'none');
  const target = document.getElementById('util-' + tab);
  if (target) target.style.display = 'block';

  document.querySelectorAll('.util-tab-btn').forEach(btn => {
    const isActive = btn.dataset.tab === tab;
    btn.style.borderLeft = isActive ? '3px solid var(--accent-blue)' : '3px solid transparent';
    btn.style.background = isActive ? 'var(--bg-tertiary)' : 'none';
    btn.style.color = isActive ? 'var(--accent-blue)' : 'var(--text-primary)';
    btn.style.fontWeight = isActive ? '600' : 'normal';
  });
}

/* ─── Helper: raw fetch wrappers ─── */
async function apiPost(url, data) {
  return fetch(url, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(data),
  });
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

/* ─── Legacy Utilities object for backward compat ─── */
const Utilities = {
  translit() { TranslitModule.transliterateAll(); },
  convertExcel(file) { Toast.show('Конвертация xlsb→xlsx требует серверной обработки', 'info'); },
  prepareRename(files) { RenamerModule.loadFiles(files); },
  pdfToExcel(files) { TicketParserModule.parseFiles(files); },
  calcStazh() { StazhModule.load(); },
};
