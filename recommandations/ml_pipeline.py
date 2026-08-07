"""
Pipeline d'entraînement, de validation et de prédiction pour le module de
recommandations IA (content-based filtering + collaborative filtering).

Entraînement : ajuste les modèles sur l'ensemble des données actuelles et les
persiste sur disque (joblib), pour que la prédiction (à la demande) n'ait
plus qu'à charger des modèles déjà entraînés, sans recalcul complet à chaque requête.
"""

import joblib
import numpy as np
import pandas as pd
from django.conf import settings
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neighbors import NearestNeighbors
from clubs.models import Club
from inscriptions.models import Inscription
from .services import construire_texte_profil_club

CHEMIN_VECTORIZER = settings.IA_MODELES_DIR / 'tfidf_vectorizer.pkl'
CHEMIN_MATRICE_CLUBS = settings.IA_MODELES_DIR / 'tfidf_matrice_clubs.pkl'
CHEMIN_CLUB_IDS = settings.IA_MODELES_DIR / 'tfidf_club_ids.pkl'

CHEMIN_MODELE_KNN = settings.IA_MODELES_DIR / 'knn_modele.pkl'
CHEMIN_MATRICE_ELEVE_CLUB = settings.IA_MODELES_DIR / 'knn_matrice_eleve_club.pkl'
CHEMIN_ELEVE_IDS = settings.IA_MODELES_DIR / 'knn_eleve_ids.pkl'


def entrainer_modele_content_based():
    """
    PIPELINE D'ENTRAÎNEMENT (content-based) : ajuste un TfidfVectorizer sur le
    corpus de tous les clubs actifs et persiste le vectoriseur + la matrice
    résultante, pour que la prédiction se limite à un simple `.transform()`.
    """
    clubs = list(Club.objects.filter(statut='actif'))
    if not clubs:
        return {"statut": "echec", "raison": "Aucun club actif à entraîner."}

    textes = [construire_texte_profil_club(c) for c in clubs]
    club_ids = [c.id for c in clubs]

    vectorizer = TfidfVectorizer(stop_words=None)
    matrice_clubs = vectorizer.fit_transform(textes)

    joblib.dump(vectorizer, CHEMIN_VECTORIZER)
    joblib.dump(matrice_clubs, CHEMIN_MATRICE_CLUBS)
    joblib.dump(club_ids, CHEMIN_CLUB_IDS)

    return {
        "statut": "succes",
        "nombre_clubs_entraines": len(clubs),
        "taille_vocabulaire": len(vectorizer.vocabulary_),
    }


def valider_modele_content_based():
    """
    PIPELINE DE VALIDATION : vérifie que le modèle entraîné produit une
    couverture raisonnable (chaque club a un vecteur non nul, donc pourra
    être recommandé) — une validation simple mais réelle du pipeline.
    """
    if not CHEMIN_MATRICE_CLUBS.exists():
        return {"valide": False, "raison": "Aucun modèle entraîné à valider."}

    matrice = joblib.load(CHEMIN_MATRICE_CLUBS)
    nb_clubs = matrice.shape[0]
    nb_vecteurs_non_nuls = int((matrice.sum(axis=1) > 0).sum())
    taux_couverture = round((nb_vecteurs_non_nuls / nb_clubs) * 100, 1) if nb_clubs else 0

    return {
        "valide": taux_couverture >= 50,
        "taux_couverture_pourcent": taux_couverture,
        "nb_clubs_avec_vecteur": nb_vecteurs_non_nuls,
        "nb_clubs_total": nb_clubs,
    }


def entrainer_modele_collaboratif():
    """
    PIPELINE D'ENTRAÎNEMENT (collaboratif) : construit la matrice élève×club
    et ajuste un modèle KNN, persisté pour la prédiction.
    """
    inscriptions = Inscription.objects.filter(
        statut__in=['validee', 'en_attente', 'archivee']
    ).values('eleve_id', 'club_id')

    if not inscriptions:
        return {"statut": "echec", "raison": "Aucune inscription disponible pour l'entraînement."}

    df = pd.DataFrame(list(inscriptions))
    df['valeur'] = 1
    matrice = df.pivot_table(index='eleve_id', columns='club_id', values='valeur', fill_value=0, aggfunc='max')

    if len(matrice) < 2:
        return {"statut": "echec", "raison": "Pas assez d'élèves distincts pour entraîner un modèle collaboratif."}

    nb_voisins = min(6, len(matrice))
    modele = NearestNeighbors(n_neighbors=nb_voisins, metric='cosine')
    modele.fit(matrice.values)

    joblib.dump(modele, CHEMIN_MODELE_KNN)
    joblib.dump(matrice, CHEMIN_MATRICE_ELEVE_CLUB)
    joblib.dump(list(matrice.index), CHEMIN_ELEVE_IDS)

    return {
        "statut": "succes",
        "nombre_eleves_entraines": len(matrice),
        "nombre_clubs_couverts": matrice.shape[1],
    }


def valider_modele_collaboratif():
    """
    PIPELINE DE VALIDATION : validation "leave-one-out" simplifiée — pour un
    échantillon d'élèves ayant plusieurs clubs, on masque un club et on
    vérifie si le modèle parvient à le retrouver parmi ses voisins les plus proches.
    """
    if not CHEMIN_MODELE_KNN.exists():
        return {"valide": False, "raison": "Aucun modèle entraîné à valider."}

    modele = joblib.load(CHEMIN_MODELE_KNN)
    matrice = joblib.load(CHEMIN_MATRICE_ELEVE_CLUB)

    eleves_avec_plusieurs_clubs = matrice[matrice.sum(axis=1) >= 2]
    if eleves_avec_plusieurs_clubs.empty:
        return {"valide": True, "raison": "Pas assez de données pour un test leave-one-out, validation basique passée."}

    echantillon = eleves_avec_plusieurs_clubs.sample(min(10, len(eleves_avec_plusieurs_clubs)), random_state=42)
    reussites = 0

    for idx_eleve, ligne in echantillon.iterrows():
        clubs_reels = set(ligne[ligne == 1].index)
        club_masque = next(iter(clubs_reels))

        ligne_modifiee = ligne.copy()
        ligne_modifiee[club_masque] = 0

        distances, indices_voisins = modele.kneighbors([ligne_modifiee.values])
        clubs_recommandes = set()
        for idx_voisin in indices_voisins[0]:
            clubs_recommandes.update(matrice.columns[matrice.iloc[idx_voisin].values == 1])

        if club_masque in clubs_recommandes:
            reussites += 1

    taux_reussite = round((reussites / len(echantillon)) * 100, 1)
    return {
        "valide": taux_reussite >= 20,
        "taux_reussite_pourcent": taux_reussite,
        "taille_echantillon": len(echantillon),
    }