#Django
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from cupon.models import Cupon
from django.core.validators import RegexValidator

#Local
from adm.functions.country import Country

class RegisterUserForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class':'form-control p-3','placeholder':'E-mail'})
    )

    country = forms.ChoiceField(
        required=True,
        choices=[],
        widget=forms.Select(attrs={'class':'form-control p-3', 'id':'id_country'})
    )

    phoneNumberRegex = RegexValidator(regex=r"^\d{8,15}$", message="Número de teléfono debe tener entre 8 y 15 dígitos")
    phone_number = forms.CharField(
        required=True,
        validators=[phoneNumberRegex],
        max_length=15,
        widget=forms.TextInput(attrs={'class':'form-control p-3','placeholder':'Número de WhatsApp', 'id':'id_phone_number'})
    )

    verification_code = forms.CharField(
        required=False,
        max_length=6,
        widget=forms.TextInput(attrs={'class':'form-control p-3 text-center','placeholder':'000000', 'id':'id_verification_code', 'maxlength':'6'})
    )

    class Meta:
        model = User
        fields=['username','email','password1','password2','country','phone_number']
        widgets={
            'username':forms.TextInput(attrs={'class':'form-control p-3','placeholder':'Nombre de Usuario'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({'class':'form-control p-3','placeholder':'Contraseña'})
        self.fields['password2'].widget.attrs.update({'class':'form-control p-3','placeholder':'Repetir Contraseña'})

        # Cargar países con sus ladas
        countries_dict = Country.get_country_lada()
        country_choices = [('', 'Selecciona tu país')]
        country_choices.extend([(country, f"{country} (+{lada})") for country, lada in countries_dict.items()])
        self.fields['country'].choices = country_choices

class RedeemForm(forms.Form):
        name = forms.CharField()

class MpPaymentForm(forms.Form):
    amount = forms.FloatField(label='Cantidad')
    description = forms.CharField(label='Descripción')

class WhatsAppLoginForm(forms.Form):
    """
    Form for WhatsApp login - phone verification
    """
    country = forms.ChoiceField(
        required=True,
        choices=[],
        widget=forms.Select(attrs={'class':'form-control p-3', 'id':'id_login_country'})
    )

    phoneNumberRegex = RegexValidator(regex=r"^\d{8,15}$", message="Número de teléfono debe tener entre 8 y 15 dígitos")
    phone_number = forms.CharField(
        required=True,
        validators=[phoneNumberRegex],
        max_length=15,
        widget=forms.TextInput(attrs={'class':'form-control p-3','placeholder':'Número de WhatsApp', 'id':'id_login_phone_number'})
    )

    verification_code = forms.CharField(
        required=False,
        max_length=6,
        widget=forms.TextInput(attrs={'class':'form-control p-3 text-center','placeholder':'000000', 'id':'id_login_verification_code', 'maxlength':'6'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Cargar países con sus ladas
        countries_dict = Country.get_country_lada()
        country_choices = [('', 'Selecciona tu país')]
        country_choices.extend([(country, f"{country} (+{lada})") for country, lada in countries_dict.items()])
        self.fields['country'].choices = country_choices