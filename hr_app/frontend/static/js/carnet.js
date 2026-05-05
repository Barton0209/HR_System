/* ═══════════════════════════════════════════════════════════════
   Карнет — Объединение Excel-карнетов
   Веб-версия MergeCarnetTab из FolderForge Pro / cedicos
   ═══════════════════════════════════════════════════════════════ */

const Carnet = (() => {
  /* state */
  let _files = [];       // [{name, type, sheets:[{name,headers,hidden,header_row,selected,max_col}]}]
  let _tableRows = [];   // [{fileIdx, sheetIdx, colIdx, fileName, sheetName, headerName, headerRow, colNum, status, targetField}]
  let _requiredFields = [];
  let _uploadedFileObjects = {}; // name -> File object (kept for merge)

  /* ─── init ───────────────────────────────────────────────── */
  function init() {
    _renderFileList();
    _renderTable();
    _populateDatalist();
  }

  function _populateDatalist() {
    const dl = document.getElementById('carnet-fields-list');
    if (!dl) return;
    if (dl.children.length) return;
    const fields = _requiredFields.length ? _requiredFields : [
      "Табельный номер","Фактическая должность","Участок по факту","Прораб",
      "Позиция","ДЕНЬ/НОЧЬ","да/нет","ОП/Проект","Оценка","ФИО",
      "Гражданство","Должность","Разряд","Подразделение","Компания","ИТР",
      "Сектор","Вид работ","Виза/ гражданство","Удостоверение Серия","Удостоверение Номер",
      "1","2","3","4","5","6","7","8","9","10","11","12","13","14","15",
      "16","17","18","19","20","21","22","23","24","25","26","27","28","29","30","31",
      "ПРИМЕЧАНИЕ","Итого произв. Часов","Итого актираных часов",
    ];
    dl.innerHTML = fields.map(f => `<option value="${escHtml(f)}">`).join('');
  }

  /* ─── file upload ────────────────────────────────────────── */
  async function openFiles() {
    const input = document.getElementById('carnet-file-input');
    input.value = '';
    input.click();
  }

  async function onFilesSelected(input) {
    const fileList = Array.from(input.files);
    if (!fileList.length) return;
    await _scanFiles(fileList);
  }

  async function _scanFiles(fileList) {
    _setStatus('Загрузка файлов…');
    const fd = new FormData();
    fileList.forEach(f => {
      fd.append('files', f, f.name);
      _uploadedFileObjects[f.name] = f;
    });

    try {
      const res = await fetch('/api/carnet/scan', { method: 'POST', body: fd });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      _requiredFields = data.required_fields || [];

      data.files.forEach(f => {
        const existing = _files.findIndex(x => x.name === f.name);
        if (existing >= 0) _files[existing] = f;
        else _files.push(f);
      });

      _renderFileList();
      _setStatus(`Загружено файлов: ${_files.length}`);
    } catch (e) {
      _setStatus('Ошибка: ' + e.message);
    }
  }

  /* ─── file list (left panel) ──────────────────────────────── */
  function _renderFileList() {
    const ul = document.getElementById('carnet-file-list');
    if (!ul) return;
    ul.innerHTML = '';
    if (!_files.length) {
      ul.innerHTML = '<li class="carnet-empty">Нет файлов — нажмите «Файлы»</li>';
      document.getElementById('carnet-file-count').textContent = '0';
      return;
    }
    document.getElementById('carnet-file-count').textContent = String(_files.length);

    _files.forEach((file, fi) => {
      const icons = { xlsx: '📊', xls: '📄', xlsm: '⚙️', xlsb: '⚡' };
      const ico = icons[file.type] || '📊';
      const li = document.createElement('li');
      li.className = 'carnet-file-item';
      li.innerHTML = `<div class="carnet-file-name">${ico} ${escHtml(file.name)}</div>`;
      if (file.error) {
        li.innerHTML += `<div class="carnet-sheet-item err">⚠️ ${escHtml(file.error)}</div>`;
      } else {
        (file.sheets || []).forEach((sheet, si) => {
          const shIco = sheet.hidden ? '🚫' : '📄';
          const chk = document.createElement('div');
          chk.className = 'carnet-sheet-item';
          chk.innerHTML = `
            <label class="carnet-sheet-label">
              <input type="checkbox" ${sheet.selected ? 'checked' : ''}
                onchange="Carnet._toggleSheet(${fi},${si},this.checked)">
              ${shIco} ${escHtml(sheet.name)}
              <span class="carnet-sheet-meta">(${sheet.max_col} кол, строка&nbsp;
                <select class="carnet-hrow-sel" onchange="Carnet._setHeaderRow(${fi},${si},this.value)">
                  ${[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15].map(n =>
                    `<option value="${n}" ${sheet.header_row === n ? 'selected' : ''}>${n}</option>`
                  ).join('')}
                </select>)
              </span>
            </label>`;
          li.appendChild(chk);
        });
      }
      ul.appendChild(li);
    });
  }

  function _toggleSheet(fi, si, checked) {
    if (_files[fi] && _files[fi].sheets[si]) {
      _files[fi].sheets[si].selected = checked;
    }
  }

  function _setHeaderRow(fi, si, val) {
    if (_files[fi] && _files[fi].sheets[si]) {
      _files[fi].sheets[si].header_row = parseInt(val, 10);
    }
  }

  function selectAll() {
    _files.forEach(f => (f.sheets || []).forEach(s => { s.selected = true; }));
    _renderFileList();
  }

  function clearFileList() {
    _files = [];
    _uploadedFileObjects = {};
    _tableRows = [];
    _renderFileList();
    _renderTable();
    _setStatus('—');
  }

  /* ─── generate headers table (middle panel) ──────────────── */
  function generateHeaders() {
    _tableRows = [];
    _files.forEach((file, fi) => {
      (file.sheets || []).forEach((sheet, si) => {
        if (!sheet.selected) return;
        const headers = sheet.headers || [];
        headers.forEach((hdr, ci) => {
          _tableRows.push({
            fileIdx: fi, sheetIdx: si, colIdx: ci,
            fileName: file.name,
            sheetName: sheet.name,
            headerName: hdr,
            headerRow: sheet.header_row,
            colNum: ci + 1,
            status: sheet.hidden ? 'Скрытый' : 'Видимый',
            targetField: '',
          });
        });
      });
    });
    _renderTable();
    document.getElementById('carnet-row-count').textContent = 'Строк: ' + _tableRows.length;
  }

  function _renderTable() {
    const tbody = document.getElementById('carnet-map-tbody');
    if (!tbody) return;
    if (!_tableRows.length) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:24px;color:var(--text-muted)">Нажмите «Заголовки» после выбора файлов</td></tr>';
      return;
    }
    tbody.innerHTML = _tableRows.map((r, i) => `
      <tr class="${r.status === 'Скрытый' ? 'carnet-row-hidden' : ''}">
        <td title="${escHtml(r.fileName)}">${escHtml(r.fileName.length > 22 ? r.fileName.slice(0,20)+'…' : r.fileName)}</td>
        <td title="${escHtml(r.sheetName)} / строка ${r.headerRow}">${escHtml(r.headerName)}</td>
        <td style="text-align:center">${r.headerRow}</td>
        <td style="text-align:center">${r.colNum}</td>
        <td style="text-align:center">
          <span class="carnet-status-badge ${r.status === 'Скрытый' ? 'hidden' : 'visible'}">${r.status}</span>
        </td>
        <td>
          <input class="carnet-target-input" type="text"
            value="${escHtml(r.targetField)}"
            list="carnet-fields-list"
            oninput="Carnet._setTarget(${i}, this.value)"
            placeholder="—">
        </td>
      </tr>`).join('');
  }

  function _setTarget(i, val) {
    if (_tableRows[i]) _tableRows[i].targetField = val;
  }

  /* ─── auto-fill target fields ────────────────────────────── */
  function autoFill() {
    if (!_tableRows.length) { _setStatus('Сначала нажмите «Заголовки»'); return; }
    const rfSet = new Set(_requiredFields);
    let filled = 0;
    _tableRows.forEach(r => {
      if (rfSet.has(r.headerName.trim())) {
        r.targetField = r.headerName.trim();
        filled++;
      }
    });
    _renderTable();
    _setStatus(`Автозаполнено: ${filled} полей`);
  }

  /* ─── check required fields ─────────────────────────────── */
  function checkFields() {
    if (!_tableRows.length) { _setStatus('Сначала нажмите «Заголовки»'); return; }
    const byFile = {};
    _tableRows.forEach(r => {
      if (!byFile[r.fileName]) byFile[r.fileName] = new Set();
      if (r.targetField.trim()) byFile[r.fileName].add(r.targetField.trim());
    });

    const lines = [];
    let allOk = true;
    for (const [fname, fields] of Object.entries(byFile)) {
      const missing = _requiredFields.filter(f => !fields.has(f));
      if (missing.length) {
        allOk = false;
        lines.push(`❌ ${fname}: отсутствуют ${missing.length > 4 ? missing.length + ' полей' : missing.join(', ')}`);
      } else {
        lines.push(`✅ ${fname}: все обязательные поля есть`);
      }
    }

    const log = document.getElementById('carnet-log');
    if (log) {
      log.textContent = lines.join('\n');
      log.style.color = allOk ? 'var(--success)' : 'var(--danger)';
    }
    _setStatus(allOk ? 'Проверка пройдена ✅' : 'Есть пропущенные поля ❌');
  }

  /* ─── merge ─────────────────────────────────────────────── */
  async function merge() {
    if (!_tableRows.length) { _setStatus('Нет данных для объединения'); return; }

    const bySheetKey = {};
    _tableRows.forEach(r => {
      const key = r.fileName + '|||' + r.sheetName;
      if (!bySheetKey[key]) {
        bySheetKey[key] = {
          filename: r.fileName,
          sheet: r.sheetName,
          header_row: r.headerRow,
          columns: [],
        };
      }
      if (r.targetField.trim()) {
        bySheetKey[key].columns.push({
          src_header: r.headerName,
          target_field: r.targetField.trim(),
        });
      }
    });

    const mapping = Object.values(bySheetKey).filter(e => e.columns.length > 0);
    if (!mapping.length) { _setStatus('Нет целевых полей — заполните «Целевое поле»'); return; }

    const fd = new FormData();
    fd.append('mapping_json', JSON.stringify(mapping));

    const fileNames = [...new Set(mapping.map(e => e.filename))];
    let missingFiles = [];
    fileNames.forEach(name => {
      const f = _uploadedFileObjects[name];
      if (f) fd.append('files', f, name);
      else missingFiles.push(name);
    });
    if (missingFiles.length) {
      _setStatus('Файлы не найдены в памяти: ' + missingFiles.join(', ') + '. Перезагрузите файлы.');
      return;
    }

    _setStatus('Объединение…');
    const log = document.getElementById('carnet-log');
    if (log) { log.textContent = '⏳ Объединяю…'; log.style.color = ''; }

    try {
      const res = await fetch('/api/carnet/merge', { method: 'POST', body: fd });
      if (!res.ok) {
        const err = await res.text();
        throw new Error(err);
      }
      const rowCount = res.headers.get('X-Row-Count') || '?';
      const logData = res.headers.get('X-Merge-Log');
      let logLines = [];
      try { logLines = JSON.parse(logData || '[]'); } catch {}

      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'Итоговый_карнет.xlsx';
      a.click();
      URL.revokeObjectURL(url);

      if (log) log.textContent = logLines.join('\n') || '✅ Готово';
      _setStatus(`✅ Объединено ${rowCount} строк`);
    } catch (e) {
      if (log) { log.textContent = '❌ ' + e.message; log.style.color = 'var(--danger)'; }
      _setStatus('Ошибка: ' + e.message);
    }
  }

  /* ─── export table ─────────────────────────────────────── */
  function exportTable() {
    if (!_tableRows.length) return;
    const header = ['Файл', 'Заголовок', 'Строка', 'Столбец', 'Статус', 'Целевое поле'];
    const rows = _tableRows.map(r => [r.fileName, r.headerName, r.headerRow, r.colNum, r.status, r.targetField]);
    const csv = [header, ...rows].map(r => r.map(v => `"${String(v).replace(/"/g, '""')}"`).join(',')).join('\n');
    const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'headers_export.csv'; a.click();
    URL.revokeObjectURL(url);
  }

  /* ─── clear workspace ─────────────────────────────────── */
  function clearWorkspace() {
    _tableRows = [];
    _renderTable();
    document.getElementById('carnet-row-count').textContent = 'Строк: 0';
    const log = document.getElementById('carnet-log');
    if (log) { log.textContent = ''; }
  }

  /* ─── status ─────────────────────────────────────────── */
  function _setStatus(msg) {
    const el = document.getElementById('carnet-status');
    if (el) el.textContent = msg;
  }

  return {
    init, openFiles, onFilesSelected, selectAll, clearFileList,
    generateHeaders, autoFill, checkFields, merge, exportTable, clearWorkspace,
    _toggleSheet, _setHeaderRow, _setTarget,
  };
})();
