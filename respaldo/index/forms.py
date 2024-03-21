#Django
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from cupon.models import Cupon

#Local
# from .models import 

class RegisterUserForm(UserCreationForm):
    class Meta:
        model = User
        fields=['username','email','password1','password2','is_active']
        widgets={
            'username':forms.TextInput(attrs={'class':'form-control p-3','placeholder':'Nombre de Usuario'}),
            'email':forms.TextInput(attrs={'class':'form-control p-3','placeholder':'E-mail','required':'True'}),
            'password1':forms.PasswordInput(attrs={'class':'form-control p-3','placeholder':'Contraseña'}),
            'password2':forms.PasswordInput(attrs={'class':'form-control p-3','placeholder':'Repetir Contraseña'}),
        }

class RedeemForm(forms.Form):
        name = forms.CharField()

class MpPaymentForm(forms.Form):
    amount = forms.FloatField(label='Cantidad')
    description = forms.CharField(label='Descripción')