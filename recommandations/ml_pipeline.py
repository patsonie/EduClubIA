"""
Pipeline d'entraînement, de validation et de prédiction pour le module de
recommandations IA (content-based filtering + collaborative filtering).

Entraînement : ajuste les modèles sur l'ensemble des données actuelles et les
persiste sur disque (joblib). La prédiction charge ces modèles (avec cache) et
retombe sur un calcul à la volée s'ils sont absents ou périmés.

Validation : métriques de classement calculées SANS fuite de données
(l'élément masqué est retiré de la matrice d'entraînement), comparées à une
baseline de popularité.
"""

import joblib
import numpy as np
import pandas as pd
from django.conf import settings
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.neighbors import NearestNeighbors
from clubs.models import Club
from inscriptions.models import Inscription
from .services import (
    construire_texte_profil_club, construire_texte_profil_eleve, nouveau_vectoriseur,
)

# Emplacement des fichiers du modèle « profil » (TF-IDF).
CHEMIN_VECTORIZER = settings.IA_MODELES_DIR / 'tfidf_vectorizer.pkl'
CHEMIN_MATRICE_CLUBS = settings.IA_MODELES_DIR / 'tfidf_matrice_clubs.pkl'
CHEMIN_CLUB_IDS = settings.IA_MODELES_DIR / 'tfidf_club_ids.pkl'

# Emplacement des fichiers du modèle « comportement » (KNN).
CHEMIN_MODELE_KNN = settings.IA_MODELES_DIR / 'knn_modele.pkl'
CHEMIN_MATRICE_ELEVE_CLUB = settings.IA_MODELES_DIR / 'knn_matrice_eleve_club.pkl'
CHEMIN_ELEVE_IDS = settings.IA_MODELES_DIR / 'knn_eleve_ids.pkl'

# Nombre de clubs proposés pris en compte lors de la validation (top 3).
TOP_K_VALIDATION = 3


def entrainer_modele_content_based():
    """
    PIPELINE D'ENTRAÎNEMENT (content-based) : ajuste un TF-IDF sur le corpus des
    clubs actifs et persiste le vectoriseur + la matrice résultante.
    """
    clubs = list(Club.objects.filter(statut=Club.Statut.ACTIF))
    if not clubs:
        return {"statut": "echec", "raison": "Aucun club actif à entraîner."}

    # Texte de chaque club actif → matrice TF-IDF.
    textes = [construire_texte_profil_club(c) for c in clubs]
    club_ids = [c.id for c in clubs]

    vectorizer = nouveau_vectoriseur()
    try:
        matrice_clubs = vectorizer.fit_transform(textes)
    except ValueError:
        return {"statut": "echec", "raison": "Vocabulaire vide : descriptions de clubs insuffisantes."}

    # Sauvegarde sur disque, relue ensuite par services.py.
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
    VALIDATION (content-based) : pour chaque élève ayant un profil déclaré
    (centres d'intérêt / filière) et au moins un club validé, on classe les clubs
    à partir du seul profil déclaré (sans l'historique d'inscriptions) et on mesure
    si un de ses clubs réels figure dans le top-k (hit rate@k), par rapport à une
    baseline de popularité. Précision@k et couverture sont aussi fournies.
    """
    clubs = list(Club.objects.filter(statut=Club.Statut.ACTIF))
    if len(clubs) < 2:
        return {"valide": False, "raison": "Pas assez de clubs actifs pour valider."}

    # Clubs réellement suivis par chaque élève, et clubs les plus populaires (référence de comparaison).
    from utilisateurs.models import Utilisateur
    inscriptions = Inscription.objects.filter(
        statut=Inscription.Statut.VALIDEE, club__statut=Club.Statut.ACTIF
    ).values_list('eleve_id', 'club_id')
    clubs_par_eleve = {}
    for eleve_id, club_id in inscriptions:
        clubs_par_eleve.setdefault(eleve_id, set()).add(club_id)
    popularite = pd.Series([c for _, c in inscriptions]).value_counts()
    top_populaires = list(popularite.index[:TOP_K_VALIDATION]) if len(popularite) else []

    # Élèves évalués : ceux qui ont un profil déclaré et au moins un club validé.
    eleves = [
        e for e in Utilisateur.objects.filter(id__in=clubs_par_eleve.keys()).prefetch_related('interets')
        if construire_texte_profil_eleve(e, inclure_historique=False).strip()
    ]
    if len(eleves) < 5:
        return {
            "valide": False,
            "raison": "Moins de 5 élèves avec profil déclaré et club validé : validation non significative.",
            "nb_eleves_evalues": len(eleves),
        }

    # Similarité entre le profil de chaque élève et chaque club.
    textes_clubs = [construire_texte_profil_club(c) for c in clubs]
    ids_clubs = [c.id for c in clubs]
    textes_eleves = [construire_texte_profil_eleve(e, inclure_historique=False) for e in eleves]
    try:
        matrice = nouveau_vectoriseur().fit_transform(textes_clubs + textes_eleves)
    except ValueError:
        return {"valide": False, "raison": "Vocabulaire vide."}
    sim = cosine_similarity(matrice[len(clubs):], matrice[:len(clubs)])

    # Pour chaque élève : un de ses vrais clubs est-il dans le top 3 proposé ?
    hits, hits_baseline, precisions, clubs_recommandes = 0, 0, [], set()
    for i, eleve in enumerate(eleves):
        reels = clubs_par_eleve[eleve.id]
        top = [ids_clubs[j] for j in np.argsort(-sim[i])[:TOP_K_VALIDATION]]
        clubs_recommandes.update(top)
        correct = len(reels & set(top))
        hits += 1 if correct else 0
        precisions.append(correct / TOP_K_VALIDATION)
        hits_baseline += 1 if reels & set(top_populaires) else 0

    # Le modèle est jugé valide s'il fait au moins aussi bien que la simple popularité.
    hit_rate = round(hits / len(eleves) * 100, 1)
    hit_baseline = round(hits_baseline / len(eleves) * 100, 1)
    return {
        "valide": hit_rate >= hit_baseline,
        "k": TOP_K_VALIDATION,
        "hit_rate_pourcent": hit_rate,
        "baseline_popularite_pourcent": hit_baseline,
        "precision_moyenne_pourcent": round(float(np.mean(precisions)) * 100, 1),
        "couverture_catalogue_pourcent": round(len(clubs_recommandes) / len(clubs) * 100, 1),
        "nb_eleves_evalues": len(eleves),
    }


# Matrice élève × club (1 = inscrit) utilisée par le modèle collaboratif.
def _matrice_eleve_club():
    inscriptions = Inscription.objects.filter(
        statut__in=['validee', 'en_attente', 'archivee']
    ).values('eleve_id', 'club_id')
    donnees = list(inscriptions)
    if not donnees:
        return pd.DataFrame()
    df = pd.DataFrame(donnees)
    df['valeur'] = 1
    return df.pivot_table(index='eleve_id', columns='club_id', values='valeur', fill_value=0, aggfunc='max')


def entrainer_modele_collaboratif():
    """
    PIPELINE D'ENTRAÎNEMENT (collaboratif) : matrice élève×club et KNN cosinus, persistés.
    """
    matrice = _matrice_eleve_club()
    if matrice.empty:
        return {"statut": "echec", "raison": "Aucune inscription disponible pour l'entraînement."}

    if len(matrice) < 2:
        return {"statut": "echec", "raison": "Pas assez d'élèves distincts pour entraîner un modèle collaboratif."}

    # Ajustement du KNN (6 voisins au plus) puis sauvegarde sur disque.
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


def valider_modele_collaboratif(k_voisins=5, top_k=TOP_K_VALIDATION, taille_max=100):
    """
    VALIDATION « leave-one-out » sans fuite : pour chaque élève ayant >= 2 clubs, on
    masque un club DANS LA MATRICE D'ENTRAÎNEMENT (la ligne de l'élève est modifiée
    avant l'ajustement du KNN), puis on regarde si ce club apparaît dans le top-k des
    clubs recommandés par les voisins. Métriques : hit rate@k, précision@k, rappel@k,
    comparées à la baseline « clubs les plus populaires ».
    """
    matrice = _matrice_eleve_club()
    if matrice.empty:
        return {"valide": False, "raison": "Aucune donnée pour valider."}

    # Seuls les élèves ayant au moins 2 clubs peuvent être évalués (on en masque un).
    eligibles = matrice[matrice.sum(axis=1) >= 2]
    if len(eligibles) < 5 or len(matrice) < 6:
        return {
            "valide": False,
            "raison": "Moins de 5 élèves avec au moins 2 clubs : validation non significative.",
            "nb_eleves_evalues": int(len(eligibles)),
        }

    echantillon = eligibles.sample(min(taille_max, len(eligibles)), random_state=42)
    popularite = matrice.sum(axis=0).sort_values(ascending=False)

    hits = hits_baseline = 0
    precisions, rappels, clubs_recommandes = [], [], set()

    # Pour chaque élève de l'échantillon : masquer un club, réentraîner, et vérifier qu'il est retrouvé.
    for eleve_id, ligne in echantillon.iterrows():
        clubs_reels = list(ligne[ligne == 1].index)
        club_masque = clubs_reels[0]  # déterministe (index trié)

        entrainement = matrice.copy()
        entrainement.loc[eleve_id, club_masque] = 0  # masquage AVANT l'ajustement : pas de fuite
        modele = NearestNeighbors(n_neighbors=min(k_voisins + 1, len(entrainement)), metric='cosine')
        modele.fit(entrainement.values)

        position = entrainement.index.get_loc(eleve_id)
        distances, voisins = modele.kneighbors([entrainement.iloc[position].values])

        # Score de chaque club selon les voisins les plus proches.
        scores = {}
        for distance, idx in zip(distances[0], voisins[0]):
            if entrainement.index[idx] == eleve_id:
                continue
            for club_id in entrainement.columns[entrainement.iloc[idx].values == 1]:
                if entrainement.loc[eleve_id, club_id] == 1:
                    continue  # déjà rejoint (hors club masqué)
                scores[club_id] = scores.get(club_id, 0) + (1 - distance)

        top = [c for c, _ in sorted(scores.items(), key=lambda x: -x[1])[:top_k]]
        clubs_recommandes.update(top)
        reussi = club_masque in top
        hits += 1 if reussi else 0
        precisions.append((1 if reussi else 0) / top_k)
        rappels.append(1 if reussi else 0)

        # Même test avec la simple popularité (référence).
        top_pop = [c for c in popularite.index if entrainement.loc[eleve_id, c] == 0][:top_k]
        hits_baseline += 1 if club_masque in top_pop else 0

    # Bilan de la validation.
    n = len(echantillon)
    hit_rate = round(hits / n * 100, 1)
    hit_baseline = round(hits_baseline / n * 100, 1)
    return {
        "valide": hit_rate >= hit_baseline,
        "k": top_k,
        "hit_rate_pourcent": hit_rate,
        "baseline_popularite_pourcent": hit_baseline,
        "precision_moyenne_pourcent": round(float(np.mean(precisions)) * 100, 1),
        "rappel_moyen_pourcent": round(float(np.mean(rappels)) * 100, 1),
        "couverture_catalogue_pourcent": round(len(clubs_recommandes) / matrice.shape[1] * 100, 1),
        "nb_eleves_evalues": n,
    }
