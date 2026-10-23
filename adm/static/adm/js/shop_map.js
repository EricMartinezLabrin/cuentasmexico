(() => {
  'use strict';
  const root=document.getElementById('shop-map-app'); if(!root) return;
  const U=window.ShopMaps, $=id=>document.getElementById(id), base=root.dataset.base;
  const colors={active:'#15803d',suspended:'#dc2626',pending:'#b45309'}, names={active:'Activa',suspended:'Suspendida',pending:'Pendiente'};
  let shops=[], selected=[], map=null, layers=[], editor=null, editingId=null, clickMode=null, originMarker=null, routeLine=null, batchRunning=false, requestNumber=0, detailNumber=0;
  function message(text, error=false){const box=$('map-message');box.className=`alert ${error?'alert-danger':'alert-info'}`;box.textContent=text;}
  const run=fn=>async(...args)=>{try{await fn(...args);}catch(e){message(e.message,true);}};
  function bind(id,fn){$(id).addEventListener('click',run(fn));}
  const getShop=id=>shops.find(s=>s.id===id);
  const origin=()=>U.point($('origin-lat').value,$('origin-lng').value);
  const selectedShops=()=>selected.map(getShop).filter(Boolean);
  function setOrigin(p){$('origin-lat').value=p.lat;$('origin-lng').value=p.lng;if(map){if(originMarker)map.removeLayer(originMarker);originMarker=L.marker(p).addTo(map).bindTooltip('Origen');map.panTo(p);}clickMode=null;drawRoute();}
  function drawRoute(){
    if(!map)return;if(routeLine){map.removeLayer(routeLine);routeLine=null;}
    let p;try{p=origin();}catch(_){return;}
    const points=[p,...selectedShops().map(s=>s.point)];if($('route-return').checked)points.push(p);
    if(points.length>1)routeLine=L.polyline(points,{color:'#2563eb',dashArray:'6,8',weight:3}).addTo(map);
  }
  function toggle(id){const s=getShop(id);if(!s?.point||!s.confirmed){message('Confirma ubicación exacta antes de seleccionar.',true);return;}selected=selected.includes(id)?selected.filter(v=>v!==id):[...selected,id];renderLists();renderRoute();}
  function renderLists(){
    $('map-count').textContent=String(shops.length);$('missing-count').textContent=String(shops.filter(s=>!s.point).length);
    $('shops-results').replaceChildren();$('shops-missing').replaceChildren();
    shops.forEach(s=>{
      const row=U.node('div',null,'shop-map-row');
      if(s.point){const c=U.node('input');c.type='checkbox';c.checked=selected.includes(s.id);c.disabled=!s.confirmed;c.setAttribute('aria-label',`Seleccionar ${s.name}`);c.onchange=()=>toggle(s.id);row.append(c);}
      const b=U.button(`${s.name} · ${names[s.state]} · ${s.point?(s.confirmed?'Confirmada':'Aproximada'):'Sin ubicación'}`,run(()=>showDetail(s.id)),'btn btn-light shop-name');row.append(b);
      $(s.point?'shops-results':'shops-missing').append(row);
    });
  }
  function renderRoute(){
    $('selection-count').textContent=String(selected.length);$('route-stops').replaceChildren();
    selectedShops().forEach((s,index)=>{
      const row=U.node('div',null,'shop-map-route-row');row.append(U.node('span',`${index+1}. ${s.name}`));
      const move=delta=>{const next=index+delta;if(next<0||next>=selected.length)return;[selected[index],selected[next]]=[selected[next],selected[index]];renderRoute();};
      const up=U.button('Subir',()=>move(-1));up.disabled=index===0;const down=U.button('Bajar',()=>move(1));down.disabled=index===selected.length-1;
      row.append(up,down,U.button('Quitar',()=>toggle(s.id)));$('route-stops').append(row);
    });drawRoute();
  }
  function popup(s){const box=U.node('div',null,'shop-map-popup');box.append(U.node('strong',s.name),U.node('div',`${names[s.state]} · ${s.confirmed?'Confirmada':'Aproximada'}`),U.button('Ver ficha',run(()=>showDetail(s.id))));if(s.confirmed)box.append(U.button('Agregar / quitar de recorrido',()=>toggle(s.id)));return box;}
  function renderMap(fit=false){
    if(!map)return;layers.forEach(l=>map.removeLayer(l));layers=[];
    const located=shops.filter(s=>s.point);
    if($('map-mode').value==='points'){
      const group=L.markerClusterGroup?L.markerClusterGroup({spiderfyOnMaxZoom:true,showCoverageOnHover:false}):L.layerGroup();
      located.forEach(s=>{const marker=L.marker(s.point,{icon:L.divIcon({className:`shop-map-marker ${s.confirmed?'':'approximate'}`,html:'',iconSize:[18,18]})});marker.on('add',()=>{const el=marker.getElement();if(el)el.style.backgroundColor=colors[s.state];});marker.bindPopup(popup(s));group.addLayer(marker);});group.addTo(map);layers.push(group);
    }else if(L.heatLayer){
      ['active','suspended','pending'].forEach(state=>{const points=located.filter(s=>s.state===state).map(s=>[s.point.lat,s.point.lng,Number($('heat-intensity').value)]);if(!points.length)return;const layer=L.heatLayer(points,{radius:Number($('heat-radius').value),blur:18,max:3,maxZoom:0,minOpacity:0.35,gradient:{0.1:'#dbeafe',0.3:colors[state],0.7:colors[state],1:'#111827'}}).addTo(map);layers.push(layer);});
    }else message('No cargó capa de calor. Prueba vista de puntos.',true);
    if(fit&&located.length)map.fitBounds(L.latLngBounds(located.map(s=>s.point)),{padding:[25,25],maxZoom:15});drawRoute();
  }
  async function load(){
    const seq=++requestNumber;const form=new FormData($('map-filters'));form.delete('csrfmiddlewaretoken');
    if(!form.getAll('state').length){message('Selecciona al menos un estado.',true);return;}
    const result=await U.api(`${base}data/?${new URLSearchParams(form)}`);if(seq!==requestNumber)return;
    shops=result.shops;const old=selected.length;selected=selected.filter(id=>{const s=getShop(id);return s?.point&&s.confirmed;});
    message(`${shops.length} tiendas. ${old-selected.length} selecciones retiradas por filtros o ubicación.`);renderLists();renderRoute();renderMap(true);
  }
  function clearEditor(){if(editor&&map)map.removeLayer(editor);editor=null;editingId=null;clickMode=null;}
  function setEditor(p){
    $('shop-lat').value=p.lat;$('shop-lng').value=p.lng;$('confirm-shop-location').checked=false;
    if(map){if(editor)map.removeLayer(editor);editor=L.marker(p,{draggable:true}).addTo(map);editor.on('dragend',()=>{const p=editor.getLatLng();$('shop-lat').value=p.lat.toFixed(7);$('shop-lng').value=p.lng.toFixed(7);$('confirm-shop-location').checked=false;});map.setView(p,17);}
  }
  async function showDetail(id){
    const seq=++detailNumber;const s=await U.api(`${base}detail/${id}/`);if(seq!==detailNumber)return;
    clearEditor();editingId=id;$('shop-map-detail').hidden=false;$('shop-detail-fields').replaceChildren();$('shop-address-results').replaceChildren();
    const fields={name:'Tienda',owner:'Dueño',phone:'WhatsApp',email:'Email',giro:'Giro',address:'Dirección',city:'Ciudad',cp:'CP',balance:'Saldo',credit_limit:'Límite de crédito',available:'Disponible',confirmation_date:'Fecha aprobación',comision_date:'Fecha comisión',last_negative_balance_since:'Saldo negativo desde',consecutive_on_time_payments:'Pagos puntuales',location_source:'Origen de ubicación',location_reviewed_at:'Fecha revisión',location_reviewed_by:'Revisado por'};
    Object.entries(fields).forEach(([key,label])=>{const row=U.node('div');row.append(U.node('strong',`${label}: `),U.node('span',s[key]??'—'));$('shop-detail-fields').append(row);});
    $('shop-detail-fields').append(U.node('div',`Estado: ${names[s.state]} · Ubicación: ${s.point?(s.location_confirmed?'Confirmada':'Aproximada'):'Sin ubicación'}`));
    $('shop-detail-link').href=s.detail_url;$('shop-lat').value='';$('shop-lng').value='';if(s.point)setEditor(s.point);$('confirm-shop-location').checked=false;
    $('shop-map-detail').scrollIntoView({behavior:'smooth',block:'start'});
  }
  function results(container,rows,choose){container.replaceChildren();if(!rows.length)container.append(U.node('p','Sin resultados. Coloca pin manualmente.'));rows.forEach(p=>container.append(U.button(p.label,()=>choose(p),'btn btn-outline-secondary d-block my-2 text-start')));}
  async function routes(){const data=await U.api(`${base}routes/`);$('saved-routes').replaceChildren();data.routes.forEach(r=>{const row=U.node('div',null,'my-2');const a=U.node('a',`Recorrido #${r.id}`);a.href=r.url;a.target='_blank';a.rel='noopener';row.append(a,U.node('span',` · ${r.revoked?'Revocado':new Date(r.expires_at)<=new Date()?'Caducado':`Vence ${new Date(r.expires_at).toLocaleString()}`} `));if(!r.revoked)row.append(U.button('Revocar',run(async()=>{await U.api(`${base}routes/${r.id}/revoke/`,{});await routes();})));$('saved-routes').append(row);});}
  async function batchStatus(){const r=await U.api(`${base}batch/`);batchProgress(r);}
  function batchProgress(r){const box=$('batch-progress');box.replaceChildren(U.node('p',`${r.finished?'Terminado':r.started?'En proceso / pausado':'Sin iniciar'}: ${r.processed}/${r.total}`));(r.errors||[]).forEach(e=>box.append(U.node('div',`Tienda #${e.id}: ${e.reason}`)));}
  $('map-filters').addEventListener('submit',run(async e=>{e.preventDefault();clearEditor();await load();}));
  bind('all-states',()=>{$('map-filters').querySelectorAll('[name=state]').forEach(e=>e.checked=true);return load();});
  ['map-mode','heat-radius','heat-intensity'].forEach(id=>$(id).addEventListener('input',()=>renderMap()));
  bind('select-results',()=>{selected=shops.filter(s=>s.point&&s.confirmed).map(s=>s.id);renderLists();renderRoute();});
  bind('clear-selection',()=>{selected=[];renderLists();renderRoute();});
  bind('shop-search-address',async()=>{if(!editingId)throw Error('Selecciona una tienda.');const rows=await U.api(`${base}search/`,{shop_id:editingId});results($('shop-address-results'),rows.results,setEditor);});
  bind('shop-pin-mode',()=>{if(!editingId)throw Error('Selecciona una tienda.');clickMode='shop';message('Pulsa mapa para ubicar tienda.');$('shops-map').scrollIntoView({behavior:'smooth'});});
  bind('close-location-editor',()=>{clearEditor();$('shop-map-detail').hidden=true;});
  bind('save-shop-location',async()=>{if(!editingId)throw Error('Selecciona una tienda.');await U.api(`${base}location/${editingId}/`,{...U.point($('shop-lat').value,$('shop-lng').value),confirmed:$('confirm-shop-location').checked});clearEditor();$('shop-map-detail').hidden=true;await load();message('Ubicación guardada.');});
  ['shop-lat','shop-lng'].forEach(id=>$(id).addEventListener('input',()=>{$('confirm-shop-location').checked=false;}));
  bind('origin-gps',()=>new Promise((resolve,reject)=>{if(!navigator.geolocation){reject(Error('GPS no disponible. Define origen por dirección o pin.'));return;}navigator.geolocation.getCurrentPosition(p=>{setOrigin({lat:p.coords.latitude,lng:p.coords.longitude});resolve();},()=>reject(Error('No se obtuvo GPS. Define origen por dirección o pin.')),{timeout:15000,enableHighAccuracy:true});}));
  bind('origin-pin',()=>{clickMode='origin';message('Pulsa mapa para elegir origen.');$('shops-map').scrollIntoView({behavior:'smooth'});});
  bind('origin-search',async()=>{const r=await U.api(`${base}search/`,{address:$('origin-address').value});results($('origin-results'),r.results,setOrigin);});
  ['origin-lat','origin-lng','route-return'].forEach(id=>$(id).addEventListener('change',drawRoute));
  bind('route-nearest',()=>{let p=origin();const remain=selectedShops();const sorted=[];while(remain.length){remain.sort((a,b)=>U.distance(p,a.point)-U.distance(p,b.point)||a.id-b.id);const s=remain.shift();sorted.push(s.id);p=s.point;}selected=sorted;renderRoute();});
  bind('route-share',async()=>{
    const b=$('route-share');b.disabled=true;try{const r=await U.api(`${base}routes/create/`,{origin:origin(),shops:selected,return_to_origin:$('route-return').checked,order:'manual'});const box=$('route-share-result');box.replaceChildren();const a=U.node('a',r.url);a.href=r.url;a.target='_blank';a.rel='noopener';box.append(a,U.button('Copiar / compartir',run(()=>U.share(r.url))));await routes();}finally{b.disabled=false;}
  });
  bind('reload-routes',routes);
  bind('start-batch',async()=>{if(batchRunning)return;batchRunning=true;$('start-batch').disabled=true;try{while(batchRunning){const r=await U.api(`${base}batch/step/`,{});batchProgress(r);if(r.finished)break;}}finally{batchRunning=false;$('start-batch').disabled=false;await load();}});
  bind('stop-batch',()=>{batchRunning=false;message('El lote pausará al finalizar la consulta actual.');});
  if(window.L){
    map=L.map('shops-map').setView([23.6,-102.5],5);U.tile(map,JSON.parse($('shop-map-settings').textContent));
    if(L.Control.Draw){map.addControl(new L.Control.Draw({draw:{rectangle:true,polygon:{allowIntersection:false},polyline:false,circle:false,circlemarker:false,marker:false}}));map.on(L.Draw.Event.CREATED,e=>{let count=0;const bounds=e.layer.getBounds();const vertices=e.layer.getLatLngs()[0];const inside=p=>{if(e.layerType==='rectangle')return bounds.contains(p);let hit=false;for(let i=0,j=vertices.length-1;i<vertices.length;j=i++){const a=vertices[i],b=vertices[j];if(((a.lat>p.lat)!==(b.lat>p.lat))&&(p.lng<(b.lng-a.lng)*(p.lat-a.lat)/(b.lat-a.lat)+a.lng))hit=!hit;}return hit;};shops.forEach(s=>{if(s.point&&s.confirmed&&!selected.includes(s.id)&&inside(s.point)){selected.push(s.id);count++;}});renderLists();renderRoute();message(`${count} tiendas confirmadas agregadas por área.`);});}
    map.on('click',e=>{if(clickMode==='origin'){setOrigin(e.latlng);return;}if(clickMode==='shop'&&editingId){setEditor(e.latlng);return;}if($('map-mode').value==='heat'){const cursor=map.latLngToContainerPoint(e.latlng);const nearby=shops.filter(s=>s.point&&cursor.distanceTo(map.latLngToContainerPoint(s.point))<Number($('heat-radius').value));if(nearby.length){const box=U.node('div',null,'shop-map-popup');nearby.forEach(s=>box.append(U.button(s.name,run(()=>showDetail(s.id)))));L.popup().setLatLng(e.latlng).setContent(box).openOn(map);}}});
  }else message('No cargó mapa. Lista y fichas siguen disponibles; revisa conexión.',true);
  run(load)();run(batchStatus)();run(routes)();
})();
