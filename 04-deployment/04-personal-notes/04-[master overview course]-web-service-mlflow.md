# Cours : workflow et flux d'information — Web service + modèle MLflow (`04-deployment/web-service-mlflow`)

> **Dossier** : `04-deployment/web-service-mlflow/` : `random-forest.ipynb`, `predict.py`, `test.py`, `dict_vectorizer.bin`, `Pipfile`, `Pipfile.lock`, `README.md`. Ton fork ajoute `Dockerfile` et `.dockerignore`.
> **Vidéo** : 4.3 « Web-services: Getting the models from the model registry (MLflow) ».
> **Ton fork et l'original** : `test.py`, `README.md` et `dict_vectorizer.bin` sont identiques. Diffèrent :
> - `predict.py` : URI `models:/m-…` et adresse du serveur MLflow lues dans l'environnement ;
> - `random-forest.ipynb` : MLflow 3 (`name=`, `model_info.model_uri`), `root_mean_squared_error`, cellules d'inspection ajoutées ;
> - `Pipfile` : Python 3.11 (avec `python_full_version = "3.11.16"`), scikit-learn 1.9.0, mlflow 3.16.0, skops 0.14.0 ; `boto3` retiré ; `[dev-packages]` vide (plus de `requests`) ;
> - `Pipfile.lock` : recalculé en conséquence (mlflow 1.26.1 dans l'original, 3.16.0 dans ton fork) ;
> - `Dockerfile` et `.dockerignore` n'existent que dans ton fork.
>
> Comparaison faite le 01/10/2026.
>
> **Convention** : le cours suit l'ordre de la vidéo. Quand ton fork fait autrement, un encadré **▲ Ton fork** donne la commande que tu tapes réellement dans ton Codespace.
>
> **Avant** : `cours-04-web-service-flux.md` (vidéo 4.2). **Après** : `cours-04-streaming-kinesis-lambda.md` (vidéo 4.4).

---

## 1. La vision globale

Au 4.2, le modèle était un fichier (`lin_reg.bin`) **copié dans le service**. Changer de modèle voulait dire changer de fichier et reconstruire l'image. Ici, le modèle vit dans **MLflow**, et le service va le chercher au démarrage à partir d'un identifiant.

Il y a deux moments bien distincts : l'**entraînement** (une fois) et le **service** (au démarrage, puis à chaque requête).

```
 ENTRAÎNEMENT (une fois)                              SERVICE

 ┌──────────────────────┐ ① params, métrique, ┌──────────────────────────┐
 │ random-forest.ipynb  │   « un modèle est   │ Serveur MLflow, port 5000│
 │ (Jupyter)            │   rangé ici »       │ métadonnées → mlflow.db  │
 │                      │────────────────────▶│ (SQLite)                 │
 └──────────────────────┘                     └──────────────────────────┘
            │ ② écrit les fichiers                ▲                 │
            │   du modèle                         │ ③ « où est le   │ réponse :
            ▼                                     │   modèle X ? »  │ un chemin
 ┌──────────────────────────┐              ┌──────┴─────────────────▼──┐
 │ Stockage des artefacts   │ ④ lit les    │ predict.py, port 9696     │
 │ vidéo : bucket S3        │   fichiers   │ (Flask ou gunicorn)       │
 │ ton fork : dossier       │─────────────▶│ modèle chargé en mémoire  │
 │ artifacts/ du Codespace  │              └───────────────────────────┘
 └──────────────────────────┘                    ▲              │
                                       ⑤ POST    │              │ ⑥ {"duration": …,
                                    /predict ┌───┴──────────────▼──┐  "model_version": …}
                                             │ test.py (le client) │
                                             └─────────────────────┘
```

| N° | Qui | Fait quoi |
|---|---|---|
| ① | Le notebook | Envoie au serveur MLflow les paramètres, la métrique RMSE et la déclaration du modèle. Le serveur les écrit dans `mlflow.db`. |
| ② | Le notebook, **lui-même** | Écrit les fichiers du modèle dans le stockage d'artefacts : le serveur lui a seulement indiqué **où**. |
| ③ | `predict.py`, au démarrage | Demande au serveur où se trouve le modèle demandé. Le serveur lit `mlflow.db` et répond par un chemin (`s3://…` ou `/workspaces/…`). |
| ④ | `predict.py`, **lui-même** | Lit les fichiers à ce chemin et charge le modèle en mémoire. **Une seule fois.** |
| ⑤⑥ | `test.py` ↔ `predict.py` | À chaque requête : même échange qu'au 4.2. MLflow **n'intervient plus**. La réponse indique en plus quel modèle a répondu. |

Le fil de la vidéo, résumé : d'abord servir le modèle **avec** le serveur MLflow (③ puis ④), puis montrer que si le serveur tombe, le service ne démarre plus, et donc charger le modèle **directement** depuis son stockage (④ seul).

Trois mots reviennent sans cesse :

| Mot | Sens ici |
|---|---|
| **Run** | Une exécution d'entraînement enregistrée dans MLflow (le bloc `with mlflow.start_run():`), avec son identifiant `RUN_ID`. |
| **URI** | Une adresse sous forme de texte, qui dit où trouver une ressource : `runs:/<RUN_ID>/model`, `models:/m-…`, `s3://bucket/chemin`, ou un simple chemin de dossier. |
| **`pyfunc`** | Le format générique de MLflow : `mlflow.pyfunc.load_model(uri)` charge n'importe quel modèle MLflow et lui donne une méthode `.predict()`, quelle que soit la bibliothèque d'origine. |

> **« Model registry » : une nuance.** Le titre de la vidéo parle du registre de modèles, mais le code de ce dossier n'y inscrit pas le modèle (pas de `registered_model_name` dans `log_model`). Il le désigne par son run (`runs:/…`, vidéo) ou par son identifiant de modèle (`models:/m-…`, ton fork). Un modèle **inscrit au registre** aurait une adresse stable du type `models:/<nom>/<version>` ou `models:/<nom>@<alias>` : c'est l'étape que décrit la page `03-model-registry-serving.md` du dépôt d'origine.

**Attention aux numéros de terminaux** : au 4.2, il y en avait deux (1 = service, 2 = client). Ici il y en a trois : **1 = serveur MLflow**, **2 = service**, **3 = client**.

Les phases, dans l'ordre de la vidéo :

| Phase | Ce qu'on fait | Dans la vidéo | Dans ton fork |
|---|---|---|---|
| 0 | Préparer le dossier et l'environnement | Oui | Oui |
| 1 | Lancer le serveur MLflow | Oui (artefacts sur S3) | Oui (artefacts locaux) |
| 2 | Entraîner et enregistrer le modèle | Oui | Oui (MLflow 3) |
| 3 | Servir **avec** le serveur MLflow | Oui (`runs:/…`) | Oui (`models:/m-…`) |
| 4 | Servir **sans** le serveur MLflow | Oui (`s3://…`) | Possible sans changer le code (chemin local) |
| 5 | Mettre le service dans Docker | Non | Oui (ajout de ton fork) |

---

## 2. Phase 0 : préparer le dossier et l'environnement

### Dans le terminal (vidéo)

La vidéo part d'une copie du dossier `web-service` (`README` : « Take the code from the previous video »). Le `Pipfile` du dossier ajoute deux paquets à ceux du 4.2 :

```bash
pipenv install mlflow boto3      # mlflow pour charger le modèle, boto3 pour lire S3
```

Pour utiliser S3, la machine doit aussi avoir des **identifiants AWS** (`aws configure`) : c'est le notebook et `predict.py` qui écrivent et lisent dans le bucket, avec ces identifiants.

> **▲ Ton fork**
> Pas d'AWS : les artefacts restent dans le dossier `artifacts/` du Codespace.
> Pas de pipenv pour travailler : **tout ce qui tourne hors Docker** (serveur MLflow, notebook, `predict.py`, `test.py`) tourne dans ton env conda `mlopszoomcamp`. C'est toi qui as entraîné le modèle dans cet environnement, donc les versions correspondent forcément. Le `Pipfile` ne sert qu'à construire l'image Docker (phase 5).
> Les données doivent être dans `data/` (le `.gitignore` les exclut du dépôt) :
>
> ```bash
> cd /workspaces/mlops-zoomcamp/04-deployment/web-service-mlflow
> ls data/green_tripdata_2021-0[12].parquet || (
>   mkdir -p data && cd data
>   wget https://d37ci6vzurychx.cloudfront.net/trip-data/green_tripdata_2021-01.parquet
>   wget https://d37ci6vzurychx.cloudfront.net/trip-data/green_tripdata_2021-02.parquet
> )
> ```

---

## 3. Phase 1 : lancer le serveur MLflow (Terminal 1)

### Dans le terminal (vidéo, `README.md`)

```bash
mlflow server \
    --backend-store-uri=sqlite:///mlflow.db \
    --default-artifact-root=s3://mlflow-models-alexey/
```

### Ce que fait la commande

| Option | Rôle |
|---|---|
| `--backend-store-uri` | Où ranger les **métadonnées** (runs, paramètres, métriques, emplacement des modèles) : une base SQLite, `mlflow.db`. |
| `--default-artifact-root` | Où ranger les **fichiers** des modèles. Le serveur ne fait que transmettre cette adresse : ce sont les clients qui y lisent et écrivent. |
| (aucun `--host`) | Par défaut, le serveur n'écoute que sur `127.0.0.1:5000` : seulement les connexions venant de la machine elle-même. |

Le terminal reste bloqué : le serveur tourne. L'interface web est sur le port 5000.

> **▲ Ton fork**
>
> ```bash
> conda activate mlopszoomcamp
> cd /workspaces/mlops-zoomcamp/04-deployment/web-service-mlflow
>
> mlflow server \
>   --backend-store-uri sqlite:////workspaces/mlops-zoomcamp/04-deployment/web-service-mlflow/mlflow.db \
>   --default-artifact-root /workspaces/mlops-zoomcamp/04-deployment/web-service-mlflow/artifacts \
>   --host 0.0.0.0 --port 5000 \
>   --allowed-hosts "localhost:5000,127.0.0.1:5000,host.docker.internal:5000"
> ```
>
> - Chemins **absolus** : `sqlite:////…` (quatre barres = chemin absolu), pour que la base ne soit jamais créée ailleurs selon le dossier où tu te trouves.
> - `--host 0.0.0.0` : accepter aussi les connexions venant d'un conteneur Docker (phase 5).
> - `--allowed-hosts` : **nouveau, absent de tes notes actuelles**. Les versions récentes de MLflow 3 (dont la 3.16) refusent les requêtes dont l'en-tête `Host` (le nom de machine écrit dans l'URL appelée) n'est ni `localhost` ni une adresse IP privée. Un conteneur qui appelle `http://host.docker.internal:5000` reçoit alors `403 Invalid Host header - possible DNS rebinding attack detected` (vérifié avec MLflow 3.16.0). La liste remplace la valeur par défaut : il faut donc y remettre `localhost:5000` et `127.0.0.1:5000`, sinon le notebook et ton navigateur sont refusés à leur tour. Inutile si tu ne fais pas la phase 5.

---

## 4. Phase 2 : entraîner et enregistrer le modèle (`random-forest.ipynb`)

### Ce que tu fais

1. Vérifie que le **terminal 1** fait tourner le serveur MLflow (phase 1).
2. Ouvre `random-forest.ipynb` dans VS Code et choisis le noyau (*kernel*, en haut à droite) **`mlopszoomcamp`**.
3. Exécute les cellules dans l'ordre. Le notebook lit `data/...parquet` **relativement à son propre dossier** : les données doivent être dans `web-service-mlflow/data/`.
4. Note l'identifiant affiché (vidéo : le `RUN_ID`, lu dans l'interface MLflow ; ton fork : le `model_uri`, voir l'encadré plus bas).

### Ce que fait le notebook, cellule par cellule

1. **Connexion à MLflow** : `mlflow.set_tracking_uri("http://127.0.0.1:5000")` et `mlflow.set_experiment("green-taxi-duration")`. Toutes les écritures de **métadonnées** suivantes passent par le serveur de la phase 1 (les fichiers du modèle, eux, sont écrits directement dans le stockage : étape ② du §1).
2. **Données** : `read_dataframe` lit janvier (entraînement) et février 2021 (validation), calcule la durée en minutes et garde les courses de 1 à 60 minutes ; `prepare_dictionaries` fabrique `PU_DO` (« départ_arrivée ») et `trip_distance`, sous forme de liste de dictionnaires.
3. **Entraînement, dans `with mlflow.start_run():`** : un run MLflow s'ouvre. On y enregistre les hyperparamètres (`log_params`), on entraîne, on calcule le RMSE sur février (`log_metric`), on enregistre le modèle (`log_model`).

### Deux versions successives dans la vidéo

| | Première version | Version finale (celle du dossier) |
|---|---|---|
| Objets | Un `DictVectorizer` et un `RandomForestRegressor` séparés | **Un seul objet** : `make_pipeline(DictVectorizer(), RandomForestRegressor(...))` |
| Enregistrement | Le vectoriseur comme fichier à part (`dict_vectorizer.bin`), le modèle avec `log_model` | `mlflow.sklearn.log_model(pipeline, artifact_path="model")` |
| Ce que `predict.py` doit faire | Télécharger **et** le modèle **et** le vectoriseur (`MlflowClient().download_artifacts(...)`), puis `dv.transform` avant `model.predict` | Charger **un** objet, qui transforme et prédit d'un coup |

Les vestiges de la première version sont encore dans le dossier : le fichier `dict_vectorizer.bin`, les dernières cellules du notebook (`client.download_artifacts(run_id=RUN_ID, path='dict_vectorizer.bin')`, `pickle.load`) et le `import pickle` de `predict.py`. Ils ne servent plus.

### Où tout est rangé ensuite

| Quoi | Où (vidéo, tournée en 2022 avec MLflow 1.26) |
|---|---|
| Paramètres, métrique, existence du run | `mlflow.db`, via le serveur |
| Fichiers du modèle | `s3://mlflow-models-alexey/1/<RUN_ID>/artifacts/model/` (`1` = l'identifiant de l'expérience) |
| L'identifiant à retenir | Le **`RUN_ID`**, copié depuis l'interface MLflow |

> **▲ Ton fork (MLflow 3 et scikit-learn 1.9)**
> - `model_info = mlflow.sklearn.log_model(pipeline, name="model")` : `artifact_path=` est remplacé par `name=`.
> - `root_mean_squared_error(y_val, y_pred)` : l'option `squared=False` a été supprimée en scikit-learn 1.6.
> - L'identifiant à retenir n'est plus le run mais le **modèle** : la cellule d'entraînement (`with mlflow.start_run() as run:`) affiche `run_id   : …` et `model_uri: models:/m-…`. Note les deux : le `model_uri` pour `MODEL_URI` (phases 3 et 5), le `run_id` pour la commande `mlflow artifacts download` (phase 4). Ils changent à chaque réentraînement : relis-les toujours dans le notebook.
> - Cellules ajoutées pour inspecter le résultat : `mlflow.artifacts.list_artifacts(artifact_uri=model_info.model_uri)` liste les fichiers du modèle ; la dernière recharge le pipeline et en extrait le `DictVectorizer` (`pipeline.named_steps['dictvectorizer']`). Les cellules vestiges (`download_artifacts`, `pickle.load`, `dv`) sont commentées ; l'une affiche encore une ancienne erreur `NameError`, sans conséquence.
> - Les fichiers sont rangés ailleurs (vérifié) :
>
> ```
> artifacts/
> └── 1/                                  ← identifiant de l'expérience
>     └── models/
>         └── m-<model_id>/
>             └── artifacts/              ← LE DOSSIER DU MODÈLE
>                 ├── MLmodel             ← fiche d'identité : run_id, versions, format
>                 ├── model.skops         ← le pipeline, sérialisé avec skops (et non pickle)
>                 ├── requirements.txt    ← les versions exactes utilisées
>                 ├── python_env.yaml
>                 └── conda.yaml
> ```

---

## 5. Phase 3 : servir le modèle AVEC le serveur MLflow (sans Docker)

### Le code (version reconstituée de la vidéo : dans le fichier final, seule la ligne `runs:/` subsiste, en commentaire)

```python
mlflow.set_tracking_uri('http://127.0.0.1:5000')    # où est le serveur
RUN_ID = '...'                                      # copié depuis l'interface MLflow
logged_model = f'runs:/{RUN_ID}/model'              # « le modèle nommé model dans ce run »
model = mlflow.pyfunc.load_model(logged_model)

def predict(features):
    preds = model.predict(features)                 # plus de dv.transform : le pipeline s'en charge
    return float(preds[0])
```

La réponse du service contient maintenant `'model_version': RUN_ID` : le client sait quel modèle a produit la prédiction.

### Étape 1 — Terminal 2 : lancer le service

```bash
pipenv shell          # vidéo
python predict.py     # (ou gunicorn --bind=0.0.0.0:9696 predict:app, comme au 4.2)
```

### Étape 2 — Terminal 3 : lancer le client

```bash
python test.py
# → {'duration': ..., 'model_version': '<RUN_ID>'}
```

### Ce que font les scripts

```
 Terminal 2 : predict.py           Terminal 1 : serveur MLflow          Stockage (S3 / artifacts/)
        │                                   │                                    │
        │── ① « où est runs:/<id>/model ? »▶│                                    │
        │                                   │ ② lit mlflow.db                    │
        │◀── ③ « à tel chemin » ────────────│                                    │
        │                                                                        │
        │── ④ télécharge les fichiers du modèle ────────────────────────────────▶│
        │◀───────────────────────────────────────────────────────────────────────│
        │ ⑤ modèle en mémoire ; Flask/gunicorn écoute sur 9696
        │
        │◀── ⑥ POST /predict (test.py) ── ⑦ réponse JSON ──▶   (MLflow n'est plus contacté)
```

| N° | Ce qui se passe |
|---|---|
| ①–③ | Au démarrage, `load_model` interroge le serveur, qui lit `mlflow.db` et renvoie l'emplacement des fichiers. |
| ④ | `predict.py` télécharge lui-même les fichiers : depuis S3 avec boto3 dans la vidéo (d'où les identifiants AWS), depuis le disque dans ton fork. |
| ⑤ | Le modèle est en mémoire. Le serveur web démarre. |
| ⑥⑦ | Chaque requête : `prepare_features` → `model.predict` → `{'duration', 'model_version'}`. Aucun appel à MLflow. |

> **▲ Ton fork**
> Ton `predict.py` lit sa configuration dans l'environnement, sans valeur écrite en dur :
>
> ```python
> MLFLOW_TRACKING_URI = os.getenv('MLFLOW_TRACKING_URI', 'http://127.0.0.1:5000')
> mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
> MODEL_URI = os.getenv('MODEL_URI')
> model = mlflow.pyfunc.load_model(MODEL_URI)
> ```
>
> **Terminal 2 :**
>
> ```bash
> conda activate mlopszoomcamp
> cd /workspaces/mlops-zoomcamp/04-deployment/web-service-mlflow
> export MODEL_URI='models:/m-<ton model_id>'      # lu dans model_info.model_uri
> python predict.py                                # ou : gunicorn --bind=0.0.0.0:9696 predict:app
> ```
>
> **Terminal 3 :**
>
> ```bash
> conda activate mlopszoomcamp                     # requests y est installé
> cd /workspaces/mlops-zoomcamp/04-deployment/web-service-mlflow
> python test.py
> # → {'duration': ..., 'model_version': 'models:/m-<ton model_id>'}
> ```
>
> - En tête de ton `predict.py`, le bloc placé entre `'''` (avec un `models:/m-5e27…` par défaut) est une simple chaîne de texte : il n'est **jamais exécuté**. Seul le bloc « docker container is used » compte.
> - `MLFLOW_TRACKING_URI` n'a pas besoin d'être exporté ici : la valeur par défaut `127.0.0.1:5000` convient hors Docker.
> - Si tu oublies `export MODEL_URI`, le service plante au démarrage : `TypeError: stat: path should be string, bytes, os.PathLike or integer, not NoneType` (c'est `load_model(None)`).
> - Le `runs:/<RUN_ID>/model` de la vidéo fonctionne encore avec MLflow 3.16 (vérifié) : MLflow retrouve le modèle nommé `model` dans ce run.

---

## 6. Phase 4 : servir le modèle SANS le serveur MLflow

### Le problème montré dans la vidéo

Le service dépend du serveur MLflow **au démarrage** (étapes ①–③). Si le serveur est arrêté, `predict.py` ne peut plus démarrer. Il continue en revanche de répondre s'il était déjà lancé : le modèle est en mémoire.

> **▲ Ton fork**, serveur arrêté et `MODEL_URI=models:/m-…` (vérifié) : le démarrage reste bloqué environ quatre minutes (le client MLflow réessaie 7 fois, en attendant de plus en plus longtemps entre deux essais), puis échoue avec `MlflowException: API request to http://127.0.0.1:5000/api/2.0/mlflow/logged-models/m-… failed with exception HTTPConnectionPool(host='127.0.0.1', port=5000): Max retries exceeded`.

### La solution de la vidéo : charger directement depuis S3

C'est le `predict.py` **final** du dépôt d'origine :

```python
RUN_ID = os.getenv('RUN_ID')                                          # lu dans l'environnement
logged_model = f's3://mlflow-models-alexey/1/{RUN_ID}/artifacts/model'
# logged_model = f'runs:/{RUN_ID}/model'                              # l'ancienne version
model = mlflow.pyfunc.load_model(logged_model)                        # plus de set_tracking_uri
```

**Terminal 2 :**

```bash
export RUN_ID="<le run_id>"
python predict.py
```

**Terminal 3 :** `python test.py` → `{'duration': ..., 'model_version': '<le run_id>'}`.

Ce qui change dans le flux : les étapes ①–③ disparaissent. `load_model` lit directement le dossier du modèle sur S3 (étape ④), avec boto3 et les identifiants AWS. Le serveur MLflow peut être éteint.

Le prix : `predict.py` doit connaître la **structure de rangement** de MLflow (`<expérience>/<run_id>/artifacts/model`), et c'est toi qui choisis le `RUN_ID` à servir.

### Variante du `README.md` : télécharger le modèle sur le disque

```bash
export MLFLOW_TRACKING_URI="http://127.0.0.1:5000"
export MODEL_RUN_ID="6dd459b11b4e48dc862f4e1019d166f6"

mlflow artifacts download \
    --run-id ${MODEL_RUN_ID} \
    --artifact-path model \
    --dst-path .
```

| Option | Rôle |
|---|---|
| `MLFLOW_TRACKING_URI` | La commande a besoin du serveur, **une fois**, pour savoir où sont les fichiers. |
| `--run-id`, `--artifact-path model` | Quel run, et quel dossier de ce run. |
| `--dst-path .` | Où écrire : un dossier `./model/` est créé dans le dossier courant (`MLmodel`, fichier du modèle, `requirements.txt`…). |

Ensuite, `mlflow.pyfunc.load_model('./model')` charge le modèle **sans serveur ni réseau**. C'est aussi un moyen de **copier** le modèle dans une image Docker.

> **▲ Ton fork : la même chose, sans toucher au code**
> `mlflow.pyfunc.load_model` accepte un simple chemin de dossier. Ton `predict.py` lisant `MODEL_URI` dans l'environnement, il suffit de lui donner le chemin du dossier du modèle (vérifié serveur arrêté, avec `python predict.py` comme avec gunicorn). Deux façons d'obtenir ce chemin : **choisis-en une**.
>
> Commence par arrêter le `predict.py` de la phase 3 (`Ctrl+C` dans le terminal 2) : il occupe le port 9696 et bloque le terminal.
>
> **Option A — le dossier déjà rangé par MLflow** (aucun serveur nécessaire)
>
> 1. Terminal 2 :
>    ```bash
>    conda activate mlopszoomcamp
>    cd /workspaces/mlops-zoomcamp/04-deployment/web-service-mlflow
>    ls -d artifacts/*/models/m-*                                # → artifacts/1/models/m-<model_id>  (1 = l'expérience)
>    export MODEL_URI=$PWD/artifacts/1/models/m-<model_id>/artifacts     # le chemin affiché, + /artifacts
>    ```
>
> **Option B — la commande du README** (le serveur doit tourner le temps du téléchargement)
>
> 1. Terminal 2, serveur MLflow toujours actif dans le terminal 1 :
>    ```bash
>    conda activate mlopszoomcamp
>    cd /workspaces/mlops-zoomcamp/04-deployment/web-service-mlflow
>    export MLFLOW_TRACKING_URI="http://127.0.0.1:5000"
>    mlflow artifacts download --run-id <ton run_id> --artifact-path model --dst-path .
>    export MODEL_URI=$PWD/model
>    ```
>
> **Ensuite, dans les deux cas**
>
> 2. Arrête le serveur MLflow (`Ctrl+C` dans le terminal 1), pour constater qu'il ne sert plus.
> 3. Terminal 2 : `python predict.py` (ou `gunicorn --bind=0.0.0.0:9696 predict:app`).
> 4. Terminal 3 : `python test.py`.
>
> - Sans l'`export MLFLOW_TRACKING_URI`, MLflow 3.16 ne contacte pas le serveur : il ouvre directement le fichier `mlflow.db` **du dossier courant**. Lancée depuis un autre dossier, la commande crée une base vide et échoue. D'où l'export.
> - La commande du README fonctionne telle quelle avec MLflow 3.16 (vérifié). Équivalent avec l'identifiant de modèle : `mlflow artifacts download --artifact-uri models:/m-<model_id> --dst-path ./model`.
> - `predict.py` appelle toujours `set_tracking_uri`, mais avec un chemin local `load_model` ne contacte pas le serveur.
> - `model_version` renverra alors le chemin du dossier, et non plus l'identifiant du modèle.

---

## 7. Phase 5 : le service dans Docker (▲ ton fork seulement)

La vidéo ne construit pas d'image pour ce dossier, et le dépôt d'origine n'a pas de `Dockerfile` ici. Ton fork en ajoute un.

### Le `Dockerfile` et le `.dockerignore`

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

| Ligne | Par rapport au 4.2 |
|---|---|
| `FROM python:3.11-slim` | Python 3.11 : la version mineure de l'entraînement. |
| `RUN pipenv install --system --deploy` | Installe le lock de ton fork : scikit-learn 1.9.0, mlflow 3.16.0, skops 0.14.0, flask, gunicorn. |
| `COPY ["predict.py", "./"]` | Le code **seulement** : pas de fichier modèle. |

Différence majeure avec le 4.2 : **le modèle n'est pas dans l'image**. Le conteneur va le chercher au démarrage, avec `MODEL_URI`. La même image peut donc servir n'importe quel modèle.

Le `.dockerignore` empêche d'envoyer à Docker ce qui n'a rien à faire dans l'image : `__pycache__/`, `*.ipynb`, `.ipynb_checkpoints/`, `mlflow.db`, `artifacts/`, `mlruns/`.

### Étape 1 — Terminal 1 : le serveur MLflow

Lancé avec `--host 0.0.0.0` et `--allowed-hosts` (commande de la phase 1).

### Étape 2 (facultative, recommandée) — tester le lock avant de construire

Dix secondes au lieu d'un build de plusieurs minutes : lancer le service **dans le virtualenv pipenv** du dossier, c'est-à-dire avec exactement les paquets qui iront dans l'image. Si ça démarre et que `test.py` répond, l'image fonctionnera aussi.

```bash
conda activate mlopszoomcamp
cd /workspaces/mlops-zoomcamp/04-deployment/web-service-mlflow
pipenv sync                                                     # si le virtualenv n'existe pas encore
export MODEL_URI='models:/m-<ton model_id>'
pipenv run gunicorn --bind=0.0.0.0:9696 predict:app             # puis python test.py dans le terminal 3, puis Ctrl+C
```

### Étape 3 — Terminal 2 : construire l'image et lancer le conteneur

```bash
cd /workspaces/mlops-zoomcamp/04-deployment/web-service-mlflow     # le « . » et le $PWD en dépendent
docker build -t ride-duration-prediction-service:v2 .

docker run -it --rm \
  -p 9696:9696 \
  --add-host=host.docker.internal:host-gateway \
  -e MLFLOW_TRACKING_URI='http://host.docker.internal:5000' \
  -e MODEL_URI='models:/m-<ton model_id>' \
  -v "$PWD/artifacts:$PWD/artifacts:ro" \
  ride-duration-prediction-service:v2
```

| Option | Rôle |
|---|---|
| `-p 9696:9696` | Publier le port du service, comme au 4.2. |
| `--add-host=host.docker.internal:host-gateway` | Créer dans le conteneur le nom `host.docker.internal`, qui désigne le Codespace. Dans un conteneur, `127.0.0.1` désigne **le conteneur lui-même**. |
| `-e MLFLOW_TRACKING_URI=...` | Dire à `predict.py` où joindre le serveur MLflow. |
| `-e MODEL_URI=...` | Quel modèle servir. |
| `-v chemin:chemin:ro` | Rendre le dossier `artifacts/` visible dans le conteneur, **au même chemin**, en lecture seule. |

### Étape 4 — Terminal 3 : le même client

```bash
conda activate mlopszoomcamp
cd /workspaces/mlops-zoomcamp/04-deployment/web-service-mlflow
python test.py
```

### Ce qui se passe

```
 CODESPACE                                                    CONTENEUR
 ┌──────────────────────────────┐                             ┌───────────────────────────────────┐
 │ Terminal 1 : MLflow :5000    │◀── ① « où est m-… ? » ──────│ gunicorn importe predict.py       │
 │   lit mlflow.db              │    host.docker.internal:5000│                                   │
 │                              │─── ② « /workspaces/…/       │                                   │
 │                              │      artifacts/1/models/…» ▶│                                   │
 │                              │                             │ ③ lit ce chemin : il existe grâce │
 │ dossier artifacts/ ══════════════════ monté par -v ══════════▶   au -v                         │
 │                              │                             │ ④ modèle en mémoire, écoute 9696  │
 │ Terminal 3 : test.py ────────────── ⑤ localhost:9696, -p ───▶ predict_endpoint()              │
 │              print(...) ◀────────── ⑥ réponse JSON ─────────│                                   │
 └──────────────────────────────┘                             └───────────────────────────────────┘
```

| N° | Ce qui se passe |
|---|---|
| ① | Au démarrage du conteneur, gunicorn importe `predict.py` ; `load_model('models:/m-…')` interroge le serveur MLflow du Codespace, par le nom créé avec `--add-host`. Le serveur accepte grâce à `--host 0.0.0.0` (l'interface réseau) et `--allowed-hosts` (le nom). |
| ② | Le serveur lit `mlflow.db` et répond par un **chemin du Codespace**. Il n'envoie pas les fichiers. |
| ③ | Le conteneur ouvre lui-même ce chemin. Sans le `-v`, il n'existerait pas dans le conteneur. |
| ④ | Le modèle est en mémoire ; gunicorn écoute sur `0.0.0.0:9696`. |
| ⑤⑥ | `test.py`, dans le Codespace, appelle `localhost:9696` ; Docker relaie vers le conteneur. |

Deux besoins, deux canaux : le **réseau** pour demander où est le modèle (`--add-host`, `MLFLOW_TRACKING_URI`), le **système de fichiers** pour le lire (`-v`).

### Variantes

**Plus courte (Linux uniquement)** : `--network=host` fait partager au conteneur le réseau du Codespace. `127.0.0.1:5000` fonctionne alors tel quel, sans `--add-host`, sans `-p`, et sans `--allowed-hosts`.

```bash
docker run -it --rm --network=host \
  -e MODEL_URI='models:/m-<ton model_id>' \
  -v "$PWD/artifacts:$PWD/artifacts:ro" \
  ride-duration-prediction-service:v2
```

**Sans serveur MLflow**, l'équivalent Docker de la phase 4 : monter seulement le dossier du modèle et le désigner par son chemin. Plus de réseau vers MLflow.

```bash
docker run -it --rm -p 9696:9696 \
  -e MODEL_URI=/model \
  -v "$PWD/model:/model:ro" \
  ride-duration-prediction-service:v2
```

`$PWD/model` est le dossier téléchargé à la phase 4 (option B). Avec l'option A, monte à la place le dossier rangé par MLflow : `-v "$PWD/artifacts/1/models/m-<model_id>/artifacts:/model:ro"`.

---

## 8. Synthèse des configurations

### Dans la vidéo

| | Phase 3 : avec serveur | Phase 4 : sans serveur (S3) | Variante README : modèle téléchargé |
|---|---|---|---|
| **Terminal 1** | `mlflow server ... --default-artifact-root=s3://...` | Facultatif | Le temps du `mlflow artifacts download` |
| **Variable** | `RUN_ID` (en dur, puis `export`) | `export RUN_ID=...` | `MODEL_RUN_ID` pour le téléchargement |
| **URI donnée à `load_model`** | `runs:/<RUN_ID>/model` | `s3://mlflow-models-alexey/1/<RUN_ID>/artifacts/model` | `./model` |
| **Qui dit où est le modèle** | Le serveur MLflow (`mlflow.db`) | Le code (chemin construit à la main) | Le code (chemin local) |
| **D'où viennent les fichiers** | S3, lus par `predict.py` | S3, lus par `predict.py` | Le disque |
| **Besoin du serveur au démarrage** | Oui | Non | Non |
| **Terminal 2 / 3** | `python predict.py` / `python test.py` | idem | idem |

### Dans ton fork

| | Avec serveur | Sans serveur | Docker avec serveur | Docker sans serveur |
|---|---|---|---|---|
| **Terminal 1** | `mlflow server` (phase 1) | — | `mlflow server` avec `--host 0.0.0.0` et `--allowed-hosts` | — |
| **`MODEL_URI`** | `models:/m-…` | Chemin du dossier du modèle | `models:/m-…` | `/model` |
| **Terminal 2** | `python predict.py` ou `gunicorn ...` (env `mlopszoomcamp`) | idem | `docker run ... --add-host ... -v artifacts` | `docker run ... -v model:/model` |
| **Environnement Python du service** | conda `mlopszoomcamp` | conda `mlopszoomcamp` | Python de l'image (`Pipfile.lock`) | Python de l'image |
| **Terminal 3** | `python test.py` (env `mlopszoomcamp`) | idem | idem | idem |
| **`model_version` renvoyé** | `models:/m-…` | Le chemin | `models:/m-…` | `/model` |

---

## 9. Le dossier, fichier par fichier

| Fichier | Rôle | Phase |
|---|---|---|
| `random-forest.ipynb` | Entraîne le pipeline `DictVectorizer` + `RandomForestRegressor`, l'enregistre dans MLflow | 2 |
| `predict.py` | Charge le modèle depuis MLflow au démarrage, sert `/predict` avec Flask | 3, 4, 5 |
| `test.py` | Le client HTTP, identique au 4.2 | 3, 4, 5 |
| `dict_vectorizer.bin` | Vestige de la première version (vectoriseur séparé). Inutilisé. | — |
| `Pipfile` / `Pipfile.lock` | Vidéo : l'environnement du service (avec mlflow, boto3). Ton fork : l'environnement de l'image Docker uniquement. | 0, 5 |
| `Dockerfile`, `.dockerignore` | Ton fork seulement : l'image du service, sans le modèle | 5 |
| `README.md` | Les étapes de la vidéo, la commande `mlflow server` avec S3, la commande `mlflow artifacts download` | — |
| *(créés en route)* `mlflow.db`, `artifacts/`, `data/`, `model/` | La base MLflow, les modèles (ton fork), les données, le modèle téléchargé. Ton `.gitignore` exclut de git `mlflow.db`, `artifacts/` et `data/` : si le Codespace est supprimé, il faut réentraîner. `model/` n'est pas exclu : il apparaîtra dans `git status`. | 1, 2, 4 |

| Étape du `README.md` | Section du cours |
|---|---|
| Take the code from the previous video | §2 |
| Train another model, register with MLflow | §3, §4 |
| Put the model into a scikit-learn pipeline | §4 (deux versions) |
| Model deployment with tracking server | §5 |
| Model deployment without the tracking server | §6 |
| Starting the MLflow server with S3 | §3 |
| Downloading the artifact | §6 (variante README) |

---

## 10. Si ça casse

| Symptôme | Cause probable | Correction |
|---|---|---|
| `TypeError: stat: path should be string ... not NoneType` au démarrage | `MODEL_URI` non exporté dans **ce** terminal | `export MODEL_URI=...` puis relancer |
| Démarrage bloqué, puis `MlflowException ... Max retries exceeded` | Serveur MLflow arrêté, ou mauvaise adresse | Relancer le terminal 1 ; ou passer en mode sans serveur (§6) |
| `403 ... Invalid Host header - possible DNS rebinding attack detected` (dans les logs du conteneur) | Serveur MLflow 3 lancé sans `--allowed-hosts` | Relancer avec `--allowed-hosts "localhost:5000,127.0.0.1:5000,host.docker.internal:5000"` (§3) |
| Depuis le conteneur, après une longue attente : `Failed to resolve 'host.docker.internal'` | `--add-host=host.docker.internal:host-gateway` absent du `docker run` | Ajouter l'option |
| Depuis le conteneur, après une longue attente : `Connection refused` | Serveur MLflow lancé sur `127.0.0.1`, ou `-e MLFLOW_TRACKING_URI` absent (le conteneur appelle alors **son propre** `127.0.0.1`) | `--host 0.0.0.0` au serveur ; vérifier le `-e MLFLOW_TRACKING_URI` |
| `FileNotFoundError` sur un chemin `/workspaces/.../artifacts/...` dans le conteneur | `-v` absent, ou lancé depuis un autre dossier (`$PWD` différent) | `cd` dans `web-service-mlflow` avant `docker run` |
| `docker build` refuse à `pipenv install --deploy` en parlant de la version de Python | `python_full_version = "3.11.16"` dans ton `Pipfile`, alors que l'image `python:3.11-slim` peut livrer une autre 3.11 (déjà signalé dans `04-[master-course]-IT-web-service-mlflow.md`, §11) | Retirer la ligne `python_full_version`, ou épingler l'image sur la même version |
| `mlflow artifacts download` : `Run with id=... not found` | Lancée sans `export MLFLOW_TRACKING_URI`, depuis un autre dossier : MLflow a ouvert (et créé) un `mlflow.db` vide | `export MLFLOW_TRACKING_URI="http://127.0.0.1:5000"`, ou `cd` dans `web-service-mlflow` |
| `test.py` : `ModuleNotFoundError: No module named 'requests'` | Lancé hors de `mlopszoomcamp` (la section `[dev-packages]` de ton `Pipfile` est vide) | `conda activate mlopszoomcamp` |

---

## 11. Reprise express (ton fork)

```bash
# ═══ Terminal 1 : MLflow ═══
conda activate mlopszoomcamp
cd /workspaces/mlops-zoomcamp/04-deployment/web-service-mlflow
mlflow server \
  --backend-store-uri sqlite:////workspaces/mlops-zoomcamp/04-deployment/web-service-mlflow/mlflow.db \
  --default-artifact-root /workspaces/mlops-zoomcamp/04-deployment/web-service-mlflow/artifacts \
  --host 0.0.0.0 --port 5000 \
  --allowed-hosts "localhost:5000,127.0.0.1:5000,host.docker.internal:5000"

# ═══ Notebook : entraîner (si besoin), noter model_info.model_uri ═══

# ═══ Terminal 2 : le service (au choix) ═══
conda activate mlopszoomcamp
cd /workspaces/mlops-zoomcamp/04-deployment/web-service-mlflow
export MODEL_URI='models:/m-<ton model_id>'
python predict.py                                   # (a) Flask dev
gunicorn --bind=0.0.0.0:9696 predict:app            # (b) gunicorn

# (c) sans serveur MLflow : pointer directement sur le dossier du modèle, puis (a) ou (b)
export MODEL_URI=$PWD/artifacts/1/models/m-<ton model_id>/artifacts

docker build -t ride-duration-prediction-service:v2 .      # (d) Docker (avec MODEL_URI='models:/m-…')
docker run -it --rm -p 9696:9696 \
  --add-host=host.docker.internal:host-gateway \
  -e MLFLOW_TRACKING_URI='http://host.docker.internal:5000' \
  -e MODEL_URI=$MODEL_URI \
  -v "$PWD/artifacts:$PWD/artifacts:ro" \
  ride-duration-prediction-service:v2

# ═══ Terminal 3 : tester — identique dans tous les cas ═══
conda activate mlopszoomcamp
cd /workspaces/mlops-zoomcamp/04-deployment/web-service-mlflow
python test.py
```

---

## 12. Ce qui a été vérifié pour ce cours

- Comparaison fichier par fichier de `web-service-mlflow/` entre ton fork et l'original (01/10/2026) ; `pipenv verify` : `Pipfile.lock` cohérent avec le `Pipfile`.
- Exécuté avec les versions de ton fork (Python 3.11, scikit-learn 1.9.0, mlflow 3.16.0, skops 0.14.0) et un serveur lancé comme le tien (SQLite + dossier `artifacts/` local, `--host 0.0.0.0`) : entraînement du pipeline et enregistrement avec `name="model"`, arborescence `artifacts/1/models/m-…/artifacts/`, `predict.py` de ton fork avec `models:/m-…` (Flask) et `test.py` contre lui, chargement par `runs:/<run_id>/model`, les trois formes de `mlflow artifacts download`, le démarrage avec serveur arrêté (échec avec `models:/`, succès avec un chemin local, sous Flask et gunicorn), l'erreur sans `MODEL_URI`, le service qui continue de répondre après l'arrêt du serveur, le délai d'échec au démarrage sans serveur (≈ 4 min), le refus `403` d'un en-tête `Host: host.docker.internal:5000` et son acceptation avec `--allowed-hosts`, le comportement de `mlflow artifacts download` sans `MLFLOW_TRACKING_URI`.
- Relecture par un agent indépendant, fichiers du dépôt à l'appui (exactitude, exhaustivité, lisibilité pour un débutant) ; ses corrections sont intégrées.
- Les données d'entraînement étaient **synthétiques** (le site des données NYC n'était pas joignable) et la forêt réduite à 10 arbres : les valeurs de durée et de RMSE ne sont pas celles de ton modèle. Seule la mécanique a été vérifiée.
- **Non exécuté** : S3 (pas de compte AWS) et Docker (Docker Hub inaccessible : aucune image n'a pu être construite). Le `403` a été reproduit avec le client Python MLflow hors conteneur, en faisant pointer `host.docker.internal` vers le serveur ; la commande `docker run` elle-même vient de ton dépôt et de tes notes.
- La première version de la vidéo (vectoriseur enregistré à part) est déduite des vestiges du dossier (`dict_vectorizer.bin`, cellules `download_artifacts`, `import pickle`).