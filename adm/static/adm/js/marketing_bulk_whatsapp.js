(function () {
  const form = document.getElementById('marketing-bulk-whatsapp-form');
  const status = document.getElementById('marketing-bulk-whatsapp-status');
  if (!form || !status) return;

  const numbersInput = document.getElementById('bulk-phone-numbers');
  const imageInput = document.getElementById('bulk-image');

  function values() {
    return String(numbersInput.value || '').split(/[\s,]+/).map((v) => v.trim()).filter(Boolean);
  }

  function validNumbers() {
    return values().filter((value) => {
      const digits = value.replace(/\D/g, '');
      return digits.length === 10 || (digits.length === 12 && digits.startsWith('52')) || (digits.length === 13 && digits.startsWith('521'));
    });
  }

  form.addEventListener('submit', async function (event) {
    event.preventDefault();
    const all = values();
    const valid = validNumbers();
    const image = imageInput.files && imageInput.files.length ? 'con imagen' : 'solo texto';
    const min = document.getElementById('bulk-delay-min').value;
    const max = document.getElementById('bulk-delay-max').value;
    const summary = `Se procesarán ${all.length} entradas (${valid.length} con formato válido), ${image}, delay normal de ${min}-${max} minutos y pausa obligatoria de 10-15 minutos cada 5 intentos.`;
    if (!window.confirm(`${summary}\n\n¿Deseas encolar el envío?`)) return;

    status.className = 'alert alert-info mt-3';
    status.textContent = 'Creando proceso persistente...';
    const button = form.querySelector('button[type="submit"]');
    if (button) button.disabled = true;
    try {
      const response = await fetch(form.action, {
        method: 'POST',
        body: new FormData(form),
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      });
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.error || 'No se pudo crear el proceso.');
      window.location.href = data.detail_url;
    } catch (error) {
      status.className = 'alert alert-danger mt-3';
      status.textContent = error.message || 'Error de red al crear el proceso.';
      if (button) button.disabled = false;
    }
  });
})();
