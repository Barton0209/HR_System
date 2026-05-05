// web_ui/static/js/app.js
'use strict';

// ── Состояние ─────────────────────────────────────────────────────────────────
let currentJobId  = null;
let currentResult = null;
let pollTimer     = null;

// ── DOM ───────────────────────────────────────────────────────────────────────
const dropZone       = document.getElementById('dropZone');
const fileInput      = document.getElementById('fileInput');
const uploadBtn      = document.getElementById('uploadBtn');
const langSelect     = document.getElementById('langSelect');
const docTypeSelect  = document.getElementById('docTypeSelect');
const progressBlock  = document.getElementById('progressBlock');
const progressBar    = document.getElementById('progressBar');
const progressText   = document.getElementById('progressText');
const resultSection  = document.getElementById('resultSection');
const docsBody       = document.getElementById('docsBody');
const modal          = document.getElementById('modal');
const modalBody      = document.getElementById('modalBody');
const modalTitle     = document.getElementById('modalTitle');

// ── Drag & Drop ───────────────────────────────────────────────────────────────
dropZone.addEventListener('click', () => fileInput.click());
dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file) setFile(file);
});
fileInput.addEventListener('change', () => {
  if (fileInput.files[0]) setFile(fileInput.files[0]);
});

function setFile(file) {
  dropZone.classList.add('has-file');
  dropZone.querySelector('.drop-text').innerHTML =
    `<strong>${file.name}</strong><br><span style="font-size:12px">${formatSize(file.size)}</span>`;
  uploadBtn.disabled = false;
  uploadBtn._file = file;
}

// ── Загрузка ──────────────────────────────────────────────────────────────────
uploadBtn.addEventListener('click', async () => {
  const file = uploadBtn._file;
  if (!file) return;

  setProgress(10, 'Загрузка файла...');
  uploadBtn.disabled = true;
  resultSection.classList.add('hidden');

  const fd = new FormData();
  fd.append('file', file);

  try {
    const resp = await fetch(
      `/api/documents/upload?lang=${langSelect.value}&doc_type=${docTypeSelect.value}`,
      { method: 'POST', body: fd }
    );
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    currentJobId = data.id;
    setProgress(25, 'OCR — распознавание текста...');
    pollStatus();
  } catch (e) {
    setProgress(0, `Ошибка: ${e.message}`);
    uploadBtn.disabled = false;
  }
});

// ── Polling статуса ───────────────────────────────────────────────────────────
const STATUS_PROGRESS = {
  uploaded: 20, preprocessed: 35, ocr_completed: 60,
  nlp_completed: 85, finished: 100, failed: 0,
};
const STATUS_TEXT = {
  uploaded: 'Загружено, ожидание...', preprocessed: 'Предобработка...',
  ocr_completed: 'OCR завершён, NLP обработка...', nlp_completed: 'Извлечение данных...',
  finished: 'Готово!', failed: 'Ошибка обработки',
};

function pollStatus() {
  clearTimeout(pollTimer);
  pollTimer = setTimeout(async () => {
    try {
      const resp = await fetch(`/api/documents/${currentJobId}/status`);
      const data = await resp.json();
      const pct  = STATUS_PROGRESS[data.status] || 50;
      setProgress(pct, STATUS_TEXT[data.status] || data.status);

      if (data.status === 'finished') {
        await loadResult();
        refreshDocsList();
      } else if (data.status === 'failed') {
        setProgress(0, 'Ошибка обработки');
        uploadBtn.disabled = false;
        refreshDocsList();
      } else {
        pollStatus();
      }
    } catch (e) {
      pollStatus();
    }
  }, 1200);
}

// ── Результат ─────────────────────────────────────────────────────────────────
async function loadResult() {
  const resp = await fetch(`/api/documents/${currentJobId}/result`);
  currentResult = await resp.json();
  renderResult(currentResult);
  progressBlock.classList.add('hidden');
  resultSection.classList.remove('hidden');
  uploadBtn.disabled = false;
  resultSection.scrollIntoView({ behavior: 'smooth' });
}

function renderResult(job) {
  const nlp      = job.nlp || {};
  const docClass = job.doc_class || nlp.doc_class || 'unknown';
  const conf     = nlp.confidence || nlp.doc_class_conf || 0;
  const ocrPages = job.ocr?.pages || [];
  const fullText = ocrPages.map(p => p.text || '').join('\n\n--- Страница ---\n\n');

  document.getElementById('badgeType').textContent = docTypeLabel(docClass);
  document.getElementById('badgeConf').textContent = `Уверенность: ${Math.round(conf * 100)}%`;
  document.getElementById('ocrText').textContent   = fullText || '(текст не распознан)';

  // Скрываем все блоки
  ['passportResult', 'ticketResult', 'genericResult'].forEach(id =>
    document.getElementById(id).classList.add('hidden'));

  if (docClass === 'passport_ru' || docClass === 'passport_foreign') {
    renderPassport(nlp);
  } else if (docClass === 'ticket_request') {
    renderTicket(nlp);
  } else {
    renderGeneric(nlp);
  }
}

function renderPassport(nlp) {
  const el = document.getElementById('passportResult');
  el.classList.remove('hidden');
  const fields = [
    ['ФИО',              nlp.fio],
    ['Дата рождения',    nlp.birth_date],
    ['Гражданство',      nlp.citizenship],
    ['Серия',            nlp.doc_series],
    ['Номер',            nlp.doc_number],
    ['Тип документа',    nlp.doc_type === 'passport_ru' ? 'Паспорт РФ' : 'Иностранный паспорт'],
    ['Дата выдачи',      nlp.issue_date],
    ['Дата окончания',   nlp.expiry_date],
    ['Кем выдан',        nlp.issuer],
    ['Адрес',            nlp.address],
    ['Телефон',          (nlp.phones || [])[0]],
    ['СНИЛС',            nlp.snils],
  ];
  document.getElementById('passportFields').innerHTML = fields.map(fieldHtml).join('');
}

function renderTicket(nlp) {
  const el = document.getElementById('ticketResult');
  el.classList.remove('hidden');
  const fields = [
    ['ФИО',           nlp.fio],
    ['Маршрут 1',     nlp.route],
    ['Дата вылета 1', nlp.date],
    ['Маршрут 2',     nlp.route2],
    ['Дата вылета 2', nlp.date2],
    ['Обоснование',   nlp.reason],
    ['Телефон',       nlp.phone],
    ['Серия паспорта', nlp.doc_series],
    ['Номер паспорта', nlp.doc_number],
  ];
  document.getElementById('ticketFields').innerHTML = fields.map(fieldHtml).join('');
}

function renderGeneric(nlp) {
  const el = document.getElementById('genericResult');
  el.classList.remove('hidden');
  const ent = nlp.entities || nlp;
  const fields = [
    ['ФИО',         (ent.fio || [])[0]],
    ['Телефон',     (ent.phones || [])[0]],
    ['Email',       (ent.emails || [])[0]],
    ['Дата',        ((ent.dates || [])[0] || {}).normalized],
    ['Адрес',       ent.address],
    ['Гражданство', ent.citizenship],
    ['Серия',       (ent.passport || {}).series],
    ['Номер',       (ent.passport || {}).number],
    ['СНИЛС',       ent.snils],
    ['Обоснование', ent.reason],
  ];
  document.getElementById('genericFields').innerHTML = fields.map(fieldHtml).join('');
}

function fieldHtml([label, value]) {
  const empty = !value;
  return `<div class="field-item">
    <div class="field-label">${label}</div>
    <div class="field-value ${empty ? 'empty' : ''}">${value || '—'}</div>
  </div>`;
}

// ── Список документов ─────────────────────────────────────────────────────────
async function refreshDocsList() {
  try {
    const resp = await fetch('/api/documents?limit=50');
    const data = await resp.json();
    renderDocsList(data.items || []);
  } catch (e) { /* ignore */ }
}

function renderDocsList(items) {
  if (!items.length) {
    docsBody.innerHTML = '<tr><td colspan="5" class="empty-row">Нет документов</td></tr>';
    return;
  }
  docsBody.innerHTML = items.map(job => `
    <tr>
      <td><strong>${escHtml(job.filename || '—')}</strong></td>
      <td><span class="doc-type">${docTypeLabel(job.doc_class || '—')}</span></td>
      <td><span class="status-badge status-${job.status}">${statusLabel(job.status)}</span></td>
      <td>${formatDate(job.uploaded_at)}</td>
      <td>
        ${job.status === 'finished'
          ? `<button class="btn btn-sm btn-outline" onclick="showDetails('${job.job_id}')">Детали</button>`
          : ''}
        <button class="btn btn-sm btn-danger" onclick="deleteDoc('${job.job_id}')"
                style="margin-left:4px">✕</button>
      </td>
    </tr>`).join('');
}

async function showDetails(jobId) {
  const resp = await fetch(`/api/documents/${jobId}/result`);
  const job  = await resp.json();
  modalTitle.textContent = job.filename || 'Документ';
  const nlp = job.nlp || {};
  const ent = nlp.entities || nlp;
  modalBody.innerHTML = `
    <p><strong>Тип:</strong> ${docTypeLabel(job.doc_class || '—')}</p>
    <p><strong>Статус:</strong> ${statusLabel(job.status)}</p>
    <p><strong>Загружен:</strong> ${formatDate(job.uploaded_at)}</p>
    <hr style="margin:12px 0">
    <pre style="font-size:12px;white-space:pre-wrap;max-height:400px;overflow-y:auto">${
      escHtml(JSON.stringify(nlp, null, 2))
    }</pre>`;
  modal.classList.remove('hidden');
}

async function deleteDoc(jobId) {
  if (!confirm('Удалить документ?')) return;
  await fetch(`/api/documents/${jobId}`, { method: 'DELETE' });
  refreshDocsList();
}

// ── Кнопки ────────────────────────────────────────────────────────────────────
document.getElementById('copyJsonBtn').addEventListener('click', () => {
  if (!currentResult) return;
  navigator.clipboard.writeText(JSON.stringify(currentResult.nlp, null, 2));
  showToast('JSON скопирован');
});

document.getElementById('exportCsvBtn').addEventListener('click', () => {
  if (!currentResult) return;
  const nlp = currentResult.nlp || {};
  const rows = Object.entries(nlp)
    .filter(([, v]) => typeof v === 'string' && v)
    .map(([k, v]) => `"${k}","${v.replace(/"/g, '""')}"`);
  const csv = 'Поле,Значение\n' + rows.join('\n');
  downloadText(csv, `${currentResult.filename || 'result'}.csv`, 'text/csv');
});

document.getElementById('newDocBtn').addEventListener('click', () => {
  resultSection.classList.add('hidden');
  dropZone.classList.remove('has-file');
  dropZone.querySelector('.drop-text').innerHTML =
    'Перетащите файл сюда<br><span>или нажмите для выбора</span>';
  uploadBtn.disabled = true;
  uploadBtn._file = null;
  fileInput.value = '';
  currentJobId = null;
  currentResult = null;
});

document.getElementById('refreshBtn').addEventListener('click', refreshDocsList);
document.getElementById('modalClose').addEventListener('click', () => modal.classList.add('hidden'));
modal.addEventListener('click', e => { if (e.target === modal) modal.classList.add('hidden'); });

// ── Проверка сервисов ─────────────────────────────────────────────────────────
async function checkServices() {
  const el = document.getElementById('svcStatus');
  try {
    const resp = await fetch('/health');
    const data = await resp.json();
    el.textContent = data.status === 'ok' ? '✅ Сервисы работают' : '⚠ Проблема с сервисами';
  } catch {
    el.textContent = '❌ Сервисы недоступны';
  }
}

// ── Вспомогательные ───────────────────────────────────────────────────────────
function setProgress(pct, text) {
  progressBlock.classList.remove('hidden');
  progressBar.style.width = pct + '%';
  progressText.textContent = text;
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / 1048576).toFixed(1) + ' MB';
}

function formatDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('ru-RU', { day:'2-digit', month:'2-digit',
    year:'numeric', hour:'2-digit', minute:'2-digit' });
}

function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function docTypeLabel(t) {
  const map = {
    passport_ru: '🇷🇺 Паспорт РФ', passport_foreign: '🌍 Иностр. паспорт',
    ticket_request: '✈ Заявка на билеты', invoice: '🧾 Счёт/Акт',
    contract: '📝 Договор', act: '📋 Акт', snils: '🏥 СНИЛС',
    inn: '🏢 ИНН', unknown: '❓ Неизвестно',
  };
  return map[t] || t || '—';
}

function statusLabel(s) {
  const map = {
    uploaded: 'Загружен', preprocessed: 'Предобработка', ocr_completed: 'OCR готов',
    nlp_completed: 'NLP готов', finished: 'Готово', failed: 'Ошибка',
  };
  return map[s] || s;
}

function downloadText(content, filename, mime) {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([content], { type: mime }));
  a.download = filename;
  a.click();
}

function showToast(msg) {
  const t = document.createElement('div');
  t.textContent = msg;
  Object.assign(t.style, {
    position:'fixed', bottom:'24px', right:'24px', background:'#217346',
    color:'#fff', padding:'10px 20px', borderRadius:'6px', fontSize:'13px',
    boxShadow:'0 4px 12px rgba(0,0,0,.2)', zIndex:'999', transition:'opacity .3s',
  });
  document.body.appendChild(t);
  setTimeout(() => { t.style.opacity = '0'; setTimeout(() => t.remove(), 300); }, 2500);
}

// ── Инициализация ─────────────────────────────────────────────────────────────
checkServices();
refreshDocsList();
setInterval(refreshDocsList, 10000);
