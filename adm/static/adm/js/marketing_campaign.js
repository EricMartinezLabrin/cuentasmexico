(function () {
  function initCreatePage() {
    const form = document.getElementById('marketing-campaign-form');
    const statusBox = document.getElementById('marketing-generate-status');
    if (!form || !statusBox) return;

    async function pollStatus(url) {
      for (let i = 0; i < 240; i += 1) {
        const res = await fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
        const data = await res.json();
        if (data.done) {
          if (data.generation_status === 'error') {
            statusBox.className = 'alert alert-danger mt-3';
            statusBox.innerHTML = `La IA falló: ${data.error || 'Error desconocido'}. <a href="${data.detail_url}" class="alert-link">Abrir campaña</a>`;
            return;
          }
          statusBox.className = 'alert alert-success mt-3';
          statusBox.innerHTML = `La IA terminó de generar la campaña. <a href="${data.detail_url}" class="alert-link">Ver resultado</a>`;
          return;
        }
        if (data.generation_status === 'needs_input') {
          statusBox.className = 'alert alert-warning mt-3';
          statusBox.innerHTML = `La IA necesita respuestas para afinar la campaña. <a href="${data.detail_url}" class="alert-link">Abrir campaña y responder</a>`;
          return;
        }
        statusBox.className = 'alert alert-info mt-3';
        statusBox.textContent = 'La IA está creando campaña y recomendaciones (sin recargar la página)...';
        await new Promise((resolve) => setTimeout(resolve, 2000));
      }
      statusBox.className = 'alert alert-warning mt-3';
      statusBox.textContent = 'La generación sigue en proceso. Puedes volver al listado y revisar en unos momentos.';
    }

    form.addEventListener('click', async function (e) {
      const button = e.target.closest('button[data-action]');
      if (!button) return;
      e.preventDefault();
      const action = button.getAttribute('data-action');
      const formData = new FormData(form);
      formData.set('action', action);
      statusBox.className = 'alert alert-info mt-3';
      statusBox.textContent = 'Encolando generación con IA...';
      statusBox.classList.remove('d-none');

      const postUrl = form.getAttribute('action') || window.location.href;
      const response = await fetch(postUrl, {
        method: 'POST',
        body: formData,
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      });
      const data = await response.json();
      if (!data.success) {
        statusBox.className = 'alert alert-danger mt-3';
        statusBox.textContent = 'No fue posible iniciar la generación.';
        return;
      }
      await pollStatus(data.status_url);
    });
  }

  function initDetailPage() {
    const imgForm = document.getElementById('marketing-image-regenerate-form');
    const imgStatus = document.getElementById('marketing-image-regenerate-status');
    const imgPreview = document.getElementById('marketing-image-preview');
    const imgMeta = document.getElementById('marketing-image-meta');
    const imgMetaMessage = document.getElementById('marketing-image-meta-message');
    const imgEmpty = document.getElementById('marketing-image-empty-note');
    if (imgForm && imgStatus) {
      imgForm.addEventListener('submit', async function (e) {
        e.preventDefault();
        imgStatus.className = 'alert alert-info mt-2';
        imgStatus.classList.remove('d-none');
        imgStatus.textContent = 'Regenerando imagen con IA...';
        const formData = new FormData(imgForm);
        try {
          const res = await fetch(imgForm.getAttribute('action'), {
            method: 'POST',
            body: formData,
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
          });
          const data = await res.json();
          if (!data.success) {
            imgStatus.className = 'alert alert-danger mt-2';
            imgStatus.textContent = data.error || data.message || 'No se pudo regenerar la imagen.';
          } else {
            imgStatus.className = 'alert alert-success mt-2';
            imgStatus.textContent = 'Imagen regenerada correctamente.';
          }
          if (data.image_response && imgMeta) {
            const m = data.image_response;
            imgMeta.textContent = `Proveedor: ${m.provider || '-'} | Modelo: ${m.model || '-'} | Estado: ${m.status || '-'}`;
          }
          if (imgMetaMessage) {
            imgMetaMessage.textContent = data.message || '';
          }
          if (data.image_url) {
            if (imgPreview) {
              imgPreview.src = `${data.image_url}?t=${Date.now()}`;
            } else {
              window.location.reload();
            }
            if (imgEmpty) {
              imgEmpty.classList.add('d-none');
            }
          }
        } catch (err) {
          imgStatus.className = 'alert alert-danger mt-2';
          imgStatus.textContent = 'Error de red al regenerar imagen.';
        }
      });
    }

    const clarForm = document.getElementById('marketing-clarifications-form');
    const clarStatus = document.getElementById('marketing-clarifications-status');
    if (clarForm && clarStatus) {
      clarForm.addEventListener('submit', async function (e) {
        e.preventDefault();
        clarStatus.className = 'alert alert-info mt-3';
        clarStatus.classList.remove('d-none');
        clarStatus.textContent = 'Enviando respuestas y continuando generación...';
        const formData = new FormData(clarForm);
        try {
          const res = await fetch(clarForm.getAttribute('action'), {
            method: 'POST',
            body: formData,
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
          });
          const data = await res.json();
          if (!data.success) {
            clarStatus.className = 'alert alert-danger mt-3';
            clarStatus.textContent = data.error || 'No se pudo continuar generación.';
            return;
          }
          clarStatus.className = 'alert alert-success mt-3';
          clarStatus.innerHTML = `Generación reanudada. <a href="${data.detail_url}" class="alert-link">Refrescar detalle</a>`;
        } catch (err) {
          clarStatus.className = 'alert alert-danger mt-3';
          clarStatus.textContent = 'Error de red al enviar respuestas.';
        }
      });
    }

  }

  document.addEventListener('DOMContentLoaded', function () {
    initCreatePage();
    initDetailPage();
  });
})();
