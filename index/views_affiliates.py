# python
from functools import wraps

# django
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST, require_GET
from django.core.paginator import Paginator
from django.utils import timezone
from django.db.models import Sum, Count

# models
from adm.models import (
    Affiliate, AffiliateSale, AffiliateCommission,
    AffiliateWithdrawal, AffiliateClick, AffiliateNotification,
    AffiliateSettings
)

# forms
from .forms_affiliates import (
    ActivarAfiliadoForm, PerfilAfiliadoForm, SolicitarRetiroForm
)

# utils
from .utils_affiliates import (
    generar_qr_afiliado, get_affiliate_link, registrar_clic_afiliado,
    get_estadisticas_afiliado, crear_notificacion_afiliado
)


def affiliate_required(view_func):
    """Decorador que verifica que el usuario tenga rol de afiliado activo"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, 'Debes iniciar sesion para acceder a esta seccion.')
            return redirect('login')

        try:
            affiliate = request.user.affiliate
            if affiliate.status != 'activo':
                messages.warning(request, 'Tu cuenta de afiliado esta inactiva o suspendida.')
                return redirect('afiliados_activar')
        except Affiliate.DoesNotExist:
            messages.info(request, 'Activa tu cuenta de afiliado para acceder.')
            return redirect('afiliados_activar')

        return view_func(request, *args, **kwargs)
    return wrapper


def get_affiliate_context(request):
    """Obtiene contexto comun para las vistas de afiliados"""
    affiliate = request.user.affiliate
    settings_aff = AffiliateSettings.get_settings()

    # Notificaciones no leidas
    notificaciones_no_leidas = affiliate.notificaciones.filter(leida=False).count()

    return {
        'affiliate': affiliate,
        'affiliate_settings': settings_aff,
        'notificaciones_no_leidas': notificaciones_no_leidas,
    }


# ============================================
# VISTAS PUBLICAS
# ============================================

def affiliate_redirect(request, codigo):
    """
    Procesa clics en links de afiliado y redirige a la tienda.
    URL: /afiliados/r/<codigo>/
    """
    try:
        affiliate = Affiliate.objects.get(codigo_afiliado=codigo.upper(), status='activo')

        # Registrar clic
        registrar_clic_afiliado(request, affiliate)

        # Guardar en sesion para tracking de conversion
        request.session['affiliate_code'] = affiliate.codigo_afiliado
        request.session.set_expiry(60 * 60 * 24 * 30)  # 30 dias

    except Affiliate.DoesNotExist:
        pass  # Ignorar codigos invalidos

    # Redirigir a la tienda
    return redirect('index')


# ============================================
# ACTIVACION DE AFILIADO
# ============================================

@login_required
def activar_afiliado(request):
    """
    Vista para activar el rol de afiliado en un usuario existente.
    URL: /afiliados/activar/
    """
    # Verificar si ya es afiliado
    try:
        affiliate = request.user.affiliate
        if affiliate.status == 'activo':
            return redirect('afiliados_dashboard')
        # Si existe pero esta inactivo, mostrar mensaje
        messages.info(request, 'Tu cuenta de afiliado esta inactiva. Contacta a soporte.')
        return render(request, 'index/afiliados/activar.html', {
            'ya_es_afiliado': True,
            'affiliate': affiliate
        })
    except Affiliate.DoesNotExist:
        pass

    settings_aff = AffiliateSettings.get_settings()

    if request.method == 'POST':
        form = ActivarAfiliadoForm(request.POST)
        if form.is_valid():
            # Crear afiliado
            affiliate = Affiliate(user=request.user)

            # Verificar codigo de referido
            codigo_referido = form.cleaned_data.get('codigo_referido')
            if codigo_referido:
                try:
                    referidor = Affiliate.objects.get(
                        codigo_afiliado=codigo_referido,
                        status='activo'
                    )
                    affiliate.referido_por = referidor
                    affiliate.fecha_referido = timezone.now()
                except Affiliate.DoesNotExist:
                    pass  # Ya validado en el form

            affiliate.save()

            # Notificar al referidor si existe
            if affiliate.referido_por:
                crear_notificacion_afiliado(
                    affiliate.referido_por,
                    'referido',
                    'Nuevo Referido!',
                    f'{request.user.username} se ha unido como afiliado usando tu codigo.',
                    '/afiliados/referidos/'
                )

            messages.success(request, 'Tu cuenta de afiliado ha sido activada exitosamente!')
            return redirect('afiliados_dashboard')
    else:
        # Pre-llenar codigo de referido si viene de un link
        initial = {}
        ref_code = request.GET.get('ref')
        if ref_code:
            initial['codigo_referido'] = ref_code
        form = ActivarAfiliadoForm(initial=initial)

    return render(request, 'index/afiliados/activar.html', {
        'form': form,
        'settings': settings_aff,
        'ya_es_afiliado': False
    })


# ============================================
# DASHBOARD
# ============================================

@login_required
@affiliate_required
def dashboard(request):
    """
    Dashboard principal del afiliado.
    URL: /afiliados/
    """
    context = get_affiliate_context(request)
    affiliate = context['affiliate']

    # Estadisticas del mes
    stats = get_estadisticas_afiliado(affiliate, 'mes')
    context['stats'] = stats

    # Ultimas 5 ventas
    context['ultimas_ventas'] = affiliate.ventas.select_related('sale')[:5]

    # Ultimas 5 notificaciones
    context['ultimas_notificaciones'] = affiliate.notificaciones.all()[:5]

    # Tipo de soporte
    tipo_soporte, contacto_soporte = affiliate.get_tipo_soporte()
    context['tipo_soporte'] = tipo_soporte
    context['contacto_soporte'] = contacto_soporte

    return render(request, 'index/afiliados/dashboard.html', context)


# ============================================
# ESTADISTICAS
# ============================================

@login_required
@affiliate_required
def estadisticas(request):
    """
    Estadisticas detalladas del afiliado.
    URL: /afiliados/estadisticas/
    """
    context = get_affiliate_context(request)
    affiliate = context['affiliate']

    periodo = request.GET.get('periodo', 'mes')
    if periodo not in ['semana', 'mes', 'ano', 'total']:
        periodo = 'mes'

    stats = get_estadisticas_afiliado(affiliate, periodo)
    context['stats'] = stats
    context['periodo_actual'] = periodo

    return render(request, 'index/afiliados/estadisticas.html', context)


# ============================================
# VENTAS
# ============================================

@login_required
@affiliate_required
def ventas_list(request):
    """
    Lista de ventas generadas por el afiliado.
    URL: /afiliados/ventas/
    """
    context = get_affiliate_context(request)
    affiliate = context['affiliate']

    ventas = affiliate.ventas.select_related('sale', 'sale__customer', 'sale__account__account_name')

    # Paginacion
    paginator = Paginator(ventas, 20)
    page = request.GET.get('page', 1)
    context['ventas'] = paginator.get_page(page)

    return render(request, 'index/afiliados/ventas/list.html', context)


# ============================================
# COMISIONES
# ============================================

@login_required
@affiliate_required
def comisiones_list(request):
    """
    Lista de comisiones del afiliado.
    URL: /afiliados/comisiones/
    """
    context = get_affiliate_context(request)
    affiliate = context['affiliate']

    # Filtro por status
    status_filter = request.GET.get('status', '')
    comisiones = affiliate.comisiones.all()

    if status_filter and status_filter in ['pendiente', 'aprobada', 'rechazada']:
        comisiones = comisiones.filter(status=status_filter)

    # Paginacion
    paginator = Paginator(comisiones, 20)
    page = request.GET.get('page', 1)
    context['comisiones'] = paginator.get_page(page)
    context['status_filter'] = status_filter

    # Totales
    context['total_aprobadas'] = affiliate.comisiones.filter(
        status='aprobada'
    ).aggregate(total=Sum('monto'))['total'] or 0

    context['total_pendientes'] = affiliate.comisiones.filter(
        status='pendiente'
    ).aggregate(total=Sum('monto'))['total'] or 0

    return render(request, 'index/afiliados/comisiones/list.html', context)


# ============================================
# RETIROS
# ============================================

@login_required
@affiliate_required
def retiros_list(request):
    """
    Lista de retiros del afiliado.
    URL: /afiliados/retiros/
    """
    context = get_affiliate_context(request)
    affiliate = context['affiliate']

    retiros = affiliate.retiros.all()

    # Paginacion
    paginator = Paginator(retiros, 20)
    page = request.GET.get('page', 1)
    context['retiros'] = paginator.get_page(page)

    return render(request, 'index/afiliados/retiros/list.html', context)


@login_required
@affiliate_required
def solicitar_retiro(request):
    """
    Formulario para solicitar un retiro.
    URL: /afiliados/retiros/solicitar/
    """
    context = get_affiliate_context(request)
    affiliate = context['affiliate']

    if request.method == 'POST':
        form = SolicitarRetiroForm(affiliate, request.POST)
        if form.is_valid():
            monto = form.cleaned_data['monto']

            # Crear snapshot de datos de pago
            datos_pago = {}
            if affiliate.metodo_retiro == 'transferencia':
                datos_pago = {
                    'banco_nombre': affiliate.banco_nombre,
                    'banco_titular': affiliate.banco_titular,
                    'banco_cuenta': affiliate.banco_cuenta,
                    'banco_clabe': affiliate.banco_clabe,
                }
            elif affiliate.metodo_retiro == 'paypal':
                datos_pago = {
                    'paypal_email': affiliate.paypal_email,
                }

            # Crear retiro
            retiro = AffiliateWithdrawal.objects.create(
                affiliate=affiliate,
                monto=monto,
                metodo=affiliate.metodo_retiro,
                datos_pago=datos_pago
            )

            # Si es credito, aprobar automaticamente
            if affiliate.metodo_retiro == 'credito':
                retiro.aprobar()
                messages.success(
                    request,
                    f'Tu retiro de ${monto:.2f} MXN ha sido procesado como credito en tienda.'
                )
            else:
                messages.success(
                    request,
                    f'Tu solicitud de retiro de ${monto:.2f} MXN ha sido enviada. '
                    f'Te notificaremos cuando sea procesada.'
                )

            return redirect('afiliados_retiros')
    else:
        form = SolicitarRetiroForm(affiliate)

    context['form'] = form
    return render(request, 'index/afiliados/retiros/solicitar.html', context)


# ============================================
# PERFIL
# ============================================

@login_required
@affiliate_required
def perfil(request):
    """
    Ver perfil del afiliado.
    URL: /afiliados/perfil/
    """
    context = get_affiliate_context(request)
    return render(request, 'index/afiliados/perfil/view.html', context)


@login_required
@affiliate_required
def editar_perfil(request):
    """
    Editar perfil del afiliado.
    URL: /afiliados/perfil/editar/
    """
    context = get_affiliate_context(request)
    affiliate = context['affiliate']

    if request.method == 'POST':
        form = PerfilAfiliadoForm(request.POST, instance=affiliate)
        if form.is_valid():
            form.save()
            messages.success(request, 'Perfil actualizado correctamente.')
            return redirect('afiliados_perfil')
    else:
        form = PerfilAfiliadoForm(instance=affiliate)

    context['form'] = form
    return render(request, 'index/afiliados/perfil/edit.html', context)


# ============================================
# REFERIDOS
# ============================================

@login_required
@affiliate_required
def referidos_list(request):
    """
    Lista de afiliados referidos.
    URL: /afiliados/referidos/
    """
    context = get_affiliate_context(request)
    affiliate = context['affiliate']

    referidos = affiliate.referidos.all()

    # Paginacion
    paginator = Paginator(referidos, 20)
    page = request.GET.get('page', 1)
    context['referidos'] = paginator.get_page(page)

    # Link de referido
    context['link_referido'] = f"{get_affiliate_link(affiliate)}?ref={affiliate.codigo_afiliado}"

    return render(request, 'index/afiliados/referidos/list.html', context)


# ============================================
# MATERIALES PROMOCIONALES
# ============================================

@login_required
@affiliate_required
def materiales(request):
    """
    Materiales promocionales (links, codigos, QR).
    URL: /afiliados/materiales/
    """
    context = get_affiliate_context(request)
    affiliate = context['affiliate']

    context['link_afiliado'] = get_affiliate_link(affiliate)
    context['link_referido'] = f"{get_affiliate_link(affiliate)}?ref={affiliate.codigo_afiliado}"

    return render(request, 'index/afiliados/materiales.html', context)


@login_required
@affiliate_required
def generar_qr(request, codigo):
    """
    Genera y descarga QR del afiliado.
    URL: /afiliados/qr/<codigo>/
    """
    affiliate = request.user.affiliate

    # Verificar que el codigo pertenece al usuario
    if affiliate.codigo_afiliado != codigo.upper():
        return HttpResponse('No autorizado', status=403)

    # Generar QR
    size = int(request.GET.get('size', 300))
    size = min(max(size, 100), 1000)  # Limitar entre 100 y 1000

    buffer = generar_qr_afiliado(affiliate, size)

    if buffer is None:
        return HttpResponse('Error generando QR. Instala: pip install qrcode[pil]', status=500)

    response = HttpResponse(buffer.getvalue(), content_type='image/png')
    response['Content-Disposition'] = f'attachment; filename="qr_{affiliate.codigo_afiliado}.png"'
    return response


# ============================================
# NOTIFICACIONES
# ============================================

@login_required
@affiliate_required
def notificaciones(request):
    """
    Lista de notificaciones del afiliado.
    URL: /afiliados/notificaciones/
    """
    context = get_affiliate_context(request)
    affiliate = context['affiliate']

    notificaciones_qs = affiliate.notificaciones.all()

    # Paginacion
    paginator = Paginator(notificaciones_qs, 20)
    page = request.GET.get('page', 1)
    context['notificaciones'] = paginator.get_page(page)

    return render(request, 'index/afiliados/notificaciones.html', context)


@login_required
@affiliate_required
@require_POST
def marcar_notificacion_leida(request, pk):
    """
    Marca una notificacion como leida.
    URL: /afiliados/notificaciones/marcar-leida/<pk>/
    """
    affiliate = request.user.affiliate
    notificacion = get_object_or_404(AffiliateNotification, pk=pk, affiliate=affiliate)
    notificacion.marcar_leida()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})

    return redirect('afiliados_notificaciones')


@login_required
@affiliate_required
@require_POST
def marcar_todas_leidas(request):
    """
    Marca todas las notificaciones como leidas.
    URL: /afiliados/notificaciones/marcar-todas-leidas/
    """
    affiliate = request.user.affiliate
    affiliate.notificaciones.filter(leida=False).update(leida=True)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})

    messages.success(request, 'Todas las notificaciones marcadas como leidas.')
    return redirect('afiliados_notificaciones')


# ============================================
# API INTERNA (AJAX)
# ============================================

@login_required
@affiliate_required
@require_GET
def api_stats(request):
    """
    API para obtener estadisticas (AJAX).
    URL: /afiliados/api/stats/
    """
    affiliate = request.user.affiliate
    periodo = request.GET.get('periodo', 'mes')

    stats = get_estadisticas_afiliado(affiliate, periodo)

    return JsonResponse(stats)


@login_required
@affiliate_required
@require_GET
def api_notificaciones_count(request):
    """
    API para obtener conteo de notificaciones no leidas.
    URL: /afiliados/api/notificaciones-count/
    """
    affiliate = request.user.affiliate
    count = affiliate.notificaciones.filter(leida=False).count()

    return JsonResponse({'count': count})
