# Contrato esperado: wiki de Soporte

La pestaña **Soporte** consume un endpoint del backend Django para mostrar sus
secciones.

Si el endpoint no existe, falla o devuelve una lista vacía, la app no muestra
tarjetas y conserva únicamente el botón **Hablar con soporte**.

## Endpoint requerido

### `GET /api/wiki/sections/`

Headers enviados por la app:

```http
X-Clerk-User-Id: <id-del-usuario>
```

El endpoint puede exigir autenticación según las reglas del backend. La app no
envía body.

Respuesta exitosa `200 OK`:

```json
{
  "sections": [
    {
      "id": "pagos",
      "title": "Pagos",
      "body": "Consulta tu saldo, crédito disponible y pagos pendientes.",
      "order": 1
    },
    {
      "id": "cuentas",
      "title": "Cuentas",
      "body": "Ayuda con accesos, cambios y renovaciones.",
      "order": 2
    }
  ]
}
```

Campos:

- `sections`: arreglo. Si es `[]`, no se muestran secciones.
- `id`: string o número, único dentro de la respuesta.
- `title`: título visible; requerido.
- `body`: descripción visible; requerida.
- `order`: número opcional para ordenar ascendentemente. Si se omite, se
  considera `0`.

Respuesta sin contenido:

```json
{ "sections": [] }
```

La app también acepta `204 No Content`, `404 Not Found` o errores de red como
ausencia de secciones y mantiene disponible el botón de WhatsApp.

## Endpoint opcional recomendado

### `GET /api/wiki/sections/<id>/`

Puede crearse para una futura pantalla de detalle. La versión actual de la app
no lo consume.

Respuesta sugerida `200 OK`:

```json
{
  "id": "pagos",
  "title": "Pagos",
  "body": "Contenido completo de la sección...",
  "order": 1,
  "updated_at": "2026-09-24T12:00:00Z"
}
```

## Notas de implementación Django

- Aplicar permisos para que el usuario solo reciba las secciones
  correspondientes a su tienda, si el wiki es privado.
- Excluir secciones inactivas y ordenar por `order` en el backend.
- Mantener `title` y `body` como texto seguro para renderizado en la app.
