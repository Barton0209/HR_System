/* Daily Tracking module — Ежедневный учёт */
const DailyTracking = {
  page: 0, pageSize: 200, total: 0,
  selectedDate: null,
  pendingFiles: [],

  init() {
    // Set today's date
    const today = new Date();
    const dateStr = today.toISOString().split('T')[0];
    const dateEl = document.getElementById('eju-date');
    if (dateEl && !dateEl.value) dateEl.value = dateStr;
    this.loadDates();
    this._setupSearch();
  },

  _setupSearch() {
    const inp = document.getElementById('eju-search');
    if (inp) {
      let t;
      inp.addEventListener('input', () => {
        clearTimeout(t);
        t = setTimeout(() => this.loadData(), 400);
      });
    }
  },

  async loadDates() {
    try {
      const data = await api('/daily-tracking/dates');
      const tbody = document.getElementById('eju-dates-list');
      if (!data.dates.length) {
        tbody.innerHTML = '<tr><td colspan="2" style="text-align:center;padding:12px;color:var(--text-muted)">Нет данных</td></tr>';
        return;
      }
      tbody.innerHTML = data.dates.map(d =>
        `<tr style="cursor:pointer" onclick="DailyTracking.selectDate('${d.date}')">
          <td><span style="font-weight:500">${escHtml(d.date)}</span></td>
          <td style="text-align:right"><span class="badge badge-blue">${fmtNum(d.count)}</span></td>
        </tr>`
      ).join('');
      // Auto-select first
      if (data.dates.length && !this.selectedDate) {
        this.selectDate(data.dates[0].date);
      }
    } catch(e) {}
  },

  selectDate(date) {
    this.selectedDate = date;
    this.page = 0;
    const dateEl = document.getElementById('eju-date');
    if (dateEl) {
      // Convert DD.MM.YYYY to YYYY-MM-DD if needed
      if (date.includes('.')) {
        const [d, m, y] = date.split('.');
        dateEl.value = `${y}-${m}-${d}`;
      } else {
        dateEl.value = date;
      }
    }
    this.loadPlatforms();
    this.loadData();
  },

  async loadPlatforms() {
    if (!this.selectedDate) return;
    try {
      const data = await api(`/daily-tracking/platforms?track_date=${encodeURIComponent(this.selectedDate)}`);
      const sel = document.getElementById('eju-platform-filter');
      sel.innerHTML = data.platforms.map(p =>
        `<option value="${escHtml(p)}">${escHtml(p === 'ALL' ? 'Все площадки' : p)}</option>`
      ).join('');
    } catch(e) {}
  },

  async loadData() {
    const dateEl = document.getElementById('eju-date');
    let date = this.selectedDate;
    if (!date && dateEl?.value) {
      const d = new Date(dateEl.value);
      date = `${String(d.getDate()).padStart(2,'0')}.${String(d.getMonth()+1).padStart(2,'0')}.${d.getFullYear()}`;
    }
    if (!date) return;

    const platform = document.getElementById('eju-platform-filter')?.value || 'ALL';
    const search = document.getElementById('eju-search')?.value || '';
    const params = new URLSearchParams({ track_date: date, platform, search, limit: this.pageSize, offset: this.page * this.pageSize });

    const tbody = document.getElementById('eju-tbody');
    tbody.innerHTML = `<tr><td colspan="11" class="loading-overlay"><div class="spinner"></div></td></tr>`;

    try {
      const data = await api(`/daily-tracking/data?${params}`);
      this.total = data.total;
      document.getElementById('eju-info').textContent = `${fmtNum(data.total)} записей за ${date}`;
      this._updatePagination();

      if (!data.rows.length) {
        tbody.innerHTML = `<tr><td colspan="11" style="text-align:center;padding:30px;color:var(--text-muted)">Нет данных за ${escHtml(date)}</td></tr>`;
        return;
      }

      renderTable('eju-tbody', data.rows, [
        'region','platform','tab_num','fio','position','section',
        'visa','visa_type','visa_region','visa_expire','shift_start'
      ], {
        fio: val => `<strong>${escHtml(val)}</strong>`,
        visa_expire: val => val
          ? `<span style="color:var(--accent-orange);font-weight:600">${escHtml(val)}</span>`
          : '—',
        visa: val => val === 'Да' || val === 'да' || val === '1'
          ? '<span class="badge badge-orange">ВИЗА</span>' : (val || '—'),
      });
    } catch(e) {
      tbody.innerHTML = `<tr><td colspan="11" style="color:var(--accent-red);text-align:center;padding:20px">Ошибка: ${escHtml(e.message)}</td></tr>`;
    }
  },

  handleFiles(files) {
    this.pendingFiles = Array.from(files);
    const listEl = document.getElementById('eju-file-list');
    listEl.innerHTML = this.pendingFiles.map((f, i) =>
      `<div class="file-item">
        <span class="fi-name">📄 ${escHtml(f.name)}</span>
        <span class="fi-size">${(f.size / 1024).toFixed(0)} KB</span>
        <span class="fi-remove" onclick="DailyTracking.removeFile(${i})">✕</span>
      </div>`
    ).join('');
  },

  removeFile(idx) {
    this.pendingFiles.splice(idx, 1);
    this.handleFiles(this.pendingFiles);
  },

  async upload() {
    if (!this.pendingFiles.length) {
      return Toast.show('Выберите файлы ЕЖУ', 'warning');
    }
    const dateEl = document.getElementById('eju-date');
    if (!dateEl?.value) return Toast.show('Укажите дату', 'warning');

    const d = new Date(dateEl.value);
    const dateStr = `${String(d.getDate()).padStart(2,'0')}.${String(d.getMonth()+1).padStart(2,'0')}.${d.getFullYear()}`;

    const fd = new FormData();
    fd.append('track_date', dateStr);
    for (const f of this.pendingFiles) fd.append('files', f);

    Toast.show(`Загрузка ${this.pendingFiles.length} файлов ЕЖУ...`, 'info', 3000);
    try {
      const result = await apiUpload('/daily-tracking/upload-folder', fd);
      if (result.ok) {
        Toast.show(result.message, 'success', 5000);
        this.pendingFiles = [];
        document.getElementById('eju-file-list').innerHTML = '';
        this.selectedDate = dateStr;
        await this.loadDates();
        this.loadPlatforms();
        this.loadData();
      } else {
        Toast.show('Ошибка: ' + result.message, 'error');
      }
    } catch(e) {
      Toast.show('Ошибка загрузки: ' + e.message, 'error');
    }
  },

  _updatePagination() {
    const totalPages = Math.ceil(this.total / this.pageSize);
    document.getElementById('eju-pg-info').textContent = `Стр. ${this.page + 1} из ${totalPages || 1}`;
    document.getElementById('eju-prev').disabled = this.page === 0;
    document.getElementById('eju-next').disabled = (this.page + 1) >= totalPages;
  },
  prevPage() { if (this.page > 0) { this.page--; this.loadData(); } },
  nextPage() { if ((this.page + 1) * this.pageSize < this.total) { this.page++; this.loadData(); } },
};

/* Carnet module */
const Carnet = {
  rows: [],

  async load() {
    // Load from API (uses tickets module DB for now)
    document.getElementById('carnet-info').textContent = 'Модуль в разработке';
  },

  addRow() {
    Toast.show('Функция добавления Карнета в разработке', 'info');
  },

  exportExcel() {
    Toast.show('Экспорт Карнета в разработке', 'info');
  }
};
