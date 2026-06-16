from django.urls import path
from . import views

app_name = 'crm'

urlpatterns = [
    # ── Dashboard CRM enrichi ────────────────────────────────────────────────
    path('tableau-de-bord/',             views.CRMDashboardView.as_view(),           name='crm_dashboard'),

    # ── Pipeline Kanban ──────────────────────────────────────────────────────
    path('',                             views.PipelineView.as_view(),               name='pipeline'),

    # ── Lead CRUD ────────────────────────────────────────────────────────────
    path('nouveau/',                     views.LeadCreateView.as_view(),             name='lead_create'),
    path('<int:pk>/',                    views.LeadDetailView.as_view(),             name='lead_detail'),
    path('<int:pk>/modifier/',           views.LeadCreateView.as_view(),             name='lead_edit'),
    path('<int:pk>/statut/',             views.LeadStatusUpdateView.as_view(),       name='lead_status'),
    path('<int:pk>/supprimer/',          views.LeadDeleteView.as_view(),             name='lead_delete'),
    path('<int:pk>/note/',               views.LeadNoteCreateView.as_view(),         name='lead_note'),
    path('<int:pk>/lier-projet/',        views.LeadLinkProjectView.as_view(),        name='lead_link_project'),

    # ── Workflow validation ──────────────────────────────────────────────────
    path('<int:pk>/soumettre/',          views.LeadSubmitView.as_view(),             name='lead_submit'),
    path('<int:pk>/valider/',            views.LeadValidateView.as_view(),           name='lead_validate'),
    path('<int:pk>/rejeter/',            views.LeadRejectView.as_view(),             name='lead_reject'),
    path('<int:pk>/assigner/',           views.LeadAssignView.as_view(),             name='lead_assign'),

    # ── Chiffrage depuis lead ────────────────────────────────────────────────
    path('<int:pk>/chiffrage/',          views.LeadChiffrageCreateView.as_view(),    name='lead_chiffrage'),

    # ── Activités agenda (existant) ──────────────────────────────────────────
    path('<int:lead_pk>/activite/',      views.ActivityCreateView.as_view(),         name='activity_create'),
    path('activites/',                   views.ActivityCreateView.as_view(),         name='activity_create_standalone'),
    path('activites/<int:pk>/',          views.ActivityUpdateView.as_view(),         name='activity_update'),
    path('activites/<int:pk>/supprimer/', views.ActivityDeleteView.as_view(),        name='activity_delete'),
    path('agenda/',                      views.AgendaView.as_view(),                 name='agenda'),

    # ── Journal activité (log) ───────────────────────────────────────────────
    path('<int:lead_pk>/log/',           views.LeadLogCreateView.as_view(),          name='lead_log'),

    # ── Rendez-vous (Appointment) ────────────────────────────────────────────
    path('<int:lead_pk>/rdv/nouveau/',   views.AppointmentCreateView.as_view(),      name='appointment_create'),
    path('rdv/<int:pk>/modifier/',       views.AppointmentUpdateView.as_view(),      name='appointment_update'),
    path('rdv/<int:pk>/compte-rendu/',   views.AppointmentReportView.as_view(),      name='appointment_report'),

    # ── Documents ────────────────────────────────────────────────────────────
    path('<int:lead_pk>/documents/ajouter/', views.LeadDocumentUploadView.as_view(), name='document_upload'),
    path('documents/<int:pk>/supprimer/',    views.LeadDocumentDeleteView.as_view(), name='document_delete'),

    # ── Import en masse (admin) ───────────────────────────────────────────────
    path('import/',                          views.ImportLeadsView.as_view(),         name='import_leads'),

    # ── COMEX Dashboard ───────────────────────────────────────────────────────
    path('comex/',                           views.COMEXDashboardView.as_view(),      name='comex'),
]
