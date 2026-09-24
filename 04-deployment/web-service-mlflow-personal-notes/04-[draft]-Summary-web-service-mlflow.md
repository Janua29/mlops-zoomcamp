Voici le récapitulatif complet de cette partie. Prends le temps de le lire en entier, il consolide tout ce qu'on a traversé.

---

# Récapitulatif — 04-deployment / web-service-mlflow

## 1. L'objectif du chapitre

Au chapitre précédent (`web-service`), ton modèle était un fichier `.bin` posé à côté de ton code. Simple, mais fragile : d'où vient ce fichier ? Avec quelles données a-t-il été entraîné ? Quelle version est en production ?

Ici, on remplace ce fichier par **une référence vers le registre MLflow**. Ton service ne transporte plus le modèle, il va le chercher. C'est ça, le passage de « déployer un fichier » à « déployer une référence ».

---

## 2. Pipeline vs ancienne méthode

### L'ancienne méthode : deux objets séparés

```python
dv = DictVectorizer()
X_train = dv.fit_transform(dict_train)      # objet 1
model = RandomForestRegressor()
model.fit(X_train, y_train)                 # objet 2
```

Il faut alors sauvegarder **deux choses**, et les recharger **toutes les deux** dans `predict.py` :

```python
X = dv.transform(dicts)
y = model.predict(X)
```

Les problèmes sont réels :
- deux téléchargements, deux chargements, deux occasions de se tromper
- rien ne garantit que le `dv` chargé est celui qui a servi à entraîner ce modèle-là
- la logique de transformation est **dupliquée** entre le notebook et `predict.py` : si tu changes l'un sans l'autre, tu produis des prédictions fausses sans aucune erreur. C'est le pire type de bug — silencieux.

### Le Pipeline : un seul objet

```python
pipeline = make_pipeline(
    DictVectorizer(),
    RandomForestRegressor(**params, n_jobs=-1)
)
```

Le `Pipeline` est un objet scikit-learn qui **encapsule une chaîne d'étapes**. Il expose la même interface qu'un modèle ordinaire (`fit`, `predict`), mais en interne il fait passer les données par chaque étape.

Conséquence décisive : quand tu le sérialises, **tout part ensemble**. Le DictVectorizer entraîné, avec le vocabulaire qu'il a appris, voyage à l'intérieur du modèle. Il n'y a plus qu'un objet à gérer, et la cohérence est garantie par construction.

Dans `predict.py`, ça devient :

```python
preds = model.predict([features])   # la vectorisation est dedans
```

### Cellules du notebook : utiles / inutiles

| Cellule | Statut | Pourquoi |
|---|---|---|
| chargement des données, `read_dataframe` | **utile** | inchangé |
| construction de `dict_train` / `dict_val` | **utile** | le Pipeline prend des dicts en entrée |
| `dv = DictVectorizer()` seul, `dv.fit_transform(...)` | **inutile** | le Pipeline s'en charge |
| entraînement avec `make_pipeline` | **utile** | c'est le cœur |
| `client.download_artifacts(... 'dict_vectorizer.bin')` | **inutile** | plus de DV séparé |
| `with open(path, 'rb'): dv = pickle.load(...)` | **inutile** | idem |
| `MlflowClient(tracking_uri=...)` | **optionnel** | pratique pour explorer, plus nécessaire au flux principal |
| `RUN_ID = 'b4d3bca8...'` codé en dur | **à remplacer** | l'ID de l'auteur du cours, inexistant chez toi |

---

## 3. MLflow 3 vs MLflow 2

C'est le changement qui t'a coûté le plus de temps, il mérite d'être bien compris.

### Le changement de fond

En MLflow 2, un modèle était **un dossier d'artifacts à l'intérieur d'un run**. `log_model` n'était qu'un `log_artifact` déguisé.

En MLflow 3, le modèle est devenu une **entité de premier ordre** : il a sa propre existence, son propre identifiant (`model_id`), et le run ne fait plus que le référencer.

L'intuition derrière ce choix : un modèle a un cycle de vie plus long que l'expérience qui l'a produit. Il est promu, déployé, comparé, retiré. Le coupler au run qui l'a créé était une contrainte artificielle.

### Le tableau des différences

| | MLflow 2 | MLflow 3 |
|---|---|---|
| Logger un modèle | `log_model(m, artifact_path="model")` | `log_model(m, name="model")` |
| Identifiant | `runs:/<run_id>/model` | `models:/m-<hash>` |
| Récupérer l'URI | construite à la main | `model_info.model_uri` |
| `client.list_artifacts(RUN_ID)` | montre `model/` | **vide** (le modèle n'est plus là) |
| `client.download_artifacts(...)` | existe | **retirée** → `mlflow.artifacts.download_artifacts(...)` |

### Ce qu'il faut retenir

Le `run_id` et le `model_id` répondent à deux questions différentes :
- **run_id** : « quelle exécution d'entraînement ? » — params, métriques, artifacts divers
- **model_id** : « quel modèle ? » — l'objet servi en production

Pour déployer, c'est le `model_id` qui compte. C'est pourquoi ton `predict.py` renvoie `model_version: MODEL_URI` : en cas d'incident, tu sais exactement quel modèle a produit quelle prédiction.

---

## 4. Bucket S3 vs serveur local dans `predict.py`

### Le concept clé : l'URI est un pointeur

Regarde ces trois lignes :

```python
model = mlflow.pyfunc.load_model('s3://mlflow-models-alexey/1/abc.../artifacts/model')
model = mlflow.pyfunc.load_model('models:/m-5e276730f700...')
model = mlflow.pyfunc.load_model('/home/pierre/models/model')
```

**Le code est identique.** Seule la chaîne change. MLflow lit le **schéma** (la partie avant `://` ou `:/`) et choisit le mécanisme de téléchargement approprié — S3, local, HTTP, Azure Blob…

C'est ce qu'on appelle une **abstraction** : une interface unique qui masque des implémentations différentes. C'est ce qui permet de passer du dev à la prod sans réécrire le code.

### Ce que ça change concrètement

| | `s3://...` | `models:/m-...` (ton cas) |
|---|---|---|
| Où vit le modèle | AWS, dans le cloud | disque du Codespace |
| Ce qu'il faut pour y accéder | clés AWS (`AWS_ACCESS_KEY_ID`…) | le serveur MLflow joignable |
| `set_tracking_uri()` nécessaire ? | non — l'adresse est complète | **oui** — il faut résoudre la référence |
| Ton erreur `NoCredentialsError` | ← venait de là | — |

### Le point subtil sur `models:/`

Un URI `s3://` est **auto-suffisant** : il contient l'adresse complète du fichier.

Un URI `models:/m-...` est **une référence indirecte**. MLflow doit d'abord demander au serveur de tracking : « où est rangé le modèle `m-5e276730` ? » Le serveur répond avec le vrai chemin, et seulement ensuite le téléchargement a lieu.

D'où l'obligation absolue de :

```python
mlflow.set_tracking_uri("http://127.0.0.1:5000")
```

**avant** le `load_model`. Sans ça, MLflow ne sait à qui poser la question.

### La fragilité que ça introduit

Ton service web ne peut plus démarrer si le serveur MLflow est éteint. En production, c'est un **point de défaillance unique** : MLflow tombe → plus aucun nouveau déploiement ne peut démarrer.

La solution du cours : pointer directement vers le stockage des artifacts (`s3://...`), en contournant le serveur de tracking. Le service devient autonome. C'est précisément pour ça qu'Alexey utilise S3 dans le fichier original.

---

## 5. Pourquoi pas de nouveau pipenv

### Rappel de pourquoi il en fallait un au chapitre précédent

Le modèle `.bin` fourni par le cours avait été **pické avec scikit-learn 1.0.2**. Le pickle Python ne stocke pas les objets, il stocke des instructions de reconstruction qui référencent des classes précises. Si la structure interne de la classe a changé entre 1.0.2 et 1.9, la reconstruction casse — d'où la cascade : pipenv → Python 3.10 → `numpy<2`.

### Pourquoi c'est différent ici

**C'est toi qui viens d'entraîner le modèle**, dans `mlopszoomcamp`. Le modèle a été sérialisé avec exactement les versions présentes dans cet environnement. Quand `predict.py` le recharge depuis ce même environnement, les versions correspondent nécessairement.

Le problème d'incompatibilité n'existe pas parce que **producteur et consommateur sont le même environnement**.

### Quand pipenv redeviendra nécessaire

Au moment du Docker. Là, tu construis un environnement **neuf**, vide, à partir d'une image de base. Tu dois donc déclarer explicitement ce qu'il faut y installer — et le `Pipfile.lock` sert exactement à ça : garantir que le conteneur reçoit les mêmes versions que ta machine.

Le principe général : **un environnement isolé est nécessaire quand le code va s'exécuter ailleurs que là où il a été développé.**

### Méthode de travail à retenir

Fais marcher le code d'abord, empaquette-le ensuite. Si tu introduis Docker et MLflow en même temps et que ça casse, tu ne sais pas lequel des deux accuser. **Une variable à la fois.**

---

## 6. Le code du pipeline, ligne par ligne

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
    mlflow.log_metric('rmse', rmse)

    model_info = mlflow.sklearn.log_model(pipeline, name="model")

RUN_ID = run.info.run_id
```

### `with mlflow.start_run() as run:`

Deux mécanismes Python en une ligne.

**Le `with`** ouvre un *gestionnaire de contexte*. Il garantit qu'une action de fermeture aura lieu à la sortie du bloc, **même si une erreur survient**. Ici : le run sera marqué comme terminé côté serveur. Sans ça, une exception au milieu de l'entraînement laisserait un run éternellement « en cours ».

**Le `as run`** capture l'objet produit par le contexte dans une variable. Sans lui, le run existe et fonctionne, mais tu n'as aucun moyen de le désigner — d'où l'erreur qu'on a eue.

L'indentation définit la portée : tout ce qui est indenté est rattaché à ce run.

### `params = dict(...)` puis `mlflow.log_params(params)`

On définit les hyperparamètres **une seule fois**, dans une variable. Ils serviront à deux usages : configurer le modèle, et être enregistrés dans MLflow.

Si tu les écrivais deux fois, tu pourrais en modifier un et oublier l'autre — MLflow enregistrerait alors des paramètres qui ne correspondent pas au modèle réel. Ton expérience deviendrait irreproductible sans que rien ne le signale.

### `**params` — le dépaquetage

```python
RandomForestRegressor(**params)
# équivaut à :
RandomForestRegressor(max_depth=20, n_estimators=100, min_samples_leaf=10, random_state=0)
```

Le `**` devant un dictionnaire le **déplie** en arguments nommés. Chaque clé devient un nom de paramètre, chaque valeur son contenu. C'est ce qui permet de n'écrire les hyperparamètres qu'une fois.

### `n_jobs=-1`

Nombre de cœurs CPU à utiliser. `-1` signifie « tous ceux disponibles ». Une forêt aléatoire entraîne des arbres indépendants les uns des autres : ils peuvent donc être calculés en parallèle. Sur ton Codespace 2 cœurs, le gain est modeste mais réel.

`random_state=0` fixe le générateur aléatoire : deux exécutions identiques donneront le même modèle. Indispensable pour la reproductibilité.

### `make_pipeline(...)`

Construit le Pipeline en nommant automatiquement les étapes d'après le nom de la classe en minuscules : `dictvectorizer`, `randomforestregressor`. L'ordre compte — les données traversent les étapes de gauche à droite.

Tu peux inspecter le résultat :

```python
print(pipeline.named_steps)
```

### `pipeline.fit(dict_train, y_train)` — le point le plus important

Voici ce qui se passe en interne :

```
dict_train  →  DictVectorizer.fit_transform()  →  X_train  →  RandomForestRegressor.fit()
```

Le DictVectorizer reçoit un **`fit_transform`** : il apprend le vocabulaire (quelles clés existent, quelles valeurs catégorielles) *et* transforme les données.

### `pipeline.predict(dict_val)`

```
dict_val  →  DictVectorizer.transform()  →  X_val  →  RandomForestRegressor.predict()
```

Ici le DictVectorizer reçoit un **`transform` seul**. Il réutilise le vocabulaire appris sur le train, sans rien réapprendre.

**C'est exactement la distinction `fit_transform` / `transform` que tu connais** — sauf que le Pipeline l'applique correctement pour toi, automatiquement. C'est sa deuxième grande valeur, après l'encapsulation : il rend la fuite de données (*data leakage*) structurellement impossible. Si le DV réapprenait son vocabulaire sur les données de validation, ton score serait faussement optimiste.

### `root_mean_squared_error(y_val, y_pred)`

Attention à l'ordre : **vérité d'abord, prédiction ensuite**. Pour le RMSE l'ordre est sans conséquence (l'erreur est élevée au carré), mais pour d'autres métriques il change le résultat. Prends l'habitude correcte.

L'ancien `mean_squared_error(..., squared=False)` a été retiré en scikit-learn 1.6.

### `model_info = mlflow.sklearn.log_model(pipeline, name="model")`

Sérialise le Pipeline entier et l'enregistre comme entité MLflow. Retourne un objet `ModelInfo` contenant notamment `model_uri` — l'identifiant `models:/m-...` que tu passeras à `predict.py`.

Récupérer cette valeur plutôt que la reconstruire à la main est la bonne pratique : tu ne peux pas te tromper de format.

### `RUN_ID = run.info.run_id` (hors du bloc)

L'objet `run` reste accessible après la fermeture du `with` : la variable Python ne disparaît pas, c'est seulement le run côté serveur qui passe en statut terminé.

---

## 7. Bonnes pratiques VS Code

### Toujours sauvegarder avant d'exécuter

VS Code te montre un **buffer en mémoire**. Python lit le **fichier sur le disque**. Tant que tu n'as pas sauvegardé, ce sont deux choses différentes.

- Le signal : un **point ●** au lieu de la croix dans l'onglet du fichier
- Le réflexe : `Cmd+S` avant chaque exécution
- Le confort : active l'auto-save — `Cmd+Shift+P` → `Preferences: Open Settings (UI)` → chercher `auto save` → mettre `afterDelay`

À noter : Jupyter n'a pas ce problème, parce que le code de la cellule est envoyé directement au kernel. C'est justement pour ça que le piège surprend quand on passe du notebook au script.

### La méthode de lecture d'une traceback

C'est la compétence de debug la plus rentable que tu puisses acquérir.

**Lis la dernière ligne en premier.** C'est l'erreur réelle : `NoCredentialsError: Unable to locate credentials`. Tout ce qui est au-dessus n'est que le chemin parcouru pour y arriver.

**Lis la première ligne ensuite.** C'est *ton* code — le point d'entrée dans ton fichier. Le milieu, ce sont les bibliothèques ; tu n'as presque jamais besoin de le lire.

**Vérifie que le code affiché correspond à ce que tu as écrit.** La traceback cite la ligne source telle qu'elle est *sur le disque*. C'est exactement comme ça qu'on a trouvé ton fichier non sauvegardé : la ligne 12 affichée ne correspondait pas à ta ligne 12.

**Cherche les indices dans les chemins.** `s3_artifact_repo.py` puis `botocore` t'ont dit, sans ambiguïté, que le code essayait d'aller sur AWS. Les noms de fichiers racontent l'histoire.

### La famille de pièges « où », pas « quoi »

Tu as maintenant rencontré quatre variantes du même problème :

- mauvais environnement conda activé
- kernel Jupyter différent du terminal
- fichier non sauvegardé
- mauvais dossier de travail

Dans tous les cas, ton code est juste. Ce qui est faux, c'est **le contexte d'exécution**. Quand une erreur te semble absurde au regard de ton code, suspecte le contexte avant la logique :

```bash
which python          # quel interpréteur ?
pwd                   # quel dossier ?
conda env list         # quel environnement ?
head -20 fichier.py   # quel contenu réel ?
echo $MODEL_URI       # quelle configuration ?
```

---

## 8. L'architecture finale

Trois processus tournent simultanément :

| Terminal | Processus | Port | Rôle |
|---|---|---|---|
| 1 | serveur MLflow | 5000 | registre : métadonnées + artifacts |
| 2 | `predict.py` ou gunicorn | 9696 | service de prédiction |
| 3 | `test.py` | — | client, s'exécute et rend la main |

**Au démarrage**, le terminal 2 interroge le 5000 pour télécharger le modèle. Une fois chargé, le modèle vit en mémoire dans le processus.

**À chaque requête**, le terminal 3 envoie du JSON au 9696, qui prédit et répond. MLflow n'est plus sollicité.

Ce découplage est intentionnel : le chargement du modèle est coûteux, on le fait **une seule fois au démarrage**, pas à chaque requête. C'est pour ça que la ligne `load_model` est au niveau du module, en dehors de toute fonction.

### Les variables d'environnement

```bash
export MODEL_URI='models:/m-5e276730f7004842b7c3a36ea11b5044'
```

Principe : **séparer le code de sa configuration**. Le code dit *comment* servir un modèle, la variable dit *lequel*. Réentraîner ne demande alors aucune modification de code — juste une nouvelle valeur.

Trois choses à savoir :
- la variable ne vit que dans **ce terminal** — nouveau terminal, nouvel `export`
- vérification : `echo $MODEL_URI`
- en Docker : `docker run -e MODEL_URI='...'`

Et l'astuce du `os.getenv` à deux arguments :

```python
MODEL_URI = os.getenv('MODEL_URI', 'models:/m-5e276...')
```

Le second argument est une **valeur par défaut** si la variable n'existe pas. Pratique en développement, mais à éviter en production : une valeur codée en dur qui prend le relais silencieusement, c'est un incident en préparation.

---

## 9. Flask puis gunicorn

```bash
python predict.py                              # serveur de dev
gunicorn --bind=0.0.0.0:9696 predict:app       # serveur de production
```

Rappel de la distinction : **Flask est un framework** (il définit tes routes, parse le JSON), **gunicorn est un serveur** (il gère les connexions réseau, les processus, la concurrence). Ils se parlent via l'interface WSGI.

La syntaxe `predict:app` signifie : dans le module `predict`, prends l'objet nommé `app`.

Et `0.0.0.0` = écouter sur toutes les interfaces réseau, contre `127.0.0.1` = seulement les connexions locales. Indispensable en conteneur, comme tu l'as vu.

---

## 10. La suite

L'étape logique est la conteneurisation : `Dockerfile` avec pipenv, puis `docker build` et `docker run -e MODEL_URI=...`.

Un point à anticiper : un conteneur a **son propre `127.0.0.1`** — le sien, pas celui du Codespace. Ton `set_tracking_uri("http://127.0.0.1:5000")` ne trouvera donc rien depuis l'intérieur du conteneur. C'est exactement la même leçon que le tunnel SSH : `localhost` est toujours relatif à qui parle. On verra les options le moment venu.

---

Dis-moi si tu veux que j'en fasse un document que tu pourras garder et annoter.