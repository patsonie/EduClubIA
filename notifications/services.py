from .models import Notification
from django.core.mail import send_mail
from django.conf import settings


def creer_notification(destinataire, type_notification, titre, message):
    """
    Crée une notification interne pour un utilisateur, et envoie un email
    si l'utilisateur a activé ce canal dans ses préférences.
    Respecte les préférences de canal internes existantes.
    """
    preference = getattr(destinataire, 'preference_notification', None)

    notification = None
    if not preference or preference.notifications_internes:
        notification = Notification.objects.create(
            destinataire=destinataire,
            type_notification=type_notification,
            titre=titre,
            message=message,
        )

    if preference and preference.notifications_email and destinataire.email:
        envoyer_email_notification(destinataire, titre, message)

    return notification


def envoyer_email_notification(destinataire, titre, message):
    """Envoie une notification par email. N'échoue jamais bruyamment (fail_silently)."""
    try:
        send_mail(
            subject=f"EduClubIA — {titre}",
            message=(
                f"Bonjour {destinataire.prenom},\n\n"
                f"{message}\n\n"
                f"Connectez-vous à votre espace EduClubIA pour plus de détails.\n"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[destinataire.email],
            fail_silently=True,
        )
    except Exception:
        # Une erreur d'envoi d'email ne doit jamais bloquer la création de la notification
        # interne ni l'action métier qui l'a déclenchée (ex: valider une inscription).
        pass


def notifier_nouvelle_activite(activite):
    """Notifie tous les élèves inscrits (validés) au club concerné par la nouvelle activité."""
    from inscriptions.models import Inscription

    inscriptions = Inscription.objects.filter(club=activite.club, statut=Inscription.Statut.VALIDEE)
    for inscription in inscriptions:
        creer_notification(
            destinataire=inscription.eleve,
            type_notification=Notification.TypeNotification.NOUVELLE_ACTIVITE,
            titre=f"Nouvelle activité : {activite.titre}",
            message=f"Le club {activite.club.nom} organise « {activite.titre} » le {activite.date}.",
        )


def notifier_validation_inscription(inscription):
    creer_notification(
        destinataire=inscription.eleve,
        type_notification=Notification.TypeNotification.VALIDATION_INSCRIPTION,
        titre="Inscription validée",
        message=f"Votre inscription au club {inscription.club.nom} a été validée.",
    )


def notifier_refus_inscription(inscription):
    creer_notification(
        destinataire=inscription.eleve,
        type_notification=Notification.TypeNotification.REFUS_INSCRIPTION,
        titre="Inscription refusée",
        message=f"Votre inscription au club {inscription.club.nom} a été refusée.",
    )
    
def notifier_parents(eleve, type_notification, titre, message):
    """Envoie une notification à tous les parents liés à un élève."""
    for parent in eleve.parents:
        creer_notification(
            destinataire=parent,
            type_notification=type_notification,
            titre=titre,
            message=message,
        )


def notifier_parents_validation_inscription(inscription):
    notifier_parents(
        inscription.eleve,
        Notification.TypeNotification.VALIDATION_INSCRIPTION,
        "Inscription de votre enfant validée",
        f"L'inscription de {inscription.eleve.nom_complet} au club {inscription.club.nom} a été validée.",
    )


def notifier_parents_nouvelle_activite(activite):
    from inscriptions.models import Inscription
    inscriptions = Inscription.objects.filter(club=activite.club, statut=Inscription.Statut.VALIDEE)
    for inscription in inscriptions:
        notifier_parents(
            inscription.eleve,
            Notification.TypeNotification.NOUVELLE_ACTIVITE,
            "Nouvelle activité pour votre enfant",
            f"Le club {activite.club.nom} organise « {activite.titre} » le {activite.date} "
            f"pour {inscription.eleve.nom_complet}.",
        )


def notifier_parents_absence(participation):
    if participation.statut not in ['absent', 'excuse']:
        return
    eleve = participation.inscription.eleve
    notifier_parents(
        eleve,
        Notification.TypeNotification.AUTRE,
        "Absence enregistrée",
        f"{eleve.nom_complet} a été marqué(e) absent(e) à l'activité « {participation.activite.titre} ».",
    )