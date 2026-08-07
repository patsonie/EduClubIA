from django.db import models


class AnneeScolaire(models.Model):
    """
    Représente une année scolaire (ex: 2025-2026).
    Une seule année peut être "active" à la fois.
    """

    libelle = models.CharField(max_length=20, unique=True, help_text="Ex: 2025-2026")
    date_debut = models.DateField()
    date_fin = models.DateField()
    est_active = models.BooleanField(default=False)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Année scolaire"
        verbose_name_plural = "Années scolaires"
        ordering = ['-date_debut']

    def __str__(self):
        return self.libelle

    def save(self, *args, **kwargs):
        # Si cette année est marquée comme active, désactive toutes les autres.
        if self.est_active:
            AnneeScolaire.objects.exclude(pk=self.pk).update(est_active=False)
        super().save(*args, **kwargs)