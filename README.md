# cuentasmexico

## Wiki

- [Contrato esperado: wiki de Soporte](docs/wiki-soporte.md)
- [Integración móvil: solicitudes de soporte](docs/soporte-app-movil.md)

## Version de la app móvil

`GET /api/app/version/` es público y devuelve la versión publicada, URL de actualización y notas opcionales.

Configurar en Django mediante `.env`:

```env
APP_VERSION=1.1.0
APP_UPDATE_URL=https://downloads.example.com/tiendas-mexico-1.1.0.apk
APP_RELEASE_NOTES=Mejoras de ventas y credito
```

La app solo debe mostrar actualización cuando `version` sea mayor que su versión instalada y `update_url` no esté vacío. Si la consulta falla, debe continuar normalmente.
