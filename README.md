# EduClubIA

Plateforme de gestion des clubs et activités extrascolaires pour les établissements secondaires du Cameroun
(Django 6, Django REST Framework, SimpleJWT, Channels/WebSocket, scikit-learn).

## Rôles

| Rôle | Accès principal |
|---|---|
| Administrateur | Tout : comptes, clubs, années scolaires, IA, rapports |
| Responsable pédagogique (`proviseur`) | Clubs, activités, inscriptions, comptes élèves/encadreurs/parents (suspension), rapports. **Ne peut pas** modifier ni suspendre un administrateur ou un autre responsable |
| Encadreur | Uniquement **ses clubs** : inscriptions, activités, présences, salons de discussion, prédictions |
| Élève | Ses propres données, ses clubs, recommandations |
| Parent | Uniquement les enfants dont le rattachement a été **validé** par un gestionnaire |

### Rattachement parent → enfant
À l'inscription, le parent peut indiquer le matricule de son enfant : cela crée une **demande**
(`RelationParentEleve.statut = en_attente`). Un gestionnaire la consulte
(`GET /api/auth/parents/demandes_rattachement/`) puis la valide
(`POST /api/auth/parents/{id}/lier_enfant/` avec `{"enfant": <id>}`). Tant qu'elle n'est pas validée,
le parent n'a accès à aucune donnée de l'élève.

### Liste officielle des matricules
Pour empêcher qu'un élève (ou encadreur professionnel) s'inscrive avec le matricule d'un autre, importer la liste
fournie par l'établissement (CSV `matricule,nom,prenom,classe` ; séparateur `,` ou `;`) :

```bash
python manage.py importer_matricules eleves.csv --role eleve
python manage.py importer_matricules encadreurs.csv --role encadreur
```

ou via l'API : `POST /api/auth/matricules/importer/` (administrateur, multipart `fichier` + `role`),
consultation `GET /api/auth/matricules/` (administrateur / responsable pédagogique) ou l'admin Django.

**Dès qu'une liste existe pour un rôle**, l'inscription publique de ce rôle n'est acceptée que si le matricule figure dans la
liste **et** que le nom et le prénom correspondent (insensible à la casse et aux accents, prénoms composés tolérés). Le message
d'erreur est identique pour un matricule inconnu et pour une identité incorrecte. Tant qu'aucune liste n'est importée, l'inscription
reste libre : **importer la liste avant d'ouvrir les inscriptions**. L'orthographe officielle du matricule et la classe sont
reprises automatiquement dans le compte.

## Installation (développement)

```bash
conda activate clubs_lycee            # ou tout environnement Python 3.13
pip install -r requirements.txt
cp .env.example .env                  # puis compléter (voir ci-dessous)
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver            # Daphne sert HTTP + WebSocket
python manage.py test
```

Les tests peuvent tourner sans MySQL : `DATABASE_URL=sqlite:///db.sqlite3 python manage.py test`.

## Variables d'environnement

| Variable | Rôle |
|---|---|
| `SECRET_KEY` | Obligatoire |
| `DEBUG` | `False` par défaut |
| `DATABASE_URL` | PostgreSQL en production. Sinon `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` (MySQL local) |
| `ALLOWED_HOSTS`, `RENDER_EXTERNAL_HOSTNAME` | Hôtes autorisés ; sur Render, alimente aussi CORS, `FRONTEND_BASE_URL` et `NUM_PROXIES` |
| `FRONTEND_BASE_URL` | Base des liens envoyés par email (déduite de Render, sinon `http://127.0.0.1:8000`) |
| `NUM_PROXIES` | Nombre de proxys de confiance devant l'application (1 sur Render) : nécessaire au throttling par IP |
| `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL` | Emails (console par défaut : rien n'est réellement envoyé) |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `ADMIN_NOM`, `ADMIN_PRENOM` | Création de l'administrateur initial (`bootstrap_admin`) |
| `MEDIA_ROOT` | Dossier des fichiers envoyés (disque persistant sur Render) |
| `AWS_STORAGE_BUCKET_NAME` (+ `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_S3_ENDPOINT_URL`, `AWS_S3_REGION_NAME`) | Stockage objet S3 (optionnel) |
| `IA_MODELES_DIR` | Dossier des modèles ML persistés |
| `REDIS_URL` | Couche de canaux Redis (obligatoire dès qu'il y a plusieurs instances) |

## Déploiement Render

Le fichier `render.yaml` décrit le service web (Daphne), la base PostgreSQL et les variables.
`build.sh` installe, collecte les fichiers statiques, migre et crée l'administrateur.

- **Fichiers** : le disque de Render est éphémère. Utiliser le disque persistant du blueprint
  (`MEDIA_ROOT=/var/data/media`) ou un stockage S3. Seuls `utilisateurs/photos/` et `clubs/logos/` sont
  publics ; justificatifs et pièces jointes du chat sont servis par des vues authentifiées.
- **WebSocket** : `InMemoryChannelLayer` suffit pour **une seule instance**. Définir `REDIS_URL` avant d'en lancer plusieurs.
- **Modèles IA** : stockés dans `IA_MODELES_DIR` ; s'ils sont absents ou périmés, le calcul se fait à la volée.
  Réentraînement : `python manage.py reentrainer_modeles_ia --type hebdomadaire` (à planifier avec un Cron Job Render) ou via l'API admin.

## Architecture

```
config/          settings, urls, asgi (HTTP + WebSocket), pagination optionnelle, tests transverses
utilisateurs/    utilisateur personnalisé, rôles, JWT (statut vérifié), parents, comptes en attente
clubs/ activites/ inscriptions/ participations/ annees_scolaires/   métier
notifications/   notifications internes (+ email selon préférences)
messagerie/      salons (club, activité, privé), WebSocket, pièces jointes protégées
recommandations/ recommandation de clubs (IA)
analytics/       prédictions et indicateurs (IA + règles), rapports PDF
```

Points de conception :
- **Périmètre par objet** : `utilisateurs/perimetre.py` (`clubs_geres`, `peut_gerer_club`) — un encadreur n'agit que sur ses clubs.
- **JWT** : access 2 h, refresh 7 j avec rotation + blacklist ; `JWTAuthenticationStatutValide` refuse les comptes non « valide » ;
  suspension/refus révoquent les refresh tokens ; changement de mot de passe invalide les jetons.
- **Pagination** : à la demande (`?page=1&page_size=50`) ; sans paramètre, la liste complète est renvoyée (compatibilité front).

## Intelligence artificielle — ce qui existe réellement

### 1. Recommandation de clubs (`recommandations/`) — système de recommandation
- **Content-based** : TF-IDF (mots normalisés, sans accents ni mots vides) sur `catégorie + description + objectifs` des clubs,
  similarité cosinus avec le profil de l'élève (centres d'intérêt, filière, catégories des clubs déjà rejoints).
- **Collaboratif** : matrice élève × club binaire, KNN (cosinus, 5 voisins).
- **Hybride** : `0,6 × profil + 0,4 × comportement` (poids fixés a priori, non optimisés). Sans signal comportemental : profil seul ;
  sans aucun signal (nouvel élève) : repli sur les clubs actifs les plus populaires (*cold start*).
- Seuls les clubs **actifs** sont recommandés ; un modèle persisté périmé (clubs créés/désactivés) est ignoré au profit d'un calcul à la volée.
- **Validation** (à l'entraînement, sans fuite de données) : leave-one-out (le club masqué est retiré de la matrice avant l'ajustement),
  hit rate@3, précision@3, rappel@3, couverture du catalogue, comparés à une baseline de popularité.
  Sur de petits effectifs (< 5 élèves éligibles) la validation est déclarée non significative.

### 2. Analytics (`analytics/`) — système prédictif et indicateurs
- **Prédiction du nombre de participants** (*vrai modèle prédictif*) : régression linéaire par club sur le rang chronologique des
  activités terminées (minimum 3). Métriques : MAE, RMSE, R² sur un découpage chronologique 75/25, comparées à la baseline « moyenne ».
  Limites : séries courtes, aucune information sur la date/le type d'activité — c'est une extrapolation de tendance.
- **Risque de désengagement** et **clubs en difficulté** : indicateurs **à base de règles** (taux de présence global/récent, baisse relative
  entre deux fenêtres d'activités). Ce ne sont **pas** des modèles de machine learning : aucune variable cible, aucun apprentissage.

### Différence recommandation / prédiction
Une **recommandation** classe des éléments (clubs) pour un utilisateur et se juge sur la pertinence du classement (hit rate, précision@k).
Une **prédiction** estime une valeur cible mesurable (nombre de présents) et se juge sur l'erreur (MAE, RMSE, R²).

## Sécurité — points d'attention
- Les seuls comptes pouvant modifier rôles, e-mails ou statuts sont les **administrateurs**.
- Les mots de passe sont soumis aux validateurs Django (mots de passe courants, numériques).
- Uploads : extension, taille (5 Mo) **et signature du contenu** vérifiées.
- WebSocket : origine vérifiée, droits revérifiés à chaque message, limitation de débit par connexion. Le jeton est transmis dans l'URL
  (limite des WebSocket navigateur) : éviter de journaliser les URLs de la couche proxy.
- `.env` n'est jamais versionné.

## Limites connues / pistes
- Les emails sont envoyés de façon synchrone (file de tâches à prévoir pour de gros effectifs).
- Pas d'écran de validation des rattachements parent → enfant (API et admin Django uniquement).
- Pas de multi-établissement : un responsable pédagogique voit tous les élèves de l'instance.
