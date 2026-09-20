# 04 — Python / ML : le notebook `random-forest.ipynb`

> **Dossier concerné** : `04-deployment/web-service-mlflow/`
> **Fichier commenté** : `random-forest.ipynb`
> **Comparaison** : `01-intro/duration-prediction.ipynb` — le notebook qui a produit le `lin_reg.bin` utilisé dans `04-deployment/web-service/`
> **Portée** : uniquement le code Python et le machine learning. Tout ce qui concerne Flask, gunicorn, pipenv et Docker est dans `04-IT-web-service-mlflow.md`.

---

## Sommaire

1. [Où on en est, et ce que ce notebook change](#1-o%C3%B9-on-en-est-et-ce-que-ce-notebook-change)
2. [Le point de départ : `duration-prediction.ipynb` (module 1)](#2-le-point-de-d%C3%A9part--duration-predictionipynb-module-1)
3. [Vue d'ensemble du notebook](#3-vue-densemble-du-notebook)
4. [Les cellules de préparation (0 à 4)](#4-les-cellules-de-pr%C3%A9paration-0-%C3%A0-4)
5. [`make_pipeline` — le cœur du chapitre](#5-make_pipeline--le-cœur-du-chapitre)
6. [Le bloc MLflow, ligne par ligne (cellule 5)](#6-le-bloc-mlflow-ligne-par-ligne-cellule-5)
7. [Les quatre familles de `log_*` : `log_params`, `log_metric`, `log_artifact`, `log_model`](#7-les-quatre-familles-de-log_--log_params-log_metric-log_artifact-log_model)
8. [MLflow 2.x vs 3.x : ce qui a cassé et pourquoi](#8-mlflow-2x-vs-3x--ce-qui-a-cass%C3%A9-et-pourquoi)
9. [Les cellules d'inspection (6 à 13)](#9-les-cellules-dinspection-6-%C3%A0-13)
10. [Tableau des différences avec `duration-prediction.ipynb`](#10-tableau-des-diff%C3%A9rences-avec-duration-predictionipynb)
11. [Ce que le notebook livre à `predict.py`](#11-ce-que-le-notebook-livre-%C3%A0-predictpy)
12. [Les pièges rencontrés, et ce qu'ils enseignent](#12-les-pi%C3%A8ges-rencontr%C3%A9s-et-ce-quils-enseignent)
13. [Mémo : les commandes et les vérifications](#13-m%C3%A9mo--les-commandes-et-les-v%C3%A9rifications)

---

## 1. Où on en est, et ce que ce notebook change

Depuis le début du module 4, on cherche à répondre à une question :

> Comment transformer un modèle entraîné en un service que n'importe quel programme peut appeler ?

La partie précédente (`web-service/`) y a répondu d'une façon simple : **poser un fichier `.bin` à côté du code**. Ça marche, mais ça laisse trois questions sans réponse :

- D'où vient ce fichier ?
- Avec quelles données a-t-il été entraîné ?
- Quelle version tourne actuellement en production ?

Ce notebook-ci répond à ces trois questions en remplaçant le fichier par **une référence vers le registre MLflow**. Le service ne transporte plus le modèle : il va le chercher, par son identifiant.

Mais avant même cette histoire de registre, le notebook introduit un changement plus discret et plus profond : **le `Pipeline` scikit-learn**. C'est lui qui fait que le modèle devient un objet unique, autonome, transportable. Sans lui, le registre MLflow ne servirait pas à grand-chose — il faudrait quand même trimballer le `DictVectorizer` à part.

Deux idées, donc, et c'est l'ordre logique :

| Idée | Ce qu'elle résout |
|---|---|
| **`Pipeline`** | le modèle devient **un seul objet** contenant son préprocessing |
| **Registre MLflow** | ce seul objet devient **adressable** par un identifiant stable |

---

## 2. Le point de départ : `duration-prediction.ipynb` (module 1)

C'est le notebook qui a produit `lin_reg.bin`, le fichier utilisé dans `04-deployment/web-service/`. Il faut l'avoir en tête, parce que **tout ce que `random-forest.ipynb` fait différemment, il le fait en réaction à lui.**

### Les cellules qui comptent

```python
# Cellule 12 — le préprocessing
categorical = ['PU_DO']
numerical = ['trip_distance']

dv = DictVectorizer()                                 # ← objet 1

train_dicts = df_train[categorical + numerical].to_dict(orient='records')
X_train = dv.fit_transform(train_dicts)               # apprend + transforme

val_dicts = df_val[categorical + numerical].to_dict(orient='records')
X_val = dv.transform(val_dicts)                       # transforme seulement
```

```python
# Cellule 14 — l'entraînement
lr = LinearRegression()                               # ← objet 2
lr.fit(X_train, y_train)

y_pred = lr.predict(X_val)
root_mean_squared_error(y_val, y_pred)
```

```python
# Cellule 15 — la sauvegarde
with open('models/lin_reg.bin', 'wb') as f_out:
    pickle.dump((dv, lr), f_out)                      # ← un tuple de deux objets
```

### Ce qu'il faut retenir de cette dernière ligne

`pickle.dump((dv, lr), f_out)` ne sauvegarde **pas** un modèle. Il sauvegarde un **tuple** de deux objets indépendants :

- `dv` — le `DictVectorizer` entraîné. Il connaît le vocabulaire : quelles clés existent, quelles valeurs catégorielles ont été vues, et surtout **dans quel ordre** les colonnes du vecteur numérique sont rangées.
- `lr` — la `LinearRegression` entraînée, c'est-à-dire un tableau de coefficients.

Le préprocessing **fait partie du modèle déployé**. Un modèle seul est inutilisable : il ne saurait pas convertir `{"PU_DO": "10_50", "trip_distance": 40}` en nombres, ni dans quel ordre les placer.

C'est pourquoi `web-service/predict.py` doit faire deux choses :

```python
with open('lin_reg.bin', 'rb') as f_in:
    (dv, model) = pickle.load(f_in)      # dépaqueter le tuple

def predict(features):
    X = dv.transform(features)           # étape 1 : vectoriser
    preds = model.predict(X)             # étape 2 : prédire
    return float(preds[0])
```

### Les trois problèmes de cette approche

1. **Deux objets à gérer** — deux chargements, deux occasions de se tromper.
2. **Aucune garantie de cohérence** — rien, au niveau du code, ne garantit que le `dv` chargé est bien celui qui a servi à entraîner *ce* modèle-là. Si tu réentraînes le modèle et oublies de réexporter le `dv`, tout continue de fonctionner… en produisant des prédictions fausses.
3. **La logique de transformation est dupliquée** — elle existe dans le notebook (`dv.fit_transform`) *et* dans `predict.py` (`dv.transform`). Si tu modifies l'une sans l'autre, tu obtiens ce qu'on appelle un **training-serving skew** : le modèle prédit n'importe quoi, sans lever la moindre erreur.

> Le point 3 est le pire type de bug qui existe : **silencieux**. Un plantage se voit. Une prédiction fausse, non.

C'est très exactement ce que le `Pipeline` élimine.

---

## 3. Vue d'ensemble du notebook

Voici la carte du fichier `random-forest.ipynb` tel qu'il est dans ton repo, avec le statut de chaque cellule.

| Cellule | Contenu | Statut |
|---|---|---|
| 0 | imports (`pickle`, `pandas`, `DictVectorizer`, `RandomForestRegressor`, métriques) | utile |
| 1 | `from sklearn.pipeline import make_pipeline` | **la nouveauté** |
| 2 | `mlflow.set_tracking_uri(...)` + `set_experiment(...)` | utile — connexion au serveur |
| 3 | `read_dataframe()` et `prepare_dictionaries()` | utile — inchangé depuis le module 1 |
| 4 | chargement train/val, `y_train`, `y_val`, `dict_train`, `dict_val` | utile |
| **5** | **le bloc `with mlflow.start_run()` : pipeline + fit + log** | **le cœur** |
| 6 | `print(model_info.model_uri)` | pratique — c'est la valeur à copier dans le terminal |
| 7–8 | `MlflowClient(...)`, `RUN_ID = '...'` | optionnel — exploration |
| 9 | `client.download_artifacts(...)` | **mort** (commenté) — API retirée en MLflow 3 |
| 10 | `mlflow.artifacts.list_artifacts(...)` | inspection — voir ce que contient le modèle |
| 11–12 | `pickle.load` du DictVectorizer | **mort** (commenté) — plus de DV séparé |
| 13 | recharger le pipeline et afficher `named_steps` | pédagogique — voir le DV *dans* le pipeline |

Deux remarques sur cette carte.

**Les cellules 9, 11 et 12 sont commentées, pas supprimées.** C'est un bon réflexe pour apprendre : le code mort raconte l'ancienne méthode. Mais c'est un mauvais réflexe pour un fichier qu'on garde : dans six mois, tu ne sauras plus si ces lignes sont « à réactiver » ou « à oublier ». Si tu veux garder la trace, mets-la dans une cellule markdown qui dit explicitement *pourquoi* c'est mort.

**Le notebook s'arrête à l'entraînement.** Il ne sert pas le modèle. Il produit un identifiant (`models:/m-...`) que tu transmets ensuite au service. C'est la frontière entre ce document et le second.

---

## 4. Les cellules de préparation (0 à 4)

### Cellule 2 — la connexion à MLflow

```python
import mlflow

mlflow.set_tracking_uri("http://127.0.0.1:5000")
mlflow.set_experiment("green-taxi-duration")
```

**`set_tracking_uri`** dit à la bibliothèque MLflow *à qui parler*. Ici, un serveur qui tourne sur la même machine (le Codespace), sur le port 5000.

Point de vocabulaire important, parce qu'il revient constamment : `127.0.0.1` — aussi appelé `localhost` — désigne **toujours la machine qui parle**. Depuis le notebook, il désigne le Codespace. Depuis l'intérieur d'un conteneur Docker, il désignerait le conteneur. C'est la source de la moitié des erreurs réseau des débutants, et tu la recroiseras au chapitre Docker.

**`set_experiment`** regroupe les runs sous un nom. Si l'expérience n'existe pas, MLflow la crée. C'est un classeur : tous tes essais de prédiction de durée green-taxi finissent au même endroit, comparables entre eux dans l'UI.

> **Ordre imposé** : ces deux lignes doivent s'exécuter **avant** le premier `start_run()`. Sinon MLflow écrit dans un dossier `mlruns/` local, et tu ne trouveras jamais ton run dans l'interface.

### Cellule 3 — les deux fonctions

```python
def read_dataframe(filename: str):
    df = pd.read_parquet(filename)

    df['duration'] = df.lpep_dropoff_datetime - df.lpep_pickup_datetime
    df.duration = df.duration.dt.total_seconds() / 60
    df = df[(df.duration >= 1) & (df.duration <= 60)]

    categorical = ['PULocationID', 'DOLocationID']
    df[categorical] = df[categorical].astype(str)
    return df
```

Rien de nouveau ici par rapport au module 1, mais deux détails valent qu'on s'y arrête.

**`.astype(str)` sur les identifiants de zone.** Les `PULocationID` sont des nombres (10, 50, 264…) mais ce ne sont pas des *quantités* : la zone 50 n'est pas « cinq fois » la zone 10. Les laisser en numérique ferait croire au modèle à un ordre et à des distances qui n'existent pas. En les passant en texte, on force leur traitement comme **catégories**.

**Le filtre `1 <= duration <= 60`.** On jette les trajets aberrants — durées nulles, négatives, ou de plusieurs heures. C'est un choix de modélisation, pas un nettoyage neutre : ton modèle ne saura pas prédire un trajet de 90 minutes, parce qu'il n'en a jamais vu.

```python
def prepare_dictionaries(df: pd.DataFrame):
    df['PU_DO'] = df['PULocationID'] + '_' + df['DOLocationID']
    categorical = ['PU_DO']
    numerical = ['trip_distance']
    dicts = df[categorical + numerical].to_dict(orient='records')
    return dicts
```

**`PU_DO`** est une *feature d'interaction* : au lieu de traiter « départ zone 10 » et « arrivée zone 50 » comme deux informations indépendantes, on crée une seule catégorie `"10_50"` qui représente le trajet complet. L'intuition : le trajet 10→50 a une durée caractéristique qui n'est pas la simple addition de deux effets.

Le `+` fonctionne parce que les deux colonnes sont maintenant des chaînes — c'est une concaténation, pas une addition. D'où l'importance du `.astype(str)` juste avant.

**`to_dict(orient='records')`** transforme le DataFrame en **liste de dictionnaires** :

```python
[
  {'PU_DO': '10_50', 'trip_distance': 1.01},
  {'PU_DO': '43_151', 'trip_distance': 2.4},
  ...
]
```

C'est précisément le format qu'attend le `DictVectorizer`. Et c'est aussi, ce n'est pas un hasard, le format naturel du JSON qu'un client enverra au service. Cette correspondance est ce qui rendra `predict.py` si court.

### Cellule 4 — le chargement

```python
df_train = read_dataframe('data/green_tripdata_2021-01.parquet')
df_val   = read_dataframe('data/green_tripdata_2021-02.parquet')

target = 'duration'
y_train = df_train[target].values
y_val   = df_val[target].values

dict_train = prepare_dictionaries(df_train)
dict_val   = prepare_dictionaries(df_val)
```

**Janvier pour entraîner, février pour valider.** Ce n'est pas un `train_test_split` aléatoire : c'est une séparation **temporelle**. C'est le bon choix ici, parce qu'en production le modèle prédira toujours le futur à partir du passé. Un split aléatoire mélangerait les deux et te donnerait un score trop optimiste.

**`.values`** convertit la Series pandas en tableau NumPy. Scikit-learn accepte les deux, mais le tableau évite de traîner l'index pandas.

---

## 5. `make_pipeline` — le cœur du chapitre

### Ce qu'est un `Pipeline`

Un `Pipeline` scikit-learn est un objet qui **enchaîne plusieurs étapes de traitement et les présente comme un seul estimateur**. Il expose la même interface qu'un modèle ordinaire — `.fit()`, `.predict()` — mais en interne il fait circuler les données à travers chaque étape.

```python
from sklearn.pipeline import make_pipeline

pipeline = make_pipeline(
    DictVectorizer(),
    RandomForestRegressor(**params, n_jobs=-1)
)
```

Regarde bien : les deux objets sont passés **non entraînés**. On ne fait pas `dv.fit_transform()` avant. On décrit une *chaîne de montage*, on ne la fait pas encore tourner.

### `make_pipeline` vs `Pipeline` : deux écritures

Il existe deux façons de construire la même chose.

```python
# Version courte — les noms sont générés
from sklearn.pipeline import make_pipeline

pipeline = make_pipeline(
    DictVectorizer(),
    RandomForestRegressor(**params)
)
```

```python
# Version explicite — tu nommes toi-même
from sklearn.pipeline import Pipeline

pipeline = Pipeline([
    ('vectorizer', DictVectorizer()),
    ('regressor',  RandomForestRegressor(**params))
])
```

`make_pipeline` est un raccourci (*factory function*) : il nomme automatiquement chaque étape d'après le **nom de la classe en minuscules**. D'où `dictvectorizer` et `randomforestregressor`.

```python
print(pipeline.named_steps)
# {'dictvectorizer': DictVectorizer(),
#  'randomforestregressor': RandomForestRegressor(...)}
```

Ces noms ne sont pas cosmétiques. Ils servent à deux choses :

- **accéder à une étape** : `pipeline.named_steps['dictvectorizer']` (c'est ce que fait ta cellule 13)
- **régler les hyperparamètres depuis l'extérieur**, avec la syntaxe double-underscore :
  ```python
  GridSearchCV(pipeline, {'randomforestregressor__max_depth': [10, 20, 30]})
  ```

En pratique : `make_pipeline` pour un prototype, `Pipeline` avec des noms explicites dès que tu fais de la recherche d'hyperparamètres ou que tu veux du code lisible dans six mois.

### Ce qui se passe au `fit`

C'est le point le plus important de tout ce document.

```python
pipeline.fit(dict_train, y_train)
```

En interne :

```
dict_train ──► DictVectorizer.fit_transform() ──► X_train ──► RandomForestRegressor.fit(X_train, y_train)
                     ↑
             apprend le vocabulaire
             ET transforme
```

Le `DictVectorizer` reçoit un **`fit_transform`** : il apprend quelles clés existent, quelles valeurs catégorielles apparaissent, quel index de colonne correspond à quoi — *et* il transforme les données dans la foulée.

La règle générale du `Pipeline` : **toutes les étapes sauf la dernière reçoivent `fit_transform`, la dernière reçoit `fit`.**

### Ce qui se passe au `predict`

```python
y_pred = pipeline.predict(dict_val)
```

```
dict_val ──► DictVectorizer.transform() ──► X_val ──► RandomForestRegressor.predict(X_val)
                    ↑
            RÉUTILISE le vocabulaire appris,
            n'apprend rien
```

Ici, le `DictVectorizer` reçoit un **`transform` seul**.

### Pourquoi cette distinction est décisive

C'est exactement la distinction `fit_transform` / `transform` que tu appliquais à la main au module 1 :

```python
X_train = dv.fit_transform(train_dicts)   # ← fit_transform
X_val   = dv.transform(val_dicts)         # ← transform
```

Sauf qu'à la main, **rien ne t'empêche de te tromper**. Écris `dv.fit_transform(val_dicts)` par inadvertance, et le vectorizer réapprend son vocabulaire sur les données de validation. Ton score de validation devient faussement bon, parce que le préprocessing a « vu » les données de test. C'est ce qu'on appelle une **fuite de données** (*data leakage*).

Le `Pipeline` rend cette erreur **structurellement impossible**. Ce n'est pas qu'il te prévient : c'est que le chemin pour la commettre n'existe plus.

> C'est une idée qui dépasse largement ce chapitre. En ingénierie, la bonne réponse à « on peut se tromper ici » n'est jamais « il faut faire attention » — c'est « rendons l'erreur impossible ».

### Et le bénéfice décisif pour le déploiement

Quand tu sérialises le pipeline, **tout part ensemble**. Le `DictVectorizer` entraîné, avec son vocabulaire, voyage à l'intérieur de l'objet.

Conséquence dans `predict.py` :

```python
# Avant (web-service) — deux objets, deux étapes
X = dv.transform(features)
preds = model.predict(X)

# Après (web-service-mlflow) — un objet, une étape
preds = model.predict(features)
```

La vectorisation est *dedans*. Il n'y a plus de logique de transformation dupliquée entre le notebook et le service. Le training-serving skew n'est plus possible, parce qu'il n'y a plus qu'un seul endroit où la transformation est définie.

### Une limite à connaître : les catégories inconnues

Le `DictVectorizer` a un comportement qu'il faut avoir en tête pour la production. À l'entraînement, il a vu un certain nombre de valeurs de `PU_DO` — mettons 8 000 trajets distincts. Si une requête arrive avec `PU_DO = "17_203"` qu'il n'a jamais vu, il ne lève **aucune erreur** : il ignore simplement la clé inconnue, et la ligne correspondante est vectorisée avec des zéros partout sur la partie catégorielle.

Le modèle prédit quand même. Il prédit mal, mais il prédit, et rien ne te le signale.

Vérifie combien de colonnes ton vectorizer a apprises (c'est ce que fait ta cellule 13) :

```python
dv = pipeline.named_steps['dictvectorizer']
print(len(dv.feature_names_))
```

C'est le genre de chose qu'on surveille en production — ce sera le sujet du module 5 (monitoring).

### Les hyperparamètres du `RandomForestRegressor`

```python
params = dict(max_depth=20, n_estimators=100, min_samples_leaf=10, random_state=0)
RandomForestRegressor(**params, n_jobs=-1)
```

| Paramètre | Ce qu'il contrôle |
|---|---|
| `n_estimators=100` | le nombre d'arbres dans la forêt. Plus il y en a, plus la prédiction est stable, plus c'est lent. |
| `max_depth=20` | la profondeur maximale de chaque arbre. Limiter la profondeur limite le surapprentissage. |
| `min_samples_leaf=10` | une feuille doit contenir au moins 10 observations. Même rôle : empêcher l'arbre de mémoriser des cas isolés. |
| `random_state=0` | fige le générateur aléatoire. Deux exécutions donnent le même modèle. **Indispensable pour la reproductibilité.** |
| `n_jobs=-1` | utilise tous les cœurs CPU disponibles. Les arbres d'une forêt sont indépendants : ils se calculent en parallèle. |

Deux notes :

**`n_jobs` n'est pas dans `params`.** C'est délibéré, et c'est une distinction propre : `n_jobs` ne change pas le modèle produit, seulement la vitesse à laquelle il est produit. Ce n'est pas un hyperparamètre, c'est un paramètre d'exécution. Il n'a donc rien à faire dans ce qu'on logge comme configuration du modèle.

**Sur ton Codespace à 2 cœurs**, le gain de `n_jobs=-1` est réel mais modeste.

### `**params` — le dépaquetage de dictionnaire

```python
RandomForestRegressor(**params, n_jobs=-1)

# est strictement équivalent à :
RandomForestRegressor(max_depth=20, n_estimators=100,
                      min_samples_leaf=10, random_state=0, n_jobs=-1)
```

Le `**` devant un dictionnaire le **déplie en arguments nommés** : chaque clé devient un nom de paramètre, chaque valeur son contenu.

Pourquoi c'est utile ici : tu écris les hyperparamètres **une seule fois**, dans `params`, et tu t'en sers **deux fois** — pour configurer le modèle *et* pour les enregistrer dans MLflow (`mlflow.log_params(params)`).

Si tu les écrivais deux fois, tu pourrais en modifier un et oublier l'autre. MLflow enregistrerait alors des paramètres qui ne correspondent pas au modèle réel, et ton expérience deviendrait irreproductible sans qu'aucune erreur ne le signale. Encore le même principe : rendre l'incohérence impossible plutôt que de compter sur l'attention.

> Le cousin de `**` est `*`, qui déplie une liste en arguments positionnels : `f(*[1, 2])` ≡ `f(1, 2)`. Tu les croiseras aussi dans les *signatures* de fonctions (`def f(*args, **kwargs)`), où ils font l'inverse : ils **collectent** au lieu de déplier.

---

## 6. Le bloc MLflow, ligne par ligne (cellule 5)

```python
with mlflow.start_run() as run:
    params = dict(max_depth=20, n_estimators=100, min_samples_leaf=10, random_state=0)
    mlflow.log_params(params)

    pipeline = make_pipeline(
        DictVectorizer(),
        RandomForestRegressor(**params, n_jobs=-1)
    )

    pipeline.fit(dict_train, y_train)
    y_pred = pipeline.predict(dict_val)

    rmse = root_mean_squared_error(y_val, y_pred)
    print(params, rmse)
    mlflow.log_metric('rmse', rmse)

    model_info = mlflow.sklearn.log_model(pipeline, name="model")
    print(model_info.model_uri)

RUN_ID = run.info.run_id
print("run_id   :", RUN_ID)
print("model_uri:", model_info.model_uri)
```

### `with mlflow.start_run() as run:`

Deux mécanismes Python en une ligne.

**Le `with`** ouvre un *gestionnaire de contexte* (*context manager*). Sa promesse : une action de fermeture aura lieu à la sortie du bloc, **même si une erreur survient au milieu**. Ici, cette action est « marquer le run comme terminé côté serveur ».

Sans le `with`, une exception pendant `pipeline.fit()` laisserait un run éternellement en statut `RUNNING` dans l'UI MLflow. Et — plus pénible — le run suivant échouerait avec un message du genre « un run est déjà actif ».

C'est le même mécanisme que tu utilises depuis le module 1 sans y penser :

```python
with open('lin_reg.bin', 'wb') as f_out:
    pickle.dump((dv, lr), f_out)
# ← le fichier est fermé ici, même si pickle.dump a planté
```

**Le `as run`** capture l'objet produit par le contexte dans une variable. Sans lui, le run existe et fonctionne parfaitement, mais tu n'as **aucun moyen de le désigner** ensuite. C'est exactement l'erreur que tu as eue : `run.info.run_id` échouait parce que `run` n'existait pas.

**L'indentation définit la portée.** Tout ce qui est indenté sous le `with` est rattaché à ce run. Une ligne désindentée par erreur, et ta métrique atterrit en dehors — ou nulle part.

### `mlflow.log_params(params)`

Enregistre les hyperparamètres. Pluriel : prend un dictionnaire et logge toutes les paires d'un coup. Le singulier existe aussi : `mlflow.log_param('max_depth', 20)`.

Un paramètre MLflow est **immuable** : une fois loggé dans un run, il ne peut plus changer. Ça a du sens — la configuration d'un entraînement est fixée avant qu'il commence.

### `root_mean_squared_error(y_val, y_pred)`

**L'ordre est : vérité d'abord, prédiction ensuite.** Pour le RMSE l'ordre n'a pas d'incidence (l'erreur est élevée au carré, donc symétrique), mais pour d'autres métriques il change le résultat. Prends l'habitude correcte tout de suite.

L'ancienne écriture du cours :

```python
rmse = mean_squared_error(y_pred, y_val, squared=False)   # ✗ scikit-learn ≥ 1.6
```

L'argument `squared` a été **supprimé en scikit-learn 1.6**, au profit d'une fonction dédiée :

```python
from sklearn.metrics import root_mean_squared_error
rmse = root_mean_squared_error(y_val, y_pred)             # ✓
```

Tu es en 1.9.0, donc l'ancienne forme lève une `TypeError`. Le matériel du cours date de 2022 ; c'est le genre d'écart que tu rencontreras régulièrement.

### `mlflow.log_metric('rmse', rmse)`

Enregistre un résultat mesuré. Contrairement à un paramètre, une **métrique est versionnée dans le temps** : tu peux la logger plusieurs fois dans un même run avec un `step`, et MLflow en trace la courbe.

```python
for epoch in range(100):
    mlflow.log_metric('loss', loss, step=epoch)   # ← une courbe dans l'UI
```

Ici, une seule valeur suffit : un `RandomForest` n'a pas d'époques.

C'est la différence de fond entre les deux :

| | `log_params` | `log_metric` |
|---|---|---|
| Nature | ce que tu as **décidé** | ce que tu as **mesuré** |
| Type | texte | nombre |
| Dans le temps | une seule valeur, immuable | une série, avec `step` |
| Usage dans l'UI | filtrer, grouper | trier, comparer, tracer |

### `model_info = mlflow.sklearn.log_model(pipeline, name="model")`

C'est la ligne qui fait basculer le notebook dans le déploiement. Elle mérite sa propre section — voir §7 et §8.

### `RUN_ID = run.info.run_id` (hors du bloc)

L'objet `run` reste accessible après la fermeture du `with`. Ce n'est pas la variable Python qui disparaît — c'est seulement le run **côté serveur** qui passe au statut `FINISHED`.

C'est une nuance qui déroute au début : le `with` gère un *effet de bord* (l'état du run sur le serveur), pas la durée de vie de la variable.

---

## 7. Les quatre familles de `log_*` : `log_params`, `log_metric`, `log_artifact`, `log_model`

MLflow propose quatre façons d'enregistrer quelque chose dans un run. Elles sont souvent confondues. Voici la carte.

| Fonction | Ce qu'elle enregistre | Format | Exemple |
|---|---|---|---|
| `log_param(s)` | une décision de configuration | clé → texte | `max_depth = 20` |
| `log_metric` | un résultat mesuré | clé → nombre (+ `step`) | `rmse = 6.7` |
| `log_artifact` | **un fichier quelconque** | fichier brut | un `.png`, un `.csv`, un `.bin` |
| `log_model` | **un modèle**, au format standard MLflow | dossier structuré | le pipeline sérialisé |

### `mlflow.log_artifact` — ce que c'est

```python
mlflow.log_artifact(local_path="models/preprocessor.b", artifact_path="preprocessor")
```

Traduction : « prends ce fichier qui existe sur mon disque, et copie-le dans le stockage d'artifacts de ce run, sous ce sous-dossier ».

MLflow ne regarde **pas** ce qu'il y a dedans. C'est un dépôt de fichiers, point. Tu peux y mettre :

- une courbe d'apprentissage en `.png`
- un `requirements.txt`
- un échantillon des données d'entrée en `.csv`
- un rapport de validation en `.html`
- … ou un objet Python picklé à la main

> Note de vocabulaire : dans MLflow, « **artifact** » veut simplement dire « fichier attaché à un run ». Ce n'est pas un terme technique chargé de sens ; c'est un synonyme de « pièce jointe ».

### Ce que le cours en faisait, et pourquoi tu ne l'utilises pas

Dans la version originale du cours, le `DictVectorizer` était entraîné **séparément** du modèle, puis picklé à la main et attaché au run :

```python
# Version historique du cours — reconstituée
with open('dict_vectorizer.bin', 'wb') as f_out:
    pickle.dump(dv, f_out)

mlflow.log_artifact('dict_vectorizer.bin')       # ← le DV, en pièce jointe
mlflow.sklearn.log_model(model, artifact_path="model")   # ← le modèle, à part
```

Et côté consommation, dans le notebook du cours :

```python
path = client.download_artifacts(run_id=RUN_ID, path='dict_vectorizer.bin')
with open(path, 'rb') as f_out:
    dv = pickle.load(f_out)
```

C'est exactement la cellule 9 de ton notebook, celle que tu as commentée. Elle **téléchargeait la pièce jointe** pour reconstituer le duo `(dv, model)` côté service.

**Pourquoi c'est devenu inutile chez toi** : ton `DictVectorizer` n'est plus un objet séparé. Il est *dans* le pipeline, et le pipeline part entier dans `log_model`. Il n'y a plus de pièce jointe à attacher, plus de pièce jointe à télécharger, plus de risque de désynchronisation entre les deux.

```
Version cours (MLflow 2 + objets séparés)
    log_model(model)        →  models/…            ┐  deux choses à
    log_artifact(dv.bin)    →  dict_vectorizer.bin ┘  charger et à synchroniser

Ta version (Pipeline)
    log_model(pipeline)     →  models/…               une seule chose
```

C'est le même gain que celui du §5, vu depuis MLflow au lieu de scikit-learn : **le `Pipeline` supprime le besoin de `log_artifact`**.

### Quand `log_artifact` te resservira

Dès que tu voudras attacher à un run quelque chose qui n'est **pas** le modèle :

- un graphique de résidus pour justifier un choix
- le fichier de configuration exact utilisé
- un rapport de drift (module 5)
- la liste des colonnes vues à l'entraînement

Ce sont des pièces justificatives. Elles ne servent pas à prédire, elles servent à **comprendre et à auditer**.

### `mlflow.sklearn.log_model` — ce que ça fait vraiment

```python
model_info = mlflow.sklearn.log_model(pipeline, name="model")
```

Ce n'est pas un `log_artifact` sur un pickle. C'est plus riche. MLflow sérialise le pipeline **et** écrit autour de lui un dossier standardisé :

```
model/
├── MLmodel                 ← le manifeste : flavors, signature, version MLflow
├── model.pkl               ← le pipeline sérialisé
├── conda.yaml              ← l'environnement conda pour le recharger
├── python_env.yaml         ← idem, version venv
└── requirements.txt        ← les versions exactes des dépendances
```

C'est la cellule 10 de ton notebook qui te montre ce contenu :

```python
for a in mlflow.artifacts.list_artifacts(artifact_uri=model_info.model_uri):
    print(a.path)
```

Deux choses à retenir de cette structure.

**Le fichier `MLmodel` déclare des *flavors*.** Une *flavor* est une façon de charger le modèle. Ton pipeline en a deux :

- `sklearn` — pour le récupérer comme un vrai objet scikit-learn (`mlflow.sklearn.load_model`)
- `python_function` — pour le charger comme une boîte noire avec une méthode `.predict()` (`mlflow.pyfunc.load_model`)

C'est la seconde que `predict.py` utilise. Pourquoi ? Parce qu'elle est **générique** : le même code de service fonctionne que le modèle soit un scikit-learn, un XGBoost, un PyTorch ou un modèle custom. Le service n'a pas à savoir ce qu'il sert.

```python
# Dans predict.py — générique, marche avec n'importe quel modèle MLflow
model = mlflow.pyfunc.load_model(MODEL_URI)

# Dans ton notebook cellule 13 — spécifique, pour inspecter l'objet sklearn
pipeline = mlflow.sklearn.load_model(model_info.model_uri)
print(pipeline.named_steps)
```

**Le `requirements.txt` est ta réponse à « quelles versions ont entraîné ce modèle ? »** C'est le point que tes notes soulignent : pour un modèle picklé à la main, il faut aller fouiller les octets du fichier (`strings lin_reg.bin | grep _sklearn_version`). Pour un modèle MLflow, l'information est écrite à côté, en clair. Tu t'en serviras au moment du `Pipfile`.

### `name="model"` — un seul argument, beaucoup de sens

Le `name` nomme le modèle **à l'intérieur** du run. Tu pourrais en logger plusieurs :

```python
mlflow.sklearn.log_model(pipeline_rf,  name="random-forest")
mlflow.sklearn.log_model(pipeline_gbm, name="gradient-boosting")
```

La convention `"model"` quand il n'y en a qu'un est solidement établie — garde-la.

Attention : en MLflow 2 le paramètre s'appelait `artifact_path`. C'est le sujet de la section suivante.

---

## 8. MLflow 2.x vs 3.x : ce qui a cassé et pourquoi

C'est le changement qui t'a coûté le plus de temps. Il mérite d'être compris, pas seulement contourné.

### Le changement de fond

**En MLflow 2**, un modèle était **un dossier d'artifacts à l'intérieur d'un run**. `log_model` n'était qu'un `log_artifact` déguisé, qui écrivait dans `<run>/artifacts/model/`. D'où l'adressage `runs:/<run_id>/model` : « le sous-dossier `model` des artifacts du run untel ».

**En MLflow 3**, le modèle est devenu une **entité de premier ordre** (*first-class citizen*). Il a sa propre existence, son propre identifiant (`model_id`), et le run ne fait plus que le *référencer*.

L'intuition derrière ce choix : **un modèle a un cycle de vie plus long que l'expérience qui l'a produit.** Il est promu, déployé, comparé, retiré, redéployé. Le coupler à jamais au run qui l'a créé était une contrainte artificielle.

### Le tableau des différences

| | MLflow 2 | MLflow 3 |
|---|---|---|
| Logger un modèle | `log_model(m, artifact_path="model")` | `log_model(m, name="model")` |
| Identifiant du modèle | `runs:/<run_id>/model` | `models:/m-<hash>` |
| Récupérer l'URI | construite à la main en f-string | `model_info.model_uri` |
| `client.list_artifacts(RUN_ID)` | montre `model/` | **ne le montre plus** — il n'est plus là |
| Télécharger un artifact | `client.download_artifacts(...)` | **retirée** → `mlflow.artifacts.download_artifacts(...)` |
| Lister les fichiers d'un modèle | — | `mlflow.artifacts.list_artifacts(artifact_uri=...)` |

### `run_id` et `model_id` : deux questions différentes

C'est la confusion à dissiper, et c'est la réponse à la question que tu notais dans `04-buildmyservice.md` (« pour MODEL_URI : faut prendre l'ID du run ou l'ID du model ? ») :

| | `run_id` | `model_id` |
|---|---|---|
| Répond à | « quelle **exécution d'entraînement** ? » | « quel **modèle** ? » |
| Contient | params, métriques, artifacts divers, tags, durée | l'objet sérialisé à servir |
| Forme | `0ee6291ee44b48b4a7aae38f11a01465` | `m-5e276730f7004842b7c3a36ea11b5044` |
| URI | `runs:/<run_id>/…` | `models:/m-<hash>` |
| Sert à | comprendre, comparer, auditer | **déployer** |

**Pour `MODEL_URI` dans `predict.py`, c'est le `model_id`.** C'est-à-dire exactement la valeur que te rend `model_info.model_uri`, et que la cellule 6 imprime pour que tu n'aies qu'à la copier.

C'est aussi pourquoi ton `predict.py` renvoie `model_version: MODEL_URI` dans sa réponse : en cas d'incident, tu peux relier chaque prédiction au modèle exact qui l'a produite.

### `models:/m-<hash>` vs modèle enregistré : une nuance

Tu croiseras une **troisième** forme d'URI dans la documentation :

```python
'models:/m-5e276730f7004842b7c3a36ea11b5044'    # un logged model — ton cas
'models:/ride-duration/3'                        # un registered model, version 3
'models:/ride-duration@champion'                 # un registered model, par alias
```

La première désigne **le modèle tel qu'il a été loggé** — un identifiant technique, opaque.

Les deux suivantes désignent un modèle **enregistré dans le Model Registry** sous un nom métier. C'est une couche au-dessus : tu déclares « ce modèle-là s'appelle désormais `ride-duration`, il est en version 3, et l'alias `champion` pointe dessus ». Réentraîner devient alors : logger un nouveau modèle, l'enregistrer en version 4, et déplacer l'alias — **sans toucher au service**, qui pointe sur `@champion`.

Ce n'est pas au programme de ce chapitre, mais c'est la suite logique, et c'est ce qu'on fait en entreprise. Retiens juste la hiérarchie :

```
run          ─► produit un logged model  (models:/m-…)
logged model ─► peut être enregistré     (models:/nom/version)
version      ─► peut recevoir un alias   (models:/nom@champion)
```

### `mlflow.artifacts.list_artifacts` — la cellule 10

```python
for a in mlflow.artifacts.list_artifacts(artifact_uri=model_info.model_uri):
    print(a.path)
```

Elle remplace l'ancienne `client.list_artifacts(RUN_ID)`, qui en MLflow 3 renverrait une liste **vide** — le modèle n'étant plus dans les artifacts du run.

Note le changement de paradigme dans l'API : on ne passe plus par un `client` attaché à un run, mais par un module `mlflow.artifacts` qui travaille sur une **URI**. C'est cohérent avec le reste : en MLflow 3, l'unité d'adressage est l'URI, pas le run.

---

## 9. Les cellules d'inspection (6 à 13)

Ces cellules ne participent pas au flux principal. Elles servent à **voir** ce qui a été produit. C'est une bonne habitude : après une opération qui écrit quelque part, on vérifie ce qui a été écrit.

### Cellule 6 — récupérer l'URI

```python
print(model_info.model_uri)   # → models:/m-xxxxxxxx
```

C'est la valeur que tu copieras dans le terminal :

```bash
export MODEL_URI='models:/m-5e276730f7004842b7c3a36ea11b5044'
```

**Récupérer cette valeur de `model_info` plutôt que la reconstruire à la main est une règle.** Une URI construite en f-string (`f'runs:/{RUN_ID}/model'`) suppose que tu connais le format attendu par ta version de MLflow — et ce format vient justement de changer. Demande à la bibliothèque, ne devine pas.

### Cellules 7–8 — le `MlflowClient`

```python
from mlflow.tracking import MlflowClient

MLFLOW_TRACKING_URI = 'http://127.0.0.1:5000'
RUN_ID = '0ee6291ee44b48b4a7aae38f11a01465'

client = MlflowClient(tracking_uri=MLFLOW_TRACKING_URI)
```

Deux façons de parler à MLflow coexistent, et c'est une source de confusion :

| | API fonctionnelle | API client |
|---|---|---|
| Écriture | `mlflow.log_metric(...)` | `client.log_metric(run_id, ...)` |
| État | garde un « run courant » implicite | sans état — tu passes l'id à chaque appel |
| Usage | dans un script d'entraînement | pour explorer, administrer, scripter |

`MlflowClient` est l'API bas niveau. Elle sert quand tu veux lister des runs, chercher le meilleur, renommer, supprimer, gérer le registry — bref, quand tu n'es pas en train d'entraîner.

Ici, ces deux cellules ne servent à rien dans le flux : tu peux les laisser, mais marque-les comme exploratoires.

> Le `RUN_ID` codé en dur ici est le tien. Dans le notebook original du cours, c'était celui de l'auteur (`b4d3bca8...`), qui n'existe évidemment pas chez toi. C'est le premier piège du chapitre pour tout le monde.

### Cellules 9, 11, 12 — le code mort

```python
# path = client.download_artifacts(run_id=RUN_ID, path='dict_vectorizer.bin')  → MLflow 2
# with open(path, 'rb') as f_out:
#     dv = pickle.load(f_out)
```

L'ancienne méthode, doublement obsolète : `download_artifacts` a disparu du client en MLflow 3, **et** il n'y a plus de `dict_vectorizer.bin` à télécharger puisque le DV est dans le pipeline.

Si tu voulais vraiment télécharger un artifact en MLflow 3 :

```python
path = mlflow.artifacts.download_artifacts(artifact_uri='...')
```

### Cellule 13 — voir le `DictVectorizer` *dans* le pipeline

```python
pipeline = mlflow.sklearn.load_model(model_info.model_uri)
print(pipeline.named_steps)

dv = pipeline.named_steps['dictvectorizer']
print(len(dv.feature_names_))
```

Excellente cellule pédagogique — elle démontre concrètement le point du §5.

- `mlflow.sklearn.load_model` (et non `pyfunc`) parce que tu veux le **vrai objet scikit-learn**, pas la boîte noire.
- `named_steps` te rend le dictionnaire des étapes.
- `feature_names_` est la liste des colonnes apprises par le vectorizer. Sa longueur te dit combien de features le modèle manipule — et donc, indirectement, combien de trajets `PU_DO` distincts il a vus.

**C'est la preuve que le DV a bien voyagé avec le modèle.** Tu ne l'as jamais sauvegardé séparément, tu ne l'as jamais téléchargé, et pourtant il est là, entraîné, avec son vocabulaire.

---

## 10. Tableau des différences avec `duration-prediction.ipynb`

Le récapitulatif de tout ce document.

| | `01-intro/duration-prediction.ipynb` | `04-deployment/web-service-mlflow/random-forest.ipynb` |
|---|---|---|
| **Algorithme** | `LinearRegression` | `RandomForestRegressor` |
| **Préprocessing** | `dv = DictVectorizer()` manipulé à la main | `DictVectorizer()` **dans** un `Pipeline` |
| **`fit`** | `dv.fit_transform()` puis `lr.fit()` — deux appels | `pipeline.fit()` — un appel |
| **`predict`** | `dv.transform()` puis `lr.predict()` — deux appels | `pipeline.predict()` — un appel |
| **Risque de fuite de données** | réel (rien n'empêche un `fit_transform` sur la validation) | **structurellement impossible** |
| **Objet produit** | un **tuple** `(dv, lr)` | **un** objet `Pipeline` |
| **Sauvegarde** | `pickle.dump((dv, lr), f_out)` dans un fichier local | `mlflow.sklearn.log_model(pipeline, name="model")` |
| **Où vit le modèle** | `models/lin_reg.bin`, dans le dossier | stockage d'artifacts MLflow, référencé par `models:/m-…` |
| **Traçabilité** | aucune — le fichier ne dit rien de son origine | run MLflow : params, rmse, versions, date, code |
| **Versions de bibliothèques** | à retrouver dans les octets du pickle | écrites dans `requirements.txt` à côté du modèle |
| **Suivi d'expériences** | aucun | `set_experiment`, `log_params`, `log_metric` |
| **Identification** | le nom du fichier | `model_id` (`models:/m-…`) et `run_id` |
| **Pour changer de modèle** | remplacer le fichier et reconstruire l'image | changer une variable d'environnement |
| **Métrique** | `root_mean_squared_error` | `root_mean_squared_error` (idem) |
| **Reproductibilité** | non fixée | `random_state=0` + params loggés |
| **Ce que fait `predict.py`** | `dv.transform()` puis `model.predict()` | `model.predict()` |

### La phrase à retenir

> Au module 1, le modèle était **un fichier**. Ici, c'est **une entité identifiée, tracée et adressable**.

Et le `Pipeline` est ce qui rend ce passage possible : sans lui, l'entité serait incomplète, puisqu'il faudrait quand même transporter le vectorizer à côté.

---

## 11. Ce que le notebook livre à `predict.py`

Le notebook produit exactement **une chaîne de caractères** :

```
models:/m-5e276730f7004842b7c3a36ea11b5044
```

C'est tout. Cette chaîne est le contrat entre le notebook et le service.

Côté service :

```python
MODEL_URI = os.getenv('MODEL_URI')
model = mlflow.pyfunc.load_model(MODEL_URI)
...
def predict(features):
    preds = model.predict(features)      # ← la vectorisation est dedans
    return float(preds[0])
```

### Le concept à emporter : l'URI est un pointeur

Regarde ces trois lignes :

```python
model = mlflow.pyfunc.load_model('s3://mlflow-models-alexey/1/abc.../artifacts/model')
model = mlflow.pyfunc.load_model('models:/m-5e276730f700...')
model = mlflow.pyfunc.load_model('/home/pierre/models/model')
```

**Le code est identique.** Seule la chaîne change. MLflow lit le *schéma* — la partie avant `://` ou `:/` — et choisit le mécanisme de téléchargement approprié : S3, registre, disque local, Azure Blob, HTTP.

C'est ce qu'on appelle une **abstraction** : une interface unique qui masque des implémentations différentes. C'est elle qui permet de passer du développement à la production sans réécrire une ligne.

### La nuance qui compte : référence directe vs indirecte

| | `s3://bucket/...` | `models:/m-...` (ton cas) |
|---|---|---|
| Nature | adresse **complète** | référence **indirecte** |
| Étape supplémentaire | aucune | demander au serveur « où est ce modèle ? » |
| `set_tracking_uri()` nécessaire ? | **non** | **oui**, impérativement, avant le `load_model` |
| Serveur MLflow requis au démarrage | non | **oui** |

Un URI `s3://` est **auto-suffisant** : il contient l'adresse du fichier.

Un URI `models:/m-...` est **une référence** : MLflow doit d'abord demander au serveur de tracking où le modèle est rangé, recevoir le vrai chemin, puis seulement télécharger. D'où l'obligation absolue de configurer `set_tracking_uri()` avant.

**Conséquence** : ton service ne peut pas démarrer si le serveur MLflow est éteint. C'est un *point de défaillance unique*. La solution du cours — pointer directement sur `s3://` — supprime ce maillon :

```
Ton setup : service → serveur MLflow → stockage → modèle
Son setup : service ─────────────────→ stockage → modèle
```

Ce n'est pas du bricolage de la part de l'instructeur, c'est **le point du chapitre**.

### Un détail de format à connaître pour plus tard

`predict.py` passe un **dictionnaire unique** à `model.predict()` :

```python
features = {'PU_DO': '10_50', 'trip_distance': 40}
preds = model.predict(features)
```

Ça fonctionne parce que le `DictVectorizer` accepte aussi bien un dictionnaire seul qu'une liste de dictionnaires.

Deux réserves pour la suite :

- **Si tu logges une *signature* de modèle** (`mlflow.sklearn.log_model(..., signature=...)`), MLflow devient strict sur le format d'entrée et peut refuser un dict nu. C'est une bonne pratique en production — mais elle demande d'adapter `predict.py` en conséquence.
- **Pour prédire en lot**, passe une liste : `model.predict([f1, f2, f3])` renvoie un tableau. C'est ce que fera le chapitre *batch*.

---

## 12. Les pièges rencontrés, et ce qu'ils enseignent

| Symptôme | Cause réelle | Leçon |
|---|---|---|
| `TypeError` sur `squared=False` | argument retiré en scikit-learn 1.6 | le matériel de cours vieillit, pas l'écosystème |
| `run` n'existe pas | `with mlflow.start_run()` sans `as run` | le `with` crée le contexte, le `as` te donne la poignée |
| `client.list_artifacts()` renvoie vide | MLflow 3 : le modèle n'est plus dans les artifacts du run | lire les *release notes* d'une majeure |
| `download_artifacts` inexistante | méthode retirée du client en MLflow 3 | une API bouge ; l'objet qu'elle manipulait aussi |
| `RUN_ID` du cours introuvable | c'est l'identifiant de l'auteur | tout id codé en dur dans un tutoriel est à remplacer |
| `NoCredentialsError` | l'URI pointait sur `s3://`, MLflow a cherché des clés AWS | **lis le schéma de l'URI** : il dit où le code va aller |
| Le modèle chargé n'est pas celui attendu | fichier non sauvegardé dans VS Code | Python lit le **disque**, VS Code te montre un **buffer** |

### La famille de pièges « où », pas « quoi »

Tu as rencontré plusieurs variantes du même problème :

- mauvais environnement conda activé
- kernel Jupyter différent de celui du terminal
- fichier non sauvegardé (`●` au lieu de `×` dans l'onglet VS Code)
- mauvais répertoire de travail

Dans tous les cas, **ton code est juste**. Ce qui est faux, c'est le *contexte d'exécution*. Quand une erreur te paraît absurde au regard de ce que tu as écrit, suspecte le contexte avant la logique :

```bash
which python           # quel interpréteur ?
pwd                    # quel dossier ?
conda env list         # quels environnements, lequel est actif ?
echo $MODEL_URI        # quelle configuration ?
```

### Lire une traceback

La compétence de debug la plus rentable que tu puisses acquérir, en quatre réflexes :

1. **La dernière ligne en premier.** C'est l'erreur réelle (`NoCredentialsError: Unable to locate credentials`). Tout ce qui précède n'est que le chemin parcouru pour y arriver.
2. **La première ligne ensuite.** C'est *ton* code, le point d'entrée. Le milieu, ce sont les bibliothèques — tu n'as presque jamais besoin de le lire.
3. **Vérifie que le code affiché correspond à ce que tu as écrit.** La traceback cite la ligne telle qu'elle est *sur le disque*. C'est exactement comme ça qu'on a trouvé ton fichier non sauvegardé.
4. **Cherche les indices dans les chemins de fichiers.** `s3_artifact_repo.py` puis `botocore` disaient sans ambiguïté que le code partait vers AWS. Les noms de fichiers racontent l'histoire.

---

## 13. Mémo : les commandes et les vérifications

### Avant de lancer le notebook

```bash
conda activate mlopszoomcamp
cd /workspaces/mlops-zoomcamp/04-deployment/web-service-mlflow
```

Lancer le serveur MLflow dans un terminal dédié (détaillé dans `04-IT-web-service-mlflow.md`) :

```bash
mlflow server \
  --backend-store-uri sqlite:////workspaces/mlops-zoomcamp/04-deployment/web-service-mlflow/mlflow.db \
  --default-artifact-root /workspaces/mlops-zoomcamp/04-deployment/web-service-mlflow/artifacts \
  --host 0.0.0.0 \
  --port 5000
```

Puis **vérifie le kernel du notebook** : il doit être `mlopszoomcamp`, pas `base`.

### Vérifier ses versions

```bash
python -c "import sys, sklearn, mlflow; print(sys.version.split()[0], sklearn.__version__, mlflow.__version__)"
# → 3.11.16 1.9.0 3.16.0
```

Ces trois valeurs sont **critiques** : ton modèle a été sérialisé par elles. Tu les réutiliseras telles quelles dans le `Pipfile`.

### Inspecter le modèle après l'entraînement

```python
# Son identifiant, à copier dans le terminal
print(model_info.model_uri)
print(run.info.run_id)

# Ce que le dossier du modèle contient
for a in mlflow.artifacts.list_artifacts(artifact_uri=model_info.model_uri):
    print(a.path)

# Les étapes du pipeline, et la taille du vocabulaire appris
pipeline = mlflow.sklearn.load_model(model_info.model_uri)
print(pipeline.named_steps)
print(len(pipeline.named_steps['dictvectorizer'].feature_names_))
```

### Un test qui vaut mieux qu'une explication

Pour graver la distinction « le modèle vit en mémoire » / « le serveur est requis au démarrage » :

1. Lance le service, `test.py` fonctionne.
2. Arrête MLflow (`Ctrl+C` dans son terminal).
3. Relance `test.py` → **ça marche encore** (le modèle est en RAM).
4. Arrête le service et relance `python predict.py` → **ça plante** (il faut MLflow pour résoudre `models:/`).

Cinq minutes, et la distinction est acquise pour de bon.

---

## Ce qu'il faut retenir en trois phrases

1. **Le `Pipeline` transforme deux objets fragiles en un seul objet cohérent**, et rend la fuite de données structurellement impossible.
2. **MLflow transforme ce seul objet en entité identifiée** : le service ne transporte plus un fichier, il pointe vers un identifiant.
3. **`models:/` est une référence indirecte** — pratique, mais elle couple ton service au serveur MLflow au démarrage. `s3://` est ce qui brise ce couplage.

---

*Document de notes personnelles — MLOps Zoomcamp, module 4, partie `web-service-mlflow`.*
*Suite : `04-IT-web-service-mlflow.md` — du notebook au conteneur Docker.*
