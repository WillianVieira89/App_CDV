from django import forms
from .models import Receptor, Transmissor


class ReceptorForm(forms.ModelForm):
    hora_coleta = forms.TimeField(
        required=False,
        widget=forms.TimeInput(attrs={"type": "time"})
    )

    class Meta:
        model = Receptor
        fields = [
            # ... seus outros campos ...
            "hora_coleta",
        ]


class TransmissorForm(forms.ModelForm):
    hora_coleta = forms.TimeField(
        required=False,
        widget=forms.TimeInput(attrs={"type": "time"})
    )

    class Meta:
        model = Transmissor
        fields = [
            # ... seus outros campos ...
            "hora_coleta",
        ]
