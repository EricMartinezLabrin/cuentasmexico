function copyAcc(copyId) {
  const codigoACopiar = document.getElementById(copyId);
  const text = codigoACopiar.value || codigoACopiar.textContent;

  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(function() {
      if (typeof showToast === 'function') {
        showToast('Claves copiadas al portapapeles');
      }
    }).catch(function() {
      fallbackCopy(codigoACopiar);
    });
  } else {
    fallbackCopy(codigoACopiar);
  }
}

function fallbackCopy(element) {
  element.select();
  document.execCommand("copy");
  if (typeof showToast === 'function') {
    showToast('Claves copiadas al portapapeles');
  }
}
