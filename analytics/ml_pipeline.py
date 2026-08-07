"""
Pipeline d'entraînement/validation pour la prédiction de participation.
Entraîne un modèle de régression par club (sur l'historique d'activités),
persisté globalement, pour que la prédiction en production soit un simple chargement.
"""

import joblib
import numpy as np
from django.conf import settings
from sklearn.linear_model import LinearRegression
from clubs.models import Club
from activites.models import Activite

CHEMIN_MODELES_PARTICIPATION = settings.IA_MODELES_DIR / 'modeles_participation_par_club.pkl'


def entrainer_modele_participation():
    """
    PIPELINE D'ENTRAÎNEMENT : ajuste une régression linéaire par club (sur la
    séquence chronologique de ses activités terminées) et persiste l'ensemble
    des modèles dans un seul fichier (dictionnaire club_id -> modèle entraîné).
    """
    modeles_par_club = {}
    nb_clubs_entraines = 0

    for club in Club.objects.filter(statut='actif'):
        activites_terminees = Activite.objects.filter(
            club=club, statut=Activite.Statut.TERMINEE
        ).order_by('date')

        effectifs = [
            act.participations.filter(statut='present').count()
            for act in activites_terminees
        ]
        effectifs = [e for e in effectifs if e > 0]

        if len(effectifs) < 3:
            continue

        X = np.arange(len(effectifs)).reshape(-1, 1)
        y = np.array(effectifs)

        modele = LinearRegression()
        modele.fit(X, y)

        modeles_par_club[club.id] = {
            "modele": modele,
            "nb_points_entrainement": len(effectifs),
            "capacite_max": club.nombre_max_membres,
        }
        nb_clubs_entraines += 1

    if not modeles_par_club:
        return {"statut": "echec", "raison": "Aucun club n'a assez d'historique d'activités pour être entraîné (minimum 3 activités terminées avec présences)."}

    joblib.dump(modeles_par_club, CHEMIN_MODELES_PARTICIPATION)

    return {"statut": "succes", "nombre_clubs_entraines": nb_clubs_entraines}


def valider_modele_participation():
    """
    PIPELINE DE VALIDATION : pour les clubs ayant assez de données, calcule
    l'erreur moyenne absolue (MAE) via un découpage train/test simple.
    """
    if not CHEMIN_MODELES_PARTICIPATION.exists():
        return {"valide": False, "raison": "Aucun modèle entraîné à valider."}

    modeles_par_club = joblib.load(CHEMIN_MODELES_PARTICIPATION)
    erreurs = []

    for club_id, contenu in modeles_par_club.items():
        club = Club.objects.filter(id=club_id).first()
        if not club:
            continue

        activites_terminees = Activite.objects.filter(
            club=club, statut=Activite.Statut.TERMINEE
        ).order_by('date')
        effectifs = [
            act.participations.filter(statut='present').count()
            for act in activites_terminees
        ]
        effectifs = [e for e in effectifs if e > 0]

        if len(effectifs) < 4:
            continue

        limite_test = max(1, len(effectifs) // 4)
        entrainement = effectifs[:-limite_test]
        test = effectifs[-limite_test:]

        X_entrainement = np.arange(len(entrainement)).reshape(-1, 1)
        modele_test = LinearRegression().fit(X_entrainement, np.array(entrainement))

        X_test = np.arange(len(entrainement), len(entrainement) + len(test)).reshape(-1, 1)
        predictions = modele_test.predict(X_test)

        erreur_moyenne = float(np.mean(np.abs(predictions - np.array(test))))
        erreurs.append(erreur_moyenne)

    if not erreurs:
        return {"valide": True, "raison": "Pas assez de données pour valider avec un découpage train/test ; validation basique passée."}

    mae_globale = round(float(np.mean(erreurs)), 2)
    return {"valide": True, "mae_moyenne": mae_globale, "nombre_clubs_valides": len(erreurs)}


def predire_avec_modele_entraine(activite):
    """Utilise le modèle persisté pour ce club, si disponible. Retourne None sinon (repli à gérer par l'appelant)."""
    if not CHEMIN_MODELES_PARTICIPATION.exists():
        return None

    modeles_par_club = joblib.load(CHEMIN_MODELES_PARTICIPATION)
    contenu = modeles_par_club.get(activite.club_id)
    if not contenu:
        return None

    nb_points = contenu["nb_points_entrainement"]
    prediction = contenu["modele"].predict([[nb_points]])[0]
    prediction = max(round(prediction), 0)
    return min(prediction, contenu["capacite_max"])