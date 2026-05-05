/* Dashboard module */
const Dashboard = {
  async load() {
    try {
      const data = await api(`/dashboard/stats?status_op=${State.mode}&platform=${State.platform}`);
      const { stats, counts } = data;

      // KPIs
      const fmt = n => n?.toLocaleString('ru-RU') ?? '0';
      document.getElementById('kpi-total').textContent = fmt(counts.total);
      document.getElementById('kpi-active').textContent = fmt(counts.active_op);
      document.getElementById('kpi-finished').textContent = fmt(counts.finished_op);
      document.getElementById('kpi-itr').textContent = fmt(counts.itr);
      document.getElementById('kpi-workers').textContent = fmt(counts.workers);
      document.getElementById('kpi-foreign').textContent = fmt(counts.foreign);

      App.updateHeaderStats(counts);

      if (!stats.total) {
        document.querySelectorAll('#tab-dashboard canvas').forEach(c => {
          c.closest('.chart-card').querySelector('.card-title').insertAdjacentHTML('afterend',
            '<div style="color:var(--text-muted);font-size:11px;margin-top:4px">Нет данных — загрузите базу в Настройках</div>');
        });
        return;
      }

      // Charts
      Charts.pie('chart-citizenship', stats.by_citizenship.slice(0, 12));
      Charts.pie('chart-status', stats.by_status.slice(0, 10));
      Charts.pie('chart-class', stats.by_classification);

      // Dynamics
      const allMonths = [...new Set([
        ...stats.hire_by_month.map(d => d.label),
        ...stats.fire_by_month.map(d => d.label)
      ])].sort().slice(-18);

      Charts.line('chart-dynamics', [
        { label: 'Приём', data: allMonths.map(m => stats.hire_by_month.find(d => d.label === m)?.value || 0) },
        { label: 'Увольнение', data: allMonths.map(m => stats.fire_by_month.find(d => d.label === m)?.value || 0) },
      ], allMonths.map(m => m.replace(/^(\d{4})-/, '$1/')));

      // Orgs bar
      Charts.bar('chart-orgs', stats.by_org.slice(0, 12), { horizontal: true, color: '#3fb950' });

      // Mini tables
      document.getElementById('tbl-platforms').innerHTML =
        stats.by_platform.slice(0, 20).map(r =>
          `<tr><td>${escHtml(r.label)}</td><td style="text-align:right;font-weight:600">${fmtNum(r.value)}</td></tr>`
        ).join('');

      document.getElementById('tbl-schedules').innerHTML =
        stats.by_schedule.slice(0, 15).map(r =>
          `<tr><td>${escHtml(r.label)}</td><td style="text-align:right;font-weight:600">${fmtNum(r.value)}</td></tr>`
        ).join('');

    } catch(e) {
      Toast.show('Ошибка загрузки дашборда: ' + e.message, 'error');
    }
  }
};
