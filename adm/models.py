# python
from datetime import timedelta

# django
from django.db import models
from django.db.models import Q
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.utils import timezone


class Level(models.Model):
    name = models.CharField(max_length=100)
    discount = models.IntegerField()

    def __str__(self):
        return self.name


class Business(models.Model):
    name = models.CharField(max_length=50)
    email = models.EmailField(max_length=30)
    url = models.CharField(max_length=50)
    phoneNumberRegex = RegexValidator(regex=r"^\+?1?\d{8,15}$")
    phone_number = models.CharField(
        validators=[phoneNumberRegex], max_length=16, null=False, blank=False)
    stripe_customer_key = models.CharField(
        max_length=255, null=True, blank=True)
    stripe_secret_key = models.CharField(max_length=255, null=True, blank=True)
    stripe_sandbox = models.BooleanField(default=True)
    flow_customer_key = models.CharField(max_length=255, null=True, blank=True)
    flow_secret_key = models.CharField(max_length=255, null=True, blank=True)
    flow_show = models.BooleanField(default=True)
    logo = models.FileField(upload_to="settings/", null=True, blank=True)
    free_days = models.IntegerField(default=7)

    def __str__(self):
        return self.name


class Service(models.Model):
    description = models.CharField(max_length=40)
    info = models.CharField(max_length=255, null=True, blank=True)
    perfil_quantity = models.IntegerField()
    status = models.BooleanField(default=True)
    logo = models.FileField(upload_to="settings/", null=True, blank=True)
    old_id = models.IntegerField(blank=True, null=True)
    price = models.IntegerField(default=85)
    regular_price = models.IntegerField(default=100)

    def __str__(self):
        return self.description


class Bank(models.Model):
    business = models.ForeignKey(Business, on_delete=models.DO_NOTHING)
    bank_name = models.CharField(max_length=30, null=False)
    headline = models.CharField(max_length=30, null=False)
    card_number = models.CharField(max_length=16, null=False)
    clabe = models.CharField(max_length=18, null=False)
    logo = models.FileField(upload_to="bank/", null=True, blank=True)
    status = models.BooleanField(default=True)

    def __str__(self):
        return str(self.card_number) + " " + self.headline


class PaymentMethod(models.Model):
    description = models.CharField(max_length=40, null=False)

    def __str__(self):
        return self.description


class Status(models.Model):
    description = models.CharField(max_length=40, null=False)

    def __str__(self):
        return self.description


class UserDetail(models.Model):
    business = models.ForeignKey(Business, on_delete=models.DO_NOTHING)
    phoneNumberRegex = RegexValidator(regex=r"^\+?1?\d{8,15}$")
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone_number = models.CharField(
        validators=[phoneNumberRegex], max_length=16, null=False)
    lada = models.IntegerField(null=False)
    country = models.CharField(max_length=40, null=False)
    picture = models.FileField(upload_to="users/", null=True, blank=True)
    reference = models.IntegerField(null=True, blank=True)
    reference_used = models.BooleanField(default=False)
    free_days = models.IntegerField(default=0)
    level = models.ForeignKey(
        Level, on_delete=models.CASCADE, blank=True, null=True)
    token = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return self.user.username


class Supplier(models.Model):
    business = models.ForeignKey(Business, on_delete=models.DO_NOTHING)
    phoneNumberRegex = RegexValidator(regex=r"^\+?1?\d{8,15}$")
    name = models.CharField(max_length=50, null=False, blank=False)
    phone_number = models.CharField(
        validators=[phoneNumberRegex], max_length=16, null=False, blank=False)

    def __str__(self):
        return self.name


class UserPhoneHistory(models.Model):
    """
    Registro histórico de cambios de teléfono de usuarios
    """
    user_detail = models.ForeignKey(UserDetail, on_delete=models.CASCADE, related_name='phone_history')
    old_phone_number = models.CharField(max_length=16, null=True, blank=True)
    old_lada = models.IntegerField(null=True, blank=True)
    new_phone_number = models.CharField(max_length=16, null=False)
    new_lada = models.IntegerField(null=False)
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)
    reason = models.TextField(null=True, blank=True, max_length=500)
    
    class Meta:
        ordering = ['-changed_at']
        verbose_name = 'Historial de Cambios de Teléfono'
        verbose_name_plural = 'Historiales de Cambios de Teléfono'
    
    def __str__(self):
        return f"{self.user_detail.user.username} - {self.changed_at}"
    
    @property
    def old_phone_full(self):
        if self.old_lada and self.old_phone_number:
            return f"+{self.old_lada} {self.old_phone_number}"
        return "No registrado"
    
    @property
    def new_phone_full(self):
        return f"+{self.new_lada} {self.new_phone_number}"


class Account(models.Model):
    business = models.ForeignKey(Business, on_delete=models.DO_NOTHING)
    supplier = models.ForeignKey(
        Supplier, on_delete=models.DO_NOTHING, default=1)
    status = models.BooleanField(default=True)
    customer = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.CASCADE, related_name='adm_customer')
    created_by = models.ForeignKey(
        User, on_delete=models.DO_NOTHING, related_name='created_by')
    modified_by = models.ForeignKey(
        User, on_delete=models.DO_NOTHING, related_name='modified_by')
    account_name = models.ForeignKey(Service, on_delete=models.DO_NOTHING)
    created_at = models.DateTimeField(
        auto_now=False, auto_now_add=True, null=False)
    expiration_date = models.DateTimeField(
        auto_now=False, auto_now_add=False, null=False)
    renewal_date = models.DateTimeField(null=True, blank=True)
    email = models.EmailField(max_length=50, null=False)
    password = models.CharField(max_length=50, null=False)
    pin = models.IntegerField(blank=True, null=True)
    comments = models.CharField(
        max_length=250, null=True, blank=True, default="")
    profile = models.IntegerField(null=True, blank=True, default=1)
    sent = models.BooleanField(null=True, blank=True, default=False)
    renovable = models.BooleanField(null=True, blank=True, default=False)
    external_status = models.CharField(
        max_length=50, default='Disponible', 
        choices=[('Disponible', 'Disponible'), ('No Disponible', 'No Disponible'), ('Suspendida', 'Suspendida')])

    def __str__(self):
        return self.account_name.description + "," + self.email


class Sale(models.Model):
    business = models.ForeignKey(Business, on_delete=models.DO_NOTHING)
    user_seller = models.ForeignKey(
        User, on_delete=models.DO_NOTHING, related_name="Worker")
    bank = models.ForeignKey(
        Bank, on_delete=models.DO_NOTHING, blank=True, null=True)
    customer = models.ForeignKey(
        User, on_delete=models.DO_NOTHING, related_name='Customer')
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    status = models.BooleanField(default=True)
    payment_method = models.ForeignKey(
        PaymentMethod, on_delete=models.DO_NOTHING, blank=True, null=True)
    created_at = models.DateTimeField(auto_now=False, auto_now_add=True)
    expiration_date = models.DateTimeField(auto_now=False, auto_now_add=False)
    payment_amount = models.IntegerField(null=False)
    invoice = models.CharField(max_length=250, null=False)
    comment = models.CharField(max_length=255, blank=True, null=True)
    old_acc = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return self.customer.userdetail.phone_number


class Credits(models.Model):
    customer = models.ForeignKey(User, on_delete=models.CASCADE)
    date = models.DateTimeField(auto_now=True)
    credits = models.IntegerField(default=0)
    detail = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f'{self.customer.username}: {credits} creditos.'


class IndexCarouselImage(models.Model):
    """Imágenes del carrusel principal del index"""
    image = models.ImageField(upload_to="index/carousel/")
    title = models.CharField(max_length=100, blank=True, null=True)
    order = models.IntegerField(default=0, help_text="Orden de aparición (menor número = primero)")
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', '-created_at']
        verbose_name = "Imagen del Carrusel"
        verbose_name_plural = "Imágenes del Carrusel"

    def __str__(self):
        return f"Carrusel {self.order} - {self.title or 'Sin título'}"


class IndexPromoImage(models.Model):
    """Imágenes de las promociones del index"""
    POSITION_CHOICES = [
        ('left', 'Izquierda'),
        ('right', 'Derecha'),
    ]

    image = models.ImageField(upload_to="index/promos/")
    title = models.CharField(max_length=100, blank=True, null=True)
    position = models.CharField(max_length=10, choices=POSITION_CHOICES, default='left')
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['position', '-created_at']
        verbose_name = "Imagen de Promoción"
        verbose_name_plural = "Imágenes de Promociones"

    def __str__(self):
        return f"Promo {self.get_position_display()} - {self.title or 'Sin título'}"


class PageVisit(models.Model):
    """Rastrear visitas por página"""
    PAGE_CHOICES = [
        ('home', 'Página Principal (cuentasmexico.mx)'),
        ('myaccount', 'Mi Cuenta (/myaccount)'),
        ('cart', 'Carrito (/cart)'),
        ('checkout', 'Checkout'),
        ('services', 'Servicios'),
        ('service', 'Clic en Servicio'),
        ('other', 'Otra'),
    ]

    page = models.CharField(max_length=50, choices=PAGE_CHOICES)
    page_url = models.CharField(max_length=500)
    service = models.ForeignKey(Service, on_delete=models.SET_NULL, null=True, blank=True, help_text="Servicio si se registró un clic en uno")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)
    referrer = models.CharField(max_length=500, blank=True, null=True)
    visited_at = models.DateTimeField(auto_now_add=True)
    session_key = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        ordering = ['-visited_at']
        verbose_name = "Visita de Página"
        verbose_name_plural = "Visitas de Páginas"
        indexes = [
            models.Index(fields=['page', 'visited_at']),
            models.Index(fields=['visited_at']),
            models.Index(fields=['session_key']),
        ]

    def __str__(self):
        if self.page == 'service' and self.service:
            return f"Clic en {self.service.description} - {self.visited_at.strftime('%Y-%m-%d %H:%M')}"
        return f"{self.get_page_display()} - {self.visited_at.strftime('%Y-%m-%d %H:%M')}"


class Promocion(models.Model):
    """Modelo para gestionar promociones de la tienda"""
    TIPO_DESCUENTO_CHOICES = [
        ('porcentaje', 'Porcentaje'),
        ('monto_fijo', 'Monto Fijo'),
        ('nxm', 'NxM (ej. 2x1, 3x2)'),
    ]

    APLICACION_CHOICES = [
        ('todos', 'Todos los servicios'),
        ('especificos', 'Servicios específicos'),
        ('excepto', 'Todos excepto algunos'),
    ]

    STATUS_CHOICES = [
        ('activa', 'Activa'),
        ('inactiva', 'Inactiva'),
        ('programada', 'Programada'),
        ('expirada', 'Expirada'),
    ]

    TIPO_NXM_CHOICES = [
        ('meses', 'Meses de suscripción (ej. 3 meses por el precio de 2)'),
        ('servicios', 'Servicios diferentes (ej. 3 servicios por el precio de 2)'),
        ('perfiles', 'Perfiles/Pantallas (ej. 3 perfiles por el precio de 2)'),
    ]

    # Información básica
    nombre = models.CharField(max_length=200, help_text="Nombre de la promoción")
    descripcion = models.TextField(blank=True, null=True, help_text="Descripción detallada")

    # Tipo de descuento
    tipo_descuento = models.CharField(max_length=20, choices=TIPO_DESCUENTO_CHOICES, default='porcentaje')
    porcentaje_descuento = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, help_text="Porcentaje de descuento (ej. 50 para 50%)")
    monto_descuento = models.IntegerField(blank=True, null=True, help_text="Monto fijo de descuento en pesos")

    # Para promociones tipo NxM (2x1, 3x2, etc)
    tipo_nxm = models.CharField(
        max_length=20,
        choices=TIPO_NXM_CHOICES,
        default='meses',
        blank=True,
        null=True,
        help_text="A qué se aplica la promoción NxM"
    )
    cantidad_llevar = models.IntegerField(blank=True, null=True, help_text="Cantidad que lleva el cliente (ej. 3 en 3x2)")
    cantidad_pagar = models.IntegerField(blank=True, null=True, help_text="Cantidad que paga el cliente (ej. 2 en 3x2)")

    # Aplicación de la promoción
    aplicacion = models.CharField(max_length=20, choices=APLICACION_CHOICES, default='todos')
    servicios = models.ManyToManyField(Service, blank=True, related_name='promociones', help_text="Servicios a los que aplica o excluye")

    # Fechas
    fecha_inicio = models.DateTimeField(blank=True, null=True, help_text="Fecha y hora de inicio (dejar vacío para iniciar inmediatamente)")
    fecha_fin = models.DateTimeField(blank=True, null=True, help_text="Fecha y hora de finalización (dejar vacío para sin límite)")

    # Estado
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='inactiva')

    # Imagen para banner
    imagen = models.ImageField(upload_to='promociones/', blank=True, null=True, help_text="Imagen para banner promocional")
    mostrar_en_banner = models.BooleanField(default=False, help_text="Mostrar en banners de la página principal")
    orden_banner = models.IntegerField(default=0, help_text="Orden de aparición en banners (menor número = primero)")

    # Metadatos
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='promociones_creadas')

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Promoción"
        verbose_name_plural = "Promociones"

    def __str__(self):
        return f"{self.nombre} - {self.get_status_display()}"

    def save(self, *args, **kwargs):
        """Actualizar estado automáticamente según las fechas"""
        now = timezone.now()

        # Si está inactiva manualmente, no cambiar el estado
        if self.status == 'inactiva':
            super().save(*args, **kwargs)
            return

        # Actualizar estado según fechas
        if self.fecha_fin and now > self.fecha_fin:
            self.status = 'expirada'
        elif self.fecha_inicio and now < self.fecha_inicio:
            self.status = 'programada'
        elif (not self.fecha_inicio or now >= self.fecha_inicio) and (not self.fecha_fin or now <= self.fecha_fin):
            if self.status != 'inactiva':
                self.status = 'activa'

        super().save(*args, **kwargs)

    def is_active(self):
        """Verifica si la promoción está activa en este momento"""
        if self.status == 'inactiva':
            return False

        now = timezone.now()

        # Verificar fecha de inicio
        if self.fecha_inicio and now < self.fecha_inicio:
            return False

        # Verificar fecha de fin
        if self.fecha_fin and now > self.fecha_fin:
            return False

        return self.status == 'activa'

    def aplica_a_servicio(self, servicio):
        """Verifica si esta promoción aplica a un servicio específico"""
        if not self.is_active():
            return False

        if self.aplicacion == 'todos':
            return True
        elif self.aplicacion == 'especificos':
            return self.servicios.filter(id=servicio.id).exists()
        elif self.aplicacion == 'excepto':
            return not self.servicios.filter(id=servicio.id).exists()

        return False

    def calcular_precio_con_descuento(self, precio_original, cantidad=1):
        """
        Calcula el precio final con descuento aplicado

        Args:
            precio_original: Precio base del servicio (por unidad/mes)
            cantidad: Cantidad de unidades (meses, servicios, perfiles según tipo_nxm)

        Returns:
            Precio final con descuento aplicado
        """
        if not self.is_active():
            return precio_original

        if self.tipo_descuento == 'porcentaje' and self.porcentaje_descuento:
            descuento = precio_original * (self.porcentaje_descuento / 100)
            return int(precio_original - descuento)

        elif self.tipo_descuento == 'monto_fijo' and self.monto_descuento:
            precio_con_descuento = precio_original - self.monto_descuento
            return max(0, precio_con_descuento)

        elif self.tipo_descuento == 'nxm' and self.cantidad_pagar and self.cantidad_llevar:
            # Verificar que la cantidad sea suficiente para aplicar la promoción
            if cantidad >= self.cantidad_llevar:
                # Cuántos sets completos aplican a la promoción
                sets_completos = cantidad // self.cantidad_llevar
                items_restantes = cantidad % self.cantidad_llevar

                # LÓGICA CORREGIDA:
                # Ejemplo 3x2: llevas 3, pagas 2
                # - sets_completos = cuántas veces se completa el set de "llevar"
                # - precio_por_set = precio_original * cantidad_pagar (lo que pagas por cada set)
                # - items_restantes = los que no completan un set (se cobran precio normal)

                precio_por_set = precio_original * self.cantidad_pagar
                precio_total = (sets_completos * precio_por_set) + (items_restantes * precio_original)
                return int(precio_total)
            else:
                # Si no alcanza la cantidad mínima, no aplica descuento
                return precio_original * cantidad

        return precio_original

    @classmethod
    def verificar_solapamiento(cls, fecha_inicio, fecha_fin, excluir_id=None):
        """
        Verifica si hay solapamiento con otras promociones activas

        Args:
            fecha_inicio: Fecha de inicio de la nueva promoción
            fecha_fin: Fecha de fin de la nueva promoción
            excluir_id: ID de promoción a excluir (para edición)

        Returns:
            tuple: (tiene_solapamiento, promocion_conflictiva)
        """
        # Buscar promociones que no estén inactivas
        promociones_query = cls.objects.exclude(status='inactiva')

        if excluir_id:
            promociones_query = promociones_query.exclude(id=excluir_id)

        # Si no hay fechas, significa que es permanente, siempre hay conflicto
        if not fecha_inicio and not fecha_fin:
            # Buscar si hay alguna promoción activa o programada
            promocion_conflictiva = promociones_query.filter(
                Q(status='activa') | Q(status='programada')
            ).first()

            if promocion_conflictiva:
                return True, promocion_conflictiva
            return False, None

        # Si solo hay fecha_inicio (sin fin)
        if fecha_inicio and not fecha_fin:
            # Verificar si alguna promoción activa termina después de nuestra fecha_inicio
            # o si alguna no tiene fecha_fin
            promociones_conflictivas = promociones_query.filter(
                Q(status='activa') | Q(status='programada')
            ).filter(
                Q(fecha_fin__gte=fecha_inicio) | Q(fecha_fin__isnull=True)
            )

            promocion_conflictiva = promociones_conflictivas.first()
            if promocion_conflictiva:
                return True, promocion_conflictiva
            return False, None

        # Si solo hay fecha_fin (sin inicio) - comienza ahora
        if not fecha_inicio and fecha_fin:
            now = timezone.now()
            fecha_inicio = now

        # Si hay ambas fechas, verificar solapamiento de rangos
        promociones_conflictivas = promociones_query.filter(
            Q(status='activa') | Q(status='programada')
        )

        for promo in promociones_conflictivas:
            # Caso 1: La promoción existente no tiene fechas (es permanente)
            if not promo.fecha_inicio and not promo.fecha_fin:
                return True, promo

            # Caso 2: La promoción existente no tiene fecha de fin
            if not promo.fecha_fin:
                inicio_promo = promo.fecha_inicio or timezone.now()
                if fecha_fin >= inicio_promo:
                    return True, promo

            # Caso 3: La promoción existente no tiene fecha de inicio (comienza ahora)
            if not promo.fecha_inicio:
                if fecha_inicio <= promo.fecha_fin:
                    return True, promo

            # Caso 4: Ambas tienen fechas completas - verificar solapamiento
            if promo.fecha_inicio and promo.fecha_fin:
                # Hay solapamiento si:
                # - Nueva empieza antes que termine la existente Y
                # - Nueva termina después que empiece la existente
                if fecha_inicio <= promo.fecha_fin and fecha_fin >= promo.fecha_inicio:
                    return True, promo

        return False, None

    @classmethod
    def recomendar_proxima_fecha(cls, duracion_dias=None, excluir_id=None):
        """
        Recomienda la próxima fecha disponible para una promoción

        Args:
            duracion_dias: Duración en días de la promoción
            excluir_id: ID de promoción a excluir (para edición)

        Returns:
            dict con fecha_inicio y fecha_fin recomendadas
        """
        now = timezone.now()

        # Buscar todas las promociones activas o programadas
        promociones = cls.objects.filter(
            Q(status='activa') | Q(status='programada')
        ).exclude(status='inactiva')

        if excluir_id:
            promociones = promociones.exclude(id=excluir_id)

        # Ordenar por fecha de fin
        promociones = promociones.order_by('fecha_fin')

        # Si no hay promociones, puede empezar ahora
        if not promociones.exists():
            fecha_inicio_rec = now
            if duracion_dias:
                fecha_fin_rec = now + timedelta(days=duracion_dias)
            else:
                fecha_fin_rec = None

            return {
                'fecha_inicio': fecha_inicio_rec,
                'fecha_fin': fecha_fin_rec,
                'puede_empezar_ahora': True
            }

        # Buscar la última fecha de finalización
        ultima_fecha_fin = None
        for promo in promociones:
            if promo.fecha_fin:
                if not ultima_fecha_fin or promo.fecha_fin > ultima_fecha_fin:
                    ultima_fecha_fin = promo.fecha_fin

        # Si alguna promoción no tiene fecha de fin, no podemos recomendar
        if not ultima_fecha_fin:
            # Hay una promoción permanente, recomendar que la desactiven
            return {
                'fecha_inicio': None,
                'fecha_fin': None,
                'puede_empezar_ahora': False,
                'mensaje': 'Existe una promoción sin fecha de finalización. Debes finalizarla o establecer una fecha de fin antes de crear una nueva.'
            }

        # Recomendar empezar 1 minuto después de la última finalización
        fecha_inicio_rec = ultima_fecha_fin + timedelta(minutes=1)

        if duracion_dias:
            fecha_fin_rec = fecha_inicio_rec + timedelta(days=duracion_dias)
        else:
            fecha_fin_rec = None

        return {
            'fecha_inicio': fecha_inicio_rec,
            'fecha_fin': fecha_fin_rec,
            'puede_empezar_ahora': False,
            'ultima_promocion_termina': ultima_fecha_fin
        }


# ============================================
# SISTEMA DE AFILIADOS
# ============================================

class AffiliateSettings(models.Model):
    """Configuración global del sistema de afiliados - Singleton"""
    comision_monto = models.DecimalField(
        max_digits=10, decimal_places=2, default=50.00,
        help_text="Monto fijo de comisión por venta (MXN)"
    )
    porcentaje_descuento_default = models.DecimalField(
        max_digits=5, decimal_places=2, default=5.00,
        help_text="Porcentaje de descuento por defecto para nuevos afiliados"
    )
    minimo_retiro = models.DecimalField(
        max_digits=10, decimal_places=2, default=500.00,
        help_text="Monto mínimo para retiro en efectivo (MXN)"
    )
    email_soporte = models.EmailField(
        default='soporte@cuentasmexico.com',
        help_text="Email para afiliados con ventas < umbral"
    )
    whatsapp_soporte = models.CharField(
        max_length=20, default='+521 833 535 5863',
        help_text="WhatsApp para afiliados con ventas > umbral"
    )
    umbral_soporte_premium = models.DecimalField(
        max_digits=10, decimal_places=2, default=5000.00,
        help_text="Umbral de ventas mensuales para soporte WhatsApp"
    )
    porcentaje_comision_referido = models.DecimalField(
        max_digits=5, decimal_places=2, default=10.00,
        help_text="Porcentaje de comisión de ventas de referido (primer mes)"
    )
    banner_activo = models.BooleanField(default=True)
    texto_banner = models.CharField(
        max_length=255,
        default="¡Gana dinero recomendándonos! Únete al programa de afiliados"
    )
    url_terminos = models.URLField(
        blank=True, null=True,
        help_text="URL a los términos y condiciones del programa de afiliados"
    )

    class Meta:
        verbose_name = "Configuración de Afiliados"
        verbose_name_plural = "Configuración de Afiliados"

    def save(self, *args, **kwargs):
        # Singleton pattern - solo una configuración
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass  # No permitir eliminar

    @classmethod
    def get_settings(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return "Configuración del Sistema de Afiliados"


class Affiliate(models.Model):
    """Perfil de afiliado vinculado a un usuario existente"""
    METODO_RETIRO_CHOICES = [
        ('transferencia', 'Transferencia Bancaria'),
        ('paypal', 'PayPal'),
        ('credito', 'Crédito en Tienda'),
    ]

    STATUS_CHOICES = [
        ('activo', 'Activo'),
        ('inactivo', 'Inactivo'),
        ('suspendido', 'Suspendido'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='affiliate')
    codigo_afiliado = models.CharField(max_length=20, unique=True, db_index=True)
    codigo_descuento = models.CharField(max_length=30, unique=True, db_index=True)
    porcentaje_descuento = models.DecimalField(
        max_digits=5, decimal_places=2, default=5.00,
        help_text="Descuento que ofrece el código del afiliado a clientes"
    )
    metodo_retiro = models.CharField(
        max_length=20, choices=METODO_RETIRO_CHOICES, default='credito'
    )
    comision_automatica = models.BooleanField(
        default=False,
        help_text="Si está activo, las comisiones se aprueban automáticamente"
    )
    # Datos bancarios (opcional)
    banco_nombre = models.CharField(max_length=100, blank=True, null=True)
    banco_titular = models.CharField(max_length=100, blank=True, null=True)
    banco_cuenta = models.CharField(max_length=20, blank=True, null=True)
    banco_clabe = models.CharField(max_length=18, blank=True, null=True)
    # Datos PayPal (opcional)
    paypal_email = models.EmailField(blank=True, null=True)
    # Afiliado que lo refirió (un solo nivel)
    referido_por = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='referidos'
    )
    fecha_referido = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='activo')
    fecha_registro = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Afiliado"
        verbose_name_plural = "Afiliados"
        ordering = ['-fecha_registro']

    def __str__(self):
        return f"{self.user.username} - {self.codigo_afiliado}"

    def save(self, *args, **kwargs):
        if not self.codigo_afiliado:
            self.codigo_afiliado = self._generate_unique_code('AF')
        if not self.codigo_descuento:
            self.codigo_descuento = self._generate_unique_code('CM')
        if not self.porcentaje_descuento:
            settings = AffiliateSettings.get_settings()
            self.porcentaje_descuento = settings.porcentaje_descuento_default
        super().save(*args, **kwargs)

    def _generate_unique_code(self, prefix):
        import random
        import string
        while True:
            code = f"{prefix}{''.join(random.choices(string.ascii_uppercase + string.digits, k=6))}"
            if prefix == 'AF':
                if not Affiliate.objects.filter(codigo_afiliado=code).exists():
                    return code
            else:
                if not Affiliate.objects.filter(codigo_descuento=code).exists():
                    return code

    @property
    def balance_disponible(self):
        """Calcula el balance disponible para retiro"""
        from django.db.models import Sum
        comisiones = self.comisiones.filter(
            status='aprobada'
        ).aggregate(total=Sum('monto'))['total'] or 0
        retiros = self.retiros.filter(
            status__in=['aprobado', 'procesando']
        ).aggregate(total=Sum('monto'))['total'] or 0
        return comisiones - retiros

    @property
    def balance_pendiente(self):
        """Calcula el balance pendiente de aprobación"""
        from django.db.models import Sum
        return self.comisiones.filter(
            status='pendiente'
        ).aggregate(total=Sum('monto'))['total'] or 0

    @property
    def ventas_mes_actual(self):
        """Total de ventas del mes actual"""
        from django.db.models import Sum
        from calendar import monthrange
        now = timezone.now()
        start = timezone.make_aware(
            timezone.datetime(now.year, now.month, 1, 0, 0, 0),
            timezone.get_current_timezone()
        ) if timezone.is_naive(timezone.datetime(now.year, now.month, 1, 0, 0, 0)) else timezone.datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=timezone.get_current_timezone())
        last_day = monthrange(now.year, now.month)[1]
        end = timezone.make_aware(
            timezone.datetime(now.year, now.month, last_day, 23, 59, 59),
            timezone.get_current_timezone()
        ) if timezone.is_naive(timezone.datetime(now.year, now.month, last_day, 23, 59, 59)) else timezone.datetime(now.year, now.month, last_day, 23, 59, 59, tzinfo=timezone.get_current_timezone())

        return self.ventas.filter(
            created_at__range=(start, end)
        ).aggregate(total=Sum('sale__payment_amount'))['total'] or 0

    @property
    def total_ventas(self):
        """Total de ventas generadas"""
        return self.ventas.count()

    @property
    def total_clics(self):
        """Total de clics en links de afiliado"""
        return self.clicks.count()

    @property
    def tasa_conversion(self):
        """Tasa de conversión (ventas / clics)"""
        clics = self.total_clics
        if clics == 0:
            return 0
        return round((self.total_ventas / clics) * 100, 2)

    def get_tipo_soporte(self):
        """Determina el tipo de soporte según ventas mensuales"""
        settings = AffiliateSettings.get_settings()
        if self.ventas_mes_actual >= settings.umbral_soporte_premium:
            return 'whatsapp', settings.whatsapp_soporte
        return 'email', settings.email_soporte


class AffiliateSale(models.Model):
    """Registro de ventas generadas por afiliados"""
    affiliate = models.ForeignKey(Affiliate, on_delete=models.CASCADE, related_name='ventas')
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='affiliate_sale')
    codigo_usado = models.CharField(max_length=30)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Venta de Afiliado"
        verbose_name_plural = "Ventas de Afiliados"
        unique_together = ['affiliate', 'sale']
        ordering = ['-created_at']

    def __str__(self):
        return f"Venta {self.sale.id} por {self.affiliate.codigo_afiliado}"


class AffiliateCommission(models.Model):
    """Comisiones generadas por ventas"""
    STATUS_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('aprobada', 'Aprobada'),
        ('rechazada', 'Rechazada'),
    ]

    TIPO_CHOICES = [
        ('venta_directa', 'Venta Directa'),
        ('referido', 'Comisión de Referido'),
    ]

    affiliate = models.ForeignKey(Affiliate, on_delete=models.CASCADE, related_name='comisiones')
    affiliate_sale = models.ForeignKey(
        AffiliateSale, on_delete=models.CASCADE, related_name='comisiones',
        null=True, blank=True
    )
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='venta_directa')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pendiente')
    descripcion = models.TextField(blank=True, null=True)
    aprobado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='comisiones_aprobadas'
    )
    fecha_aprobacion = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Comisión"
        verbose_name_plural = "Comisiones"
        ordering = ['-created_at']

    def __str__(self):
        return f"${self.monto} - {self.affiliate.codigo_afiliado} - {self.get_status_display()}"

    def aprobar(self, usuario=None):
        """Aprueba la comisión"""
        self.status = 'aprobada'
        self.aprobado_por = usuario
        self.fecha_aprobacion = timezone.now()
        self.save()

    def rechazar(self, usuario=None, motivo=None):
        """Rechaza la comisión"""
        self.status = 'rechazada'
        self.aprobado_por = usuario
        self.fecha_aprobacion = timezone.now()
        if motivo:
            self.descripcion = f"{self.descripcion or ''}\nRechazada: {motivo}"
        self.save()


class AffiliateWithdrawal(models.Model):
    """Solicitudes de retiro de afiliados"""
    STATUS_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('procesando', 'Procesando'),
        ('aprobado', 'Aprobado'),
        ('rechazado', 'Rechazado'),
    ]

    METODO_CHOICES = [
        ('transferencia', 'Transferencia Bancaria'),
        ('paypal', 'PayPal'),
        ('credito', 'Crédito en Tienda'),
    ]

    affiliate = models.ForeignKey(Affiliate, on_delete=models.CASCADE, related_name='retiros')
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    metodo = models.CharField(max_length=20, choices=METODO_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pendiente')
    # Datos de pago al momento del retiro (snapshot)
    datos_pago = models.JSONField(blank=True, null=True)
    notas = models.TextField(blank=True, null=True)
    procesado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='retiros_procesados'
    )
    fecha_procesado = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Solicitud de Retiro"
        verbose_name_plural = "Solicitudes de Retiro"
        ordering = ['-created_at']

    def __str__(self):
        return f"${self.monto} - {self.affiliate.codigo_afiliado} - {self.get_status_display()}"

    def aprobar(self, usuario=None):
        """Aprueba el retiro"""
        self.status = 'aprobado'
        self.procesado_por = usuario
        self.fecha_procesado = timezone.now()
        self.save()

        # Si es crédito en tienda, crear el crédito automáticamente
        if self.metodo == 'credito':
            Credits.objects.create(
                customer=self.affiliate.user,
                credits=int(self.monto),
                detail=f'Retiro de comisiones de afiliado #{self.id}'
            )

    def rechazar(self, usuario=None, motivo=None):
        """Rechaza el retiro"""
        self.status = 'rechazado'
        self.procesado_por = usuario
        self.fecha_procesado = timezone.now()
        if motivo:
            self.notas = f"{self.notas or ''}\nRechazado: {motivo}"
        self.save()


class AffiliateClick(models.Model):
    """Tracking de clics en links de afiliados"""
    affiliate = models.ForeignKey(Affiliate, on_delete=models.CASCADE, related_name='clicks')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)
    referrer = models.CharField(max_length=500, blank=True, null=True)
    session_key = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    converted = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Clic de Afiliado"
        verbose_name_plural = "Clics de Afiliados"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['affiliate', 'created_at']),
            models.Index(fields=['session_key']),
        ]

    def __str__(self):
        return f"Clic {self.affiliate.codigo_afiliado} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"


class AffiliateNotification(models.Model):
    """Notificaciones internas para afiliados (campanita)"""
    TIPO_CHOICES = [
        ('venta', 'Nueva Venta'),
        ('comision', 'Comisión Aprobada'),
        ('comision_rechazada', 'Comisión Rechazada'),
        ('retiro', 'Retiro Procesado'),
        ('retiro_rechazado', 'Retiro Rechazado'),
        ('referido', 'Nuevo Referido'),
        ('sistema', 'Notificación del Sistema'),
    ]

    affiliate = models.ForeignKey(Affiliate, on_delete=models.CASCADE, related_name='notificaciones')
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    titulo = models.CharField(max_length=100)
    mensaje = models.TextField()
    leida = models.BooleanField(default=False)
    url = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Notificación de Afiliado"
        verbose_name_plural = "Notificaciones de Afiliados"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.titulo} - {self.affiliate.codigo_afiliado}"

    def marcar_leida(self):
        self.leida = True
        self.save()
