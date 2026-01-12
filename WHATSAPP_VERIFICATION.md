# Sistema de Verificación por WhatsApp en Registro

## Descripción General

El sistema de registro ahora incluye verificación obligatoria del número de WhatsApp mediante un código de 6 dígitos enviado al usuario.

## Flujo de Usuario

1. El usuario completa el formulario de registro con:
   - Nombre de usuario
   - Email
   - Contraseña (2 veces)
   - **País** (selector con lada automática)
   - **Número de WhatsApp** (solo números, sin lada)

2. El usuario hace clic en "Enviar código"
   - Se valida que haya seleccionado un país
   - Se valida el formato del número de teléfono (8-15 dígitos)
   - Se genera un código de 6 dígitos aleatorio
   - Se envía al API de WhatsApp configurado en `WHATSAPP_API_URL`
   - El código se guarda en caché por 10 minutos

3. Se abre un modal para ingresar el código
   - El usuario ingresa el código de 6 dígitos recibido
   - Al hacer clic en "Verificar":
     - Si el código es correcto: se marca el número como verificado
     - Si es incorrecto: se muestra un error
     - Si expiró: se pide solicitar uno nuevo

4. Una vez verificado:
   - El botón "Registrarme" se habilita
   - El usuario puede completar el registro
   - Al enviar el formulario:
     - Se verifica nuevamente que el teléfono esté verificado
     - Se crea el usuario
     - Se crea el `UserDetail` con país, lada y número de WhatsApp
     - Se agrega al grupo "Cliente" automáticamente

## Archivos Modificados/Creados

### Nuevos Archivos

1. **`index/whatsapp_verification.py`**
   - Clase `WhatsAppVerification` con métodos:
     - `generate_verification_code()`: Genera código de 6 dígitos
     - `get_lada_from_country()`: Obtiene código de país
     - `send_verification_code()`: Envía código vía WhatsApp API
     - `verify_code()`: Verifica código ingresado
     - `is_verified()`: Verifica estado de verificación

### Archivos Modificados

1. **`index/forms.py`**
   - Agregados campos: `country`, `phone_number`, `verification_code`
   - Validación de teléfono (8-15 dígitos)
   - Carga dinámica de países con ladas

2. **`index/views.py`**
   - `RegisterCustomerView.form_valid()`:
     - Valida verificación de WhatsApp
     - Crea `UserDetail` con datos de WhatsApp
   - Nuevas vistas API:
     - `send_whatsapp_verification()`: POST para enviar código
     - `verify_whatsapp_code()`: POST para verificar código

3. **`index/urls.py`**
   - `/api/send-whatsapp-verification/`: Enviar código
   - `/api/verify-whatsapp-code/`: Verificar código

4. **`index/templates/index/register.html`**
   - Campos de país y WhatsApp
   - Botón "Enviar código"
   - Modal de verificación
   - JavaScript para manejo del flujo
   - Validaciones en frontend

5. **`CuentasMexico/settings.py`**
   - Variable `WHATSAPP_API_URL` (desde `.env`)

## Configuración Requerida

### Variables de Entorno (.env)

```bash
WHATSAPP_API_URL=https://n8n.fadetechs.com/webhook/e17ed441-4396-447e-a632-1801966f8001
```

### API de WhatsApp

El endpoint debe aceptar:

```json
{
  "phone": "+525512345678",  // Lada + número
  "message": "Tu código de verificación para Cuentas México es: 123456\n\nEste código expira en 10 minutos."
}
```

Y responder con status 200 si fue exitoso.

## Caché

El sistema utiliza Django cache para:

1. **Códigos de verificación** (10 minutos):
   - Key: `whatsapp_verify_{country}_{phone_number}`
   - Value: código de 6 dígitos

2. **Estado de verificación** (1 hora):
   - Key: `whatsapp_verified_{country}_{phone_number}`
   - Value: `True`

## Seguridad

- ✅ El código expira en 10 minutos
- ✅ El estado "verificado" expira en 1 hora (tiempo para completar registro)
- ✅ Se valida la verificación tanto en frontend como backend
- ✅ Los códigos son aleatorios de 6 dígitos
- ✅ CSRF exempt en APIs (solo para estas vistas específicas)
- ✅ El usuario debe estar verificado antes de crear la cuenta

## Validaciones

### Frontend (JavaScript)
- País seleccionado
- Teléfono no vacío
- Código de 6 dígitos
- Botón de registro deshabilitado hasta verificar

### Backend (Python)
- Formato de teléfono (regex: `^\d{8,15}$`)
- País existe en lista
- Código coincide con el guardado
- Código no expirado
- Teléfono verificado al momento del registro

## Pruebas

Ejecutar tests:

```bash
source venv/bin/activate
python manage.py shell < tests/test_whatsapp_verification.py
```

## Troubleshooting

### "WhatsApp API no configurada"
- Verificar que `WHATSAPP_API_URL` esté en `.env`
- Verificar que settings.py cargue la variable

### "Código expirado"
- Los códigos expiran en 10 minutos
- Solicitar un nuevo código

### "Debes verificar tu número de WhatsApp antes de registrarte"
- El estado de verificación expiró (1 hora)
- Verificar nuevamente el número

### "Error de conexión"
- Verificar que el endpoint de WhatsApp esté disponible
- Revisar logs en `logs/django.log`
