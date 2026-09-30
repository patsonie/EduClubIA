from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('annees_scolaires', '0001_initial'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='anneescolaire',
            constraint=models.UniqueConstraint(
                condition=models.Q(('est_active', True)),
                fields=('est_active',),
                name='une_seule_annee_active',
            ),
        ),
    ]
