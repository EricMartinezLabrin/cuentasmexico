# Mapa de tiendas y recorridos

Pestaña **Mapa** en `/adm/shops/`. Requiere personal (`is_staff` o superusuario). Las rutas públicas muestran solo nombres, coordenadas y orden, caducan a los siete días y pueden revocarse desde el mapa.

## Preparación y despliegue

- Migración: `cupon.0008_shopgeocodecache_shopgeocodecontrol_and_more`. Solo agrega seis campos de ubicación y tres modelos para caché/control y recorridos. No incorpora diferencias antiguas entre modelos y migraciones.
- Antes de desplegar: respaldo, revisar plan de migración y autorizar aplicación en la BD objetivo. **No ejecutar geocodificación automáticamente en deploy.**
- Tras aplicar migración autorizada: desplegar código, ejecutar `collectstatic` según flujo existente, reiniciar aplicación y comprobar mapa con usuario staff.
- Sin migración, consultas al modelo Shop requieren las columnas nuevas: aplicar migración antes de servir esta versión.
- El historial previo de migraciones del repositorio tiene diferencias respecto de modelos actuales; no generar ni aplicar migraciones generales para resolverlas dentro de este cambio.

## Proveedores

Variables opcionales, con valores predeterminados:

```dotenv
SHOP_MAP_TILE_URL=https://tile.openstreetmap.org/{z}/{x}/{y}.png
SHOP_MAP_ATTRIBUTION=© OpenStreetMap contributors
SHOP_GEOCODER_URL=https://nominatim.openstreetmap.org/search
SHOP_GEOCODER_USER_AGENT=CuentasMexico-ShopMap/1.0 (+https://cuentasmexico.com)
SHOP_GEOCODE_INITIAL_LIMIT=100
```

Servicios alternativos deben ofrecer respuesta compatible con búsqueda Nominatim (`lat`, `lon`, `display_name`). No aumentar volumen sobre Nominatim público: cambiar primero de proveedor. No existe optimización por carretera ni API de pago de Google en esta función.

Nominatim público: máximo global 1 consulta/segundo, un proceso para carga inicial pequeña, resultados persistentes en caché, sin autocompletado y sin procesamiento periódico. Política: https://operations.osmfoundation.org/policies/nominatim/. Se envían únicamente direcciones comerciales, ciudad, CP y país. No enviar direcciones privadas ni datos personales. Ante bloqueo/cuota o errores, el lote se pausa y puede reanudarse.

OSM: atribución visible, solicitudes HTTPS, Referer válido, caché normal del navegador y sin precarga/offline. Política: https://operations.osmfoundation.org/policies/tiles/. Disponibilidad sin SLA; proveedor configurable. Leaflet 1.9.4, heat 0.2.0, draw 1.0.4 y markercluster 1.5.3 se cargan desde unpkg; permitir esos recursos y el proveedor configurado en políticas de red/CSP del despliegue.

## Operación

- Estados: activa = `status=True, confirmation=True`; suspendida = `status=False, confirmation=True`; pendiente = `confirmation=False`.
- Creación y edición admiten coordenadas opcionales, búsqueda por botón y pin corregible. Confirmación es explícita. Cambiar dirección, ciudad o CP invalida revisión previa.
- Calor incluye ubicaciones conocidas del filtro, confirmadas o aproximadas; filtro de calidad permite separarlas. No representa ventas ni deuda. Puntos coincidentes se agrupan y despliegan al máximo zoom.
- Selección por lista, puntos, rectángulo o polígono; solo confirmadas. Cambiar filtros retira selección fuera de resultados y avisa.
- Ubicación inicial: en el mapa desplegar **Localización inicial**, iniciar lote solo tras autorización operativa. Procesa todas las tiendas sin coordenadas hasta el máximo inicial capturado; nuevas tiendas posteriores se revisan manualmente. Cada consulta requiere POST; cerrar pestaña/pausar detiene lote tras consulta en curso. Otra sesión puede reanudarlo. Solo un lote inicial por instalación.
- Un resultado único se guarda como aproximado; múltiples resultados o ninguno quedan sin pin y aparecen en errores. Revisión manual desde ficha permite elegir candidato y confirmar. No se sobrescriben ubicaciones confirmadas.
- Proximidad = vecino más cercano por distancia geográfica desde origen; editable con Subir/Bajar. No estima tráfico, distancia vial ni tiempo. Máximo 500 tiendas por recorrido; pueden generarse varios recorridos.
- GPS se obtiene solo al pulsar botón y requiere contexto seguro/HTTPS. Si se deniega, usar dirección o pin. Origen y final/regreso quedan congelados en el itinerario compartido.
- Google Maps abre tramos con hasta tres paradas intermedias y destino, conservando continuidad. Las líneas del mapa son orientativas. Validar navegación en teléfono real antes de considerar verificación GPS completa.
- **Enlaces creados** lista los 100 más recientes para staff y permite revocar. Copiar/compartir usa el menú nativo, portapapeles o copia manual.

## Interfaces administrativas

Sin cambios bajo `/api/` ni al contrato móvil. Bajo `/adm/shops/map/`:

- GET `config/`, `data/?state=active&state=suspended&city=Tampico&cp=89000&q=...&location=confirmed`, `detail/<id>/`.
- POST `search/`: `{"shop_id": 123}` o `{"address":"Calle Comercial 10, Tampico, 89000, Mexico"}`.
- POST `location/<id>/`: `{"lat":22.2,"lng":-97.8,"confirmed":true}`.
- GET `batch/`; POST `batch/step/`: `{}`. Un paso por tienda; mismo cursor para todos los procesos.
- POST `routes/create/`: `{"shops":[123,456],"origin":{"lat":22.2,"lng":-97.8},"return_to_origin":false,"order":"manual"}`. `order` también admite `nearest`.
- GET `routes/`; POST `routes/<id>/revoke/`: `{}`.

Escrituras requieren sesión y token CSRF. Vista pública: `/adm/shops/route/<token>/`. Responde 410 cuando caduca o se revoca, no consulta datos vivos de tiendas, no permite indexación y no cachea el itinerario.

## Validación aislada

```powershell
venv\Scripts\python.exe manage.py test adm.test_shop_maps --settings=adm.shop_map_test_settings --noinput
```

SQLite en memoria; nunca usa MySQL configurado. Tests funcionales sincronizan modelos porque migraciones históricas incluyen SQL exclusivo de MySQL y diferencias anteriores. La migración nueva también se ha aplicado por separado sobre su historial hasta `cupon.0007` en SQLite en memoria. Esto no prueba bloqueo entre workers MySQL ni despliegue real.

Verificacion realizada: 21 pruebas aisladas; navegador Edge en 1440 px y emulacion de 390 px, calor/puntos, seleccion por area, recorrido de 29 tiendas en ocho tramos, filtros, ficha editable, pagina publica y colocacion de pin en formulario. Navegacion GPS en telefono fisico y concurrencia entre workers MySQL siguen pendientes de validar en entorno autorizado.
