import os
from django.core.exceptions import ValidationError

EXTENSIONS_JUSTIFICATIF_AUTORISEES = ['.pdf', '.jpg', '.jpeg', '.png', '.doc', '.docx']
EXTENSIONS_PHOTO_AUTORISEES = ['.jpg', '.jpeg', '.png', '.webp']
TAILLE_MAX_FICHIER_MO = 5


def valider_extension_justificatif(fichier):
    extension = os.path.splitext(fichier.name)[1].lower()
    if extension not in EXTENSIONS_JUSTIFICATIF_AUTORISEES:
        raise ValidationError(
            f"Format non autorisé. Formats acceptés : {', '.join(EXTENSIONS_JUSTIFICATIF_AUTORISEES)}."
        )


def valider_extension_photo(fichier):
    extension = os.path.splitext(fichier.name)[1].lower()
    if extension not in EXTENSIONS_PHOTO_AUTORISEES:
        raise ValidationError(
            f"Format d'image non autorisé. Formats acceptés : {', '.join(EXTENSIONS_PHOTO_AUTORISEES)}."
        )


def valider_taille_fichier(fichier):
    limite_octets = TAILLE_MAX_FICHIER_MO * 1024 * 1024
    if fichier.size > limite_octets:
        raise ValidationError(f"Le fichier ne doit pas dépasser {TAILLE_MAX_FICHIER_MO} Mo.")