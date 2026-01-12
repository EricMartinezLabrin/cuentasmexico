# django
from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from PIL import Image

# local
from ..models import Bank, Business, Service, UserDetail, Account, PaymentMethod, Status, Supplier, IndexCarouselImage, IndexPromoImage
from CuentasMexico import settings


class SettingsForm(forms.ModelForm):
    class Meta:
        model = Business
        fields = '__all__'
        labels = {
            'name': 'Nombre Empresa',
            'email': 'E-Mail de Ventas',
            'url': 'Url Principal',
            'phone_number': ' Teléfono Principal',
            'stripe_customer_key': 'Stripe Publishable Key',
            'stripe_secret_key': 'Stripe Secret Key',
            'stripe_sandbox': 'Stripe Entorno de Pruebas',
            'flow_customer_key': 'Flow Customer Key',
            'flow_secret_key': 'Flow Secret Key',
            'flow_show': 'Mostrar Boton de Flow',
            'logo': 'Logo'
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'url': forms.TextInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'mp_customer_key': forms.TextInput(attrs={'class': 'form-control'}),
            'mp_secret_key': forms.TextInput(attrs={'class': 'form-control'}),
            'logo': forms.FileInput(attrs={'class': 'form-control'}),
            'stripe_customer_key': forms.TextInput(attrs={'class': 'form-control'}),
            'stripe_secret_key': forms.TextInput(attrs={'class': 'form-control'}),
            'stripe_sandbox': forms.CheckboxInput(),
            'flow_customer_key': forms.TextInput(attrs={'class': 'form-control'}),
            'flow_secret_key': forms.TextInput(attrs={'class': 'form-control'}),
            'flow_show': forms.CheckboxInput(),
        }


class UserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        labels = {
            'first_name': 'Nombre:',
            'last_name': 'Apellido:',
            'email': 'E-Mail:'
        }
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }


class UserDetailForm(forms.ModelForm):
    class Meta:
        model = UserDetail
        fields = ['user', 'phone_number', 'lada', 'country', 'picture']
        labels = {
            'phone_number': 'Número de teléfono',
            'lada': 'Lada',
            'country': 'País',
            'picture': 'Foto de Perfil'
        }
        widgets = {
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'lada': forms.TextInput(attrs={'class': 'form-control'}),
            'country': forms.TextInput(attrs={'class': 'form-control'}),
            'picture': forms.FileInput(attrs={'class': 'form-control'}),
            'user': forms.HiddenInput(),
        }


class ServicesForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ['description', 'perfil_quantity', 'logo']
        labels = {
            'description': 'Nombre del Servicio',
            'perfil_quantity': '¿Cuantos Perfiles Tendrá?',
            'logo': 'Logo'
        }
        widgets = {
            'description': forms.TextInput(attrs={'class': 'form-control'}),
            'perfil_quantity': forms.NumberInput(attrs={'class': 'form-control'}),
            'logo': forms.FileInput(attrs={'class': 'form-control'}),
        }


class FilterAccountForm(forms.ModelForm):
    class Meta:
        model = Account

        fields = ['account_name', 'email']
        labels = {
            'account_name': 'Cuenta',
            'email': 'E-Mail',

        }
        widgets = {
            'account_name': forms.Select(attrs={'class': 'form-select', 'id': 'inputGroupSelect01'}),
            'email': forms.TextInput(attrs={'id': 'addon-wrapping'}),
        }


class BankForm(forms.ModelForm):
    class Meta:
        model = Bank
        fields = ['business', 'bank_name', 'headline',
                  'card_number', 'clabe', 'logo']
        labels = {
            'bank_name': 'Nombre del Banco',
            'headline': 'Titular de la cuenta',
            'card_number': 'Número de Tarjeta',
            'clabe': 'Número de Clabe',
            'logo': 'Logo'
        }
        widgets = {
            'bank_name': forms.TextInput(attrs={'class': 'form-control'}),
            'headline': forms.TextInput(attrs={'class': 'form-control'}),
            'card_number': forms.TextInput(attrs={'class': 'form-control'}),
            'clabe': forms.TextInput(attrs={'class': 'form-control'}),
            'logo': forms.FileInput(attrs={'class': 'form-control'}),
            'business': forms.TextInput(attrs={'value': '1', 'type': 'hidden'})
        }


class PaymentMethodForm(forms.ModelForm):

    class Meta:
        model = PaymentMethod
        fields = '__all__'
        labels = {
            'description': 'Metodo de Pago'
        }
        widgets = {
            'description': forms.TextInput(attrs={'class': 'form-control'})
        }


class StatusForm(forms.ModelForm):

    class Meta:
        model = Status
        fields = '__all__'
        labels = {
            'description': 'Metodo de Pago'
        }
        widgets = {
            'description': forms.TextInput(attrs={'class': 'form-control'})
        }


class SupplierForm(forms.ModelForm):

    class Meta:
        model = Supplier
        fields = ['business', 'name', 'phone_number']
        labels = {
            'business': 'Empresa',
            'name': 'Nombre',
            'phone_number': 'Número de Teléfono'
        }
        widgets = {
            'business': forms.TextInput(attrs={'value': '1', 'type': 'hidden'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'})
        }


class AccountsForm(forms.ModelForm):
    class Meta:
        model = Account
        fields = ['business', 'supplier', 'account_name', 'expiration_date',
                  'email', 'password', 'comments', 'renovable', 'created_by', 'modified_by', 'renewal_date']
        labels = {
            'business': 'Empresa',
            'supplier': 'Proveedor',
            'account_name': 'Cuenta',
            'expiration_date': 'Fecha de Vencimiento',
            'email': 'E-Mail',
            'password': 'Contraseña',
            'comments': 'Comentarios',
            'renovable': '¿Es renovable?'

        }
        widgets = {
            'business': forms.TextInput(attrs={'value': 1, 'type': 'hidden'}),
            'supplier': forms.Select(attrs={'class': 'form-control'}),
            'account_name': forms.Select(attrs={'class': 'form-control'}),
            'expiration_date': forms.DateInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'password': forms.TextInput(attrs={'class': 'form-control'}),
            'pin': forms.NumberInput(attrs={'class': 'form-control', 'max': 5}),
            'comments': forms.TextInput(attrs={'class': 'form-control'}),
            'renovable': forms.CheckboxInput()

        }


class CustomerUpdateForm(forms.ModelForm):
    class Meta:
        model = UserDetail
        fields = ['phone_number', 'lada', 'country']
        labels = {
            'phone_number': 'Número de teléfono',
            'lada': 'Lada (Código de país, puedes buscarlo por el nombre del pais.)',
            'country': 'País'
        }
        widgets = {
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'lada': forms.TextInput(attrs={'class': 'form-control'}),
            'country': forms.TextInput(attrs={'class': 'form-control'})
        }


class UserMainForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'is_staff', 'is_active']
        labels = {
            'first_name': 'Nombres',
            'last_name': 'Apellidos',
            'email': 'E-Mail',
            'is_staff': '¿Es Trabajador?',
            'is_active': '¿Está activo?',
            'is_superuser': '¿Es Administrador?'
        }
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }


class IndexCarouselImageForm(forms.ModelForm):
    """Formulario para imágenes del carrusel con validación de dimensiones"""

    class Meta:
        model = IndexCarouselImage
        fields = ['image', 'title', 'order', 'active']
        labels = {
            'image': 'Imagen',
            'title': 'Título (opcional)',
            'order': 'Orden de aparición',
            'active': 'Activa'
        }
        widgets = {
            'image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/jpeg,image/png,image/jpg'
            }),
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Oferta Black Friday'}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        help_texts = {
            'image': 'La imagen debe tener dimensiones de 2000x600 píxeles (o relación 10:3)',
            'order': 'Menor número aparece primero. Puedes usar 0, 1, 2, etc.'
        }

    def clean_image(self):
        image = self.cleaned_data.get('image')

        if image:
            try:
                img = Image.open(image)
                width, height = img.size

                # Dimensiones recomendadas para carrusel (ancho banner)
                RECOMMENDED_WIDTH = 2000
                RECOMMENDED_HEIGHT = 600
                TOLERANCE = 0.1  # 10% de tolerancia

                # Calcular relación de aspecto
                aspect_ratio = width / height
                expected_ratio = RECOMMENDED_WIDTH / RECOMMENDED_HEIGHT

                # Validar que la relación de aspecto sea aproximadamente 10:3
                if abs(aspect_ratio - expected_ratio) > expected_ratio * TOLERANCE:
                    raise ValidationError(
                        f'La imagen debe tener una relación de aspecto de aproximadamente 10:3. '
                        f'Dimensión actual: {width}x{height}px. '
                        f'Dimensión recomendada: {RECOMMENDED_WIDTH}x{RECOMMENDED_HEIGHT}px o similar.'
                    )

                # Validar dimensiones mínimas
                if width < 1200 or height < 360:
                    raise ValidationError(
                        f'La imagen es demasiado pequeña. Dimensión mínima: 1200x360px. '
                        f'Dimensión actual: {width}x{height}px.'
                    )

                # Validar tamaño del archivo (5MB máximo)
                if image.size > 5 * 1024 * 1024:
                    raise ValidationError('El tamaño del archivo no debe exceder 5MB.')

            except ValidationError:
                raise
            except Exception as e:
                raise ValidationError(f'Error al procesar la imagen: {str(e)}')

        return image


class IndexPromoImageForm(forms.ModelForm):
    """Formulario para imágenes de promociones con validación de dimensiones"""

    class Meta:
        model = IndexPromoImage
        fields = ['image', 'title', 'position', 'active']
        labels = {
            'image': 'Imagen',
            'title': 'Título (opcional)',
            'position': 'Posición',
            'active': 'Activa'
        }
        widgets = {
            'image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/jpeg,image/png,image/jpg'
            }),
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Promoción 3x2'}),
            'position': forms.Select(attrs={'class': 'form-select'}),
            'active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        help_texts = {
            'image': 'La imagen debe tener dimensiones de 1000x600 píxeles (o relación 5:3)',
            'position': 'Selecciona si la imagen aparecerá a la izquierda o derecha'
        }

    def clean_image(self):
        image = self.cleaned_data.get('image')

        if image:
            try:
                img = Image.open(image)
                width, height = img.size

                # Dimensiones recomendadas para promociones (cuadradas/rectangulares)
                RECOMMENDED_WIDTH = 1000
                RECOMMENDED_HEIGHT = 600
                TOLERANCE = 0.15  # 15% de tolerancia

                # Calcular relación de aspecto
                aspect_ratio = width / height
                expected_ratio = RECOMMENDED_WIDTH / RECOMMENDED_HEIGHT

                # Validar que la relación de aspecto sea aproximadamente 5:3
                if abs(aspect_ratio - expected_ratio) > expected_ratio * TOLERANCE:
                    raise ValidationError(
                        f'La imagen debe tener una relación de aspecto de aproximadamente 5:3. '
                        f'Dimensión actual: {width}x{height}px. '
                        f'Dimensión recomendada: {RECOMMENDED_WIDTH}x{RECOMMENDED_HEIGHT}px o similar.'
                    )

                # Validar dimensiones mínimas
                if width < 600 or height < 360:
                    raise ValidationError(
                        f'La imagen es demasiado pequeña. Dimensión mínima: 600x360px. '
                        f'Dimensión actual: {width}x{height}px.'
                    )

                # Validar tamaño del archivo (5MB máximo)
                if image.size > 5 * 1024 * 1024:
                    raise ValidationError('El tamaño del archivo no debe exceder 5MB.')

            except ValidationError:
                raise
            except Exception as e:
                raise ValidationError(f'Error al procesar la imagen: {str(e)}')

        return image
