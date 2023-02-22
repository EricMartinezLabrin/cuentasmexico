#django
from django import forms
from django.contrib.auth.models import User

#local
from ..models import Bank, Business, Service, UserDetail, Account, PaymentMethod, Status, Supplier
from CuentasMexico import settings

class SettingsForm(forms.ModelForm):
    class Meta:
        model= Business
        fields = '__all__'
        labels = {
            'name': 'Nombre Empresa',
            'email': 'E-Mail de Ventas',
            'url': 'Url Principal',
            'phone_number': ' Teléfono Principal',
            'mp_customer_key': 'Customer Key MercadoPago',
            'mp_secret_key':'Secret Key MercadoPago',
            'logo': 'Logo'
        }
        widgets = {
            'name': forms.TextInput(attrs={'class':'form-control'}),
            'email': forms.EmailInput(attrs={'class':'form-control'}),
            'url': forms.TextInput(attrs={'class':'form-control'}),
            'phone_number': forms.TextInput(attrs={'class':'form-control'}),
            'mp_customer_key': forms.TextInput(attrs={'class':'form-control'}),
            'mp_secret_key':forms.TextInput(attrs={'class':'form-control'}),
            'logo': forms.FileInput(attrs={'class':'form-control'})
        }

class UserForm(forms.ModelForm):
    class Meta:
        model= User
        fields = ['first_name','last_name','email']
        labels={
            'first_name':'Nombre:',
            'last_name':'Apellido:',
            'email':'E-Mail:'
        }
        widgets={
            'first_name': forms.TextInput(attrs={'class':'form-control'}),
            'last_name': forms.TextInput(attrs={'class':'form-control'}),
            'email': forms.EmailInput(attrs={'class':'form-control'}),
        }

class UserDetailForm(forms.ModelForm):
    class Meta:
        model=UserDetail
        fields = ['user','phone_number','lada','country','picture']
        labels={
            'phone_number': 'Número de teléfono',
            'lada': 'Lada',
            'country': 'País',
            'picture':'Foto de Perfil'
        }
        widgets={
            'phone_number': forms.TextInput(attrs={'class':'form-control'}),
            'lada': forms.TextInput(attrs={'class':'form-control'}),
            'country': forms.TextInput(attrs={'class':'form-control'}),
            'picture': forms.FileInput(attrs={'class':'form-control'}),
            'user':forms.HiddenInput(),
        }

class ServicesForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ['description','perfil_quantity','logo']
        labels={
            'description': 'Nombre del Servicio',
            'perfil_quantity': '¿Cuantos Perfiles Tendrá?',
            'logo': 'Logo'
        }      
        widgets={
            'description': forms.TextInput(attrs={'class':'form-control'}),
            'perfil_quantity': forms.NumberInput(attrs={'class':'form-control'}),
            'logo': forms.FileInput(attrs={'class':'form-control'}),
        }

class FilterAccountForm(forms.ModelForm):
    class Meta:
        model = Account

        fields = ['account_name','email']
        labels = {
            'account_name': 'Cuenta',
            'email': 'E-Mail',

        }
        widgets = {
            'account_name': forms.Select(attrs={'class':'form-select','id':'inputGroupSelect01'}),
            'email': forms.TextInput(attrs={'id':'addon-wrapping'}),
        }

class BankForm(forms.ModelForm):
    class Meta:
        model=Bank
        fields = ['business','bank_name','headline','card_number','clabe','logo']
        labels = {
            'bank_name': 'Nombre del Banco',
            'headline': 'Titular de la cuenta',
            'card_number': 'Número de Tarjeta',
            'clabe': 'Número de Clabe',
            'logo': 'Logo'
        }
        widgets={
            'bank_name': forms.TextInput(attrs={'class':'form-control'}),
            'headline': forms.TextInput(attrs={'class':'form-control'}),
            'card_number': forms.TextInput(attrs={'class':'form-control'}),
            'clabe': forms.TextInput(attrs={'class':'form-control'}),
            'logo': forms.FileInput(attrs={'class':'form-control'}),
            'business': forms.TextInput(attrs={'value':'1','type':'hidden'})        
        }

class PaymentMethodForm(forms.ModelForm):
    
    class Meta:
        model = PaymentMethod
        fields = '__all__'
        labels={
            'description': 'Metodo de Pago'
        }
        widgets={
            'description': forms.TextInput(attrs={'class':'form-control'})
        }

class StatusForm(forms.ModelForm):
    
    class Meta:
        model = Status
        fields = '__all__'
        labels={
            'description': 'Metodo de Pago'
        }
        widgets={
            'description': forms.TextInput(attrs={'class':'form-control'})
        }

class SupplierForm(forms.ModelForm):
    
    class Meta:
        model = Supplier
        fields = ['business','name','phone_number']
        labels={
            'business': 'Empresa',
            'name': 'Nombre',
            'phone_number': 'Número de Teléfono'
        }
        widgets={
            'business': forms.TextInput(attrs={'value':'1','type':'hidden'}),
            'name': forms.TextInput(attrs={'class':'form-control'}),
            'phone_number': forms.TextInput(attrs={'class':'form-control'})
        }

class AccountsForm(forms.ModelForm):
    class Meta:
        model = Account
        fields = ['business','supplier','account_name','expiration_date','email','password','comments','renovable','created_by','modified_by']
        labels={
            'business': 'Empresa',
            'supplier': 'Proveedor',
            'account_name': 'Cuenta',
            'expiration_date':'Fecha de Vencimiento',
            'email': 'E-Mail',
            'password': 'Contraseña',
            'comments':'Comentarios',
            'renovable': '¿Es renovable?'

        }
        widgets={
            'business': forms.TextInput(attrs={'value':1,'type':'hidden'}),
            'supplier': forms.Select(attrs={'class':'form-control'}),
            'account_name': forms.Select(attrs={'class':'form-control'}),
            'expiration_date': forms.DateInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class':'form-control'}),
            'password': forms.TextInput(attrs={'class':'form-control'}),
            'pin': forms.NumberInput(attrs={'class':'form-control','max':5}),
            'comments': forms.TextInput(attrs={'class':'form-control'}),
            'renovable': forms.CheckboxInput()

        }
        
class CustomerUpdateForm(forms.ModelForm):
    class Meta:
        model=UserDetail
        fields = ['phone_number','lada','country']
        labels={
            'phone_number': 'Número de teléfono',
            'lada': 'Lada (Código de país, puedes buscarlo por el nombre del pais.)',
            'country': 'País'
        }
        widgets={
            'phone_number': forms.TextInput(attrs={'class':'form-control'}),
            'lada': forms.TextInput(attrs={'class':'form-control'}),
            'country': forms.TextInput(attrs={'class':'form-control'})
        }

class UserMainForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name','last_name','email','is_staff','is_active']
        labels={
            'first_name': 'Nombres',
            'last_name': 'Apellidos',
            'email': 'E-Mail',
            'is_staff': '¿Es Trabajador?',
            'is_active': '¿Está activo?',
            'is_superuser': '¿Es Administrador?'
        }
        widgets={
            'first_name': forms.TextInput(attrs={'class':'form-control'}),
            'last_name': forms.TextInput(attrs={'class':'form-control'}),
            'email': forms.EmailInput(attrs={'class':'form-control'}),
        }






