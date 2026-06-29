"""
Service de calcul — module Suivi Décomptes (autonome, aucune liaison Project).
"""

ROLES_LECTURE  = ('ADV', 'DIRECTEUR', 'MANAGER', 'FINANCE', 'ADMIN')
ROLES_ECRITURE = ('ADV', 'ADMIN')


def peut_lire(user) -> bool:
    if user.is_superuser:
        return True
    return getattr(user, 'role', None) in ROLES_LECTURE


def peut_ecrire(user) -> bool:
    if user.is_superuser:
        return True
    return getattr(user, 'role', None) in ROLES_ECRITURE


def compute_kpis(projet) -> dict:
    """Retourne tous les indicateurs calculés pour un DecompteProjet."""
    return {
        'marche_yc_avenants':          projet.marche_yc_avenants,
        'cumul_attachement':           projet.cumul_attachement,
        'cumul_rg':                    projet.cumul_rg,
        'cumul_rf':                    projet.cumul_rf,
        'cumul_prorata':               projet.cumul_prorata,
        'cumul_reglements':            projet.cumul_reglements,
        'cumul_liv_systeme':           projet.cumul_liv_systeme,
        'cumul_amortissement_acompte': projet.cumul_amortissement_acompte,
        'alerte_acompte':              projet.alerte_acompte,
        'reste_a_livrer':              projet.reste_a_livrer,
        'reste_a_attacher':            projet.reste_a_attacher,
        'dernier_decompte':            projet._dernier,
    }


def get_dashboard_rows(user) -> list:
    """
    Retourne la liste des DecompteProjet avec leurs KPIs.
    Filtre par commercial si l'utilisateur est COMMERCIAL.
    """
    from apps.projects.models import DecompteProjet

    qs = DecompteProjet.objects.select_related(
        'commercial', 'chef_de_projet',
    ).prefetch_related('avenants_decompte', 'decompte_lignes')

    role = getattr(user, 'role', None)
    if not user.is_superuser and role == 'COMMERCIAL':
        qs = qs.filter(commercial=user)

    rows = []
    for dp in qs:
        kpis = compute_kpis(dp)
        rows.append({'projet': dp, **kpis})
    return rows
