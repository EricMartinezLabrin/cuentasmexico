#Django
from ast import Import
from tkinter import Widget
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, UserChangeForm

#Local
# from .models import 

class RegisterUserForm(UserCreationForm):
    class Meta:
        model = User
        fields=['username','email','password1','password2','is_active']
        widgets={
            'username':forms.TextInput(attrs={'placeholder':'Nombre de Usuario'}),
            'email':forms.TextInput(attrs={'placeholder':'E-mail'}),
            'password1':forms.PasswordInput(attrs={'placeholder':'Contraseña'}),
            'password2':forms.PasswordInput(attrs={'placeholder':'Repetir Contraseña'}),
        }