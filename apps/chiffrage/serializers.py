from rest_framework import serializers

from .models import DemandeChiffrage, FichierChiffrage, HistoriqueAction, MessageFil


class UserCompactSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    full_name = serializers.SerializerMethodField()
    role = serializers.CharField()

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username


class FichierChiffrageSerializer(serializers.ModelSerializer):
    uploaded_by = UserCompactSerializer(read_only=True)
    fichier_url = serializers.SerializerMethodField()

    class Meta:
        model = FichierChiffrage
        fields = [
            'id', 'nom', 'fichier_url', 'taille_human', 'is_devis',
            'uploaded_by', 'uploaded_at',
        ]

    def get_fichier_url(self, obj):
        request = self.context.get('request')
        if not obj.fichier:
            return None
        url = obj.fichier.url
        return request.build_absolute_uri(url) if request else url


class MessageFilSerializer(serializers.ModelSerializer):
    auteur = UserCompactSerializer(read_only=True)
    fichier_url = serializers.SerializerMethodField()

    class Meta:
        model = MessageFil
        fields = ['id', 'auteur', 'contenu', 'fichier_url', 'nom_fichier', 'created_at']

    def get_fichier_url(self, obj):
        request = self.context.get('request')
        if not obj.fichier:
            return None
        url = obj.fichier.url
        return request.build_absolute_uri(url) if request else url


class HistoriqueActionSerializer(serializers.ModelSerializer):
    auteur = UserCompactSerializer(read_only=True)

    class Meta:
        model = HistoriqueAction
        fields = ['id', 'action', 'detail', 'auteur', 'created_at']


_POST_DG_STATUTS = {'DEVIS_VALIDE', 'TRANSMIS', 'ACCEPTE', 'REFUSE_CLI', 'ARCHIVE'}


class DemandeChiffrageListSerializer(serializers.ModelSerializer):
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    statut_color = serializers.CharField(source='get_statut_color', read_only=True)
    urgence_display = serializers.CharField(source='get_urgence_display', read_only=True)
    montant_ht = serializers.SerializerMethodField()
    is_retard = serializers.BooleanField(read_only=True)
    can_edit = serializers.BooleanField(source='can_commercial_edit', read_only=True)
    assigned_to = UserCompactSerializer(read_only=True)
    commercial = UserCompactSerializer(read_only=True)
    peut_valider_dc = serializers.SerializerMethodField()
    peut_valider_dg = serializers.SerializerMethodField()
    peut_valider_rm = serializers.SerializerMethodField()
    peut_traiter_methodes = serializers.SerializerMethodField()

    class Meta:
        model = DemandeChiffrage
        fields = [
            'id', 'reference', 'client_nom', 'client_ref_affaire', 'commercial',
            'urgence', 'urgence_display', 'statut', 'statut_display', 'statut_color',
            'delai_souhaite', 'is_retard', 'can_edit', 'montant_ht', 'assigned_to',
            'peut_valider_dc', 'peut_valider_dg', 'peut_valider_rm', 'peut_traiter_methodes',
            'created_at', 'updated_at',
        ]

    def _user(self):
        request = self.context.get('request')
        return getattr(request, 'user', None)

    def get_montant_ht(self, obj):
        user = self._user()
        if not user:
            return None
        if user.is_superuser or user.role in ('DIRECTEUR', 'ESTIMATEUR'):
            return obj.montant_ht
        if user.role == 'MANAGER':
            return obj.montant_ht if obj.statut in _POST_DG_STATUTS else None
        return obj.montant_ht if obj.montant_visible_commercial else None

    def get_peut_valider_dc(self, obj):
        user = self._user()
        if not user or not (user.is_superuser or user.role == 'MANAGER'):
            return False
        return obj.statut == DemandeChiffrage.Statut.EN_ATTENTE

    def get_peut_valider_dg(self, obj):
        user = self._user()
        if not user or not (user.is_superuser or user.role == 'DIRECTEUR'):
            return False
        return obj.statut == DemandeChiffrage.Statut.SOUMIS_DG

    def get_peut_valider_rm(self, obj):
        user = self._user()
        if not user or not (user.is_superuser or user.role == 'RESP_METHODES'):
            return False
        return obj.statut == DemandeChiffrage.Statut.SOUMIS_RM

    def get_peut_traiter_methodes(self, obj):
        user = self._user()
        if not user or not (user.is_superuser or user.role == 'ESTIMATEUR'):
            return False
        if obj.statut != DemandeChiffrage.Statut.EN_CHIFFRAGE:
            return False
        return user.is_superuser or obj.assigned_to_id == user.id


class DemandeChiffrageDetailSerializer(DemandeChiffrageListSerializer):
    jalon_display = serializers.CharField(source='get_jalon_display', read_only=True)
    fichiers = serializers.SerializerMethodField()
    messages = serializers.SerializerMethodField()
    historique = HistoriqueActionSerializer(many=True, read_only=True)

    class Meta(DemandeChiffrageListSerializer.Meta):
        fields = DemandeChiffrageListSerializer.Meta.fields + [
            'description', 'finitions', 'kits_references', 'quantites_estimees',
            'contraintes_techniques', 'commentaires', 'lien_telechargement',
            'jalon', 'jalon_display', 'validated_dc_at', 'validated_dg_at', 'transmis_client_at',
            'revision_motif', 'revision_commentaire_dc', 'rm_rejet_motif',
            'fichiers', 'messages', 'historique',
        ]

    def _is_commercial(self):
        user = self._user()
        return bool(user and user.role == 'COMMERCIAL' and not user.is_superuser)

    def get_fichiers(self, obj):
        qs = obj.fichiers.filter(is_devis=False)
        if self._is_commercial():
            qs = qs.filter(is_internal=False)
        return FichierChiffrageSerializer(qs, many=True, context=self.context).data

    def get_messages(self, obj):
        qs = obj.messages.filter(is_internal=False) if self._is_commercial() else obj.messages.all()
        return MessageFilSerializer(qs, many=True, context=self.context).data


class DemandeChiffrageCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DemandeChiffrage
        fields = [
            'client_nom', 'client_ref_affaire', 'description', 'delai_souhaite',
            'urgence', 'finitions', 'kits_references', 'quantites_estimees',
            'contraintes_techniques', 'commentaires', 'lien_telechargement',
        ]

    def validate_client_nom(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError('Le nom du client est obligatoire.')
        return value

    def validate_description(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError('La description est obligatoire.')
        return value
