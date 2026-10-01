# Etape 0. Entrainer mon model dans jupyternotebook

## Activer MLflow server et environnement de dev conda

cd /workspaces/mlops-zoomcamp/04-deployment/web-service-mlflow
conda activate mlopszoomcamp

mlflow server \
  --backend-store-uri sqlite:////workspaces/mlops-zoomcamp/04-deployment/web-service-mlflow/mlflow.db \
  --default-artifact-root /workspaces/mlops-zoomcamp/04-deployment/web-service-mlflow/artifacts \
  --host 127.0.0.1 \
  --port 5000

  Runner les différentes cellules de random_forest.ipynb
  - je constuirt un pipline
  - j'enregistre les paraètres dans un artifact
  - j'enregistre le model et le DictVect grâce au pipleine

## Une fois le model entrainer, le mettre dans un webservice avec fLASK

cf. le fichier predict.py
pour MODEL_URI : faut prendre l'ID du rune ou l'ID du model ?

ici il faut écrei dans le termine export MODEL_URI ='...' --> on met la  valeur de la variable "MODEL_URI" en mémoire dans le shell
dans predict.py, on prend la variable MODEL_URI


Question est-ce que à un moment donné il faut export la varial MODEL_URI dans le shell ?

A partir de la opn a créé un webservice. Ce webservice tourne sur le serveur de développement flask, serveur héberger sur la machine du codespace

à partir de là, on peut écrire
- python predict.py dans le terminla pour lancer le service
- dans un autre terminal, écrire python test.py pour tester le service

## Utiliser server de production gunicorn

installé gunicorn dans le conda env mlopszoomcamp

Activé le server gunicorn : gunicorn --bind=0.0.0.0:9696 predict:app. (le serveur est toujours hbergé sur la machine du codespace)

run python test.py

à partir de là, on peut tester le service à partir du server gunicorn
- run python test.py

### Exporter le service dans un container docker


## vérifier les version des livrauries python ayant permis d'netrainer le model


  (base) @Janua29 ➜ /workspaces/mlops-zoomcamp (main) $ conda activate mlopszoomcamp
cd /workspaces/mlops-zoomcamp/04-deployment/web-service-mlflow
python -c "import sys, sklearn, mlflow; print(sys.version.split()[0], sklearn.__version__, mlflow.__version__)"
3.11.16 1.9.0 3.16.0
(mlopszoomcamp) @Janua29 ➜ /workspaces/mlops-zoomcamp/04-deployment/web-service-mlflow (main) $ rm -f Pipfile Pipfile.lock
pipenv install --python=3.11.16 scikit-learn==1.9.0 mlflow==3.16.0 flask gunicorn

## crééer le pipenv environnement, depuis l'env de développement conda mlopszoomcamp

écrire le dockerfile
builder l'image docker
run le container docker. On met : -e MODEL_URI='models:/m-5e276730f7004842b7c3a36ea11b5044' \ pour exporter la valeur MODEL_URI dans la mémoire du shell, qui est réutiliser dans predict.py


____________________________________________________________________

Ton plan est bon dans les grandes lignes, mais il manque une étape — et c'est celle qui va te coûter du temps si tu ne l'anticipes pas. Je la mets en évidence au moment venu.

Les trois étapes que tu cites sont justes. J'en ajoute deux :

1. Relever les versions exactes de ton environnement
2. Créer le pipenv
3. **Adapter `predict.py`** ← l'étape manquante
4. Écrire le `Dockerfile`, puis build
5. Run avec gunicorn

---

## Étape 0 — Relever tes versions

Tu as bien identifié le problème : le `Pipfile` du cours date de 2022. Mais plutôt que de deviner, demande à ton environnement ce qu'il contient réellement.

```bash
conda activate mlopszoomcamp
cd /workspaces/mlops-zoomcamp/04-deployment/web-service-mlflow
python -c "import sys, sklearn, mlflow; print(sys.version.split()[0], sklearn.__version__, mlflow.__version__)"
```

Note les trois valeurs. Elles sont critiques : ton modèle a été sérialisé par **ces versions précises**. Si le conteneur en installe d'autres, tu retombes sur le problème de dépicklage du chapitre précédent — sauf que cette fois, c'est toi qui auras créé l'incompatibilité.

## Étape 1 — Le pipenv

Supprime les fichiers du cours et repars de zéro :

```bash
rm -f Pipfile Pipfile.lock
pipenv install --python=3.11 scikit-learn==X.Y.Z mlflow==A.B.C flask gunicorn
```

Remplace `X.Y.Z` et `A.B.C` par tes valeurs de l'étape 0. Adapte aussi `--python` si ta version diffère.

Deux remarques :

- **Pourquoi épingler scikit-learn et mlflow mais pas Flask ni gunicorn ?** Les deux premiers touchent à la sérialisation du modèle — une différence de version peut casser le chargement. Flask et gunicorn ne font que servir des requêtes HTTP ; leur version n'a aucun impact sur le modèle.
- Le `Pipfile.lock` généré fige aussi toutes les **dépendances transitives** (numpy, scipy, pandas…). C'est lui qui garantit la reproductibilité, pas le `Pipfile`.

## Étape 2 — Adapter `predict.py`

Voilà l'étape manquante, et voici pourquoi elle est nécessaire.

Ton fichier contient :

```python
mlflow.set_tracking_uri("http://127.0.0.1:5000")
```

Souviens-toi de la leçon du tunnel SSH : **`127.0.0.1` désigne toujours celui qui parle**. Un conteneur Docker possède sa propre pile réseau, donc son propre `127.0.0.1` — le sien, pas celui du Codespace. Depuis l'intérieur du conteneur, cette adresse pointe vers le conteneur lui-même, où rien n'écoute sur le port 5000.

Même famille de problème, troisième occurrence. Applique le principe qu'on a vu avec `MODEL_URI` : sors la configuration du code.

```python
MLFLOW_TRACKING_URI = os.getenv('MLFLOW_TRACKING_URI', 'http://127.0.0.1:5000')
mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)

MODEL_URI = os.getenv('MODEL_URI')
model = mlflow.pyfunc.load_model(MODEL_URI)
```

En local, le défaut s'applique et rien ne change. Dans le conteneur, tu injecteras une autre valeur. J'ai aussi retiré le défaut de `MODEL_URI` : en conteneur, mieux vaut un plantage immédiat qu'un modèle codé en dur servi silencieusement.

N'oublie pas `Cmd+S`.

## Étape 3 — Le Dockerfile

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

Les points à comprendre :

- **`python:3.11-slim`** doit correspondre à ta version Python. Sinon, incompatibilité de pickle.
- **Les `COPY` sont séparés volontairement.** Docker met en cache chaque instruction. Comme le `Pipfile` change rarement et `predict.py` souvent, cet ordre évite de réinstaller toutes les dépendances à chaque modification de ton code. Inverse les deux lignes et chaque build reprendra de zéro.
- **`--system`** installe dans le Python du conteneur plutôt que dans un virtualenv. Un conteneur est déjà isolé ; ajouter un venv dedans serait une isolation dans l'isolation.
- **`--deploy`** échoue si le `Pipfile.lock` ne correspond pas au `Pipfile`. C'est un garde-fou : il t'interdit de construire une image avec des dépendances incohérentes.
- **`EXPOSE`** est purement documentaire. Il n'ouvre rien — c'est le `-p` au `run` qui compte.
- **`0.0.0.0`** dans le bind : gunicorn doit accepter les connexions venant de l'extérieur du conteneur.

Ajoute aussi un `.dockerignore` :

```
__pycache__/
*.ipynb
.ipynb_checkpoints/
mlflow.db
artifacts/
mlruns/
```

Sans lui, tout le contexte est transféré au démon Docker — y compris ta base et tes artifacts. Lenteur inutile, et invalidation du cache à chaque run MLflow.

## Étape 4 — Build

```bash
docker build -t ride-duration-prediction-service:v2 .
```

Le `.` final est le **contexte de build** : le dossier envoyé au démon. Il est obligatoire.

## Étape 5 — Run

Et maintenant, le problème qu'il faut résoudre.

### Deux obstacles, pas un

**Obstacle 1 — joindre le serveur MLflow.** Réglé par l'adaptation de `predict.py`, plus un drapeau Docker qui donne au conteneur une route vers sa machine hôte.

**Obstacle 2 — lire les artifacts.** Celui-là est moins évident. Tu as lancé MLflow avec :

```
--default-artifact-root /workspaces/mlops-zoomcamp/04-deployment/web-service-mlflow/artifacts
```

Le serveur de tracking ne te transmet pas les fichiers du modèle : il te répond **où ils se trouvent**, c'est-à-dire ce chemin local. Ton client va ensuite le lire lui-même sur son propre disque. Or ce chemin n'existe pas dans le conteneur, dont le système de fichiers est complètement séparé.

Il faut donc y rendre ce dossier visible, **au même chemin**.

### La commande

```bash
docker run -it --rm \
  -p 9696:9696 \
  --add-host=host.docker.internal:host-gateway \
  -e MLFLOW_TRACKING_URI='http://host.docker.internal:5000' \
  -e MODEL_URI='models:/m-5e276730f7004842b7c3a36ea11b5044' \
  -v /workspaces/mlops-zoomcamp/04-deployment/web-service-mlflow/artifacts:/workspaces/mlops-zoomcamp/04-deployment/web-service-mlflow/artifacts:ro \
  ride-duration-prediction-service:v2
```

Décortiquons :

| Drapeau | Rôle |
|---|---|
| `-p 9696:9696` | port 9696 du Codespace → port 9696 du conteneur |
| `--add-host=...:host-gateway` | crée le nom `host.docker.internal` pointant vers le Codespace |
| `-e MLFLOW_TRACKING_URI=...` | dit au conteneur où joindre MLflow |
| `-e MODEL_URI=...` | quel modèle servir |
| `-v chemin:chemin:ro` | monte le dossier d'artifacts, en lecture seule |
| `--rm` | supprime le conteneur à l'arrêt |

Le `-v` avec le **même chemin des deux côtés** est l'astuce : le conteneur recevra du serveur un chemin absolu, et ce chemin sera valide chez lui aussi.

### Une alternative plus courte

Sur Linux — donc dans ton Codespace — il existe un raccourci :

```bash
docker run -it --rm --network=host \
  -e MODEL_URI='models:/m-5e276730f7004842b7c3a36ea11b5044' \
  -v /workspaces/mlops-zoomcamp/04-deployment/web-service-mlflow/artifacts:/workspaces/mlops-zoomcamp/04-deployment/web-service-mlflow/artifacts:ro \
  ride-duration-prediction-service:v2
```

`--network=host` supprime l'isolation réseau : le conteneur partage directement la pile réseau de la machine. Du coup `127.0.0.1:5000` fonctionne tel quel, et le `-p` devient inutile.

C'est plus simple, mais je te conseille de faire la première version d'abord. Le mapping de ports est un concept Docker fondamental que tu retrouveras partout, alors que `--network=host` ne marche que sous Linux et masque ce qui se passe.

## Étape 6 — Tester

Depuis un troisième terminal, sans aucune modification :

```bash
conda activate mlopszoomcamp
python test.py
```

`test.py` interroge `localhost:9696` depuis le Codespace. Le mapping `-p` l'envoie dans le conteneur. Du point de vue du client, rien n'a changé — c'est exactement ce qu'on cherche.

---

## Si ça coince

| Symptôme | Piste |
|---|---|
| `Connection refused` au démarrage | MLflow éteint, ou `MLFLOW_TRACKING_URI` mal formé |
| `FileNotFoundError` sur un chemin `/workspaces/...` | le `-v` manque ou le chemin diffère |
| Erreur de dépicklage | versions du `Pipfile` ≠ versions d'entraînement |
| `--deploy` échoue au build | `Pipfile` et `Pipfile.lock` désynchronisés → `pipenv lock` |

Un rappel de méthode : tu introduis **beaucoup** de nouveautés d'un coup ici. Si ça casse, ne modifie qu'une chose à la fois. Et pour inspecter l'intérieur du conteneur :

```bash
docker run -it --rm --entrypoint=bash ride-duration-prediction-service:v2
```

Tu obtiens un shell dedans, sans lancer gunicorn. Utile pour vérifier ce qui a été installé et ce qui est visible.

---

Ce que cette étape t'apprend au-delà de la technique : ton service est maintenant **portable** (il embarque ses dépendances) mais **pas autonome** (il dépend de MLflow et d'un dossier monté). C'est précisément le couplage dont on parlait, rendu visible par Docker. Le `s3://` de l'instructeur supprime les deux contraintes d'un coup — plus de serveur à joindre, plus de volume à monter. Tu vois maintenant concrètement pourquoi il a fait ce choix.


Bonne nouvelle, et correction de ma part : MLflow **tourne bien**. Je l'avais supposé éteint à cause du prompt `(base)` — j'ai extrapolé au lieu de vérifier. Le `curl` tranche.

## Alors pourquoi le conteneur est-il refusé ?

C'est la seconde moitié de mon message précédent qui est la bonne : ton serveur écoute sur `--host 127.0.0.1`.

- Ton `curl` part du Codespace lui-même → arrive par la boucle locale → **accepté**
- Le conteneur part du réseau Docker → arrive par une autre interface → **refusé**

MLflow ne dit pas « je n'existe pas », il dit « je n'accepte pas les connexions venant de là ».

Il faut donc le relancer. D'abord l'arrêter — soit `Ctrl+C` dans son terminal, soit, si tu ne le retrouves pas :

```bash
lsof -i :5000
kill <PID>
```

Puis :

```bash
conda activate mlopszoomcamp
mlflow server \
  --backend-store-uri sqlite:////workspaces/mlops-zoomcamp/04-deployment/web-service-mlflow/mlflow.db \
  --default-artifact-root /workspaces/mlops-zoomcamp/04-deployment/web-service-mlflow/artifacts \
  --host 0.0.0.0 \
  --port 5000
```

---

## Le récapitulatif conda

### Le principe

Un environnement conda ne sert qu'à une chose : **fournir un interpréteur Python et ses bibliothèques**. Donc la question à se poser est toujours la même :

> Cette commande a-t-elle besoin de bibliothèques Python installées dans `mlopszoomcamp` ?

Si oui → active l'environnement. Si non → peu importe.

### Le tableau

| Commande | Environnement | Pourquoi |
|---|---|---|
| `mlflow server ...` | **`mlopszoomcamp`** | `mlflow` n'est installé que là |
| `python predict.py` (hors Docker) | **`mlopszoomcamp`** | a besoin de mlflow, sklearn, flask |
| `gunicorn ... predict:app` (hors Docker) | **`mlopszoomcamp`** | idem |
| `python test.py` | **`mlopszoomcamp`** | a besoin de `requests` |
| Jupyter / le notebook | **`mlopszoomcamp`** | (et vérifie aussi le kernel) |
| `docker build` | peu importe | Docker est un binaire système |
| `docker run` | peu importe | idem |
| `curl`, `lsof`, `kill` | peu importe | outils système |
| `pipenv install` | **`mlopszoomcamp`** | pour que `--python=3.11` trouve le bon interpréteur |

### Pourquoi Docker s'en moque

C'est le point conceptuel. Quand tu lances `docker run`, tu ne fais **pas** tourner du Python sur le Codespace. Tu demandes au démon Docker de démarrer un conteneur, lequel contient son propre Python et ses propres bibliothèques, installés depuis le `Pipfile.lock` pendant le build.

Ton environnement conda est totalement invisible depuis l'intérieur du conteneur. C'est précisément ce qu'on cherche : **l'image est autonome**. Si Docker dépendait de ton conda, tu n'aurais rien gagné en portabilité.

### En pratique

Le plus simple : active `mlopszoomcamp` par réflexe dans tout nouveau terminal. Ça ne gêne jamais, y compris pour Docker, et ça t'évite l'erreur inverse — qui est la plus fréquente.

Et garde le réflexe de lire ton prompt : `(base)` ou `(mlopszoomcamp)` en début de ligne te dit immédiatement où tu es.