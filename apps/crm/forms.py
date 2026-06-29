from django import forms

from apps.users.models import User
from .models import OpportunitePipeline

_I = 'form-input'


class OpportunitePipelineForm(forms.ModelForm):

    class Meta:
        model  = OpportunitePipeline
        fields = [
            'commercial', 'client', 'projet', 'segment',
            'ville', 'region', 'pays',
            'potentiel_mad', 'probabilite',
            'commentaire_terrain', 'statut',
            'prochaine_action', 'date_action', 'date_closing_est',
            'risque',
        ]
        widgets = {
            'client':              forms.TextInput(attrs={'class': _I}),
            'projet':              forms.TextInput(attrs={'class': _I}),
            'segment':             forms.Select(attrs={'class': _I}),
            'ville':               forms.TextInput(attrs={'class': _I}),
            'region':              forms.TextInput(attrs={'class': _I}),
            'pays':                forms.TextInput(attrs={'class': _I}),
            'potentiel_mad':       forms.NumberInput(attrs={'class': _I, 'step': '0.01', 'min': '0'}),
            'probabilite':         forms.Select(attrs={'class': _I}),
            'commentaire_terrain': forms.Textarea(attrs={'class': _I, 'rows': 3}),
            'statut':              forms.Select(attrs={'class': _I}),
            'prochaine_action':    forms.TextInput(attrs={'class': _I}),
            'date_action':         forms.DateInput(attrs={'class': _I, 'type': 'date'}),
            'date_closing_est':    forms.DateInput(attrs={'class': _I, 'type': 'date'}),
            'risque':              forms.Select(attrs={'class': _I}),
            'commercial':          forms.Select(attrs={'class': _I}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['commercial'].queryset = User.objects.filter(
            role__in=('COMMERCIAL', 'MANAGER'), is_active_employee=True,
        ).order_by('last_name', 'first_name')
        # Champs optionnels
        for f in ('ville', 'region', 'commentaire_terrain', 'prochaine_action',
                  'date_action', 'date_closing_est', 'risque', 'probabilite', 'potentiel_mad'):
            self.fields[f].required = False
        # Commercial en lecture seule pour les commerciaux
        if user and user.role == 'COMMERCIAL' and not user.is_superuser:
            self.fields['commercial'].initial  = user.pk
            self.fields['commercial'].widget   = forms.HiddenInput()
            self.fields['commercial'].required = True
