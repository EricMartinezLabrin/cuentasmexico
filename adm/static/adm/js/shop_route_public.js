(() => {
 const U=window.ShopMaps,data=JSON.parse(document.getElementById('public-itinerary').textContent),message=document.getElementById('share-message');
 document.getElementById('route-origin').textContent=`Origen: ${data.origin.lat}, ${data.origin.lng}`;
 document.getElementById('share-public-route').onclick=async()=>{try{await U.share(location.href);message.textContent='Enlace listo para compartir.';}catch(_){message.textContent=location.href;}};
 if(!window.L){message.textContent='Mapa no disponible. Puedes usar lista y enlaces de Google Maps.';return;}
 const map=L.map('public-route-map');U.tile(map,JSON.parse(document.getElementById('public-map-settings').textContent));
 const points=[data.origin,...data.stops];if(data.return_to_origin)points.push(data.origin);
 L.marker(data.origin).addTo(map).bindPopup(U.node('span','Origen'));
 data.stops.forEach((s,i)=>L.marker(s).addTo(map).bindPopup(U.node('span',`${i+1}. ${s.name}`)));
 L.polyline(points,{color:'#2563eb',dashArray:'6,8'}).addTo(map);map.fitBounds(L.latLngBounds(points),{padding:[30,30],maxZoom:16});
})();
