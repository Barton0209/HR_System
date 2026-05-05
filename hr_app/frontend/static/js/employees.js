/* Employees module — с Handsontable для Excel-подобного интерфейса */
const Employees = {
  page: 0,
  pageSize: 100,
  total: 0,
  hotInstance: null,
  changesBuffer: [], // Буфер изменений

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

    const container = document.getElementById('emp-hot-container');
    container.innerHTML = '<div class="loading-overlay" style="height:600px;display:flex;align-items:center;justify-content:center"><div class="spinner"></div><span style="margin-left:10px">Загрузка данных...</span></div>';

    try {
      const data = await api(`/employees?${params}`);
      this.total = data.total;
      this._renderHandsontable(data.rows);
      this._updatePagination();
      document.getElementById('emp-info').textContent =
        `Показано ${data.rows.length} из ${fmtNum(data.total)} записей`;
    } catch(e) {
      container.innerHTML = `<div style="padding:20px;color:var(--accent-red);text-align:center">Ошибка: ${escHtml(e.message)}</div>`;
    }
  },

  _renderHandsontable(rows) {
    const container = document.getElementById('emp-hot-container');
    
    // Преобразуем данные в массив массивов
    const columns = [
      { data: 'tab_num', title: 'Табном', width: 80 },
      { data: 'fio', title: 'ФИО', width: 200 },
      { data: 'citizenship', title: 'Гражданство', width: 120 },
      { data: 'birth_date', title: 'Дата рождения', width: 100, type: 'date', dateFormat: 'YYYY-MM-DD' },
      { data: 'position', title: 'Должность', width: 150 },
      { data: 'department', title: 'Подразделение', width: 150 },
      { data: 'platform_eju', title: 'Площадка ЕЖУ', width: 120 },
      { data: 'status', title: 'Статус', width: 100 },
      { data: 'status_op', title: 'Статус ОП', width: 120 },
      { data: 'classification', title: 'Классификация', width: 100 },
      { data: 'work_schedule', title: 'График', width: 80 },
      { data: 'hire_date', title: 'Приём', width: 100, type: 'date', dateFormat: 'YYYY-MM-DD' },
      { data: 'fire_date', title: 'Увольнение', width: 100, type: 'date', dateFormat: 'YYYY-MM-DD' },
      { data: 'phone_mobile', title: 'Телефон', width: 120 },
      { data: 'org', title: 'Организация', width: 150 }
    ];

    // Добавляем id к данным для сохранения
    const dataWithId = rows.map(r => ({ ...r }));

    if (this.hotInstance) {
      this.hotInstance.destroy();
    }

    this.hotInstance = new Handsontable(container, {
      data: dataWithId,
      columns: columns,
      colHeaders: true,
      rowHeaders: true,
      height: '100%',
      width: '100%',
      stretchH: 'all',
      licenseKey: 'non-commercial-and-evaluation',
      language: 'ru-RU',
      contextMenu: ['row_above', 'row_below', 'remove_row', 'separator', 'copy', 'cut', 'paste'],
      manualColumnResize: true,
      manualRowResize: true,
      filters: true,
      dropdownMenu: true,
      columnSorting: true,
      copyPaste: {
        pasteMode: 'replace',
        rowsLimit: 1000,
        columnsLimit: 100
      },
      afterChange: (changes, source) => {
        if (source === 'edit' && changes) {
          changes.forEach(([row, prop, oldVal, newVal]) => {
            if (oldVal !== newVal) {
              const rowData = this.hotInstance.getSourceDataAtRow(row);
              this.changesBuffer.push({
                id: rowData.id,
                field: prop,
                oldValue: oldVal,
                newValue: newVal
              });
            }
          });
          this._showUnsavedIndicator();
        }
      }
    });
  },

  _showUnsavedIndicator() {
    const btn = document.querySelector('button[onclick="Employees.saveChanges()"]');
    if (btn && this.changesBuffer.length > 0) {
      btn.textContent = `💾 Сохранить (${this.changesBuffer.length})`;
      btn.style.background = 'var(--accent-orange)';
    }
  },

  async saveChanges() {
    if (this.changesBuffer.length === 0) {
      Toast.show('Нет изменений для сохранения', 'info');
      return;
    }

    try {
      // Отправляем изменения на сервер
      const response = await fetch('/api/employees/batch-update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ changes: this.changesBuffer })
      });

      if (!response.ok) throw new Error('Ошибка сохранения');

      this.changesBuffer = [];
      Toast.show(`Сохранено ${this.hotInstance.countRows()} записей`, 'success');
      this._resetSaveButton();
      this.load(); // Перезагружаем данные
    } catch(e) {
      Toast.show('Ошибка: ' + e.message, 'error');
    }
  },

  _resetSaveButton() {
    const btn = document.querySelector('button[onclick="Employees.saveChanges()"]');
    if (btn) {
      btn.textContent = '💾 Сохранить изменения';
      btn.style.background = '';
    }
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
    if (!this.hotInstance) return Toast.show('Нет данных для экспорта', 'warning');
    
    Toast.show('Подготовка Excel...', 'info', 2000);
    
    // Получаем данные из Handsontable
    const data = this.hotInstance.getData();
    const headers = this.hotInstance.getColHeader().map(h => h || '');
    
    // Создаем workbook с помощью SheetJS
    const ws = XLSX.utils.aoa_to_sheet([headers, ...data]);
    
    // Настраиваем ширину колонок
    const colWidths = this.hotInstance.getSettings().columns.map(c => ({ wch: Math.max(10, (c.width || 100) / 7) }));
    ws['!cols'] = colWidths;
    
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, 'Сотрудники');
    
    // Генерируем файл
    XLSX.writeFile(wb, `Сотрудники_${new Date().toISOString().slice(0,10)}.xlsx`);
    Toast.show(`Экспортировано ${data.length} записей`, 'success');
  }
};
