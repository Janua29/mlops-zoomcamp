# Module 4 — Partie 1 : web-service - déployer un modèle en web service

## 1. D'où on part, et le problème à résoudre

À la fin du module 2, tu avais un modèle entraîné, tracké dans MLflow, et… c'est tout. Il vit dans un notebook, sur ta machine. Pour l'utiliser, il faut ouvrir Jupyter, charger le fichier, écrire du Python.

Ce n'est pas utilisable par une application. Le problème du module 4 est donc :

> **Comment transformer un modèle entraîné en un service que n'importe quel programme peut appeler, depuis n'importe quelle machine, de façon fiable et reproductible ?**

Le point d'arrivée de cette partie 1 : une **image Docker** que tu peux envoyer à un collègue, déployer sur un serveur ou dans le cloud, et qui répondra exactement de la même manière partout. Ton modèle devient une brique logicielle autonome.

### Les trois modes de déploiement

Avant de plonger, le cadre général du module. Il existe trois façons de servir un modèle :

| Mode | Fonctionnement | Cas d'usage typique |
|---|---|---|
| **Batch** (offline) | Un job tourne à intervalle régulier sur un gros volume de données, écrit les résultats quelque part | Scorer tous les clients chaque nuit pour détecter le churn |
| **Web service** (online) | Une requête arrive → une réponse immédiate | L'appli affiche la durée estimée du trajet au moment de la réservation |
| **Streaming** (online) | Un flux continu d'événements est consommé au fil de l'eau | Détection de fraude sur chaque transaction en temps réel |

**Cette partie 1 couvre le web service.** Le batch et le streaming viennent ensuite.

Le critère de choix est simple : *quand ai-je besoin de la prédiction ?* Si la réponse est « tout de suite, en réaction à une action utilisateur », c'est du web service. Si c'est « demain matin, pour tout le monde d'un coup », c'est du batch.

---

## 2. Le point de départ : le modèle sérialisé

L'instructeur a sauvegardé, à la fin du module 1, un fichier **`lin_reg.bin`** via `pickle` :

```python
with open('lin_reg.bin', 'wb') as f_out:
    pickle.dump((dv, model), f_out)
```

### Le point conceptuel à retenir

Ce fichier ne contient **pas seulement le modèle**. Il contient un *tuple* de deux objets :

- **`dv`** — le `DictVectorizer` entraîné, qui sait transformer un dictionnaire Python en vecteur numérique
- **`model`** — la `LinearRegression` entraînée

**Le préprocessing fait partie intégrante du modèle déployé.** Un modèle seul est inutilisable : il ne saurait pas convertir `{"PU_DO": "10_50", "trip_distance": 40}` en nombres, et surtout il ne saurait pas dans quel **ordre** placer les colonnes. Le `DictVectorizer` mémorise ce mapping au moment du `fit`.

C'est une source d'erreur classique en production : le training-serving skew. Si le préprocessing à l'inférence diffère ne serait-ce que d'un détail de celui de l'entraînement, le modèle produit des prédictions fausses **sans lever la moindre erreur**. Embarquer le `dv` entraîné plutôt que de réécrire la transformation à la main élimine ce risque.

### La conséquence sur les versions

`pickle` ne sauvegarde pas le code des objets, seulement leur *état* et la référence à leur classe. Au chargement, Python recrée les objets à partir des classes présentes dans l'environnement courant.

Donc : **l'environnement qui déserialise doit avoir la même version de scikit-learn que celui qui a sérialisé.** Sinon, dans l'ordre de gravité : un `InconsistentVersionWarning`, un plantage, ou — le pire — des prédictions silencieusement fausses parce qu'un attribut interne a changé de signification entre deux versions.

Cette contrainte explique toute l'étape suivante.

---

## 3. Étape 1 — L'environnement reproductible avec pipenv

### Ce qu'on fait

```bash
pipenv install scikit-learn==1.0.2 flask --python=3.9
```

Pipenv crée deux fichiers dans le dossier :

- **`Pipfile`** — ce que **tu as demandé** (lisible, court, écrit par toi)
- **`Pipfile.lock`** — ce qui a **réellement été installé** : l'arbre complet des dépendances, versions exactes + hashs cryptographiques (généré automatiquement, jamais édité à la main)

### Pourquoi pipenv plutôt que pip ou conda ?

**Face à `pip` seul.** `pip install` installe dans l'environnement Python courant, sans isolation. Et un `requirements.txt` écrit à la main ne verrouille que ce que tu y as écrit : si tu notes `scikit-learn==1.0.2`, tu ne contrôles pas la version de `numpy` ou `scipy` que pip choisira. Or ces dépendances transitives peuvent casser le dépicklage. Le `Pipfile.lock` fige **tout l'arbre**.

**Face à `conda`.** Conda est excellent en phase exploratoire — il gère aussi les binaires non-Python (CUDA, MKL, compilateurs). Mais il est lourd : une image Docker avec conda pèse facilement 2–3 Go contre ~150 Mo avec `python:3.9-slim` + pipenv. En production, on veut la plus petite surface possible : moins de disque, démarrage plus rapide, moins de failles de sécurité potentielles.

**Le vrai argument, au fond** : `Pipfile` + `Pipfile.lock` sont deux petits fichiers texte qu'on versionne dans git et qu'on copie dans l'image Docker. C'est le **contrat de reproductibilité** du service — la garantie que ta machine, celle de ton collègue et le serveur de production exécutent rigoureusement le même code.

> *Note 2026* : beaucoup d'équipes utilisent aujourd'hui `uv` ou `poetry` plutôt que pipenv (nettement plus rapides). Le principe est identique : un fichier de déclaration + un fichier de verrouillage. Ce que tu apprends ici est transposable.

### Les dépendances de développement

```bash
pipenv install --dev requests
```

Le flag `--dev` signifie « nécessaire pour développer et tester, mais à **ne pas embarquer** en production ». Le service ne fait que *recevoir* des requêtes ; il n'a pas besoin de la bibliothèque `requests` pour en *envoyer*. Seul le script de test en a besoin.

---

## 4. Étape 2 — Le web service avec Flask (`predict.py`)

### Le rôle de Flask

Flask est une bibliothèque qui **expose des fonctions Python derrière des URLs**. Tu ne « places » pas ton script dans un web service : Flask *transforme* ton script en web service.

### La structure du fichier

```python
import pickle
from flask import Flask, request, jsonify

# 1. Chargement du modèle — UNE SEULE FOIS, au démarrage
with open('lin_reg.bin', 'rb') as f_in:
    (dv, model) = pickle.load(f_in)

# 2. Les fonctions métier
def prepare_features(ride):
    features = {}
    features['PU_DO'] = '%s_%s' % (ride['PULocationID'], ride['DOLocationID'])
    features['trip_distance'] = ride['trip_distance']
    return features

def predict(features):
    X = dv.transform(features)       # dictionnaire → vecteur numérique
    preds = model.predict(X)
    return float(preds[0])

# 3. L'application Flask
app = Flask('duration-prediction')

@app.route('/predict', methods=['POST'])
def predict_endpoint():
    ride = request.get_json()        # data brute reçue du client
    features = prepare_features(ride)
    pred = predict(features)
    result = {'duration': pred}
    return jsonify(result)           # dict Python → réponse JSON

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=9696)
```

### Ligne par ligne, les points importants

**Le chargement hors des fonctions.** Le `pickle.load` est au niveau module, donc exécuté **une fois au démarrage**. Si tu le mettais dans `predict_endpoint()`, tu relirais le fichier à chaque requête — catastrophique en performance. Le modèle reste en mémoire vive et sert toutes les requêtes.

**`@app.route('/predict', methods=['POST'])`.** C'est un *décorateur* : il enregistre la fonction dans la table de routage de Flask. Traduction : « quand une requête HTTP de type POST arrive sur le chemin `/predict`, exécute cette fonction ». D'où l'URL complète côté client : `http://localhost:9696/predict`.

**Pourquoi POST et pas GET ?** GET transmet ses paramètres dans l'URL (`?distance=40`), ce qui est visible, limité en taille, et mis en cache. POST transmet dans le *corps* de la requête, ce qui permet d'envoyer une structure JSON complète. Convention générale : GET pour lire une ressource, POST pour soumettre des données à traiter.

**`request.get_json()`.** Flask parse automatiquement le corps JSON de la requête en dictionnaire Python. **`jsonify()`** fait l'inverse en sortie : dict Python → JSON + en-tête `Content-Type: application/json`.

**`host='0.0.0.0'`.** Point crucial, détaillé plus bas.

**`if __name__ == "__main__":`.** Cette garde signifie « n'exécute ceci que si le fichier est lancé directement ». Elle est ce qui permet au *même fichier* de servir en développement et en production (voir étape 4).

---

## 5. Étape 3 — Le client de test (`test.py`)

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

**Statut de ce fichier : ce n'est pas une partie du déploiement.** C'est un client de test, qui simule ce que ferait l'application appelante — le backend de l'appli de taxi, par exemple. Il ne sera jamais dans l'image Docker.

### Serveur et client : deux programmes, deux terminaux

C'est le point d'architecture le plus important à intégrer.

| | `predict.py` | `test.py` |
|---|---|---|
| **Rôle** | Serveur — il **attend** | Client — il **demande** |
| **Durée de vie** | Tourne en permanence | S'exécute en 1 seconde et se termine |
| **Effet sur le terminal** | Le bloque (jusqu'au `Ctrl+C`) | Le rend immédiatement |

```
Terminal 1 : pipenv run python predict.py
             └─► processus vivant, occupe le port 9696, bloque le terminal

Terminal 2 : pipenv run python test.py
             └─► envoie une requête au 9696, affiche la réponse, se termine
```

Lancer `test.py` sans serveur actif donne une `ConnectionRefusedError`. C'est le premier réflexe de debug : *le serveur tourne-t-il vraiment ?*

### Sur la question des terminaux

Un terminal **n'appartient à rien**. Ce n'est pas « le terminal de gunicorn » ou « le terminal de Docker ». C'est juste une fenêtre où tu tapes des commandes depuis un répertoire donné. Si l'instructeur réutilise le terminal 1 pour une nouvelle commande, c'est simplement qu'il a fait `Ctrl+C` et que le terminal est redevenu disponible.

La seule règle : **une commande qui bloque (un serveur) monopolise son terminal**. Il en faut donc un second pour faire autre chose pendant ce temps.

---

## 6. Étape 4 — Passer en production avec gunicorn

### Ce n'est pas « Flask ou gunicorn », c'est « Flask et gunicorn »

Il faut séparer deux rôles que Flask assume tous les deux, ce qui crée la confusion :

| Rôle | Qui le remplit | Devenir |
|---|---|---|
| **Le framework** — routage, parsing JSON, `jsonify` | Flask | **Conservé** |
| **Le serveur HTTP** — connexions réseau, concurrence, workers | Werkzeug (serveur de dev intégré à Flask) → **gunicorn** | **Remplacé** |

Le serveur de développement de Flask est mono-processus, traite une requête à la fois, et n'est pas durci contre les attaques. D'où l'avertissement rouge que tu as vu : *« This is a development server. Do not use it in a production deployment. »*

**Gunicorn** est un vrai serveur WSGI : il lance N processus *workers*, chacun avec une copie de ton application Flask en mémoire, et répartit les requêtes entrantes entre eux.

> *WSGI* = Web Server Gateway Interface. C'est la norme Python qui définit comment un serveur HTTP et une application Python se parlent. Flask respecte cette norme, gunicorn aussi — c'est pourquoi ils sont interchangeables avec n'importe quel autre couple (Django + uWSGI, par exemple).

### La commande

```bash
pipenv run gunicorn --bind=0.0.0.0:9696 predict:app
```

**`predict:app`** se lit : « dans le module `predict.py`, prends l'objet nommé `app` ». Gunicorn **importe** ton fichier et récupère l'application Flask.

C'est ici que la garde `if __name__ == "__main__":` prend tout son sens :

- `python predict.py` → le fichier est le programme principal, `__name__` vaut `"__main__"`, `app.run()` s'exécute → serveur de dev.
- `gunicorn predict:app` → gunicorn importe le fichier comme module, `__name__` vaut `"predict"`, `app.run()` **ne s'exécute pas** → gunicorn gère le réseau lui-même.

**Le même fichier sert dans les deux cas, sans modifier une seule ligne.** Tu gardes le serveur de dev pour itérer vite (avec `debug=True` qui recharge automatiquement à chaque sauvegarde), gunicorn prend le relais en production.

### Rien n'est « par défaut » ni persistant

Installer gunicorn ne change rien automatiquement. Il n'y a **aucune configuration mémorisée** quelque part disant « ce projet tourne avec gunicorn ». Il n'y a qu'un **processus vivant** dans un terminal, issu de la commande que tu as tapée. Ferme le terminal, relance `python predict.py` demain : tu es de retour sur le serveur de dev.

Et les deux ne peuvent pas cohabiter : **un port n'accepte qu'un seul processus**. Lancer `python predict.py` pendant que gunicorn écoute sur 9696 donne `OSError: [Errno 98] Address already in use`.

### La démonstration du cours

`test.py` renvoie **exactement le même résultat** que le serveur soit Flask-dev ou gunicorn. Le client ne voit aucune différence : il envoie du HTTP à un port, il reçoit du JSON.

C'est la propriété fondamentale d'un web service : **le contrat, c'est l'URL et le format des messages**. L'implémentation derrière peut changer librement — changer de serveur, de langage, de machine, de modèle — sans que le client ait à le savoir.

### `0.0.0.0` n'est pas `localhost`

Erreur de débutant très classique, et qui va devenir critique à l'étape Docker.

| Adresse | Signification |
|---|---|
| `127.0.0.1` (= `localhost`) | « N'écoute que l'interface loopback » → seules les connexions **venant de la machine elle-même** sont acceptées |
| `0.0.0.0` | « Écoute sur **toutes** les interfaces réseau » → les connexions venant de l'extérieur sont acceptées aussi |

`0.0.0.0` n'est pas une adresse de destination : c'est un joker **côté serveur** signifiant « n'importe laquelle de mes adresses ». On ne s'y connecte jamais, on écoute dessus.

Un conteneur Docker est, du point de vue réseau, une machine distincte. Un service qui écoute sur `127.0.0.1` à l'intérieur d'un conteneur n'accepte que les connexions **internes au conteneur** — depuis ta machine, tu ne pourras jamais l'atteindre, même avec le bon mapping de port.

### Les workers

Par défaut, gunicorn lance **un seul worker**. Pour exploiter la concurrence :

```bash
gunicorn --bind=0.0.0.0:9696 --workers=4 predict:app
```

Règle empirique : `(2 × nombre de cœurs) + 1`. Ton Codespace ayant 2 cœurs, tu resteras autour de 4–5. Attention : chaque worker charge sa propre copie du modèle en mémoire — avec un modèle lourd, la RAM devient le facteur limitant avant le CPU.

---

## 7. Étape 5 — Docker : empaqueter le tout

### Pourquoi Docker ?

Tu as maintenant un service qui fonctionne… **sur ta machine**. Mais il dépend de : Python 3.9, scikit-learn 1.0.2, pipenv installé, gunicorn, le fichier `lin_reg.bin` au bon endroit, la bonne commande de lancement. Le fameux *« ça marche chez moi »*.

Docker résout ça en empaquetant **tout l'environnement d'exécution** — OS minimal, Python, dépendances, code, modèle, commande de démarrage — dans une **image** unique et immuable.

### Image vs conteneur

Une confusion fréquente, alors autant la lever tout de suite :

| | Image | Conteneur |
|---|---|---|
| Nature | Fichier figé, en lecture seule | Processus en cours d'exécution |
| Analogie | La recette + les ingrédients sous vide | Le plat en train d'être cuisiné |
| Analogie 2 | Une classe Python | Une instance de cette classe |
| Commande | `docker build` la crée | `docker run` en démarre un |

Une image peut donner naissance à autant de conteneurs qu'on veut, tous identiques au démarrage.

### Le Dockerfile, ligne par ligne

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

---

**`FROM python:3.9.7-slim`**

Le point de départ : une image de base déjà construite, récupérée depuis Docker Hub. Tu ne pars jamais de zéro — tu hérites d'une image existante et tu ajoutes tes couches par-dessus.

- `python` = le nom de l'image officielle
- `3.9.7-slim` = le tag (voir plus bas). `slim` = variante allégée, sans les outils de compilation ni la documentation. ~120 Mo contre ~900 Mo pour l'image complète.
- Le choix de **3.9.7** n'est pas arbitraire : c'est la version qui a servi à entraîner et sérialiser le modèle.

---

**`RUN pip install -U pip`** et **`RUN pip install pipenv`**

`RUN` exécute une commande **au moment de la construction** de l'image, et le résultat est figé dedans. On met à jour pip, puis on installe pipenv — dont on aura besoin pour lire le `Pipfile.lock`.

---

**`WORKDIR /app`**

Définit le répertoire de travail à l'intérieur du conteneur. Deux effets : le dossier `/app` est créé s'il n'existe pas, et toutes les instructions suivantes (`COPY`, `RUN`, `ENTRYPOINT`) s'exécutent depuis là. C'est l'équivalent d'un `cd` persistant.

---

**`COPY [ "Pipfile", "Pipfile.lock", "./" ]`**

Copie des fichiers **depuis ta machine vers l'image**. Le `./` de destination désigne le `WORKDIR`, donc `/app/`.

**Pourquoi copier seulement ces deux fichiers d'abord, et pas tout d'un coup ?** À cause du **cache par couches**.

Chaque instruction du Dockerfile crée une *couche* (layer). Lors d'une reconstruction, Docker réutilise les couches dont les entrées n'ont pas changé, et ne recalcule qu'à partir de la première qui a changé.

Or, l'installation des dépendances prend plusieurs minutes, alors que ton `predict.py` change vingt fois par jour. En copiant les dépendances **avant** le code :

- Tu modifies `predict.py` → seules les couches après `COPY predict.py` sont recalculées → **rebuild en 2 secondes**.
- Tu modifies le `Pipfile` → tout est recalculé à partir de là, mais c'est rare.

Si tu avais tout copié en une fois, le moindre changement de code relancerait l'installation complète. C'est une optimisation qu'on retrouve dans tous les Dockerfiles bien écrits : **du plus stable au plus volatil**.

---

**`RUN pipenv install --system --deploy`**

Installe les dépendances listées dans le `Pipfile.lock`. Les deux flags sont importants :

- **`--system`** : installe dans le Python **système du conteneur**, sans créer d'environnement virtuel. Pourquoi ? *Parce que le conteneur EST déjà l'isolation.* Créer un venv dans un conteneur, c'est mettre une boîte dans une boîte : complexité inutile, et il faudrait ensuite activer ce venv dans l'`ENTRYPOINT`.
- **`--deploy`** : fait **échouer le build** si le `Pipfile.lock` n'est pas cohérent avec le `Pipfile`. C'est un garde-fou : il interdit de construire une image à partir d'un lock périmé. Sans lui, tu pourrais déployer silencieusement des versions différentes de celles que tu as testées.

Note aussi que les dépendances `--dev` (donc `requests`) ne sont **pas** installées. L'image de production ne contient que le strict nécessaire.

---

**`COPY [ "predict.py", "lin_reg.bin", "./" ]`**

Le code et le modèle. Ici, le modèle est **embarqué dans l'image** — ce qui est simple mais a un défaut : changer de modèle impose de reconstruire et redéployer l'image. La leçon 4.3 corrigera ça en récupérant le modèle depuis le model registry MLflow au démarrage.

---

**`EXPOSE 9696`**

⚠️ Instruction **purement documentaire**. Elle n'ouvre aucun port et ne publie rien. Elle déclare simplement « ce conteneur écoute sur le 9696 », information lisible via `docker inspect` et exploitée par certains outils d'orchestration.

C'est le `-p` de `docker run` qui fait le vrai travail. Beaucoup de débutants croient qu'`EXPOSE` suffit — ce n'est pas le cas.

---

**`ENTRYPOINT [ "gunicorn", "--bind=0.0.0.0:9696", "predict:app" ]`**

La commande exécutée **au démarrage de chaque conteneur**. C'est ici que ton choix de gunicorn devient enfin un vrai « par défaut » : il n'est plus une convention orale ou une commande à retenir, c'est **du code versionné dans git**. N'importe qui faisant `docker run` sur cette image démarre gunicorn, sans le savoir ni avoir à y penser.

Et c'est ici que `0.0.0.0` devient indispensable. Avec `127.0.0.1`, le service serait injoignable depuis l'extérieur du conteneur, quel que soit ton mapping de ports.

> *Forme JSON* : `["gunicorn", "--bind=...", ...]` s'appelle la forme *exec*. Elle lance directement le binaire, sans passer par un shell. Avantage : gunicorn devient le processus PID 1 du conteneur et reçoit correctement les signaux d'arrêt (`SIGTERM`), ce qui permet un arrêt propre. La forme shell (`ENTRYPOINT gunicorn --bind=...`) intercale un `/bin/sh` qui avale les signaux. **Toujours préférer la forme JSON.**

---

### La commande de build

```bash
docker build -t ride-duration-prediction-service:v1 .
```

| Élément | Rôle |
|---|---|
| `docker build` | Lit un Dockerfile et construit une image |
| `-t` | *tag* — donne un nom à l'image (`--tag` en version longue) |
| `ride-duration-prediction-service` | Le nom de l'image |
| `:v1` | Le tag de version |
| **`.`** | **Le build context** — à ne surtout pas oublier |

**Le `.` final** désigne le *build context* : le dossier envoyé au démon Docker pour la construction. Docker y cherche le `Dockerfile`, et c'est la racine de tous les `COPY`. Un `COPY predict.py ./` cherche `predict.py` **relativement au build context**, pas relativement à ton shell.

C'est la seule contrainte sur l'endroit d'où tu lances la commande : il faut que le contexte soit le bon dossier (ici `04-deployment/web-service/`). Peu importe le terminal.

> Astuce : ajoute un fichier `.dockerignore` (même syntaxe que `.gitignore`) pour exclure `__pycache__`, `.git`, les notebooks, les datasets. Sans lui, Docker envoie tout le dossier au démon — sur un dossier contenant des Parquet de plusieurs centaines de Mo, le build devient très lent.

### Qu'est-ce qu'un tag ?

Un tag, c'est **l'étiquette de version collée sur une image**. La syntaxe est toujours `nom:tag`. Tu l'as déjà vu sans y prêter attention : `python:3.9.7-slim`, `postgres:13`, `apache/airflow:2.9.0`.

**Pourquoi c'est central en MLOps ?** Parce que le tag rend le déploiement *réversible* :

1. Tu construis `ride-duration:v1`, tu déploies, tout va bien.
2. Tu réentraînes, tu construis `ride-duration:v2`, tu déploies.
3. Les prédictions deviennent bizarres en production.
4. Tu redéployes `v1` en une commande. **Rollback immédiat**, aucune reconstruction, aucune recherche dans git.

Les deux images coexistent. Sans tag, tu n'aurais aucun moyen de désigner « la version d'avant ».

**Le piège du tag `latest`.** Si tu omets le tag, Docker met automatiquement `:latest`. C'est une mauvaise habitude : `latest` est une étiquette *mouvante*, que tu peux recoller sur une autre image à tout moment. Deux machines faisant `docker pull mon-image:latest` à une semaine d'écart peuvent obtenir deux images différentes. Adieu la reproductibilité. **Toujours taguer explicitement.**

**Détail technique utile** : un tag n'est qu'un *pointeur*. La vraie identité d'une image est son digest SHA256. On peut donc coller plusieurs tags sur la même image :

```bash
docker tag ride-duration-prediction-service:v1 ride-duration-prediction-service:2026-09-18
```

En entreprise, on tague souvent avec le hash du commit git (`:a3f8c12`), ce qui relie l'image déployée à l'état exact du code qui l'a produite. Exactement la même logique que le `run_id` MLflow.

---

### La commande de lancement

```bash
docker run -it --rm -p 9696:9696 ride-duration-prediction-service:v1
```

**`docker run`** — crée un **conteneur** à partir de l'image et le démarre.

---

**`-it`** — en réalité deux flags fusionnés :

- **`-i`** (`--interactive`) : garde l'entrée standard (STDIN) ouverte
- **`-t`** (`--tty`) : alloue un pseudo-terminal

Concrètement, ce que ça t'apporte : tu **vois les logs de gunicorn s'afficher en direct** dans ton terminal, correctement formatés (avec les couleurs, sans buffering bizarre), et **`Ctrl+C` fonctionne** pour arrêter le conteneur.

Sans `-it`, le conteneur tourne quand même, mais l'expérience est dégradée — et surtout, `Ctrl+C` ne le tuerait pas proprement. En production réelle, on utilise plutôt `-d` (*detached*) pour le lancer en arrière-plan, mais en développement `-it` est parfait : c'est le mode « je veux voir ce qui se passe ».

---

**`--rm`** — supprime automatiquement le conteneur quand il s'arrête.

Par défaut, un conteneur arrêté **reste sur ton disque**, visible via `docker ps -a`. Sans `--rm`, tester dix fois ton service laisse dix conteneurs morts qui s'accumulent et consomment de l'espace. Sur un Codespace avec un disque limité, c'est loin d'être anodin.

Le réflexe : **`--rm` pour tout conteneur jetable de test**. On l'omet quand on veut inspecter les logs *après* l'arrêt (`docker logs <id>`), ou pour un service de longue durée.

---

**`-p 9696:9696`** — la publication de port. Syntaxe :

```
-p  PORT_HÔTE : PORT_CONTENEUR
        ↓            ↓
-p     9696    :    9696
```

**L'ordre compte** : à gauche ta machine, à droite le conteneur.

Un conteneur a son propre espace réseau isolé. Gunicorn écoute sur le port 9696 **du conteneur**, qui est invisible depuis l'extérieur. `-p` crée un tunnel : « tout ce qui arrive sur le port 9696 de l'hôte, redirige-le vers le port 9696 du conteneur ».

Les deux nombres sont **indépendants**. Tu peux écrire `-p 8080:9696` : le conteneur continue d'écouter sur 9696 (il n'en sait rien), mais tu l'appellerais depuis `http://localhost:8080/predict`. C'est utile quand le port 9696 est déjà pris sur ta machine, ou pour lancer plusieurs conteneurs du même service :

```bash
docker run -p 9696:9696 ride-duration:v1   # instance 1
docker run -p 9697:9696 ride-duration:v1   # instance 2, même image
```

**Le lien avec `0.0.0.0`** : pour que le tunnel fonctionne, il faut que gunicorn écoute sur **toutes** les interfaces du conteneur. S'il écoutait sur `127.0.0.1`, il ne verrait que le trafic interne, et le mapping de port ne servirait à rien. C'est la panne classique : `-p` correctement configuré, et pourtant `Connection refused`.

---

**`ride-duration-prediction-service:v1`** — l'image à partir de laquelle créer le conteneur. Le tag garantit que tu lances bien la version voulue.

---

### Le test final

Une fois le conteneur lancé (terminal 1), dans un autre terminal :

```bash
pipenv run python test.py
```

**Et c'est exactement le même `test.py`, avec la même URL `http://localhost:9696/predict`, qui renvoie le même résultat.** Le client ne sait pas — et n'a pas à savoir — qu'il parle maintenant à un conteneur Docker plutôt qu'à un processus Python local.

C'est l'aboutissement de la partie 1 : **l'interface est restée stable pendant que tout l'intérieur a changé.**

> Note Codespaces : quand tu lances un conteneur avec `-p`, VS Code détecte automatiquement le port et l'ajoute à l'onglet **PORTS**. C'est de là que tu récupères l'URL forwardée si tu veux tester depuis le navigateur de ton PC — exactement comme pour MLflow sur le 5000.

---

## 8. Les quatre couches d'isolation

Le fil conducteur de toute cette partie, vu d'en haut. À chaque étape, on a fermé une porte d'entrée aux problèmes :

| Couche | Ce qu'elle garantit | Ce qu'elle ne garantit pas |
|---|---|---|
| **Le pickle `(dv, model)`** | Le préprocessing voyage avec le modèle | Rien sur les versions de bibliothèques |
| **Pipenv + `Pipfile.lock`** | Les versions exactes des paquets Python | Rien sur la version de Python, l'OS, les libs système |
| **Docker** | L'environnement complet : OS, Python, paquets, code, modèle | Rien sur *où* ça tourne |
| **Le tag d'image** | Quelle version précise est déployée, et le retour arrière | — |

Chaque couche répond à une question de la forme « *et si l'environnement d'exécution n'était pas celui que je crois ?* ». C'est, en une phrase, ce que signifie « productioniser » un modèle.

---

## 9. Récapitulatif des commandes

```bash
# --- Setup (une seule fois) ---
cd 04-deployment/web-service
pipenv install scikit-learn==1.0.2 flask --python=3.9
pipenv install --dev requests
pipenv install gunicorn

# --- Développement : Terminal 1 ---
pipenv run python predict.py
# → serveur de dev Flask, rechargement auto, avertissement rouge

# --- Production locale : Terminal 1 ---
pipenv run gunicorn --bind=0.0.0.0:9696 predict:app
# → serveur WSGI, logs [INFO] Booting worker

# --- Docker : Terminal 1 ---
docker build -t ride-duration-prediction-service:v1 .
docker run -it --rm -p 9696:9696 ride-duration-prediction-service:v1

# --- Test : Terminal 2, identique dans les 3 cas ---
pipenv run python test.py
```

**Commandes Docker utiles pour le debug :**

```bash
docker images                    # lister les images construites
docker ps                        # conteneurs en cours
docker ps -a                     # + les conteneurs arrêtés
docker logs <container_id>       # voir les logs d'un conteneur
docker exec -it <id> bash        # ouvrir un shell DANS un conteneur qui tourne
docker system prune              # nettoyer images/conteneurs orphelins
```

`docker exec -it <id> bash` est ton meilleur outil de diagnostic : tu entres dans le conteneur et tu vérifies que `lin_reg.bin` est bien là, que les paquets sont installés, etc.

---

## 10. Ce qui vient ensuite

1. **Récupérer le modèle depuis le model registry MLflow** au lieu de l'embarquer dans l'image. Le service téléchargera le modèle au démarrage depuis S3/le registry → changer de version de modèle sans reconstruire l'image. C'est la jonction entre le module 2 et le module 4.
2. **Batch scoring** — transformer un notebook en script paramétré qui lit un mois de données, prédit en masse, et écrit les résultats.
3. **Streaming avec AWS Kinesis + Lambda** (optionnel, nécessite un compte AWS).

Le fil rouge du module reste : **un seul modèle, trois enveloppes différentes** selon le besoin métier.