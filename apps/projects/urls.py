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
