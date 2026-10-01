import re
import unicodedata

import joblib
import numpy as np
import pandas as pd
from django.conf import settings
from django.db.models import Count, Q
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.neighbors import NearestNeighbors

from clubs.models import Club
from inscriptions.models import Inscription

# Mots vides français minimaux (sklearn n'en fournit pas pour le français).
MOTS_VIDES = frozenset(
    "le la les un une des du de d l et ou en au aux ce ces cette dans par pour sur avec sans son sa ses "
    "leur leurs qui que quoi dont est sont etre a ont avoir il elle ils elles nous vous je tu on se ne pas "
    "plus tres aussi mais donc car comme entre vers chez club clubs".split()
)


def normaliser(texte):
    """Minuscules, sans accents."""
    texte = unicodedata.normalize('NFKD', texte or '')
    return ''.join(c for c in texte if not unicodedata.combining(c)).lower()


def analyser_texte(texte):
    """Découpage en mots normalisés, sans mots vides ni mots trop courts."""
    return [m for m in re.findall(r'[a-z0-9]+', normaliser(texte)) if len(m) > 2 and m not in MOTS_VIDES]


def nouveau_vectoriseur():
    """Vectoriseur TF-IDF commun à l'entraînement, à la prédiction et au repli à la volée."""
    return TfidfVectorizer(analyzer=analyser_texte, sublinear_tf=True)


_CACHE_MODELES = {}


def charger_modele(chemin):
    """Charge un modèle joblib avec cache invalidé par la date de modification du fichier."""
    mtime = chemin.stat().st_mtime
    entree = _CACHE_MODELES.get(str(chemin))
    if entree and entree[0] == mtime:
        return entree[1]
    objet = joblib.load(chemin)
    _CACHE_MODELES[str(chemin)] = (mtime, objet)
    return objet


def interets_actifs(eleve):
    """Centres d'intérêt actifs de l'élève (liste vide s'il n'en a pas choisi)."""
    return [i for i in eleve.interets.all() if i.actif]


def interets_correspondants(eleve, club):
    """
    Noms des centres d'intérêt de l'élève réellement liés à ce club : même catégorie de club,
    ou mot du nom de l'intérêt présent dans le texte du club.
    """
    mots_club = set(analyser_texte(construire_texte_profil_club(club)))
    noms = []
    for interet in interets_actifs(eleve):
        if (interet.categorie_club and interet.categorie_club == club.categorie) \
                or mots_club & set(analyser_texte(interet.nom)):
            noms.append(interet.nom)
    return noms


def construire_texte_profil_eleve(eleve, inclure_historique=True):
    """
    Texte représentant le profil de l'élève : centres d'intérêt, filière et
    (optionnellement) catégories des clubs déjà rejoints.
    """
    elements = []

    # Centres d'intérêt choisis (signal principal) : leur nom, et la catégorie de club associée,
    # présente dans le texte des clubs. Le texte libre historique reste pris en compte.
    for interet in interets_actifs(eleve):
        elements.append(interet.nom)
        if interet.categorie_club:
            elements.append(interet.categorie_club)

    if eleve.centres_interet:
        elements.append(eleve.centres_interet)

    if eleve.filiere:
        elements.append(eleve.filiere)

    if inclure_historique:
        categories_passees = Inscription.objects.filter(
            eleve=eleve
        ).exclude(
            statut__in=[Inscription.Statut.REFUSEE, Inscription.Statut.ANNULEE]
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


def mots_communs_profil_club(texte_eleve, texte_club):
    """Mots (normalisés) présents à la fois dans le profil de l'élève et dans le texte du club."""
    mots_club = set(analyser_texte(texte_club))
    vus = []
    for mot in analyser_texte(texte_eleve):
        if mot in mots_club and mot not in vus:
            vus.append(mot)
    return vus


def generer_explication(eleve, club, mots_communs):
    """Génère une explication lisible à partir des intérêts et mots-clés réellement communs."""
    interets = interets_correspondants(eleve, club)
    if interets:
        return (
            f"Le club {club.nom} vous est recommandé car il correspond à vos centres d'intérêt : "
            f"{', '.join(interets[:3])}."
        )
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
    Utilise le modèle entraîné et persisté (joblib) s'il est à jour par rapport
    aux clubs actifs ; sinon calcule à la volée (avant le premier entraînement,
    ou si des clubs ont été créés/désactivés depuis).
    """
    texte_eleve = construire_texte_profil_eleve(eleve)
    if not texte_eleve.strip():
        return []

    chemin_vectorizer = settings.IA_MODELES_DIR / 'tfidf_vectorizer.pkl'
    chemin_matrice = settings.IA_MODELES_DIR / 'tfidf_matrice_clubs.pkl'
    chemin_ids = settings.IA_MODELES_DIR / 'tfidf_club_ids.pkl'

    ids_deja_rejoints = set(clubs_deja_rejoints(eleve))
    clubs_actifs = {c.id: c for c in Club.objects.filter(statut=Club.Statut.ACTIF)}

    modele_disponible = chemin_vectorizer.exists() and chemin_matrice.exists() and chemin_ids.exists()
    if modele_disponible:
        club_ids = charger_modele(chemin_ids)
        modele_disponible = set(club_ids) == set(clubs_actifs)  # modèle périmé sinon

    if modele_disponible:
        # --- Utilisation du modèle entraîné ---
        vectorizer = charger_modele(chemin_vectorizer)
        matrice_clubs = charger_modele(chemin_matrice)
        vecteur_eleve = vectorizer.transform([texte_eleve])
        similarites = cosine_similarity(vecteur_eleve, matrice_clubs)[0]
        candidats = list(zip(club_ids, similarites))
    else:
        # --- Repli : calcul à la volée sur les clubs actifs ---
        clubs = [c for c in clubs_actifs.values() if c.id not in ids_deja_rejoints]
        if not clubs:
            return []
        corpus = [texte_eleve] + [construire_texte_profil_club(c) for c in clubs]
        try:
            matrice_tfidf = nouveau_vectoriseur().fit_transform(corpus)
        except ValueError:  # vocabulaire vide
            return []
        similarites = cosine_similarity(matrice_tfidf[0:1], matrice_tfidf[1:])[0]
        candidats = list(zip([c.id for c in clubs], similarites))

    resultats = []
    for club_id, score in candidats:
        club = clubs_actifs.get(club_id)
        if club is None or club_id in ids_deja_rejoints:
            continue
        mots = mots_communs_profil_club(texte_eleve, construire_texte_profil_club(club))
        resultats.append({
            "club": club,
            "score": round(float(score) * 100, 2),
            "explication": generer_explication(eleve, club, mots),
        })

    resultats.sort(key=lambda x: x["score"], reverse=True)
    return resultats[:top_n]


def _scores_par_voisins(matrice, modele, eleve_id, ids_deja_rejoints):
    """Somme des similarités des voisins de l'élève, par club (hors clubs déjà rejoints)."""
    index_eleve = matrice.index.get_loc(eleve_id)
    distances, indices_voisins = modele.kneighbors([matrice.iloc[index_eleve].values])

    scores_clubs = {}
    for distance, idx_voisin in zip(distances[0], indices_voisins[0]):
        if matrice.index[idx_voisin] == eleve_id:
            continue
        similarite = 1 - distance
        for club_id in matrice.columns[matrice.iloc[idx_voisin].values == 1]:
            club_id = int(club_id)
            if club_id in ids_deja_rejoints:
                continue
            scores_clubs[club_id] = scores_clubs.get(club_id, 0) + similarite
    return scores_clubs


def calculer_recommandations_collaboratives(eleve, top_n=10, k_voisins=5):
    """
    PIPELINE DE PRÉDICTION (collaboratif, KNN cosinus sur la matrice élève × club).
    Utilise le modèle persisté si l'élève en faisait partie ; sinon calcule à la volée.
    Ne retourne que des clubs actifs. Retour : {club_id: score 0..100}.
    """
    chemin_modele = settings.IA_MODELES_DIR / 'knn_modele.pkl'
    chemin_matrice = settings.IA_MODELES_DIR / 'knn_matrice_eleve_club.pkl'

    ids_deja_rejoints = set(clubs_deja_rejoints(eleve))
    scores_clubs = None

    if chemin_modele.exists() and chemin_matrice.exists():
        modele = charger_modele(chemin_modele)
        matrice = charger_modele(chemin_matrice)
        if eleve.id in matrice.index:
            scores_clubs = _scores_par_voisins(matrice, modele, eleve.id, ids_deja_rejoints)

    if scores_clubs is None:
        # --- Repli : calcul à la volée (élève absent du dernier entraînement, ou aucun modèle) ---
        matrice = construire_matrice_eleve_club()
        if matrice.empty or eleve.id not in matrice.index:
            return {}
        nb_voisins_possibles = min(k_voisins + 1, len(matrice))
        if nb_voisins_possibles < 2:
            return {}
        modele = NearestNeighbors(n_neighbors=nb_voisins_possibles, metric='cosine')
        modele.fit(matrice.values)
        scores_clubs = _scores_par_voisins(matrice, modele, eleve.id, ids_deja_rejoints)

    if not scores_clubs:
        return {}

    # Seuls les clubs actifs sont recommandables
    ids_actifs = set(
        Club.objects.filter(id__in=scores_clubs.keys(), statut=Club.Statut.ACTIF).values_list('id', flat=True)
    )
    scores_clubs = {cid: s for cid, s in scores_clubs.items() if cid in ids_actifs}
    if not scores_clubs:
        return {}

    score_max = max(scores_clubs.values())
    if score_max <= 0:
        return {}
    return {cid: round((s / score_max) * 100, 2) for cid, s in scores_clubs.items()}


def construire_matrice_eleve_club():
    """
    Matrice élève × club (DataFrame pandas) : 1 si l'élève a été inscrit
    (validée, en attente ou archivée) à ce club, sinon 0.
    """
    inscriptions = Inscription.objects.filter(
        statut__in=[Inscription.Statut.VALIDEE, Inscription.Statut.EN_ATTENTE, Inscription.Statut.ARCHIVEE]
    ).values('eleve_id', 'club_id')

    donnees = list(inscriptions)
    if not donnees:
        return pd.DataFrame()

    df = pd.DataFrame(donnees)
    df['valeur'] = 1
    return df.pivot_table(
        index='eleve_id', columns='club_id', values='valeur', fill_value=0, aggfunc='max'
    )


def recommandations_populaires(eleve, top_n=5):
    """
    Repli « cold start » : clubs actifs les plus populaires (effectif validé),
    hors clubs déjà rejoints. Score = popularité relative (0..100).
    """
    ids_deja_rejoints = set(clubs_deja_rejoints(eleve))
    clubs = list(
        Club.objects.filter(statut=Club.Statut.ACTIF)
        .exclude(id__in=ids_deja_rejoints)
        .annotate(nb=Count('inscriptions', filter=Q(inscriptions__statut=Inscription.Statut.VALIDEE)))
        .order_by('-nb', 'nom')[:top_n]
    )
    if not clubs:
        return []
    maximum = max(c.nb for c in clubs) or 1
    return [
        {
            "club": c,
            "score": round(c.nb / maximum * 100, 2),
            "explication": (
                f"Le club {c.nom} est l'un des plus populaires de l'établissement. "
                "Complétez vos centres d'intérêt pour des recommandations personnalisées."
            ),
            "score_profil": 0,
            "score_comportement": 0,
        }
        for c in clubs
    ]


def calculer_recommandations_hybrides(eleve, top_n=10, poids_profil=0.6, poids_comportement=0.4):
    """
    Combine le content-based filtering (profil) et le collaborative filtering
    (comportement) : Score Final = 60% Similarité Profil + 40% Similarité Comportement.
    Sans signal collaboratif, le score repose sur le profil seul ; sans aucun signal
    (nouvel élève), repli sur les clubs populaires.

    Retourne une liste de dicts triée par score décroissant :
    [{"club": Club, "score": float, "explication": str, "score_profil": float,
      "score_comportement": float}, ...]
    """
    resultats_profil = calculer_recommandations_content_based(eleve, top_n=1000)
    scores_profil = {r["club"].id: r["score"] for r in resultats_profil}
    explications = {r["club"].id: r["explication"] for r in resultats_profil}
    clubs_par_id = {r["club"].id: r["club"] for r in resultats_profil}

    scores_comportement = calculer_recommandations_collaboratives(eleve)

    tous_ids_clubs = set(scores_profil) | set(scores_comportement)
    if not tous_ids_clubs:
        return recommandations_populaires(eleve, top_n=min(top_n, 5))

    ids_manquants = set(scores_comportement) - set(clubs_par_id)
    if ids_manquants:
        for club in Club.objects.filter(id__in=ids_manquants, statut=Club.Statut.ACTIF):
            clubs_par_id[club.id] = club

    resultats_finaux = []
    a_du_comportement = bool(scores_comportement)

    for club_id in tous_ids_clubs:
        club = clubs_par_id.get(club_id)
        if not club:
            continue

        score_p = scores_profil.get(club_id, 0)
        score_c = scores_comportement.get(club_id, 0)

        if a_du_comportement:
            score_final = round(poids_profil * score_p + poids_comportement * score_c, 2)
        else:
            score_final = round(score_p, 2)

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
