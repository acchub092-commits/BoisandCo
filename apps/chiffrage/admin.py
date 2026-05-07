from django.contrib import admin
from .models import DemandeChiffrage, FichierChiffrage, MessageFil, HistoriqueAction, DemandeModification


class FichierInline(admin.TabularInline):
    model = FichierChiffrage
    extra = 0
    readonly_fields = ['taille', 'uploaded_at']


class MessageInline(admin.TabularInline):
    model = MessageFil
    extra = 0
    readonly_fields = ['created_at']


class HistoriqueInline(admin.TabularInline):
    model = HistoriqueAction
    extra = 0
    readonly_fields = ['auteur', 'action', 'detail', 'ancien_statut', 'nouveau_statut', 'created_at']

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DemandeChiffrage)
class DemandeChiffrageAdmin(admin.ModelAdmin):
    list_display = ['reference', 'client_nom', 'statut', 'urgence', 'commercial', 'assigned_to', 'created_at']
    list_filter  = ['statut', 'urgence']
    search_fields = ['reference', 'client_nom', 'client_ref_affaire']
    readonly_fields = ['reference', 'created_at', 'updated_at']
    inlines = [FichierInline, MessageInline, HistoriqueInline]


@admin.register(DemandeModification)
class DemandeModifAdmin(admin.ModelAdmin):
    list_display = ['demande', 'soumis_par', 'statut', 'urgence', 'created_at']
    list_filter  = ['statut', 'urgence']
