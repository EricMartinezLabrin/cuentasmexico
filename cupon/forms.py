from django import forms
from django.core.files.images import get_image_dimensions

from adm.models import Service
from cupon.models import Cupon


class CuponForm(forms.ModelForm):
    folder = forms.IntegerField(required=False, min_value=0, widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0}))
    max_uses = forms.IntegerField(required=False, min_value=0, widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0}))

    class Meta:
        model = Cupon
        fields = [
            'name',
            'status',
            'price',
            'folder',
            'max_uses',
            'one_use_per_phone',
            'duration_unit',
            'duration_quantity',
            'image',
            'excluded_services',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'status': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'one_use_per_phone': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'duration_unit': forms.Select(attrs={'class': 'form-select'}),
            'duration_quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'excluded_services': forms.SelectMultiple(attrs={'class': 'form-select', 'size': 6}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['excluded_services'].queryset = Service.objects.filter(status=True).order_by('description')
        self.fields['excluded_services'].required = False

    def clean_name(self):
        return (self.cleaned_data.get('name') or '').strip().lower()

    def clean_folder(self):
        folder = self.cleaned_data.get('folder')
        return 0 if folder is None else folder

    def clean_max_uses(self):
        max_uses = self.cleaned_data.get('max_uses')
        return 0 if max_uses is None else max_uses

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if not image:
            return image

        # Validamos proporción 1:1 (ancho == alto).
        try:
            width, height = get_image_dimensions(image)
        except Exception:
            raise forms.ValidationError('No se pudo procesar la imagen. Sube un archivo válido.')
        finally:
            if hasattr(image, 'seek'):
                try:
                    image.seek(0)
                except Exception:
                    pass

        if not width or not height:
            raise forms.ValidationError('No se pudo leer el tamaño de la imagen.')
        if width != height:
            raise forms.ValidationError('La imagen debe tener proporción 1:1 (ancho y alto iguales).')
        return image
