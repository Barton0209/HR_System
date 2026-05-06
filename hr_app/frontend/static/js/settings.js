/* Settings module */
const Settings = {
  async load() {
    await Promise.all([this.loadDbInfo(), this.loadOllamaStatus(), this.loadLog()]);
  },

  async loadDbInfo() {
    try {
      const data = await api('/settings/db-info');
      const el = document.getElementById('db-info-content');
      const baseInfo = document.getElementById('base-info');
      if (baseInfo) {
        if (data.main_base_name && data.main_base_name !== 'не загружена') {
          baseInfo.innerHTML = `<span style="color:var(--accent-green)">✅ ${escHtml(data.main_base_name)}</span> · ${fmtNum(data.employees.total)} сотрудников`;
        } else {
          baseInfo.innerHTML = `<span style="color:var(--accent-orange)">⚠️ База не загружена</span>`;
        }
      }
      if (!el) return;
      el.innerHTML = `
        <div style="display:grid;gap:8px">
          ${[
            ['База данных', data.db_path],
            ['Размер БД', `${data.db_size_mb} МБ`],
            ['Файл базы', data.main_base_name],
            ['Всего сотрудников', fmtNum(data.employees.total)],
            ['Активные ОП', fmtNum(data.employees.active_op)],
            ['Завершённые ОП', fmtNum(data.employees.finished_op)],
            ['ИТР', fmtNum(data.employees.itr)],
            ['Рабочие', fmtNum(data.employees.workers)],
          ].map(([k, v]) => `
            <div style="display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid var(--border)">
              <span style="color:var(--text-muted);font-size:11px">${k}</span>
              <span style="font-weight:600;font-size:12px">${v}</span>
            </div>`).join('')}
        </div>`;
    } catch(e) {
      const el = document.getElementById('db-info-content');
      if (el) el.innerHTML = `<div style="color:var(--accent-red);font-size:12px">Ошибка загрузки</div>`;
    }
  },

  async loadOllamaStatus() {
    try {
      const data = await api('/ocr/status');
      const el = document.getElementById('ollama-status-content');
      if (!el) return;
      if (data.available) {
        el.innerHTML = `
          <div style="color:var(--accent-green);margin-bottom:8px">✅ Ollama работает</div>
          <div style="font-size:11px;color:var(--text-muted);margin-bottom:6px">Доступные модели:</div>
          <div style="display:flex;flex-wrap:wrap;gap:4px">
            ${data.models.map(m =>
              `<span class="badge badge-${m.includes('glm-ocr') || m.includes('qwen2.5vl') ? 'green' : 'gray'}">${escHtml(m)}</span>`
            ).join('')}
          </div>`;
      } else {
        el.innerHTML = `
          <div style="color:var(--accent-red);margin-bottom:8px">❌ Ollama недоступен</div>
          <div style="font-size:11px;color:var(--text-muted)">Запустите: <code style="background:var(--bg-panel);padding:2px 5px;border-radius:3px">ollama serve</code></div>`;
      }
    } catch(e) {}
  },

  async loadLog() {
    try {
      const data = await api('/settings/load-log?limit=20');
      const tbody = document.getElementById('load-log-tbody');
      if (!tbody) return;
      if (!data.log.length) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:12px;color:var(--text-muted)">Нет операций</td></tr>';
        return;
      }
      tbody.innerHTML = data.log.map(r => `<tr>
        <td style="font-size:10px;color:var(--text-muted)">${escHtml((r.created_at || '').slice(0, 16))}</td>
        <td>${escHtml(r.action || '')}</td>
        <td style="max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${escHtml(r.filename || '')}">${escHtml(r.filename || '')}</td>
        <td style="text-align:right">${fmtNum(r.rows_count)}</td>
        <td><span class="badge ${r.status === 'ok' ? 'badge-green' : 'badge-red'}">${escHtml(r.status)}</span></td>
      </tr>`).join('');
    } catch(e) {}
  },

  async uploadMainBase(file) {
    if (!file) return;
    const fd = new FormData();
    fd.append('file', file);
    Toast.show(`Загрузка ${file.name} (${(file.size/1024/1024).toFixed(1)} МБ)...`, 'info', 5000);
    try {
      const result = await apiUpload('/settings/upload-main-base', fd);
      if (result.ok) {
        Toast.show(`✅ ${result.message}`, 'success', 5000);
        this.loadDbInfo();
        App.loadFilters();
        App.updateHeaderStats({ total: result.count });
      } else {
        Toast.show('❌ ' + result.message, 'error', 6000);
      }
    } catch(e) {
      Toast.show('Ошибка загрузки: ' + e.message, 'error');
    }
  },

  async uploadPasswordAccess(file) {
    if (!file) return;
    const fd = new FormData();
    fd.append('file', file);
    Toast.show(`Загрузка ${file.name}...`, 'info', 3000);
    try {
      const result = await apiUpload('/settings/upload-password-access', fd);
      if (result.ok) {
        Toast.show(`✅ ${result.message}`, 'success', 4000);
        this.loadLog();
      } else {
        Toast.show('❌ ' + result.message, 'error', 5000);
      }
    } catch(e) {
      Toast.show('Ошибка загрузки: ' + e.message, 'error');
    }
  },

  async uploadDepartments(file) {
    if (!file) return;
    const fd = new FormData();
    fd.append('file', file);
    Toast.show(`Загрузка ${file.name}...`, 'info', 3000);
    try {
      const result = await apiUpload('/settings/upload-departments', fd);
      if (result.ok) {
        Toast.show(`✅ ${result.message}`, 'success', 4000);
        this.loadLog();
      } else {
        Toast.show('❌ ' + result.message, 'error', 5000);
      }
    } catch(e) {
      Toast.show('Ошибка загрузки: ' + e.message, 'error');
    }
  },

  async uploadAreas(file) {
    if (!file) return;
    const fd = new FormData();
    fd.append('file', file);
    Toast.show(`Загрузка ${file.name}...`, 'info', 3000);
    try {
      const result = await apiUpload('/settings/upload-areas', fd);
      if (result.ok) {
        Toast.show(`✅ ${result.message}`, 'success', 4000);
        this.loadLog();
      } else {
        Toast.show('❌ ' + result.message, 'error', 5000);
      }
    } catch(e) {
      Toast.show('Ошибка загрузки: ' + e.message, 'error');
    }
  },

  async uploadPositions(file) {
    if (!file) return;
    const fd = new FormData();
    fd.append('file', file);
    Toast.show(`Загрузка ${file.name}...`, 'info', 3000);
    try {
      const result = await apiUpload('/settings/upload-positions', fd);
      if (result.ok) {
        Toast.show(`✅ ${result.message}`, 'success', 4000);
        this.loadLog();
      } else {
        Toast.show('❌ ' + result.message, 'error', 5000);
      }
    } catch(e) {
      Toast.show('Ошибка загрузки: ' + e.message, 'error');
    }
  },

  async uploadRoutes(file) {
    if (!file) return;
    const fd = new FormData();
    fd.append('file', file);
    try {
      const result = await apiUpload('/settings/upload-routes', fd);
      Toast.show(`Маршруты загружены: ${result.count}`, 'success');
    } catch(e) { Toast.show('Ошибка: ' + e.message, 'error'); }
  },

  async uploadTicketCosts(files) {
    if (!files?.length) return;
    const fd = new FormData();
    for (const f of files) fd.append('files', f);
    Toast.show('Загрузка реестров...', 'info', 2000);
    try {
      const result = await apiUpload('/settings/upload-ticket-costs', fd);
      Toast.show(result.message, 'success');
      this.loadLog();
    } catch(e) { Toast.show('Ошибка: ' + e.message, 'error'); }
  },

  async generateTotalExperienceReport() {
    Toast.show('Генерация отчета ОБЩИЙ_СТАЖ.xlsx...', 'info', 3000);
    try {
      const result = await api('/settings/generate-total-experience-report', { method: 'POST' });
      if (result.ok) {
        Toast.show(`✅ ${result.message}`, 'success', 4000);
        window.open('/settings/download-report/ОБЩИЙ_СТАЖ.xlsx', '_blank');
        this.loadLog();
      } else {
        Toast.show('❌ ' + result.message, 'error', 5000);
      }
    } catch(e) {
      Toast.show('Ошибка генерации: ' + e.message, 'error');
    }
  },

  async generateTicketCostsReport() {
    Toast.show('Генерация отчета Реестр_по_затратам_на_билеты.xlsx...', 'info', 3000);
    try {
      const result = await api('/settings/generate-ticket-costs-report', { method: 'POST' });
      if (result.ok) {
        Toast.show(`✅ ${result.message}`, 'success', 4000);
        window.open('/settings/download-report/Реестр_по_затратам_на_билеты.xlsx', '_blank');
        this.loadLog();
      } else {
        Toast.show('❌ ' + result.message, 'error', 5000);
      }
    } catch(e) {
      Toast.show('Ошибка генерации: ' + e.message, 'error');
    }
  },

  async reloadBase() {
    Toast.show('Перезагрузка базы...', 'info', 2000);
    try {
      const result = await api('/settings/reload-main-base', { method: 'POST' });
      Toast.show(result.message, result.ok ? 'success' : 'error', 4000);
      if (result.ok) { this.loadDbInfo(); App.loadFilters(); }
    } catch(e) { Toast.show('Ошибка: ' + e.message, 'error'); }
  },

  saveOllamaUrl() {
    const url = document.getElementById('ollama-url-input')?.value;
    if (!url) return;
    const fd = new FormData();
    fd.append('key', 'ollama_url'); fd.append('value', url);
    apiUpload('/settings/set', fd).then(() => {
      Toast.show('URL сохранён. Перезапустите сервер.', 'success');
    });
  }
};
