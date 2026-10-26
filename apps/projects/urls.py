from django.urls import path
from . import views
from . import decompte_views

app_name = 'projects'

urlpatterns = [
    # API — Chef de projet
    path('api/projets/<int:pk>/chef/', views.DesignChefView.as_view(), name='api_desig_chef'),
    path('api/projets/<int:pk>/chef/valider/', views.ValidateChefView.as_view(), name='api_validate_chef'),
    # API — Étapes projet
    path('api/projets/<int:pk>/etapes/', views.ProjectStepListView.as_view(), name='api_step_list'),
    path('api/etapes/<int:pk>/terminer/', views.ProjectStepCompleteView.as_view(), name='api_step_complete'),
    path('api/etapes/<int:pk>/commentaires/', views.StepCommentListCreateView.as_view(), name='api_step_comments'),
    # API — Commentaires projet
    path('api/projets/<int:pk>/commentaires/', views.ProjectCommentListCreateView.as_view(), name='api_project_comments'),

    path('', views.DashboardView.as_view(), name='dashboard'),
    path('projets/', views.ProjectListView.as_view(), name='list'),
    path('projets/nouveau/', views.ProjectCreateView.as_view(), name='create'),
    path('projets/<int:pk>/', views.ProjectDetailView.as_view(), name='detail'),
    # Phase actions
    path('phases/<int:pk>/activer/', views.PhaseActivateView.as_view(), name='phase_activate'),
    path('phases/<int:pk>/terminer/', views.PhaseCompleteView.as_view(), name='phase_complete'),
    path('phases/<int:pk>/commentaire/', views.PhaseCommentCreateView.as_view(), name='phase_comment'),
    # Task detail + comments
    path('taches/<int:pk>/', views.TaskDetailView.as_view(), name='task_detail'),
    path('taches/<int:pk>/commentaire/', views.TaskCommentCreateView.as_view(), name='task_comment'),
    # Task actions
    path('taches/<int:pk>/avancement/', views.TaskProgressView.as_view(), name='task_progress'),
    path('taches/<int:pk>/affecter/', views.TaskAssignView.as_view(), name='task_assign'),
    # Gabarits
    path('gabarits/', views.TemplateListView.as_view(), name='template_list'),
    path('gabarits/nouveau/', views.TemplateSaveView.as_view(), name='template_create'),
    path('gabarits/<int:pk>/modifier/', views.TemplateSaveView.as_view(), name='template_edit'),
    path('gabarits/<int:pk>/supprimer/', views.TemplateDeleteView.as_view(), name='template_delete'),
    # Planning / Gantt
    path('projets/<int:pk>/planning/', views.ProjectGanttView.as_view(), name='gantt'),
    path('projets/<int:pk>/planning/<int:phase_pk>/update/', views.GanttPhaseUpdateView.as_view(), name='gantt_phase_update'),
    # Chat projet
    path('projets/<int:pk>/chat/', views.ProjectMessageListView.as_view(), name='project_chat'),
    path('projets/<int:pk>/chat/nouveau/', views.ProjectMessageCreateView.as_view(), name='project_message_create'),
    # Chef de projet (formulaires HTML)
    path('projets/<int:pk>/chef/designer/', views.ChefDesignFormView.as_view(), name='chef_design'),
    path('projets/<int:pk>/chef/valider/', views.ChefValidateFormView.as_view(), name='chef_validate'),
    # Étapes projet (formulaires HTML)
    path('etapes/<int:pk>/commentaire/', views.ProjectStepCommentFormView.as_view(), name='step_comment'),
    path('etapes/<int:pk>/terminer/', views.ProjectStepCompleteFormView.as_view(), name='step_complete'),
    # Pose
    path('pose/', views.PoseDashboardView.as_view(), name='pose_dashboard'),
    path('pose/projets/<int:pk>/', views.PoseProjectView.as_view(), name='pose_project'),
    path('pose/projets/<int:pk>/plan/', views.InstallationPlanUpdateView.as_view(), name='pose_plan_update'),
    path('pose/projets/<int:pk>/rapport/', views.InstallationReportCreateView.as_view(), name='pose_report_create'),

    # Gestion de la pose — extension (CDC) — préfixe distinct pour éviter toute collision
    # avec les routes 'pose/' ci-dessus (module planning existant, non modifié).
    path('pose-gestion/creer/', views.PoseGestionCreateProjetView.as_view(), name='pose_gestion_create'),
    path('pose-gestion/poseurs/', views.PoseGestionPoseursListView.as_view(), name='pose_gestion_poseurs_list'),
    path('pose-gestion/poseurs/nouveau/', views.PoseGestionPoseurCreateView.as_view(), name='pose_gestion_poseur_create'),
    path('pose-gestion/poseurs/<int:poseur_pk>/scan-cin/', views.PoseGestionPoseurScanCinUploadView.as_view(), name='pose_gestion_poseur_scan_cin_upload'),
    path('pose-gestion/projets/<int:pk>/', views.PoseGestionProjetTableauView.as_view(), name='pose_gestion_projet'),
    path('pose-gestion/projets/<int:pk>/modifier/', views.PoseGestionProjetUpdateView.as_view(), name='pose_gestion_projet_update'),
    path('pose-gestion/projets/<int:pk>/supprimer/', views.PoseGestionProjetDeleteView.as_view(), name='pose_gestion_projet_delete'),
    path('pose-gestion/projets/<int:pk>/articles/<int:article_pk>/', views.PoseGestionArticleUpdateView.as_view(), name='pose_gestion_article_update'),
    path('pose-gestion/projets/<int:pk>/articles/enregistrer-tout/', views.PoseGestionArticlesBulkUpdateView.as_view(), name='pose_gestion_articles_bulk_update'),
    path('pose-gestion/projets/<int:pk>/articles/export.xlsx', views.PoseGestionArticlesExportXLSXView.as_view(), name='pose_gestion_articles_export'),
    path('pose-gestion/validation/', views.PoseGestionValidationListView.as_view(), name='pose_gestion_validation'),
    path('pose-gestion/validation/<int:article_pk>/decision/', views.PoseGestionValidationDecisionView.as_view(), name='pose_gestion_validation_decision'),
    path('pose-gestion/validation/valider-masse/', views.PoseGestionValidationValiderMasseView.as_view(), name='pose_gestion_validation_valider_masse'),
    path('pose-gestion/projets/<int:pk>/pointage/', views.PoseGestionPointageView.as_view(), name='pose_gestion_pointage'),
    path('pose-gestion/projets/<int:pk>/pointage/lot/creer/', views.PoseGestionLotCreateView.as_view(), name='pose_gestion_lot_create'),
    path('pose-gestion/projets/<int:pk>/pointage/lot/<int:lot_pk>/pointer/', views.PoseGestionLotPointerView.as_view(), name='pose_gestion_lot_pointer'),
    path('pose-gestion/projets/<int:pk>/reglement/', views.PoseGestionReglementView.as_view(), name='pose_gestion_reglement'),
    path('pose-gestion/projets/<int:pk>/reglement/verser/', views.PoseGestionPaiementCreateView.as_view(), name='pose_gestion_paiement_create'),
    path('pose-gestion/projets/<int:pk>/reglement/solder-poseur/', views.PoseGestionSolderPoseurView.as_view(), name='pose_gestion_solder_poseur'),
    path('pose-gestion/projets/<int:pk>/reglement/solder-projet/', views.PoseGestionSolderProjetView.as_view(), name='pose_gestion_solder_projet'),
    path('pose-gestion/projets/<int:pk>/reglement/export.csv', views.PoseGestionReglementExportCSVView.as_view(), name='pose_gestion_reglement_export'),
    path('pose-gestion/projets/<int:pk>/reglement/bons/approuver/', views.PoseGestionBonApprouverView.as_view(), name='pose_gestion_bon_approuver'),
    path('pose-gestion/projets/<int:pk>/reglement/bons/<int:bon_pk>/', views.PoseGestionBonEditView.as_view(), name='pose_gestion_bon_edit'),
    path('pose-gestion/bons/validation/', views.PoseGestionBonsValidationListView.as_view(), name='pose_gestion_bons_validation'),
    path('pose-gestion/bons/<int:bon_pk>/valider/', views.PoseGestionBonValiderView.as_view(), name='pose_gestion_bon_valider'),
    path('pose-gestion/paiements/', views.PoseGestionPaiementsValidesListView.as_view(), name='pose_gestion_paiements'),
    path('pose-gestion/paiements/<int:paiement_pk>/approuver/', views.PoseGestionPaiementApprouverView.as_view(), name='pose_gestion_paiement_approuver'),
    path('pose-gestion/paiements/<int:paiement_pk>/rejeter/', views.PoseGestionPaiementRejeterView.as_view(), name='pose_gestion_paiement_rejeter'),
    path('pose-gestion/pipeline/', views.PoseGestionPipelineView.as_view(), name='pose_gestion_pipeline'),
    path('pose-gestion/projets/<int:pk>/cumul-attachement/', views.PoseGestionCumulAttachementUpdateView.as_view(), name='pose_gestion_cumul_attachement'),

    # Décomposition d'articles + pointage par composant (workflow BROUILLON/VALIDÉ/PAYÉ)
    path('pose-gestion/projets/<int:pk>/articles/<int:article_pk>/decomposition/', views.PoseGestionDecompositionView.as_view(), name='pose_gestion_decomposition'),
    path('pose-gestion/projets/<int:pk>/articles/<int:article_pk>/decomposition/ajouter/', views.PoseGestionDecompositionCreateView.as_view(), name='pose_gestion_decomposition_create'),
    path('pose-gestion/projets/<int:pk>/decomposition/<int:decomposition_pk>/modifier/', views.PoseGestionDecompositionUpdateView.as_view(), name='pose_gestion_decomposition_update'),
    path('pose-gestion/projets/<int:pk>/decomposition/<int:decomposition_pk>/supprimer/', views.PoseGestionDecompositionDeleteView.as_view(), name='pose_gestion_decomposition_delete'),
    path('pose-gestion/projets/<int:pk>/pointage-composants/', views.PoseGestionPointageComposantView.as_view(), name='pose_gestion_pointage_composant'),
    path('pose-gestion/projets/<int:pk>/pointage-composants/<int:decomposition_pk>/saisir/', views.PoseGestionPointageComposantSaisirView.as_view(), name='pose_gestion_pointage_composant_saisir'),
    path('pose-gestion/projets/<int:pk>/pointage-composants/enregistrer-tout/', views.PoseGestionPointageComposantBulkSaisirView.as_view(), name='pose_gestion_pointage_composant_bulk_saisir'),
    path('pose-gestion/projets/<int:pk>/pointage-composants/historique/export/', views.PoseGestionHistoriquePointageExportView.as_view(), name='pose_gestion_historique_pointage_export'),
    path('pose-gestion/projets/<int:pk>/releve-poseurs/', views.PoseGestionRelevePoseurView.as_view(), name='pose_gestion_releve_poseur'),
    path('pose-gestion/projets/<int:pk>/releve-poseurs/marquer-paye/', views.PoseGestionRelevePoseurMarquerPayeView.as_view(), name='pose_gestion_releve_poseur_marquer_paye'),
    path('pose-gestion/projets/<int:pk>/pieces-comptage/<int:piece_pk>/valider/', views.PoseGestionPieceComptageValiderView.as_view(), name='pose_gestion_piece_comptage_valider'),
    path('pose-gestion/projets/<int:pk>/pieces-comptage/<int:piece_pk>/refuser/', views.PoseGestionPieceComptageRefuserView.as_view(), name='pose_gestion_piece_comptage_refuser'),
    path('pose-gestion/pieces-comptage/', views.PoseGestionPiecesComptageEnAttenteListView.as_view(), name='pose_gestion_pieces_comptage_en_attente'),
    path('pose-gestion/pieces-comptage/valider-masse/', views.PoseGestionPiecesComptageValiderMasseView.as_view(), name='pose_gestion_pieces_comptage_valider_masse'),
    path('pose-gestion/projets/<int:pk>/pointage-composants/fiche/<int:fiche_pk>/demander-modification/', views.PoseGestionDemandeModificationCreateView.as_view(), name='pose_gestion_demande_modification_create'),
    path('pose-gestion/demandes-modification/', views.PoseGestionDemandesModificationListView.as_view(), name='pose_gestion_demandes_modification'),
    path('pose-gestion/demandes-modification/valider-masse/', views.PoseGestionDemandesModificationValiderMasseView.as_view(), name='pose_gestion_demandes_modification_valider_masse'),
    path('pose-gestion/demandes-modification/<int:demande_pk>/approuver/', views.PoseGestionDemandeApprouverView.as_view(), name='pose_gestion_demande_approuver'),
    path('pose-gestion/demandes-modification/<int:demande_pk>/refuser/', views.PoseGestionDemandeRefuserView.as_view(), name='pose_gestion_demande_refuser'),
    path('pose-gestion/poseurs/<int:poseur_pk>/releve/', views.PoseGestionPoseurReleveGlobalView.as_view(), name='pose_gestion_poseur_releve'),
    path('pose-gestion/demandes-paiement/', views.PoseGestionDemandesPaiementListView.as_view(), name='pose_gestion_demandes_paiement'),
    path('pose-gestion/demandes-paiement/valider-masse/', views.PoseGestionDemandesPaiementValiderMasseView.as_view(), name='pose_gestion_demandes_paiement_valider_masse'),
    path('pose-gestion/demandes-paiement/creer/', views.PoseGestionDemandePaiementBrouillonView.as_view(), name='pose_gestion_demande_paiement_brouillon'),
    path('pose-gestion/demandes-paiement/<int:demande_pk>/', views.PoseGestionDemandePaiementDetailView.as_view(), name='pose_gestion_demande_paiement_detail'),
    path('pose-gestion/demandes-paiement/<int:demande_pk>/ajouter-lignes/', views.PoseGestionDemandePaiementAjouterLignesView.as_view(), name='pose_gestion_demande_paiement_ajouter_lignes'),
    path('pose-gestion/demandes-paiement/<int:demande_pk>/lignes/<int:ligne_pk>/supprimer/', views.PoseGestionDemandePaiementLigneSupprimerView.as_view(), name='pose_gestion_demande_paiement_ligne_supprimer'),
    path('pose-gestion/demandes-paiement/<int:demande_pk>/soumettre/', views.PoseGestionDemandePaiementSoumettreView.as_view(), name='pose_gestion_demande_paiement_soumettre'),
    path('pose-gestion/demandes-paiement/<int:demande_pk>/valider/', views.PoseGestionDemandePaiementValiderView.as_view(), name='pose_gestion_demande_paiement_valider'),
    path('pose-gestion/demandes-paiement/<int:demande_pk>/refuser/', views.PoseGestionDemandePaiementRefuserView.as_view(), name='pose_gestion_demande_paiement_refuser'),
    path('pose-gestion/demandes-paiement/<int:demande_pk>/edition/', views.PoseGestionDemandePaiementEditionView.as_view(), name='pose_gestion_demande_paiement_edition'),
    path('pose-gestion/demandes-paiement/<int:demande_pk>/edition/enregistrer-impression/', views.PoseGestionDemandePaiementEnregistrerImpressionView.as_view(), name='pose_gestion_demande_paiement_enregistrer_impression'),
    path('pose-gestion/recus-paiement/', views.PoseGestionRecusPaiementListView.as_view(), name='pose_gestion_recus_paiement'),
    path('pose-gestion/recus-paiement/creer/', views.PoseGestionRecuPaiementCreerView.as_view(), name='pose_gestion_recu_paiement_creer'),
    path('pose-gestion/recus-paiement/<int:recu_pk>/', views.PoseGestionRecuPaiementDetailView.as_view(), name='pose_gestion_recu_paiement_detail'),
    path('pose-gestion/recus-paiement/<int:recu_pk>/edition/', views.PoseGestionRecuPaiementEditionView.as_view(), name='pose_gestion_recu_paiement_edition'),
    path('pose-gestion/recus-paiement/<int:recu_pk>/edition/enregistrer-impression/', views.PoseGestionRecuPaiementEnregistrerImpressionView.as_view(), name='pose_gestion_recu_paiement_enregistrer_impression'),
    path('pose-gestion/projets/<int:pk>/delegations/', views.PoseGestionDelegationView.as_view(), name='pose_gestion_delegations'),
    path('pose-gestion/projets/<int:pk>/delegations/<int:delegation_pk>/revoquer/', views.PoseGestionDelegationRevoquerView.as_view(), name='pose_gestion_delegation_revoquer'),
    path('pose-gestion/mes-projets-pointage/', views.PoseGestionMesProjetsPointageView.as_view(), name='pose_gestion_mes_projets_pointage'),

    # ── Suivi Décomptes — module autonome ──────────────────────────────────────
    path('decomptes/',                                          decompte_views.DecompteDashboardView.as_view(),    name='decompte_dashboard'),
    path('decomptes/nouveau/',                                  decompte_views.DecompteProjetCreateView.as_view(), name='decompte_create'),
    path('decomptes/import-csv/',                               decompte_views.ImportDecompteCSVView.as_view(),    name='decompte_import_csv'),
    path('decomptes/<int:pk>/',                                 decompte_views.DecompteProjetDetailView.as_view(), name='decompte_projet'),
    path('decomptes/<int:pk>/saisie/',                          decompte_views.DecompteSaisieView.as_view(),       name='decompte_saisie'),
    path('decomptes/<int:pk>/ligne/<int:lid>/modifier/',        decompte_views.DecompteSaisieView.as_view(),       name='decompte_ligne_edit'),
    path('decomptes/<int:pk>/avenant/ajouter/',                 decompte_views.AvenantCreateView.as_view(),        name='avenant_create'),
    path('decomptes/<int:pk>/avenant/<int:aid>/supprimer/',     decompte_views.AvenantDeleteView.as_view(),        name='avenant_delete'),
]
