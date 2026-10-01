# Cours : workflow et flux d'information — Web service Flask + Docker (`04-deployment/web-service`)

> **Dossier** : `04-deployment/web-service/` : `predict.py`, `test.py`, `lin_reg.bin`, `Pipfile`, `Pipfile.lock`, `Dockerfile`, `README.md`.
> **Vidéo** : 4.2 « Web-services: Deploying models with Flask and Docker ».
> **Ton fork et l'original** : `predict.py`, `test.py`, `lin_reg.bin` et `README.md` sont identiques. Trois fichiers diffèrent : `Pipfile` (Python 3.10 + `numpy<2`), `Pipfile.lock` (entièrement recalculé : flask 3.1.3, gunicorn 26.2.0, numpy 1.26.4… au lieu de flask 2.1.2, gunicorn 20.1.0, numpy 1.22.4) et `Dockerfile` (`python:3.10.21-slim`). Comparaison faite le 01/10/2026.
>
> **Convention** : le cours suit l'ordre de la vidéo. Quand ton fork fait autrement, un encadré **▲ Ton fork** donne la commande que tu tapes réellement dans ton Codespace.
>
> **La suite** : `cours-04-web-service-mlflow-flux.md` (vidéo 4.3), qui reprend ce dossier : `lin_reg.bin` y est remplacé par un modèle rangé dans MLflow, que le service va chercher au démarrage.

---

## 1. La vision globale

Le but : transformer le modèle du module 1 (un fichier `lin_reg.bin`) en **service web**. Un autre programme lui envoie une course en JSON, le service répond avec la durée prédite.

```
 ┌───────────────────┐                       ┌──────────────────────────────────────┐
 │ test.py           │ ① POST /predict       │ Serveur web, port 9696               │
 │ (le client)       │   {"PULocationID": 10,│   Flask (dev) OU gunicorn            │
 │                   │    "DOLocationID": 50,│   OU gunicorn dans un conteneur      │
 │                   │    "trip_distance":40}│             │                        │
 │                   │──────────────────────▶│             │ ② appelle              │
 │                   │                       │             ▼                        │
 │                   │                       │ predict.py : predict_endpoint()      │
 │                   │                       │   prepare_features → dv → model      │
 │                   │                       │             ▲                        │
 │                   │ ④ réponse JSON        │             │ ③ chargé UNE fois,     │
 │ print(...)        │◀──────────────────────│   lin_reg.bin   au démarrage         │
 └───────────────────┘ {"duration": 26.43…}  └──────────────────────────────────────┘
```

| N° | Qui | Fait quoi |
|---|---|---|
| ① | `test.py` | Envoie une requête HTTP `POST` à `http://localhost:9696/predict`, avec la course en JSON. |
| ② | Le serveur web | Reçoit la requête et appelle la fonction Python liée à l'adresse `/predict` : `predict_endpoint()`. |
| ③ | `predict.py` | Utilise le `DictVectorizer` (`dv`) et le modèle (`model`) **déjà en mémoire** : ils ont été lus dans `lin_reg.bin` une seule fois, au démarrage du serveur (une fois par processus, plus exactement : voir la remarque de la phase 2). |
| ④ | Le serveur web | Renvoie `{"duration": ...}` en JSON. `test.py` l'affiche. |

**L'idée à retenir pour tout le chapitre** : `test.py` ne change jamais. Seul ce qui se trouve **derrière le port 9696** change d'une phase à l'autre : Flask, puis gunicorn, puis gunicorn dans Docker.

Les phases, dans l'ordre de la vidéo :

| Phase | Ce qu'on teste | Transport |
|---|---|---|
| 0 | Préparer l'environnement Python (pipenv) | — |
| 1 | La logique de prédiction seule | Appel de fonction Python |
| 2 | Le service avec le serveur de développement Flask | HTTP |
| 3 | Le service avec gunicorn | HTTP |
| 4 | Le service dans un conteneur Docker | HTTP, à travers le port publié par Docker |

---

## 2. Phase 0 : préparer l'environnement (pipenv)

### Pourquoi un environnement dédié ?

`lin_reg.bin` est un fichier **pickle** : il ne contient pas le modèle « en soi », mais des instructions pour reconstruire des objets scikit-learn. Il doit être relu avec **la version de scikit-learn qui l'a écrit**. Pour la connaître sans rien charger :

```bash
cd /workspaces/mlops-zoomcamp/04-deployment/web-service
strings lin_reg.bin | grep -A2 _sklearn_version
# _sklearn_version
# 1.0.2
# sklearn.linear_model._base
```

Le service a donc besoin de scikit-learn **1.0.2**, alors que ton env conda `mlopszoomcamp` est en 1.9.0. D'où un environnement séparé, propre au dossier : un **virtualenv** (un dossier qui contient un Python et ses bibliothèques, isolé des autres), créé et géré par **pipenv**.

### Dans le terminal (vidéo)

```bash
cd 04-deployment/web-service
pip freeze | grep scikit-learn                          # la vidéo vérifie la version de son env : 1.0.2
pipenv install scikit-learn==1.0.2 flask --python=3.9
pipenv shell                                            # entrer dans l'environnement
```

Plus tard dans la vidéo, deux ajouts :

```bash
pipenv install gunicorn          # le serveur de production (phase 3)
pipenv install --dev requests    # pour test.py (phase 2) ; --dev = ne partira pas dans l'image Docker
```

### Ce que font les commandes

1. `pipenv install ...` crée un **virtualenv** rattaché au dossier, y installe les paquets, et écrit deux fichiers :
   - `Pipfile` : ce que tu demandes (`flask = "*"`, `scikit-learn = "==1.0.2"`) ;
   - `Pipfile.lock` : les versions exactes de **tout** ce qui a été installé, avec leurs empreintes. C'est lui que Docker utilisera.
2. `pipenv shell` ouvre un shell dans cet environnement : `python` désigne alors le Python du virtualenv.

> **▲ Ton fork**
> Le `Pipfile` et le `Pipfile.lock` existent déjà : **ne relance pas** `pipenv install scikit-learn==1.0.2 flask`, qui réécrirait le lock. Deux écarts avec la vidéo, déjà réglés dans ton dépôt :
> - **Python 3.10 au lieu de 3.9** : pip 26 refuse Python 3.9. 3.10 est la version la plus récente pour laquelle scikit-learn 1.0.2 publie des paquets précompilés.
> - **`numpy<2`** : scikit-learn 1.0.2 a été compilé pour numpy 1.x ; avec numpy 2 il plante au chargement.
>
> **À chaque nouveau terminal** (la commande `pipenv` elle-même est installée dans `mlopszoomcamp`) :
>
> ```bash
> conda activate mlopszoomcamp
> cd /workspaces/mlops-zoomcamp/04-deployment/web-service
> pipenv run python -c "import sys, sklearn; print(sys.version.split()[0], sklearn.__version__)"   # → 3.10.x 1.0.2
> ```
>
> **Seulement si le virtualenv n'existe pas encore** (Codespace neuf : `pipenv --venv` répond qu'il n'y en a pas) :
>
> ```bash
> conda env list | grep py310 || conda create -n py310 python=3.10 -y      # le « fournisseur » de Python 3.10 ; ne jamais le supprimer
> pipenv --python /home/codespace/miniconda3/envs/py310/bin/python          # crée le virtualenv avec ce Python
> pipenv sync --dev                                                         # installe exactement le Pipfile.lock, + requests
> ```
>
> `pipenv sync` installe le lock **sans jamais le recalculer**, contrairement à `pipenv install` ou `pipenv lock` (c'est un recalcul qui avait fait arriver numpy 2).
>
> Préfère **`pipenv run <commande>`** à `pipenv shell` : `pipenv shell` ouvre un shell enfant qui relit `~/.bashrc`, et conda peut y réactiver `(base)` devant ton virtualenv. `pipenv run` n'ouvre pas de shell, donc pas ce risque.
> **Signal d'alerte** : dans ce dossier, `python predict.py` tapé **sans** `pipenv run` utilise le Python de `mlopszoomcamp`, donc scikit-learn 1.9.0 face à un pickle 1.0.2.

---

## 3. Phase 1 : la prédiction seule, par un appel Python direct (vidéo seulement)

Dans la vidéo, avant d'écrire la partie Flask, `test.py` **importe** `predict.py` et appelle ses fonctions directement. Aucun serveur, aucun réseau. Cette version n'est plus dans le dossier final ; tu peux la recréer dans un fichier à part pour voir la logique seule :

```python
# test_direct.py (à créer si tu veux refaire cette étape)
import predict

ride = {"PULocationID": 10, "DOLocationID": 50, "trip_distance": 40}

features = predict.prepare_features(ride)
pred = predict.predict(features)
print(pred)
```

```
[test_direct.py] ── appel de fonction Python ──▶ [predict.py] ── return ──▶ [test_direct.py]
```

### Dans le terminal (un seul suffit : il n'y a pas de serveur)

```bash
python test_direct.py                   # vidéo, dans le pipenv shell
pipenv run python test_direct.py        # ▲ ton fork, après conda activate mlopszoomcamp + cd (§2)
# → 26.43883355119793
```

### Ce que font les scripts

1. `import predict` **exécute** `predict.py` de haut en bas : ouverture de `lin_reg.bin`, `pickle.load` → deux objets en mémoire, `dv` (le `DictVectorizer`) et `model` (la régression linéaire). L'objet Flask `app` est créé, mais le serveur **ne démarre pas** : la ligne `app.run(...)` est protégée par `if __name__ == "__main__":`, qui est faux lors d'un import.
2. `prepare_features(ride)` fabrique `{'PU_DO': '10_50', 'trip_distance': 40}`.
3. `predict(features)` : `dv.transform(features)` transforme le dictionnaire en vecteur, `model.predict(X)` renvoie un tableau, `float(preds[0])` en extrait un nombre Python.
4. Le résultat revient par un simple `return`, et `print` l'affiche.

---

## 4. Phase 2 : le service avec le serveur de développement Flask (sans Docker)

On ajoute une couche HTTP autour de la même logique. Il faut maintenant **deux terminaux** : un pour le serveur, qui tourne en continu, un pour le client.

```
 Terminal 2                                      Terminal 1
 ┌──────────────────┐ ① POST JSON          ┌───────────────────────────────┐
 │ python test.py   │─────────────────────▶│ python predict.py             │
 │                  │ localhost:9696       │ serveur de dev Flask          │
 │                  │                      │  ② predict_endpoint()         │
 │                  │ ③ réponse JSON       │     prepare_features, predict │
 │ print(...)       │◀─────────────────────│                               │
 └──────────────────┘                      └───────────────────────────────┘
```

| N° | Ce qui se passe |
|---|---|
| ① | `requests.post(url, json=ride)` convertit le dictionnaire en texte JSON et l'envoie au port 9696. |
| ② | Flask reconnaît l'adresse `/predict` et la méthode `POST` (décorateur `@app.route('/predict', methods=['POST'])`) et appelle `predict_endpoint()`. |
| ③ | `jsonify(result)` transforme le dictionnaire en réponse HTTP JSON (code 200) ; `response.json()` la retransforme en dictionnaire côté client. |

### Étape 1 — Terminal 1 : lancer le serveur

```bash
python predict.py                    # vidéo, dans le pipenv shell

# ▲ ton fork
conda activate mlopszoomcamp
cd /workspaces/mlops-zoomcamp/04-deployment/web-service
pipenv run python predict.py
```

Le terminal se bloque et affiche notamment :

```
 * Serving Flask app 'duration-prediction'
 * Debug mode: on
WARNING: This is a development server. Do not use it in a production deployment. Use a production WSGI server instead.
 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:9696
```

### Étape 2 — Terminal 2 : lancer le client

```bash
python test.py                       # vidéo (requests installé en dev-package)

# ▲ ton fork
conda activate mlopszoomcamp
cd /workspaces/mlops-zoomcamp/04-deployment/web-service
pipenv run python test.py
# → {'duration': 26.43883355119793}
```

### Ce que font les scripts

1. **Au lancement de `predict.py`** : chargement de `lin_reg.bin` (une fois), création de `app = Flask('duration-prediction')`. Cette fois le fichier est **lancé** et non importé : `__name__ == "__main__"` est vrai, donc `app.run(debug=True, host='0.0.0.0', port=9696)` démarre le serveur de développement.
2. **`test.py`** prépare la course `{"PULocationID": 10, "DOLocationID": 50, "trip_distance": 40}` et l'envoie à `http://localhost:9696/predict`.
3. **Flask** appelle `predict_endpoint()` : `request.get_json()` lit le JSON reçu → `prepare_features` → `predict` → `{'duration': pred}` → `jsonify`.
4. **`test.py`** reçoit la réponse et affiche `response.json()`. Puis il se termine ; le serveur, lui, continue d'attendre.

Pour arrêter le serveur : `Ctrl+C` dans le terminal 1.

> L'avertissement « development server » est la transition de la vidéo vers la phase 3 : ce serveur, fourni par Flask, est fait pour développer, pas pour encaisser du trafic. Il conseille un « production WSGI server » : WSGI est la norme Python qui définit comment un serveur HTTP et une application web Python se parlent ; gunicorn en est un.
>
> Détail visible dans les logs : avec `debug=True`, la ligne `Restarting with stat` signale que Flask relance `predict.py` dans un **second processus** (pour recharger le code à chaque modification). Le modèle est donc chargé deux fois, une par processus. Sans importance ici ; gunicorn n'a pas ce comportement.

---

## 5. Phase 3 : le service avec gunicorn (sans Docker)

Flask garde son rôle (router les requêtes, lire et écrire le JSON). Seul le **serveur HTTP** change : gunicorn remplace le serveur de développement. Le schéma de la phase 2 reste valable, avec gunicorn dans le terminal 1.

### Étape 1 — Terminal 1 : lancer gunicorn

```bash
pipenv install gunicorn                              # vidéo, une fois
gunicorn --bind=0.0.0.0:9696 predict:app             # vidéo, dans le pipenv shell

# ▲ ton fork (gunicorn est déjà dans le Pipfile), après conda activate mlopszoomcamp + cd
pipenv run gunicorn --bind=0.0.0.0:9696 predict:app
```

Sortie attendue (relevée lors de la vérification avec gunicorn 26.2.0, la version de ton lock ; dates et numéros changeront chez toi) :

```
[2026-10-01 10:19:46 +0200] [848] [INFO] Starting gunicorn 26.2.0
[2026-10-01 10:19:46 +0200] [848] [INFO] Listening at: http://0.0.0.0:9696 (848)
[2026-10-01 10:19:46 +0200] [848] [INFO] Using worker: sync
[2026-10-01 10:19:46 +0200] [850] [INFO] Booting worker with pid: 850
[2026-10-01 10:19:46 +0200] [848] [INFO] Control socket listening at /home/codespace/.gunicorn/gunicorn.ctl
```

Le nombre entre crochets est le numéro de processus : `848` est le processus principal de gunicorn, `850` le *worker* qui traite les requêtes.

### Étape 2 — Terminal 2 : le même client

```bash
pipenv run python test.py            # → {'duration': 26.43883355119793}
```

### Ce que fait gunicorn

1. `predict:app` se lit « dans le fichier `predict.py`, prends l'objet `app` ». gunicorn **importe** `predict.py` : le modèle est chargé, l'objet `app` est créé.
2. Comme c'est un import, `if __name__ == "__main__":` est faux : `app.run(...)` ne s'exécute pas. C'est gunicorn qui écoute sur le port.
3. `--bind=0.0.0.0:9696` : écouter sur toutes les interfaces réseau, port 9696. Indispensable à la phase 4 : avec `127.0.0.1`, gunicorn n'accepterait que les connexions venant de l'intérieur du conteneur.
4. À chaque requête, gunicorn appelle `app`, qui appelle `predict_endpoint()`. Le reste est identique à la phase 2.

> Un seul serveur à la fois sur un port. Si le serveur Flask de la phase 2 tourne encore, gunicorn affiche `[ERROR] Connection in use: ('0.0.0.0', 9696)` en boucle puis abandonne : arrête l'autre (`Ctrl+C`).

---

## 6. Phase 4 : le service dans un conteneur Docker

Le but : livrer le service avec **tout** ce dont il a besoin (Python, bibliothèques, code, modèle), pour qu'il tourne pareil sur n'importe quelle machine.

### Le `Dockerfile`, ligne par ligne

Le fichier du dossier (dans ton fork, la première ligne est `FROM python:3.10.21-slim`) :

```dockerfile
FROM python:3.9.7-slim

RUN pip install -U pip
RUN pip install pipenv

WORKDIR /app

COPY [ "Pipfile", "Pipfile.lock", "./" ]

RUN pipenv install --system --deploy

COPY [ "predict.py", "lin_reg.bin", "./" ]

EXPOSE 9696

ENTRYPOINT [ "gunicorn", "--bind=0.0.0.0:9696", "predict:app" ]
```

| Ligne | Rôle |
|---|---|
| `FROM` | L'image de base : un Linux minimal avec Python. Même version mineure que le `Pipfile`. |
| `RUN pip install ...` | Exécuté **pendant la construction** de l'image : mettre pip à jour, installer pipenv. |
| `WORKDIR /app` | Le dossier de travail **dans le conteneur** (créé s'il n'existe pas). Les `./` suivants désignent `/app`. |
| `COPY Pipfile Pipfile.lock` | Copier d'abord les seuls fichiers de dépendances. Tant qu'ils ne changent pas, Docker réutilise l'étape suivante depuis son cache. |
| `pipenv install --system --deploy` | `--system` : installer dans le Python de l'image, sans virtualenv (le conteneur isole déjà). `--deploy` : échouer si le lock ne correspond plus au `Pipfile`. Seuls les `[packages]` sont installés : `requests` (dev) n'entre pas dans l'image. |
| `COPY predict.py lin_reg.bin` | Copier le code et le modèle. Le modèle fait désormais **partie de l'image**. |
| `EXPOSE 9696` | Documentation seulement : n'ouvre aucun port. C'est le `-p` du `docker run` qui publie le port. |
| `ENTRYPOINT` | La commande lancée au démarrage de chaque conteneur : gunicorn, comme à la phase 3. |

> La page `02-flask-docker.md` du dépôt d'origine montre une version simplifiée de ce `Dockerfile` (un seul `COPY`, `CMD` au lieu d'`ENTRYPOINT`, image `ride-duration-model`). Ce cours suit le fichier du dossier, celui de la vidéo.

### Étape 1 — Terminal 1 : construire l'image, puis lancer le conteneur

```bash
cd /workspaces/mlops-zoomcamp/04-deployment/web-service    # le « . » ci-dessous = ce dossier
docker build -t ride-duration-prediction-service:v1 .
docker run -it --rm -p 9696:9696 ride-duration-prediction-service:v1
```

| Option | Rôle |
|---|---|
| `-t nom:tag` | Le nom de l'image (`v1` est le tag, une étiquette de version). |
| `.` | Le **contexte de build** : le dossier dont le contenu est envoyé à Docker pour les `COPY`. |
| `-it` | Mode interactif : tu vois les logs de gunicorn, `Ctrl+C` arrête le conteneur. |
| `--rm` | Supprimer le conteneur à l'arrêt (sinon il reste sur le disque). |
| `-p 9696:9696` | Publier le port : `port du Codespace : port du conteneur`. |

### Étape 2 — Terminal 2 : le même client, sans aucune modification

```bash
python test.py                       # vidéo

# ▲ ton fork : le client tourne toujours dans le Codespace, dans le virtualenv du dossier
conda activate mlopszoomcamp
cd /workspaces/mlops-zoomcamp/04-deployment/web-service
pipenv run python test.py
# → {'duration': 26.43883355119793}
```

### Ce qui se passe

```
 CODESPACE                                         CONTENEUR (image ride-duration-prediction-service:v1)
 ┌────────────────────────┐                        ┌───────────────────────────────────────────┐
 │ Terminal 2             │ ① POST localhost:9696  │                                           │
 │ pipenv run python      │───────────────────────▶│ ② port 9696 ─▶ gunicorn ─▶ predict:app     │
 │   test.py              │   (Docker relaie,      │                 │                         │
 │                        │    grâce à -p)         │                 ▼                         │
 │                        │                        │ ③ /app/predict.py + /app/lin_reg.bin      │
 │                        │ ④ réponse JSON         │    (copiés au build, figés dans l'image)  │
 │ print(...)             │◀───────────────────────│                                           │
 └────────────────────────┘                        └───────────────────────────────────────────┘
```

| N° | Ce qui se passe |
|---|---|
| ① | `test.py` tourne **dans le Codespace**, dans ton environnement pipenv : il envoie sa requête à `localhost:9696`, comme avant. |
| ② | Docker relaie ce port vers le port 9696 du conteneur, où gunicorn écoute sur `0.0.0.0`. |
| ③ | gunicorn a importé `/app/predict.py` au démarrage du conteneur ; le modèle est celui copié **au moment du build**. Modifier `predict.py` sur ton disque ne change rien au conteneur : il faut reconstruire l'image. |
| ④ | La réponse repart par le même chemin. |

Le client ne voit aucune différence avec la phase 3 : c'est tout l'intérêt de l'interface HTTP.

> **▲ Ton fork**
> `FROM python:3.10.21-slim` pour rester aligné sur le `python_version = "3.10"` du `Pipfile`. Les commandes `docker build` et `docker run` sont identiques à la vidéo.

---

## 7. Synthèse des configurations

| | Phase 1 : appel direct | Phase 2 : Flask dev | Phase 3 : gunicorn | Phase 4 : Docker |
|---|---|---|---|---|
| **Terminal 1 (serveur)** | `python test_direct.py` (pas de serveur : un seul terminal) | `python predict.py` | `gunicorn --bind=0.0.0.0:9696 predict:app` | `docker build ...` puis `docker run -it --rm -p 9696:9696 ...:v1` |
| **Terminal 2 (client)** | — | `python test.py` | `python test.py` | `python test.py` |
| **Dans ton fork** | `conda activate mlopszoomcamp`, `cd`, puis `pipenv run` devant chaque commande Python | idem | idem | idem, pour le client seulement |
| **Qui exécute `predict.py`** | Ton script, par `import` | Python, lancé directement (`__main__`) | gunicorn, par `import` | gunicorn, par `import`, dans le conteneur |
| **Environnement Python du service** | pipenv du dossier | pipenv du dossier | pipenv du dossier | Python de l'image (`pipenv install --system`) |
| **D'où vient `lin_reg.bin`** | Ton disque | Ton disque | Ton disque | Copie figée dans l'image |
| **Transport entrée / sortie** | Appel de fonction / `return` | HTTP POST / réponse JSON | HTTP POST / réponse JSON | HTTP POST / réponse JSON, via `-p` |
| **Ce que tu lis** | `26.43883355119793` | `{'duration': 26.43883355119793}` | idem | idem |

---

## 8. Le dossier, fichier par fichier

Pour vérifier que rien ne manque par rapport au `README.md` et au dossier :

| Fichier | Rôle | Phase |
|---|---|---|
| `lin_reg.bin` | Le pickle `(dv, model)` du module 1, écrit avec scikit-learn 1.0.2 | 1 à 4 |
| `predict.py` | Chargement du modèle + `prepare_features` + `predict` + application Flask `/predict` | 1 à 4 |
| `test.py` | Le client HTTP : envoie une course, affiche la réponse | 2 à 4 |
| `Pipfile` / `Pipfile.lock` | Les dépendances : `[packages]` (scikit-learn, flask, gunicorn ; + `numpy<2` dans ton fork) et `[dev-packages]` (requests) | 0, 4 |
| `Dockerfile` | La recette de l'image | 4 |
| `README.md` | Les 4 étapes de la vidéo + les commandes `docker build` / `docker run` | — |

| Étape du `README.md` | Section du cours |
|---|---|
| Creating a virtual environment with Pipenv | §2 |
| Creating a script for predicting | §3 |
| Putting the script into a Flask app | §4 et §5 |
| Packaging the app to Docker | §6 |

---

## 9. Si ça casse

| Symptôme | Cause probable | Correction |
|---|---|---|
| `test.py` : `ConnectionError ... [Errno 111] Connection refused` | Aucun serveur n'écoute sur 9696 | Lancer le terminal 1 d'abord |
| Flask : `Address already in use` / `Port 9696 is in use by another program` ; gunicorn : `[ERROR] Connection in use: ('0.0.0.0', 9696)` ; Docker : `Bind for 0.0.0.0:9696 failed: port is already allocated` | Un autre serveur occupe déjà 9696 | `Ctrl+C` dans son terminal, ou `lsof -i :9696` puis `kill <PID>` |
| `pipenv: command not found` | Terminal resté en `(base)` | `conda activate mlopszoomcamp` |
| `InconsistentVersionWarning`, ou erreur numpy au chargement de `lin_reg.bin` | `python predict.py` lancé **sans** `pipenv run` (scikit-learn 1.9.0 de `mlopszoomcamp`), ou numpy 2 | Passer par `pipenv run` ; vérifier `numpy<2` |
| Prompt `(web-service) (base)` après `pipenv shell` | conda réactivé dans le shell enfant | `exit`, puis utiliser `pipenv run` |
| `docker build` échoue à `pipenv install --deploy` | `Pipfile` modifié sans régénérer le lock | Ne pas éditer le `Pipfile` à la légère ; `pipenv lock` re-résout **tout** (c'est ainsi que numpy 2 est arrivé) |
| Le conteneur répond avec l'ancien code | L'image a été construite avant ta modification | Relancer `docker build` |

---

## 10. Reprise express (ton fork)

```bash
# Dans CHAQUE terminal
conda activate mlopszoomcamp
cd /workspaces/mlops-zoomcamp/04-deployment/web-service

# Sans Docker — Terminal 1 (au choix)
pipenv run python predict.py                          # serveur de dev Flask
pipenv run gunicorn --bind=0.0.0.0:9696 predict:app   # gunicorn

# Avec Docker — Terminal 1
docker build -t ride-duration-prediction-service:v1 .
docker run -it --rm -p 9696:9696 ride-duration-prediction-service:v1

# Terminal 2 — toujours le même
pipenv run python test.py
```

---

## 11. Ce qui a été vérifié pour ce cours

- Comparaison fichier par fichier de `web-service/` entre ton fork et l'original (01/10/2026).
- Exécuté avec Python 3.10, scikit-learn 1.0.2, numpy 1.26.4 (les versions de ton `Pipfile.lock`) : la version lue dans `lin_reg.bin` (`strings`), le `test_direct.py` de la phase 1, le serveur Flask de la phase 2, gunicorn 26.2.0 à la phase 3, `test.py` contre chacun (même résultat, `26.43883355119793`), et l'erreur `Connection refused` sans serveur.
- `Pipfile.lock` de ton fork cohérent avec son `Pipfile` (`pipenv verify`), donc `--deploy` ne bloquera pas sur ce point.
- Les messages « port déjà occupé » de Flask et de gunicorn (celui de Docker, au §9, est le message standard de Docker, non reproduit ici) ; `pipenv` présent dans l'env `mlopszoomcamp` (d'après `env-backups/mlopszoomcamp.yml`).
- Relecture par un agent indépendant, fichiers du dépôt à l'appui (exactitude, exhaustivité, lisibilité pour un débutant) ; ses corrections sont intégrées.
- **Non exécuté** : la construction et le lancement de l'image Docker (Docker Hub inaccessible depuis l'environnement de rédaction). Les commandes de la phase 4 sont celles de la vidéo et de ton dépôt.
- La phase 1 (`import predict` dans `test.py`) est reconstituée d'après la vidéo : elle ne laisse aucune trace dans les fichiers du dossier, et `test_direct.py` n'existe pas dans le dépôt. Si tu revois la vidéo et qu'elle diffère, c'est la vidéo qui fait foi.