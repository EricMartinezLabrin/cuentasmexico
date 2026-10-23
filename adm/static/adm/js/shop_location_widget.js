(() => {
  const root=document.getElementById('shop-location-widget');if(!root)return;
  const U=window.ShopMaps,$=id=>document.getElementById(id),box=$('form-location-results');let map,marker;
  const report=e=>{box.textContent=e.message;box.className='alert alert-danger';};
  function setPoint(p){$('id_latitude').value=p.lat.toFixed(7);$('id_longitude').value=p.lng.toFixed(7);$('id_confirm_location').checked=false;draw(p);}
  function draw(p){if(!map)return;if(marker)map.removeLayer(marker);marker=L.marker(p,{draggable:true}).addTo(map);marker.on('dragend',()=>{const p=marker.getLatLng();$('id_latitude').value=p.lat.toFixed(7);$('id_longitude').value=p.lng.toFixed(7);$('id_confirm_location').checked=false;});map.setView(p,17);}
  async function init(){if(map){map.invalidateSize();return;}if(!window.L)throw Error('Mapa no disponible. Puedes capturar coordenadas manualmente.');const config=await U.api(root.dataset.config);map=L.map('form-location-map').setView([23.6,-102.5],5);U.tile(map,config);map.on('click',e=>setPoint(e.latlng));try{draw(U.point($('id_latitude').value,$('id_longitude').value));}catch(_){} }
  root.querySelector('details').addEventListener('toggle',()=>{if(root.querySelector('details').open)init().catch(report);});
  $('form-search-location').onclick=async()=>{const b=$('form-search-location');b.disabled=true;try{const address=[$('id_address').value,$('id_city').value,$('id_cp').value,'Mexico'].filter(Boolean).join(', ');const r=await U.api(root.dataset.search,{address});box.replaceChildren();box.className='';if(!r.results.length)box.textContent='Sin resultados. Coloca pin manualmente.';r.results.forEach(p=>box.append(U.button(p.label,()=>setPoint(p),'btn btn-outline-secondary d-block my-2 text-start')));}catch(e){report(e);}finally{b.disabled=false;}};
  ['id_latitude','id_longitude'].forEach(id=>$(id).addEventListener('input',()=>{$('id_confirm_location').checked=false;}));
})();
