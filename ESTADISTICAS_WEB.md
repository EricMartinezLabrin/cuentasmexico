# Estadísticas Web - CuentasMexico

## Nuevas funcionalidades implementadas

Se han agregado nuevas estadísticas al dashboard administrativo en `http://localhost:8000/adm/` que incluyen:

### 1. Contador de visitantes por página

El sistema ahora rastrea automáticamente todas las visitas a las **páginas públicas** del sitio:

**IMPORTANTE**: Solo se rastrean páginas públicas del sitio web. Las visitas al panel de administración (/adm/) NO se cuentan.

#### Páginas rastreadas:
- **Página Principal** (cuentasmexico.mx /)
- **Mi Cuenta** (/myaccount)
- **Carrito** (/cart)
- **Checkout**
- **Servicios**
- **Otras páginas públicas**

#### Páginas excluidas del rastreo:
- ❌ Panel de administración (/adm/)
- ❌ Django admin (/admin/)
- ❌ Archivos estáticos (/static/)
- ❌ Archivos multimedia (/media/)
- ❌ API endpoints (/api/, /api_bot/)
- ❌ Login/Logout
- ❌ Cuentas de Django (/accounts/)

#### Estadísticas disponibles:
- Visitas totales por página (acumuladas)
- Visitas de hoy por página
- Visitas de los últimos 7 días
- Visitantes únicos (por IP)
- Gráfico de evolución de visitas (últimos 30 días)

### 2. Estadísticas de ventas web

Se agregaron métricas específicas para ventas realizadas **SOLO** a través de la web con pasarelas de pago (MercadoPago, Stripe, PayPal).

**IMPORTANTE**: Estas estadísticas excluyen ventas manuales realizadas desde el admin (/adm).

#### Métricas disponibles:
- **Ventas Web Hoy**: Total y cantidad de ventas del día (solo pasarelas de pago)
- **Ventas Web Semanales**: Total de la semana actual
- **Ventas Web Mensuales**: Total del mes actual
- **Ventas Web Anuales**: Total del año actual
- **Gráfico de ventas**: Últimos 12 meses con desglose mensual

#### Pasarelas de pago contabilizadas:
- ✅ MercadoPago
- ✅ Stripe (para futuro)
- ✅ PayPal (para futuro)

#### Excluidas de las estadísticas web:
- ❌ Ventas en efectivo
- ❌ Ventas por transferencia bancaria
- ❌ Ventas manuales desde /adm/

### 3. Gráficos interactivos

Se implementaron gráficos visuales usando Chart.js:

1. **Gráfico de dona**: Visitas por página (últimos 7 días)
2. **Gráfico de líneas**: Evolución de visitas diarias (últimos 30 días)
3. **Gráfico de barras**: Ventas web mensuales (últimos 12 meses)

## Archivos modificados/creados

### Nuevos archivos:
- `adm/models.py` - Modelo `PageVisit` agregado
- `adm/middleware.py` - Middleware para capturar visitas automáticamente
- `ESTADISTICAS_WEB.md` - Este archivo de documentación

### Archivos modificados:
- `adm/functions/dashboard.py` - Nuevas funciones de estadísticas
- `adm/views.py` - Vista `index` actualizada con nuevos datos
- `adm/templates/adm/index.html` - Template actualizado con gráficos
- `CuentasMexico/settings.py` - Middleware registrado

### Migraciones:
- `adm/migrations/0003_pagevisit.py` - Migración para tabla PageVisit

## Cómo funciona

### Rastreo automático de visitas

El middleware `PageVisitMiddleware` captura automáticamente cada request a **páginas públicas** del sitio y registra:

- Página visitada
- URL completa
- Usuario (si está autenticado)
- IP del visitante
- User Agent (navegador)
- Referrer (página de origen)
- Session key
- Timestamp

**Rutas excluidas automáticamente:**
El middleware ignora completamente:
- `/adm/` - Panel de administración
- `/admin/` - Django admin
- `/static/` - Archivos estáticos
- `/media/` - Archivos multimedia
- `/api/` - Endpoints de API
- `/api_bot/` - API del bot
- `/login` y `/logout`
- `/accounts/` - Sistema de cuentas Django

Esto garantiza que solo se rastreen visitas reales de usuarios al sitio público.

### Filtrado de ventas web

Las estadísticas de ventas web cuentan **ÚNICAMENTE** ventas realizadas con:
- MercadoPago
- Stripe
- PayPal

**Se excluyen automáticamente**:
- Ventas marcadas como "Efectivo"
- Ventas marcadas como "Transferencia"
- Cualquier otro método de pago manual

Esto permite ver específicamente las ventas realizadas a través del sitio web con pasarelas de pago automáticas, diferenciándolas de las ventas manuales del panel de administración.

## Acceso a las estadísticas

Las nuevas estadísticas están disponibles en:

```
http://localhost:8000/adm/
```

**Nota**: Requiere permisos de superusuario (`is_superuser`)

## Configuración

El middleware está configurado en `settings.py` y se ejecuta automáticamente en cada request. No requiere configuración adicional.

Para desactivar el rastreo temporalmente, comenta esta línea en `settings.py`:

```python
# 'adm.middleware.PageVisitMiddleware',
```

## Optimización

- El modelo `PageVisit` incluye índices en campos clave para mejorar el rendimiento de las consultas
- Las consultas de estadísticas están optimizadas con agregaciones de Django ORM
- Los gráficos se renderizan en el cliente usando Chart.js para no sobrecargar el servidor

## Próximas mejoras sugeridas

1. Panel de filtros por fechas personalizadas
2. Exportación de reportes en PDF/Excel
3. Alertas automáticas de caída de tráfico
4. Análisis de conversión (visitas → ventas)
5. Dashboard en tiempo real con WebSockets
6. Comparativa con períodos anteriores
7. Segmentación por dispositivo (móvil/escritorio)
8. Mapa de calor de visitas

## Mantenimiento

### Limpieza de datos antiguos

Para mantener la base de datos ligera, se recomienda crear un comando de Django que limpie visitas antiguas periódicamente:

```python
# Ejemplo: mantener solo últimos 90 días
from datetime import timedelta
from django.utils import timezone
from adm.models import PageVisit

cutoff_date = timezone.now() - timedelta(days=90)
PageVisit.objects.filter(visited_at__lt=cutoff_date).delete()
```

## Soporte

Para preguntas o reportar problemas con las estadísticas, contactar al equipo de desarrollo.
