# Calculs d'analyse : risque de désengagement, prédiction de participation, clubs en difficulté.
from datetime import timedelta
from participations.models import Participation
from inscriptions.models import Inscription
import numpy as np
from sklearn.linear_model import LinearRegression
from django.utils import timezone
from activites.models import Activite
from clubs.models import Club


# --- Risque de désengagement (règles simples, sans apprentissage) ---
def calculer_taux_presence(inscription, depuis_jours=None):
    """Calcule le taux de présence d'une inscription, optionnellement limité à une période récente."""
    participations = Participation.objects.filter(inscription=inscription)

    if depuis_jours:
        date_limite = timezone.now() - timedelta(days=depuis_jours)
        participations = participations.filter(date_enregistrement__gte=date_limite)

    # Aucune présence enregistrée sur la période : pas de taux calculable.
    total = participations.count()
    if total == 0:
        return None

    presences = participations.filter(statut=Participation.Statut.PRESENT).count()
    return presences / total


def calculer_risque_desengagement(inscription):
    """
    Calcule un score de risque de désengagement (0 à 100) pour une inscription active,
    à partir du taux de présence global, du taux de présence récent (30 derniers jours)
    et de la tendance entre les deux.
    """
    taux_global = calculer_taux_presence(inscription)
    taux_recent = calculer_taux_presence(inscription, depuis_jours=30)

    if taux_global is None:
        # Aucune participation enregistrée : risque neutre, pas assez de données
        return 30.0

    if taux_recent is None:
        taux_recent = taux_global

    # Le taux récent pèse plus lourd (comportement actuel) que le taux global (historique)
    score_engagement = (0.4 * taux_global + 0.6 * taux_recent)

    # Pénalité supplémentaire si la tendance est à la baisse
    tendance_baisse = taux_recent < taux_global
    penalite_tendance = 15 if tendance_baisse else 0

    score_risque = round((1 - score_engagement) * 100 + penalite_tendance, 2)
    return min(max(score_risque, 0), 100)


# Seuils des niveaux : 60 et plus = élevé, 30 à 59 = moyen, sinon faible.
def determiner_niveau_risque(score):
    if score >= 60:
        return 'eleve'
    elif score >= 30:
        return 'moyen'
    return 'faible'


def calculer_risques_desengagement_tous_eleves(**filtre):
    """
    Calcule le risque de désengagement pour les inscriptions actives (éventuellement
    restreintes par `filtre`, ex. eleve__in / club__in) et retourne la liste des
    résultats (sans les sauvegarder — la vue s'en charge).
    Méthode : score à base de règles (taux de présence global/récent), pas d'apprentissage.
    """
    # Uniquement les inscriptions validées (élèves membres).
    inscriptions_actives = Inscription.objects.filter(
        statut=Inscription.Statut.VALIDEE, **filtre
    ).select_related('eleve', 'club')

    resultats = []
    for inscription in inscriptions_actives:
        score = calculer_risque_desengagement(inscription)
        resultats.append({
            "eleve": inscription.eleve,
            "club": inscription.club,
            "score_risque": score,
            "niveau": determiner_niveau_risque(score),
        })

    return resultats

# --- Prédiction du nombre de participants à une activité ---
def predire_nombre_participants(activite):
    """
    PIPELINE DE PRÉDICTION : utilise le modèle entraîné et persisté si
    disponible pour ce club ; sinon, calcule à la volée (comportement de repli).
    """
    from .ml_pipeline import predire_avec_modele_entraine

    prediction_modele_entraine = predire_avec_modele_entraine(activite)
    if prediction_modele_entraine is not None:
        return prediction_modele_entraine

    # --- Repli : calcul à la volée (aucun modèle entraîné pour ce club) ---
    from .ml_pipeline import effectifs_historiques
    effectifs = effectifs_historiques(activite.club, exclure_activite_id=activite.id)

    # Aucun historique : on prévoit la moitié des membres.
    if not effectifs:
        return max(round(activite.club.nombre_membres_actuels * 0.5), 1)

    # Peu d'historique : moyenne des effectifs passés.
    if len(effectifs) < 3:
        return round(sum(effectifs) / len(effectifs))

    # Sinon : tendance par régression linéaire, plafonnée au nombre maximal de membres.
    X = np.arange(len(effectifs)).reshape(-1, 1)
    modele = LinearRegression().fit(X, np.array(effectifs))
    prediction = max(round(modele.predict([[len(effectifs)]])[0]), 0)
    return min(prediction, activite.club.nombre_max_membres)


# --- Détection des clubs en difficulté ---
# Pour être moins ou plus sévère, modifier seuil_baisse (baisse en % à partir de laquelle on alerte).
def detecter_clubs_en_difficulte(seuil_baisse=30):
    """
    Détecte les clubs ayant une baisse d'activité significative, en comparant :
    - le taux de présence moyen sur les 3 dernières activités terminées
    - le taux de présence moyen sur les 3 activités précédentes

    Retourne une liste de dicts : [{"club": Club, "score_difficulte": float, "raison": str}, ...]
    """
    resultats = []

    for club in Club.objects.filter(statut='actif'):
        activites_terminees = Activite.objects.filter(
            club=club, statut=Activite.Statut.TERMINEE
        ).order_by('-date')

        # Taux de présence de chaque activité terminée (de la plus récente à la plus ancienne).
        taux_par_activite = []
        for act in activites_terminees:
            total = act.participations.count()
            if total == 0:
                continue
            presents = act.participations.filter(statut='present').count()
            taux_par_activite.append(presents / total)

        if len(taux_par_activite) < 4:
            continue  # pas assez de données pour évaluer une tendance

        # Compare les 3 activités les plus récentes aux 3 précédentes.
        recentes = taux_par_activite[:3]
        anciennes = taux_par_activite[3:6] if len(taux_par_activite) >= 6 else taux_par_activite[3:]

        if not anciennes:
            continue

        moyenne_recente = sum(recentes) / len(recentes)
        moyenne_ancienne = sum(anciennes) / len(anciennes)

        if moyenne_ancienne == 0:
            continue

        # Baisse en pourcentage ; alerte si elle dépasse le seuil.
        baisse_pourcent = round((1 - moyenne_recente / moyenne_ancienne) * 100, 2)

        if baisse_pourcent >= seuil_baisse:
            resultats.append({
                "club": club,
                "score_difficulte": min(baisse_pourcent, 100),
                "raison": (
                    f"Le taux de présence moyen est passé de {round(moyenne_ancienne*100, 1)}% "
                    f"à {round(moyenne_recente*100, 1)}% sur les activités récentes."
                ),
            })

    resultats.sort(key=lambda x: x["score_difficulte"], reverse=True)
    return resultats