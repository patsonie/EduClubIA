import os
from django.core.exceptions import ValidationError

# Signatures (« magic bytes ») attendues par extension : évite un exécutable renommé en .pdf.
SIGNATURES = {
    '.pdf': [b'%PDF'],
    '.jpg': [b'\xff\xd8\xff'],
    '.jpeg': [b'\xff\xd8\xff'],
    '.png': [b'\x89PNG\r\n\x1a\n'],
    '.webp': [b'RIFF'],
    '.doc': [b'\xd0\xcf\x11\xe0'],
    '.docx': [b'PK\x03\x04'],
}


def valider_contenu_fichier(fichier):
    """Vérifie que le début du fichier correspond à son extension."""
    extension = os.path.splitext(fichier.name)[1].lower()
    signatures = SIGNATURES.get(extension)
    if not signatures:
        return
    try:
        position = fichier.tell()
    except (AttributeError, OSError):
        position = None
    debut = fichier.read(16)
    if position is not None:
        fichier.seek(position)
    else:
        fichier.seek(0)
    if not any(debut.startswith(sig) for sig in signatures):
        raise ValidationError("Le contenu du fichier ne correspond pas à son extension.")

EXTENSIONS_JUSTIFICATIF_AUTORISEES = ['.pdf', '.jpg', '.jpeg', '.png', '.doc', '.docx']
EXTENSIONS_PHOTO_AUTORISEES = ['.jpg', '.jpeg', '.png', '.webp']
TAILLE_MAX_FICHIER_MO = 5
EXTENSIONS_MESSAGE_AUTORISEES = ['.pdf', '.jpg', '.jpeg', '.png', '.doc', '.docx']


def valider_extension_justificatif(fichier):
    extension = os.path.splitext(fichier.name)[1].lower()
    if extension not in EXTENSIONS_JUSTIFICATIF_AUTORISEES:
        raise ValidationError(
            f"Format non autorisé. Formats acceptés : {', '.join(EXTENSIONS_JUSTIFICATIF_AUTORISEES)}."
        )
    valider_contenu_fichier(fichier)


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


def valider_fichier_message(fichier):
    """Accepte uniquement des pièces jointes usuelles, de taille maîtrisée."""
    extension = os.path.splitext(fichier.name)[1].lower()
    if extension not in EXTENSIONS_MESSAGE_AUTORISEES:
        raise ValidationError(
            f"Format non autorisé. Formats acceptés : {', '.join(EXTENSIONS_MESSAGE_AUTORISEES)}."
        )
    valider_taille_fichier(fichier)
    valider_contenu_fichier(fichier)
