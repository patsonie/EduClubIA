"""Liste officielle des matricules : vérification à l'inscription et import CSV."""
import csv
import io
import re
import unicodedata

from django.db import transaction

from .models import MatriculeOfficiel

# Message volontairement identique pour « matricule inconnu » et « mauvaise identité »
# (ne révèle pas si un matricule existe).
MESSAGE_NON_RECONNU = (
    "Ce matricule et cette identité ne correspondent à aucune entrée de la liste officielle "
    "de l'établissement. Vérifiez la saisie ou contactez l'administration."
)


def _jetons(texte):
    """Mots en minuscules sans accents : « Éric-Jean » -> {'eric', 'jean'}."""
    texte = unicodedata.normalize('NFKD', texte or '')
    texte = ''.join(c for c in texte if not unicodedata.combining(c)).lower()
    return set(re.findall(r'[a-z0-9]+', texte))


def _compatibles(a, b):
    """Deux ensembles de mots sont compatibles si l'un contient l'autre (prénoms composés)."""
    return bool(a) and bool(b) and (a <= b or b <= a)


# Compare nom/prénom saisis et officiels, en tolérant accents, casse et inversion nom/prénom.
def identite_correspond(entree, nom, prenom):
    n, p = _jetons(nom), _jetons(prenom)
    en, ep = _jetons(entree.nom), _jetons(entree.prenom)
    droit = _compatibles(n, en) and _compatibles(p, ep)
    inverse = _compatibles(n, ep) and _compatibles(p, en)  # nom/prénom permutés à la saisie
    return droit or inverse


def liste_active(role):
    """La vérification s'applique dès qu'au moins une entrée existe pour ce rôle."""
    return MatriculeOfficiel.objects.filter(role=role).exists()


def trouver_entree_officielle(role, matricule, nom, prenom):
    """
    Retourne l'entrée officielle correspondante, None si aucune liste n'est importée pour ce rôle
    (vérification désactivée), ou lève ValueError(message) si le matricule/l'identité sont inconnus.
    """
    if not liste_active(role):
        return None
    entree = MatriculeOfficiel.objects.filter(role=role, matricule__iexact=(matricule or '').strip()).first()
    if not entree or not identite_correspond(entree, nom, prenom):
        raise ValueError(MESSAGE_NON_RECONNU)
    return entree


def importer_csv(contenu, role):
    """
    Importe (ajoute ou met à jour) des matricules depuis un CSV.
    Colonnes : matricule, nom, prenom, classe (facultative) ; séparateur « , » ou « ; ».
    Retourne {"crees", "mis_a_jour", "erreurs": [...]}.
    """
    # Lecture du fichier : encodage UTF-8 (avec ou sans BOM), détection automatique du séparateur.
    texte = contenu.decode('utf-8-sig') if isinstance(contenu, bytes) else contenu
    try:
        dialecte = csv.Sniffer().sniff(texte[:2048], delimiters=',;\t')
    except csv.Error:
        dialecte = csv.excel
    lecteur = csv.DictReader(io.StringIO(texte), dialect=dialecte)
    if not lecteur.fieldnames:
        raise ValueError("Fichier vide.")
    # Vérifie la présence des colonnes obligatoires (insensible à la casse).
    colonnes = {(c or '').strip().lower(): c for c in lecteur.fieldnames}
    for requise in ('matricule', 'nom', 'prenom'):
        if requise not in colonnes:
            raise ValueError(f"Colonne « {requise} » manquante (colonnes attendues : matricule, nom, prenom, classe).")

    crees = mis_a_jour = 0
    erreurs = []
    vus = set()
    # Tout l'import est fait dans une transaction : en cas d'erreur grave, rien n'est enregistré.
    with transaction.atomic():
        for numero, ligne in enumerate(lecteur, start=2):
            matricule = (ligne.get(colonnes['matricule']) or '').strip()
            nom = (ligne.get(colonnes['nom']) or '').strip()
            prenom = (ligne.get(colonnes['prenom']) or '').strip()
            classe = (ligne.get(colonnes.get('classe', '')) or '').strip() if 'classe' in colonnes else ''

            # Contrôles ligne par ligne : les lignes invalides sont signalées et ignorées.
            if not (matricule and nom and prenom):
                erreurs.append(f"Ligne {numero} : matricule, nom et prénom sont obligatoires.")
                continue
            if len(matricule) > 30 or len(nom) > 100 or len(prenom) > 100 or len(classe) > 20:
                erreurs.append(f"Ligne {numero} : valeur trop longue.")
                continue
            if matricule.lower() in vus:
                erreurs.append(f"Ligne {numero} : matricule {matricule} en double dans le fichier.")
                continue
            vus.add(matricule.lower())

            # Matricule déjà connu → mise à jour ; sinon → création.
            entree = MatriculeOfficiel.objects.filter(matricule__iexact=matricule).first()
            if entree:
                entree.role, entree.nom, entree.prenom, entree.classe = role, nom, prenom, classe or None
                entree.save()
                mis_a_jour += 1
            else:
                MatriculeOfficiel.objects.create(
                    matricule=matricule, role=role, nom=nom, prenom=prenom, classe=classe or None
                )
                crees += 1
    return {"crees": crees, "mis_a_jour": mis_a_jour, "erreurs": erreurs}
