function copyAcc(copyId) {
  const codigoACopiar = document.getElementById(copyId);
  codigoACopiar.select();
  document.execCommand("copy");
}
