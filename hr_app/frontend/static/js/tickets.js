/* Tickets module — Покупка билетов */
const Tickets = {
  page: 0, pageSize: 100, total: 0,
  rows: [],

  async load() {
    const dept = document.getElementById('tkt-dept-filter')?.value || '';
    const params = new URLSearchParams({ department: dept, limit: this.pageSize, offset: this.page * this.pageSize });
    try {
      const data = await api(`/tickets/orders?${params}`);
      this.total = data.total;
      this.rows = data.rows;
      this._render();
      this._updatePagination();
      document.getElementById('tkt-info').textContent = `${fmtNum(data.total)} записей`;
      this._loadDepts();
    } catch(e) {
      document.getElementById('tkt-tbody').innerHTML =
        `<tr><td colspan="29" style="color:var(--accent-red);text-align:center;padding:20px">Ошибка: ${escHtml(e.message)}</td></tr>`;
    }
  },

  async _loadDepts() {
    try {
      const data = await api('/tickets/departments');
      const sel = document.getElementById('tkt-dept-filter');
      const cur = sel.value;
      sel.innerHTML = '<option value="">Все подразделения</option>' +
        data.departments.map(d => `<option value="${escHtml(d)}">${escHtml(d)}</option>`).join('');
      sel.value = cur;
    } catch(e) {}
  },

  _render() {
    const cols = [
      'num','department','section_dept','operation','classification','order_date',
      'org','fio','fio_lat','tab_num','citizenship','birth_date','doc_type',
      'doc_series','doc_num','doc_issue_date','doc_expire_date','doc_issuer',
      'route','reason','transport_type','flight_date','note','responsible',
      'ticket','amount','payment','phone'
    ];
    const tbody = document.getElementById('tkt-tbody');
    if (!this.rows.length) {
      tbody.innerHTML = `<tr><td colspan="29" style="text-align:center;padding:30px;color:var(--text-muted)">Нет данных. Добавьте строки или загрузите PDF.</td></tr>`;
      return;
    }
    tbody.innerHTML = this.rows.map((row, i) =>
      `<tr data-id="${row.id}">
        ${cols.map(k => {
          const v = escHtml(String(row[k] ?? ''));
          if (k === 'fio') return `<td><span style="font-weight:500;color:var(--accent-blue)">${v}</span></td>`;
          if (k === 'citizenship') return `<td>${citizenBadge(row[k])}</td>`;
          if (k === 'note' && row[k]?.includes('НЕ НАЙДЕН')) return `<td><span class="badge badge-red">НЕ НАЙДЕН</span></td>`;
          return `<td class="editable-cell" contenteditable="true" onblur="Tickets.editCell(${row.id},'${k}',this)">${v}</td>`;
        }).join('')}
        <td><button class="btn btn-danger btn-sm" onclick="Tickets.deleteRow(${row.id})">✕</button></td>
      </tr>`
    ).join('');
  },

  async editCell(id, field, el) {
    const val = el.textContent.trim();
    try {
      await api(`/tickets/orders/${id}`, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ [field]: val })
      });
    } catch(e) { Toast.show('Ошибка сохранения: ' + e.message, 'error'); }
  },

  async addRow() {
    const dept = document.getElementById('tkt-dept-filter')?.value || '';
    const today = new Date().toLocaleDateString('ru-RU');
    try {
      await api('/tickets/orders', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          num: this.total + 1,
          department: dept,
          operation: 'Заказ',
          order_date: today,
          transport_type: 'АВИА',
          payment: 'Монтаж',
        })
      });
      this.load();
      Toast.show('Строка добавлена', 'success', 1500);
    } catch(e) { Toast.show('Ошибка: ' + e.message, 'error'); }
  },

  async deleteRow(id) {
    if (!confirm('Удалить строку?')) return;
    try {
      await api(`/tickets/orders/${id}`, { method: 'DELETE' });
      this.load();
      Toast.show('Удалено', 'success', 1500);
    } catch(e) { Toast.show('Ошибка: ' + e.message, 'error'); }
  },

  async fillFromBase() {
    const fios = this.rows.filter(r => r.fio && !r.tab_num).map(r => r.fio);
    if (!fios.length) return Toast.show('Нет строк без табельного номера', 'info');
    let filled = 0;
    for (const row of this.rows.filter(r => r.fio && !r.tab_num)) {
      try {
        const emp = await api(`/employees/by-fio?fio=${encodeURIComponent(row.fio)}`);
        await api(`/tickets/orders/${row.id}`, {
          method: 'PUT',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            tab_num: emp.tab_num || '',
            citizenship: emp.citizenship || '',
            birth_date: emp.birth_date || '',
            doc_series: emp.doc_series || '',
            doc_num: emp.doc_num || '',
            doc_issue_date: emp.doc_issue_date || '',
            doc_issuer: emp.doc_issuer || '',
            address: emp.address || '',
            phone: emp.phone_mobile || '',
          })
        });
        filled++;
      } catch(e) {}
    }
    this.load();
    Toast.show(`Заполнено из базы: ${filled} сотрудников`, 'success');
  },

  importPDF() {
    const inp = document.createElement('input');
    inp.type = 'file'; inp.accept = '.pdf'; inp.multiple = true;
    inp.onchange = async (e) => {
      const files = e.target.files;
      if (!files.length) return;
      Toast.show('Обработка PDF...', 'info', 2000);
      for (const file of files) {
        const fd = new FormData();
        fd.append('file', file);
        fd.append('department', document.getElementById('tkt-dept-filter')?.value || '');
        try {
          const result = await apiUpload('/tickets/upload-pdf', fd);
          if (result.results?.length) {
            for (const r of result.results) {
              await api('/tickets/orders', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ fio: r.fio, route: r.route, flight_date: r.date, phone: r.phone, operation: 'Заказ', transport_type: 'АВИА' })
              });
            }
          }
        } catch(e) { Toast.show('Ошибка PDF: ' + e.message, 'error'); }
      }
      this.load();
      Toast.show('PDF обработаны', 'success');
    };
    inp.click();
  },

  exportExcel() {
    const dept = document.getElementById('tkt-dept-filter')?.value || '';
    apiDownload(`/tickets/orders/export?department=${encodeURIComponent(dept)}`)
      .then(() => Toast.show('Заявка экспортирована', 'success'))
      .catch(e => Toast.show('Ошибка: ' + e.message, 'error'));
  },

  clearAll() {
    if (!confirm('Очистить все заявки?')) return;
    api('/tickets/orders?limit=10000&offset=0').then(data => {
      Promise.all(data.rows.map(r => api(`/tickets/orders/${r.id}`, { method: 'DELETE' })))
        .then(() => { this.load(); Toast.show('Очищено', 'success'); });
    });
  },

  _updatePagination() {
    const totalPages = Math.ceil(this.total / this.pageSize);
    document.getElementById('tkt-pg-info').textContent = `Стр. ${this.page + 1} из ${totalPages || 1}`;
    document.getElementById('tkt-prev').disabled = this.page === 0;
    document.getElementById('tkt-next').disabled = (this.page + 1) >= totalPages;
  },
  prevPage() { if (this.page > 0) { this.page--; this.load(); } },
  nextPage() { if ((this.page + 1) * this.pageSize < this.total) { this.page++; this.load(); } },
};

/* Ticket Costs module */
const TicketCosts = {
  async load() {
    try {
      const [costs, summary] = await Promise.all([
        api('/tickets/costs?limit=500'),
        api('/tickets/costs/summary'),
      ]);

      document.getElementById('cost-total-val').textContent = fmtNum(Math.round(summary.total_amount || 0));
      document.getElementById('cost-count-val').textContent = fmtNum(costs.total);
      document.getElementById('cost-files-val').textContent = fmtNum(summary.by_org?.length || 0);
      document.getElementById('costs-info').textContent = `${fmtNum(costs.total)} записей`;

      renderTable('costs-tbody', costs.rows, [
        'source_file','tab_num','fio','route','flight_date','ticket_num','amount','payment','org','department','note'
      ], {
        amount: val => `<span style="color:var(--accent-green);font-weight:600">${val ? fmtNum(val) + ' ₽' : '—'}</span>`,
        fio: val => `<strong>${escHtml(val)}</strong>`,
      });

      // Charts
      if (summary.by_org?.length) {
        Charts.bar('chart-costs-org', summary.by_org.map(r => ({
          label: r.org || '—', value: Math.round(r.total || 0)
        })), { horizontal: true, color: '#58a6ff' });
      }
      if (summary.by_month?.length) {
        Charts.bar('chart-costs-month', summary.by_month.map(r => ({
          label: r.month || '—', value: Math.round(r.total || 0)
        })), { color: '#3fb950' });
      }
    } catch(e) {
      Toast.show('Ошибка загрузки затрат: ' + e.message, 'error');
    }
  },

  async upload(files) {
    if (!files?.length) return;
    const fd = new FormData();
    for (const f of files) fd.append('files', f);
    Toast.show('Загрузка реестров...', 'info', 2000);
    try {
      const result = await apiUpload('/settings/upload-ticket-costs', fd);
      Toast.show(result.message, 'success');
      this.load();
    } catch(e) { Toast.show('Ошибка: ' + e.message, 'error'); }
  },
};

/* Evaluations */
const Eval = {
  async uploadROP(files) {
    if (!files?.length) return;
    Toast.show('Загрузка оценок РОП...', 'info', 2000);
    // Generic Excel load — show in table
    for (const file of files) {
      const fd = new FormData();
      fd.append('file', file);
      // For now, just show a success toast and indicate it's loaded
      Toast.show(`Файл ${file.name} принят (функционал в разработке)`, 'info');
    }
  },
  exportROPExcel() { Toast.show('Экспорт РОП в разработке', 'info'); }
};
