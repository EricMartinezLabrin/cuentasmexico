# Integración móvil: solicitudes de soporte

Documento para actualizar la app móvil. El backend expone:

- `GET /api/support/customer-lookup/`
- `POST /api/support/error-image/`

El endpoint existente `GET /api/wiki/sections/` no cambia y sigue usándose para las tarjetas informativas de Soporte.

## Autenticación

Usar el `access_token` entregado por el login OTP:

```http
Authorization: Bearer <access_token>
```

No enviar `X-Clerk-User-Id` para estos endpoints. Si la API responde `401`, borrar el token local y regresar al flujo de login.

La cuenta debe pertenecer a una tienda activa y aprobada. Si no, la API responde `403`.

## Flujo de pantalla

1. Trabajador captura teléfono del cliente.
2. App elimina espacios, guiones, paréntesis y prefijos no numéricos.
3. App conserva los últimos 10 dígitos y consulta `customer-lookup`.
4. Si `exists` es `false`, mostrar cliente inexistente.
5. Si `has_active_service` es `false`, impedir crear soporte y mostrar que no tiene servicio activo.
6. Si ambos valores son `true`, permitir elegir una imagen.
7. Subir imagen con `error-image`.
8. Abrir WhatsApp con el texto preparado.
9. El trabajador debe presionar **Enviar** manualmente.

## Buscar cliente

```http
GET /api/support/customer-lookup/?phone=8331234567
Authorization: Bearer <access_token>
```

El teléfono enviado debe contener exactamente 10 dígitos. El backend hace la normalización mexicana y busca globalmente.

Respuesta `200` en todos los resultados de negocio:

```json
{
  "exists": true,
  "customer_phone": "8331234567",
  "has_active_service": true
}
```

No consultar ventas, cuentas ni datos personales adicionales desde la app para calcular `has_active_service`.

## Subir foto

Formatos aceptados: JPEG, PNG y WebP. Tamaño máximo: 10 MB.

```ts
const form = new FormData();
form.append("customer_phone", customerPhone10Digits);
form.append("image", {
  uri: image.uri,
  name: image.fileName ?? "support-error.jpg",
  type: image.mimeType ?? "image/jpeg",
});

const response = await api.post("/api/support/error-image/", form);
const { photo_url, expires_in } = response.data;
```

Con `fetch`, no fijar manualmente `Content-Type`; dejar que el cliente genere el boundary de `multipart/form-data`.

Respuesta `201`:

```json
{
  "photo_url": "https://...",
  "expires_in": 86400
}
```

La URL es firmada y expira en 24 horas. No guardar credenciales de Backblaze ni intentar subir archivos directamente desde la app.

## WhatsApp

La app no envía el mensaje automáticamente:

```ts
import { Linking } from "react-native";

const text = [
  `Hola, soy el dueño de la tienda ${shopName}.`,
  `Telefono de la tienda: ${shopPhone}.`,
  `Numero del cliente: ${customerPhone}.`,
  photoUrl
    ? `Link de la foto del error: ${photoUrl}.`
    : "Solicitud creada sin foto del error.",
].join("\n");

const whatsappUrl =
  `https://wa.me/528335355863?text=${encodeURIComponent(text)}`;

await Linking.openURL(whatsappUrl);
```

Si no hay foto, mostrar una advertencia grande antes de abrir WhatsApp:

> El cliente debe enviar la foto del error cuando Soporte la solicite. Sin la foto, Soporte no podrá atenderlo.

## Errores de UI

| HTTP | Código | Acción |
| --- | --- | --- |
| 400 | `INVALID_PHONE` / `INVALID_CUSTOMER` | Corregir teléfono |
| 400 | `CUSTOMER_NO_ACTIVE_SERVICE` | Impedir soporte y explicar motivo |
| 400 | `INVALID_ERROR_IMAGE` | Pedir JPEG, PNG o WebP menor a 10 MB |
| 401 | `SESSION_INVALID` | Borrar sesión y pedir login |
| 403 | `SUPPORT_FORBIDDEN` | Mostrar que la tienda no está activa/aprobada |
| 404 | `CUSTOMER_NOT_FOUND` | Mostrar cliente inexistente |
| 502 | `SUPPORT_IMAGE_UPLOAD_FAILED` | Permitir reintentar carga |

## Backblaze

La app no recibe ni configura credenciales. Estas variables existentes solo viven en backend/Dokploy:

```text
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
AWS_STORAGE_BUCKET_NAME
AWS_S3_ENDPOINT_URL
AWS_S3_REGION_NAME
AWS_S3_CUSTOM_DOMAIN
```

La app no construye URLs; la API entrega `photo_url` firmado.
