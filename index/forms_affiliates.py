# django
from django import forms
from django.core.validators import RegexValidator

# models
from adm.models import (
    Affiliate, AffiliateSettings, AffiliateWithdrawal
)


class ActivarAfiliadoForm(forms.Form):
    """Formulario para activar el rol de afiliado en un usuario existente"""
    codigo_referido = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ej: AF123456 (opcional)'
        }),
        help_text='Si alguien te invito, ingresa su codigo de afiliado'
    )
    acepto_terminos = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        label='Acepto los terminos y condiciones del programa de afiliados'
    )

    def clean_codigo_referido(self):
        codigo = self.cleaned_data.get('codigo_referido')
        if codigo:
            codigo = codigo.upper().strip()
            if not Affiliate.objects.filter(codigo_afiliado=codigo, status='activo').exists():
                raise forms.ValidationError('El codigo de afiliado no es valido o esta inactivo')
        return codigo


class PerfilAfiliadoForm(forms.ModelForm):
    """Formulario para editar perfil de afiliado"""
    class Meta:
        model = Affiliate
        fields = ['metodo_retiro', 'banco_nombre', 'banco_titular',
                  'banco_cuenta', 'banco_clabe', 'paypal_email']
        widgets = {
            'metodo_retiro': forms.Select(attrs={'class': 'form-select'}),
            'banco_nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: BBVA, Banorte, Santander'
            }),
            'banco_titular': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre completo del titular'
            }),
            'banco_cuenta': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Numero de cuenta'
            }),
            'banco_clabe': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '18 digitos',
                'maxlength': '18'
            }),
            'paypal_email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'correo@paypal.com'
            }),
        }
        labels = {
            'metodo_retiro': 'Metodo de retiro preferido',
            'banco_nombre': 'Nombre del banco',
            'banco_titular': 'Titular de la cuenta',
            'banco_cuenta': 'Numero de cuenta',
            'banco_clabe': 'CLABE interbancaria',
            'paypal_email': 'Email de PayPal',
        }

    def clean_banco_clabe(self):
        clabe = self.cleaned_data.get('banco_clabe')
        if clabe:
            clabe = clabe.strip()
            if not clabe.isdigit() or len(clabe) != 18:
                raise forms.ValidationError('La CLABE debe tener exactamente 18 digitos')
        return clabe

    def clean(self):
        cleaned_data = super().clean()
        metodo = cleaned_data.get('metodo_retiro')

        if metodo == 'transferencia':
            # Validar que tenga datos bancarios
            if not cleaned_data.get('banco_nombre'):
                self.add_error('banco_nombre', 'Requerido para transferencia bancaria')
            if not cleaned_data.get('banco_titular'):
                self.add_error('banco_titular', 'Requerido para transferencia bancaria')
            if not cleaned_data.get('banco_clabe'):
                self.add_error('banco_clabe', 'Requerido para transferencia bancaria')

        elif metodo == 'paypal':
            if not cleaned_data.get('paypal_email'):
                self.add_error('paypal_email', 'Requerido para retiros por PayPal')

        return cleaned_data


class SolicitarRetiroForm(forms.Form):
    """Formulario para solicitar un retiro de comisiones"""
    monto = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '0.00',
            'step': '0.01',
            'min': '0'
        }),
        label='Monto a retirar (MXN)'
    )

    def __init__(self, affiliate, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.affiliate = affiliate
        self.settings = AffiliateSettings.get_settings()

        # Actualizar placeholder con balance disponible
        self.fields['monto'].widget.attrs['max'] = str(affiliate.balance_disponible)
        self.fields['monto'].help_text = f'Balance disponible: ${affiliate.balance_disponible:.2f} MXN'

    def clean_monto(self):
        monto = self.cleaned_data.get('monto')

        if monto <= 0:
            raise forms.ValidationError('El monto debe ser mayor a 0')

        if monto > self.affiliate.balance_disponible:
            raise forms.ValidationError(
                f'El monto excede tu balance disponible (${self.affiliate.balance_disponible:.2f})'
            )

        # Solo validar minimo si NO es credito en tienda
        if self.affiliate.metodo_retiro != 'credito':
            if monto < self.settings.minimo_retiro:
                raise forms.ValidationError(
                    f'El monto minimo para retiro es ${self.settings.minimo_retiro:.2f} MXN. '
                    f'Puedes usar "Credito en Tienda" sin limite minimo.'
                )

        return monto

    def clean(self):
        cleaned_data = super().clean()
        metodo = self.affiliate.metodo_retiro

        # Validar que tenga datos de pago configurados
        if metodo == 'transferencia':
            if not self.affiliate.banco_clabe:
                raise forms.ValidationError(
                    'Debes configurar tus datos bancarios antes de solicitar un retiro por transferencia.'
                )
        elif metodo == 'paypal':
            if not self.affiliate.paypal_email:
                raise forms.ValidationError(
                    'Debes configurar tu email de PayPal antes de solicitar un retiro.'
                )

        return cleaned_data
