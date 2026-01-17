# django
from django import forms
from django.core.exceptions import ValidationError

# local
from ..models import Promocion


class PromocionForm(forms.ModelForm):
    """Formulario para crear y editar promociones"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Convertir fechas al formato correcto para datetime-local
        if self.instance.pk:
            if self.instance.fecha_inicio:
                # Formato: YYYY-MM-DDTHH:MM
                self.initial['fecha_inicio'] = self.instance.fecha_inicio.strftime('%Y-%m-%dT%H:%M')
            if self.instance.fecha_fin:
                self.initial['fecha_fin'] = self.instance.fecha_fin.strftime('%Y-%m-%dT%H:%M')

    class Meta:
        model = Promocion
        fields = [
            'nombre', 'descripcion', 'tipo_descuento', 'porcentaje_descuento',
            'monto_descuento', 'tipo_nxm', 'cantidad_llevar', 'cantidad_pagar',
            'aplicacion', 'servicios', 'fecha_inicio', 'fecha_fin', 'status',
            'imagen', 'mostrar_en_banner', 'orden_banner'
        ]
        labels = {
            'nombre': 'Nombre de la Promoción',
            'descripcion': 'Descripción',
            'tipo_descuento': 'Tipo de Descuento',
            'porcentaje_descuento': 'Porcentaje (%)',
            'monto_descuento': 'Monto Fijo ($)',
            'tipo_nxm': 'Tipo de Promoción NxM',
            'cantidad_llevar': 'Cantidad que Lleva',
            'cantidad_pagar': 'Cantidad que Paga',
            'aplicacion': 'Aplicar a',
            'servicios': 'Servicios',
            'fecha_inicio': 'Fecha y Hora de Inicio',
            'fecha_fin': 'Fecha y Hora de Fin',
            'status': 'Estado',
            'imagen': 'Imagen para Banner',
            'mostrar_en_banner': 'Mostrar en Banners',
            'orden_banner': 'Orden en Banners'
        }
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 3 meses por el precio de 2'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Descripción detallada de la promoción'}),
            'tipo_descuento': forms.Select(attrs={'class': 'form-control', 'id': 'id_tipo_descuento'}),
            'porcentaje_descuento': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Ej: 50'}),
            'monto_descuento': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 100'}),
            'tipo_nxm': forms.Select(attrs={'class': 'form-control', 'id': 'id_tipo_nxm'}),
            'cantidad_llevar': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 3 en 3x2'}),
            'cantidad_pagar': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 2 en 3x2'}),
            'aplicacion': forms.Select(attrs={'class': 'form-control', 'id': 'id_aplicacion'}),
            'servicios': forms.SelectMultiple(attrs={'class': 'form-control', 'size': 10, 'id': 'id_servicios'}),
            'fecha_inicio': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'fecha_fin': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'imagen': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'mostrar_en_banner': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'orden_banner': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Menor número = primero'})
        }
        help_texts = {
            'porcentaje_descuento': 'Porcentaje de descuento a aplicar (ejemplo: 50 para 50%)',
            'monto_descuento': 'Monto fijo a descontar en pesos',
            'tipo_nxm': 'Selecciona si la promoción aplica a meses, servicios diferentes o perfiles',
            'cantidad_llevar': 'Lo que lleva el cliente (ej. 3 en una promoción 3x2)',
            'cantidad_pagar': 'Lo que paga el cliente (ej. 2 en una promoción 3x2)',
            'servicios': 'Mantén presionado Ctrl (Windows) o Cmd (Mac) para seleccionar múltiples',
            'fecha_inicio': 'Dejar vacío para iniciar inmediatamente',
            'fecha_fin': 'Dejar vacío para promoción sin límite de tiempo',
        }

    def clean(self):
        cleaned_data = super().clean()
        tipo_descuento = cleaned_data.get('tipo_descuento')
        porcentaje_descuento = cleaned_data.get('porcentaje_descuento')
        monto_descuento = cleaned_data.get('monto_descuento')
        cantidad_pagar = cleaned_data.get('cantidad_pagar')
        cantidad_llevar = cleaned_data.get('cantidad_llevar')
        fecha_inicio = cleaned_data.get('fecha_inicio')
        fecha_fin = cleaned_data.get('fecha_fin')
        status = cleaned_data.get('status')

        # Validar que se proporcionen los campos según el tipo de descuento
        if tipo_descuento == 'porcentaje':
            if not porcentaje_descuento:
                raise ValidationError('Debes especificar el porcentaje de descuento')
            if porcentaje_descuento <= 0 or porcentaje_descuento > 100:
                raise ValidationError('El porcentaje debe estar entre 0 y 100')

        elif tipo_descuento == 'monto_fijo':
            if not monto_descuento:
                raise ValidationError('Debes especificar el monto de descuento')
            if monto_descuento <= 0:
                raise ValidationError('El monto de descuento debe ser mayor a 0')

        elif tipo_descuento == 'nxm':
            tipo_nxm = cleaned_data.get('tipo_nxm')

            if not tipo_nxm:
                raise ValidationError('Debes seleccionar el tipo de promoción NxM (meses, servicios o perfiles)')

            if not cantidad_llevar or not cantidad_pagar:
                raise ValidationError('Debes especificar cantidad que lleva y cantidad que paga para promociones NxM')

            if cantidad_llevar <= 0 or cantidad_pagar <= 0:
                raise ValidationError('Las cantidades deben ser mayores a 0')

            if cantidad_pagar >= cantidad_llevar:
                raise ValidationError('La cantidad que lleva debe ser mayor a la cantidad que paga (ej: en 3x2, lleva 3 y paga 2)')

        # Validar fechas
        if fecha_inicio and fecha_fin:
            if fecha_inicio >= fecha_fin:
                raise ValidationError('La fecha de inicio debe ser anterior a la fecha de fin')

        # Validar solapamiento de promociones SOLO si el status no es 'inactiva'
        if status != 'inactiva':
            excluir_id = self.instance.pk if self.instance and self.instance.pk else None

            tiene_solapamiento, promocion_conflictiva = Promocion.verificar_solapamiento(
                fecha_inicio, fecha_fin, excluir_id
            )

            if tiene_solapamiento:
                # Obtener recomendación de fecha
                if fecha_inicio and fecha_fin:
                    from datetime import timedelta
                    duracion = (fecha_fin - fecha_inicio).days
                else:
                    duracion = None

                recomendacion = Promocion.recomendar_proxima_fecha(duracion, excluir_id)

                # Construir mensaje de error con recomendación
                error_msg = f'Ya existe una promoción activa en estas fechas: "{promocion_conflictiva.nombre}".'

                if recomendacion.get('puede_empezar_ahora'):
                    error_msg += ' Sin embargo, no hay conflicto para iniciar ahora.'
                elif recomendacion.get('mensaje'):
                    error_msg += f' {recomendacion["mensaje"]}'
                elif recomendacion.get('fecha_inicio'):
                    fecha_rec = recomendacion['fecha_inicio'].strftime('%d/%m/%Y %H:%M')
                    error_msg += f' La próxima fecha disponible es: {fecha_rec}'
                    if recomendacion.get('ultima_promocion_termina'):
                        fecha_term = recomendacion['ultima_promocion_termina'].strftime('%d/%m/%Y %H:%M')
                        error_msg += f' (después de que termine "{promocion_conflictiva.nombre}" el {fecha_term})'

                raise ValidationError(error_msg)

        return cleaned_data
