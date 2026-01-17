# python

# django
from django.db import models
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
