"""
Service — calculs de décomposition/pointage par composant (module Gestion de la pose).
Fonctions pures : rien n'est stocké ici, tout est recalculé à la demande (RG-03).
"""
from decimal import Decimal

TOLERANCE_SOMME_POIDS = Decimal('0.001')


def montant_composant(decomposition, quantite_posee, prix_article) -> Decimal:
    """Montant représenté par une quantité posée sur un composant pondéré."""
    quantite_posee = quantite_posee or Decimal('0')
    prix_article = prix_article or Decimal('0')
    return (quantite_posee * prix_article * decomposition.poids_prix).quantize(Decimal('0.01'))


def _decompositions_actives(article):
    return list(article.decompositions.filter(actif=True).prefetch_related('pointages'))


def _quantite_totale_composant(decomposition) -> Decimal:
    """Σ quantité posée toutes fiches confondues (une par poseur si l'article en a 2+, une
    fiche partagée sinon) — total partagé, pas de quota individuel (voir recap_pose)."""
    fiches = decomposition.pointages.all()
    return sum((f.quantite_posee for f in fiches), Decimal('0'))


def montant_article(article) -> Decimal:
    """Σ des montants de chaque composant actif — jamais stocké (RG-03)."""
    total = Decimal('0')
    for decomposition in _decompositions_actives(article):
        quantite = _quantite_totale_composant(decomposition)
        total += montant_composant(decomposition, quantite, article.prix_de_pose)
    return total


def avancement_article(article) -> float:
    """% d'avancement de l'article = montant recomposé / (prix de pose × quantité prévue)."""
    prix = article.prix_de_pose or Decimal('0')
    base = prix * article.quantite
    if not base:
        return 0.0
    return round(float(montant_article(article)) * 100 / float(base), 1)


def valider_somme_poids(article):
    """RG-04 : Σ poids des composants actifs doit valoir 1.0 (±0.001).

    Référence unique appelée par le formulaire d'édition (clean), la vue d'édition
    et l'import du bordereau (avertissement, non bloquant à l'import — RG-13/RG-14).
    Retourne (is_valid, somme, ecart).
    """
    somme = sum((d.poids_prix for d in _decompositions_actives(article)), Decimal('0'))
    ecart = (somme - Decimal('1')).copy_abs()
    is_valid = ecart <= TOLERANCE_SOMME_POIDS
    return is_valid, somme, ecart


def recap_pose(article):
    """Équivalent RECAP DE POSE : une ligne par composant actif avec poids, quantité totale
    (tous poseurs confondus), montant, avancement — plus le détail par poseur en
    `sous_lignes` pour la saisie (RG nouvelle « split pointage par poseur »).

    Reste/montant/avancement portent toujours sur le TOTAL de l'article (quantité prévue −
    Σ quantités de tous les poseurs) : pas de quota individuel figé par poseur, même quand
    la saisie est éclatée en plusieurs lignes.
    """
    lignes = []
    prix = article.prix_de_pose or Decimal('0')
    poseurs = list(article.poseurs.all())
    split = len(poseurs) >= 2

    for decomposition in _decompositions_actives(article):
        fiches = list(decomposition.pointages.all())
        quantite_totale = sum((f.quantite_posee for f in fiches), Decimal('0'))
        montant = montant_composant(decomposition, quantite_totale, prix)
        base = prix * article.quantite
        avancement = round(float(montant) * 100 / float(base), 1) if base else 0.0

        if split:
            fiches_par_poseur = {f.poseur_id: f for f in fiches if f.poseur_id}
            sous_lignes = [
                {
                    'poseur': poseur,
                    'fiche': fiches_par_poseur.get(poseur.pk),
                    'quantite_posee': (
                        fiches_par_poseur[poseur.pk].quantite_posee if poseur.pk in fiches_par_poseur else Decimal('0')
                    ),
                }
                for poseur in poseurs
            ]
        else:
            fiche_partagee = next((f for f in fiches if f.poseur_id is None), None)
            sous_lignes = [{
                'poseur': poseurs[0] if poseurs else None,
                'fiche': fiche_partagee,
                'quantite_posee': fiche_partagee.quantite_posee if fiche_partagee else Decimal('0'),
            }]

        lignes.append({
            'decomposition': decomposition,
            'quantite_posee': quantite_totale,
            'reste': article.quantite - quantite_totale,
            'montant': montant,
            'avancement': avancement,
            'poids_pourcent': (decomposition.poids_prix * 100).quantize(Decimal('0.01')),
            'sous_lignes': sous_lignes,
            'split': split,
        })
    return lignes


def releve_global_poseur(poseur, exclure_fiche_ids=None):
    """Relevé de paiement d'un poseur sur TOUS ses projets de pose (RG paiement global — un
    poseur travaille souvent sur plusieurs chantiers en parallèle) : montants validés-non-payés
    (« à payer ») et déjà payés, avec le détail par ligne (projet, article, composant, poseur).

    Le paiement est toujours calculé par différence (quantite_posee - quantite_payee), jamais
    sur la quantité totale de la fiche : poser davantage après un premier règlement partiel ne
    doit jamais remettre en cause ce qui a déjà été payé, ni le refacturer. Une même fiche peut
    ainsi apparaître dans les deux listes (un reste à payer validé pendant qu'une part
    antérieure est déjà réglée).

    `exclure_fiche_ids` : fiches à exclure de la liste « à payer » (déjà engagées dans une
    autre demande de paiement en cours — voir pose_workflow_service.fiches_engagees_ids).
    Sert de base aux demandes de paiement (pose_workflow_service.ajouter_lignes_demande).
    """
    from .models import Project
    from .models_pose import PosePointageComposant

    exclure_fiche_ids = exclure_fiche_ids or set()
    a_payer, deja_paye = [], []
    total_a_payer = total_paye = Decimal('0')

    projects = Project.objects.filter(
        pose_meta__isnull=False, pose_articles__poseurs=poseur,
    ).distinct()

    for project in projects:
        articles = project.pose_articles.filter(poseurs=poseur).prefetch_related(
            'poseurs', 'decompositions__pointages__poseur',
        )
        for article in articles:
            poseurs_article = list(article.poseurs.all())
            poseur_unique = poseurs_article[0] if len(poseurs_article) == 1 else None
            prix = article.prix_de_pose or Decimal('0')
            for decomposition in article.decompositions.filter(actif=True):
                for fiche in decomposition.pointages.all():
                    if fiche.quantite_posee <= 0 and fiche.quantite_payee <= 0:
                        continue
                    fiche_poseur = fiche.poseur or poseur_unique
                    if fiche_poseur != poseur:
                        continue

                    solde_impaye = fiche.quantite_posee - fiche.quantite_payee
                    if (
                        fiche.statut == PosePointageComposant.Statut.VALIDE
                        and solde_impaye > 0
                        and fiche.pk not in exclure_fiche_ids
                    ):
                        montant_du = montant_composant(decomposition, solde_impaye, prix)
                        a_payer.append({
                            'project': project, 'article': article, 'poseur': poseur,
                            'decomposition': decomposition, 'fiche': fiche,
                            'quantite': solde_impaye, 'montant': montant_du,
                        })
                        total_a_payer += montant_du

                    if fiche.quantite_payee > 0:
                        montant_regle = montant_composant(decomposition, fiche.quantite_payee, prix)
                        deja_paye.append({
                            'project': project, 'article': article, 'poseur': poseur,
                            'decomposition': decomposition, 'fiche': fiche,
                            'quantite': fiche.quantite_payee, 'montant': montant_regle,
                        })
                        total_paye += montant_regle

    return {
        'a_payer': a_payer, 'deja_paye': deja_paye,
        'total_a_payer': total_a_payer, 'total_paye': total_paye,
    }
