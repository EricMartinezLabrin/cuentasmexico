function copyAcc(copyId) {
  const codigoACopiar = document.getElementById(copyId);
  codigoACopiar.select();
  document.execCommand("copy");

  // Mostrar notificación toast si la función existe
  if (typeof showToast === 'function') {
    showToast('Claves copiadas al portapapeles');
  }
}
