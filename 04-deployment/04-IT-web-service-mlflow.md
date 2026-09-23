# 04 — IT / Déploiement : du notebook au conteneur Docker

> **Dossier concerné** : `04-deployment/web-service-mlflow/`
> **Fichiers** : `predict.py`, `test.py`, `Pipfile`, `Pipfile.lock`, `Dockerfile`, `.dockerignore`
> **Comparaison** : le setup de `04-deployment/web-service/`
> **Portée** : tout ce qui n'est pas du machine learning. Le notebook `random-forest.ipynb`, `make_pipeline` et les API MLflow sont traités dans `04-python-web-service-mlflow.md`.

Ce document suit le plan que tu avais commencé dans `04-buildmyservice.md`, complété des étapes qui manquaient.

> **Tu reviens ici pour refaire, pas pour comprendre ?** Va directement au **§19 — Cheat sheet** : le parcours complet en une page. Puis au **§18 — Dépannage** si ça casse. Le reste de ce document explique *pourquoi* chaque ligne est là.

---

## Sommaire

1. [Le vocabulaire, d'abord](#1-le-vocabulaire-dabord)
2. [L'architecture cible](#2-larchitecture-cible)
3. [Étape 0 — Lancer le serveur MLflow et entraîner](#3-%C3%A9tape-0--lancer-le-serveur-mlflow-et-entra%C3%AEner)
4. [Étape 1 — `predict.py`, ligne par ligne](#4-%C3%A9tape-1--predictpy-ligne-par-ligne)
5. [Étape 2 — `test.py`, le client](#5-%C3%A9tape-2--testpy-le-client)
6. [Étape 3 — Le serveur de développement Flask](#6-%C3%A9tape-3--le-serveur-de-d%C3%A9veloppement-flask)
7. [Étape 4 — Passer à gunicorn](#7-%C3%A9tape-4--passer-%C3%A0-gunicorn)
8. [Étape 5 — Relever les versions exactes](#8-%C3%A9tape-5--relever-les-versions-exactes)
9. [Étape 6 — Créer le pipenv](#9-%C3%A9tape-6--cr%C3%A9er-le-pipenv)
10. [Étape 7 — Adapter `predict.py` pour le conteneur](#10-%C3%A9tape-7--adapter-predictpy-pour-le-conteneur)
11. [Étape 8 — Le `Dockerfile` et le `.dockerignore`](#11-%C3%A9tape-8--le-dockerfile-et-le-dockerignore)
12. [Étape 9 — Construire l'image](#12-%C3%A9tape-9--construire-limage)
13. [Étape 10 — Lancer le conteneur : les deux obstacles](#13-%C3%A9tape-10--lancer-le-conteneur--les-deux-obstacles)
14. [Étape 11 — Tester](#14-%C3%A9tape-11--tester)
15. [Les trois architectures, en schémas](#15-les-trois-architectures-en-sch%C3%A9mas)
16. [Récapitulatif : environnements, shells, terminaux, ports](#16-r%C3%A9capitulatif--environnements-shells-terminaux-ports)
17. [Différences avec le setup `web-service`](#17-diff%C3%A9rences-avec-le-setup-web-service)
18. [Dépannage](#18-d%C3%A9pannage)
19. [Cheat sheet des commandes](#19-cheat-sheet-des-commandes)

---

## 1. Le vocabulaire, d'abord

C'est la partie qui t'a le plus gêné, alors on la pose proprement avant tout le reste. Cinq mots qu'on emploie comme des synonymes alors qu'ils désignent cinq choses différentes.

### Terminal

Une **fenêtre**. Clavier + écran. C'est un meuble, rien d'autre : il n'exécute rien lui-même, il affiche. Dans VS Code, chaque onglet du panneau du bas est un terminal.

> Un terminal **n'appartient à rien**. Il n'existe pas de « terminal de gunicorn » ou de « terminal de Docker ». Si l'instructeur réutilise le terminal 1 pour autre chose, c'est simplement qu'il a fait `Ctrl+C` et que le terminal s'est libéré.

### Shell

Le **programme** qui tourne dans le terminal, lit ce que tu tapes et lance les programmes correspondants. Chez toi, c'est `bash`.

Un shell est un **processus vivant qui maintient un état** :

- un répertoire courant (`pwd`)
- un jeu de variables d'environnement (`PATH`, `MODEL_URI`…)

C'est important : **cet état ne sort pas du shell**. Un `export MODEL_URI=...` dans le terminal 1 n'existe pas dans le terminal 2.

### Processus

Un **programme en cours d'exécution**. `python predict.py` lance un processus. `mlflow server` en lance un autre. Chacun a son propre identifiant (PID), sa propre mémoire, ses propres fichiers ouverts.

Distinction utile :

| Type de processus | Comportement | Exemple |
|---|---|---|
| **Éphémère** | s'exécute, affiche, se termine, rend le terminal | `python test.py`, `ls`, `docker build` |
| **Long-running** (serveur) | ne se termine jamais tout seul, **bloque son terminal** | `mlflow server`, `python predict.py`, `gunicorn` |

**La règle qui explique tout** : un processus qui bloque monopolise son terminal. Il t'en faut donc un autre pour faire autre chose pendant ce temps. C'est la seule et unique raison pour laquelle ce chapitre demande trois terminaux.

### Service

Un processus long-running **qui écoute sur un port réseau** et répond à des requêtes. Ton `predict.py` lancé est un service. `mlflow server` en est un autre.

Un service a deux caractéristiques :

- il **attend** (il ne fait rien tant qu'on ne l'appelle pas)
- il est joignable par une **adresse + un port** (`localhost:9696`)

> Quand on dit « arrête le service », on veut dire : `Ctrl+C` dans le terminal où il tourne.

### Environnement

Un **jeu d'interpréteur Python + bibliothèques**. Rien de plus.

La mécanique est plus simple qu'elle n'en a l'air. `PATH` est une liste de dossiers séparés par `:`. Quand tu tapes `python`, le shell parcourt cette liste **de gauche à droite** et exécute le **premier** exécutable trouvé.

```bash
echo $PATH | tr ':' '\n'
```

**Activer un environnement, c'est mettre son dossier `bin/` en tête de cette liste.** `conda activate`, `pipenv shell`, `source venv/bin/activate` : tous font exactement ça. Aucune magie.

La question à se poser devant une commande est donc toujours la même :

> Cette commande a-t-elle besoin de bibliothèques Python installées quelque part ?

Si oui → active le bon environnement. Si non (`docker`, `curl`, `lsof`, `kill`) → peu importe.

### Shell parent, shell enfant

Un shell peut en lancer un autre. L'enfant reçoit une **copie** de l'environnement du parent, et ce qu'il modifie ne remonte jamais au parent.

C'est ce qui explique le prompt bizarre `(web-service) (base)` que tu avais au chapitre précédent :

```
shell parent           PATH = [conda/mlopszoomcamp/bin, ...]
│                      prompt : (mlopszoomcamp)
│
└─ pipenv shell  →  shell ENFANT
                       1. bash démarre, relit ~/.bashrc depuis le début
                       2. ~/.bashrc contient le hook conda → active base
                       3. pipenv ajoute son virtualenv en tête
                       prompt : (web-service) (base)
```

Les deux préfixes ne disent pas **où tu es**. Ils disent **quels activateurs sont passés par là**. Seul `which python` fait foi.

> C'est pour ça que `pipenv run <commande>` est préférable à `pipenv shell` : il n'ouvre pas de sous-shell, donc `~/.bashrc` n'est jamais relu, donc conda n'a aucune occasion de s'interposer.

### Le tableau qui résume

| Mot | Ce que c'est | Combien il y en a ici |
|---|---|---|
| Terminal | une fenêtre | 3 (par confort) |
| Shell | le programme qui lit tes commandes | 1 par terminal |
| Processus | un programme en cours | autant que de commandes lancées |
| Service | un processus qui écoute un port | 2 (MLflow:5000, prédiction:9696) |
| Environnement | interpréteur + bibliothèques | 2 (conda `mlopszoomcamp`, pipenv du dossier) + 1 dans l'image Docker |

---

## 2. L'architecture cible

Voilà où on va, pour avoir la carte avant de marcher.

```
                    CODESPACE (une machine Linux)
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│  Terminal 1                Terminal 2              Terminal 3    │
│  ┌──────────────┐          ┌──────────────┐       ┌───────────┐  │
│  │ mlflow server│          │  le service  │       │  test.py  │  │
│  │  port 5000   │◄─────────│  port 9696   │◄──────│  (client) │  │
│  │              │  1 fois  │              │  à    │           │  │
│  │ registre :   │  au      │ Flask dev    │ chaque│ s'exécute │  │
│  │ métadonnées  │  démar-  │   OU gunicorn│ requê-│ et rend   │  │
│  │ + artifacts  │  rage    │   OU Docker  │ te    │ la main   │  │
│  └──────────────┘          └──────────────┘       └───────────┘  │
│         ▲                                                        │
│         │ sqlite mlflow.db + dossier artifacts/                  │
└──────────────────────────────────────────────────────────────────┘
```

Deux moments distincts, et c'est la clé :

- **Au démarrage du service** : il interroge le 5000 pour résoudre `models:/m-…`, télécharge le modèle, le charge en mémoire.
- **À chaque requête** : le client envoie du JSON au 9696, qui répond. **MLflow n'est plus sollicité.**

Ce découplage est intentionnel : charger un modèle est coûteux, on le fait **une fois**. C'est pour ça que la ligne `load_model` est au niveau du module, en dehors de toute fonction.

La colonne du milieu est la seule qui bouge au fil du chapitre :

| Étape | Terminal 2 |
|---|---|
| Développement | `python predict.py` (serveur de dev Flask) |
| Production locale | `gunicorn --bind=0.0.0.0:9696 predict:app` |
| Production empaquetée | `docker run … ride-duration-prediction-service:v2` |

Et le terminal 3 ne change **jamais** : `python test.py`. C'est ton point de repère fixe.

> Ce schéma est volontairement grossier — il vaut pour les trois variantes à la fois. Le **§15** reprend chacune en détail, avec ce qui se passe au démarrage et à chaque requête. N'y va pas tout de suite : il n'a d'intérêt qu'une fois les trois étapes traversées.

---

## 3. Étape 0 — Lancer le serveur MLflow et entraîner

### Prérequis : les données

⚠️ Avant toute chose, vérifie que les deux fichiers de données sont là. Le `.gitignore` du dépôt exclut `data/`, `*.parquet`, `*.db` et `**/artifacts/` : après un clone frais, le notebook lèvera un `FileNotFoundError` à la cellule 4.

```bash
cd /workspaces/mlops-zoomcamp/04-deployment/web-service-mlflow
ls data/green_tripdata_2021-0[12].parquet || (
  mkdir -p data && cd data
  wget https://d37ci6vzurychx.cloudfront.net/trip-data/green_tripdata_2021-01.parquet
  wget https://d37ci6vzurychx.cloudfront.net/trip-data/green_tripdata_2021-02.parquet
)
```

### La commande

```bash
conda activate mlopszoomcamp
cd /workspaces/mlops-zoomcamp/04-deployment/web-service-mlflow

mlflow server \
  --backend-store-uri sqlite:////workspaces/mlops-zoomcamp/04-deployment/web-service-mlflow/mlflow.db \
  --default-artifact-root /workspaces/mlops-zoomcamp/04-deployment/web-service-mlflow/artifacts \
  --host 0.0.0.0 \
  --port 5000
```

### Chaque drapeau

| Drapeau | Rôle |
|---|---|
| `--backend-store-uri` | où stocker les **métadonnées** : runs, params, métriques, tags. Ici une base SQLite dans un fichier. |
| `--default-artifact-root` | où stocker les **fichiers** : modèles sérialisés, graphiques… Ici un dossier local. |
| `--host` | sur quelles interfaces réseau écouter |
| `--port` | sur quel port |

> **Le quadruple slash** de `sqlite:////workspaces/...` n'est pas une faute de frappe. La forme complète est `sqlite://<hôte>/<chemin>`. L'hôte est vide (la base est locale), ce qui donne déjà `sqlite:///` ; puis le chemin absolu ajoute son propre `/` en tête — quatre barres au total.
>
> Trois barres = chemin **relatif** au répertoire courant. Quatre = chemin **absolu**. C'est une source d'erreur classique : la base se crée au mauvais endroit et tu ne retrouves plus tes runs.

### `--host 0.0.0.0` et non `127.0.0.1`

C'est la correction la plus importante de cette étape, et elle t'a coûté du temps.

| Adresse | Signification |
|---|---|
| `127.0.0.1` (= `localhost`) | « n'accepte que les connexions **venant de cette machine** » |
| `0.0.0.0` | « accepte les connexions sur **toutes mes interfaces réseau** » |

`0.0.0.0` n'est pas une adresse de destination : c'est un joker **côté serveur** qui veut dire « n'importe laquelle de mes adresses ». On ne s'y connecte jamais, on écoute dessus.

Tant que tout tourne sur le Codespace, `127.0.0.1` suffit. Mais un conteneur Docker est, du point de vue réseau, **une machine distincte** : ses requêtes arrivent par une autre interface, et MLflow les refuse.

Ce n'est pas « MLflow n'existe pas », c'est « MLflow n'accepte pas les connexions venant de là ». Le symptôme est identique (`Connection refused`), la cause est différente.

> Le piège de diagnostic : un `curl http://127.0.0.1:5000` **depuis le Codespace** réussit, parce que la requête passe par la boucle locale. Tu conclus « le serveur tourne, donc ce n'est pas lui ». Sauf que la question n'est pas « tourne-t-il ? » mais « accepte-t-il les connexions venant d'où j'appelle ? ».

Mets `0.0.0.0` dès le départ, ça t'évitera de tout relancer plus tard.

> Tu recroiseras cette distinction quatre fois dans ce chapitre. Le tableau de synthèse est au **§16** (« `0.0.0.0` vs `127.0.0.1` — le tableau à retenir ») ; les occurrences suivantes y renvoient plutôt que de tout réexpliquer.

### Ce que produit le notebook

Le notebook (`random-forest.ipynb`, voir l'autre document) produit une chaîne :

```
models:/m-5e276730f7004842b7c3a36ea11b5044
```

C'est le seul livrable de cette étape, et le contrat avec le reste du chapitre.

> ⚠️ **Cet identifiant est cité partout dans ces notes, et il meurt au premier réentraînement.** Il ne vaut que pour *ton* `mlflow.db` actuel. Si tu relances la cellule 5 ou si tu repars d'une base neuve, tu obtiens un nouveau `m-…`. Ne le recopie jamais depuis ces notes : relis-le dans `model_info.model_uri` (cellule 6 du notebook). C'est la leçon du `RUN_ID` codé en dur du cours, appliquée à ce document-ci.

---

## 4. Étape 1 — `predict.py`, ligne par ligne

### Le fichier complet (version finale, prête pour Docker)

```python
import os
import mlflow
from flask import Flask, request, jsonify

# --- 1. Configuration, lue dans l'environnement ---
MLFLOW_TRACKING_URI = os.getenv('MLFLOW_TRACKING_URI', 'http://127.0.0.1:5000')
mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)

MODEL_URI = os.getenv('MODEL_URI')
if MODEL_URI is None:
    raise RuntimeError(
        "MODEL_URI n'est pas définie : export MODEL_URI='models:/m-…' "
        "(ou docker run -e MODEL_URI=…)"
    )

# --- 2. Chargement du modèle : UNE SEULE FOIS, au démarrage ---
model = mlflow.pyfunc.load_model(MODEL_URI)

# --- 3. Les fonctions métier ---
def prepare_features(ride):
    features = {}
    features['PU_DO'] = '%s_%s' % (ride['PULocationID'], ride['DOLocationID'])
    features['trip_distance'] = ride['trip_distance']
    return features

def predict(features):
    preds = model.predict(features)
    return float(preds[0])

# --- 4. L'application Flask ---
app = Flask('duration-prediction')

@app.route('/predict', methods=['POST'])
def predict_endpoint():
    ride = request.get_json()
    features = prepare_features(ride)
    pred = predict(features)

    result = {
        'duration': pred,
        'model_version': MODEL_URI
    }
    return jsonify(result)

# --- 5. Le point d'entrée en développement ---
if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=9696)
```

> La garde `if MODEL_URI is None` n'est **pas encore dans ton dépôt** : c'est l'ajout que ces notes recommandent, expliqué au Bloc 1. Tout le reste est le fichier tel qu'il est.

### Bloc 1 — La configuration sort du code

```python
MLFLOW_TRACKING_URI = os.getenv('MLFLOW_TRACKING_URI', 'http://127.0.0.1:5000')
mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
MODEL_URI = os.getenv('MODEL_URI')
```

**`os.getenv(nom)`** lit une variable d'environnement du processus. C'est le pont entre le shell et Python.

**`os.getenv(nom, défaut)`** avec deux arguments : le second est la valeur utilisée si la variable n'existe pas.

Le principe derrière : **séparer le code de sa configuration**. Le code dit *comment* servir un modèle ; la variable dit *lequel*. Réentraîner ne demande alors aucune modification de code — juste une nouvelle valeur.

Remarque la dissymétrie, elle est délibérée :

| Variable | Défaut ? | Pourquoi |
|---|---|---|
| `MLFLOW_TRACKING_URI` | oui (`http://127.0.0.1:5000`) | en local c'est toujours ça ; le défaut évite un `export` de plus |
| `MODEL_URI` | **non** | mieux vaut un plantage immédiat qu'un modèle codé en dur servi silencieusement |

C'est la leçon la plus transférable de ce fichier : **un défaut qui prend le relais sans bruit est un incident en préparation.** Mieux vaut échouer fort et tôt.

**Fort, tôt — et lisible.** Sans le `if MODEL_URI is None`, l'échec est bien immédiat, mais `load_model(None)` produit une traceback qui parle de MLflow, pas de ta variable (voir plus bas). Les trois lignes de garde ne coûtent rien et transforment vingt minutes de recherche en une lecture. C'est la vraie fin de l'argument : un échec précoce n'a de valeur que si son message désigne la cause.

### Réponse à ta question : faut-il faire `export MODEL_URI` ?

Oui, **à chaque fois que tu lances le service hors Docker**, et **dans le terminal où tu le lances**.

```bash
export MODEL_URI='models:/m-5e276730f7004842b7c3a36ea11b5044'
echo $MODEL_URI                       # vérification
python predict.py
```

Trois choses à savoir :

- La variable ne vit que dans **ce shell**. Nouveau terminal → nouvel `export`. Ce n'est pas un réglage du projet, c'est un état de processus.
- Elle est héritée par les **processus enfants**. C'est pour ça que `python predict.py`, lancé depuis ce shell, la voit.
- En Docker, l'équivalent est `-e MODEL_URI='...'` sur le `docker run`. Ton `export` local n'a **aucun effet** sur un conteneur : un conteneur ne partage pas l'environnement de ton shell.

**À quoi ressemble l'oubli.** C'est de loin l'erreur numéro un de ce chapitre, et le message ne te dit pas « tu as oublié l'export ». Sans la garde ajoutée au Bloc 1, `os.getenv('MODEL_URI')` rend `None`, puis `load_model(None)` plante sur une URI invalide ou un `NoneType` — une traceback qui parle de MLflow, pas de ta variable. Avec la garde, le message te dit quoi faire. D'où le réflexe : **`echo $MODEL_URI` avant chaque lancement**, et la ligne correspondante dans le tableau de dépannage du §18.

> Si tu en as assez de retaper l'`export`, un fichier `.env` à la racine du dossier fait l'affaire (`python-dotenv`, ou `set -a; source .env; set +a`). Mais alors **ajoute-le au `.gitignore` et au `.dockerignore`** — c'est le genre de fichier qui finit par contenir des credentials.

### Bloc 2 — Le chargement, hors de toute fonction

```python
model = mlflow.pyfunc.load_model(MODEL_URI)
```

Cette ligne est au **niveau du module**, pas dans une fonction. Elle s'exécute donc **une fois, au démarrage** du processus.

Si tu la mettais dans `predict_endpoint()`, tu téléchargerais et rechargerais le modèle **à chaque requête**. Sur un modèle de quelques centaines de Ko, ce serait déjà 100× plus lent. Sur un modèle d'un Go, le service serait inutilisable.

C'est un motif qu'on retrouve partout : **ce qui est coûteux et invariant se fait au démarrage.** Connexions à une base, chargement d'un modèle, lecture d'une configuration.

**`pyfunc` plutôt que `sklearn`** : `mlflow.pyfunc.load_model` charge le modèle comme une boîte noire exposant `.predict()`. Le service n'a pas à savoir s'il sert un scikit-learn, un XGBoost ou un PyTorch. C'est ce qui rend ce fichier réutilisable tel quel pour un autre modèle.

### Bloc 3 — Les fonctions métier

```python
def prepare_features(ride):
    features = {}
    features['PU_DO'] = '%s_%s' % (ride['PULocationID'], ride['DOLocationID'])
    features['trip_distance'] = ride['trip_distance']
    return features
```

Transforme la requête brute du client en dictionnaire de features, dans le format attendu par le `DictVectorizer` du pipeline.

Le `'%s_%s' % (a, b)` est l'ancienne syntaxe de formatage Python. L'équivalent moderne : `f"{a}_{b}"`. Les deux marchent ; la f-string est plus lisible.

```python
def predict(features):
    preds = model.predict(features)
    return float(preds[0])
```

**Deux lignes seulement**, alors que dans `web-service/predict.py` il y en avait trois :

```python
# web-service — l'ancien
X = dv.transform(features)      # ← disparue
preds = model.predict(X)
return float(preds[0])
```

La vectorisation est maintenant **dans le pipeline**. C'est le gain concret du `make_pipeline` expliqué dans l'autre document.

**Le `float()`** convertit le `numpy.float64` renvoyé par scikit-learn en float Python natif. Sans lui, `jsonify` lève une `TypeError: Object of type float64 is not JSON serializable`. Petit détail, grande cause d'erreur.

**Le `[0]`** : `predict` renvoie toujours un tableau, même pour une seule observation. On prend le premier élément.

### Bloc 4 — L'application Flask

```python
app = Flask('duration-prediction')
```

Crée l'objet application. L'argument est un nom, utilisé dans les logs et pour localiser les ressources. **C'est cet objet `app` que gunicorn ira chercher** — retiens-le, c'est le sens du `predict:app` plus loin.

```python
@app.route('/predict', methods=['POST'])
def predict_endpoint():
```

Le `@` introduit un **décorateur** : une fonction qui en enveloppe une autre pour lui ajouter un comportement. Ici, `app.route` enregistre `predict_endpoint` dans la table de routage de Flask.

Traduction : « quand une requête HTTP **POST** arrive sur le chemin **`/predict`**, exécute cette fonction ». D'où l'URL complète côté client : `http://localhost:9696/predict`.

**Pourquoi POST et pas GET ?** GET transmet ses paramètres dans l'URL (`?distance=40`) : visible dans les logs, limité en taille, mis en cache par les proxies. POST transmet dans le **corps** de la requête, ce qui permet d'envoyer une structure JSON complète. Convention : GET pour *lire* une ressource, POST pour *soumettre des données à traiter*.

```python
ride = request.get_json()
...
return jsonify(result)
```

`request.get_json()` parse le corps JSON de la requête en dictionnaire Python. `jsonify()` fait l'inverse en sortie : dictionnaire Python → JSON, **plus** l'en-tête `Content-Type: application/json`. C'est cet en-tête qui permet au client de faire `response.json()`.

```python
result = {
    'duration': pred,
    'model_version': MODEL_URI
}
```

**Renvoyer la version du modèle dans la réponse est une bonne pratique de production.** En cas d'incident, tu peux relier chaque prédiction au modèle exact qui l'a produite. Sans ça, « les prédictions étaient bizarres mardi » est une enquête ; avec ça, c'est une requête.

### Bloc 5 — La garde `if __name__ == "__main__"`

```python
if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=9696)
```

`__name__` est une variable que Python met automatiquement dans chaque module :

- si le fichier est **lancé directement** (`python predict.py`) → `__name__` vaut `"__main__"`
- si le fichier est **importé** par un autre programme → `__name__` vaut `"predict"`

Conséquence, et c'est tout l'intérêt :

| Commande | `__name__` | `app.run()` s'exécute ? | Résultat |
|---|---|---|---|
| `python predict.py` | `"__main__"` | oui | serveur de développement Flask |
| `gunicorn predict:app` | `"predict"` | **non** | gunicorn gère le réseau lui-même |

**Le même fichier sert dans les deux cas, sans modifier une seule ligne.** C'est une des constructions les plus élégantes du chapitre.

`debug=True` active le rechargement automatique : Flask surveille tes fichiers et redémarre dès que tu en sauvegardes un. Pratique en dev, à proscrire en production (il expose un débogueur interactif).

> **Pourquoi tu vois les logs MLflow passer deux fois au lancement.** Le rechargeur fonctionne en lançant un processus *superviseur* qui démarre à son tour le vrai processus applicatif. Les deux importent `predict.py`, donc `load_model` s'exécute **deux fois**. Tu n'as rien cassé. Et ça confirme au passage le point du §4 : le chargement a lieu à l'import du module, pas à la première requête.

### Les blocs commentés en tête de ton fichier

Ton `predict.py` conserve trois versions historiques en commentaire :

```python
# RUN_ID = os.getenv('RUN_ID')
# logged_model = f's3://mlflow-models-alexey/1/{RUN_ID}/artifacts/model'   → cours, MLflow 2
# logged_model = f'runs:/{RUN_ID}/model'                                   → MLflow 2
```

```python
'''
mlflow.set_tracking_uri("http://127.0.0.1:5000")
MODEL_URI = os.getenv('MODEL_URI', 'models:/m-5e276730f...')
model = mlflow.pyfunc.load_model(MODEL_URI)
'''
```

C'est utile pour apprendre — on voit l'évolution. C'est encombrant pour un fichier qu'on garde. Si tu veux conserver la trace, elle appartient à ce document de notes, pas au fichier de production.

Dans la même famille : ton `predict.py` commence encore par `import pickle`, hérité de la version `web-service`. Plus rien ne l'utilise depuis que le modèle vient de MLflow. Un import mort ne coûte rien à l'exécution, mais il raconte une histoire fausse à qui lit le fichier.

> Attention aussi : le bloc entre `'''` n'est pas un commentaire au sens strict. C'est une **chaîne de caractères** évaluée puis jetée. En tête de module, Python la prendrait même pour une *docstring*. Ça fonctionne, mais le vrai commentaire multi-ligne en Python, c'est `#` sur chaque ligne (ou `Cmd+/` dans VS Code).

---

## 5. Étape 2 — `test.py`, le client

```python
import requests

ride = {
    "PULocationID": 10,
    "DOLocationID": 50,
    "trip_distance": 40
}

url = 'http://localhost:9696/predict'
response = requests.post(url, json=ride)
print(response.json())
```

Quatre choses à comprendre.

**`test.py` ne fait pas partie du déploiement.** C'est un client de test qui simule ce que ferait l'application appelante — le backend de l'appli de taxi, par exemple. Il ne sera **jamais** dans l'image Docker.

**`requests.post(url, json=ride)`** : l'argument `json=` sérialise automatiquement le dictionnaire et pose l'en-tête `Content-Type: application/json`. Avec `data=`, il faudrait faire les deux à la main.

**`response.json()`** parse la réponse JSON en dictionnaire Python.

**`test.py` ne change JAMAIS.** C'est le point central du chapitre, et la réponse à la question que tu posais : comment tester quand on passe de Flask à gunicorn, puis à Docker ?

| Étape | Terminal 2 (serveur) | Terminal 3 (client) |
|---|---|---|
| Flask dev | `python predict.py` | `python test.py` |
| Gunicorn | `gunicorn --bind=0.0.0.0:9696 predict:app` | `python test.py` |
| Docker | `docker run … ride-duration-prediction-service:v2` | `python test.py` |

Une seule colonne bouge.

`test.py` envoie une requête HTTP à `http://localhost:9696/predict`. Il ne sait pas — et n'a aucun moyen de savoir — ce qu'il y a derrière ce port. Serveur de dev, gunicorn, conteneur : pour lui c'est identique.

**C'est ça, une interface.** Le contrat, c'est l'URL et le format des messages. L'implémentation derrière peut changer complètement — de serveur, de langage, de machine, de modèle — sans que le client s'en aperçoive.

> Le test de compréhension : lance le conteneur, puis dans le terminal 3, au lieu de `test.py`, envoie la requête à la main.
>
> ```bash
> curl -X POST http://localhost:9696/predict \
>   -H "Content-Type: application/json" \
>   -d '{"PULocationID": 10, "DOLocationID": 50, "trip_distance": 40}'
> ```
>
> `curl` ne connaît ni Python, ni Flask, ni ton modèle. Il parle HTTP, et ça suffit.
>
> Essaie aussi avec `"PULocationID": "10"` (une chaîne) : ça marche encore, parce que le `'%s_%s'` de `prepare_features` gomme la différence. Pratique — et dangereux : le service accepte n'importe quel type sans broncher. C'est exactement l'ambiguïté qu'une *signature* MLflow (voir `04-python-web-service-mlflow.md`, §11) rendrait explicite.

### Serveur et client : deux programmes, deux terminaux

| | `predict.py` | `test.py` |
|---|---|---|
| Rôle | serveur — il **attend** | client — il **demande** |
| Durée de vie | tourne en permanence | s'exécute en une seconde et se termine |
| Effet sur le terminal | le bloque jusqu'au `Ctrl+C` | le rend immédiatement |

Lancer `test.py` sans serveur actif donne cette erreur — lis-la jusqu'au bout, l'information utile est à la fin :

```
requests.exceptions.ConnectionError: HTTPConnectionPool(host='localhost', port=9696):
Max retries exceeded with url: /predict
(Caused by NewConnectionError(... [Errno 111] Connection refused))
```

`requests` enveloppe l'erreur système dans la sienne : ce n'est donc pas `ConnectionRefusedError` que tu dois chercher dans un moteur de recherche, mais `[Errno 111] Connection refused`. C'est le premier réflexe de debug : *le serveur tourne-t-il vraiment ?*

---

## 6. Étape 3 — Le serveur de développement Flask

```bash
conda activate mlopszoomcamp
export MODEL_URI='models:/m-5e276730f7004842b7c3a36ea11b5044'
python predict.py
```

Tu obtiens un avertissement en rouge :

```
WARNING: This is a development server. Do not use it in a production deployment.
```

Il est justifié, mais pas pour la raison qu'on croit. Le serveur de développement vient de **Werkzeug**, la bibliothèque WSGI sur laquelle Flask est bâti. Contrairement à une idée répandue, il **traite bien plusieurs requêtes en parallèle** : `app.run()` active `threaded=True` par défaut depuis Flask 1.0.

Ce qui lui manque est tout le reste :

- aucune gestion de charge, aucun timeout configurable
- aucun redémarrage automatique si le processus meurt
- non durci contre les requêtes malveillantes
- un crash fait tomber le serveur entier

Il est parfait pour développer — notamment grâce au rechargement automatique de `debug=True`. Il n'a rien à faire en production.

### Pour l'arrêter

`Ctrl+C` dans le terminal où il tourne. (`Ctrl`, pas `Cmd`, même sur Mac : les raccourcis de terminal suivent la convention Unix.)

Ce n'est pas un « bouton stop » : c'est l'envoi d'un **signal** au processus, appelé `SIGINT` (*signal interrupt*). Le système dit poliment au programme « on te demande de t'arrêter », et le programme peut fermer proprement ses connexions avant de quitter.

Si jamais ça résiste, depuis un **autre** terminal :

```bash
lsof -i :9696     # qui occupe le port ?
kill <PID>        # demande d'arrêt (SIGTERM)
kill -9 <PID>     # arrêt forcé (SIGKILL), en dernier recours
```

Le `-9` envoie `SIGKILL`, que le processus **ne peut pas intercepter** : il est tué net, sans possibilité de fermer quoi que ce soit. À réserver aux cas désespérés.

> Bon à savoir pour Docker : c'est ce même mécanisme de signaux qui explique la *forme JSON* de l'`ENTRYPOINT` (voir §11).

---

## 7. Étape 4 — Passer à gunicorn

### Ce n'est pas « Flask ou gunicorn »

La confusion vient de ce que Flask remplit **deux rôles distincts** :

| Rôle | Qui le remplit | Devenir |
|---|---|---|
| **Le framework** — routage, parsing JSON, `jsonify` | Flask | **conservé** |
| **Le serveur HTTP** — connexions, concurrence, workers | Werkzeug (dev) → **gunicorn** | **remplacé** |

Gunicorn ne remplace pas Flask : il l'**exécute**. Ton code métier ne change pas d'une ligne.

### Le contrat : WSGI

*WSGI* (*Web Server Gateway Interface*, PEP 3333) est la norme Python qui définit comment un serveur HTTP et une application Python se parlent.

Flask expose une application conforme WSGI. Gunicorn est un serveur WSGI. C'est pour ça qu'ils sont interchangeables : n'importe quel serveur WSGI pourrait exécuter ton app Flask, et gunicorn pourrait exécuter du Django.

> Flask écrit le contenu, gunicorn est l'imprimerie.

### La commande

```bash
gunicorn --bind=0.0.0.0:9696 predict:app
```

**`predict:app`** se lit : « dans le module `predict` (le fichier `predict.py`), prends l'objet nommé `app` ». Gunicorn **importe** ton fichier et récupère l'application Flask.

C'est ici que la garde `if __name__ == "__main__"` prend tout son sens : à l'import, `__name__` vaut `"predict"`, donc `app.run()` ne s'exécute pas, et gunicorn gère le réseau lui-même.

**`--bind=0.0.0.0:9696`** : écouter sur toutes les interfaces, port 9696. Le `0.0.0.0` deviendra indispensable en conteneur — voir §13.

### Les workers

Par défaut, gunicorn lance **un seul worker**. Pour exploiter la concurrence :

```bash
gunicorn --bind=0.0.0.0:9696 --workers=4 predict:app
```

Règle empirique : `(2 × nombre de cœurs) + 1`. Ton Codespace ayant 2 cœurs, reste autour de 4–5.

> ⚠️ **Écart à signaler dans ton dépôt** : l'`ENTRYPOINT` de ton `Dockerfile` ne passe **aucun** `--workers`. Ton image dite « de production » tourne donc avec un worker unique. Ce n'est pas grave pour apprendre, mais ne te raconte pas que l'image est prête pour la production : il y manque au minimum `--workers` et `--timeout`.

**Attention** : chaque worker charge sa **propre copie** du modèle en mémoire. Avec un modèle de quelques centaines de Ko, sans importance. Avec un modèle d'un Go sur une machine à 8 Go, le nombre de workers devient un calcul, et la RAM devient le facteur limitant avant le CPU.

> Nuance : `--preload` change la donne. Le maître importe alors `predict.py` **une fois** — donc charge le modèle une fois — puis *forke* les workers, qui héritent de sa mémoire en copie-sur-écriture. Tant que personne n'écrit dans le modèle, la RAM n'est payée qu'une fois. Le prix : un redémarrage de worker ne relit plus le code.

**Le piège gunicorn de ce chapitre.** Un worker a **30 secondes** par défaut pour démarrer. Or ton démarrage inclut la résolution de `models:/` et le téléchargement du modèle. Si ça dépasse — réseau lent, gros modèle — gunicorn tue le worker avec `[CRITICAL] WORKER TIMEOUT`, en relance un, qui retélécharge, qui est tué… Le service ne répond jamais et le terminal défile. La parade : `--timeout 120` (ou `--preload`, qui charge dans le maître, hors du chrono des workers). C'est dans le tableau de dépannage du §18.

### Rien n'est « par défaut » ni persistant

Installer gunicorn ne change **rien** automatiquement. Il n'existe aucune configuration mémorisée quelque part disant « ce projet tourne avec gunicorn ». Il n'y a qu'un **processus vivant**, issu de la commande que tu as tapée. Ferme le terminal, relance `python predict.py` demain : tu es de retour sur le serveur de dev.

Et les deux ne peuvent pas cohabiter : **un port ne peut être *lié* qu'une seule fois**. Lancer `python predict.py` pendant que gunicorn écoute sur 9696 donne `OSError: [Errno 98] Address already in use`.

> Nuance pour plus tard : gunicorn avec plusieurs workers n'y déroge pas. Le processus maître lie le port **une fois**, et les workers héritent de la même socket d'écoute. Chacun appelle `accept()` dessus de son côté ; c'est le **noyau** qui attribue chaque connexion entrante à l'un d'eux — le maître ne distribue rien, il surveille et redémarre les workers.

C'est au `ENTRYPOINT` du Dockerfile que gunicorn deviendra enfin un vrai « par défaut » — parce qu'il sera alors **du code versionné dans git**, et non plus une commande à se rappeler.

---

## 8. Étape 5 — Relever les versions exactes

C'est l'étape que l'on saute et qu'on regrette.

```bash
conda activate mlopszoomcamp
cd /workspaces/mlops-zoomcamp/04-deployment/web-service-mlflow
python -c "import sys, sklearn, mlflow; print(sys.version.split()[0], sklearn.__version__, mlflow.__version__)"
```

```
3.11.16 1.9.0 3.16.0
```

### Pourquoi c'est critique

Ton modèle a été sérialisé par **ces versions précises**. Le pickle Python ne stocke pas les objets, il stocke des **instructions de reconstruction** qui référencent des classes. Si la structure interne d'une classe a changé entre deux versions de scikit-learn, la reconstruction casse.

Si le conteneur installe d'autres versions, tu retombes sur le problème de dépicklage du chapitre précédent — sauf que cette fois, c'est **toi** qui auras créé l'incompatibilité.

### L'alternative : demander à MLflow

Pour un modèle MLflow, tu n'as même pas besoin d'interroger ton environnement : le dossier du modèle contient un `requirements.txt` et un `conda.yaml` qui donnent la réponse directement.

```python
for a in mlflow.artifacts.list_artifacts(artifact_uri=model_info.model_uri):
    print(a.path)
# MLmodel, conda.yaml, model.skops, python_env.yaml, requirements.txt
```

**Lis ce `requirements.txt` avant d'écrire ton `Pipfile`.** Il liste les versions exactes avec lesquelles *ce modèle-là* a été écrit, et il t'apprend un nom que tu n'aurais pas deviné : **`skops`**, le format de sérialisation utilisé par MLflow 3 à la place du pickle (voir `04-python-web-service-mlflow.md`, §7).

Pour le lire, et non seulement le lister, il faut aller chercher son contenu — depuis le notebook, ou depuis un `python` lancé dans `mlopszoomcamp` :

```python
import mlflow
mlflow.set_tracking_uri("http://127.0.0.1:5000")
MODEL_URI = 'models:/m-5e276730f7004842b7c3a36ea11b5044'
print(mlflow.artifacts.load_text(MODEL_URI + "/requirements.txt"))
```

> `list_artifacts` ne rend que des **noms** de fichiers ; `load_text` rend leur **contenu**. Et si tu lances le snippet précédent depuis un terminal frais, `model_info` n'existe pas — c'est une variable du notebook. D'où l'URI en dur ici.

> Pour un pickle fait à la main (comme `lin_reg.bin`), il faut fouiller les octets :
> ```bash
> strings lin_reg.bin | grep -A2 _sklearn_version
> ```
> On lit le fichier sans rien désérialiser. Aucun besoin d'avoir scikit-learn installé.
>
> C'est un des bénéfices peu cités de MLflow : **il écrit l'environnement à côté du modèle**.

---

## 9. Étape 6 — Créer le pipenv

### Pourquoi il n'en fallait pas jusqu'ici

Question légitime : au chapitre `web-service`, on créait un pipenv **dès le début**. Ici, on a fait tourner `predict.py` et gunicorn sans rien créer. Pourquoi ?

Parce que **c'est toi qui viens d'entraîner le modèle**, dans `mlopszoomcamp`. Le modèle a été sérialisé avec exactement les versions présentes dans cet environnement. Quand `predict.py` le recharge depuis ce même environnement, les versions correspondent nécessairement.

Le problème d'incompatibilité n'existe pas, parce que **producteur et consommateur sont le même environnement**.

Au chapitre précédent, c'était l'inverse : le `.bin` venait du cours, pické avec scikit-learn 1.0.2, et ton environnement était en 1.9.0. D'où la cascade pipenv → Python 3.10 → `numpy<2`.

### Quand il redevient nécessaire

**Au moment du Docker.** Là, tu construis un environnement **neuf**, vide, à partir d'une image de base. Tu dois donc déclarer explicitement ce qu'il faut y installer.

Le principe général, à retenir :

> **Un environnement isolé est nécessaire quand le code va s'exécuter ailleurs que là où il a été développé.**

### Les commandes

```bash
conda activate mlopszoomcamp
cd /workspaces/mlops-zoomcamp/04-deployment/web-service-mlflow

rm -f Pipfile Pipfile.lock          # ⚠️ UNE SEULE FOIS — voir l'avertissement ci-dessous
pipenv install --python=3.11 scikit-learn==1.9.0 mlflow==3.16.0 skops==0.14.0 flask gunicorn
```

> ⚠️ **Le `rm -f` est à faire une seule fois**, pour jeter les fichiers livrés par le cours (ils datent de 2022). Dès la deuxième lecture de ce document, le `Pipfile` de ce dossier sera **le tien** : ne le supprime pas, tu perdrais tes versions épinglées. Si un `Pipfile` correct est déjà là, saute cette ligne et fais simplement `pipenv sync` (pas `pipenv install`, qui peut re-résoudre le lock si `Pipfile` et `Pipfile.lock` ont divergé — voir §19).

> `--python=3.11` et non `3.11.16` : pipenv écrit cette contrainte dans `[requires]`, et c'est elle que `--deploy` vérifiera dans l'image. Avec la version complète, tu obtiens `python_full_version = "3.11.16"` — c'est l'état actuel de ton `Pipfile` — et une image `python:3.11-slim` peut être refusée, voir §11.
>
> `conda activate` avant `pipenv install` sert uniquement à ce que `--python=3.11` **trouve** l'interpréteur dans ton `PATH`. Pipenv le cherche, il ne le fabrique pas. (Si `pyenv` est installé sur la machine, les versions récentes de pipenv peuvent proposer de télécharger la version manquante — ce n'est pas le cas sur ton Codespace.)

### Sers-t'en une fois avant Docker

Tu viens de créer un virtualenv que, dans la suite de ce document, tu n'utilises **jamais** en local — tout tourne dans `mlopszoomcamp`, et le pipenv ne sert qu'à produire le `Pipfile.lock` pour l'image. Question légitime : pourquoi le garder sur le disque ?

Parce qu'il est la **validation la moins chère du lock**. Avant de lancer un build de trois minutes :

```bash
export MODEL_URI='models:/m-…'
pipenv run gunicorn --bind=0.0.0.0:9696 predict:app     # dans le virtualenv du dossier, pas dans conda
```

Si ça démarre et que `test.py` répond, ton `Pipfile.lock` contient tout ce qu'il faut pour servir le modèle — et tu le sais en dix secondes. Si ça plante ici, ça aurait planté dans l'image, après le build. Même principe qu'au §18 : **une nouveauté à la fois** — d'abord l'environnement, ensuite le conteneur.

> `pipenv run` plutôt que `pipenv shell`, pour la raison du §1 : pas de sous-shell, donc conda ne s'invite pas.

### Pourquoi épingler sklearn, mlflow et skops mais pas flask ni gunicorn ?

| Paquet | Épinglé ? | Pourquoi |
|---|---|---|
| `scikit-learn` | **oui** | touche à la sérialisation du modèle — une différence de version casse le chargement |
| `mlflow` | **oui** | idem : il écrit et relit le format du modèle |
| `skops` | **oui** | c'est le format dans lequel le modèle est écrit (`model.skops`) — on fige la version qui l'a écrit |
| `flask` | non | ne fait que servir des requêtes HTTP ; aucun impact sur le modèle |
| `gunicorn` | non | idem |

La règle est nette : **tout ce qui touche à la sérialisation est épinglé, le reste est libre.**

> ⚠️ Ne te trompe pas sur la raison d'ajouter `skops`. Ce n'est **pas** pour garantir sa présence : `skops<1` est une dépendance **cœur** de MLflow, donc `pipenv install mlflow==3.16.0` l'installe de toute façon. C'est pour en **figer la version**, exactement comme pour scikit-learn. La preuve que la présence n'est pas le sujet : un `Pipfile` sans `skops` produit quand même un `Pipfile.lock` qui le contient.

Ce n'est pas de la négligence : **épingler ce qui n'a pas besoin de l'être crée de la dette**. Chaque version figée est une mise à jour de sécurité que tu devras faire à la main un jour.

### `Pipfile` vs `Pipfile.lock`

| | `Pipfile` | `Pipfile.lock` |
|---|---|---|
| Écrit par | **toi** | la machine |
| Contenu | des **contraintes** (`flask = "*"`) | les **versions exactes**, y compris les dépendances transitives |
| Éditable à la main | oui | **jamais** |
| Contient aussi | — | les empreintes SHA256 de chaque fichier téléchargé, et une empreinte du Pipfile |

C'est le **lock** qui garantit la reproductibilité, pas le Pipfile. Le Pipfile dit « je veux du Flask » ; le lock dit « Flask 3.0.3, avec Werkzeug 3.0.4, Jinja2 3.1.4, MarkupSafe 2.1.5… et voici leurs empreintes ».

> **La leçon la plus coûteuse du chapitre précédent** : `numpy==1.22.4` était dans le lock d'origine sans être dans le `Pipfile`. En lançant `pipenv lock`, tu as re-résolu depuis le Pipfile seul, qui ne contraignait pas numpy. Pipenv a pris une 2.x, et le code C de scikit-learn 1.0.2 s'est cassé dessus.
>
> Morale : `pipenv lock` n'est **jamais anodin** sur un projet ancien.

### `[packages]` vs `[dev-packages]`

Voici le `Pipfile` **cible**, tel qu'il doit finir. Le tien n'y est pas encore — sa section `[dev-packages]` est vide, voir l'avertissement plus bas.

```toml
[packages]          # part dans l'image Docker
flask = "*"
gunicorn = "*"
scikit-learn = "==1.9.0"
mlflow = "==3.16.0"
skops = "==0.14.0"

[dev-packages]      # ne part PAS dans l'image
requests = "*"      # ← à ajouter : pipenv install --dev requests
```

La distinction est conceptuelle et importante :

- `predict.py` tourne **dans** le service → flask, sklearn, mlflow, skops, gunicorn → `[packages]`
- `test.py` tourne **en face** du service, c'est le client → requests → `[dev-packages]`

Une image livrée ne contient que ce qui sert à **répondre**. Pas ce qui sert à interroger.

> ⚠️ **État actuel de ton `Pipfile`** : la section `[dev-packages]` est **vide**. `requests` n'y est déclaré nulle part. Ça fonctionne quand même, parce que tu lances `test.py` depuis `mlopszoomcamp` où `requests` est installé — mais rien dans le projet ne dit que `test.py` a besoin de `requests`. Si tu reprends ce dossier dans six mois, ou si quelqu'un d'autre le clone, l'information est perdue.
>
> La correction : `pipenv install --dev requests`. Elle ne change rien à l'image Docker (les `[dev-packages]` n'y entrent pas), elle rend juste la dépendance explicite.

> *Note 2026* : beaucoup d'équipes utilisent aujourd'hui `uv` ou `poetry` plutôt que pipenv (nettement plus rapides). Le principe est identique : un fichier de déclaration + un fichier de verrouillage. Ce que tu apprends ici est transposable tel quel.

---

## 10. Étape 7 — Adapter `predict.py` pour le conteneur

C'est l'étape qui manquait à ton plan initial, et c'est celle qui coûte du temps si on ne l'anticipe pas.

### Le problème

Ton fichier contenait :

```python
mlflow.set_tracking_uri("http://127.0.0.1:5000")
```

Souviens-toi du principe : **`127.0.0.1` désigne toujours celui qui parle**. Un conteneur Docker possède sa propre pile réseau, donc **son propre `127.0.0.1`** — le sien, pas celui du Codespace. Depuis l'intérieur du conteneur, cette adresse pointe vers le conteneur lui-même, où rien n'écoute sur le port 5000.

Même famille de problème, **troisième occurrence** dans ce module. (Les deux premières : le tunnel SSH du module 2, et le `--host` de MLflow au §3. La quatrième t'attend au `--bind` de gunicorn en conteneur.)

### La solution : sortir la configuration du code

```python
MLFLOW_TRACKING_URI = os.getenv('MLFLOW_TRACKING_URI', 'http://127.0.0.1:5000')
mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)

MODEL_URI = os.getenv('MODEL_URI')
model = mlflow.pyfunc.load_model(MODEL_URI)
```

En local, le défaut s'applique et rien ne change. Dans le conteneur, tu injecteras une autre valeur via `-e`.

C'est exactement le même principe que celui appliqué à `MODEL_URI` — et c'est la règle générale :

> **Tout ce qui dépend de l'endroit où le code tourne doit sortir du code.**

Adresses, chemins, credentials, ports. Ce qui reste dans le fichier, c'est la logique — la partie qui est vraie partout.

**N'oublie pas de sauvegarder** (`Ctrl+S` sur Codespace et Linux, `Cmd+S` sur macOS). VS Code te montre un **buffer en mémoire** ; Python lit le **fichier sur le disque**. Tant que tu n'as pas sauvegardé, ce sont deux choses différentes. Le signal : un **point ●** au lieu de la croix dans l'onglet.

> Le confort : active l'auto-save — `Ctrl+Shift+P` (`Cmd+Shift+P` sur macOS) → `Preferences: Open Settings (UI)` → chercher `auto save` → mettre `afterDelay`.
>
> Jupyter n'a pas ce problème, parce que le code de la cellule est envoyé directement au kernel. C'est justement pour ça que le piège surprend quand on passe du notebook au script.

---

## 11. Étape 8 — Le `Dockerfile` et le `.dockerignore`

### Image vs conteneur

Levons la confusion tout de suite :

| | Image | Conteneur |
|---|---|---|
| Nature | fichier figé, en lecture seule | processus en cours d'exécution |
| Analogie | la recette + les ingrédients sous vide | le plat en train d'être cuisiné |
| Analogie 2 | une classe Python | une instance de cette classe |
| Commande | `docker build` la crée | `docker run` en démarre un |

Une image peut donner naissance à autant de conteneurs qu'on veut, tous identiques au démarrage.

### Le client et le démon

Quand tu tapes `docker build`, tu imagines qu'un seul programme fait tout. En réalité **Docker est composé de deux programmes** :

| | Le client (`docker`) | Le démon (`dockerd`) |
|---|---|---|
| Rôle | prend ta commande, la traduit en requête | fait le vrai travail |
| Ce qu'il fait | rien de concret | construit les images, lance les conteneurs, gère réseau et stockage |
| Analogie | le serveur qui prend la commande | la cuisine |

*(« Démon » est le terme Unix pour un programme qui tourne en permanence en arrière-plan. Rien de diabolique : ça vient de *daemon*, l'esprit serviteur de la mythologie grecque.)*

Ils communiquent via une **API HTTP** — exactement le même schéma client/serveur que ton `test.py` et ton `predict.py`.

**La conséquence décisive** : le client et le démon ne partagent pas forcément le même système de fichiers. Le démon ne peut donc pas « aller lire » tes fichiers. **Il faut les lui envoyer.** C'est ce qu'on appelle le *build context* — voir §12.

### Le Dockerfile

```dockerfile
FROM python:3.11-slim

RUN pip install -U pip && pip install pipenv

WORKDIR /app

COPY ["Pipfile", "Pipfile.lock", "./"]

RUN pipenv install --system --deploy

COPY ["predict.py", "./"]

EXPOSE 9696

ENTRYPOINT ["gunicorn", "--bind=0.0.0.0:9696", "predict:app"]
```

#### `FROM python:3.11-slim`

L'image de base, récupérée depuis Docker Hub. Tu ne pars jamais de zéro : tu hérites d'une image existante et tu ajoutes tes couches par-dessus.

- `python` = le nom de l'image officielle
- `3.11-slim` = le tag. `slim` est la variante allégée, sans outils de compilation ni documentation : ~120 Mo contre ~900 Mo pour l'image complète.

**Le choix de 3.11 n'est pas arbitraire** : c'est la version qui a servi à entraîner et sérialiser le modèle. Une autre version, et tu risques l'incompatibilité de pickle.

> ⚠️ Ton `Pipfile` déclare **deux** contraintes : `python_version = "3.11"` et `python_full_version = "3.11.16"`. La seconde a été écrite par `pipenv install --python=3.11.16`. Or le tag `python:3.11-slim` livre la dernière 3.11 publiée, qui n'est pas forcément la .16. Si `--deploy` refuse de construire en se plaignant de la version de Python, c'est de là que ça vient. Deux sorties, la première est la bonne :
>
> 1. **Supprimer la ligne `python_full_version` du `Pipfile`** (ou recréer le pipenv avec `--python=3.11`, comme le §9 le recommande désormais) : tu ne veux figer que la mineure, c'est elle qui compte pour la compatibilité ; le patch n'apporte que des correctifs de sécurité que tu *veux* recevoir.
> 2. Épingler l'image : `FROM python:3.11.16-slim`. Ça marche, mais tu t'interdis les correctifs de la 3.11 tant que tu ne rebuild pas à la main.

#### `RUN pip install -U pip && pip install pipenv`

`RUN` exécute une commande **au moment de la construction**, et le résultat est figé dans l'image. On met pip à jour, puis on installe pipenv — dont on aura besoin pour lire le `Pipfile.lock`.

Le `&&` enchaîne les deux dans **une seule couche** plutôt que deux. Sur un Dockerfile de production, on regroupe ainsi les `RUN` pour limiter le nombre de couches et la taille finale.

#### `WORKDIR /app`

Définit le répertoire de travail **à l'intérieur du conteneur**. Deux effets : `/app` est créé s'il n'existe pas, et toutes les instructions suivantes (`COPY`, `RUN`, `ENTRYPOINT`) s'exécutent depuis là. C'est l'équivalent d'un `cd` persistant.

#### `COPY` — et pourquoi il y en a deux, séparés

```dockerfile
COPY ["Pipfile", "Pipfile.lock", "./"]
RUN pipenv install --system --deploy
COPY ["predict.py", "./"]
```

`COPY` copie des fichiers **depuis le build context vers l'image**. Le `./` de destination désigne le `WORKDIR`, donc `/app/`.

C'est une **copie**, pas une lecture. Le fichier existe désormais dans le système de fichiers de l'image, indépendamment de tout. Vérifiable :

```bash
docker run -it --rm --entrypoint=ls ride-duration-prediction-service:v2 -la /app
```

**Pourquoi c'est forcément une copie** : le build context est éphémère. Une fois le build terminé, le démon le jette. Si `COPY` n'était qu'une lecture, l'image se retrouverait avec des références vers des fichiers inexistants — elle serait inutilisable dès la fin de la construction.

> Conséquence pratique qui surprend toujours : **modifier `predict.py` sur ton disque après le build ne change rien à l'image.** Elle est figée. Tout changement de code = rebuild.

**Pourquoi séparer les deux `COPY`** — c'est le **cache par couches**.

Chaque instruction du Dockerfile crée une *couche*. Lors d'une reconstruction, Docker réutilise les couches dont les entrées n'ont pas changé, et ne recalcule qu'à partir de la première qui a changé.

Or l'installation des dépendances prend plusieurs minutes, alors que ton `predict.py` change vingt fois par jour. En copiant les dépendances **avant** le code :

- tu modifies `predict.py` → seules les couches après ce `COPY` sont recalculées → **rebuild en 2 secondes**
- tu modifies le `Pipfile` → tout est recalculé à partir de là, mais c'est rare

Inverse les deux lignes, et chaque build repart de zéro. C'est une règle qu'on retrouve dans tous les Dockerfiles bien écrits : **du plus stable au plus volatil**.

> **Vérifie ta compréhension.** Tu corriges une faute de frappe dans `predict.py` et tu relances `docker build`. Quelles couches sont recalculées ? Et si le Dockerfile commençait par `COPY . .` ?
>
> <details><summary>Réponse</summary>
>
> Seule la couche `COPY ["predict.py", "./"]` et celles qui la suivent (`EXPOSE`, `ENTRYPOINT`, quasi gratuites). `FROM`, `pip install pipenv`, `COPY Pipfile*` et `pipenv install` sortent du cache. Avec `COPY . .` en première instruction, le fichier modifié fait partie de cette couche, donc **tout** ce qui suit est recalculé — dépendances comprises.
> </details>

#### `RUN pipenv install --system --deploy`

| Drapeau | Rôle |
|---|---|
| `--system` | installe dans le Python **système du conteneur**, sans créer de virtualenv |
| `--deploy` | **fait échouer le build** si le `Pipfile.lock` n'est pas cohérent avec le `Pipfile` |

**`--system`** : pourquoi pas de virtualenv ? *Parce que le conteneur EST déjà l'isolation.* Créer un venv dans un conteneur, c'est mettre une boîte dans une boîte : complexité inutile, et il faudrait ensuite activer ce venv dans l'`ENTRYPOINT`.

**`--deploy`** est un garde-fou. Il t'interdit de construire une image avec des dépendances incohérentes, ou avec une version de Python qui ne correspond pas au `[requires]` du Pipfile. C'est pénible sur le moment — c'est exactement ce que tu veux avant d'envoyer une image en production.

Note aussi que les `[dev-packages]` ne sont **pas** installées. L'image de production ne contient que le strict nécessaire.

#### `EXPOSE 9696`

⚠️ Instruction **purement documentaire**. Elle n'ouvre aucun port et ne publie rien. Elle déclare « ce conteneur écoute sur le 9696 », information lisible via `docker inspect` et exploitée par certains outils d'orchestration.

C'est le `-p` du `docker run` qui fait le vrai travail. Beaucoup de débutants croient qu'`EXPOSE` suffit — ce n'est pas le cas.

#### `ENTRYPOINT ["gunicorn", "--bind=0.0.0.0:9696", "predict:app"]`

La commande exécutée **au démarrage de chaque conteneur**.

C'est ici que ton choix de gunicorn devient enfin un vrai « par défaut » : il n'est plus une convention orale ou une commande à retenir, c'est **du code versionné dans git**. N'importe qui faisant `docker run` sur cette image démarre gunicorn, sans le savoir ni avoir à y penser.

Et c'est ici que `0.0.0.0` devient indispensable : avec `127.0.0.1`, gunicorn n'écouterait que le trafic **interne au conteneur**, et serait injoignable depuis l'extérieur quel que soit ton mapping de ports.

> **La forme JSON** (`["gunicorn", "--bind=...", ...]`) s'appelle la *forme exec*. Elle lance directement le binaire, sans passer par un shell. Avantage : gunicorn devient le processus **PID 1** du conteneur et reçoit correctement les signaux d'arrêt (`SIGTERM`), ce qui permet un arrêt propre.
>
> La forme shell (`ENTRYPOINT gunicorn --bind=...`) intercale un `/bin/sh` qui avale les signaux, et ton conteneur met 10 secondes à mourir à chaque `docker stop`. **Toujours préférer la forme JSON.**

### Le `.dockerignore`

```
__pycache__/
*.ipynb
.ipynb_checkpoints/
mlflow.db
artifacts/
mlruns/
```

> ⚠️ **Écart à corriger dans ton dépôt** : c'est le fichier tel qu'il est, et il lui manque trois choses que ces notes créent ou signalent ailleurs — `data/` et `*.parquet` (§3, plusieurs Mo de données), `*.bin` (le `dict_vectorizer.bin` vestige, voir l'autre document §7) et `.env` (§4, si tu adoptes un fichier de variables). Version complète :
>
> ```
> __pycache__/
> *.ipynb
> .ipynb_checkpoints/
> mlflow.db
> artifacts/
> mlruns/
> data/
> *.parquet
> *.bin
> .env
> ```

Même syntaxe qu'un `.gitignore`. Le client filtre **avant** l'envoi au démon.

Sans lui, **tout** le dossier est transféré au démon à chaque build — y compris ta base SQLite et ton dossier `artifacts/`, qui grossit à chaque run MLflow. Trois impacts concrets :

- **Vitesse.** Le transfert prend du temps, surtout si le démon est distant (CI/CD, Docker Desktop sur macOS où le démon tourne dans une VM).
- **Cache.** Le cache d'un `COPY` dépend de l'empreinte des **fichiers copiés**, pas du contexte entier. Ton Dockerfile copie des fichiers nommés (`Pipfile`, `Pipfile.lock`, `predict.py`) : un `.pyc` régénéré ou un nouveau run MLflow ne lui fait donc rien. Mais avec un `COPY . .` — l'écriture qu'on voit dans neuf tutoriels sur dix — n'importe quel fichier modifié dans le contexte invalide la couche et tout ce qui suit, y compris l'installation des dépendances. Trois minutes perdues pour un checkpoint Jupyter. Une raison de plus de ne jamais écrire `COPY . .` sans `.dockerignore`.
- **Sécurité.** Si tu as un `.env` avec des credentials ou une clé AWS dans le dossier, un `COPY . .` distrait les embarque dans l'image. Et **une couche d'image est permanente** : même si tu supprimes le fichier dans une instruction suivante, il reste récupérable dans l'historique des couches. C'est une fuite de secrets classique.

> `.dockerignore` n'est pas qu'une optimisation, c'est un **garde-fou**. Sur un projet ML où le dossier contient des données, des credentials cloud et des artefacts MLflow, c'est un fichier qu'on écrit dès le début.

---

## 12. Étape 9 — Construire l'image

```bash
docker build -t ride-duration-prediction-service:v2 .
```

| Élément | Rôle |
|---|---|
| `docker build` | lit un Dockerfile et construit une image |
| `-t` | *tag* — donne un nom à l'image |
| `ride-duration-prediction-service` | le nom |
| `:v2` | la version (`v1` était celle du chapitre `web-service`) |
| **`.`** | **le build context** — à ne surtout pas oublier |

### Le build context, en détail

Le `.` final désigne le dossier **envoyé au démon Docker**. Tu vois passer une ligne de *transfert de contexte* :

```
[+] Building 0.3s (9/9) FINISHED
 => [internal] load build context
 => => transferring context: 4.10kB
```

> Beaucoup de tutoriels montrent à la place `Sending build context to Docker daemon  4.096kB`. C'est l'ancien constructeur : depuis Docker 23 (2023), `docker build` utilise **BuildKit** par défaut, dont la sortie est celle ci-dessus. Même mécanisme, affichage différent.

C'est littéralement un transfert. Le client compresse le dossier, l'expédie au démon, et **le démon travaille sur sa copie**.

Ce qui implique :

- **Les `COPY` lisent dans cette copie**, pas sur ton disque.
- **Tu ne peux pas sortir du contexte.** `COPY ../data/model.bin ./` échoue systématiquement — non par règle arbitraire, mais parce que `../data/` n'a jamais été envoyé : le fichier est physiquement absent chez le démon.

```
ton disque ──(1) envoi──► build context ──(2) COPY──► couche de l'image
                         (copie temporaire        (copie permanente,
                          chez le démon)           qui voyage avec l'image)
```

### La contradiction apparente, levée

« Si le build dépend d'un dossier précis, où est la portabilité de Docker ? »

Il faut séparer **deux moments de vie** :

```
┌──────────────────── CONSTRUCTION ────────────────────┐
│  UNE FOIS, sur TA machine de développement           │
│                                                      │
│  Dossier web-service-mlflow/   docker build   Image  │
│  ├── Dockerfile          ─────────────────►  figée   │
│  ├── Pipfile.lock         (besoin du         et      │
│  └── predict.py            contexte)         autonome│
└──────────────────────────────────────────────────────┘
                        │ docker push (registry)
                        ▼
┌──────────────────── EXÉCUTION ───────────────────────┐
│  N FOIS, sur N'IMPORTE QUELLE machine                │
│                                                      │
│  docker pull mon-registry/ride-duration:v2           │
│  docker run -p 9696:9696 ride-duration:v2            │
│                                                      │
│  ➜ Aucun besoin du dossier source, du Dockerfile,    │
│    de Python, de pipenv, de scikit-learn.            │
└──────────────────────────────────────────────────────┘
```

> **Le build context est un ingrédient de la recette, pas du plat.** Tu as besoin de farine, d'un four et de ta cuisine pour faire le pain. Une fois le pain cuit, tu l'emportes partout — personne n'a besoin de ta cuisine pour le manger.

La portabilité de Docker porte sur l'**exécution**, pas sur la construction.

Et le build lui-même n'est pas si rigide : le `.` n'est qu'un raccourci pour « le dossier courant ». Tu peux passer n'importe quel chemin :

```bash
cd /workspaces/mlops-zoomcamp
docker build -t ride-duration:v2 04-deployment/web-service-mlflow
```

Le dernier argument est **toujours** le contexte. Et si le Dockerfile est ailleurs, `-f` le précise :

```bash
docker build -t ride-duration:v2 -f docker/Dockerfile ./web-service-mlflow
                                    └── où est la recette  └── quels fichiers envoyer
```

La seule vraie règle : **le contexte doit contenir tous les fichiers que le Dockerfile veut copier.** Le répertoire depuis lequel tu tapes la commande n'a aucune importance.

C'est pour ça qu'en CI/CD (GitHub Actions, GitLab CI), le build se fait depuis la racine du dépôt avec des chemins explicites — personne ne fait de `cd` dans un pipeline.

### Qu'est-ce qu'un tag ?

L'étiquette de version collée sur une image. Syntaxe toujours `nom:tag`. Tu l'as déjà vu sans y prêter attention : `python:3.11-slim`, `postgres:13`.

**Pourquoi c'est central en MLOps** : le tag rend le déploiement **réversible**.

1. Tu construis `ride-duration:v1`, tu déploies, tout va bien.
2. Tu réentraînes, tu construis `:v2`, tu déploies.
3. Les prédictions deviennent bizarres en production.
4. Tu redéploies `:v1` en une commande. **Rollback immédiat**, aucune reconstruction.

Les deux images coexistent. Sans tag, tu n'aurais aucun moyen de désigner « la version d'avant ».

**Le piège du tag `latest`** : si tu omets le tag, Docker met automatiquement `:latest`. C'est une mauvaise habitude — `latest` est une étiquette *mouvante*, que tu peux recoller sur une autre image à tout moment. Deux machines faisant `docker pull mon-image:latest` à une semaine d'écart peuvent obtenir deux images différentes. Adieu la reproductibilité.

> Détail utile : un tag n'est qu'un **pointeur**. La vraie identité d'une image est son digest SHA256. On peut donc coller plusieurs tags sur la même image :
> ```bash
> docker tag ride-duration-prediction-service:v2 ride-duration-prediction-service:2026-09-20
> ```
> En entreprise, on tague souvent avec le hash du commit git (`:a3f8c12`), ce qui relie l'image déployée à l'état exact du code qui l'a produite. Exactement la même logique que le `run_id` MLflow.

---

## 13. Étape 10 — Lancer le conteneur : les deux obstacles

C'est l'étape la plus délicate du chapitre, parce qu'il y a **deux problèmes distincts**, et qu'on croit souvent n'en avoir qu'un.

### Pourquoi il y en a deux, et pas un

Parce que le conteneur a besoin de **deux choses différentes**, rangées au même endroit mais atteintes par **deux canaux différents** :

```
                 Comment le CONTENEUR atteint chaque chose

  mlflow.db          ──►  JAMAIS directement.
  (les métadonnées)       Il interroge le serveur en HTTP sur le port 5000,
                          et c'est LE SERVEUR qui lit la base.
                          canal = RÉSEAU        →  --add-host

  artifacts/         ──►  DIRECTEMENT, comme un fichier local.
  (model.skops)           Le serveur lui a seulement donné le chemin ;
                          c'est le conteneur qui ouvre le fichier lui-même.
                          canal = FICHIERS      →  -v
```

Deux canaux, deux drapeaux. Ce n'est pas une redondance : si tu n'ouvres que le réseau, le conteneur sait *où* est le modèle mais ne peut pas le lire ; si tu ne montes que le volume, il a les fichiers sous la main mais ne sait pas lequel prendre.

> **Vérifie ta compréhension.** Quand le conteneur démarre, qui lit `mlflow.db` ? Faut-il le monter avec `-v` ?
>
> <details><summary>Réponse</summary>
>
> Personne dans le conteneur. C'est le **serveur MLflow**, sur l'hôte, qui ouvre `mlflow.db` pour répondre à la question « où est `m-…` ? ». Le conteneur ne voit que la réponse HTTP. Monter `mlflow.db` serait donc inutile — et dangereux : deux processus sur une même base SQLite, c'est une corruption qui attend son heure.
> </details>

> Garde cette asymétrie en tête pour la note de fin de section : en mode `mlflow-artifacts:/`, les artifacts passent **eux aussi** par le réseau. Le canal « fichiers » disparaît, et le `-v` avec lui.

### Obstacle 1 — joindre le serveur MLflow

Le conteneur a son propre `127.0.0.1`. Il faut donc :

- côté code : lire l'adresse dans une variable d'environnement (fait à l'étape 7)
- côté Docker : donner au conteneur une **route vers sa machine hôte**
- côté MLflow : écouter sur `0.0.0.0` (étape 0)

Le drapeau `--add-host=host.docker.internal:host-gateway` crée, à l'intérieur du conteneur, un nom d'hôte `host.docker.internal` qui pointe vers le Codespace.

### Obstacle 2 — lire les artifacts

Celui-là est moins évident, et c'est celui qui bloque tout le monde.

Tu as lancé MLflow avec :

```
--default-artifact-root /workspaces/mlops-zoomcamp/04-deployment/web-service-mlflow/artifacts
```

Le serveur de tracking **ne te transmet pas les fichiers du modèle**. Il te répond **où ils se trouvent** — c'est-à-dire ce chemin local. Ton client va ensuite le lire lui-même, sur son propre disque.

Or ce chemin n'existe pas dans le conteneur, dont le système de fichiers est complètement séparé.

Il faut donc y rendre ce dossier visible, **au même chemin**. C'est le rôle du `-v`.

### La commande complète

```bash
cd /workspaces/mlops-zoomcamp/04-deployment/web-service-mlflow   # le $PWD ci-dessous en dépend
docker run -it --rm \
  -p 9696:9696 \
  --add-host=host.docker.internal:host-gateway \
  -e MLFLOW_TRACKING_URI='http://host.docker.internal:5000' \
  -e MODEL_URI='models:/m-5e276730f7004842b7c3a36ea11b5044' \
  -v "$PWD/artifacts:$PWD/artifacts:ro" \
  ride-duration-prediction-service:v2
```

| Drapeau | Rôle |
|---|---|
| `-it` | interactif + pseudo-terminal : tu vois les logs en direct et `Ctrl+C` fonctionne |
| `--rm` | supprime le conteneur à l'arrêt |
| `-p 9696:9696` | publie le port : `hôte:conteneur` |
| `--add-host=…:host-gateway` | crée le nom `host.docker.internal` pointant vers le Codespace |
| `-e MLFLOW_TRACKING_URI=…` | dit au conteneur où joindre MLflow |
| `-e MODEL_URI=…` | quel modèle servir |
| `-v chemin:chemin:ro` | monte le dossier d'artifacts, en lecture seule |

### Les drapeaux en détail

**`-it`** — deux drapeaux fusionnés : `-i` (`--interactive`, garde STDIN ouvert) et `-t` (`--tty`, alloue un pseudo-terminal). Concrètement : tu vois les logs de gunicorn s'afficher correctement, et `Ctrl+C` arrête le conteneur proprement.

En production réelle, on utilise plutôt `-d` (*detached*) pour lancer en arrière-plan. En développement, `-it` est le mode « je veux voir ce qui se passe ».

**`--rm`** — par défaut, un conteneur arrêté **reste sur ton disque**, visible via `docker ps -a`. Tester dix fois ton service laisse dix conteneurs morts. Sur un Codespace à disque limité, ce n'est pas anodin.

Le réflexe : `--rm` pour tout conteneur jetable de test. On l'omet quand on veut inspecter les logs *après* l'arrêt (`docker logs <id>`).

**`-p 9696:9696`** — la publication de port.

```
-p  PORT_HÔTE : PORT_CONTENEUR
        ↓             ↓
-p     9696     :    9696
```

**L'ordre compte** : à gauche ta machine, à droite le conteneur. Les deux nombres sont **indépendants** : `-p 8080:9696` ferait écouter le service sur `localhost:8080` chez toi, le conteneur continuant d'écouter sur 9696 sans le savoir.

> **Vérifie ta compréhension.** Pourquoi `-p 8080:9696` fonctionne sans reconstruire l'image ni toucher à gunicorn ?
>
> <details><summary>Réponse</summary>
>
> Parce que gunicorn n'a jamais connu que « son » 9696, à l'intérieur du conteneur. Le `-p` est un réglage de `docker run`, appliqué **autour** du conteneur : Docker écoute sur le 8080 de l'hôte et relaie vers le 9696 interne. Ni l'image ni le processus ne savent qu'un tunnel existe. C'est exactement la séparation image / conteneur du §11.
> </details>

C'est utile quand le port est déjà pris, ou pour lancer plusieurs instances :

```bash
docker run -p 9696:9696 ride-duration:v2   # instance 1
docker run -p 9697:9696 ride-duration:v2   # instance 2, même image
```

**`-v source:destination:ro`** — le montage de volume.

Un volume rend un dossier de l'hôte visible à l'intérieur du conteneur. Le `:ro` le monte en lecture seule — bonne pratique quand le conteneur n'a aucune raison d'écrire.

**Le point subtil** : ici, source et destination sont **le même chemin**. Ce n'est pas un hasard. Le conteneur va recevoir du serveur MLflow un chemin absolu (`/workspaces/…/artifacts/…`) ; en montant le dossier au même endroit, ce chemin devient valide chez lui aussi.

`$PWD` est développé par **ton shell**, avant que Docker ne voie la commande : les deux côtés reçoivent le même chemin absolu, écrit une seule fois. Et la commande reste valable ailleurs qu'en Codespace — à condition d'être dans `web-service-mlflow/` au moment de la taper.

> C'est aussi le seul mécanisme de ce chapitre qui lit des fichiers de l'hôte **en direct**, au `run` et non au `build`. Ne confonds pas : `COPY` fige au build, `-v` relie à l'exécution.

### L'alternative plus courte (Linux uniquement)

```bash
docker run -it --rm --network=host \
  -e MODEL_URI='models:/m-5e276730f7004842b7c3a36ea11b5044' \
  -v "$PWD/artifacts:$PWD/artifacts:ro" \
  ride-duration-prediction-service:v2
```

`--network=host` supprime l'isolation réseau : le conteneur partage directement la pile réseau de la machine. Du coup `127.0.0.1:5000` fonctionne tel quel, et le `-p` devient inutile.

C'est plus simple — mais **fais la première version d'abord**. Le mapping de ports est un concept Docker fondamental que tu retrouveras partout, alors que `--network=host` ne marche que sous Linux et masque ce qui se passe.

### Ce que cette étape t'apprend au-delà de la technique

Ton service est maintenant **portable** (il embarque ses dépendances) mais **pas autonome** (il dépend de MLflow joignable et d'un dossier monté).

C'est précisément le couplage dont parle l'autre document, rendu visible par Docker. Le `s3://` de l'instructeur supprime les deux contraintes d'un coup : plus de serveur à joindre, plus de volume à monter. Tu vois maintenant **concrètement** pourquoi il a fait ce choix.

> **Le `-v` n'est pas une fatalité de `models:/`.** Il découle d'un choix que tu as fait au §3 : `--default-artifact-root <chemin local>`. Ce drapeau dit au serveur « les artifacts sont rangés là », et le serveur se contente alors de **te donner le chemin**.
>
> Lancé **sans** ce drapeau, MLflow passe en mode *artifacts proxifiés* : il sert les fichiers lui-même, en HTTP, sous le schéma `mlflow-artifacts:/`. Le conteneur reçoit alors les octets et non un chemin — et le `-v` disparaît.
>
> Il y a donc **deux couplages indépendants**, et trois leviers :
>
> | Couplage | Cause | Comment le casser |
> |---|---|---|
> | Il faut joindre le serveur | l'URI `models:/` est une référence indirecte | passer à une URI auto-suffisante (`s3://`) |
> | Il faut monter un volume | `--default-artifact-root` local | laisser MLflow proxifier (`mlflow-artifacts:/`) |
>
> Le `s3://` casse les deux à la fois parce qu'il fait d'une pierre deux coups. Mais ce ne sont pas les deux faces d'un même problème.

---

## 14. Étape 11 — Tester

Depuis un troisième terminal, **sans aucune modification** :

```bash
conda activate mlopszoomcamp
python test.py
```

`test.py` interroge `localhost:9696` depuis le Codespace. Le mapping `-p` l'envoie dans le conteneur. Du point de vue du client, rien n'a changé — c'est exactement ce qu'on cherchait.

Tu devrais obtenir :

```json
{"duration": 21.3, "model_version": "models:/m-5e276730f7004842b7c3a36ea11b5044"}
```

> **Note Codespaces** : quand tu lances un conteneur avec `-p`, VS Code détecte automatiquement le port et l'ajoute à l'onglet **PORTS**. C'est de là que tu récupères l'URL forwardée si tu veux tester depuis le navigateur de ton PC — exactement comme pour MLflow sur le 5000.

---

## 15. Les trois architectures, en schémas

Tu as maintenant traversé les trois setups. Cette section les met côte à côte. Pour chacun : **où vivent les choses**, puis **ce qui se passe au démarrage**, puis **ce qui se passe à chaque requête**.

Garde en tête la distinction des deux phases — c'est elle qui explique presque tout :

| Phase | Quand | Qui parle à qui |
|---|---|---|
| **A — Démarrage** | une seule fois, au lancement du service | le service → MLflow → le disque |
| **B — Requête** | à chaque appel client | le client → le service (et c'est tout) |

---

### Setup 1 — Flask seul, sans Docker

#### Où vivent les choses

```
╔══════════════════════════ CODESPACE (une seule machine) ══════════════════════════╗
║                                                                                   ║
║   Terminal 1                    Terminal 2                    Terminal 3          ║
║  ┌───────────────────┐        ┌────────────────────┐        ┌──────────────────┐  ║
║  │ mlflow server     │        │ export MODEL_URI=… │        │ python test.py   │  ║
║  │  --host 0.0.0.0   │        │ python predict.py  │        │                  │  ║
║  │  --port 5000      │        │                    │        │ POST vers        │  ║
║  │                   │        │ Flask dev          │        │ localhost:9696   │  ║
║  │ écoute :5000      │        │ écoute 0.0.0.0:9696│        │ puis se termine  │  ║
║  └───────────────────┘        └────────────────────┘        └──────────────────┘  ║
║                                                                                   ║
║  ┌─ le disque du Codespace ────────────────────────────────────────────────────┐  ║
║  │  mlflow.db                    → les métadonnées (où est rangé quoi)         │  ║
║  │  artifacts/1/…/model.skops    → les fichiers du modèle                      │  ║
║  └─────────────────────────────────────────────────────────────────────────────┘  ║
╚═══════════════════════════════════════════════════════════════════════════════════╝
```

#### Phase A — au démarrage (une seule fois)

```
  Terminal 2 : python predict.py
        │
        │ ①  os.getenv('MODEL_URI')  →  lit le shell  →  'models:/m-5e2767…'
        │
        │ ②  load_model('models:/m-5e2767…')
        │       « models: » n'est pas une adresse → il faut résoudre
        ▼
  ┌───────────────────────┐
  │ mlflow server  :5000  │ ③  « où est rangé m-5e2767… ? »
  │                       │ ④  ← "/workspaces/…/artifacts/1/…/"
  └───────────────────────┘
        │
        │ ⑤  predict.py ouvre ce chemin LUI-MÊME, sur le disque
        │     (même machine, même filesystem → ça marche tout seul)
        ▼
   modèle désérialisé (skops) → en RAM dans le processus python
        │
        ▼
   ⑥  Flask démarre et écoute sur 0.0.0.0:9696
```

**Le point de l'étape ⑤** : le serveur MLflow ne t'envoie pas le modèle. Il t'envoie **une adresse**, et c'est ton propre processus qui va ensuite lire les fichiers. Ici ça passe inaperçu — même machine, même disque. Au setup 3, c'est ce qui casse.

#### Phase B — à chaque requête

```
  Terminal 3               loopback              Terminal 2
  test.py  ──── POST ────► 127.0.0.1:9696 ────►  Flask
           ◄─── JSON ────                        └─ predict() sur le modèle en RAM

   MLflow n'est PLUS sollicité.  ✗ ── pas d'appel au 5000 ──
```

> Ici, `--host 127.0.0.1` suffirait encore : tout le monde est sur la même machine, tout passe par la boucle locale. Le schéma montre quand même `0.0.0.0`, parce que c'est ce que le §3 te recommande de taper dès le départ — au setup 3, tu n'auras plus le choix.

---

### Setup 2 — Flask + gunicorn, sans Docker

**Une seule chose change : le serveur HTTP.** Ton code Flask, le chargement du modèle, MLflow, `test.py` : identiques.

#### Où vivent les choses

```
╔══════════════════════════ CODESPACE (une seule machine) ══════════════════════════╗
║                                                                                   ║
║   Terminal 1                    Terminal 2                    Terminal 3          ║
║  ┌───────────────────┐        ┌──────────────────────┐      ┌──────────────────┐  ║
║  │ mlflow server     │        │ export MODEL_URI=…   │      │ python test.py   │  ║
║  │ écoute :5000      │        │ gunicorn             │      │ POST vers        │  ║
║  │                   │        │  --bind=0.0.0.0:9696 │      │ localhost:9696   │  ║
║  │                   │        │  predict:app         │      │                  │  ║
║  └───────────────────┘        └──────────────────────┘      └──────────────────┘  ║
║                                                                                   ║
║  ┌─ le disque du Codespace ─────────────── strictement inchangé / setup 1 ───┐    ║
║  │  mlflow.db                    → les métadonnées (où est rangé quoi)       │    ║
║  │  artifacts/1/…/model.skops    → les fichiers du modèle                    │    ║
║  └───────────────────────────────────────────────────────────────────────────┘    ║
╚═══════════════════════════════════════════════════════════════════════════════════╝
```

#### Phase A — au démarrage : ce que fait `predict:app`

```
  gunicorn  ──① importe le module `predict` ────────────────────────┐
                                                                    ▼
                                              predict.py s'exécute de haut en bas
                                              ├─ os.getenv(...)
                                              ├─ load_model(...)   ← même phase A
                                              │                      qu'au setup 1
                                              ├─ app = Flask(...)
                                              └─ if __name__ == "__main__":
                                                     ✗ NE S'EXÉCUTE PAS
                                                     (__name__ vaut "predict")
                                                                    │
  gunicorn  ◄─② récupère l'objet `app` ─────────────────────────────┘
        │
        ▼
  ③ gunicorn ouvre lui-même la socket 0.0.0.0:9696 et gère le réseau
```

C'est le seul endroit du chapitre où la garde `if __name__ == "__main__"` a un effet visible : elle éteint le serveur de dev pendant que gunicorn prend la main, **sans qu'une ligne de code change**.

#### Phase B — à chaque requête

```
  test.py ──POST──► 127.0.0.1:9696 ──► gunicorn (processus maître)
                                              │  lie le port, surveille
                                              │  les workers
                                    ┌─────────┴──────────────────────┐
                                    │ worker 1 : app Flask           │
                                    │            + SA copie du modèle│
                                    │ worker 2 : app Flask           │
                                    │            + SA copie du modèle│
                                    └────────────────────────────────┘
```

Le maître ne traite aucune requête : il lie le port une fois, puis surveille les workers. Ceux-ci héritent de la même socket et y font `accept()` eux-mêmes — la répartition est faite par le noyau, pas par le maître. Et **chaque worker importe `predict.py` de son côté**, donc chacun refait la phase A et charge sa propre copie du modèle en mémoire. Quatre workers = quatre fois la taille du modèle en RAM. C'est ce qui fait que `--workers` n'est pas un curseur qu'on pousse au maximum.

**Le point à retenir** : `test.py` n'a pas bougé d'une ligne. Il parle à un port ; ce qu'il y a derrière ne le regarde pas.

---

### Setup 3 — Docker

Ici deux mondes apparaissent, avec **deux systèmes de fichiers** et **deux piles réseau**. C'est toute la difficulté de l'étape, et tout ce qui la rend instructive.

#### Où vivent les choses

```
╔═══════════════════════════════ CODESPACE — L'HÔTE ═══════════════════════════════╗
║                                                                                  ║
║   ┌─ Terminal 1 ─────────────────┐      ┌─ Terminal 3 ─────────────────┐         ║
║   │ mlflow server                │      │ python test.py               │         ║
║   │   --host 0.0.0.0             │      │ POST http://localhost:9696   │         ║
║   │   --port 5000                │      └──────────────────────────────┘         ║
║   └──────────────────────────────┘                                               ║
║                                                                                  ║
║   ┌─ disque de l'hôte ───────────────────────────────────────────────────┐       ║
║   │ mlflow.db                   ← lu par le SERVEUR, jamais par le       │       ║
║   │                               conteneur. NON monté.                  │       ║
║   │ /workspaces/…/artifacts/1/…/model.skops                              │       ║
║   │                             ← greffé dans le conteneur par (2)       │       ║
║   └──────────────────────────────────────────────────────────────────────┘       ║
╚══════════════════════════════════════════════════════════════════════════════════╝

        ▲ (1)                  ▲ (2)                            ▲ (3)
        │ host.docker          │ -v : artifacts/ ci-dessus est  │ -p 9696:9696
        │ .internal:5000       │   greffé AU MÊME CHEMIN        │   tunnel de port
        │   → le 5000 ci-dessus│   dans le conteneur            │
        │                      │                                │
┌ ─ ─ ─ ┼ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┼─ ─ LE CONTENEUR ─ ─ ─ ─ ─ ─ ─ ─┼─ ─ ─ ─ ─ ─ ─ ─ ┐
        │                      │                                │
│  ┌────┴──────────────────────┴────┐          ┌────────────────┴─────────────┐ │
   │ predict.py                     │          │ gunicorn                     │  
│  │  MLFLOW_TRACKING_URI → (1)     │ ◄── importé par ─┐                      │ │
   │  MODEL_URI (via -e)            │          │  --bind=0.0.0.0:9696         │  
│  │  ouvre /workspaces/… → (2)     │          │  predict:app  ◄──────────────┘ │
   └────────────────────────────────┘          └──────────────────────────────┘  
│                                                                               │
   ┌─ système de fichiers du conteneur ──────────────────────────────────────┐   
│  │ /app/predict.py                                                         │  │
   │ /usr/local/lib/python3.11/…   (les paquets du Pipfile.lock)             │   
│  │ /workspaces/…/artifacts       ← n'existe QUE grâce au -v                │  │
   └─────────────────────────────────────────────────────────────────────────┘   
└ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘
```

#### Ce que chaque drapeau installe, AVANT que Python démarre

C'est l'ordre qu'on rate le plus souvent : **Docker prépare le décor, ensuite seulement le programme s'exécute.**

```
docker run
  -e MODEL_URI='models:/m-5e2767…'      → pose la variable dans l'env du conteneur
  -e MLFLOW_TRACKING_URI='http://host.docker.internal:5000'
                                         → idem
  --add-host=host.docker.internal:host-gateway
                                         → écrit une ligne dans le /etc/hosts
                                           du conteneur : ce nom → l'hôte
  -v /workspaces/…/artifacts:/workspaces/…/artifacts:ro
                                         → greffe le dossier de l'hôte dans le
                                           FS du conteneur, AU MÊME CHEMIN
  -p 9696:9696                           → tunnel : 9696 de l'hôte → 9696 du conteneur

  ↓ seulement ENSUITE, l'ENTRYPOINT s'exécute
  gunicorn --bind=0.0.0.0:9696 predict:app
```

**Deux confusions à éviter, tant qu'elles sont fraîches :**

- **`-p` n'appartient pas à gunicorn.** C'est un drapeau de `docker run`. Gunicorn écoute sur le 9696 *de son conteneur* et ignore totalement l'existence du tunnel.
- **`predict.py` ne « va pas chercher le modèle via le `-v` ».** Le `-v` a fini son travail avant le démarrage : il a rendu un chemin de l'hôte valide dans le conteneur. `predict.py` ouvre ensuite un fichier ordinaire, sans savoir qu'un volume existe.

#### Phase A — au démarrage

```
  ENTRYPOINT → gunicorn → importe predict.py
        │
        │ ①  os.getenv('MLFLOW_TRACKING_URI') → 'http://host.docker.internal:5000'
        │    os.getenv('MODEL_URI')           → 'models:/m-5e2767…'
        │
        │ ②  load_model('models:/m-5e2767…')  → il faut résoudre
        ▼
   host.docker.internal ═══ franchit la frontière conteneur→hôte ═══►
        ▼
  ┌──────────────────────────┐
  │ mlflow server :5000      │  ③ « où est m-5e2767… ? »
  │ (accepte parce que       │  ④ ← "/workspaces/…/artifacts/1/…"
  │  --host 0.0.0.0)         │
  └──────────────────────────┘
        │
        │ ⑤  predict.py ouvre /workspaces/…/artifacts/1/…/model.skops
        │       ┌─────────────────────────────────────────────────┐
        │       │ Pour lui c'est un fichier local ordinaire.      │
        │       │ Il ne sait pas qu'un volume existe.             │
        │       │ C'est le -v qui a rendu ce chemin valide ICI.   │
        │       └─────────────────────────────────────────────────┘
        ▼
   modèle en RAM, dans le processus du conteneur
        │
        ▼
   ⑥  gunicorn écoute 0.0.0.0:9696 (dans le conteneur)
```

Compare avec la phase A du setup 1 : **les six étapes sont les mêmes.** Seuls deux détails changent — ③ passe par un nom d'hôte au lieu de la loopback, et ⑤ lit un chemin qui n'existe que grâce au `-v`. Toute la difficulté de Docker tient dans ces deux endroits.

#### Phase B — à chaque requête

```
  Terminal 3 (hôte)          Docker              CONTENEUR
  ┌──────────┐           ┌──────────┐         ┌─────────────────────────┐
  │ test.py  │──POST────►│   -p     │────────►│ gunicorn 0.0.0.0:9696   │
  │          │  :9696    │9696:9696 │  :9696  │      │                  │
  │          │◄──JSON────│          │◄────────│  app Flask → predict()  │
  └──────────┘           └──────────┘         │      └─ modèle en RAM   │
                                              └─────────────────────────┘

  Ni MLflow ni le volume ne sont sollicités.
```

#### Pourquoi `0.0.0.0` est indispensable des **deux** côtés

```
  MLflow --host 127.0.0.1 ?  →  la requête du conteneur arrive par l'interface
                                docker0, pas par la loopback  →  REFUSÉE

  gunicorn --bind 127.0.0.1 ? →  il n'écoute que le trafic interne au conteneur ;
                                 le -p redirige vers une socket où personne n'écoute
                                 →  Connection refused
```

Les deux pannes se ressemblent sans donner le même message : un refus franc (`Connection refused`) côté MLflow, souvent un `Connection reset by peer` ou un `Empty reply from server` côté `-p` — parce que le proxy Docker accepte la connexion puis échoue à joindre l'application.

Le critère fiable n'est pas le message, c'est **le moment** :

| Quand ça casse | Cause | Où regarder |
|---|---|---|
| le conteneur **ne démarre pas** | il n'a pas pu charger le modèle | MLflow : `--host`, `--add-host`, `-v` (les deux obstacles du §13) |
| il démarre, mais `test.py` échoue | le service est injoignable de l'extérieur | le `--bind` de gunicorn et le `-p` — un troisième problème, distinct des deux obstacles du §13 |

---

### Ce qui change entre les trois

| | Setup 1 (Flask) | Setup 2 (+ gunicorn) | Setup 3 (Docker) |
|---|---|---|---|
| Serveur HTTP | Werkzeug (dev) | gunicorn | gunicorn |
| Qui exécute `predict.py` | Python directement | gunicorn (import) | gunicorn (import), dans le conteneur |
| `if __name__ == "__main__"` | **s'exécute** | ignoré | ignoré |
| Environnement Python | conda `mlopszoomcamp` | conda `mlopszoomcamp` | celui de l'image, depuis `Pipfile.lock` |
| Systèmes de fichiers | 1 | 1 | **2** (hôte + conteneur) |
| Piles réseau | 1 | 1 | **2** |
| Comment `MODEL_URI` arrive | `export` dans le shell | `export` dans le shell | `-e` au `docker run` |
| Accès au dossier `artifacts/` | direct | direct | **via `-v`** |
| Joindre MLflow | `127.0.0.1:5000` | `127.0.0.1:5000` | **`host.docker.internal:5000`** |
| `--host` de MLflow | `127.0.0.1` suffit | `127.0.0.1` suffit | **`0.0.0.0` obligatoire** |
| Exposer le 9696 | rien à faire | rien à faire | **`-p 9696:9696`** |
| Phase A (démarrage) | 6 étapes | 6 étapes (+ import) | 6 étapes (+ 2 frontières) |
| Phase B (requête) | identique | identique | identique |
| `test.py` | inchangé | inchangé | **inchangé** |

Les trois dernières lignes sont le fil rouge du chapitre : trois architectures internes radicalement différentes, **un seul contrat** — `POST http://localhost:9696/predict`.

---

## 16. Récapitulatif : environnements, shells, terminaux, ports

### Les environnements en jeu

| Environnement | Rôle | Python | Contient |
|---|---|---|---|
| `mlopszoomcamp` (conda) | ton atelier : notebooks, MLflow, exploration | 3.11.16 | sklearn 1.9.0, mlflow 3.16.0, pandas, jupyter, requests |
| pipenv du dossier | le service à livrer | 3.11.16 | sklearn 1.9.0, mlflow 3.16.0, skops 0.14.0, flask, gunicorn |
| dans l'image Docker | le service livré | 3.11 (image de base) | installé depuis `Pipfile.lock`, sans virtualenv |

Ils ne sont **pas imbriqués**, ils sont côte à côte. Le virtualenv pipenv ne voit aucun paquet de conda.

Ton environnement conda est **totalement invisible** depuis l'intérieur du conteneur. C'est précisément ce qu'on cherche : **l'image est autonome**. Si Docker dépendait de ton conda, tu n'aurais rien gagné en portabilité.

### Quelle commande dans quel environnement ?

| Commande | Environnement | Pourquoi |
|---|---|---|
| `mlflow server …` | **`mlopszoomcamp`** | `mlflow` n'est installé que là |
| Jupyter / le notebook | **`mlopszoomcamp`** | (et vérifie aussi le **kernel** du notebook) |
| `python predict.py` (hors Docker) | **`mlopszoomcamp`** | a besoin de mlflow, sklearn, flask |
| `gunicorn … predict:app` (hors Docker) | **`mlopszoomcamp`** | idem |
| `python test.py` | **`mlopszoomcamp`** | a besoin de `requests` |
| `pipenv install` | **`mlopszoomcamp`** | pour que `--python=3.11` trouve le bon interpréteur |
| `pipenv run gunicorn …` | **pipenv du dossier** | valider le lock avant Docker (§9) |
| `docker build` | **peu importe** | Docker est un binaire système |
| `docker run` | **peu importe** | idem |
| `curl`, `lsof`, `kill` | **peu importe** | outils système |

**En pratique** : active `mlopszoomcamp` par réflexe dans tout nouveau terminal. Ça ne gêne jamais, y compris pour Docker, et ça t'évite l'erreur inverse — qui est la plus fréquente.

Et garde le réflexe de **lire ton prompt** : `(base)` ou `(mlopszoomcamp)` en début de ligne te dit immédiatement où tu es.

> ⚠️ Nuance importante par rapport au chapitre précédent : **ici, lancer le service depuis conda est correct**, parce que conda est l'environnement qui a entraîné le modèle. Au chapitre `web-service`, c'était l'inverse : un prompt `(mlopszoomcamp)` dans ce dossier était un signal d'alerte, parce que le pickle venait de scikit-learn 1.0.2 et que seul le virtualenv pipenv l'avait.
>
> La règle générale, elle, ne change pas : **l'environnement qui sert doit correspondre à l'environnement qui a entraîné.**

### La carte des ports

| Port | Occupé par | Depuis où joignable |
|---|---|---|
| 5000 | `mlflow server` | Codespace ; et depuis le conteneur si `--host 0.0.0.0` |
| 9696 | le service de prédiction | Codespace ; et depuis l'extérieur du conteneur si `-p` **et** `--bind 0.0.0.0` |

**Un port ne peut être lié qu'une seule fois.** D'où `Address already in use` quand on oublie d'arrêter le précédent.

### `0.0.0.0` vs `127.0.0.1` — le tableau à retenir

| | `127.0.0.1` / `localhost` | `0.0.0.0` |
|---|---|---|
| Côté **serveur** (`--host`, `--bind`) | n'accepte que les connexions locales | accepte toutes les interfaces |
| Côté **client** (une URL) | « la machine d'où je parle » | **jamais utilisé** — ce n'est pas une destination |

Les **quatre** occurrences rencontrées jusqu'ici :

1. Le tunnel SSH du module 2
2. `mlflow server --host` (§3) — sinon le conteneur est refusé
3. `set_tracking_uri("http://127.0.0.1:5000")` dans `predict.py` (§10) — le conteneur a son propre 127.0.0.1
4. `gunicorn --bind` (§11) — sinon le `-p` ne sert à rien

**`localhost` est toujours relatif à qui parle.** Si tu ne retiens qu'une phrase de tout ce document, que ce soit celle-là.

---

## 17. Différences avec le setup `web-service`

| | `web-service` | `web-service-mlflow` |
|---|---|---|
| **Source du modèle** | fichier `lin_reg.bin` dans le dossier | registre MLflow, via `models:/m-…` |
| **Chargement** | `pickle.load()` sur un fichier local | `mlflow.pyfunc.load_model(URI)` |
| **Ce que contient le modèle** | tuple `(dv, model)` | un `Pipeline` complet |
| **Dans `predict()`** | `dv.transform()` puis `model.predict()` | `model.predict()` seul |
| **Configuration** | aucune — tout est en dur | 2 variables d'environnement (`MODEL_URI`, `MLFLOW_TRACKING_URI`) |
| **Réponse HTTP** | `{'duration': …}` | `{'duration': …, 'model_version': …}` |
| **Python** | 3.10.21 | 3.11.16 |
| **scikit-learn** | `==1.0.2` (imposé par le pickle du cours) | `==1.9.0` (celui qui a entraîné) |
| **Contraintes supplémentaires** | `numpy<2` (ABI de sklearn 1.0.2) | aucune |
| **Pourquoi un pipenv** | l'environnement de dev ≠ l'environnement du pickle | uniquement pour Docker |
| **`[dev-packages]`** | `requests` (pour `test.py`) | — (vide dans le dépôt ; `requests` à ajouter, voir §9) |
| **Image de base** | `python:3.10.21-slim` | `python:3.11-slim` |
| **`COPY` du code** | `predict.py` **et** `lin_reg.bin` | `predict.py` seul — le modèle n'est plus dans l'image |
| **`.dockerignore`** | absent | présent |
| **`docker run`** | `-p` seulement | `-p`, `-e ×2`, `--add-host`, `-v` |
| **Dépendances au runtime** | aucune — l'image est autonome | serveur MLflow + dossier `artifacts/` monté |
| **Tag** | `:v1` | `:v2` |
| **Changer de modèle** | rebuild + redéploiement de l'image | changer une variable d'environnement |
| **Terminaux nécessaires** | 2 | **3** (MLflow en plus) |

### Le compromis, en une phrase

> `web-service` produit une image **autonome mais figée**.
> `web-service-mlflow` produit une image **flexible mais couplée**.

Ni l'un ni l'autre n'est « la bonne réponse ». Le vrai objectif, c'est d'avoir les deux à la fois — et c'est ce que permet le `s3://` : un modèle changeable par variable d'environnement, **sans** dépendre d'un serveur de tracking au démarrage.

### Les quatre couches d'isolation

Le fil conducteur de tout le module, vu d'en haut. À chaque étape, on ferme une porte d'entrée aux problèmes :

| Couche | Ce qu'elle garantit | Ce qu'elle ne garantit pas |
|---|---|---|
| **Le `Pipeline`** | le préprocessing voyage avec le modèle | rien sur les versions de bibliothèques |
| **Pipenv + `Pipfile.lock`** | les versions exactes des paquets Python | rien sur Python, l'OS, les libs système |
| **Docker** | l'environnement complet : OS, Python, paquets, code | rien sur *où* ça tourne |
| **Le tag d'image** | quelle version précise est déployée, et le retour arrière | — |

Chaque couche répond à une question de la forme « *et si l'environnement d'exécution n'était pas celui que je crois ?* ». C'est, en une phrase, ce que signifie **productioniser** un modèle.

---

## 18. Dépannage

| Symptôme | Piste |
|---|---|
| `[Errno 111] Connection refused` sur `test.py` | le service ne tourne pas, ou pas sur 9696 |
| `RuntimeError: MODEL_URI n'est pas définie` — ou, sans la garde du §4, une traceback MLflow parlant d'URI invalide / `NoneType` au démarrage | **`MODEL_URI` non exportée dans ce terminal** → `echo $MODEL_URI` |
| `Connection refused` au démarrage du conteneur | MLflow éteint, lancé sur `--host 127.0.0.1`, ou `MLFLOW_TRACKING_URI` mal formé |
| `FileNotFoundError` sur `/workspaces/…` depuis le conteneur | le `-v` manque, ou les deux chemins diffèrent |
| Erreur de dépicklage / `InconsistentVersionWarning` | versions du `Pipfile` ≠ versions d'entraînement |
| `--deploy` échoue au build | `Pipfile` et `Pipfile.lock` désynchronisés → `pipenv lock` ; ou version Python de l'image ≠ `[requires]` |
| `OSError: Address already in use` | un serveur tourne déjà sur ce port → `lsof -i :9696` puis `kill` |
| `[CRITICAL] WORKER TIMEOUT` en boucle au démarrage de gunicorn | le chargement du modèle dépasse les 30 s par défaut → `--timeout 120` ou `--preload` (§7) |
| `docker build … requires 1 argument` | le `.` du contexte est oublié |
| `TypeError: Object of type float64 is not JSON serializable` | il manque le `float()` autour de `preds[0]` |
| Le code modifié n'a aucun effet | fichier non sauvegardé (`●` dans l'onglet VS Code), ou image non reconstruite |
| `NoCredentialsError` | l'URI pointe sur `s3://` — MLflow cherche des clés AWS |

### Inspecter l'intérieur d'une image

```bash
docker run -it --rm --entrypoint=bash ride-duration-prediction-service:v2
```

Tu obtiens un shell dedans, **sans lancer gunicorn**. Utile pour vérifier ce qui a été installé et ce qui est visible :

```bash
ls -la /app
pip list | grep -E "scikit|mlflow|flask|gunicorn"
python -c "import sys; print(sys.version)"
```

### La méthode

Un rappel qui vaut plus que la liste ci-dessus : **tu introduis beaucoup de nouveautés d'un coup** dans ce chapitre — MLflow, pipenv, Docker, variables d'environnement, volumes. Si ça casse, **ne modifie qu'une chose à la fois**.

Fais marcher le code d'abord, empaquette-le ensuite. Si tu introduis Docker et MLflow en même temps et que ça casse, tu ne sais pas lequel des deux accuser.

Et quand une erreur te semble absurde au regard de ton code, **suspecte le contexte avant la logique** :

```bash
which python           # quel interpréteur ?
pwd                    # quel dossier ?
conda env list         # quels environnements ?
echo $MODEL_URI        # quelle configuration ?
head -20 predict.py    # quel contenu réel sur le disque ?
lsof -i :9696          # qui occupe le port ?
docker ps              # quels conteneurs tournent ?
```

---

## 19. Cheat sheet des commandes

### Le parcours complet

```bash
# ═══ Terminal 1 : MLflow ═══
conda activate mlopszoomcamp
cd /workspaces/mlops-zoomcamp/04-deployment/web-service-mlflow
mlflow server \
  --backend-store-uri sqlite:////workspaces/mlops-zoomcamp/04-deployment/web-service-mlflow/mlflow.db \
  --default-artifact-root /workspaces/mlops-zoomcamp/04-deployment/web-service-mlflow/artifacts \
  --host 0.0.0.0 --port 5000

# ═══ Notebook : entraîner ═══
# → run random-forest.ipynb, noter model_info.model_uri

# ═══ Relever les versions ═══
python -c "import sys, sklearn, mlflow; print(sys.version.split()[0], sklearn.__version__, mlflow.__version__)"

# ═══ Créer le pipenv (une seule fois) ═══
rm -f Pipfile Pipfile.lock
pipenv install --python=3.11 scikit-learn==1.9.0 mlflow==3.16.0 skops==0.14.0 flask gunicorn

# ═══ Terminal 2 : le service ═══
conda activate mlopszoomcamp
export MODEL_URI='models:/m-5e276730f7004842b7c3a36ea11b5044'
echo $MODEL_URI

python predict.py                                  # (a) serveur de dev Flask
gunicorn --bind=0.0.0.0:9696 predict:app           # (b) serveur de production

# (c) Docker  — le « . » final est le contexte, donc le cd compte
cd /workspaces/mlops-zoomcamp/04-deployment/web-service-mlflow
docker build -t ride-duration-prediction-service:v2 .
docker run -it --rm \
  -p 9696:9696 \
  --add-host=host.docker.internal:host-gateway \
  -e MLFLOW_TRACKING_URI='http://host.docker.internal:5000' \
  -e MODEL_URI='models:/m-5e276730f7004842b7c3a36ea11b5044' \
  -v "$PWD/artifacts:$PWD/artifacts:ro" \
  ride-duration-prediction-service:v2

# ═══ Terminal 3 : tester — identique dans les 3 cas ═══
conda activate mlopszoomcamp
python test.py
```

### pipenv

| Commande | Effet |
|---|---|
| `pipenv install` | installe depuis le `Pipfile.lock` **si** il est cohérent avec le `Pipfile` ; sinon **re-résout** d'abord — et peut donc changer des versions sans te le dire |
| `pipenv sync` | installe **strictement** ce que dit le `Pipfile.lock`, sans jamais re-résoudre. Le bon réflexe sur un projet qu'on reprend |
| `pipenv install --dev` | idem + les `[dev-packages]` |
| `pipenv install <paquet>` | ajoute au Pipfile et re-résout le lock |
| `pipenv install --python=3.11` | impose l'interpréteur (le **trouve**, ne l'installe pas) |
| `pipenv lock` | régénère le lock depuis le Pipfile. **Jamais anodin sur un projet ancien** |
| `pipenv run <commande>` | exécute dans l'env, sans sous-shell. **À privilégier** |
| `pipenv shell` | lance un sous-shell. Conda peut s'y réinviter |
| `pipenv --venv` | affiche le chemin du virtualenv |
| `pipenv --rm` | supprime le virtualenv du projet |

> Pipenv cherche un `Pipfile` dans le répertoire courant, puis remonte de parent en parent. D'où l'importance du `cd`. Le nom du virtualenv (`web-service-mlflow-ToH4o1-o`) combine le nom du dossier et une empreinte de son chemin absolu.

### Docker

```bash
docker build -t nom:tag .
docker run -it --rm -p 9696:9696 nom:tag
docker images                                    # lister les images
docker ps                                        # conteneurs en cours
docker ps -a                                     # + les conteneurs arrêtés
docker logs <container_id>                       # les logs d'un conteneur
docker exec -it <id> bash                        # shell DANS un conteneur qui tourne
docker run -it --rm --entrypoint=bash nom:tag    # shell dans l'image, sans la démarrer
docker system prune                              # nettoyer images/conteneurs orphelins
```

### Diagnostic

```bash
which python                                     # quel binaire sera exécuté
python -c "import sys; print(sys.executable)"    # confirmation depuis Python
python -m pip freeze                             # le -m force le pip de l'interpréteur courant
echo $PATH | tr ':' '\n'                         # la liste des dossiers fouillés
echo $MODEL_URI                                  # la config du shell courant
lsof -i :9696                                    # qui occupe le port
kill $(lsof -t -i:9696)                          # le libérer
curl http://127.0.0.1:5000                       # MLflow répond-il ?
```

> `pip freeze` lit les métadonnées du gestionnaire de paquets. `import sklearn` interroge le module réellement chargé. En cas de désaccord, **c'est l'import qui dit la vérité**. D'où le réflexe `python -m pip` plutôt que `pip`.

---

## Ce qu'il faut retenir en trois phrases

1. **Le client ne change jamais.** `test.py` interroge une URL et un port ; ce qu'il y a derrière — Flask, gunicorn, un conteneur — ne le regarde pas. C'est ça, une interface.
2. **`localhost` est toujours relatif à qui parle.** Quatre pannes de ce seul module viennent de là, et tu en recroiseras d'autres.
3. **Ce qui dépend de l'endroit où le code tourne doit sortir du code.** Adresses, chemins, identifiants de modèle : dans l'environnement, pas dans le fichier.

---

*Document de notes personnelles — MLOps Zoomcamp, module 4, partie `web-service-mlflow`.*
*Complément : `04-python-web-service-mlflow.md` — le notebook, `make_pipeline` et les API MLflow.*
