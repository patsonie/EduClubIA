"""
Pipeline d'entraînement/validation pour la prédiction de participation.

Modèle : régression linéaire par club sur la série chronologique du nombre de présents
aux activités terminées (variable explicative : rang de l'activité). C'est une
extrapolation de tendance ; les limites (petites séries, pas d'information sur la
date/type d'activité) sont documentées dans le README.
"""

import joblib
import numpy as np
from django.conf import settings
from django.db.models import Count, Q
from sklearn.linear_model import LinearRegression
from clubs.models import Club
from activites.models import Activite

CHEMIN_MODELES_PARTICIPATION = settings.IA_MODELES_DIR / 'modeles_participation_par_club.pkl'
MIN_POINTS_ENTRAINEMENT = 3
MIN_POINTS_VALIDATION = 4


def effectifs_historiques(club, exclure_activite_id=None):
    """Nombre de présents par activité terminée du club (ordre chronologique), présences > 0 seulement."""
    activites = Activite.objects.filter(club=club, statut=Activite.Statut.TERMINEE)
    if exclure_activite_id:
        activites = activites.exclude(id=exclure_activite_id)
    activites = activites.annotate(
        presents=Count('participations', filter=Q(participations__statut='present'))
    ).order_by('date', 'heure')
    return [a.presents for a in activites if a.presents > 0]


def entrainer_modele_participation():
    """
    PIPELINE D'ENTRAÎNEMENT : ajuste une régression linéaire par club (au moins
    3 activités terminées avec présences) et persiste le dictionnaire club_id -> modèle.
    """
    modeles_par_club = {}

    for club in Club.objects.filter(statut=Club.Statut.ACTIF):
        effectifs = effectifs_historiques(club)
        if len(effectifs) < MIN_POINTS_ENTRAINEMENT:
            continue

        X = np.arange(len(effectifs)).reshape(-1, 1)
        modele = LinearRegression().fit(X, np.array(effectifs))
        modeles_par_club[club.id] = {"modele": modele, "nb_points_entrainement": len(effectifs)}

    if not modeles_par_club:
        return {"statut": "echec", "raison": "Aucun club n'a assez d'historique d'activités pour être entraîné (minimum 3 activités terminées avec présences)."}

    joblib.dump(modeles_par_club, CHEMIN_MODELES_PARTICIPATION)
    return {"statut": "succes", "nombre_clubs_entraines": len(modeles_par_club)}


def valider_modele_participation():
    """
    VALIDATION : découpage chronologique (75 % entraînement / 25 % test) par club
    (>= 4 points). Métriques agrégées : MAE, RMSE et R² du modèle, comparés à une
    baseline « moyenne des effectifs passés ». Le modèle n'est jugé valide que s'il
    fait au moins aussi bien que la baseline.
    """
    clubs_valides = []
    erreurs_modele, erreurs_baseline = [], []
    y_vrais, y_pred = [], []

    for club in Club.objects.filter(statut=Club.Statut.ACTIF):
        effectifs = effectifs_historiques(club)
        if len(effectifs) < MIN_POINTS_VALIDATION:
            continue

        limite_test = max(1, len(effectifs) // 4)
        entrainement, test = effectifs[:-limite_test], effectifs[-limite_test:]

        X_train = np.arange(len(entrainement)).reshape(-1, 1)
        modele = LinearRegression().fit(X_train, np.array(entrainement))
        X_test = np.arange(len(entrainement), len(entrainement) + len(test)).reshape(-1, 1)
        predictions = np.maximum(modele.predict(X_test), 0)

        erreurs_modele.extend(np.abs(predictions - np.array(test)))
        erreurs_baseline.extend(np.abs(np.mean(entrainement) - np.array(test)))
        y_vrais.extend(test)
        y_pred.extend(predictions)
        clubs_valides.append(club.id)

    if not clubs_valides:
        return {"valide": False, "raison": "Pas assez de données (>= 4 activités terminées avec présences par club) pour valider."}

    y_vrais, y_pred = np.array(y_vrais), np.array(y_pred)
    mae = float(np.mean(erreurs_modele))
    mae_baseline = float(np.mean(erreurs_baseline))
    rmse = float(np.sqrt(np.mean((y_pred - y_vrais) ** 2)))
    ss_tot = float(np.sum((y_vrais - np.mean(y_vrais)) ** 2))
    r2 = round(1 - float(np.sum((y_vrais - y_pred) ** 2)) / ss_tot, 3) if ss_tot > 0 else None

    return {
        "valide": mae <= mae_baseline,
        "mae": round(mae, 2),
        "mae_baseline_moyenne": round(mae_baseline, 2),
        "rmse": round(rmse, 2),
        "r2": r2,
        "nombre_clubs_valides": len(clubs_valides),
        "nombre_points_test": int(len(y_vrais)),
    }


def predire_avec_modele_entraine(activite):
    """
    Utilise le modèle persisté du club. Le rang à prédire est recalculé à partir
    de l'historique actuel (nombre d'activités terminées avec présences), de sorte
    que la prédiction reste cohérente après de nouvelles activités.
    Retourne None si aucun modèle n'est disponible (repli à gérer par l'appelant).
    """
    if not CHEMIN_MODELES_PARTICIPATION.exists():
        return None

    from recommandations.services import charger_modele
    modeles_par_club = charger_modele(CHEMIN_MODELES_PARTICIPATION)
    contenu = modeles_par_club.get(activite.club_id)
    if not contenu:
        return None

    rang = len(effectifs_historiques(activite.club, exclure_activite_id=activite.id))
    prediction = contenu["modele"].predict([[rang]])[0]
    prediction = max(round(prediction), 0)
    return min(prediction, activite.club.nombre_max_membres)
