# EduClubIA — guide pour Claude

Plateforme Django 6 / DRF / SimpleJWT / Channels de gestion des clubs scolaires (Cameroun). Rôles : `administrateur`, `proviseur` (responsable pédagogique), `encadreur`, `eleve`, `parent`. Données de mineurs : la confidentialité passe avant tout. Détails d'architecture, variables d'environnement et IA : lire `README.md` (ne pas le relire en entier sans besoin).

## Commandes (environnement conda `clubs_lycee`)

```bash
PY=/c/Users/BD/miniconda3/envs/clubs_lycee/python.exe
export PYTHONDONTWRITEBYTECODE=1 DATABASE_URL="sqlite:///$TEMP/test.sqlite3"   # évite MySQL local
$PY manage.py check
$PY manage.py makemigrations --check --dry-run
$PY manage.py test --noinput                    # ~10 s (hachage MD5 en mode test)
$PY manage.py test config.tests_securite        # tests transverses de sécurité
```

- Le `venv/` du dépôt est cassé : ne pas l'utiliser.
- Lancer les commandes lentes (imports numpy/sklearn) avec `run_in_background`, puis lire le fichier de sortie. Ne pas boucler avec `sleep`.
- Ne jamais installer/supprimer de dépendance ni lancer `migrate` sur la vraie base sans demande explicite.

## Où regarder (éviter de tout lire)

| Sujet | Fichiers |
|---|---|
| Périmètre des droits (qui gère quel club) | `utilisateurs/perimetre.py` (`clubs_geres`, `peut_gerer_club`) |
| JWT / statut du compte / révocation | `utilisateurs/authentication.py`, `utilisateurs/securite.py` (anti brute-force) |
| Comptes, parents, rattachements, matricules | `utilisateurs/views.py`, `serializers.py`, `matricules.py` |
| Messagerie / WebSocket | `messagerie/permissions.py` (règle d'accès unique), `consumers.py`, `tickets.py`, `middleware.py` |
| Centres d'intérêt (profil, inscription, signal IA) | `utilisateurs/models.py` (`CentreInteret`, `Utilisateur.interets`), `services.py` des recommandations (`interets_actifs`), `static/js/interets.js`, tests `config/tests_interets.py` |
| IA recommandations / prédictions | `recommandations/services.py`, `ml_pipeline.py`, `analytics/ml_pipeline.py` |
| Config, déploiement | `config/settings.py`, `render.yaml`, `build.sh` |
| Tests transverses | `config/tests_securite.py` (classe de base `BaseDonnees`) |

## Règles du projet

- **Contrôle d'accès** : toute nouvelle vue doit limiter son queryset au périmètre de l'utilisateur (élève : lui-même ; parent : enfants dont le lien est `validee` via `user.enfants` ; encadreur : `clubs_geres`). Ne jamais faire confiance à un `*_id` reçu sans le vérifier. Ajouter un test dans `config/tests_securite.py`.
- **Rôles** : seul l'administrateur modifie rôle, email ou statut d'un compte. Le proviseur ne touche ni aux administrateurs ni aux autres proviseurs.
- **Parent → enfant** : le lien n'existe qu'une fois validé par un gestionnaire (`RelationParentEleve.statut`). Ne pas réintroduire de rattachement automatique par matricule.
- **Fichiers** : seuls `utilisateurs/photos/` et `clubs/logos/` sont publics. Justificatifs et pièces jointes passent par des vues authentifiées ; ne jamais renvoyer une URL de stockage brute.
- **Pagination** : optionnelle (`?page=`), le front attend des listes brutes sans ce paramètre.
- **Migrations** : générer avec `makemigrations` et vérifier `--check` ; ne pas les écrire à la main.
- **Fins de ligne** : les fichiers du dépôt sont en CRLF côté disque (autocrlf). Utiliser Edit/Write, pas de réécriture globale par script qui changerait tout le diff.
- **Textes et commentaires en français**, noms de code métier en français (style existant).
- Ne pas modifier `.env` (jamais suivi par git, contient des secrets).

## Workflow attendu

1. Lire uniquement les fichiers concernés (Grep d'abord), pas l'arborescence entière.
2. Modifier, puis `check` + tests ciblés ; suite complète avant de proposer un commit.
3. Commit/push uniquement sur demande explicite de l'utilisateur ; message en français, avec l'attribution demandée par le harness.
4. Résumer en peu de mots : ce qui change, ce qui est vérifié, ce qui ne l'est pas.
