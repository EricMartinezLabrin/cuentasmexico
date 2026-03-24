(function () {
  function escapeHtml(str) {
    return String(str || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

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
    async function pollGenerationStatus(statusUrl, statusEl, doneMessage) {
      for (let i = 0; i < 240; i += 1) {
        const res = await fetch(statusUrl, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
        const data = await res.json();
        if (data.done) {
          if (data.generation_status === 'error') {
            statusEl.className = 'alert alert-danger mt-2 py-2';
            statusEl.innerHTML = `La regeneración falló: ${escapeHtml(data.error || 'Error desconocido')}`;
            return;
          }
          statusEl.className = 'alert alert-success mt-2 py-2';
          statusEl.innerHTML = doneMessage || 'Regeneración completada.';
          setTimeout(() => window.location.reload(), 900);
          return;
        }
        if (data.generation_status === 'needs_input') {
          statusEl.className = 'alert alert-warning mt-2 py-2';
          statusEl.innerHTML = 'La IA requiere respuestas adicionales para completar la regeneración.';
          return;
        }
        statusEl.className = 'alert alert-info mt-2 py-2';
        statusEl.textContent = 'Recreando campaña con IA según parámetros guardados...';
        await new Promise((resolve) => setTimeout(resolve, 2000));
      }
      statusEl.className = 'alert alert-warning mt-2 py-2';
      statusEl.textContent = 'Sigue procesando. Puedes recargar en unos segundos.';
    }

    const generationMeta = document.getElementById('marketing-generation-meta');
    const regenerateBtn = document.getElementById('marketing-regenerate-btn');
    const regenerateStatus = document.getElementById('marketing-regenerate-status');
    if (regenerateBtn && regenerateStatus) {
      regenerateBtn.addEventListener('click', async function () {
        regenerateStatus.className = 'alert alert-info mb-3';
        regenerateStatus.classList.remove('d-none');
        regenerateStatus.textContent = 'Encolando regeneración IA...';
        const formData = new FormData();
        const csrfInput = document.querySelector('input[name="csrfmiddlewaretoken"]');
        if (csrfInput && csrfInput.value) formData.append('csrfmiddlewaretoken', csrfInput.value);
        try {
          const res = await fetch(regenerateBtn.getAttribute('data-url'), {
            method: 'POST',
            body: formData,
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
          });
          const data = await res.json();
          if (!data.success) {
            regenerateStatus.className = 'alert alert-danger mb-3';
            regenerateStatus.textContent = data.error || 'No se pudo iniciar la regeneración.';
            return;
          }
          await pollGenerationStatus(
            data.status_url,
            regenerateStatus,
            'Regeneración completada. Actualizando vista...'
          );
        } catch (err) {
          regenerateStatus.className = 'alert alert-danger mb-3';
          regenerateStatus.textContent = 'Error de red al iniciar regeneración.';
        }
      });
    }

    if (generationMeta && regenerateStatus) {
      const initialStatus = generationMeta.getAttribute('data-generation-status') || '';
      const statusUrl = generationMeta.getAttribute('data-status-url') || '';
      if (initialStatus === 'processing' && statusUrl) {
        regenerateStatus.className = 'alert alert-info mb-3';
        regenerateStatus.classList.remove('d-none');
        regenerateStatus.textContent = 'La campaña sigue regenerándose. Esperando resultado...';
        pollGenerationStatus(statusUrl, regenerateStatus, 'Regeneración completada. Actualizando vista...');
      }
    }

    const titleText = document.getElementById('campaign-title-text');
    const titleEditBtn = document.getElementById('campaign-title-edit-btn');
    const titleForm = document.getElementById('campaign-title-form');
    const titleInput = document.getElementById('campaign-title-input');
    const titleCancelBtn = document.getElementById('campaign-title-cancel-btn');
    const titleStatus = document.getElementById('campaign-title-status');
    if (titleEditBtn && titleForm && titleInput && titleText) {
      const openEdit = function () {
        titleForm.classList.remove('d-none');
        titleEditBtn.classList.add('d-none');
        titleInput.focus();
        titleInput.select();
      };
      const closeEdit = function () {
        titleForm.classList.add('d-none');
        titleEditBtn.classList.remove('d-none');
      };
      titleEditBtn.addEventListener('click', openEdit);
      if (titleCancelBtn) {
        titleCancelBtn.addEventListener('click', closeEdit);
      }
      titleForm.addEventListener('submit', async function (e) {
        e.preventDefault();
        const formData = new FormData(titleForm);
        if (titleStatus) {
          titleStatus.className = 'small text-muted mt-1';
          titleStatus.textContent = 'Guardando título...';
        }
        try {
          const res = await fetch(titleForm.getAttribute('action'), {
            method: 'POST',
            body: formData,
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
          });
          const data = await res.json();
          if (!data.success) {
            if (titleStatus) {
              titleStatus.className = 'small text-danger mt-1';
              titleStatus.textContent = data.error || 'No se pudo guardar el título.';
            }
            return;
          }
          titleText.textContent = data.name || titleInput.value;
          if (titleStatus) {
            titleStatus.className = 'small text-success mt-1';
            titleStatus.textContent = 'Título actualizado.';
          }
          closeEdit();
        } catch (err) {
          if (titleStatus) {
            titleStatus.className = 'small text-danger mt-1';
            titleStatus.textContent = 'Error de red al guardar el título.';
          }
        }
      });
    }

    const promoParamsForm = document.getElementById('marketing-promo-params-form');
    const promoParamsStatus = document.getElementById('marketing-promo-params-status');
    const promoEditToggle = document.getElementById('promo-params-edit-toggle');
    const promoSaveWrap = document.getElementById('promo-params-save-wrap');
    const promoInputs = Array.from(document.querySelectorAll('.promo-param-input'));
    let promoEditMode = false;
    function setPromoEditMode(enabled) {
      promoEditMode = !!enabled;
      promoInputs.forEach((el) => {
        el.disabled = !promoEditMode;
      });
      if (promoSaveWrap) {
        promoSaveWrap.classList.toggle('d-none', !promoEditMode);
      }
      if (promoEditToggle) {
        promoEditToggle.innerHTML = promoEditMode
          ? '<i class="bi bi-eye me-1"></i>Vista previa'
          : '<i class="bi bi-pencil me-1"></i>Editar';
      }
    }
    if (promoEditToggle) {
      promoEditToggle.addEventListener('click', function () {
        setPromoEditMode(!promoEditMode);
      });
      setPromoEditMode(false);
    }
    if (promoParamsForm && promoParamsStatus) {
      promoParamsForm.addEventListener('submit', async function (e) {
        e.preventDefault();
        if (!promoEditMode) {
          promoParamsStatus.className = 'alert alert-warning mt-2 py-2';
          promoParamsStatus.classList.remove('d-none');
          promoParamsStatus.textContent = 'Activa modo edición para guardar cambios.';
          return;
        }
        promoParamsStatus.className = 'alert alert-info mt-2 py-2';
        promoParamsStatus.classList.remove('d-none');
        promoParamsStatus.textContent = 'Guardando parámetros y relanzando IA...';
        const formData = new FormData(promoParamsForm);
        try {
          const res = await fetch(promoParamsForm.getAttribute('action'), {
            method: 'POST',
            body: formData,
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
          });
          const data = await res.json();
          if (!data.success) {
            promoParamsStatus.className = 'alert alert-danger mt-2 py-2';
            promoParamsStatus.textContent = data.error || 'No se pudo guardar los parámetros.';
            return;
          }
          promoParamsStatus.className = 'alert alert-info mt-2 py-2';
          promoParamsStatus.textContent = data.message || 'Parámetros guardados. Regenerando...';
          await pollGenerationStatus(
            data.status_url,
            promoParamsStatus,
            'Parámetros aplicados y campaña regenerada. Recargando...'
          );
          setPromoEditMode(false);
        } catch (err) {
          promoParamsStatus.className = 'alert alert-danger mt-2 py-2';
          promoParamsStatus.textContent = 'Error de red al guardar parámetros.';
        }
      });
    }

    const refreshAudienceForm = document.getElementById('refresh-recommendations-form');
    const refreshAudienceStatus = document.getElementById('refresh-recommendations-status');
    const recommendationsTbody = document.getElementById('recommendations-tbody');
    const recommendationsCount = document.getElementById('recommendations-count');
    if (refreshAudienceForm && refreshAudienceStatus) {
      refreshAudienceForm.addEventListener('submit', async function (e) {
        e.preventDefault();
        refreshAudienceStatus.className = 'alert alert-info m-2 py-2';
        refreshAudienceStatus.classList.remove('d-none');
        refreshAudienceStatus.textContent = 'Recalculando clientes recomendados...';
        const formData = new FormData(refreshAudienceForm);
        try {
          const res = await fetch(refreshAudienceForm.getAttribute('action'), {
            method: 'POST',
            body: formData,
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
          });
          const data = await res.json();
          if (!data.success) {
            refreshAudienceStatus.className = 'alert alert-danger m-2 py-2';
            refreshAudienceStatus.textContent = data.error || 'No se pudo refrescar la audiencia.';
            return;
          }
          if (recommendationsCount) {
            recommendationsCount.textContent = String(data.selected_count || 0);
          }
          if (recommendationsTbody) {
            const rows = Array.isArray(data.rows) ? data.rows : [];
            if (!rows.length) {
              recommendationsTbody.innerHTML =
                '<tr><td colspan="7" class="text-center text-muted py-3">Sin recomendaciones aún.</td></tr>';
            } else {
              recommendationsTbody.innerHTML = rows
                .map(
                  (r) => `
                  <tr>
                    <td>${escapeHtml(r.username)}<br><small class="text-muted">${escapeHtml(r.email)}</small></td>
                    <td>${escapeHtml(r.country)}</td>
                    <td>${escapeHtml(r.phone)}</td>
                    <td>${escapeHtml(r.total_orders)}</td>
                    <td>$${escapeHtml(r.total_revenue)}</td>
                    <td><strong>${escapeHtml(r.score)}</strong></td>
                    <td class="small">${escapeHtml(r.reason)}</td>
                  </tr>
                `
                )
                .join('');
            }
          }
          refreshAudienceStatus.className = 'alert alert-success m-2 py-2';
          refreshAudienceStatus.textContent = data.message || 'Audiencia actualizada.';
        } catch (err) {
          refreshAudienceStatus.className = 'alert alert-danger m-2 py-2';
          refreshAudienceStatus.textContent = 'Error de red al refrescar clientes.';
        }
      });
    }

    const refreshBtn = document.getElementById('refresh-whatsapp-groups-btn');
    const groupsStatus = document.getElementById('whatsapp-groups-status');
    const groupsContainer = document.getElementById('whatsapp-groups-container');
    if (refreshBtn && groupsContainer) {
      refreshBtn.addEventListener('click', async function () {
        const baseUrl = refreshBtn.getAttribute('data-url');
        const url = `${baseUrl}?force=1`;
        if (groupsStatus) {
          groupsStatus.textContent = 'Actualizando grupos desde Evolution API...';
        }
        try {
          const res = await fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
          const data = await res.json();
          if (!data.success) {
            if (groupsStatus) groupsStatus.textContent = 'No fue posible actualizar grupos.';
            return;
          }
          const groups = Array.isArray(data.groups) ? data.groups : [];
          if (!groups.length) {
            groupsContainer.innerHTML =
              '<div class="small text-muted">No se encontraron grupos desde Evolution API ni fallback.</div>';
            if (groupsStatus) groupsStatus.textContent = 'Sin grupos disponibles.';
            return;
          }
          const rows = groups
            .map((g, idx) => {
              const id = String(g.id || '').replace(/"/g, '&quot;');
              const name = String(g.name || g.id || '').replace(/</g, '&lt;').replace(/>/g, '&gt;');
              return `
                <div class="col-12 col-md-6">
                  <div class="form-check">
                    <input class="form-check-input" type="checkbox" name="group_ids" id="group_dyn_${idx}" value="${id}">
                    <label class="form-check-label" for="group_dyn_${idx}">
                      ${name} <small class="text-muted">(${id})</small>
                    </label>
                  </div>
                </div>
              `;
            })
            .join('');
          groupsContainer.innerHTML = `<div class="row g-2">${rows}</div>`;
          if (groupsStatus) groupsStatus.textContent = `Grupos actualizados: ${groups.length}`;
        } catch (err) {
          if (groupsStatus) groupsStatus.textContent = 'Error de red al actualizar grupos.';
        }
      });
    }

    const sendForm = document.getElementById('marketing-send-real-form');
    const sendStatus = document.getElementById('marketing-send-modal-status');
    const waControls = document.getElementById('marketing-whatsapp-controls');
    if (sendForm && sendStatus) {
      function toggleChannelControls() {
        const channel = (sendForm.querySelector('input[name="delivery_channel"]:checked') || {}).value || 'whatsapp';
        if (waControls) {
          waControls.style.display = channel === 'whatsapp' ? '' : 'none';
        }
      }
      sendForm.querySelectorAll('input[name="delivery_channel"]').forEach((el) => {
        el.addEventListener('change', toggleChannelControls);
      });
      toggleChannelControls();

      sendForm.addEventListener('submit', async function (e) {
        e.preventDefault();
        sendStatus.className = 'alert alert-info mt-3';
        sendStatus.classList.remove('d-none');
        sendStatus.textContent = 'Procesando envío...';
        const formData = new FormData(sendForm);
        try {
          const res = await fetch(sendForm.getAttribute('action'), {
            method: 'POST',
            body: formData,
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
          });
          const data = await res.json();
          if (!data.success) {
            sendStatus.className = 'alert alert-danger mt-3';
            sendStatus.textContent = data.error || 'No se pudo iniciar el envío.';
            return;
          }
          sendStatus.className = 'alert alert-success mt-3';
          sendStatus.textContent = `Proceso iniciado. enviados=${data.sent_count || 0}, fallidos=${data.failed_count || 0}`;
          setTimeout(() => window.location.reload(), 1200);
        } catch (err) {
          sendStatus.className = 'alert alert-danger mt-3';
          sendStatus.textContent = 'Error de red al iniciar envío.';
        }
      });
    }

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
