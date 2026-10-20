/**
 * app.js — Ziply Dashboard v3 (Phase 4: JWT auth)
 *
 * Handles:
 *  - JWT auth: attach Bearer token to all API calls, 401 → redirect /login
 *  - Username display + logout (clears localStorage, redirects to /login)
 *  - Dark mode toggle (persisted in localStorage)
 *  - Dashboard summary (GET /api/dashboard)
 *  - Create Short URL form (POST /api/shorten)
 *  - My Links table (GET /api/links, with search filter)
 *  - Copy, Edit (modal + PATCH), Delete, Analytics navigation
 *  - QR download button
 *  - Bulk CSV shortening
 *  - Global toast notifications
 */

'use strict';

// ── Auth constants ────────────────────────────────────────────────────────────

const TOKEN_KEY   = 'ziply_token';
const USERNAME_KEY = 'ziply_username';

function getToken()    { return localStorage.getItem(TOKEN_KEY); }
function getUsername() { return localStorage.getItem(USERNAME_KEY) || 'User'; }

function authHeaders() {
  const t = getToken();
  return t ? { 'Authorization': `Bearer ${t}` } : {};
}

// Redirect to login if not authenticated
if (!getToken()) {
  window.location.replace('/login');
}

// ── Authenticated fetch helper ────────────────────────────────────────────────

async function apiFetch(url, options = {}) {
  const headers = {
    ...(options.headers || {}),
    ...authHeaders(),
  };
  const res = await fetch(url, { ...options, headers });
  if (res.status === 401) {
    // Token expired or invalid — send to login
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USERNAME_KEY);
    window.location.replace('/login');
    return res; // unreachable but satisfies linter
  }
  return res;
}

// ── DOMContentLoaded ──────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {

  // ── Display logged-in username ──────────────────────────────────────────────

  const logoutBtn = document.getElementById('logout-btn');
  if (logoutBtn) {
    logoutBtn.innerHTML = `<span>⏎</span> ${getUsername()}`;
    logoutBtn.title = 'Click to log out';
  }

  // Logout handler
  logoutBtn?.addEventListener('click', () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USERNAME_KEY);
    window.location.replace('/login');
  });


  // ── Theme ───────────────────────────────────────────────────────────────────

  const html = document.documentElement;
  const themeToggle = document.getElementById('theme-toggle');
  const themeIcon  = themeToggle?.querySelector('.theme-icon');
  const themeLabel = themeToggle?.querySelector('.theme-label');

  function applyTheme(dark) {
    html.dataset.theme = dark ? 'dark' : 'light';
    if (themeIcon)  themeIcon.textContent  = dark ? '☀️' : '🌙';
    if (themeLabel) themeLabel.textContent = dark ? 'Light' : 'Dark';
    localStorage.setItem('ziply_theme', dark ? 'dark' : 'light');
  }

  let isDark = localStorage.getItem('ziply_theme') === 'dark';
  applyTheme(isDark);

  themeToggle?.addEventListener('click', () => {
    isDark = !isDark;
    applyTheme(isDark);
  });


  // ── Toast ───────────────────────────────────────────────────────────────────

  const toastEl = document.getElementById('toast');
  let toastTimer = null;

  function showToast(msg, type = 'success') {
    if (!toastEl) return;
    toastEl.textContent = msg;
    toastEl.className = `toast toast-${type}`;
    toastEl.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { toastEl.hidden = true; }, 3200);
  }


  // ── Dashboard summary ───────────────────────────────────────────────────────

  const totalLinksEl  = document.getElementById('total-links');
  const totalClicksEl = document.getElementById('total-clicks');

  async function loadDashboard() {
    try {
      const res = await apiFetch('/api/dashboard');
      if (!res.ok) return;
      const data = await res.json();
      if (totalLinksEl)  totalLinksEl.textContent  = data.total_links;
      if (totalClicksEl) totalClicksEl.textContent = data.total_clicks;
    } catch { /* silent */ }
  }


  // ── Helpers ─────────────────────────────────────────────────────────────────

  function escHtml(s) {
    return String(s || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function extractDetail(data) {
    if (!data?.detail) return 'Something went wrong.';
    if (typeof data.detail === 'string') return data.detail;
    if (Array.isArray(data.detail)) {
      return data.detail.map(e => e.msg || e.message || JSON.stringify(e)).join(' ');
    }
    return 'Something went wrong.';
  }

  function formatDate(isoStr) {
    if (!isoStr) return '—';
    try {
      const d = new Date(isoStr);
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    } catch { return isoStr; }
  }


  // ── Create Short URL ────────────────────────────────────────────────────────

  const shortenForm    = document.getElementById('shorten-form');
  const urlInput       = document.getElementById('url-input');
  const aliasInput     = document.getElementById('alias-input');
  const expiryInput    = document.getElementById('expiry-input');
  const shortenBtn     = document.getElementById('shorten-btn');
  const btnText        = shortenBtn?.querySelector('.btn-text');
  const btnSpinner     = shortenBtn?.querySelector('.btn-spinner');
  const formError      = document.getElementById('form-error');
  const formErrorMsg   = document.getElementById('form-error-msg');
  const formSuccess    = document.getElementById('form-success');
  const formSuccessMsg = document.getElementById('form-success-msg');

  function setFormError(msg) {
    if (!formError) return;
    formErrorMsg.textContent = msg;
    formError.hidden = false;
    if (formSuccess) formSuccess.hidden = true;
    urlInput?.classList.add('is-error');
  }

  function clearFormError() {
    if (!formError) return;
    formError.hidden = true;
    formErrorMsg.textContent = '';
    urlInput?.classList.remove('is-error');
  }

  function setFormSuccess(msg) {
    if (!formSuccess) return;
    formSuccessMsg.textContent = msg;
    formSuccess.hidden = false;
    if (formError) formError.hidden = true;
    setTimeout(() => { formSuccess.hidden = true; }, 4000);
  }

  function setShortenLoading(on) {
    if (!shortenBtn) return;
    shortenBtn.disabled = on;
    if (btnText)    btnText.hidden    = on;
    if (btnSpinner) btnSpinner.hidden = !on;
  }

  shortenForm?.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearFormError();
    if (formSuccess) formSuccess.hidden = true;

    const rawUrl  = urlInput?.value.trim() || '';
    const alias   = aliasInput?.value.trim() || null;
    const expDays = expiryInput?.value.trim()
      ? parseInt(expiryInput.value.trim(), 10)
      : null;

    if (!rawUrl) { setFormError('Please enter a destination URL.'); return; }
    if (!rawUrl.startsWith('http://') && !rawUrl.startsWith('https://')) {
      setFormError('URL must start with http:// or https://'); return;
    }

    setShortenLoading(true);
    try {
      const res  = await apiFetch('/api/shorten', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ url: rawUrl, alias, expires_days: expDays }),
      });
      const data = await res.json();
      if (!res.ok) { setFormError(extractDetail(data)); return; }

      setFormSuccess(`✓ Short link created: ${data.short_url}`);
      urlInput.value   = '';
      if (aliasInput)  aliasInput.value  = '';
      if (expiryInput) expiryInput.value = '';
      await refreshAll();
    } catch {
      setFormError('Cannot reach the server. Is uvicorn running?');
    } finally {
      setShortenLoading(false);
    }
  });

  urlInput?.addEventListener('input', () => {
    if (!formError?.hidden) clearFormError();
  });


  // ── My Links table ──────────────────────────────────────────────────────────

  const linksTbody   = document.getElementById('links-tbody');
  const linksEmpty   = document.getElementById('links-empty');
  const linksLoading = document.getElementById('links-loading');
  const linkCount    = document.getElementById('link-count');
  const searchInput  = document.getElementById('search-input');

  let allLinks = [];

  function renderLinks(links) {
    if (!linksTbody) return;
    linksTbody.innerHTML = '';

    if (links.length === 0) {
      if (linksEmpty)   linksEmpty.hidden   = false;
      if (linksLoading) linksLoading.hidden = true;
      if (linkCount)    linkCount.textContent = '0 links';
      return;
    }

    if (linksEmpty)   linksEmpty.hidden   = true;
    if (linksLoading) linksLoading.hidden = true;
    if (linkCount) linkCount.textContent = `${links.length} link${links.length !== 1 ? 's' : ''}`;

    links.forEach(link => {
      const tr = document.createElement('tr');
      const shortCode  = link.short_url.split('/').pop();
      const displayUrl = link.original_url.length > 38
        ? link.original_url.slice(0, 38) + '…'
        : link.original_url;

      tr.innerHTML = `
        <td class="url-cell" title="${escHtml(link.original_url)}">${escHtml(displayUrl)}</td>
        <td class="short-link-cell">
          <a href="${escHtml(link.short_url)}" target="_blank" rel="noopener noreferrer">
            ↗ ${escHtml(shortCode)}
          </a>
        </td>
        <td><span class="clicks-badge">${link.click_count}</span></td>
        <td class="date-cell">${formatDate(link.created_at)}</td>
        <td class="qr-cell">
          <img class="qr-thumb" src="${escHtml(link.qr_url)}" alt="QR code for ${escHtml(shortCode)}" loading="lazy" />
          <a class="btn btn-sm btn-qr-dl" href="${escHtml(link.qr_url)}" download="qr-${escHtml(shortCode)}.png" title="Download QR PNG">⬇ QR</a>
        </td>
        <td class="actions-cell">
          <button class="btn btn-sm btn-copy"      data-action="copy"      data-url="${escHtml(link.short_url)}">📋 Copy</button>
          <button class="btn btn-sm btn-edit"      data-action="edit"      data-code="${escHtml(link.code)}" data-alias="${escHtml(link.code)}" data-expires="${escHtml(link.expires_at || '')}">✏ Edit</button>
          <button class="btn btn-sm btn-delete"    data-action="delete"    data-code="${escHtml(link.code)}">🗑 Delete</button>
          <button class="btn btn-sm btn-analytics" data-action="analytics" data-code="${escHtml(link.code)}">📊 Analytics</button>
        </td>
      `;
      linksTbody.appendChild(tr);
    });
  }

  async function loadLinks() {
    if (linksLoading) linksLoading.hidden = false;
    if (linksEmpty)   linksEmpty.hidden   = true;
    try {
      const res = await apiFetch('/api/links');
      if (!res.ok) throw new Error('Failed');
      allLinks = await res.json();
      filterAndRender();
    } catch {
      if (linksLoading) linksLoading.hidden = true;
      if (linksEmpty) {
        linksEmpty.hidden = false;
        const p = linksEmpty.querySelector('p');
        if (p) p.textContent = 'Failed to load links.';
      }
    }
  }

  function filterAndRender() {
    const q = searchInput?.value.trim().toLowerCase() || '';
    const filtered = q
      ? allLinks.filter(l =>
          l.original_url.toLowerCase().includes(q) ||
          l.code.toLowerCase().includes(q) ||
          l.short_url.toLowerCase().includes(q)
        )
      : allLinks;
    renderLinks(filtered);
  }

  searchInput?.addEventListener('input', filterAndRender);

  // Table action delegation
  linksTbody?.addEventListener('click', async (e) => {
    const btn = e.target.closest('button[data-action]');
    if (!btn) return;
    const action = btn.dataset.action;

    if (action === 'copy') {
      const url = btn.dataset.url;
      try {
        await navigator.clipboard.writeText(url);
        showToast('Copied to clipboard!', 'success');
      } catch { showToast('Copy failed — please copy manually.', 'error'); }
    }

    if (action === 'delete') {
      const code = btn.dataset.code;
      if (!confirm(`Delete short link "/${code}"? This cannot be undone.`)) return;
      try {
        const res = await apiFetch(`/api/links/${encodeURIComponent(code)}`, { method: 'DELETE' });
        if (res.ok || res.status === 204) {
          showToast('Link deleted.', 'success');
          await refreshAll();
        } else {
          const data = await res.json().catch(() => ({}));
          showToast(extractDetail(data) || 'Delete failed.', 'error');
        }
      } catch { showToast('Network error.', 'error'); }
    }

    if (action === 'edit') {
      openEditModal(btn.dataset.code, btn.dataset.alias || '', btn.dataset.expires || '');
    }

    if (action === 'analytics') {
      window.location.href = `/analytics/${encodeURIComponent(btn.dataset.code)}`;
    }
  });


  // ── Edit Modal ──────────────────────────────────────────────────────────────

  const editModal    = document.getElementById('edit-modal');
  const editCode     = document.getElementById('edit-code');
  const editAlias    = document.getElementById('edit-alias');
  const editExpiry   = document.getElementById('edit-expiry');
  const editError    = document.getElementById('edit-error');
  const editErrorMsg = document.getElementById('edit-error-msg');
  const modalClose   = document.getElementById('modal-close');
  const modalCancel  = document.getElementById('modal-cancel');
  const modalSave    = document.getElementById('modal-save');

  function openEditModal(code, alias, expires) {
    if (!editModal) return;
    editCode.value   = code;
    editAlias.value  = alias === code ? '' : alias;
    editExpiry.value = '';
    if (editError) editError.hidden = true;
    editModal.hidden = false;
    editAlias.focus();
  }

  function closeEditModal() {
    if (editModal) editModal.hidden = true;
  }

  modalClose?.addEventListener('click',  closeEditModal);
  modalCancel?.addEventListener('click', closeEditModal);
  editModal?.addEventListener('click', (e) => { if (e.target === editModal) closeEditModal(); });

  modalSave?.addEventListener('click', async () => {
    const code       = editCode?.value;
    const newAlias   = editAlias?.value.trim() || null;
    const expDaysStr = editExpiry?.value.trim();
    const expDays    = expDaysStr !== '' ? parseInt(expDaysStr, 10) : undefined;

    if (editError) editError.hidden = true;

    const body = {};
    if (newAlias !== null)     body.alias        = newAlias;
    if (expDays  !== undefined) body.expires_days = expDays;
    if (Object.keys(body).length === 0) { closeEditModal(); return; }

    try {
      const res  = await apiFetch(`/api/links/${encodeURIComponent(code)}`, {
        method:  'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) {
        if (editErrorMsg) editErrorMsg.textContent = extractDetail(data);
        if (editError)    editError.hidden = false;
        return;
      }
      closeEditModal();
      showToast('Link updated.', 'success');
      await refreshAll();
    } catch {
      if (editErrorMsg) editErrorMsg.textContent = 'Network error.';
      if (editError)    editError.hidden = false;
    }
  });


  // ── Bulk Shorten ────────────────────────────────────────────────────────────

  const bulkFileInput    = document.getElementById('bulk-file-input');
  const bulkDropZone     = document.getElementById('bulk-drop-zone');
  const bulkFileName     = document.getElementById('bulk-file-name');
  const bulkUploadBtn    = document.getElementById('bulk-upload-btn');
  const bulkClearBtn     = document.getElementById('bulk-clear-btn');
  const bulkProgress     = document.getElementById('bulk-progress');
  const bulkProgressBar  = document.getElementById('bulk-progress-bar');
  const bulkResults      = document.getElementById('bulk-results');
  const bulkTbody        = document.getElementById('bulk-tbody');
  const bulkSuccessCount = document.getElementById('bulk-success-count');
  const bulkErrorCount   = document.getElementById('bulk-error-count');

  let bulkFile = null;

  function setBulkFile(file) {
    if (!file) return;
    bulkFile = file;
    if (bulkFileName) {
      bulkFileName.textContent = `📄 ${file.name}  (${(file.size / 1024).toFixed(1)} KB)`;
      bulkFileName.hidden = false;
    }
    if (bulkUploadBtn) bulkUploadBtn.disabled = false;
    if (bulkClearBtn)  bulkClearBtn.hidden = false;
    if (bulkResults)   bulkResults.hidden = true;
  }

  function clearBulk() {
    bulkFile = null;
    if (bulkFileInput)   bulkFileInput.value = '';
    if (bulkFileName)    { bulkFileName.textContent = ''; bulkFileName.hidden = true; }
    if (bulkUploadBtn)   bulkUploadBtn.disabled = true;
    if (bulkClearBtn)    bulkClearBtn.hidden = true;
    if (bulkResults)     bulkResults.hidden = true;
    if (bulkProgress)    bulkProgress.hidden = true;
    if (bulkProgressBar) bulkProgressBar.style.width = '0%';
    if (bulkDropZone)    bulkDropZone.classList.remove('drag-over');
  }

  bulkFileInput?.addEventListener('change', () => {
    if (bulkFileInput.files[0]) setBulkFile(bulkFileInput.files[0]);
  });

  bulkDropZone?.addEventListener('dragover', (e) => {
    e.preventDefault();
    bulkDropZone.classList.add('drag-over');
  });
  bulkDropZone?.addEventListener('dragleave', () => bulkDropZone.classList.remove('drag-over'));
  bulkDropZone?.addEventListener('drop', (e) => {
    e.preventDefault();
    bulkDropZone.classList.remove('drag-over');
    const f = e.dataTransfer?.files[0];
    if (f) setBulkFile(f);
  });
  bulkDropZone?.addEventListener('click', (e) => {
    if (
      e.target === bulkDropZone ||
      e.target.classList.contains('bulk-upload-text') ||
      e.target.classList.contains('bulk-upload-icon')
    ) {
      bulkFileInput?.click();
    }
  });

  bulkClearBtn?.addEventListener('click', clearBulk);

  bulkUploadBtn?.addEventListener('click', async () => {
    if (!bulkFile) return;

    const bText    = bulkUploadBtn.querySelector('.btn-text');
    const bSpinner = bulkUploadBtn.querySelector('.btn-spinner');

    bulkUploadBtn.disabled = true;
    if (bText)    bText.hidden    = true;
    if (bSpinner) bSpinner.hidden = false;
    if (bulkProgress) {
      bulkProgress.hidden = false;
      bulkProgressBar.style.transition = 'width 1.2s ease';
      bulkProgressBar.style.width = '40%';
    }

    const fd = new FormData();
    fd.append('file', bulkFile);

    try {
      const res = await apiFetch('/api/bulk', { method: 'POST', body: fd });
      if (bulkProgressBar) {
        bulkProgressBar.style.transition = 'width 0.3s ease';
        bulkProgressBar.style.width = '100%';
      }
      await new Promise(r => setTimeout(r, 350));

      if (!res.ok && res.status !== 207) {
        const err = await res.json().catch(() => ({ detail: 'Upload failed.' }));
        showToast(extractDetail(err), 'error');
        return;
      }

      const rows = await res.json();
      renderBulkResults(rows);
      await refreshAll();
      showToast(`Bulk upload done: ${rows.filter(r => r.status === 201).length} shortened.`, 'success');
    } catch {
      showToast('Network error during bulk upload.', 'error');
    } finally {
      bulkUploadBtn.disabled = false;
      if (bText)    bText.hidden    = false;
      if (bSpinner) bSpinner.hidden = true;
      setTimeout(() => { if (bulkProgress) bulkProgress.hidden = true; }, 800);
    }
  });

  function renderBulkResults(rows) {
    if (!bulkResults || !bulkTbody) return;
    bulkResults.hidden = false;
    bulkTbody.innerHTML = '';

    const successCount = rows.filter(r => r.status === 201).length;
    const errorCount   = rows.length - successCount;

    if (bulkSuccessCount) bulkSuccessCount.textContent = `✓ ${successCount} shortened`;
    if (bulkErrorCount)   bulkErrorCount.textContent   = errorCount > 0 ? `✕ ${errorCount} failed` : '';

    rows.forEach(row => {
      const tr = document.createElement('tr');
      const isOk = row.status === 201;
      const shortDisplay = isOk ? row.short_url.split('/').pop() : '—';
      tr.innerHTML = `
        <td>${row.row}</td>
        <td class="url-cell" title="${escHtml(row.original_url || '')}">${escHtml(((row.original_url || row.error || '').slice(0, 40)))}${(row.original_url || '').length > 40 ? '…' : ''}</td>
        <td class="short-link-cell">${isOk ? `<a href="${escHtml(row.short_url)}" target="_blank">↗ ${escHtml(shortDisplay)}</a>` : `<span class="bulk-error-msg">${escHtml(row.error || '')}</span>`}</td>
        <td><span class="${isOk ? 'bulk-status-ok' : 'bulk-status-err'}">${row.status}</span></td>
        <td>${isOk ? `<button class="btn btn-sm btn-copy" data-action="copy" data-url="${escHtml(row.short_url)}">📋</button>` : ''}</td>
      `;
      bulkTbody.appendChild(tr);
    });
  }

  // Copy delegation for bulk results
  document.getElementById('bulk-tbody')?.addEventListener('click', async (e) => {
    const btn = e.target.closest('button[data-action="copy"]');
    if (!btn) return;
    try {
      await navigator.clipboard.writeText(btn.dataset.url);
      showToast('Copied!', 'success');
    } catch { showToast('Copy failed.', 'error'); }
  });


  // ── Orchestrate ─────────────────────────────────────────────────────────────

  async function refreshAll() {
    await Promise.all([loadDashboard(), loadLinks()]);
  }

  refreshAll();

}); // end DOMContentLoaded
