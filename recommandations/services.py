from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from clubs.models import Club
from inscriptions.models import Inscription
import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors
from utilisateurs.models import Utilisateur



def construire_texte_profil_eleve(eleve):
    """
    Construit un texte représentant le profil de l'élève à partir de :
    - ses centres d'intérêt déclarés
    - sa filière
    - les catégories des clubs auxquels il a déjà été inscrit (comportement passé)
    """
    elements = []

    if eleve.centres_interet:
        elements.append(eleve.centres_interet)

    if eleve.filiere:
        elements.append(eleve.filiere)

    categories_passees = Inscription.objects.filter(
        eleve=eleve
    ).exclude(
        statut=Inscription.Statut.REFUSEE
    ).values_list('club__categorie', flat=True)

    elements.extend(categories_passees)

    return " ".join(elements) if elements else ""


def construire_texte_profil_club(club):
    """Construit un texte représentant le contenu d'un club."""
    return f"{club.categorie} {club.description} {club.objectifs}"


def clubs_deja_rejoints(eleve):
    """Retourne les IDs des clubs auxquels l'élève est déjà inscrit activement."""
    return Inscription.objects.filter(
        eleve=eleve,
        statut__in=[Inscription.Statut.VALIDEE, Inscription.Statut.EN_ATTENTE],
    ).values_list('club_id', flat=True)


def generer_explication(eleve, club, mots_communs):
    """Génère une explication lisible à partir des mots-clés communs détectés."""
    if not mots_communs:
        return f"Le club {club.nom} pourrait vous intéresser selon votre profil général."

    mots_affiches = ", ".join(mots_communs[:3])
    return (
        f"Le club {club.nom} vous est recommandé car votre profil correspond "
        f"aux thématiques suivantes : {mots_affiches}."
    )


def calculer_recommandations_content_based(eleve, top_n=10):
    """
    PIPELINE DE PRÉDICTION (content-based).
    Utilise le modèle entraîné et persisté (joblib) si disponible ; sinon,
    calcule à la volée (comportement de repli, utile avant le premier entraînement).
    """
    import joblib
    from django.conf import settings

    texte_eleve = construire_texte_profil_eleve(eleve)
    if not texte_eleve.strip():
        return []

    chemin_vectorizer = settings.IA_MODELES_DIR / 'tfidf_vectorizer.pkl'
    chemin_matrice = settings.IA_MODELES_DIR / 'tfidf_matrice_clubs.pkl'
    chemin_ids = settings.IA_MODELES_DIR / 'tfidf_club_ids.pkl'

    ids_deja_rejoints = set(clubs_deja_rejoints(eleve))

    if chemin_vectorizer.exists() and chemin_matrice.exists() and chemin_ids.exists():
        # --- Utilisation du modèle entraîné (pipeline de prédiction pur) ---
        vectorizer = joblib.load(chemin_vectorizer)
        matrice_clubs = joblib.load(chemin_matrice)
        club_ids = joblib.load(chemin_ids)

        vecteur_eleve = vectorizer.transform([texte_eleve])
        similarites = cosine_similarity(vecteur_eleve, matrice_clubs)[0]

        clubs_par_id = {c.id: c for c in Club.objects.filter(id__in=club_ids)}
        mots_eleve = set(w.lower() for w in texte_eleve.split())

        resultats = []
        for club_id, score in zip(club_ids, similarites):
            if club_id in ids_deja_rejoints or club_id not in clubs_par_id:
                continue
            club = clubs_par_id[club_id]
            texte_club = construire_texte_profil_club(club).lower()
            mots_communs = [mot for mot in mots_eleve if mot in texte_club and len(mot) > 2]

            resultats.append({
                "club": club,
                "score": round(float(score) * 100, 2),
                "explication": generer_explication(eleve, club, mots_communs),
            })

        resultats.sort(key=lambda x: x["score"], reverse=True)
        return resultats[:top_n]

    # --- Repli : calcul à la volée (aucun entraînement effectué pour l'instant) ---
    clubs = list(Club.objects.filter(statut='actif').exclude(id__in=ids_deja_rejoints))
    if not clubs:
        return []

    textes_clubs = [construire_texte_profil_club(club) for club in clubs]
    corpus = [texte_eleve] + textes_clubs
    vectorizer = TfidfVectorizer(stop_words=None)
    matrice_tfidf = vectorizer.fit_transform(corpus)

    vecteur_eleve = matrice_tfidf[0:1]
    vecteurs_clubs = matrice_tfidf[1:]
    similarites = cosine_similarity(vecteur_eleve, vecteurs_clubs)[0]

    mots_eleve = set(w.lower() for w in texte_eleve.split())
    resultats = []
    for club, score in zip(clubs, similarites):
        texte_club = construire_texte_profil_club(club).lower()
        mots_communs = [mot for mot in mots_eleve if mot in texte_club and len(mot) > 2]
        resultats.append({
            "club": club,
            "score": round(float(score) * 100, 2),
            "explication": generer_explication(eleve, club, mots_communs),
        })

    resultats.sort(key=lambda x: x["score"], reverse=True)
    return resultats[:top_n]


def calculer_recommandations_collaboratives(eleve, top_n=10, k_voisins=5):
    """
    PIPELINE DE PRÉDICTION (collaboratif).
    Utilise le modèle KNN entraîné et persisté si disponible et si l'élève
    faisait partie des données d'entraînement ; sinon, calcule à la volée.
    """
    import joblib
    from django.conf import settings

    chemin_modele = settings.IA_MODELES_DIR / 'knn_modele.pkl'
    chemin_matrice = settings.IA_MODELES_DIR / 'knn_matrice_eleve_club.pkl'

    ids_deja_rejoints = set(clubs_deja_rejoints(eleve))

    if chemin_modele.exists() and chemin_matrice.exists():
        modele = joblib.load(chemin_modele)
        matrice = joblib.load(chemin_matrice)

        if eleve.id in matrice.index:
            index_eleve = matrice.index.get_loc(eleve.id)
            distances, indices_voisins = modele.kneighbors([matrice.iloc[index_eleve].values])

            scores_clubs = {}
            for distance, idx_voisin in zip(distances[0], indices_voisins[0]):
                id_eleve_voisin = matrice.index[idx_voisin]
                if id_eleve_voisin == eleve.id:
                    continue
                similarite = 1 - distance
                clubs_du_voisin = matrice.columns[matrice.iloc[idx_voisin].values == 1]
                for club_id in clubs_du_voisin:
                    if club_id in ids_deja_rejoints:
                        continue
                    scores_clubs[club_id] = scores_clubs.get(club_id, 0) + similarite

            if scores_clubs:
                score_max = max(scores_clubs.values())
                if score_max > 0:
                    return {cid: round((s / score_max) * 100, 2) for cid, s in scores_clubs.items()}
            return {}

    # --- Repli : calcul à la volée (élève absent du dernier entraînement, ou aucun modèle) ---
    matrice = construire_matrice_eleve_club()
    if matrice.empty or eleve.id not in matrice.index:
        return {}

    nb_voisins_possibles = min(k_voisins + 1, len(matrice))
    if nb_voisins_possibles < 2:
        return {}

    modele = NearestNeighbors(n_neighbors=nb_voisins_possibles, metric='cosine')
    modele.fit(matrice.values)

    index_eleve = matrice.index.get_loc(eleve.id)
    distances, indices_voisins = modele.kneighbors([matrice.iloc[index_eleve].values])

    scores_clubs = {}
    for distance, idx_voisin in zip(distances[0], indices_voisins[0]):
        id_eleve_voisin = matrice.index[idx_voisin]
        if id_eleve_voisin == eleve.id:
            continue
        similarite = 1 - distance
        clubs_du_voisin = matrice.columns[matrice.iloc[idx_voisin].values == 1]
        for club_id in clubs_du_voisin:
            if club_id in ids_deja_rejoints:
                continue
            scores_clubs[club_id] = scores_clubs.get(club_id, 0) + similarite

    if not scores_clubs:
        return {}
    score_max = max(scores_clubs.values())
    if score_max > 0:
        scores_clubs = {cid: round((s / score_max) * 100, 2) for cid, s in scores_clubs.items()}
    return scores_clubs




def construire_matrice_eleve_club():
    """
    Construit une matrice (DataFrame pandas) élève × club, où chaque cellule vaut 1
    si l'élève a été inscrit (validée ou en attente) à ce club, sinon 0.
    """
    inscriptions = Inscription.objects.filter(
        statut__in=[Inscription.Statut.VALIDEE, Inscription.Statut.EN_ATTENTE, Inscription.Statut.ARCHIVEE]
    ).values('eleve_id', 'club_id')

    if not inscriptions:
        return pd.DataFrame()

    df = pd.DataFrame(list(inscriptions))
    df['valeur'] = 1
    matrice = df.pivot_table(
        index='eleve_id', columns='club_id', values='valeur', fill_value=0, aggfunc='max'
    )
    return matrice




def calculer_recommandations_hybrides(eleve, top_n=10, poids_profil=0.6, poids_comportement=0.4):
    """
    Combine le content-based filtering (profil) et le collaborative filtering
    (comportement) selon la formule :
    Score Final = 60% Similarité Profil + 40% Similarité Comportement

    Si le collaborative filtering ne renvoie aucun résultat (élève nouveau, peu de
    données), le score repose entièrement sur le content-based filtering.

    Retourne une liste de dicts triée par score décroissant :
    [{"club": Club, "score": float, "explication": str, "score_profil": float,
      "score_comportement": float}, ...]
    """
    resultats_profil = calculer_recommandations_content_based(eleve, top_n=1000)
    scores_profil = {r["club"].id: r["score"] for r in resultats_profil}
    explications = {r["club"].id: r["explication"] for r in resultats_profil}
    clubs_par_id = {r["club"].id: r["club"] for r in resultats_profil}

    scores_comportement = calculer_recommandations_collaboratives(eleve)

    # S'assurer que tous les clubs candidats sont couverts (profil ET/OU comportement)
    tous_ids_clubs = set(scores_profil.keys()) | set(scores_comportement.keys())

    if not tous_ids_clubs:
        return []

    # Récupérer les clubs manquants (présents seulement côté comportement)
    ids_manquants = set(scores_comportement.keys()) - set(clubs_par_id.keys())
    if ids_manquants:
        for club in Club.objects.filter(id__in=ids_manquants):
            clubs_par_id[club.id] = club

    resultats_finaux = []
    a_du_comportement = bool(scores_comportement)

    for club_id in tous_ids_clubs:
        score_p = scores_profil.get(club_id, 0)
        score_c = scores_comportement.get(club_id, 0)

        if a_du_comportement:
            score_final = round(poids_profil * score_p + poids_comportement * score_c, 2)
        else:
            score_final = round(score_p, 2)

        club = clubs_par_id.get(club_id)
        if not club:
            continue

        explication = explications.get(club_id) or generer_explication(eleve, club, [])
        if score_c > 0:
            explication += " Plusieurs élèves ayant un profil similaire au vôtre ont aussi rejoint ce club."

        resultats_finaux.append({
            "club": club,
            "score": score_final,
            "explication": explication,
            "score_profil": score_p,
            "score_comportement": score_c,
        })

    resultats_finaux.sort(key=lambda x: x["score"], reverse=True)
    return resultats_finaux[:top_n]

