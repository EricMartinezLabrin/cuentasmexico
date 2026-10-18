(function () {
  const modalElement = document.getElementById('bulkHistoryModal');
  if (!modalElement) return;
  const modal = bootstrap.Modal.getOrCreateInstance(modalElement);
  const terminal = new Set(['completed', 'cancelled', 'failed']);
  let current = null;
  let timer = null;

  function escapeHtml(value) { return String(value || '').replace(/[&<>'"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[c])); }
  function timeLeft(seconds) { const s = Math.max(0, Number(seconds || 0)); return s >= 60 ? `${Math.floor(s / 60)} min ${s % 60} s` : `${s} s`; }

  async function refresh() {
    if (!current) return;
    try {
      const response = await fetch(current.statusUrl, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.error || 'No se pudo consultar el proceso.');
      document.getElementById('history-sent').textContent = data.sent_count;
      document.getElementById('history-ignored').textContent = data.ignored_count;
      document.getElementById('history-errors').textContent = data.error_count;
      document.getElementById('history-pending').textContent = data.pending_count;
      document.getElementById('history-state').textContent = `${data.status_label}: ${data.status_message || ''}`;
      document.getElementById('history-current').textContent = data.current_number || '-';
      document.getElementById('history-countdown').textContent = data.remaining_seconds ? timeLeft(data.remaining_seconds) : '-';
      const done = data.sent_count + data.ignored_count + data.error_count;
      const percent = data.total_count ? Math.round(done * 100 / data.total_count) : 100;
      document.getElementById('history-progress').style.width = `${percent}%`;
      document.getElementById('history-progress').textContent = `${percent}%`;
      const alert = document.getElementById('bulk-history-alert');
      alert.className = `alert ${data.status === 'completed' ? 'alert-success' : data.status === 'failed' ? 'alert-danger' : data.status === 'cancelled' ? 'alert-warning' : 'alert-info'}`;
      alert.textContent = `${data.status_label}: ${data.status_message || ''}`;
      document.getElementById('bulk-history-cancel').style.display = terminal.has(data.status) ? 'none' : '';
      document.getElementById('bulk-history-edit').style.display = data.status === 'cancelled' ? '' : 'none';
      document.getElementById('bulk-history-resume').style.display = data.status === 'cancelled' && data.pending_count > 0 ? '' : 'none';
      if (terminal.has(data.status)) { clearTimeout(timer); timer = null; }
    } catch (error) {
      document.getElementById('bulk-history-alert').textContent = error.message;
    }
    if (current && !timer) timer = setTimeout(() => { timer = null; refresh(); }, 4000);
  }

  async function showDetails(status) {
    if (!current) return;
    const target = document.getElementById('bulk-history-details');
    target.classList.remove('d-none');
    target.innerHTML = '<div class="text-muted">Cargando detalles...</div>';
    const response = await fetch(`${current.detailsUrl}?status=${encodeURIComponent(status)}`);
    const data = await response.json();
    if (!data.items || !data.items.length) { target.innerHTML = '<div class="text-muted">No hay registros.</div>'; return; }
    target.innerHTML = `<div class="table-responsive"><table class="table table-sm"><thead><tr><th>Original</th><th>Normalizado</th><th>Estado</th><th>Motivo/respuesta</th><th>Fecha</th></tr></thead><tbody>${data.items.map((item) => `<tr><td>${escapeHtml(item.original_value)}</td><td>${escapeHtml(item.normalized_number || '-')}</td><td>${escapeHtml(item.status)}</td><td>${escapeHtml(item.reason || item.provider_response || '-')}</td><td>${escapeHtml(item.sent_at || item.attempted_at || '-')}</td></tr>`).join('')}</tbody></table></div>`;
  }

  document.querySelectorAll('.bulk-history-view').forEach((button) => button.addEventListener('click', () => {
    current = { detailUrl: button.dataset.detailUrl, statusUrl: button.dataset.statusUrl, detailsUrl: button.dataset.detailsUrl, cancelUrl: button.dataset.cancelUrl, resumeUrl: button.dataset.resumeUrl };
    document.getElementById('bulk-history-title').textContent = `Proceso de envío #${button.dataset.jobId}`;
    document.getElementById('bulk-history-details').classList.add('d-none');
    modal.show();
    refresh();
  }));
  document.querySelectorAll('.bulk-history-stat').forEach((button) => button.addEventListener('click', () => showDetails(button.dataset.status)));
  document.getElementById('bulk-history-cancel').addEventListener('click', async () => {
    if (!current || !window.confirm('¿Cancelar los envíos pendientes?')) return;
    const input = document.querySelector('#bulk-history-csrf input[name="csrfmiddlewaretoken"]');
    await fetch(current.cancelUrl, { method: 'POST', headers: { 'X-CSRFToken': input ? input.value : '', 'X-Requested-With': 'XMLHttpRequest' } });
    refresh();
  });
  document.getElementById('bulk-history-resume').addEventListener('click', async () => {
    if (!current || !window.confirm('¿Reanudar los envíos pendientes?')) return;
    const input = document.querySelector('#bulk-history-csrf input[name="csrfmiddlewaretoken"]');
    await fetch(current.resumeUrl, { method: 'POST', headers: { 'X-CSRFToken': input ? input.value : '', 'X-Requested-With': 'XMLHttpRequest' } });
    refresh();
  });
  document.getElementById('bulk-history-edit').addEventListener('click', () => {
    if (current && current.detailUrl) window.location.href = current.detailUrl;
  });
  modalElement.addEventListener('hidden.bs.modal', () => { current = null; clearTimeout(timer); timer = null; });
})();
