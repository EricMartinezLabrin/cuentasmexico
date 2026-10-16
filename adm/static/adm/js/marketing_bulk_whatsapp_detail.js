(function () {
  const page = document.getElementById('bulk-whatsapp-page');
  if (!page) return;
  const statusUrl = page.dataset.statusUrl;
  const detailsUrl = page.dataset.detailsUrl;
  const cancelUrl = page.dataset.cancelUrl;
  const terminal = new Set(['completed', 'cancelled', 'failed']);
  let timer;

  function escapeHtml(value) {
    return String(value || '').replace(/[&<>'"]/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[char]));
  }

  function formatTime(seconds) {
    seconds = Math.max(0, Number(seconds || 0));
    const minutes = Math.floor(seconds / 60);
    const rest = seconds % 60;
    return minutes ? `${minutes} min ${rest} s` : `${rest} s`;
  }

  async function refresh() {
    try {
      const response = await fetch(statusUrl, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.error || 'No se pudo consultar el estado.');
      document.getElementById('bulk-sent').textContent = data.sent_count;
      document.getElementById('bulk-ignored').textContent = data.ignored_count;
      document.getElementById('bulk-errors').textContent = data.error_count;
      document.getElementById('bulk-pending').textContent = data.pending_count;
      document.getElementById('bulk-state').textContent = `${data.status_label}: ${data.status_message || ''}`;
      document.getElementById('bulk-current').textContent = data.current_number || '-';
      document.getElementById('bulk-countdown').textContent = data.remaining_seconds ? formatTime(data.remaining_seconds) : '-';
      const completed = data.sent_count + data.error_count + data.ignored_count;
      const percentage = data.total_count ? Math.round((completed / data.total_count) * 100) : 100;
      const progress = document.getElementById('bulk-progress');
      progress.style.width = `${percentage}%`;
      progress.textContent = `${percentage}%`;
      const alert = document.getElementById('bulk-status-alert');
      alert.className = `alert ${data.status === 'failed' ? 'alert-danger' : data.status === 'completed' ? 'alert-success' : data.status === 'cancelled' ? 'alert-warning' : 'alert-info'}`;
      alert.textContent = `${data.status_label}: ${data.status_message || ''}`;
      document.getElementById('bulk-cancel-btn').style.display = terminal.has(data.status) ? 'none' : '';
      if (terminal.has(data.status)) clearTimeout(timer);
    } catch (error) {
      document.getElementById('bulk-status-alert').textContent = error.message;
    }
    if (!timer) timer = setTimeout(() => { timer = null; refresh(); }, 4000);
  }

  async function showDetails(status) {
    const body = document.getElementById('bulk-details-body');
    document.getElementById('bulk-details-title').textContent = `Detalles: ${status}`;
    body.innerHTML = '<div class="text-muted">Cargando...</div>';
    const modal = bootstrap.Modal.getOrCreateInstance(document.getElementById('bulkDetailsModal'));
    modal.show();
    const response = await fetch(`${detailsUrl}?status=${encodeURIComponent(status)}`);
    const data = await response.json();
    if (!data.success || !data.items.length) { body.innerHTML = '<div class="text-muted">No hay registros.</div>'; return; }
    body.innerHTML = `<div class="table-responsive"><table class="table table-sm align-middle"><thead><tr><th>Original</th><th>Normalizado</th><th>Estado</th><th>Motivo / respuesta</th><th>Fecha</th></tr></thead><tbody>${data.items.map((item) => `<tr><td>${escapeHtml(item.original_value)}</td><td>${escapeHtml(item.normalized_number || '-')}</td><td>${escapeHtml(item.status)}</td><td>${escapeHtml(item.reason || item.provider_response || '-')}</td><td>${escapeHtml(item.sent_at || item.attempted_at || '-')}</td></tr>`).join('')}</tbody></table></div>`;
  }

  document.querySelectorAll('.bulk-stat').forEach((button) => button.addEventListener('click', () => showDetails(button.dataset.status)));
  document.getElementById('bulk-cancel-btn').addEventListener('click', async () => {
    if (!window.confirm('¿Cancelar los envíos pendientes?')) return;
    const csrfInput = document.querySelector('#bulk-csrf-form input[name="csrfmiddlewaretoken"]');
    const token = csrfInput ? csrfInput.value : '';
    await fetch(cancelUrl, { method: 'POST', headers: { 'X-CSRFToken': token, 'X-Requested-With': 'XMLHttpRequest' } });
    refresh();
  });
  refresh();
})();
