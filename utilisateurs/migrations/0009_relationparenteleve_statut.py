from django.db import migrations, models


class Migration(migrations.Migration):
    """Les liens existants restent 'validee' (défaut) ; les nouvelles demandes de parents sont 'en_attente'."""

    dependencies = [
        ('utilisateurs', '0008_utilisateur_date_expiration_code_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='relationparenteleve',
            name='statut',
            field=models.CharField(
                choices=[('en_attente', 'En attente de validation'), ('validee', 'Validée')],
                default='validee',
                max_length=15,
            ),
        ),
    ]
