/* Employees module */
const Employees = {
  page: 0,
  pageSize: 100,
  total: 0,
  sortCol: null,
  sortAsc: true,

  async load() {
    const params = new URLSearchParams({
      status_op: State.mode,
      platform: State.platform,
      citizenship: State.citizenship,
      status: State.status,
      org: State.org,
      search: State.search,
      limit: this.pageSize,
      offset: this.page * this.pageSize,
    });

    const tbody = document.getElementById('emp-tbody');
    tbody.innerHTML = `<tr><td colspan="15" class="loading-overlay"><div class="spinner"></div></td></tr>`;

    try {
      const data = await api(`/employees?${params}`);
      this.total = data.total;
      this._render(data.rows);
      this._updatePagination();
      document.getElementById('emp-info').textContent =
        `Показано ${data.rows.length} из ${fmtNum(data.total)} записей`;
    } catch(e) {
      tbody.innerHTML = `<tr><td colspan="15" style="color:var(--accent-red);text-align:center;padding:20px">Ошибка: ${escHtml(e.message)}</td></tr>`;
    }
  },

  _render(rows) {
    renderTable('emp-tbody', rows, [
      'tab_num','fio','citizenship','birth_date','position','department',
      'platform_eju','status','status_op','classification','work_schedule',
      'hire_date','fire_date','phone_mobile','org'
    ], {
      citizenship: citizenBadge,
      status: statusBadge,
      status_op: val => {
        if (!val) return '<span class="badge badge-gray">—</span>';
        if (val.includes('Актив')) return `<span class="badge badge-green">${escHtml(val)}</span>`;
        if (val.includes('Завер')) return `<span class="badge badge-orange">${escHtml(val)}</span>`;
        return `<span class="badge badge-gray">${escHtml(val)}</span>`;
      },
      classification: val => {
        if (!val) return '—';
        return val === 'ИТР'
          ? `<span class="badge badge-purple">${val}</span>`
          : `<span class="badge badge-blue">${val}</span>`;
      },
      fio: val => `<span style="font-weight:500">${escHtml(val)}</span>`,
    });
  },

  _updatePagination() {
    const totalPages = Math.ceil(this.total / this.pageSize);
    document.getElementById('emp-pg-info').textContent =
      `Стр. ${this.page + 1} из ${totalPages || 1}`;
    document.getElementById('emp-prev').disabled = this.page === 0;
    document.getElementById('emp-next').disabled = (this.page + 1) >= totalPages;
  },

  prevPage() { if (this.page > 0) { this.page--; this.load(); } },
  nextPage() {
    if ((this.page + 1) * this.pageSize < this.total) { this.page++; this.load(); }
  },

  exportExcel() {
    const params = new URLSearchParams({
      status_op: State.mode,
      platform: State.platform,
      citizenship: State.citizenship,
      status: State.status,
      org: State.org,
      search: State.search,
      limit: 100000,
      offset: 0,
    });
    // Build Excel from current filtered data
    Toast.show('Экспорт подготавливается...', 'info', 2000);
    api(`/employees?${params}`).then(data => {
      // Create CSV-like export
      const rows = data.rows;
      if (!rows.length) return Toast.show('Нет данных для экспорта', 'warning');
      const cols = Object.keys(rows[0]);
      const csv = [cols.join('\t'), ...rows.map(r => cols.map(c => r[c] ?? '').join('\t'))].join('\n');
      const blob = new Blob(['\uFEFF' + csv], { type: 'text/tab-separated-values;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a'); a.href = url; a.download = 'Сотрудники.tsv';
      a.click(); URL.revokeObjectURL(url);
      Toast.show(`Экспортировано ${rows.length} записей`, 'success');
    }).catch(e => Toast.show('Ошибка: ' + e.message, 'error'));
  }
};
