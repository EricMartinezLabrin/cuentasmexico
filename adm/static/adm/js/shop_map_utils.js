/* Shared safe DOM and authenticated JSON helpers. */
window.ShopMaps = (() => {
  const node = (tag, text, cls) => { const e = document.createElement(tag); if (text != null) e.textContent = text; if (cls) e.className = cls; return e; };
  const button = (text, fn, cls = 'btn btn-sm btn-outline-secondary') => { const b = node('button', text, cls); b.type = 'button'; b.onclick = fn; return b; };
  async function api(url, data) {
    const token = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
    const res = await fetch(url, {method: data === undefined ? 'GET' : 'POST', credentials:'same-origin', headers: data === undefined ? {} : {'Content-Type':'application/json','X-CSRFToken':token || ''}, body: data === undefined ? undefined : JSON.stringify(data)});
    let value; try { value = await res.json(); } catch (_) { throw new Error(res.status === 403 ? 'Recarga la página y verifica tu sesión antes de guardar.' : 'Respuesta no válida del servidor.'); }
    if (!res.ok) throw new Error(value.error || `Error HTTP ${res.status}`);
    return value;
  }
  function tile(map, config) {
    // Attribution is text, even when supplied through deployment configuration.
    const escaped = node('span', config.attribution).outerHTML;
    L.tileLayer(config.tiles, {attribution: escaped, maxZoom:19}).addTo(map);
  }
  function point(lat, lng) {
    if (String(lat).trim() === '' || String(lng).trim() === '') throw new Error('Define latitud y longitud.');
    const p = {lat:Number(lat), lng:Number(lng)};
    if (!Number.isFinite(p.lat) || !Number.isFinite(p.lng) || Math.abs(p.lat)>90 || Math.abs(p.lng)>180) throw new Error('Coordenadas fuera de rango.');
    return p;
  }
  function distance(a,b) {
    const rad = n=>n*Math.PI/180;
    const h=Math.sin(rad(b.lat-a.lat)/2)**2+Math.cos(rad(a.lat))*Math.cos(rad(b.lat))*Math.sin(rad(b.lng-a.lng)/2)**2;
    return 2*6371*Math.asin(Math.min(1,Math.sqrt(h)));
  }
  async function share(url) {
    if (navigator.share) { try { await navigator.share({title:'Recorrido de tiendas',url}); return; } catch(e) { if(e.name==='AbortError') return; } }
    if (navigator.clipboard?.writeText) { await navigator.clipboard.writeText(url); return; }
    window.prompt('Copia el enlace',url);
  }
  return {node,button,api,tile,point,distance,share};
})();
