from django import forms
from apps.projects.models import DecompteProjet, DecompteAvenant, DecompteLigne
from apps.users.models import User

_I = 'form-input'
_D = {'type': 'date'}
_N = {'step': '0.01', 'min': '0'}


class DecompteProjetForm(forms.ModelForm):
    class Meta:
        model  = DecompteProjet
        fields = [
            'reference', 'client_name', 'nom_projet',
            'commercial', 'chef_de_projet',
            'montant_marche_ht', 'lot', 'adjudication', 'regime',
            'init_attachement', 'init_rg', 'init_rf', 'init_prorata',
            'init_acompte', 'init_reglements', 'init_liv_systeme',
        ]
        widgets = {
            'reference':          forms.TextInput(attrs={'class': _I}),
            'client_name':        forms.TextInput(attrs={'class': _I}),
            'nom_projet':         forms.TextInput(attrs={'class': _I}),
            'commercial':         forms.Select(attrs={'class': _I}),
            'chef_de_projet':     forms.Select(attrs={'class': _I}),
            'montant_marche_ht':  forms.NumberInput(attrs={'class': _I, **_N}),
            'lot':                forms.TextInput(attrs={'class': _I}),
            'adjudication':       forms.CheckboxInput(attrs={'class': 'w-4 h-4 rounded'}),
            'regime':             forms.Select(attrs={'class': _I}),
            'init_attachement':   forms.NumberInput(attrs={'class': _I, **_N}),
            'init_rg':            forms.NumberInput(attrs={'class': _I, **_N}),
            'init_rf':            forms.NumberInput(attrs={'class': _I, **_N}),
            'init_prorata':       forms.NumberInput(attrs={'class': _I, **_N}),
            'init_acompte':       forms.NumberInput(attrs={'class': _I, **_N}),
            'init_reglements':    forms.NumberInput(attrs={'class': _I, **_N}),
            'init_liv_systeme':   forms.NumberInput(attrs={'class': _I, **_N}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        active_users = User.objects.filter(is_active_employee=True).order_by('last_name', 'first_name')
        self.fields['commercial'].queryset     = active_users
        self.fields['chef_de_projet'].queryset = active_users
        for f in ('nom_projet', 'commercial', 'chef_de_projet', 'lot'):
            self.fields[f].required = False


class DecompteAvenantForm(forms.ModelForm):
    class Meta:
        model  = DecompteAvenant
        fields = ['libelle', 'montant_ht', 'date_avenant', 'reference_doc']
        widgets = {
            'libelle':       forms.TextInput(attrs={'class': _I}),
            'montant_ht':    forms.NumberInput(attrs={'class': _I, **_N}),
            'date_avenant':  forms.DateInput(attrs={'class': _I, 'type': 'date'}),
            'reference_doc': forms.TextInput(attrs={'class': _I}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['date_avenant'].required  = False
        self.fields['reference_doc'].required = False


class DecompteLigneForm(forms.ModelForm):
    class Meta:
        model  = DecompteLigne
        fields = [
            'numero_decompte', 'type_operation', 'date_edition_facture', 'ref_piece',
            'attachement', 'prorata', 'rg', 'rf', 'autre',
            'amortissement_acompte', 'acompte', 'ht', 'reglement', 'liv_systeme',
            'semaine', 'annee', 'is_dernier_decompte',
        ]
        widgets = {
            'numero_decompte':       forms.TextInput(attrs={'class': _I}),
            'type_operation':        forms.Select(attrs={'class': _I}),
            'date_edition_facture':  forms.DateInput(attrs={'class': _I, 'type': 'date'}),
            'ref_piece':             forms.TextInput(attrs={'class': _I}),
            'attachement':           forms.NumberInput(attrs={'class': _I, **_N}),
            'prorata':               forms.NumberInput(attrs={'class': _I, **_N}),
            'rg':                    forms.NumberInput(attrs={'class': _I, **_N}),
            'rf':                    forms.NumberInput(attrs={'class': _I, **_N}),
            'autre':                 forms.NumberInput(attrs={'class': _I, **_N}),
            'amortissement_acompte': forms.NumberInput(attrs={'class': _I, **_N}),
            'acompte':               forms.NumberInput(attrs={'class': _I, **_N}),
            'ht':                    forms.NumberInput(attrs={'class': _I, **_N}),
            'reglement':             forms.NumberInput(attrs={'class': _I, **_N}),
            'liv_systeme':           forms.NumberInput(attrs={'class': _I, **_N}),
            'semaine':               forms.NumberInput(attrs={'class': _I, 'min': '1', 'max': '53'}),
            'annee':                 forms.NumberInput(attrs={'class': _I, 'min': '2020', 'max': '2099'}),
            'is_dernier_decompte':   forms.CheckboxInput(attrs={'class': 'w-4 h-4 rounded'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in ('numero_decompte', 'date_edition_facture', 'ref_piece', 'semaine', 'annee'):
            self.fields[f].required = False
