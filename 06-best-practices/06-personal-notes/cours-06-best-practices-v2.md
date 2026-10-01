# Module 06 — Best Practices : comprendre et suivre le chapitre (v2)

> Sources : [DataTalksClub/mlops-zoomcamp › 06-best-practices](https://github.com/DataTalksClub/mlops-zoomcamp/tree/main/06-best-practices) · ton fork [Janua29/mlops-zoomcamp › 06-best-practices](https://github.com/Janua29/mlops-zoomcamp/tree/main/06-best-practices) (le dossier `code/` est identique à l'original).
> Contexte : tout tourne dans ton **Codespace** (VS Code desktop sur le Mac, connecté à la machine Linux distante).
> État au 27/09/2026. Ce qui a été **testé** pour écrire ce cours : installation `pipenv` des dépendances, tests unitaires, isort/black/pylint, hooks pre-commit, chargement du modèle MLflow. **Non testé** : les images Docker (Lambda, LocalStack) et toute la partie AWS/Terraform — voir §9.
> **v2 (28/09/2026)** : ajout du §3.0 (notions de base : serveur, port, HTTP, Lambda, Kinesis, callback, RIE), de la définition du flux `ride_predictions` (§5.3) et d'un récit pas à pas après chaque schéma du §5. Cours compagnon : `cours-06-model-et-lambda-function.md` (le code de `model.py` et `lambda_function.py` en détail).
> Les commentaires `# …` ajoutés dans les extraits de fichiers sont des **annotations de cours** : ne recopie pas les extraits, modifie les fichiers d'origine.

---

## 0. Faut-il un nouvel environnement ? Oui.

Ne réutilise pas ton environnement conda `mlopszoomcamp`. Trois raisons :

1. **Le code exige Python 3.9.** `Pipfile` impose `python_version = "3.9"` et `scikit-learn==1.0.2`, une version publiée pour Python 3.7 à 3.10 seulement (aucun paquet précompilé au-delà).
2. **Le modèle de test a été sauvegardé avec scikit-learn 1.0.2** (`integration-test/model/MLmodel`). Un modèle *picklé* (sérialisé) se recharge de façon fiable seulement avec la même version de la bibliothèque.
3. **Le module est construit autour de `pipenv`** (présenté au §3.1) : le `Makefile`, `integration-test/run.sh`, le `Dockerfile` et la CI l'utilisent. Le devoir (homework 2025) a d'ailleurs **son propre** `Pipfile` (Python 3.10, scikit-learn 1.5.0) : un environnement par projet, c'est exactement la logique de pipenv.

En deux mots : `Pipfile` liste les packages voulus, `Pipfile.lock` fige leurs versions exactes (détails §6.1) ; `--dev` ajoute les outils de développement (tests, qualité : §4).

**Recette (testée)** — conda fournit seulement l'interpréteur Python 3.9, pipenv gère les packages :

```bash
# 1. Un Python 3.9 + pipenv
conda create -n mlops-06 python=3.9 -y
conda activate mlops-06
pip install "pipenv==2023.12.1"

# 2. Les dépendances du module, lues dans Pipfile.lock
cd 06-best-practices/code
pipenv install --dev --python "$(which python)"   # --python : utiliser CE Python 3.9 (celui de conda)

# 3. Entrer dans l'environnement pipenv
pipenv shell
```

**Dans chaque nouveau terminal** (l'installation, elle, n'est à faire qu'une fois) :

```bash
conda activate mlops-06 && cd 06-best-practices/code && pipenv shell
```

`pipenv shell` ouvre un shell *dans* l'environnement (on y reste) ; `pipenv run <commande>` exécute une seule commande dedans (c'est ce que fait `run.sh`).

> **Pourquoi `pipenv==2023.12.1` et pas la dernière version ?** Le `Pipfile.lock` fige `mlflow==1.27.0`, dont les métadonnées ne respectent plus les règles de `pip ≥ 24.1`. Les pipenv récents embarquent leur propre pip récent → `ERROR: No matching distribution found for mlflow==1.27.0`. Vérifié : pipenv 2025.0.4 échoue, 2023.12.1 (qui embarque un pip plus ancien) fonctionne.
>
> **Et pourquoi ne pas mettre mlflow à jour (`pipenv lock`) ?** Tu changerais toutes les versions testées par le cours, et le modèle picklé avec scikit-learn 1.0.2 risquerait de ne plus se recharger. Garde le lock tel quel.

- `pipenv --venv` affiche où vit l'environnement (par défaut `~/.local/share/virtualenvs/code-xxxx`). Dans VS Code : *Python: Select Interpreter* → ce chemin.
- **Ne mets pas** `PIPENV_VENV_IN_PROJECT=1` : le `.venv` serait créé dans `code/`, et `pylint --recursive=y .` se mettrait à analyser toutes les bibliothèques installées (constaté : blocage de plus de 5 minutes).

### 0.1 Conda et pipenv : qui fait quoi ?

Ni imbriqués, ni indépendants : les deux environnements sont **dans des dossiers séparés**, mais celui de pipenv **dépend** de celui de conda.

```
/opt/conda/envs/mlops-06/                 ← environnement conda
├── bin/python3.9                         ← l'interpréteur Python 3.9 (le « moteur »)
├── bin/pipenv                            ← l'outil pipenv (installé avec pip install pipenv)
└── lib/python3.9/                        ← la bibliothèque standard (os, json…)

~/.local/share/virtualenvs/code-xxxx/     ← environnement pipenv (un autre dossier)
├── pyvenv.cfg                            ← « home = /opt/conda/envs/mlops-06/bin »
├── bin/python  →  lien vers le python3.9 de conda
└── lib/python3.9/site-packages/          ← SES packages : mlflow, boto3, pytest…
```

(Le chemin exact de l'environnement conda peut différer dans ton Codespace : `conda env list` l'affiche.)

- **Les packages sont séparés.** mlflow, pytest… sont dans le dossier de pipenv. L'environnement pipenv ne voit pas les packages de conda, et inversement.
- **L'interpréteur est partagé.** Un environnement virtuel ne contient pas de Python complet : son `bin/python` est un lien vers le Python 3.9 de conda, et la bibliothèque standard vient aussi de conda. Si tu supprimes l'environnement conda, celui de pipenv ne fonctionne plus.

En résumé : **conda fournit l'interpréteur, pipenv fournit les packages.**

**Pourquoi activer conda d'abord ?** Activer un environnement, c'est placer son dossier `bin/` en tête du `PATH`, la liste des dossiers où le terminal cherche les commandes que tu tapes. On active conda pour deux raisons :

1. **À la création** : `pipenv install --python "$(which python)"` doit trouver le Python 3.9. `which python` ne renvoie celui de conda que si conda est activé.
2. **Chaque jour** : la commande `pipenv` elle-même est installée dans `mlops-06/bin/`. Sans conda activé, le terminal ne la trouve pas (`command not found`), ou en trouve une autre version, trop récente.

Une fois l'environnement pipenv créé, conda n'a donc pas besoin d'être activé pour *exécuter* ton code (le lien vers Python 3.9 est un chemin absolu) : il l'est pour que la commande `pipenv` soit disponible.

Quand les deux sont actifs, le `PATH` ressemble à ceci :

```
PATH = …/virtualenvs/code-xxxx/bin : /opt/conda/envs/mlops-06/bin : …
         ↑ cherché en premier : python, pytest, pylint…   ↑ ensuite : pipenv
```

**Pour le vérifier toi-même :**

```bash
conda activate mlops-06 && cd 06-best-practices/code && pipenv shell
which python pipenv                       # python → virtualenvs/… ; pipenv → conda
cat "$(pipenv --venv)/pyvenv.cfg"         # la ligne home = pointe vers conda
ls -l "$(pipenv --venv)/bin/python"       # le lien vers le python3.9 de conda
```

---

## 1. Vue d'ensemble

### 1.1 Le but

Jusqu'ici, le cours a produit un modèle qui marche (modules 1-4) et un moyen de le surveiller (module 5). Le module 6 répond à une autre question : **comment modifier ce code sans le casser, et le déployer de façon reproductible ?**

On reprend le **service de prédiction en streaming du module 4** (une fonction AWS Lambda qui lit des courses dans un flux Kinesis et écrit des prédictions de durée dans un autre flux ; ces notions sont expliquées au §3.0) et on l'entoure de « bonnes pratiques » d'ingénierie logicielle.

### 1.2 La progression : deux blocs

```
BLOC A — tout en local, gratuit (vidéos 6.1 → 6.6, et le devoir)
  6.1 pytest ............ tester les fonctions Python une par une
  6.2 docker-compose .... tester le conteneur complet via HTTP
  6.3 LocalStack ........ simuler Kinesis (AWS) en local
  6.4 isort/black/pylint  formater et analyser le code
  6.5 pre-commit ........ lancer ces contrôles automatiquement à chaque commit
  6.6 make .............. donner un nom court à chaque commande

BLOC B — sur AWS, payant, compte AWS requis (vidéos 6.7 → 6.13)
  6.7-6.10 Terraform .... créer l'infrastructure AWS à partir de fichiers texte
  6.11-6.13 CI/CD ....... GitHub Actions : tester et déployer automatiquement
```

Chaque étape attrape une catégorie d'erreurs que la précédente ne voit pas :

| Contrôle | Ce qu'il attrape | Coût |
|---|---|---|
| Test unitaire | Une fonction renvoie un mauvais résultat | < 1 s |
| Test d'intégration | L'image Docker ne démarre pas, une dépendance manque, l'API répond mal | ~1 min |
| LocalStack | L'appel à Kinesis est mal formé | ~1 min |
| Lint / format | Code illisible, import inutile, variable jamais utilisée | < 5 s |
| Test de bout en bout (cloud) | Permissions AWS, configuration réelle | minutes + € |

### 1.3 Structure du dossier `code/`

```
code/
├── model.py                 ← LA logique métier : décoder, préparer, prédire, publier
├── lambda_function.py       ← le point d'entrée appelé par AWS Lambda (~20 lignes)
├── tests/
│   ├── __init__.py          ← fait de tests/ un package Python (vide)
│   ├── model_test.py        ← tests unitaires (pytest)
│   └── data.b64             ← un événement de course encodé en base64
├── integration-test/
│   ├── docker-compose.yaml  ← démarre 2 conteneurs : le service + LocalStack
│   ├── run.sh               ← orchestre tout le test d'intégration
│   ├── event.json           ← un faux événement Kinesis, tel que Lambda le reçoit
│   ├── test_docker.py       ← appelle le service en HTTP, vérifie la prédiction
│   ├── test_kinesis.py      ← lit le flux de sortie, vérifie le message publié
│   └── model/               ← un vrai modèle MLflow (DictVectorizer + RandomForest)
├── Dockerfile               ← l'image du service (base : image Lambda Python 3.9)
├── Pipfile / Pipfile.lock   ← dépendances (déclarées / figées)
├── pyproject.toml           ← configuration de black, isort, pylint
├── .pre-commit-config.yaml  ← hooks git
├── Makefile                 ← raccourcis : make test, make build...
├── .vscode/settings.json    ← réglages VS Code pour pytest
├── infrastructure/          ← BLOC B : Terraform
│   ├── main.tf, variables.tf
│   ├── vars/stg.tfvars, vars/prod.tfvars
│   └── modules/{kinesis,s3,ecr,lambda}/
├── scripts/                 ← BLOC B : déploiement et test cloud
└── plan.md, README.md       ← notes de l'auteur
```

Les workflows CI/CD ne sont pas dans `code/` : GitHub exige qu'ils soient à la racine du dépôt, dans `.github/workflows/` (ils existent dans ton fork).

---

## 2. Le service à tester : `model.py` et `lambda_function.py`

On ne peut rien tester sans comprendre ce qu'on teste. Ce code est le résultat d'un **refactoring** : le code du module 4 a été découpé pour séparer la **logique** (testable sans rien) de l'**infrastructure** (Kinesis, S3, qui nécessitent un réseau).

### 2.1 Le chemin d'une course

```
Événement Kinesis (JSON)            model.py
{"Records": [                       ─────────────────────────────────────────────
  {"kinesis": {"data": "ewog..."}}  1. base64_decode(data)   → {"ride": {...}, "ride_id": 256}
]}                                  2. prepare_features(ride) → {"PU_DO": "130_205", "trip_distance": 3.66}
                                    3. predict(features)      → 21.3
                                    4. callbacks → KinesisCallback.put_record → flux de sortie
                                    5. return {"predictions": [...]}
```

**Pourquoi du base64 ?** Kinesis transporte des octets bruts. Quand il les livre à Lambda dans un JSON, il les encode en base64 (du texte ASCII qui représente n'importe quels octets). `base64_decode` fait l'inverse, puis `json.loads` retrouve le dictionnaire.

### 2.2 Les pièces de `model.py`

| Élément | Rôle |
|---|---|
| `get_model_location(run_id)` | Si la variable d'environnement `MODEL_LOCATION` existe → l'utiliser (tests locaux). Sinon construire `s3://{MODEL_BUCKET}/{MLFLOW_EXPERIMENT_ID}/{run_id}/artifacts/model` (le rangement des artefacts MLflow du module 2). |
| `load_model(run_id)` | `mlflow.pyfunc.load_model(chemin)` : charge un modèle MLflow, depuis un dossier local ou S3. |
| `ModelService` | La classe centrale. Reçoit le modèle **en paramètre** → dans les tests, on peut lui passer un faux modèle. |
| `callbacks` | Un **callback** est une fonction qu'on *donne* à un objet pour qu'il l'appelle plus tard. Ici : une liste de fonctions appelées pour chaque prédiction. En prod : publier dans Kinesis. En test : liste vide → rien n'est publié, sans toucher au reste du code. |
| `KinesisCallback` | Enveloppe le client Kinesis : `put_record(StreamName, Data, PartitionKey)`. |
| `create_kinesis_client()` | Si `KINESIS_ENDPOINT_URL` existe → client pointé vers cette adresse (LocalStack). Sinon → vrai AWS. |
| `init(...)` | Assemble le tout. Si `test_run` est vrai, aucun callback : rien n'est publié. |

Le principe utilisé s'appelle **injection de dépendances** : au lieu que `ModelService` crée lui-même son modèle et son client Kinesis, on les lui *donne*. On peut alors lui donner des faux.

Le `return {"predictions": [...]}` de `ModelService.lambda_handler` : en production, personne ne le lit (le résultat utile part dans Kinesis via le callback). Il sert aux tests, qui peuvent vérifier ce que la fonction renvoie.

### 2.3 `lambda_function.py`

```python
PREDICTIONS_STREAM_NAME = os.getenv('PREDICTIONS_STREAM_NAME', 'ride_predictions')
RUN_ID = os.getenv('RUN_ID')
TEST_RUN = os.getenv('TEST_RUN', 'False') == 'True'

model_service = model.init(...)          # exécuté UNE fois, au démarrage du conteneur

def lambda_handler(event, context):      # exécuté à CHAQUE invocation
    return model_service.lambda_handler(event)
```

- Deux fonctions portent le même nom : `lambda_function.lambda_handler` est le **handler** (la fonction qu'AWS Lambda appelle, avec `event` = les données reçues) ; il ne fait que **déléguer** à `ModelService.lambda_handler`, qui contient la logique.
- Toute la configuration vient des **variables d'environnement** : le même code tourne en test, en staging et en prod, seules les variables changent.
- `TEST_RUN` : `os.getenv` renvoie une chaîne ; `== 'True'` la transforme en booléen.
- Le code au niveau du module (hors fonction) tourne au **démarrage à froid** (*cold start*) du conteneur Lambda. Charger le modèle là, et non dans le handler, évite de le recharger à chaque course.
- `context` est imposé par Lambda mais inutilisé → `# pylint: disable=unused-argument`, placé seul sur une ligne dans la fonction, fait taire ce message pour **toute la fonction**. (En fin d'une ligne de code, il ne vaudrait que pour cette ligne.)

---

## 3. Les outils et services

### 3.0 Les notions de base : serveur, port, HTTP, Lambda, Kinesis, callback, RIE

Tout le module repose sur des programmes qui **s'envoient des messages**. Avant les outils, le vocabulaire.

#### Serveur, client, port

- Un **serveur** est un programme qui **attend** des demandes et **y répond**. Un **client** est un programme qui envoie une demande. (Le mot « serveur » désigne parfois aussi la *machine* qui fait tourner ces programmes : ici, on parle du programme.)
- Un **port** est un numéro (de 0 à 65535) qui distingue les serveurs d'une même machine. L'adresse complète d'un serveur est donc `machine:port`, par exemple `localhost:8080` (`localhost` = « la machine où je suis »).
- Analogie : la machine est un bâtiment, chaque serveur est un guichet, le port est le numéro du guichet.

#### Protocole et HTTP

Un **protocole** est la **langue** que parlent le client et le serveur. **HTTP** est la plus répandue. Une conversation HTTP est toujours un aller-retour : une **requête**, puis une **réponse**.

| Partie | Requête (client → serveur) | Réponse (serveur → client) |
|---|---|---|
| Première ligne | Une **méthode** et un **chemin** : `GET /page` (« donne-moi »), `POST /…` (« voici des données, traite-les ») | Un **code de statut** : `200 OK`, `404 Not Found`, `500 Internal Server Error` |
| En-têtes | Informations annexes, ex. `Content-Type: application/json` | Idem |
| Corps | Les données envoyées (souvent du JSON) — facultatif | Les données renvoyées |

Exemple du module : ce que `test_docker.py` envoie, et la réponse attendue (reconstituée à partir du code et du modèle, le conteneur n'ayant pas été lancé pour écrire ce cours, §9).

```
POST /2015-03-31/functions/function/invocations HTTP/1.1     ← méthode + chemin (imposé par l'API Lambda ;
                                                                2015-03-31 = version de cette API)
Host: localhost:8080                                         ← à quel serveur
Content-Type: application/json                               ← le corps est du JSON

{"Records": [{"kinesis": {"data": "ewogICAg..."}}]}          ← corps : la course (event.json)
```

```
HTTP/1.1 200 OK                                              ← « tout s'est bien passé »

{"predictions": [{"model": "ride_duration_prediction_model", "version": "Test123",
                  "prediction": {"ride_duration": 21.29, "ride_id": 256}}]}
```

**HTTPS** = HTTP **chiffré**, sur le port 443 par défaut. Les outils AWS (AWS CLI, `boto3`, Terraform) parlent aux API d'AWS en HTTPS par défaut.

**base64** : une façon d'écrire n'importe quels octets avec seulement des lettres, des chiffres, `+` et `/`. Le JSON ne transporte que du texte ; quand Kinesis livre un message dans un JSON (à Lambda, ou dans `event.json`), il l'écrit donc en base64. C'est pourquoi `ewogICAg...` est illisible et doit être **décodé**.

#### Les serveurs que tu as déjà utilisés

| Serveur | Port | Protocole | Qui lui parle, et pour quoi faire |
|---|---|---|---|
| MLflow (`mlflow ui` / `mlflow server`, modules 2-4) | 5000 | HTTP | Ton navigateur, pour afficher l'interface. Avec un *tracking server*, ton code Python aussi : `mlflow.set_tracking_uri("http://…:5000")`, puis chaque `log_metric` est une requête HTTP. (Avec `set_tracking_uri("sqlite:///mlflow.db")`, pas de HTTP : Python écrit directement dans le fichier de base de données.) |
| Prefect (module 3) | 4200 | HTTP | Navigateur (interface) et tes flows, qui y déclarent leurs exécutions (si `PREFECT_API_URL` pointe vers ce serveur) |
| Grafana (module 5) | 3000 | HTTP | Ton navigateur |
| Adminer (module 5) | 8080 | HTTP | Ton navigateur |
| Evidently UI (module 5) | 8000 | HTTP | Ton navigateur |
| **PostgreSQL** (module 5) | 5432 | **PostgreSQL** (pas HTTP) | Tes scripts Python (`psycopg`), **Grafana** et Adminer, pour lire et écrire les métriques |
| RIE (module 6) | 8080 | HTTP | `test_docker.py` |
| LocalStack (module 6) | 4566 | HTTP | L'AWS CLI, `boto3` |
| API AWS (module 6, bloc B) | 443 | HTTPS | L'AWS CLI, `boto3`, Terraform (présentés au §3.1 et au §4) |

Grafana illustre bien la différence : il est **serveur HTTP** pour ton navigateur, et en même temps **client PostgreSQL** pour aller chercher les données qu'il affiche.

**Presque tous les serveurs sont-ils HTTP ?** Beaucoup, oui : tous ceux qui ont une interface web ou une API web. HTTP est simple, compris par tous les navigateurs, disponible dans tous les langages, et laissé passer par presque tous les pare-feux. Mais pas tous : les bases de données (PostgreSQL 5432, MySQL 3306, Redis 6379), la connexion à distance (SSH, port 22) ou l'envoi d'e-mails (SMTP, port 25) ont leur propre protocole, souvent plus rapide ou mieux adapté (connexion qui reste ouverte, transactions).

#### Lambda, Kinesis et callback, en bref

Ces trois notions sont détaillées dans le cours compagnon `cours-06-model-et-lambda-function.md` (§2, §3 et §6). L'essentiel :

- **AWS Lambda** : un service AWS qui **exécute ta fonction Python à ta place**, chaque fois qu'un événement arrive. Tu ne lances jamais le programme : AWS appelle `lambda_handler(event, context)`, où `event` contient les données reçues et `context` des informations sur l'exécution (temps restant…), inutilisées ici.
- **Kinesis** : un **tapis roulant de messages**, identifié par un nom. Un programme y dépose des messages (`put_record`), un autre les récupère (`get_records`), sans se connaître.
- **Callback** : une fonction qu'on **confie** à un objet pour qu'il l'**appelle plus tard**. Ici, on donne à `ModelService` la fonction « publier dans Kinesis » ; il l'appelle après chaque prédiction, sans savoir ce qu'elle fait.

#### Le RIE : jouer le rôle d'AWS Lambda en local

Sur ton Codespace, il n'y a pas d'AWS pour appeler `lambda_handler`. Le **RIE** (*Runtime Interface Emulator*), inclus dans l'image Docker officielle de Lambda, comble ce vide : c'est un **petit serveur HTTP**, qui attend sur le port 8080 et joue le rôle du service Lambda. Il travaille en duo avec le **client d'exécution Python** de l'image (le programme qui, dans une vraie Lambda aussi, fait le lien entre AWS et ton code) : le RIE reçoit la requête HTTP, le client d'exécution appelle ta fonction.

```
test_docker.py ──① POST, corps = event.json────► RIE (port 8080)
                                                   │ ② transmet l'événement au client d'exécution Python,
                                                   │   qui appelle lambda_handler(event, context)
                                                   ▼
                                                 ton code calcule, puis return {...}
test_docker.py ◄──④ réponse HTTP = ce JSON─────── RIE ◄──③ valeur renvoyée
```

1. `test_docker.py` envoie un `POST` dont le corps est l'événement (`event.json`).
2. Le RIE transmet l'événement au client d'exécution Python, qui le transforme en dictionnaire et appelle `lambda_handler(event, context)`, exactement comme dans une vraie Lambda. (Dans la suite du cours, « le RIE appelle `lambda_handler` » résume ce duo.)
3. Ton code calcule la prédiction et renvoie un dictionnaire.
4. Le client d'exécution rend ce résultat au RIE, qui le renvoie, en JSON, dans la réponse HTTP.

### 3.1 Bloc A (local)

| Outil | C'est quoi | Rôle ici |
|---|---|---|
| **pytest** | Framework de tests Python. Trouve les fichiers `*_test.py` / `test_*.py`, exécute les fonctions `test_*`, signale chaque `assert` faux. | Tests unitaires de `model.py`. |
| **Docker** | Emballe une application et tout son environnement dans une **image** ; une image lancée = un **conteneur**. | Construire l'image du service. |
| **Image Lambda + RIE** | `public.ecr.aws/lambda/python:3.9` est l'image de base officielle d'AWS Lambda. Elle contient le **Runtime Interface Emulator** (RIE) : un petit serveur HTTP (port 8080) qui joue le rôle d'AWS Lambda (§3.0). | Invoquer la Lambda en local avec un simple `POST`. |
| **docker-compose** | Démarre plusieurs conteneurs décrits dans un fichier YAML, sur un réseau commun. | Service + LocalStack ensemble. |
| **LocalStack** | Un faux AWS dans un conteneur : mêmes API que Kinesis, S3…, sur `localhost:4566`. | Tester la publication Kinesis sans compte AWS. |
| **AWS CLI** (`aws`) | Un **programme** installé dans le Codespace (pas le cloud AWS lui-même) : il envoie des requêtes HTTPS à l'API d'AWS et affiche la réponse. `--endpoint-url` le redirige vers LocalStack (en HTTP). | Créer le flux de test. |
| **isort** | Trie les imports. | Qualité. |
| **black** | Reformate le code selon un style unique, non négociable. | Qualité. |
| **pylint** | **Linter** : lit le code sans l'exécuter et signale erreurs et mauvaises pratiques (import inutilisé, nom de variable non conforme…). Note sur 10. | Qualité. |
| **pre-commit** | Installe des **hooks git** : des scripts exécutés automatiquement avant chaque `git commit`. Si un hook échoue, le commit est refusé. | Lancer isort/black/pylint/pytest à chaque commit. |
| **make** | Outil ancien (1976) qui exécute des « cibles » décrites dans un `Makefile`, avec leurs dépendances. | `make build` = contrôles + tests + build. |
| **pipenv** | Gestionnaire d'environnements et de dépendances : `Pipfile` (ce que tu veux) + `Pipfile.lock` (versions exactes installées, avec empreintes). | Environnement du module. |

### 3.2 Bloc B (AWS)

| Service | C'est quoi | Rôle ici |
|---|---|---|
| **Kinesis Data Streams** | Un « tapis roulant » de messages. Un **flux** (*stream*) est découpé en **shards** (voies parallèles). Chaque message (*record*) a des données + une **clé de partition** qui choisit sa voie. Les messages restent disponibles pendant la **rétention** (ici 48 h). | `ride_events` (entrée) et `ride_predictions` (sortie). |
| **Lambda** | Exécute du code **sans serveur à gérer** : AWS lance la fonction quand un événement arrive, et facture à l'usage. | Le service de prédiction. |
| **Event source mapping** | Un lien géré par Lambda qui **interroge** (*poll*) Kinesis et invoque la fonction avec des lots de messages. | Brancher `ride_events` sur la Lambda. |
| **S3** | Stockage d'objets (fichiers) dans des **buckets**. | Artefacts MLflow du modèle ; état Terraform. |
| **ECR** | Registre d'images Docker privé d'AWS. | Stocker l'image que Lambda exécute. |
| **IAM** | Gestion des droits. Un **rôle** est endossé par un service (ici la Lambda) ; des **policies** listent ce que ce rôle peut faire. | Droits de la Lambda sur Kinesis, S3, logs. |
| **ARN** | *Amazon Resource Name* : l'identifiant unique d'une ressource AWS, ex. `arn:aws:kinesis:eu-west-1:123456789012:stream/stg_ride_events-mlops-zoomcamp`. | Désigner une ressource dans les droits IAM et entre modules Terraform. |
| **CloudWatch Logs** | Journaux des services AWS. | Voir les `print` et erreurs de la Lambda. |
| **X-Ray** | Service de suivi (*tracing*) du parcours d'une requête entre services. | Activé sur la Lambda, facultatif ici. |
| **Terraform** | Outil d'**Infrastructure as Code** : tu décris l'infrastructure voulue en fichiers `.tf`, Terraform calcule les différences avec l'existant (`plan`) puis les applique (`apply`). | Créer/détruire tout le bloc B. |
| **GitHub Actions** | Service de CI/CD de GitHub : des **workflows** YAML exécutés sur des machines GitHub (*runners*) en réaction à un événement (PR, push). | `ci-tests.yml`, `cd-deploy.yml`. |

**Staging / production** : deux copies de la même infrastructure. *Staging* (`stg`) sert à tester en conditions réelles ; *prod* sert les vrais utilisateurs. Même code Terraform, fichiers de variables différents (`vars/stg.tfvars`, `vars/prod.tfvars`).

---

## 4. Packages Python nouveaux par rapport au module 5

Module 5 : `prefect, tqdm, requests, joblib, pyarrow, psycopg, evidently, pandas, numpy, scikit-learn, jupyter, matplotlib`. Nouveaux ici :

| Package | Version figée (lock) | Groupe | À quoi il sert |
|---|---|---|---|
| `boto3` | 1.24.21 | prod | Le **SDK AWS pour Python** (*Software Development Kit* : la bibliothèque officielle pour piloter AWS depuis du code) : `boto3.client('kinesis')` crée un client qui envoie les requêtes à l'API Kinesis. Lit identifiants et région dans les variables d'environnement `AWS_*` ou `~/.aws/`. |
| `mlflow` | 1.27.0 | prod | Déjà vu aux modules 2-4. Ici seulement `mlflow.pyfunc.load_model` : charge n'importe quel modèle MLflow derrière une interface unique `.predict()`. |
| `scikit-learn` | **1.0.2** (épinglé) | prod | Doit correspondre à la version qui a sauvegardé `model.pkl`. |
| `pytest` | 7.1.2 | dev | Tests (§3.1). |
| `deepdiff` | 5.8.1 | dev | Compare deux structures imbriquées (dict, listes) et décrit **les différences**. `significant_digits=1` : `21.29` et `21.3` sont jugés égaux. Plus utile qu'un `==` qui répond seulement vrai/faux. |
| `pylint` | 2.14.4 | dev | Linter. |
| `black` | 22.6.0 | dev | Formateur. |
| `isort` | 5.10.1 | dev | Tri des imports. |
| `pre-commit` | 2.19.0 | dev | Hooks git. |

**prod vs dev** : `[packages]` = nécessaire pour faire tourner le service (va dans l'image Docker). `[dev-packages]` = nécessaire seulement pour développer (tests, qualité). `pipenv install --dev` installe les deux ; le `Dockerfile` n'installe que les premiers.

`requests` (utilisé par `test_docker.py`) n'est pas déclaré : il arrive comme dépendance de `mlflow`.

---

## 5. Architecture IT

**Comment lire les schémas.** Chaque schéma est suivi d'un **récit pas à pas** : qui envoie quoi à qui, sur quelle adresse, qui calcule, et ce qui revient. Les notions de serveur, port et requête HTTP sont au §3.0.

| Symbole | Sens |
|---|---|
| `A ──► B` | A **agit** sur B : A envoie une requête à B, ou lance B. La flèche part toujours de celui qui demande. |
| `A ◄── B` | Ce que B **renvoie** à A (une réponse). |
| Texte près d'une flèche | L'adresse visée (`localhost:8080`) ou l'action (`interroge`, `put_record`). |
| `═══` | Un dossier **partagé** entre le Codespace et un conteneur (un *volume*), pas un échange réseau. |
| ①②③… | Les étapes du récit qui suit le schéma. |

### 5.1 Vue physique : qui tourne où

```
┌───────────── TON MAC ─────────────┐
│ VS Code desktop (affichage)       │
│ navigateur (optionnel)            │
└────────────────┬──────────────────┘
                 │ tunnel via GitHub (HTTPS) + redirection de ports
┌────────────────▼────── CODESPACE (Linux, chez GitHub) ──────────┐
│ terminal : Python (pipenv), pytest, aws CLI, make, terraform    │
│                                                                 │
│ Docker Engine                                                   │
│   ┌──────────────────────┐    ┌──────────────────────────────┐  │
│   │ backend        :8080 │    │ kinesis (LocalStack)   :4566 │  │
│   └──────────────────────┘    └──────────────────────────────┘  │
└────────────────┬────────────────────────────────────────────────┘
                 │ bloc B uniquement : HTTPS, port 443
┌────────────────▼────── AWS, région eu-west-1 ────────────────────┐
│ Kinesis · Lambda · S3 · ECR · IAM · CloudWatch                   │
└──────────────────────────────────────────────────────────────────┘
```

**Récit.**

1. **Ton Mac n'exécute rien du module.** VS Code desktop n'y fait que de l'affichage : ce que tu tapes part vers le Codespace, ce que le Codespace affiche revient vers ton écran. Ces échanges passent par un **tunnel chiffré** (HTTPS) géré par GitHub.
2. **Le Codespace exécute tout** : le terminal, Python, pytest, le programme `aws`, make, Terraform, et **Docker Engine**, le logiciel qui fait tourner les conteneurs. Les deux conteneurs du test d'intégration (`backend` et `kinesis`) vivent donc **dans** le Codespace.
3. **AWS n'est contacté qu'au bloc B**, depuis le Codespace (Terraform, `aws`) : des requêtes HTTPS, port 443, vers les serveurs d'Amazon en Irlande (`eu-west-1`).
4. **Redirection de ports** (facultatif) : si tu ouvres `localhost:8080` dans le navigateur de ton Mac, VS Code transporte la requête par le tunnel jusqu'au port 8080 du Codespace (onglet *Ports* de VS Code).

Retiens : **`localhost` dans ton terminal = le Codespace**, pas ton Mac. Pour les tests du module, tu n'as pas besoin de la redirection : tout se passe dans le Codespace.

### 5.2 Niveau 1 — tests unitaires : aucun réseau

```
pytest ──► tests/model_test.py ──► import model ──► ModelService(ModelMock(10.0))
                                                    (pas de Docker, pas d'AWS, pas de fichier modèle)
```

**Récit.** `pytest` est un **seul programme Python** qui tourne dans le Codespace. Il importe `model.py`, fabrique un `ModelService` avec le faux modèle `ModelMock(10.0)`, et appelle ses méthodes **directement, en mémoire**. Pas de serveur, pas de requête, pas de conteneur, pas de fichier modèle : c'est pourquoi ces tests prennent moins d'une seconde.

### 5.3 Niveau 2 — test d'intégration (`run.sh`)

Deux « mondes réseau » coexistent :

- **le Codespace** (hôte), où tournent `run.sh`, le programme `aws`, `test_docker.py` et `test_kinesis.py` ;
- **le réseau Docker** créé par docker-compose (`integration-test_default`), où les conteneurs se trouvent **par leur nom de service** (`backend`, `kinesis`) grâce au DNS interne de Docker (un annuaire qui traduit un nom en adresse).

En production (§5.4), il y a **deux** flux Kinesis : `ride_events` (les courses qui arrivent) et `ride_predictions` (les prédictions qui repartent). En local, seul le second existe ; le premier est remplacé par `test_docker.py` (explication en fin de section).

> **`aws` n'est pas le cloud AWS.** Ici, `aws` est le nom d'un **programme** : l'AWS CLI (*Command Line Interface*), installé dans le Codespace (§7.1). Il se contente d'envoyer des requêtes HTTP à une API et d'afficher la réponse, comme un navigateur envoie des requêtes à un site. Sans option, il vise les serveurs d'Amazon de la région configurée (ex. `https://kinesis.eu-west-1.amazonaws.com`). Avec `--endpoint-url=http://localhost:4566`, il vise LocalStack : aucun octet ne part chez Amazon. `boto3` fonctionne pareil en Python (`endpoint_url`).

Les **ports publiés**, écrits `"port hôte:port conteneur"` (`"8080:8080"`, `"4566:4566"`), font le pont entre les deux mondes : une requête envoyée à `localhost:8080` depuis le Codespace est transmise au port 8080 du conteneur `backend`.

```
 CODESPACE (hôte)                     │  RÉSEAU DOCKER « integration-test_default »
                                      │
 ① docker-compose up -d ──────────────┼──► démarre backend + kinesis
                                      │
 ./model (dossier) ═══ volume ════════┼════════════════════════╗
                                      │   ┌─ backend ──────────▼────────────────┐
 ③ test_docker.py                     │   │ RIE :8080 → lambda_handler          │
   POST localhost:8080/2015-03-31/…  ─┼──►│   3.3 charge le modèle (/app/model) │
   ◄── réponse : la prédiction ───────┼───│   3.4 prédit                        │
                                      │   │   3.5 put_record → kinesis:4566 ─┐  │
                                      │   └──────────────────────────────────┼──┘
                                      │   ┌─ kinesis (LocalStack) ───────────▼──┐
 ② aws kinesis create-stream         ─┼──►│ :4566   flux « ride_predictions »   │
   (→ localhost:4566)                 │   │                                     │
 ④ test_kinesis.py get_records       ─┼──►│                                     │
   (→ localhost:4566)                 │   └─────────────────────────────────────┘
```

#### Récit pas à pas

Seuls deux conteneurs tournent : `backend` (ton service de prédiction) et `kinesis` (LocalStack, le faux AWS).

**Étape 1 — `docker-compose up -d` : démarrer**

- Docker démarre les deux conteneurs sur le réseau privé `integration-test_default`.
- Dans `backend`, le RIE se met à **attendre** sur le port 8080. Le dossier `integration-test/model/` du dépôt (un modèle MLflow déjà entraîné, fourni avec le cours : `MLmodel`, `model.pkl`…) y apparaît sous `/app/model` : c'est le **volume**.
- Le conteneur reçoit aussi ses **variables d'environnement** : des paires nom=valeur, écrites dans `docker-compose.yaml` (§6.7), que le code lit avec `os.getenv`. Ce sont elles qui adaptent le code au test :

  | Variable | Valeur | Effet dans le code |
  |---|---|---|
  | `PREDICTIONS_STREAM_NAME` | `ride_predictions` | Nom du flux où publier |
  | `MODEL_LOCATION` | `/app/model` | Charger le modèle depuis ce dossier, pas depuis S3 |
  | `KINESIS_ENDPOINT_URL` | `http://kinesis:4566/` | Publier vers LocalStack, pas vers le vrai AWS |
  | `RUN_ID` | `Test123` | Étiquette « version » recopiée dans chaque prédiction |
  | `TEST_RUN` | *(absente → faux)* | Vrai couperait la publication ; faux → on publie, c'est ce qu'on veut tester |

- Dans `kinesis`, LocalStack attend sur le port 4566.
- Rien n'est encore calculé.

**Étape 2 — `aws kinesis create-stream` : préparer la boîte aux lettres**

- Le programme `aws` (dans le Codespace) envoie une requête HTTP à `localhost:4566` ; Docker la transmet à LocalStack.
- LocalStack crée un flux **vide** nommé `ride_predictions`, avec 1 **shard** (une file indépendante ; plusieurs shards = plus de débit), et répond « OK ». Ce flux recevra les prédictions à l'étape 3.

**Étape 3 — `test_docker.py` : envoyer une course, recevoir une prédiction (le cœur du test)**

1. Le script lit `event.json` : une course (ride_id 256, zones 130 → 205, 3,66 miles), encodée en base64 comme Kinesis la livrerait.
2. Il envoie cet événement en `POST` à `localhost:8080/2015-03-31/functions/function/invocations`. Docker transmet au conteneur `backend`, où le RIE reçoit la requête.
3. C'est la première requête : le RIE charge ton code. `lambda_function.py` appelle `model.init()`, qui :
   - charge le modèle depuis `/app/model` (parce que `MODEL_LOCATION=/app/model`) ;
   - crée un client Kinesis qui visera `http://kinesis:4566` (parce que `KINESIS_ENDPOINT_URL` est défini) ;
   - enregistre le callback « publier dans Kinesis » (parce que `TEST_RUN` n'est pas défini, donc faux).
4. Le RIE appelle `lambda_handler(event)`. **C'est le seul endroit du test où l'on calcule** :
   - décoder le base64 → `{"ride": {...}, "ride_id": 256}` ;
   - calculer les features → `{"PU_DO": "130_205", "trip_distance": 3.66}` ;
   - le modèle prédit **21,29 minutes** ;
   - construire le message `{model, version: "Test123", prediction: {ride_duration: 21.29, ride_id: 256}}`.
5. Le callback publie ce message : `backend` envoie une requête HTTP à `kinesis:4566` (le nom de l'autre conteneur sur le réseau Docker). LocalStack range le message dans le flux `ride_predictions`.
6. `lambda_handler` **renvoie** aussi le message ; le RIE le renvoie comme **réponse HTTP** à `test_docker.py`.
7. Le script compare la réponse à la valeur attendue (21,3, à une décimale près). Différente → il s'arrête en erreur, et `run.sh` affiche les logs puis arrête tout.

**Étape 4 — `test_kinesis.py` : vérifier que la publication a eu lieu**

- Le script demande à `localhost:4566` (LocalStack) : « donne-moi le plus ancien message du flux `ride_predictions` ». Techniquement, en deux requêtes : `get_shard_iterator` obtient un **marque-page** (*iterator*) placé au début du shard (`TRIM_HORIZON`), puis `get_records` lit à partir de ce marque-page.
- Il reçoit le message déposé à l'étape 3.5 et vérifie son contenu.
- L'étape 3 prouvait que le **calcul** marche ; celle-ci prouve que la **publication** marche.

**Étape 5 — `docker-compose down` : nettoyer**

- Les deux conteneurs sont arrêtés et supprimés ; le flux disparaît avec LocalStack.

#### Qui fait quoi

| Acteur | Où | Calcule ? | Rôle joué |
|---|---|---|---|
| `test_docker.py` | Codespace | Non | L'**arrivée d'une course** (remplace le flux d'entrée `ride_events` + le mécanisme AWS qui le lit), puis le contrôle de la réponse |
| RIE | conteneur `backend` | Non | **AWS Lambda** : traduit requête HTTP ⇄ appel de fonction |
| Ton code (`model.py`) | conteneur `backend` | **Oui** | Décoder, prédire, publier |
| LocalStack | conteneur `kinesis` | Non | **Kinesis** : stocke le message |
| `test_kinesis.py` | Codespace | Non | L'**application qui lit les prédictions**, puis le contrôle du message |

#### Les échanges, en tableau

| # | Qui (machine) | → Qui (machine) | Adresse utilisée | Sens / contenu |
|---|---|---|---|---|
| ② | Programme `aws` (Codespace) | LocalStack (conteneur `kinesis`) | `http://localhost:4566` | Crée le flux `ride_predictions` |
| ③ | `test_docker.py` (Codespace) | RIE (conteneur `backend`) | `http://localhost:8080/2015-03-31/functions/function/invocations` | Envoie `event.json`, reçoit les prédictions |
| — | `backend` | son propre disque | `/app/model` (volume monté depuis `./model`) | Charge le modèle MLflow |
| — | `backend` | `kinesis` | `http://kinesis:4566/` (nom de service Docker) | Publie la prédiction |
| ④ | `test_kinesis.py` (Codespace) | `kinesis` | `http://localhost:4566` | Relit le flux, vérifie le message |

Pourquoi deux adresses pour le même LocalStack ? Depuis l'hôte, on passe par le port publié (`localhost:4566`). Depuis un autre conteneur, `localhost` désignerait le conteneur lui-même : il faut le nom du service (`kinesis`) **et le port interne** du conteneur. Ici les deux ports sont identiques ; si on avait publié `"5000:4566"`, l'hôte utiliserait `localhost:5000`, mais `backend` garderait `kinesis:4566`. La publication de port ne concerne que l'hôte.

#### Où est défini le flux `ride_predictions` ?

Il est **créé par `integration-test/run.sh`**, en deux temps :

```bash
16  export PREDICTIONS_STREAM_NAME="ride_predictions"      # choisir le nom
...
22  aws --endpoint-url=http://localhost:4566 \
23      kinesis create-stream \                            # « crée un flux »
24      --stream-name ${PREDICTIONS_STREAM_NAME} \         # nommé ride_predictions
25      --shard-count 1                                    # avec 1 voie (shard)
```

C'est **toute** sa définition. Un flux Kinesis n'est qu'un **nom + un nombre de voies** (+ une durée de conservation des messages, 24 h par défaut) : ni colonnes, ni schéma (contrairement à une table PostgreSQL du module 5). Il transporte des octets quelconques. Le **format** des messages est une **convention entre programmes** :

- celui qui écrit : `model.py` l. 66-70 construit le dictionnaire `prediction_event` ;
- celui qui lit : `test_kinesis.py` attend exactement ce dictionnaire (`expected_record`).

Le **même nom** doit apparaître à trois endroits, tous alimentés par la ligne 16 de `run.sh` :

| Où | Rôle |
|---|---|
| `run.sh` l. 24 | Créer le flux |
| `docker-compose.yaml` l. 7 → `lambda_function.py` l. 5 | Dire au service où publier |
| `test_kinesis.py` l. 13 | Dire au test où lire (même valeur par défaut) |

Sur AWS (bloc B), c'est Terraform qui crée le flux (module `output_kinesis_stream`), sous le nom `stg_ride_predictions-mlops-zoomcamp`. Le préfixe `stg_` = *staging* : la copie d'essai de l'infrastructure, que tu déploies à la main ; `prod_` = la version réelle, déployée par la CD (§5.5). Mêmes fichiers Terraform, variables différentes (`vars/stg.tfvars`, `vars/prod.tfvars`).

**Et le flux d'entrée `ride_events` ?** En local, **il n'existe pas** : `test_docker.py` envoie la course directement au RIE, et remplace à lui seul le flux d'entrée et le mécanisme AWS qui le lit.

> **Conflit de ports possible** : au module 5, `adminer` publiait aussi le port **8080**. Si ce docker-compose tourne encore : `docker ps`, puis `docker compose down` dans `05-monitoring/`.

### 5.4 Niveau 3 — l'architecture cloud (bloc B)

```
 CODESPACE                               │ AWS eu-west-1
                                         │
 ① aws kinesis put-record ──HTTPS ───────┼──► ┌───────────────────────────┐
   (test_cloud_e2e.sh)                   │    │ Kinesis (entrée)          │
                                         │    │ stg_ride_events-…         │
                                         │    └─────────────▲─────────────┘
                                         │                  │ ② interroge (≈ 1 fois/s)
                                         │    ┌─────────────┴─────────────┐
                                         │    │ event source mapping      │
                                         │    │ (mécanisme du service     │
                                         │    │ Lambda)                   │
                                         │    └─────────────┬─────────────┘
                                         │                  │ ③ appelle avec un lot
                                         │    ┌─────────────▼─────────────┐
                                         │    │ Lambda (ton code)         │ ── ④ lit le modèle ──► S3 (bucket stg-mlflow-…)
                                         │    │ ⑤ calcule la prédiction   │
                                         │    │ image : copie venue d'ECR │
                                         │    │ droits : rôle IAM         │ ── ⑦ logs ──► CloudWatch Logs
                                         │    └─────────────┬─────────────┘
                                         │                  │ ⑥ put_record
 ⑧ aws kinesis get-records ──HTTPS ──────┼──► ┌─────────────▼─────────────┐
   ◄── réponse : les prédictions ────────┼─── │ Kinesis (sortie)          │
                                         │    │ stg_ride_predictions-…    │
                                         │    └───────────────────────────┘
                                         │
 Préparation (une fois) :                │
 terraform apply ──HTTPS ────────────────┼──► crée tous les blocs AWS ci-dessus
 docker push (pendant l'apply) ─HTTPS ───┼──► ECR (dépôt d'images Docker)
```

**Récit.** Même chaîne qu'au §5.3, mais avec les vrais services : la vraie Lambda remplace le RIE, le vrai Kinesis remplace LocalStack, S3 remplace le dossier monté, et un vrai flux d'entrée existe. Les numéros ①…⑧ du schéma correspondent aux étapes 1 à 8 ci-dessous.

**Préparation (une fois)** — depuis le Codespace :

- `terraform apply` crée les deux flux, le bucket S3, le dépôt ECR, la Lambda, ses droits (IAM) et l'*event source mapping* (le lien flux d'entrée → Lambda) ;
- pendant ce `apply`, l'image Docker du service est construite et envoyée (`docker push`) dans ECR, le dépôt d'images d'AWS ;
- le modèle est copié dans le bucket S3, et son `RUN_ID` donné à la Lambda (§7.4).

**Une course traverse le système :**

1. **Envoi.** `test_cloud_e2e.sh` lance `aws kinesis put-record` : le programme `aws` (Codespace) envoie une requête HTTPS à l'API Kinesis d'Amazon. La course (JSON) est déposée dans le flux `stg_ride_events-mlops-zoomcamp`.
2. **Détection.** L'*event source mapping*, un mécanisme du service Lambda, **interroge** ce flux environ une fois par seconde (c'est lui qui demande : Kinesis ne prévient personne). Il trouve le nouveau message.
3. **Appel.** Il met le message dans un lot et appelle la Lambda avec `event = {"Records": [...]}`, la course étant en base64 (le même format que `event.json`). S'il n'y a pas encore de conteneur Lambda prêt, AWS en démarre un à partir de l'image que Lambda a copiée et optimisée depuis ECR au déploiement.
4. **Chargement du modèle** (au démarrage du conteneur seulement). `model.init()` télécharge le modèle depuis S3, au chemin `{exp}/{run}/artifacts/model` (identifiant de l'expérience MLflow / `RUN_ID`, modules 2-4), et crée un client Kinesis qui vise le vrai AWS. Les droits nécessaires viennent du **rôle IAM** de la Lambda : pas de clé à fournir.
5. **Calcul.** `lambda_handler(event)` décode, calcule les features, prédit : **seul endroit où l'on calcule**, comme en local.
6. **Publication.** Le callback envoie la prédiction (HTTPS) dans le flux `stg_ride_predictions-mlops-zoomcamp`.
7. **Journaux.** Tout `print` et toute erreur de la Lambda arrivent dans CloudWatch Logs.
8. **Lecture.** Toi, depuis le Codespace : `aws kinesis get-shard-iterator` puis `get-records` sur le flux de sortie, pour voir la prédiction (ou les logs CloudWatch). Le `return` de `lambda_handler` n'est lu par personne.

| Service | Calcule ? | Rôle |
|---|---|---|
| Kinesis (×2) | Non | Stocker les courses / les prédictions (2 shards chacun, messages conservés 48 h) |
| Event source mapping | Non | Surveiller le flux d'entrée, appeler la Lambda |
| Lambda (ton code) | **Oui** | Prédire et publier |
| S3 | Non | Stocker le modèle |
| ECR | Non | Stocker l'image Docker |
| IAM | Non | Autoriser la Lambda à lire Kinesis/S3 et écrire dans Kinesis |
| CloudWatch | Non | Stocker les journaux |

Tous les appels faits par tes outils et ton code passent par les points d'accès publics HTTPS (port 443) de chaque service, par exemple `kinesis.eu-west-1.amazonaws.com` ; l'interrogation du flux par l'event source mapping, elle, se fait à l'intérieur d'AWS. Le sens important : **Lambda va chercher** les messages dans Kinesis (*pull*), Kinesis ne « pousse » pas vers Lambda.

### 5.5 Niveau 4 — CI/CD

```
 git push feature-x ──► Pull Request vers « develop »
                          │  (seulement si des fichiers de 06-best-practices/code/ changent)
                          ▼
                     ci-tests.yml  ─┬─ job test    : pipenv install → pytest → pylint → run.sh (LocalStack)
                                    └─ job tf-plan : terraform init + plan (prod), sans rien modifier
                          │
                  revue + merge
                          ▼
 push sur « develop » ──► cd-deploy.yml : terraform plan + apply (prod) → docker build + push ECR
                                          → RUN_ID + copie du bucket modèles dev → prod → variables Lambda
```

**Récit.** Rien ne tourne dans ton Codespace : tout s'exécute sur des **runners**, des machines Linux temporaires fournies par GitHub, créées pour un workflow puis détruites.

**Partie CI — vérifier une proposition de changement :**

1. Tu modifies le code sur une **branche** (une copie de travail du dépôt, ex. `feature-x`), tu la pousses sur GitHub, et tu ouvres une **Pull Request** (PR) : une demande de fusionner ta branche dans une autre (ici `develop`), que quelqu'un relit.
2. GitHub détecte l'événement « PR vers `develop` qui touche `06-best-practices/code/` » et lance `ci-tests.yml`, qui contient deux **jobs** exécutés en parallèle, chacun sur son runner.
3. **Job `test`** : récupère le code, installe Python 3.9 et les dépendances, lance les tests unitaires, pylint, puis le test d'intégration `run.sh` (LocalStack tourne alors sur le runner, comme au §5.3 dans ton Codespace). En l'état, cette étape échoue : voir §8.
4. **Job `tf-plan`** : `terraform init` (télécharge le plugin AWS de Terraform et se connecte au state), puis `terraform plan` sur la prod. Terraform compare les fichiers `.tf` à ce qui existe sur AWS et **affiche** ce qui changerait, sans rien modifier. Il lui faut les identifiants AWS, lus dans les **secrets** du dépôt (des valeurs chiffrées stockées par GitHub, jamais écrites dans le code).
5. Le résultat (vert ou rouge) s'affiche sur la PR. Un relecteur la valide et la **fusionne** (*merge*).

**Partie CD — mettre en service :**

6. La fusion est un **push sur `develop`**, ce qui lance `cd-deploy.yml` sur un runner.
7. `terraform plan` puis `apply` sur la prod : crée ou met à jour l'infrastructure AWS, puis donne les noms des ressources (ses *outputs*). Le `null_resource` du module `ecr` peut, à ce moment, déjà construire et pousser une image (si `lambda_function.py` ou le `Dockerfile` ont changé).
8. Construction de l'image Docker et envoi dans ECR. (⚠ La Lambda ne prend pas automatiquement cette nouvelle image : voir §10, remarque 10.)
9. Récupération du `RUN_ID` (dernier objet modifié du bucket MLflow de développement), puis copie de **tout** ce bucket vers le bucket de prod (`aws s3 sync`). Ce bucket de développement est `mlflow-models-alexey`, celui de l'auteur du cours : inaccessible depuis ton compte.
10. Attente que la Lambda soit disponible, puis mise à jour de ses variables d'environnement (nom du flux, bucket, `RUN_ID`).

**CI** (*Continuous Integration*) répond à « ce changement est-il sûr ? ». **CD** (*Continuous Delivery*) le met en service. (Au sens strict, un déploiement en prod automatique à chaque push s'appelle *Continuous Deployment* ; le *Delivery* garde une validation manuelle. Le cours dit « Delivery ».)

---

## 6. Les fichiers de configuration, pas à pas

### 6.1 `Pipfile`

```toml
[[source]]                       # où télécharger les packages : PyPI
url = "https://pypi.org/simple"

[packages]                       # dépendances d'exécution
boto3 = "*"                      # "*" = n'importe quelle version…
mlflow = "*"
scikit-learn = "==1.0.2"         # …sauf celle-ci, épinglée

[dev-packages]                   # dépendances de développement
pytest = "*"
deepdiff = "*"
pylint = "==2.14.4"
black = "*"
isort = "*"
pre-commit = "*"

[requires]
python_version = "3.9"
```

`Pipfile.lock` est généré par pipenv : il fige chaque package **et ses dépendances** à une version exacte, avec une empreinte (*hash*) qui garantit que le fichier téléchargé est le bon. C'est lui qui est lu par `pipenv install`. Même si `Pipfile` dit `mlflow = "*"`, tu obtiens 1.27.0 — **tant que tu ne modifies pas le `Pipfile`** : sinon (ou avec `pipenv install <package>`), pipenv recalcule tout le lock et installe les dernières versions.

### 6.2 `pyproject.toml` — un seul fichier pour régler les outils

```toml
[tool.pylint.messages_control]
disable = [                              # messages pylint ignorés dans tout le projet
    "missing-function-docstring",        # pas de docstring sur une fonction
    "missing-final-newline",
    "missing-class-docstring",
    "missing-module-docstring",
    "invalid-name",                      # ex. la variable X (majuscule) dans ModelMock.predict
    "too-few-public-methods"             # une classe avec 1 seule méthode publique (KinesisCallback)
]

[tool.black]
line-length = 88                         # longueur max d'une ligne
target-version = ['py39']                # syntaxe compatible Python 3.9
skip-string-normalization = true         # ne pas convertir '…' en "…"

[tool.isort]
multi_line_output = 3                    # style des imports trop longs : une ligne par nom, entre parenthèses
length_sort = true                       # trier par LONGUEUR, pas par ordre alphabétique
```

`length_sort = true` explique l'ordre inhabituel en tête de `model.py` : `import os`, `import json`, `import base64` (du plus court au plus long).

Lance ces outils **depuis `code/`** : pylint 2.14 ne lit `pyproject.toml` que dans le dossier courant (vérifié : lancé depuis `tests/`, les messages désactivés réapparaissent).

### 6.3 `.pre-commit-config.yaml`

```yaml
repos:
- repo: https://github.com/pre-commit/pre-commit-hooks   # hooks génériques, téléchargés depuis GitHub
  rev: v3.2.0                                             # version (tag git) du dépôt de hooks
  hooks:
    - id: trailing-whitespace        # supprime les espaces en fin de ligne
    - id: end-of-file-fixer          # garantit un saut de ligne final
    - id: check-yaml                 # vérifie que les .yaml sont valides
    - id: check-added-large-files    # refuse d'ajouter au dépôt un fichier > 500 Ko
- repo: https://github.com/pycqa/isort
  rev: 5.10.1                        # ⚠ ne s'installe plus : voir §8
  hooks:
    - id: isort
- repo: https://github.com/psf/black
  rev: 22.6.0
  hooks:
    - id: black
      language_version: python3.9
- repo: local                        # « local » = pas de téléchargement : on utilise l'outil déjà installé
  hooks:
    - id: pylint
      entry: pylint                  # commande lancée
      language: system               # prise dans le PATH → l'environnement pipenv doit être actif
      types: [python]                # seulement sur les fichiers .py
      args: ["-rn", "-sn", "--recursive=y"]   # pas de rapport, pas de note, récursif
- repo: local
  hooks:
    - id: pytest-check
      entry: pytest
      language: system
      pass_filenames: false          # ne pas passer la liste des fichiers modifiés à pytest
      always_run: true               # lancer même si aucun .py n'a changé
      args: ["tests/"]
```

Deux familles de hooks : ceux avec un `repo:` URL sont installés par pre-commit dans **son propre environnement isolé** (cache `~/.cache/pre-commit`) ; ceux en `repo: local` + `language: system` utilisent **ton** environnement.

Commandes :

```bash
pre-commit install            # écrit le hook dans .git/hooks/pre-commit
pre-commit run --all-files    # exécute tous les hooks sur tous les fichiers, sans commit
```

`--all-files` ne traite que les fichiers **suivis par git** : dans un dépôt neuf, fais d'abord `git add .`, sinon tous les hooks sauf pytest affichent « Skipped » et rien n'est contrôlé.

Au premier passage, `trailing-whitespace` et `end-of-file-fixer` corrigent des fichiers et affichent **Failed** : c'est normal (« j'ai modifié des fichiers, vérifie-les »). Au second passage, tout passe.

> **Piège dans ton fork (vérifié)** : pre-commit s'exécute toujours depuis la **racine du dépôt git**. Or dans ton fork, la racine est `mlops-zoomcamp/`, pas `code/`. Conséquences : `pytest tests/` échoue (`file or directory not found: tests/`), pylint ne trouve plus `code/pyproject.toml` (les messages désactivés reviennent), et `--all-files` porte sur tous les modules du dépôt. Pour pratiquer, travaille dans une copie qui est son propre dépôt :
> ```bash
> cp -r 06-best-practices/code ~/m6-sandbox && cd ~/m6-sandbox
> sed -i 's/rev: 5.10.1/rev: 5.12.0/' .pre-commit-config.yaml   # correctif isort (§8)
> git init && git add .
> pipenv install --dev --python "$(which python)"   # conda mlops-06 actif : un venv propre à ce dossier
> pipenv shell
> pre-commit install && pre-commit run --all-files
> ```
> pipenv crée un environnement **par dossier** : celui de `code/` n'est pas réutilisé dans `~/m6-sandbox`, d'où la réinstallation. Cette copie est un bac à sable : elle n'est pas dans ton fork et ne sera pas poussée sur GitHub.

### 6.4 `.vscode/settings.json`

```json
{
  "python.testing.pytestArgs": ["tests"],      // dossier des tests
  "python.testing.unittestEnabled": false,     // pas le framework unittest…
  "python.testing.pytestEnabled": true,        // …mais pytest → icône « Testing » dans VS Code
  "python.linting.pylintEnabled": true,        // obsolète (voir ci-dessous)
  "python.linting.enabled": true               // obsolète
}
```

- VS Code ne lit ce fichier que si `code/` est **le dossier ouvert** dans VS Code. Si tu as ouvert tout le fork, il est ignoré : utilise *File → Open Folder… → 06-best-practices/code*.
- Les deux lignes `python.linting.*` ne font plus rien depuis 2023 : le linting est passé dans des extensions séparées (installe l'extension **Pylint** de Microsoft).

### 6.5 `Makefile`

```makefile
# ex. 2026-09-27-14-30, calculé une fois ; puis nom:tag de l'image Docker
LOCAL_TAG:=$(shell date +"%Y-%m-%d-%H-%M")
LOCAL_IMAGE_NAME:=stream-model-duration:${LOCAL_TAG}

test:                                   # cible « test »
	pytest tests/                       # ⚠ la ligne de commande DOIT commencer par une tabulation

quality_checks:
	isort .
	black .
	pylint --recursive=y .

build: quality_checks test              # « build » dépend de deux cibles, exécutées avant
	docker build -t ${LOCAL_IMAGE_NAME} .

integration_test: build
	LOCAL_IMAGE_NAME=${LOCAL_IMAGE_NAME} bash integraton-test/run.sh   # ⚠ faute de frappe : voir §8

publish: build integration_test
	LOCAL_IMAGE_NAME=${LOCAL_IMAGE_NAME} bash scripts/publish.sh

setup:
	pipenv install --dev
	pre-commit install
```

- Syntaxe : `cible: dépendances` puis les commandes, **indentées par une tabulation** (pas des espaces).
- `:=` évalue la valeur une seule fois : toutes les cibles d'un même `make` partagent le même tag.
- `VAR=valeur commande` passe une variable d'environnement à cette seule commande. C'est ainsi que `run.sh` sait quelle image utiliser.
- `make publish` → `quality_checks` → `test` → `build` → `integration_test` → `publish`. Make n'exécute chaque cible qu'une fois par appel, même si plusieurs en dépendent.
- `scripts/publish.sh` n'est qu'un `echo` : un emplacement réservé.

### 6.6 `Dockerfile`

Fichier reproduit à l'identique (numéros de ligne à gauche), explications en dessous — un Dockerfile n'accepte pas de commentaire en fin de ligne.

```dockerfile
 1  FROM public.ecr.aws/lambda/python:3.9
 2
 3  RUN pip install -U pip
 4  RUN pip install pipenv
 5
 6  COPY [ "Pipfile", "Pipfile.lock", "./" ]
 7
 8  RUN pipenv install --system --deploy
 9
10  COPY [ "lambda_function.py", "model.py", "./" ]
11
12  CMD [ "lambda_function.lambda_handler" ]
```

| Ligne | Rôle |
|---|---|
| 1 | Image de base Lambda : Python 3.9 + RIE. |
| 3-4 | Mettre pip à jour, installer pipenv. ⚠ La ligne 4 doit être épinglée (§8). |
| 6 | Copier d'abord les fichiers de dépendances… |
| 8 | …et les installer. `--system` : dans le Python de l'image, pas dans un venv. `--deploy` : échouer si le lock ne correspond plus au `Pipfile`. |
| 10 | Copier ensuite le code. |
| 12 | « fichier.fonction » que Lambda doit appeler (le handler). |

L'ordre des `COPY` a une raison : Docker met chaque étape en **cache**. Tant que `Pipfile*` ne change pas, l'installation (lente) est réutilisée et seule la copie du code est refaite.

Aucun modèle dans l'image : il est chargé au démarrage, depuis S3 (cloud) ou un dossier monté (test).

### 6.7 `integration-test/docker-compose.yaml`

```yaml
services:
  backend:                                   # nom du service = nom DNS sur le réseau Docker
    image: ${LOCAL_IMAGE_NAME}               # image construite juste avant, nom lu dans l'environnement
    ports:
      - "8080:8080"                          # "port hôte:port conteneur"
    environment:
      - PREDICTIONS_STREAM_NAME=${PREDICTIONS_STREAM_NAME}
      - RUN_ID=Test123                       # sert juste d'étiquette « version » dans la réponse
      - AWS_DEFAULT_REGION=eu-west-1
      - MODEL_LOCATION=/app/model            # → get_model_location n'ira pas sur S3
      - KINESIS_ENDPOINT_URL=http://kinesis:4566/   # → boto3 parle à LocalStack, pas à AWS
      - AWS_ACCESS_KEY_ID=abc                # faux identifiants : sans eux, boto3 ne peut pas signer
      - AWS_SECRET_ACCESS_KEY=xyz            # put_record (« Unable to locate credentials ») ; LocalStack ne les vérifie pas
    volumes:
      - "./model:/app/model"                 # le dossier model/ de l'hôte apparaît dans le conteneur
  kinesis:
    image: localstack/localstack             # ⚠ ne démarre plus sans jeton : voir §8
    ports:
      - "4566:4566"                          # port unique de LocalStack pour tous les services AWS
    environment:
      - SERVICES=kinesis                     # ne démarrer que Kinesis
```

`TEST_RUN` n'est pas défini → vaut `False` → le callback Kinesis est **actif** : c'est voulu, on veut tester la publication.

### 6.8 `integration-test/run.sh`

```bash
if [[ -z "${GITHUB_ACTIONS}" ]]; then cd "$(dirname "$0")"; fi
#   -z = « chaîne vide ». Hors GitHub Actions, se placer dans le dossier du script.

if [ "${LOCAL_IMAGE_NAME}" == "" ]; then            # lancé seul (sans make) ?
    LOCAL_TAG=`date +"%Y-%m-%d-%H-%M"`
    export LOCAL_IMAGE_NAME="stream-model-duration:${LOCAL_TAG}"
    docker build -t ${LOCAL_IMAGE_NAME} ..           # .. = code/, où est le Dockerfile
fi

export PREDICTIONS_STREAM_NAME="ride_predictions"
docker-compose up -d                                 # -d : en arrière-plan
sleep 5                                              # laisser LocalStack démarrer (parfois trop court)

aws --endpoint-url=http://localhost:4566 kinesis create-stream \
    --stream-name ${PREDICTIONS_STREAM_NAME} --shard-count 1

pipenv run python test_docker.py                     # test 1
ERROR_CODE=$?                                        # $? = code de sortie de la dernière commande (0 = OK)
if [ ${ERROR_CODE} != 0 ]; then
    docker-compose logs; docker-compose down; exit ${ERROR_CODE}
fi

pipenv run python test_kinesis.py                    # test 2, même traitement d'erreur
...
docker-compose down                                  # tout arrêter et supprimer
```

Le schéma « lancer, vérifier `$?`, en cas d'échec afficher les logs **puis nettoyer** » garantit qu'un test raté ne laisse pas de conteneurs orphelins.

Avant de le lancer, dans le terminal : l'`aws` CLI a elle aussi besoin d'une région et d'identifiants, même factices :

```bash
export AWS_DEFAULT_REGION=eu-west-1 AWS_ACCESS_KEY_ID=abc AWS_SECRET_ACCESS_KEY=xyz
```

### 6.9 Les fichiers de test d'intégration

- **`event.json`** : un événement complet tel que Kinesis le livre à Lambda. Seul `Records[0].kinesis.data` est utilisé par le code ; le reste (ARN, numéro de séquence…) rend l'exemple réaliste.
- **`test_docker.py`** : `requests.post(url, json=event)` puis compare avec `DeepDiff`. L'URL `/2015-03-31/functions/function/invocations` est celle, fixe, de l'émulateur RIE. Valeur attendue : `21.3` (vérifié : le modèle prédit 21.29).
- **`test_kinesis.py`** : lit le flux de sortie. Pour lire un flux Kinesis, on demande d'abord un **itérateur de shard** (un curseur) : `TRIM_HORIZON` = « depuis le plus ancien message encore conservé » (par opposition à `LATEST` = « seulement les nouveaux »). Puis `get_records(ShardIterator=..., Limit=1)`.
- **`model/`** : un modèle MLflow au format standard. `MLmodel` décrit comment le charger (`loader_module: mlflow.sklearn`, `sklearn_version: 1.0.2`) ; `model.pkl` contient un `Pipeline(DictVectorizer, RandomForestRegressor)`. `conda.yaml`, `python_env.yaml` et `requirements.txt` décrivent l'environnement d'origine. Au chargement, MLflow affiche un avertissement sur des versions de `cloudpickle`/`psutil` différentes : sans conséquence ici.

### 6.10 Les tests unitaires (`tests/model_test.py`)

| Test | Vérifie | Technique |
|---|---|---|
| `test_base64_decode` | Le décodage de `data.b64` donne le bon dict | `Path(__file__).parent` pour trouver le fichier quel que soit le dossier courant |
| `test_prepare_features` | `PU_DO = "130_205"` | `ModelService(None)` : pas besoin de modèle pour cette méthode |
| `test_predict` | `predict` renvoie la première valeur donnée par le modèle (10.0) | **Mock** : `ModelMock(10.0)` imite un modèle (même méthode `predict`) et renvoie toujours 10.0 |
| `test_lambda_handler` | Le flux complet décodage → prédiction → format de sortie | Mock + aucun callback |

Un **mock** est un faux objet qui a la même « forme » que le vrai. Il rend le test rapide et **déterministe** : le résultat ne dépend ni d'un fichier, ni du réseau, ni du hasard. À quoi ressemble un test pytest (extrait de `model_test.py`) :

```python
class ModelMock:                          # le faux modèle : juste une méthode predict
    def __init__(self, value):
        self.value = value
    def predict(self, X):
        return [self.value] * len(X)      # une valeur par ligne, toujours la même

def test_predict():                       # pytest exécute toute fonction nommée test_*
    model_service = model.ModelService(ModelMock(10.0))   # injection du faux modèle
    features = {"PU_DO": "130_205", "trip_distance": 3.66}
    assert model_service.predict(features) == 10.0         # faux → le test échoue
```

Ici le mock est une classe écrite à la main. La bibliothèque standard `unittest.mock` (`Mock`, `MagicMock`, `patch`) fabrique ce genre d'objet automatiquement : tu la croiseras souvent ailleurs.

### 6.11 Terraform (`infrastructure/`)

Les fichiers `.tf` sont écrits en **HCL** (*HashiCorp Configuration Language*), le langage de Terraform.

> **Attention aux homonymes** : ici, « backend » = l'endroit où Terraform range son state (rien à voir avec le conteneur `backend` du §5.3), et « module » = une brique Terraform (ni un module Python, ni un module du cours).

**Vocabulaire minimal** :

| Mot | Sens |
|---|---|
| `provider` | Le plugin qui parle à un fournisseur (ici `aws`). |
| `resource` | Un objet à **créer et gérer** (un flux, un bucket…). |
| `data` | Un objet à **lire seulement** (ex. l'identité du compte courant). |
| `variable` / `.tfvars` | Paramètres d'entrée / leurs valeurs pour un environnement. |
| `locals` | Valeurs intermédiaires calculées dans le fichier (des « variables internes »). |
| `output` | Une valeur exposée après `apply` (lue par la CD). |
| `module` | Un dossier `.tf` réutilisable, appelé avec des paramètres : une « fonction » d'infrastructure. |
| **state** (`.tfstate`) | La mémoire de Terraform : ce qu'il a créé. Stocké ici dans un bucket S3 (**backend**). |

**`main.tf`, bloc par bloc :**

```hcl
terraform {
  required_version = ">= 1.0"
  backend "s3" {                             # où ranger le state
    bucket  = "tf-state-mlops-zoomcamp"      # ⚠ bucket à créer à la main AVANT, avec un nom à toi
    key     = "mlops-zoomcamp-stg.tfstate"   # nom du fichier state (la CI le remplace pour la prod)
    region  = "eu-west-1"
    encrypt = true
  }
}
provider "aws" { region = var.aws_region }

data "aws_caller_identity" "current_identity" {}             # « qui suis-je ? » → numéro de compte
locals { account_id = data.aws_caller_identity.current_identity.account_id }

module "source_kinesis_stream" {             # flux d'entrée
  source = "./modules/kinesis"
  retention_period = 48                      # heures
  shard_count = 2
  stream_name = "${var.source_stream_name}-${var.project_id}"   # ex. stg_ride_events-mlops-zoomcamp
  tags = var.project_id
}
module "output_kinesis_stream" { ... }       # flux de sortie, même module réutilisé
module "s3_bucket"   { ... }                 # bucket des modèles
module "ecr_image"   { ... }                 # dépôt ECR + premier push d'image
module "lambda_function" {
  image_uri         = module.ecr_image.image_uri               # sortie d'un module → entrée d'un autre
  source_stream_arn = module.source_kinesis_stream.stream_arn
  ...
}
output "lambda_function" { ... }             # 4 sorties lues par cd-deploy.yml
```

Terraform déduit l'**ordre de création** de ces références : la Lambda référence l'image et les flux (via leur ARN, §3.2), donc elle est créée après eux.

**`variables.tf` + `vars/stg.tfvars`** : `variables.tf` déclare les paramètres ; `stg.tfvars` et `prod.tfvars` leur donnent des valeurs (préfixe `stg_` ou `prod_`). `-var-file=vars/stg.tfvars` choisit l'environnement.

**Les modules :**

- **`kinesis/`** : une ressource `aws_kinesis_stream` ; les `shard_level_metrics` publient des métriques par shard dans CloudWatch. Sortie : `stream_arn`.
- **`s3/`** : un bucket ; `force_destroy = true` permet de le supprimer même non vide (pratique pour `destroy`, dangereux en vraie prod).
- **`ecr/`** : le dépôt d'images, puis un `null_resource` avec `local-exec` — une astuce qui exécute des commandes shell (`docker login`, `docker build`, `docker push`) **sur la machine qui lance Terraform**. Nécessaire car une Lambda « image » ne peut pas être créée sans image existante. `triggers` : relancer si `lambda_function.py` ou le `Dockerfile` changent (empreinte `md5`). Le `data "aws_ecr_image"` avec `depends_on` attend que le push soit fini.
- **`lambda/`** :
  - `main.tf` : la fonction (`package_type = "Image"`, `timeout = 180` s, traçage X-Ray actif) et ses variables d'environnement ; `maximum_retry_attempts = 0` (dans `aws_lambda_function_event_invoke_config`) ne concerne que les invocations **asynchrones**, pas la lecture de Kinesis ; enfin l'**event source mapping** qui branche le flux d'entrée (`starting_position = "LATEST"` : ignorer l'historique). Par défaut, un lot Kinesis en erreur est **réessayé jusqu'à expiration des messages** (ici 48 h), ce qui bloque le shard pendant ce temps.
  - `iam.tf` : le rôle endossé par la Lambda (`assume_role_policy` : « les services lambda.amazonaws.com et kinesis.amazonaws.com peuvent prendre ce rôle » — le second est inutile) et les policies attachées : Kinesis, écriture dans le flux de sortie, logs CloudWatch, S3.

**Cycle de vie :**

```bash
cd infrastructure
terraform init                            # télécharge le provider, connecte le backend S3
terraform plan  -var-file=vars/stg.tfvars # AFFICHE ce qui sera créé/modifié/détruit — ne touche à rien
terraform apply -var-file=vars/stg.tfvars # applique (demande confirmation)
terraform destroy -var-file=vars/stg.tfvars   # supprime tout — à faire après chaque session
```

(Le README écrit `terraform destroy` sans `-var-file` : les variables obligatoires seraient alors demandées une par une.)

### 6.12 `scripts/`

- **`deploy_manual.sh`** : ce que Terraform ne gère pas (le **contenu**, pas l'infrastructure). Récupère le dernier `RUN_ID` dans le bucket MLflow de développement, copie les artefacts vers le bucket créé par Terraform (`aws s3 sync`), puis injecte `RUN_ID` dans la Lambda (`aws lambda update-function-configuration`). À lancer avec `. ./scripts/deploy_manual.sh` (le `.` exécute le script dans le shell courant, ses `export` restent). Il pointe vers `mlflow-models-alexey`, le bucket de l'auteur : inaccessible pour toi (voir §7.4).
- **`test_cloud_e2e.sh`** : envoie une course dans le flux d'entrée réel. `--cli-binary-format raw-in-base64-out` : dire à AWS CLI v2 que `--data` est du texte brut à encoder, pas du base64 déjà encodé. La relecture du résultat est commentée : à faire à la main (`get-shard-iterator` puis `get-records`), ou via les logs CloudWatch.

### 6.13 `.github/workflows/` (racine du fork)

**`ci-tests.yml`** :

```yaml
on:
  pull_request:
    branches: ['develop']                        # PR qui visent la branche develop…
    paths: ['06-best-practices/code/**']         # …et modifient ce dossier
env:                                             # variables communes, lues dans les secrets du dépôt
  AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
jobs:
  test:                                          # job 1
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2                # récupérer le code
      - uses: actions/setup-python@v2            # installer Python 3.9
      - run: pip install pipenv && pipenv install --dev
      - run: pipenv run pytest tests/
      - run: pipenv run pylint --recursive=y .
      - uses: aws-actions/configure-aws-credentials@v1
      - name: Integration Test                   # ⚠ dossier mal orthographié : voir §8
        working-directory: '06-best-practices/code/integraton-test'
        run: . run.sh
  tf-plan:                                       # job 2, en parallèle du job 1
    steps: ... terraform init -backend-config="key=mlops-zoomcamp-prod.tfstate" && terraform plan
```

`uses:` appelle une **action** (un bloc réutilisable publié sur GitHub) ; `run:` exécute une commande shell. `-backend-config="key=…prod…"` remplace le `key` de `main.tf` : même code, state de prod.

**`cd-deploy.yml`** (sur `push` vers `develop`) : `terraform plan` puis `apply -auto-approve` (sans confirmation), lecture des `output` Terraform, connexion à ECR, `docker build` + `push`, copie du modèle, attente que la Lambda ne soit plus `InProgress`, mise à jour de ses variables. Les étapes se passent des valeurs via `::set-output`, une syntaxe dépréciée (aujourd'hui : `echo "nom=valeur" >> "$GITHUB_OUTPUT"`).

Dans ton fork, ces workflows ne tourneront que si trois conditions sont réunies : (1) une branche `develop` existe ; (2) les workflows sont activés dans l'onglet **Actions** du fork (GitHub les désactive par défaut sur un fork) ; (3) tes PR visent **ton** fork comme base (par défaut, GitHub propose le dépôt d'origine DataTalksClub).

---

## 7. Feuille de route pratique

### 7.1 Avant tout : appliquer les corrections

Dans ton fork (ce sont tes fichiers, tu peux les modifier et les committer), applique d'abord les corrections du §8 nécessaires au bloc A :

1. `Dockerfile` l.4 → `RUN pip install "pipenv==2023.12.1"`
2. `integration-test/docker-compose.yaml` l.17 → `image: localstack/localstack:4.14.0`
3. `Makefile` l.16 → `integration-test/run.sh`
4. `.pre-commit-config.yaml` l.12 → `rev: 5.12.0`

Et vérifie les outils du Codespace : `which aws docker-compose`. Si `docker-compose` n'existe pas mais que `docker compose version` répond, remplace `docker-compose` par `docker compose` dans `run.sh`. Pour installer AWS CLI v2 :

```bash
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o awscliv2.zip
unzip awscliv2.zip && sudo ./aws/install
```

### 7.2 Bloc A

Depuis `06-best-practices/code`, environnement du §0 actif :

```bash
pytest tests/                                     # 1. unitaires : 4 passed
isort . && black . && pylint --recursive=y .     # 2. qualité : 10.00/10
docker build -t stream-model-duration:v2 .        # 3. l'image
export AWS_DEFAULT_REGION=eu-west-1 AWS_ACCESS_KEY_ID=abc AWS_SECRET_ACCESS_KEY=xyz
LOCAL_IMAGE_NAME=stream-model-duration:v2 bash integration-test/run.sh   # 4. intégration
```

Si l'étape 4 échoue au premier essai (LocalStack pas encore prêt), relance-la. Pour pre-commit : le bac à sable du §6.3.

### 7.3 Le devoir

Le devoir (homework 2025) applique les mêmes idées à un autre script, `batch.py` (prédiction par lots, module 4) : refactoring, tests unitaires avec pytest, LocalStack pour simuler **S3**. Il a son propre `Pipfile` en Python 3.10, donc son propre environnement, avec la même recette que le §0 (`conda create -n mlops-06-hw python=3.10`, puis `pipenv install --dev --python "$(which python)"` depuis le dossier du devoir). Non testé.

### 7.4 Bloc B

Seulement avec un compte AWS et en acceptant des frais. Ordre de grandeur (tarifs US-East, eu-west-1 un peu plus cher) : 4 shards × (0,015 $ + 0,020 $ de rétention au-delà de 24 h) par heure ≈ **0,14 $/h, soit 3 à 4 $ par jour** tant que l'infrastructure existe, plus les métriques CloudWatch par shard. Vérifie sur la page de prix AWS.

1. `aws configure` avec **tes** clés, `terraform` installé.
2. Renommer ce qui doit être unique au monde : le bucket du backend (`main.tf` l.5, à créer à la main avant `init`) et `model_bucket` dans les `.tfvars` (les noms de buckets S3 sont uniques sur tout AWS).
3. `terraform init` → `plan` → `apply` (staging).
4. Mettre un modèle dans le bucket. Le plus simple, sans MLflow : réutiliser le modèle de test. Le chemin doit suivre `get_model_location` (§2.2) : `1` = `MLFLOW_EXPERIMENT_ID` par défaut, `Test123` = le `RUN_ID` choisi.
   ```bash
   aws s3 cp --recursive integration-test/model s3://<bucket-modele>/1/Test123/artifacts/model
   ```
   Puis donner les variables à la Lambda. `--environment` **remplace toutes** les variables : il faut les repasser toutes, sinon `MODEL_BUCKET` retombe sur `mlflow-models-alexey`.
   ```bash
   aws lambda update-function-configuration --function-name <nom-lambda> \
     --environment "Variables={PREDICTIONS_STREAM_NAME=<flux-sortie>, MODEL_BUCKET=<bucket-modele>, RUN_ID=Test123}"
   ```
   Un `terraform apply` ultérieur retirera `RUN_ID` (absent du Terraform) : à refaire après chaque `apply`.
5. `test_cloud_e2e.sh` (avec tes noms de flux), puis lire le flux de sortie ou les logs CloudWatch.
6. **`terraform destroy -var-file=vars/stg.tfvars`.**

---

## 8. Bugs et pièges vérifiés

Relevé seulement : aucun fichier de ton fork n'a été modifié. Les quatre premières lignes sont à corriger avant de pratiquer (§7.1).

| Fichier | Ligne | Problème | Correction proposée |
|---|---|---|---|
| `Dockerfile` | 4 | `pip install pipenv` installe la dernière version, dont le pip embarqué refuse `mlflow==1.27.0` → `docker build` échoue à la ligne 8 (reproduit hors Docker, à l'identique) | `RUN pip install "pipenv==2023.12.1"` |
| `integration-test/docker-compose.yaml` | 17 | Depuis le 23/03/2026, l'image `localstack/localstack` (sans version) exige un compte et un jeton `LOCALSTACK_AUTH_TOKEN` ; sans lui, le conteneur s'arrête (code 55) | Épingler `localstack/localstack:4.14.0`, dernière version avant ce changement, **ou** créer un compte gratuit et ajouter `- LOCALSTACK_AUTH_TOKEN=${LOCALSTACK_AUTH_TOKEN}` |
| `Makefile` | 16 | `integraton-test` (il manque un « i ») → `make integration_test` échoue | `integration-test/run.sh` |
| `.pre-commit-config.yaml` | 12 | `isort` `rev: 5.10.1` ne s'installe plus (`RuntimeError: The Poetry configuration is invalid`) | `rev: 5.12.0` (testé : au 2ᵉ passage, tous les hooks passent) |
| Environnement local | — | Même cause que la 1ʳᵉ ligne du tableau : un pipenv récent ne peut pas installer le lock | `pip install "pipenv==2023.12.1"` (§0, testé) |
| `integration-test/run.sh` | 22 | L'`aws` CLI de l'hôte n'a ni région ni identifiants → `You must specify a region` / `Unable to locate credentials` | Exporter `AWS_DEFAULT_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` factices avant (§6.8) |
| `integration-test/run.sh` | 20 | `sleep 5` peut être trop court au premier démarrage de LocalStack | Relancer, ou attendre que `curl -s localhost:4566/_localstack/health` réponde |
| Pre-commit dans le fork | — | Les hooks s'exécutent depuis la racine du dépôt (vérifié) | Bac à sable avec son propre `git init` (§6.3) |
| `.github/workflows/ci-tests.yml` | 44 | Même faute `integraton-test` dans `working-directory` | `06-best-practices/code/integration-test` |
| `integration-test/run.sh` (en CI) | 18 | GitHub a retiré `docker-compose` v1 de ses runners Ubuntu en 2024 → en CI, `command not found` probable | `docker compose` (v2) |
| `.vscode/settings.json` | 7-8 | `python.linting.*` ignorés par VS Code depuis 2023 | Extension Pylint de Microsoft |

---

## 9. Points de doute (non vérifiés, à confirmer en pratique)

Je n'ai pas pu télécharger d'images Docker ni utiliser Terraform ou AWS pour écrire ce cours. Donc :

1. **`localstack/localstack:4.14.0` sans jeton** : deux sources concordantes le présentent comme la dernière version avant le changement, mais je ne l'ai pas lancée. Si elle échoue aussi : compte LocalStack gratuit + jeton.
2. **`docker-compose` (avec tiret) dans ton Codespace** : `run.sh` l'utilise. Au module 5, tu as vu laquelle des deux commandes marchait (§7.1).
3. **`acl = "private"`** (`infrastructure/modules/s3/main.tf`, l.3) : argument déprécié dans le provider AWS de Terraform, dont la version n'est pas épinglée. Au mieux rien, au pire un avertissement d'après un ticket du provider ; non testé.
4. **Image `public.ecr.aws/lambda/python:3.9`** : le runtime Python 3.9 de Lambda est déprécié depuis le 15/12/2025 : l'image de base ne reçoit plus de correctifs. Les blocages annoncés par AWS (création au 01/02/2027, mise à jour au 03/03/2027) visent a priori les fonctions .zip ; une fonction de type image, comme ici, devrait rester déployable. Je n'ai pas pu le vérifier.
5. **Mémoire de la Lambda** : `memory_size` n'est pas défini dans `modules/lambda/main.tf` → 128 Mo par défaut. Charger mlflow + scikit-learn + pandas pourrait dépasser cette limite (erreur de mémoire dans CloudWatch). Si c'est le cas : `memory_size = 512`.
6. **CI GitHub (`actions/*@v2`, `set-output`, Python 3.9 sur `ubuntu-latest`)** : versions anciennes, qui pourraient afficher des avertissements ou échouer sur les runners actuels. Non testé.

---

## 10. Remarques d'expert (hors périmètre du cours)

1. **IAM trop large** : `iam.tf` donne `s3:*` sur **tous** les buckets et `kinesis:*` sur tous les flux (le `TODO` de l'auteur le reconnaît) ; le bloc `stream:*` sur `arn:aws:stream:*` ne correspond à aucun service AWS. Bonne pratique : le **moindre privilège**, c'est-à-dire accorder uniquement les droits nécessaires (`s3:GetObject`/`ListBucket` sur le bucket du modèle, lecture du flux d'entrée, écriture du flux de sortie).
2. **`aws_lambda_permission` inutile** : elle autorise `events.amazonaws.com` (EventBridge) avec l'ARN d'un flux Kinesis comme source. Un event source mapping Kinesis n'en a pas besoin : Lambda lit le flux avec son propre rôle. De même, `kinesis.amazonaws.com` dans l'`assume_role_policy` est superflu.
3. **Condition GitHub mal écrite** : dans `cd-deploy.yml`, `if: ${{ steps.tf-plan.outcome }} == 'success'` est toujours vrai (c'est une chaîne non vide). Forme correcte : `if: steps.tf-plan.outcome == 'success'`. Sans effet ici, car une étape est de toute façon sautée si la précédente a échoué.
4. **CD sans garde-fou** : `cd-deploy.yml` se déclenche à chaque push sur `develop`, même si la CI n'a pas tourné, et applique la **prod** avec `-auto-approve`.
5. **isort et black non alignés** : sans `profile = "black"` dans `[tool.isort]` (un préréglage qui aligne isort sur les règles de black), isort coupe les imports longs à 79 caractères, black à 88 → ils peuvent se contredire sur un import long.
6. **Reconstruction de l'image incomplète** : dans `modules/ecr/main.tf`, les `triggers` surveillent `lambda_function.py` et le `Dockerfile`, mais pas `model.py` : modifier seulement `model.py` ne relance pas le build. La région y est aussi figée à `eu-west-1` au lieu de suivre `var.aws_region`.
7. **`deploy_manual.sh`** prend « le dernier objet modifié du bucket » comme `RUN_ID` : fragile (l'auteur écrit *NOT FOR PRODUCTION*). En pratique : le Model Registry de MLflow (module 2).
8. **Réessais Kinesis non bornés** : sans `maximum_retry_attempts` ni `bisect_batch_on_function_error` sur l'event source mapping, un seul message qui fait planter la Lambda bloque son shard jusqu'à 48 h (§6.11).
9. **Les outils de qualité du Pipfile sont anciens** (pylint 2.14, black 22) et figés pour Python 3.9. Sur un projet neuf, un outil unique comme `ruff` remplace isort + black + pylint et bien plus vite. Pour suivre le cours, garde les versions du lock.
10. **La CD ne met probablement pas à jour le code de la Lambda.** `cd-deploy.yml` pousse une nouvelle image sous le **même tag** `latest`, puis ne change que la *configuration* de la Lambda. Or, d'après la documentation AWS, Lambda résout le tag en une empreinte d'image (*digest*) au déploiement et **ne suit pas** automatiquement une nouvelle image poussée sous ce tag : il faut `aws lambda update-function-code --image-uri …`. Le comportement de Lambda est documenté ; l'effet sur ce workflow précis n'a pas été testé.

---

## 11. Récapitulatif

| Notion | En une phrase |
|---|---|
| Serveur / port | Programme qui attend des requêtes et y répond / numéro qui le distingue sur sa machine (`localhost:8080`). |
| HTTP / HTTPS | Le protocole requête-réponse le plus répandu / sa version chiffrée (port 443). |
| Test unitaire | Vérifie une fonction isolée, sans réseau ni fichier, en quelques millisecondes. |
| Mock | Faux objet de même forme que le vrai, pour rendre un test rapide et déterministe. |
| Injection de dépendances | Donner à une classe ses outils (modèle, client) au lieu qu'elle les crée : on peut alors lui donner des faux. |
| Test d'intégration | Démarre le vrai conteneur et le teste de l'extérieur, en HTTP. |
| RIE | Serveur HTTP inclus dans l'image Lambda : un `POST` sur le port 8080 fait appeler `lambda_handler` (via le client d'exécution Python) et renvoie son résultat. |
| Flux Kinesis | Un nom + un nombre de voies (+ une durée de conservation), sans schéma ; créé par `run.sh` en local, par Terraform sur AWS. |
| LocalStack | Faux AWS local sur le port 4566 ; `--endpoint-url` / `endpoint_url` pour s'y connecter. |
| Nom de service Docker | Adresse d'un conteneur vu depuis un autre conteneur (`kinesis:4566`). |
| isort / black / pylint | Trier les imports / formater / analyser, réglés dans `pyproject.toml`. |
| pre-commit | Contrôles lancés automatiquement avant chaque commit, depuis la racine du dépôt. |
| make | Noms courts pour des suites de commandes, avec dépendances entre cibles. |
| pipenv | `Pipfile` (intentions) + `Pipfile.lock` (versions exactes) ; un environnement par projet. |
| Terraform | L'infrastructure décrite en fichiers : `init` → `plan` → `apply` → `destroy`. |
| Module / output | Brique d'infrastructure réutilisable / valeur qu'elle expose aux autres. |
| State / backend | Mémoire de Terraform / où elle est rangée (S3). |
| Event source mapping | Lambda interroge Kinesis et s'invoque avec les messages reçus. |
| CI / CD | Vérifier chaque changement / le déployer automatiquement. |
