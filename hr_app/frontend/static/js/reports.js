/* Reports module */
const Reports = {
  currentReport: 'headcount',

  init() {
    document.querySelectorAll('.report-tab').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.report-tab').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        this.currentReport = btn.dataset.report;
        this.load();
      });
    });
  },

  load() {
    const r = this.currentReport;
    if (!r) return;
    const params = `status_op=${State.mode}&platform=${State.platform}`;
    switch(r) {
      case 'headcount': this._headcount(params); break;
      case 'citizenship': this._citizenship(params); break;
      case 'dynamics': this._dynamics(params); break;
      case 'age': this._age(params); break;
      case 'schedule': this._schedule(params); break;
      case 'position': this._position(params); break;
      case 'department': this._department(params); break;
      case 'foreign': this._foreign(params); break;
      case 'expiring': this._expiring(); break;
      case 'no-phone': this._noPhone(); break;
      case 'duplicates': this._duplicates(); break;
      case 'org-tree': this._orgTree(params); break;
    }
  },

  _setContent(html) {
    document.getElementById('report-content').innerHTML = html;
  },

  _loading() {
    this._setContent('<div class="loading-overlay"><div class="spinner"></div></div>');
  },

  async _headcount(params) {
    this._loading();
    try {
      const data = await api(`/reports/headcount?${params}`);
      const rows = data.rows;

      // Pivot: org → { ИТР, Рабочие, total }
      const orgs = {};
      rows.forEach(r => {
        if (!orgs[r.org]) orgs[r.org] = { ИТР: 0, Рабочие: 0 };
        orgs[r.org][r.classification] = (orgs[r.org][r.classification] || 0) + r.cnt;
      });

      const sorted = Object.entries(orgs).map(([org, d]) => ({
        org, itr: d['ИТР'] || 0, workers: d['Рабочие'] || 0,
        total: (d['ИТР'] || 0) + (d['Рабочие'] || 0)
      })).sort((a, b) => b.total - a.total);

      document.getElementById('report-info').textContent = `${sorted.length} организаций`;

      this._setContent(`
        <div class="charts-row charts-row-2" style="margin-bottom:16px">
          <div class="chart-card">
            <canvas id="rpt-chart-1"></canvas>
          </div>
          <div class="mini-table-card">
            <table>
              <thead><tr><th>Организация</th><th style="text-align:right">ИТР</th><th style="text-align:right">Рабочие</th><th style="text-align:right">Итого</th></tr></thead>
              <tbody>${sorted.map(r =>
                `<tr>
                  <td><strong>${escHtml(r.org || '—')}</strong></td>
                  <td style="text-align:right"><span class="badge badge-purple">${fmtNum(r.itr)}</span></td>
                  <td style="text-align:right"><span class="badge badge-blue">${fmtNum(r.workers)}</span></td>
                  <td style="text-align:right;font-weight:700">${fmtNum(r.total)}</td>
                </tr>`
              ).join('')}</tbody>
              <tfoot><tr style="background:var(--bg-panel)">
                <td><strong>ИТОГО</strong></td>
                <td style="text-align:right;font-weight:700">${fmtNum(sorted.reduce((s,r)=>s+r.itr,0))}</td>
                <td style="text-align:right;font-weight:700">${fmtNum(sorted.reduce((s,r)=>s+r.workers,0))}</td>
                <td style="text-align:right;font-weight:700">${fmtNum(sorted.reduce((s,r)=>s+r.total,0))}</td>
              </tr></tfoot>
            </table>
          </div>
        </div>`);

      Charts.bar('rpt-chart-1', sorted.slice(0,15).map(r => ({ label: r.org, value: r.total })),
        { horizontal: true, color: '#58a6ff' });

    } catch(e) { this._setContent(`<div style="color:var(--accent-red);padding:20px">Ошибка: ${escHtml(e.message)}</div>`); }
  },

  async _citizenship(params) {
    this._loading();
    try {
      const data = await api(`/reports/citizenship?${params}`);
      // Group by citizenship
      const groups = {};
      data.rows.forEach(r => {
        if (!groups[r.citizenship]) groups[r.citizenship] = 0;
        groups[r.citizenship] += r.cnt;
      });
      const sorted = Object.entries(groups).map(([label, value]) => ({ label, value }))
        .sort((a, b) => b.value - a.value);

      document.getElementById('report-info').textContent = `${sorted.length} гражданств`;
      this._setContent(`
        <div class="charts-row charts-row-2" style="margin-bottom:16px">
          <div class="chart-card"><canvas id="rpt-citizenship-chart"></canvas></div>
          <div class="mini-table-card">
            <table>
              <thead><tr><th>Гражданство</th><th style="text-align:right">Чел.</th><th style="text-align:right">%</th></tr></thead>
              <tbody>${(() => {
                const total = sorted.reduce((s,r) => s+r.value, 0);
                return sorted.map(r =>
                  `<tr><td>${citizenBadge(r.label)}</td>
                   <td style="text-align:right;font-weight:600">${fmtNum(r.value)}</td>
                   <td style="text-align:right;color:var(--text-muted)">${total ? (r.value/total*100).toFixed(1)+'%' : '—'}</td></tr>`
                ).join('');
              })()}</tbody>
            </table>
          </div>
        </div>`);
      Charts.pie('rpt-citizenship-chart', sorted);
    } catch(e) { this._setContent(`<div style="color:var(--accent-red);padding:20px">Ошибка: ${e.message}</div>`); }
  },

  async _dynamics(params) {
    this._loading();
    try {
      const data = await api(`/reports/dynamics?${params}`);
      const allMonths = [...new Set([
        ...data.hire.map(d => d.label),
        ...data.fire.map(d => d.label)
      ])].sort();

      this._setContent(`
        <div class="chart-card" style="margin-bottom:16px">
          <div class="card-header"><div class="card-title">📈 Динамика приёма и увольнения</div></div>
          <canvas id="rpt-dynamics-chart" style="max-height:300px"></canvas>
        </div>
        <div class="charts-row charts-row-2">
          <div class="mini-table-card">
            <div style="padding:8px 12px;font-size:12px;font-weight:600;border-bottom:1px solid var(--border)">Приём по месяцам</div>
            <div style="max-height:300px;overflow-y:auto">
              <table><thead><tr><th>Месяц</th><th style="text-align:right">Чел.</th></tr></thead>
              <tbody>${data.hire.slice(-24).reverse().map(r =>
                `<tr><td>${r.label}</td><td style="text-align:right;color:var(--accent-green);font-weight:600">${fmtNum(r.value)}</td></tr>`
              ).join('')}</tbody></table>
            </div>
          </div>
          <div class="mini-table-card">
            <div style="padding:8px 12px;font-size:12px;font-weight:600;border-bottom:1px solid var(--border)">Увольнения по месяцам</div>
            <div style="max-height:300px;overflow-y:auto">
              <table><thead><tr><th>Месяц</th><th style="text-align:right">Чел.</th></tr></thead>
              <tbody>${data.fire.slice(-24).reverse().map(r =>
                `<tr><td>${r.label}</td><td style="text-align:right;color:var(--accent-red);font-weight:600">${fmtNum(r.value)}</td></tr>`
              ).join('')}</tbody></table>
            </div>
          </div>
        </div>`);

      Charts.line('rpt-dynamics-chart', [
        { label: 'Приём', data: allMonths.map(m => data.hire.find(d => d.label === m)?.value || 0) },
        { label: 'Увольнение', data: allMonths.map(m => data.fire.find(d => d.label === m)?.value || 0) },
      ], allMonths.map(m => m.replace(/^(\d{4})-(\d{2})$/, (_, y, mo) => `${mo}/${y}`)));

    } catch(e) { this._setContent(`<div style="color:var(--accent-red);padding:20px">Ошибка: ${e.message}</div>`); }
  },

  async _age(params) {
    this._loading();
    try {
      const data = await api(`/reports/age-structure?${params}`);
      this._setContent(`
        <div class="charts-row charts-row-2">
          <div class="chart-card"><canvas id="rpt-age-chart"></canvas></div>
          <div class="mini-table-card">
            <table>
              <thead><tr><th>Возрастная группа</th><th style="text-align:right">Чел.</th></tr></thead>
              <tbody>${data.rows.map(r =>
                `<tr><td><strong>${r.age_group}</strong> лет</td>
                 <td style="text-align:right;font-weight:600">${fmtNum(r.cnt)}</td></tr>`
              ).join('')}</tbody>
            </table>
          </div>
        </div>`);
      Charts.bar('rpt-age-chart', data.rows.map(r => ({ label: r.age_group, value: r.cnt })),
        { color: ['#58a6ff','#3fb950','#d29922','#f85149','#bc8cff'] });
    } catch(e) { this._setContent(`<div style="color:var(--accent-red);padding:20px">Ошибка: ${e.message}</div>`); }
  },

  async _schedule(params) {
    this._loading();
    try {
      const data = await api(`/reports/by-schedule?${params}`);
      this._setContent(`
        <div class="charts-row charts-row-2">
          <div class="chart-card"><canvas id="rpt-sched-chart"></canvas></div>
          <div class="mini-table-card">
            <table>
              <thead><tr><th>График работы</th><th style="text-align:right">Чел.</th></tr></thead>
              <tbody>${data.rows.slice(0,30).map(r =>
                `<tr><td>${escHtml(r.work_schedule || '—')}</td>
                 <td style="text-align:right;font-weight:600">${fmtNum(r.cnt)}</td></tr>`
              ).join('')}</tbody>
            </table>
          </div>
        </div>`);
      Charts.bar('rpt-sched-chart', data.rows.slice(0,15).map(r =>
        ({ label: r.work_schedule || '—', value: r.cnt })),
        { horizontal: true, color: '#d29922' });
    } catch(e) { this._setContent(`<div style="color:var(--accent-red);padding:20px">Ошибка: ${e.message}</div>`); }
  },

  async _position(params) {
    this._loading();
    try {
      const data = await api(`/reports/by-position?${params}&limit=30`);
      this._setContent(`
        <div class="mini-table-card">
          <table>
            <thead><tr><th>#</th><th>Должность</th><th style="text-align:right">Чел.</th></tr></thead>
            <tbody>${data.rows.map((r, i) =>
              `<tr><td style="color:var(--text-muted)">${i+1}</td>
               <td>${escHtml(r.position || '—')}</td>
               <td style="text-align:right;font-weight:600">${fmtNum(r.cnt)}</td></tr>`
            ).join('')}</tbody>
          </table>
        </div>`);
      document.getElementById('report-info').textContent = `ТОП-${data.rows.length} должностей`;
    } catch(e) { this._setContent(`<div style="color:var(--accent-red);padding:20px">Ошибка: ${e.message}</div>`); }
  },

  async _department(params) {
    this._loading();
    try {
      const data = await api(`/reports/by-department?${params}`);
      this._setContent(`
        <div class="data-table-wrap">
          <div class="dt-wrapper">
            <table class="dt-table">
              <thead><tr><th>Подразделение</th><th>Организация</th><th>Классификация</th><th style="text-align:right">Чел.</th></tr></thead>
              <tbody>${data.rows.map(r =>
                `<tr>
                  <td>${escHtml(r.department || '—')}</td>
                  <td style="color:var(--text-muted)">${escHtml(r.org || '—')}</td>
                  <td>${r.classification === 'ИТР' ? '<span class="badge badge-purple">ИТР</span>' : '<span class="badge badge-blue">Рабочие</span>'}</td>
                  <td style="text-align:right;font-weight:600">${fmtNum(r.cnt)}</td>
                </tr>`
              ).join('')}</tbody>
            </table>
          </div>
        </div>`);
      document.getElementById('report-info').textContent = `${data.rows.length} записей`;
    } catch(e) { this._setContent(`<div style="color:var(--accent-red);padding:20px">Ошибка: ${e.message}</div>`); }
  },

  async _foreign(params) {
    this._loading();
    try {
      const data = await api(`/reports/foreign-workers?${params}`);
      document.getElementById('report-info').textContent = `${fmtNum(data.total)} иностранных сотрудников`;
      this._setContent(`
        <div class="data-table-wrap">
          <div class="dt-wrapper" style="max-height:500px">
            <table class="dt-table">
              <thead><tr><th>ФИО</th><th>Табном</th><th>Гражданство</th><th>№ Документа</th>
                <th>Дата выдачи</th><th>Срок визы</th><th>Площадка</th><th>Подразделение</th><th>Статус</th></tr></thead>
              <tbody>${data.rows.map(r =>
                `<tr>
                  <td><strong>${escHtml(r.fio)}</strong></td>
                  <td style="color:var(--text-muted)">${escHtml(r.tab_num)}</td>
                  <td>${citizenBadge(r.citizenship)}</td>
                  <td>${escHtml(r.doc_num)}</td>
                  <td>${escHtml(r.doc_issue_date)}</td>
                  <td style="${r.visa_expire_eju ? 'color:var(--accent-orange)' : ''}">${escHtml(r.visa_expire_eju)}</td>
                  <td>${escHtml(r.platform_eju)}</td>
                  <td>${escHtml(r.department)}</td>
                  <td>${statusBadge(r.status)}</td>
                </tr>`
              ).join('')}</tbody>
            </table>
          </div>
        </div>`);
    } catch(e) { this._setContent(`<div style="color:var(--accent-red);padding:20px">Ошибка: ${e.message}</div>`); }
  },

  async _expiring() {
    this._loading();
    try {
      const data = await api('/reports/expiring-docs?days=90');
      document.getElementById('report-info').textContent = `${fmtNum(data.total)} документов истекает в 90 дней`;
      this._setContent(`
        <div class="data-table-wrap">
          <div class="dt-wrapper" style="max-height:500px">
            <table class="dt-table">
              <thead><tr><th>ФИО</th><th>Табном</th><th>Гражданство</th><th>№ Документа</th>
                <th>Срок визы/разрешения</th><th>Площадка</th><th>Подразделение</th></tr></thead>
              <tbody>${data.rows.length ? data.rows.map(r =>
                `<tr>
                  <td><strong>${escHtml(r.fio)}</strong></td>
                  <td>${escHtml(r.tab_num)}</td>
                  <td>${citizenBadge(r.citizenship)}</td>
                  <td>${escHtml(r.doc_num)}</td>
                  <td style="color:var(--accent-red);font-weight:600">${escHtml(r.visa_expire_eju)}</td>
                  <td>${escHtml(r.platform_eju)}</td>
                  <td>${escHtml(r.department)}</td>
                </tr>`
              ).join('') : '<tr><td colspan="7" style="text-align:center;padding:30px;color:var(--accent-green)">✅ Нет истекающих документов в ближайшие 90 дней</td></tr>'}</tbody>
            </table>
          </div>
        </div>`);
    } catch(e) { this._setContent(`<div style="color:var(--accent-red);padding:20px">Ошибка: ${e.message}</div>`); }
  },

  async _noPhone() {
    this._loading();
    try {
      const data = await api('/reports/no-phone');
      document.getElementById('report-info').textContent = `${fmtNum(data.total)} без телефона`;
      this._setContent(`
        <div class="data-table-wrap">
          <div class="dt-wrapper" style="max-height:500px">
            <table class="dt-table">
              <thead><tr><th>ФИО</th><th>Табном</th><th>Подразделение</th><th>Площадка</th><th>Гражданство</th><th>Статус</th></tr></thead>
              <tbody>${data.rows.map(r =>
                `<tr>
                  <td><strong>${escHtml(r.fio)}</strong></td>
                  <td>${escHtml(r.tab_num)}</td>
                  <td>${escHtml(r.department)}</td>
                  <td>${escHtml(r.platform_eju)}</td>
                  <td>${citizenBadge(r.citizenship)}</td>
                  <td>${statusBadge(r.status)}</td>
                </tr>`
              ).join('')}</tbody>
            </table>
          </div>
        </div>`);
    } catch(e) { this._setContent(`<div style="color:var(--accent-red);padding:20px">Ошибка: ${e.message}</div>`); }
  },

  async _duplicates() {
    this._loading();
    try {
      const data = await api('/reports/duplicates');
      document.getElementById('report-info').textContent = `${fmtNum(data.total)} дублирующихся записей`;
      this._setContent(`
        <div class="data-table-wrap">
          <div class="dt-wrapper" style="max-height:500px">
            <table class="dt-table">
              <thead><tr><th>ФИО</th><th>Дата рождения</th><th>Кол-во</th><th>Табельные номера</th></tr></thead>
              <tbody>${data.rows.map(r =>
                `<tr>
                  <td><strong style="color:var(--accent-red)">${escHtml(r.fio)}</strong></td>
                  <td>${escHtml(r.birth_date)}</td>
                  <td><span class="badge badge-red">${r.cnt}</span></td>
                  <td style="color:var(--text-muted);font-size:11px">${escHtml(r.tabs)}</td>
                </tr>`
              ).join('')}</tbody>
            </table>
          </div>
        </div>`);
    } catch(e) { this._setContent(`<div style="color:var(--accent-red);padding:20px">Ошибка: ${e.message}</div>`); }
  },

  async _orgTree(params) {
    this._loading();
    try {
      const data = await api(`/reports/org-tree?${params}`);
      const buildTree = (tree) => {
        return Object.values(tree).map(org => `
          <details style="margin-bottom:6px" open>
            <summary style="cursor:pointer;padding:8px 12px;background:var(--bg-panel);border-radius:4px;display:flex;align-items:center;gap:8px">
              <span style="font-weight:600">🏢 ${escHtml(org.name)}</span>
              <span class="badge badge-blue">${fmtNum(org.count)}</span>
            </summary>
            <div style="padding-left:20px;margin-top:4px">
              ${Object.values(org.children || {}).map(dept => `
                <details style="margin-bottom:4px">
                  <summary style="cursor:pointer;padding:5px 10px;background:var(--bg-card);border-radius:4px;display:flex;align-items:center;gap:6px">
                    <span>📁 ${escHtml(dept.name)}</span>
                    <span class="badge badge-gray">${fmtNum(dept.count)}</span>
                  </summary>
                  <div style="padding-left:20px;margin-top:2px">
                    ${Object.entries(dept.children || {}).slice(0,10).map(([pos, cnt]) =>
                      `<div style="display:flex;justify-content:space-between;padding:3px 8px;border-bottom:1px solid var(--border)">
                        <span style="font-size:11px;color:var(--text-secondary)">👤 ${escHtml(pos)}</span>
                        <span style="font-size:11px;font-weight:600">${fmtNum(cnt)}</span>
                      </div>`
                    ).join('')}
                  </div>
                </details>`
              ).join('')}
            </div>
          </details>`
        ).join('');
      };
      this._setContent(`<div style="max-height:600px;overflow-y:auto">${buildTree(data.tree)}</div>`);
    } catch(e) { this._setContent(`<div style="color:var(--accent-red);padding:20px">Ошибка: ${e.message}</div>`); }
  },

  exportExcel() {
    apiDownload(`/reports/export-excel/${this.currentReport}?status_op=${State.mode}&platform=${State.platform}`)
      .then(() => Toast.show('Файл скачан', 'success'))
      .catch(e => Toast.show('Ошибка экспорта: ' + e.message, 'error'));
  }
};

// Init on tab switch
document.addEventListener('DOMContentLoaded', () => {
  Reports.init();
});
