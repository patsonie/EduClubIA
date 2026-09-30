from django.conf import settings
from django.views.static import serve

# Seuls ces sous-dossiers sont publics (photos de profil, logos de clubs).
# Justificatifs et pièces jointes du chat passent par des vues authentifiées.
PREFIXES_PUBLICS = ('utilisateurs/photos/', 'clubs/logos/')


def media_publique(request, path):
    from django.http import Http404
    if not path.startswith(PREFIXES_PUBLICS):
        raise Http404("Fichier introuvable.")
    return serve(request, path, document_root=settings.MEDIA_ROOT)
