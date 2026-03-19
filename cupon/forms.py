from django import forms

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
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'status': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'one_use_per_phone': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'duration_unit': forms.Select(attrs={'class': 'form-select'}),
            'duration_quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
        }

    def clean_name(self):
        return (self.cleaned_data.get('name') or '').strip().lower()

    def clean_folder(self):
        folder = self.cleaned_data.get('folder')
        return 0 if folder is None else folder

    def clean_max_uses(self):
        max_uses = self.cleaned_data.get('max_uses')
        return 0 if max_uses is None else max_uses
