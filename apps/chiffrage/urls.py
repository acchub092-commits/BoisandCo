from django.urls import path
from . import views

app_name = 'chiffrage'

urlpatterns = [
    path('',                              views.DashboardView.as_view(),     name='dashboard'),
    path('nouveau/',                      views.DemandeCreateView.as_view(), name='create'),
    path('<int:pk>/',                     views.DemandeDetailView.as_view(), name='detail'),

    # Actions DC
    path('<int:pk>/action-dc/',           views.ActionDCView.as_view(),      name='action_dc'),

    # Actions Méthodes
    path('<int:pk>/assigner/',            views.AssignerView.as_view(),      name='assigner'),
    path('<int:pk>/jalon/',               views.JalonView.as_view(),         name='jalon'),
    path('<int:pk>/montant/',             views.MontantView.as_view(),       name='montant'),
    path('<int:pk>/soumettre-dg/',        views.SoumettreDevisView.as_view(),name='soumettre_dg'),
    path('<int:pk>/valider-rm/',          views.ValiderRMView.as_view(),     name='valider_rm'),
    path('<int:pk>/reprendre/',           views.RepriseRevisionView.as_view(),name='reprendre'),

    # Actions DG
    path('<int:pk>/action-dg/',           views.ActionDGView.as_view(),      name='action_dg'),

    # Actions Commercial
    path('<int:pk>/resultat/',            views.ResultatView.as_view(),      name='resultat'),

    # Communication
    path('<int:pk>/message/',             views.MessageView.as_view(),       name='message'),
    path('<int:pk>/fichier/',             views.FichierUploadView.as_view(), name='fichier'),

    # Modification
    path('<int:pk>/modification/',        views.ModificationView.as_view(),  name='modification'),
    path('modif/<int:pk>/arbitrer/',      views.ArbitrerModifView.as_view(), name='arbitrer_modif'),

    # Visionneuse sécurisée — devis final
    path('<int:pk>/devis/<int:fichier_pk>/apercu/', views.DevisPreviewView.as_view(), name='devis_preview'),

    # Révision technique/prix
    path('<int:pk>/revision/',    views.RevisionDemandeView.as_view(), name='revision'),
    path('<int:pk>/revision-dc/', views.RevisionDCView.as_view(),      name='revision_dc'),

    # Téléchargement sécurisé (force attachment)
    path('<int:pk>/fichier/<int:fichier_pk>/telecharger/', views.FichierDownloadView.as_view(), name='fichier_download'),

    # Suppression fichier (admin uniquement)
    path('<int:pk>/fichier/<int:fichier_pk>/supprimer/', views.FichierDeleteView.as_view(), name='fichier_delete'),
]
