/* OCR modules */
const OCRPassport = {
  lastResult: null,
  batchResults: [],

  async init() {
    const status = await api('/ocr/status').catch(() => ({ available: false, models: [] }));
    const infoEl = document.getElementById('ocr-model-info');
    if (!infoEl) return;
    if (status.available) {
      infoEl.innerHTML = `<span style="color:var(--accent-green)">✅ Ollama доступен</span> · Модели: ${status.models.slice(0,5).join(', ')}`;
      const sel = document.getElementById('ocr-model-select');
      if (sel) {
        sel.innerHTML = status.models.map(m =>
          `<option value="${escHtml(m)}" ${m.includes('glm-ocr') ? 'selected' : ''}>${escHtml(m)}</option>`
        ).join('');
      }
    } else {
      infoEl.innerHTML = `<span style="color:var(--accent-red)">❌ Ollama недоступен</span> — запустите: <code>ollama serve</code>`;
    }
  },

  async process(file) {
    if (!file) return;
    const preview = document.getElementById('ocr-preview');
    const img = document.getElementById('ocr-img');
    if (preview && img) {
      img.src = URL.createObjectURL(file);
      preview.style.display = 'block';
    }

    document.getElementById('ocr-result-fields').style.display = 'none';
    document.getElementById('ocr-raw-result').style.display = 'none';
    document.getElementById('ocr-placeholder').style.display = 'none';
    document.getElementById('ocr-loading').style.display = 'flex';
    document.getElementById('ocr-actions').style.display = 'none';

    const model = document.getElementById('ocr-model-select')?.value || 'glm-ocr:latest';
    const fd = new FormData();
    fd.append('file', file);
    fd.append('model', model);

    try {
      const result = await apiUpload('/ocr/passport', fd);
      document.getElementById('ocr-loading').style.display = 'none';
      this.lastResult = result.result;

      if (result.result && typeof result.result === 'object') {
        const r = result.result;
        // Fill structured fields
        const fields = {
          'ocr-surname': r.surname || r.фамилия || r.last_name || '',
          'ocr-name': r.name || r.имя || r.first_name || '',
          'ocr-patronymic': r.patronymic || r.отчество || r.middle_name || '',
          'ocr-birth': r.birth_date || r.дата_рождения || '',
          'ocr-gender': r.gender || r.пол || '',
          'ocr-birthplace': r.birth_place || r.место_рождения || '',
          'ocr-series': r.series || r.серия_паспорта || r.doc_series || '',
          'ocr-num': r.number || r.номер_паспорта || r.doc_number || '',
          'ocr-issue': r.issue_date || r.дата_выдачи || '',
          'ocr-issuer': r.issuer || r.кем_выдан || '',
          'ocr-expire': r.expiry_date || r.срок_действия || '',
        };
        Object.entries(fields).forEach(([id, val]) => {
          const el = document.getElementById(id);
          if (el) el.textContent = val || '—';
        });
        document.getElementById('ocr-result-fields').style.display = 'block';
      }

      // Always show raw
      const rawEl = document.getElementById('ocr-raw-text');
      if (rawEl) {
        rawEl.textContent = result.result?.raw || JSON.stringify(result.result, null, 2);
        document.getElementById('ocr-raw-result').style.display = 'block';
      }

      document.getElementById('ocr-actions').style.display = 'flex';
    } catch(e) {
      document.getElementById('ocr-loading').style.display = 'none';
      document.getElementById('ocr-placeholder').style.display = 'block';
      document.getElementById('ocr-placeholder').innerHTML = `<span style="color:var(--accent-red)">❌ Ошибка: ${escHtml(e.message)}</span>`;
      Toast.show('Ошибка OCR: ' + e.message, 'error');
    }
  },

  addToBase() {
    if (!this.lastResult) return;
    Toast.show('Добавление в базу: функция в разработке', 'info');
  },

  copyJSON() {
    if (!this.lastResult) return;
    navigator.clipboard.writeText(JSON.stringify(this.lastResult, null, 2))
      .then(() => Toast.show('JSON скопирован', 'success', 1500));
  },

  clear() {
    this.lastResult = null;
    document.getElementById('ocr-preview').style.display = 'none';
    document.getElementById('ocr-result-fields').style.display = 'none';
    document.getElementById('ocr-raw-result').style.display = 'none';
    document.getElementById('ocr-actions').style.display = 'none';
    document.getElementById('ocr-placeholder').style.display = 'block';
    document.getElementById('ocr-placeholder').textContent = 'Загрузите фото паспорта для распознавания';
    document.getElementById('ocr-input').value = '';
  },

  async batchProcess(files) {
    if (!files?.length) return;
    const container = document.getElementById('ocr-batch-results');
    container.innerHTML = `<div class="loading-overlay"><div class="spinner"></div> Обработка ${files.length} файлов...</div>`;

    const model = document.getElementById('ocr-model-select')?.value || 'glm-ocr:latest';
    const fd = new FormData();
    for (const f of files) fd.append('files', f);
    fd.append('doc_type', 'passport_ru');
    fd.append('model', model);

    try {
      const result = await apiUpload('/ocr/batch', fd);
      this.batchResults = result.results;
      container.innerHTML = `
        <div class="mini-table-card">
          <table>
            <thead><tr><th>Файл</th><th>Фамилия</th><th>Имя</th><th>Дата рождения</th><th>Серия</th><th>Номер</th></tr></thead>
            <tbody>${result.results.map(r => {
              const d = r.result || {};
              return `<tr>
                <td style="font-size:11px;color:var(--text-muted)">${escHtml(r.filename)}</td>
                <td>${escHtml(d.surname || d.фамилия || '—')}</td>
                <td>${escHtml(d.name || d.имя || '—')}</td>
                <td>${escHtml(d.birth_date || d.дата_рождения || '—')}</td>
                <td>${escHtml(d.series || d.серия_паспорта || '—')}</td>
                <td>${escHtml(d.number || d.номер_паспорта || '—')}</td>
              </tr>`;
            }).join('')}</tbody>
          </table>
        </div>`;
      Toast.show(`Обработано ${result.results.length} документов`, 'success');
    } catch(e) {
      container.innerHTML = `<div style="color:var(--accent-red)">Ошибка: ${escHtml(e.message)}</div>`;
    }
  },

  async exportBatch() {
    if (!this.batchResults.length) return Toast.show('Нет данных для экспорта', 'warning');
    const rows = this.batchResults.map(r => {
      const d = r.result || {};
      return [r.filename, d.surname || d.фамилия || '', d.name || d.имя || '',
              d.patronymic || '', d.birth_date || '', d.series || '', d.number || ''].join('\t');
    });
    const header = 'Файл\tФамилия\tИмя\tОтчество\tДата рождения\tСерия\tНомер';
    const csv = '\uFEFF' + [header, ...rows].join('\n');
    const blob = new Blob([csv], { type: 'text/tab-separated-values;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = 'Паспорта_OCR.tsv';
    a.click(); URL.revokeObjectURL(url);
  }
};

const OCRDocs = {
  async process(file) {
    if (!file) return;
    const preview = document.getElementById('doc-preview');
    const img = document.getElementById('doc-img');
    if (preview && img && file.type.startsWith('image/')) {
      img.src = URL.createObjectURL(file);
      preview.style.display = 'block';
    }

    document.getElementById('doc-result').style.display = 'none';
    document.getElementById('doc-placeholder').style.display = 'none';
    document.getElementById('doc-loading').style.display = 'flex';

    const docType = document.getElementById('doc-type-select')?.value || 'auto';
    const fd = new FormData();
    fd.append('file', file);
    fd.append('doc_type', docType);

    try {
      const result = await apiUpload('/ocr/document', fd);
      document.getElementById('doc-loading').style.display = 'none';
      const resultEl = document.getElementById('doc-result');
      resultEl.textContent = result.result?.raw || JSON.stringify(result.result, null, 2);
      resultEl.style.display = 'block';
      Toast.show('Документ распознан', 'success', 2000);
    } catch(e) {
      document.getElementById('doc-loading').style.display = 'none';
      document.getElementById('doc-placeholder').style.display = 'block';
      document.getElementById('doc-placeholder').innerHTML = `<span style="color:var(--accent-red)">❌ ${escHtml(e.message)}</span>`;
    }
  }
};

// Initialize OCR when passport tab opens
const _origSwitchTab = App.switchTab?.bind(App);
