from django import forms
from django.utils import timezone

from adm.models import MarketingCampaign


class MarketingCampaignForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].required = False

    def clean_name(self):
        name = (self.cleaned_data.get("name") or "").strip()
        if name:
            return name
        channel = (self.cleaned_data.get("channel") or "whatsapp").strip().lower()
        channel_label = "WhatsApp" if channel == "whatsapp" else "SMS"
        stamp = timezone.localtime().strftime("%Y-%m-%d %H:%M")
        return f"Campaña IA {channel_label} {stamp}"

    class Meta:
        model = MarketingCampaign
        fields = [
            "name",
            "channel",
            "objective",
            "idea_input",
        ]
        labels = {
            "name": "Nombre de la campaña",
            "channel": "Canal",
            "objective": "Objetivo",
            "idea_input": "Idea base de promoción",
        }
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Ej. Reactivación Marzo MX"}
            ),
            "channel": forms.Select(attrs={"class": "form-select"}),
            "objective": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Ej. Reactivar clientes inactivos de México"}
            ),
            "idea_input": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Escribe una idea inicial y la IA la completará/mejorará.",
                }
            ),
        }
