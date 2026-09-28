# Module 06 — `model.py` et `lambda_function.py`, bloc par bloc

> Sources : [DataTalksClub/mlops-zoomcamp › 06-best-practices/code](https://github.com/DataTalksClub/mlops-zoomcamp/tree/main/06-best-practices/code) · version du module 4 pour comparaison : `04-deployment/streaming/lambda_function.py`.
> Ce cours se lit seul. Il approfondit le §2 de `cours-06-best-practices.md` (vue d'ensemble du module).
> État au 28/09/2026. Ce qui a été exécuté pour l'écrire, et ce qui ne l'a pas été : §13.
> Les numéros à gauche des extraits de code sont les numéros de ligne des fichiers d'origine.

---

## Le scénario

Une application de VTC envoie chaque nouvelle course (lieu de départ, lieu d'arrivée, distance) dans un flux de messages AWS, `ride_events`. Une fonction AWS Lambda lit ces messages, **prédit la durée** de chaque course avec le modèle entraîné aux modules précédents, et publie la prédiction dans un second flux, `ride_predictions`, où l'application la récupère. `lambda_function.py` et `model.py` sont le code de cette fonction.

---

## Réponses courtes (détails dans le cours)

**Pourquoi `get_model_location`, `load_model` et `base64_decode` sont hors des classes ?**
Aucune n'a besoin d'un état (`self`). Surtout, `ModelService` **reçoit** un modèle déjà chargé au lieu de le charger lui-même : le chargement se fait donc **avant** que l'objet existe, dans `init()`. Résultat : dans les tests, on donne à `ModelService` un faux modèle, sans MLflow ni S3. → §11.

**Comment `lambda_function.py` interagit avec `model.py` ?**
`lambda_function.py` est le **point d'entrée** qu'AWS Lambda appelle. Il lit la configuration (variables d'environnement), appelle **une fois** `model.init(...)`, qui fabrique un `ModelService` prêt à l'emploi, puis, à **chaque** événement, délègue à `model_service.lambda_handler(event)`. Toute la logique est dans `model.py`. → §10.

**Un callback ?** Une fonction qu'on **donne** à un objet pour qu'il l'**appelle plus tard**, au bon moment. → §6.

---

## Plan

**Partie I — Les notions**
1. AWS en bref
2. Kinesis Data Streams
3. AWS Lambda
4. Kinesis → Lambda : l'*event source mapping*
5. Rappels Python et outils du projet
6. Le callback

**Partie II — Le code**
7. Carte de `model.py`
8. `model.py` bloc par bloc
9. `lambda_function.py` ligne par ligne
10. Comment les deux fichiers interagissent
11. Pourquoi ces trois fonctions sont hors des classes
12. Pièges, points de doute, remarques d'expert
13. Ce qui a été vérifié, et comment
14. Vérifie-toi
15. Récapitulatif

---

# Partie I — Les notions

## 1. AWS en bref

**Le cloud** : au lieu d'acheter des serveurs, on loue des **services** (calcul, stockage, files de messages…) facturés à l'usage. **AWS** (*Amazon Web Services*) est le cloud d'Amazon.

| Notion | Ce que c'est | Dans ce code |
|---|---|---|
| **Région** | Un groupe de centres de données, ex. `eu-west-1` (Irlande). Chaque ressource vit dans une région. | `eu-west-1` |
| **Service** | Un produit AWS : S3, Kinesis, Lambda… Chacun se pilote par une **API** : des requêtes HTTPS. | Kinesis, Lambda, S3 |
| **S3** | Stockage de fichiers (*objets*) rangés dans des **buckets**. Adresse : `s3://bucket/chemin`. | Le modèle MLflow |
| **ARN** | *Amazon Resource Name* : l'identifiant unique d'une ressource, ex. `arn:aws:kinesis:eu-west-1:387546586013:stream/ride_events`. | Dans `event.json` |
| **IAM** | Qui a le droit de faire quoi. Un **rôle** est une identité qu'un service endosse (ici la Lambda). Une **policy** est la liste écrite de ses droits (« peut écrire dans tel flux »). | Droits de la Lambda sur Kinesis et S3 |
| **Identifiants** | Preuve d'identité jointe à chaque requête : une clé d'accès et une clé secrète. | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` |
| **CloudWatch Logs** | Les journaux. Tout `print` d'une Lambda y arrive. | Déboguer |

**Parler à AWS depuis Python : boto3**, le SDK (kit de développement) Python d'AWS.

```python
import boto3
client = boto3.client('kinesis')      # un objet qui sait parler au service Kinesis
client.put_record(...)                # → une requête HTTPS vers Kinesis
```

Un *client* a besoin de trois informations, qu'il cherche seul :

| Information | Où boto3 la trouve (version du module : boto3 1.24) |
|---|---|
| Région | Variable `AWS_DEFAULT_REGION`, ou fichier `~/.aws/config`. Sans région : erreur `NoRegionError` dès la création du client. |
| Identifiants | Variables `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`, ou fichier `~/.aws/credentials`. **Dans une Lambda**, AWS crée des identifiants temporaires à partir du rôle IAM et les place lui-même dans ces variables (plus un jeton de session). |
| Adresse du service (*endpoint*) | Par défaut, le vrai AWS de la région. Le paramètre `endpoint_url` la remplace, ex. `http://localhost:4566` pour **LocalStack** (§5.2). |

Retiens `endpoint_url` : c'est ce qui permet au **même code** de parler au vrai AWS ou à un faux (§8.10).

---

## 2. Kinesis Data Streams

« Kinesis » désigne plusieurs services AWS ; ici c'est **Kinesis Data Streams**.

### 2.1 L'idée

Un **flux** (*stream*) est un **journal de messages** : des programmes y écrivent, d'autres y lisent, **sans se connaître**.

```
producteur ──écrit──▶ [ flux ride_events ] ──lit──▶ consommateur
(appli VTC)             messages conservés          (notre Lambda)
                        24 h par défaut
```

Pourquoi pas un appel direct de l'appli vers la Lambda ? Le producteur n'attend pas le consommateur, et si le consommateur tombe, les messages l'attendent dans le flux pendant la **rétention**. C'est du **découplage**.

### 2.2 Le vocabulaire

| Terme | Définition | Ici |
|---|---|---|
| **Record** (message) | L'unité stockée : des **données** (des octets bruts, que Kinesis ne lit pas) + une **clé de partition** + un **numéro de séquence**. | Le JSON d'une course |
| **Shard** | Une « voie » du flux, de capacité fixe : en écriture 1 Mo/s ou 1 000 records/s ; en lecture 2 Mo/s. Plus de débit → plus de shards. | 2 par flux sur AWS (Terraform) ; 1 dans le test d'intégration |
| **Clé de partition** | Chaîne choisie par le producteur. Kinesis la **hache** (la passe dans la fonction MD5, qui transforme n'importe quel texte en un grand nombre, toujours le même pour le même texte) ; ce nombre désigne le shard. **Même clé → même shard.** | `str(ride_id)` |
| **Numéro de séquence** | Attribué par Kinesis à l'écriture. L'ordre n'a de sens **qu'à l'intérieur d'un shard**, jamais entre shards. | Visible dans `event.json` |
| **Rétention** | Durée de conservation : 24 h par défaut, jusqu'à 365 jours. | 48 h (Terraform) |
| **Producteur / consommateur** | Qui écrit / qui lit. | La Lambda est les deux : consommatrice de `ride_events`, productrice de `ride_predictions` |

### 2.3 Écrire et lire avec boto3

```python
# Écrire : ce que fait KinesisCallback (§8.9)
client.put_record(StreamName='ride_predictions',
                  Data='{"...": "..."}',        # str ou bytes
                  PartitionKey='256')

# Lire : ce que fait integration-test/test_kinesis.py pour vérifier la sortie
it = client.get_shard_iterator(StreamName='ride_predictions',
                               ShardId='shardId-000000000000',
                               ShardIteratorType='TRIM_HORIZON')['ShardIterator']
records = client.get_records(ShardIterator=it, Limit=1)['Records']
```

Lire demande un **itérateur de shard** : un curseur qui dit *où* lire. `TRIM_HORIZON` = depuis le plus ancien message conservé ; `LATEST` = seulement les nouveaux. Lus ainsi, les `Data` arrivent en **octets** déjà décodés (le base64 du §4.1 ne concerne que les événements Lambda).

---

## 3. AWS Lambda

### 3.1 L'idée

**Lambda** exécute **ta fonction** quand un événement arrive, sans serveur à gérer. Tu fournis le code ; AWS le lance, le multiplie si besoin, et facture le temps d'exécution.

| Terme | Définition | Ici |
|---|---|---|
| **Handler** | La fonction qu'AWS appelle. Signature imposée : `handler(event, context)`. | `lambda_function.lambda_handler` |
| **`event`** | Un dictionnaire : les données de l'événement. Sa forme dépend de la source. | Un lot de records Kinesis (§4) |
| **`context`** | Un objet d'informations sur l'exécution : `aws_request_id`, `function_name`, `memory_limit_in_mb`, `get_remaining_time_in_millis()`… | Inutilisé |
| **Image conteneur** | Le code peut être livré en image Docker (§5.2). La ligne `CMD ["lambda_function.lambda_handler"]` du `Dockerfile` désigne le handler : **module** `lambda_function`, **fonction** `lambda_handler`. | Oui |
| **Variables d'environnement** | Paramètres donnés à la fonction sans changer le code. | `RUN_ID`, `PREDICTIONS_STREAM_NAME`… |

### 3.2 Le cycle de vie : la clé pour comprendre `lambda_function.py`

Lambda exécute ton code dans un **environnement d'exécution** : un petit conteneur isolé, qui traite **une invocation à la fois** (mode standard) et qu'il **peut réutiliser** pour les suivantes.

**Premier événement : démarrage à froid (*cold start*)**

```
INIT     démarrer l'environnement
         importer lambda_function → exécuter tout le code HORS fonction
                                    (lire les variables, charger le modèle)
INVOKE   appeler lambda_handler(event, context)
GEL      l'environnement est mis en pause (freeze), gardé en mémoire
```

**Événements suivants, si l'environnement est réutilisé : démarrage à chaud (*warm start*)**

```
INVOKE   appeler lambda_handler(event, context)   ← le modèle est déjà chargé
GEL
```

Pendant le **gel**, ton code ne tourne pas, mais ses variables restent en mémoire. AWS finit par détruire l'environnement (au plus tard après quelques heures, ou s'il ne sert plus) ; le prochain événement repart alors par un INIT. D'où la règle :

- code **hors** du handler = exécuté **une fois** par environnement → y mettre ce qui est coûteux (charger le modèle, créer le client Kinesis) ;
- code **dans** le handler = exécuté **à chaque** événement → y mettre le traitement.

Deux précisions de la doc AWS :
- La phase INIT est limitée à **10 s**. Si elle dépasse, Lambda la recommence au premier appel, cette fois avec le délai maximal de la fonction (ici 180 s, fixé dans le Terraform).
- Lambda peut créer **plusieurs** environnements en parallèle (par exemple un par shard) : chacun fait son propre INIT.

---

## 4. Kinesis → Lambda : l'*event source mapping*

Kinesis n'appelle pas Lambda. C'est **Lambda qui interroge** (*poll*) chaque shard, environ une fois par seconde, via un objet de configuration appelé **event source mapping** (créé par Terraform, `modules/lambda/main.tf`). Il appelle ensuite la fonction de façon **synchrone** : il attend sa réponse (réussite ou erreur) avant de passer au lot suivant du shard.

```
[ride_events] ◀─interroge── event source mapping ──appelle avec un LOT──▶ lambda_handler(event, context)
```

### 4.1 La forme de `event`

Lambda regroupe les records en **lot** (*batch*) : **jusqu'à** 100 par défaut (réglable jusqu'à 10 000), souvent moins, **tous issus du même shard**. Extrait de `integration-test/event.json` :

```json
{
  "Records": [
    {
      "kinesis": {
        "partitionKey": "1",
        "sequenceNumber": "4963008166608487929058...",
        "data": "ewogICAgICAgICJyaWRlIjogewog...",
        "approximateArrivalTimestamp": 1654161514.132
      },
      "eventSource": "aws:kinesis",
      "eventSourceARN": "arn:aws:kinesis:eu-west-1:387546586013:stream/ride_events"
    }
  ]
}
```

- `event['Records']` : une **liste**, d'où la boucle `for` du code.
- `data` est en **base64**. Pourquoi ? Les données d'un record sont des **octets bruts** ; or `event` est du JSON, qui ne transporte que du texte. Le base64 écrit n'importe quels octets avec 64 caractères sûrs (`A-Z a-z 0-9 + /`). Décodé, ce `data` donne :

```json
{"ride": {"PULocationID": 130, "DOLocationID": 205, "trip_distance": 3.66}, "ride_id": 256}
```

### 4.2 Et si la fonction plante ?

Par défaut, si le handler lève une erreur, Lambda **réessaie tout le lot**, sans limite, jusqu'à ce que les records expirent (fin de la rétention), et **n'avance plus sur ce shard** pendant ce temps. Réglages de l'event source mapping qui changent cela :

| Réglage | Effet |
|---|---|
| `MaximumRetryAttempts` | Nombre maximal de réessais (défaut : infini) |
| `MaximumRecordAgeInSeconds` | Abandonner les records trop vieux (défaut : jamais avant la rétention) |
| `BisectBatchOnFunctionError` | Couper le lot en deux pour isoler le record fautif |
| Destination en cas d'échec (`OnFailure`) | Garder une trace des records abandonnés (dans une file SQS, un sujet SNS ou S3) |

Le Terraform du module n'en règle aucun (§12).

### 4.3 La valeur renvoyée

Avec Kinesis, Lambda **ne fait rien** de ce que renvoie le handler (sauf si l'option `ReportBatchItemFailures` est activée : le handler peut alors indiquer quels records ont échoué ; ce n'est pas le cas ici). Le résultat utile part par `put_record`. Le `return` sert aux **tests**.

---

## 5. Rappels Python et outils du projet

### 5.1 Python

| Notion | En une ligne | Exemple |
|---|---|---|
| **Module** | Un fichier `.py`. `import model` exécute `model.py` **une seule fois** puis le garde en mémoire ; un 2ᵉ `import` ne ré-exécute rien. | `import model` → `model.init(...)` |
| **Variable d'environnement** | Paire nom=valeur fournie au processus par le système. `os.getenv('X', 'défaut')` renvoie une **chaîne**, ou le défaut (ou `None`) si `X` est absente. | `os.getenv('RUN_ID')` |
| **`is not None`** | Teste si une valeur existe (≠ `None`). | `if model_location is not None:` |
| **f-string** | Chaîne où `{…}` est remplacé par une valeur. Attention : `f'{None}'` donne `'None'`. | `f"{a}_{b}"` → `'130_205'` |
| **Accès dictionnaire** | `d['clé']`, qui s'enchaîne. Clé absente → erreur `KeyError`. | `record['kinesis']['data']` |
| **`a or b`** | Renvoie `a` s'il est « vrai », sinon `b`. `None`, `[]`, `''`, `0` sont « faux ». | `None or []` → `[]` |
| **Classe, objet** | Une classe est un moule ; un objet (instance) est fabriqué avec. `__init__` s'exécute à la fabrication. | `ModelService(model=m)` |
| **`self`** | L'objet lui-même, passé automatiquement à chaque méthode. `self.x = …` range une donnée **dans** l'objet : c'est son **état**. | `self.model` |
| **Fonction = objet** | Une fonction est une valeur : on peut la ranger dans une variable ou une liste **sans l'appeler** (pas de parenthèses). | `f = print` puis `f('hi')` |
| **Constante** | Nom en MAJUSCULES : par convention, la valeur ne change plus après le démarrage. | `RUN_ID` |
| **Annotation de type** | `x: str` documente le type attendu. Python ne le vérifie pas. | `run_id: str` |

### 5.2 Les outils cités dans ce cours

| Outil | En une ligne |
|---|---|
| **Docker, image, conteneur** | Une image emballe une application et tout son environnement ; une image lancée est un conteneur. |
| **docker-compose** | Lance plusieurs conteneurs décrits dans un fichier YAML, sur un réseau commun où chacun est joignable par son **nom de service** (ex. `kinesis`). « Monter » un dossier = le rendre visible dans le conteneur. |
| **LocalStack** | Un faux AWS dans un conteneur, qui répond sur le port 4566. |
| **RIE** | *Runtime Interface Emulator* : un petit serveur inclus dans l'image Lambda officielle ; un `POST` HTTP sur le port 8080 déclenche le handler, comme le ferait Lambda. |
| **Test unitaire** | Vérifie un morceau de code isolé, sans réseau, en millisecondes (ici `pytest tests/`, fichier `tests/model_test.py`). |
| **Mock** | Faux objet qui imite un vrai. Ici `ModelMock`, un faux modèle (§8.5). |
| **Test d'intégration** | Lance le vrai conteneur et le teste de l'extérieur (ici `integration-test/run.sh`, qui démarre le service + LocalStack avec docker-compose). |
| **pylint, isort** | pylint lit le code sans l'exécuter et signale erreurs et mauvaises pratiques ; isort trie les imports. |
| **Terraform** | Décrit l'infrastructure AWS (flux, Lambda, droits…) dans des fichiers `.tf` et la crée (`terraform apply`). |
| **`scripts/deploy_manual.sh`** | Script du module qui choisit le `RUN_ID` du modèle et le donne à la Lambda (§10.3). |

---

## 6. Le callback

### 6.1 Définition

Un **callback** (« rappel ») est une fonction que tu **passes** à un autre code, pour que **ce code l'appelle** au moment voulu.

Analogie : chez le cordonnier, tu laisses une fiche : « quand c'est prêt, déposez-les chez ma gardienne ». Le cordonnier ne sait pas qui est ta gardienne et n'a pas besoin de le savoir ; il sait seulement qu'à la fin, il exécute la fiche. La fiche est le callback.

- Celui qui **écrit** le callback décide **quoi** faire (déposer chez la gardienne).
- Celui qui **l'appelle** décide **quand** (quand c'est prêt).

### 6.2 Exemple minimal

```python
def afficher(resultat):                  # un callback possible
    print("Résultat :", resultat)

def calculer(x, callbacks):              # le code qui appellera les callbacks
    r = x * 2
    for cb in callbacks:
        cb(r)                            # « je te rappelle avec le résultat »
    return r

calculer(21, callbacks=[afficher])       # affiche "Résultat : 42"
calculer(21, callbacks=[])               # n'affiche rien, calcule quand même
```

`calculer` ignore ce que font ses callbacks : afficher, écrire dans un fichier, publier dans Kinesis… C'est tout l'intérêt.

### 6.3 Une méthode comme callback : la *méthode liée*

```python
class Sonnette:
    def __init__(self, son):
        self.son = son
    def sonner(self, message):
        print(self.son, message)

s = Sonnette("Ding !")
cb = s.sonner              # sans () : on prend la méthode, on ne l'appelle pas
cb("colis arrivé")         # équivaut à s.sonner("colis arrivé") → "Ding ! colis arrivé"
```

`s.sonner` est une **méthode liée** (*bound method*) : elle **emporte son objet** `s`. Quand on l'appelle plus tard, `self` vaut `s` automatiquement. C'est exactement ce que fait `init()` avec `kinesis_callback.put_record` (§8.11) : le callback emporte avec lui le client Kinesis et le nom du flux.

### 6.4 Pourquoi un callback ici

Au module 4, tout était mêlé dans un seul fichier : l'import créait un client Kinesis et chargeait le modèle depuis S3, et la publication était écrite **dans** le handler :

```python
if not TEST_RUN:
    kinesis_client.put_record(...)        # Kinesis codé en dur dans la logique
```

Au module 6, `ModelService` dit seulement : « pour chaque prédiction, j'appelle les fonctions de ma liste ». Conséquences :

| | Module 4 | Module 6 |
|---|---|---|
| Tester la logique sans AWS | Impossible : importer le fichier exige une région AWS et lit S3, même avec `TEST_RUN=True` | Faux modèle + liste de callbacks vide |
| Ajouter une sortie (log, base de monitoring…) | Modifier le handler | Ajouter une fonction à la liste |
| La logique connaît Kinesis ? | Oui | **Non** |

---

# Partie II — Le code

## 7. Carte de `model.py`

`model.py` contient quatre familles de pièces :

```
PRÉPARER les ingrédients    get_model_location, load_model      (le modèle)
                            create_kinesis_client               (le client Kinesis)
LOGIQUE                     base64_decode                       (décoder un record)
                            ModelService                        (features → prédiction → callbacks)
SORTIE                      KinesisCallback                     (publier une prédiction)
ASSEMBLER                   init                                (fabriquer un ModelService prêt)
```

Qui appelle qui :

```
init(prediction_stream_name, run_id, test_run)            ← une fois
 ├─ load_model(run_id)
 │    ├─ get_model_location(run_id)  → chemin
 │    └─ mlflow.pyfunc.load_model(chemin)  → modèle
 ├─ si non test_run :
 │    ├─ create_kinesis_client()  → client
 │    ├─ KinesisCallback(client, nom_du_flux)
 │    └─ callbacks = [kinesis_callback.put_record]
 └─ ModelService(model, model_version=run_id, callbacks)  → renvoyé

ModelService.lambda_handler(event)                        ← à chaque événement
 └─ pour chaque record :
      base64_decode → prepare_features → predict → chaque callback → liste de résultats
```

Un piège de nom : dans `lambda_function.py`, `model` désigne le **module** `model.py` ; dans `model.py`, `model` désigne l'**objet modèle ML** chargé par MLflow.

---

## 8. `model.py` bloc par bloc

### 8.1 Imports (l. 1-6)

```python
  1  import os
  2  import json
  3  import base64
  4
  5  import boto3
  6  import mlflow
```

- `os` lit les variables d'environnement ; `json` convertit texte JSON ⇄ dictionnaire ; `base64` décode le champ `data` des records ; `boto3` parle à Kinesis ; `mlflow` charge le modèle.
- Bibliothèque standard d'abord, bibliothèques installées ensuite, séparées par une ligne vide : convention appliquée par isort. L'ordre `os`, `json`, `base64` n'est pas alphabétique : `pyproject.toml` demande à isort de trier **par longueur** (`length_sort = true`).

### 8.2 `get_model_location` (l. 9-19) — *où est le modèle ?*

```python
  9  def get_model_location(run_id):
 10      model_location = os.getenv('MODEL_LOCATION')
 11
 12      if model_location is not None:
 13          return model_location
 14
 15      model_bucket = os.getenv('MODEL_BUCKET', 'mlflow-models-alexey')
 16      experiment_id = os.getenv('MLFLOW_EXPERIMENT_ID', '1')
 17
 18      model_location = f's3://{model_bucket}/{experiment_id}/{run_id}/artifacts/model'
 19      return model_location
```

| Lignes | Ce qui se passe |
|---|---|
| 10-13 | Si `MODEL_LOCATION` est définie, on l'utilise telle quelle. C'est le cas du test d'intégration : `MODEL_LOCATION=/app/model`, un dossier monté dans le conteneur → pas besoin de S3. |
| 15-16 | Sinon, on lit le bucket et l'ID d'expérience MLflow, avec des valeurs par défaut (le bucket de l'auteur du cours, l'expérience `1`). |
| 18 | On reconstruit le chemin où MLflow range les artefacts d'un *run* quand son stockage est S3 : `s3://bucket/<expérience>/<run_id>/artifacts/model`. |

Principe : **la configuration vient de l'extérieur** ; le même code sert en local et sur AWS.

Si `RUN_ID` manque, la fonction renvoie `s3://mlflow-models-alexey/1/None/artifacts/model` (le `None` devient du texte, §5.1) → le chargement échouera.

### 8.3 `load_model` (l. 22-25) — *charger le modèle*

```python
 22  def load_model(run_id):
 23      model_path = get_model_location(run_id)
 24      model = mlflow.pyfunc.load_model(model_path)
 25      return model
```

`mlflow.pyfunc.load_model` accepte un dossier local ou un chemin `s3://…` et renvoie un objet `PyFuncModel`, qui offre une méthode `.predict()` quelle que soit la bibliothèque d'origine. Derrière, ici : un pipeline scikit-learn `DictVectorizer` + `RandomForestRegressor`.

### 8.4 `base64_decode` (l. 28-31) — *record Kinesis → dictionnaire*

```python
 28  def base64_decode(encoded_data):
 29      decoded_data = base64.b64decode(encoded_data).decode('utf-8')
 30      ride_event = json.loads(decoded_data)
 31      return ride_event
```

Trois transformations :

```
"ewogICAg..."  ─b64decode─▶  b'{"ride": ...}'  ─.decode("utf-8")─▶  '{"ride": ...}'  ─json.loads─▶  {'ride': {...}, 'ride_id': 256}
 texte base64                octets (bytes)                         texte (str)                    dictionnaire
```

Fonction **pure** : même entrée → même sortie, rien d'autre modifié. C'est la plus facile à tester (`test_base64_decode`).

### 8.5 `ModelService.__init__` (l. 34-38) — *le constructeur*

```python
 34  class ModelService:
 35      def __init__(self, model, model_version=None, callbacks=None):
 36          self.model = model
 37          self.model_version = model_version
 38          self.callbacks = callbacks or []
```

| Ligne | Rôle |
|---|---|
| 35 | Trois paramètres : le modèle (**obligatoire**), sa version et la liste de callbacks (facultatifs). |
| 36 | Le modèle est **reçu**, pas chargé ici. C'est l'**injection de dépendances** : on donne à l'objet ses outils au lieu qu'il les fabrique. |
| 37 | La version (le `run_id`) sera recopiée dans chaque prédiction : on saura quel modèle l'a produite. |
| 38 | `callbacks or []` : si on ne passe rien (`None`) ou une liste vide, on obtient une liste vide neuve. |

L'injection de dépendances en pratique : voici le faux modèle de `tests/model_test.py`.

```python
class ModelMock:
    def __init__(self, value):
        self.value = value
    def predict(self, X):
        return [self.value] * len(X)       # renvoie toujours la même valeur

model_service = model.ModelService(ModelMock(10.0))   # prédira toujours 10.0
```

`ModelService` ne voit pas la différence : il appelle `.predict()`, c'est tout ce qu'il demande. Un test peut même écrire `ModelService(None)` quand il n'a pas besoin de modèle (`test_prepare_features`).

Pourquoi pas `callbacks=[]` directement dans la signature ? En Python, une valeur par défaut est créée **une seule fois**, à la définition de la fonction : tous les objets partageraient **la même** liste, et ajouter un callback à l'un l'ajouterait à tous. `None` + `or []` crée une liste neuve à chaque fois. C'est un piège Python classique.

### 8.6 `prepare_features` (l. 40-44) — *course → features*

```python
 40      def prepare_features(self, ride):
 41          features = {}
 42          features['PU_DO'] = f"{ride['PULocationID']}_{ride['DOLocationID']}"
 43          features['trip_distance'] = ride['trip_distance']
 44          return features
```

Transforme la course brute en **features** attendues par le modèle, celles du module 1 : la combinaison départ_arrivée (`'130_205'`) et la distance. Cette méthode n'utilise pas `self` (§11.4).

### 8.7 `predict` (l. 46-48) — *features → nombre*

```python
 46      def predict(self, features):
 47          pred = self.model.predict(features)
 48          return float(pred[0])
```

| Ligne | Rôle |
|---|---|
| 47 | Le modèle reçoit **un** dictionnaire (le `DictVectorizer` du pipeline l'accepte seul) et renvoie un tableau numpy d'**une** valeur, ex. `array([21.29])`. |
| 48 | `pred[0]` prend cette valeur ; `float(...)` la convertit en nombre Python ordinaire, publiable en JSON quel que soit le type numpy renvoyé par le modèle. |

### 8.8 `ModelService.lambda_handler` (l. 50-77) — *le cœur*

```python
 50      def lambda_handler(self, event):
 51          # print(json.dumps(event))
 52
 53          predictions_events = []
 54
 55          for record in event['Records']:
 56              encoded_data = record['kinesis']['data']
 57              ride_event = base64_decode(encoded_data)
 58
 59              # print(ride_event)
 60              ride = ride_event['ride']
 61              ride_id = ride_event['ride_id']
 62
 63              features = self.prepare_features(ride)
 64              prediction = self.predict(features)
 65
 66              prediction_event = {
 67                  'model': 'ride_duration_prediction_model',
 68                  'version': self.model_version,
 69                  'prediction': {'ride_duration': prediction, 'ride_id': ride_id},
 70              }
 71
 72              for callback in self.callbacks:
 73                  callback(prediction_event)
 74
 75              predictions_events.append(prediction_event)
 76
 77          return {'predictions': predictions_events}
```

| Lignes | Rôle |
|---|---|
| 51, 59 | `print` commentés : aides au débogage (leur sortie irait dans CloudWatch). |
| 53 | Liste qui accumulera les résultats du lot. |
| 55 | Un événement = un **lot** : on traite chaque record. |
| 56-57 | Extraire `data`, le décoder (§8.4). |
| 60-61 | Séparer la course de son identifiant. |
| 63-64 | Features, puis prédiction. |
| 66-70 | Construire le **message de sortie** : nom du modèle, version, prédiction et `ride_id`, pour que le consommateur sache **à quelle course** correspond la prédiction. |
| 72-73 | **Appeler chaque callback** avec ce message. En production : un seul, qui publie dans Kinesis. En test : aucun. |
| 75, 77 | Garder le message, et tout renvoyer à la fin (utile aux tests, ignoré par Lambda, §4.3). |

Exécuté avec le vrai modèle et un lot de deux courses :

```
entrée  : course 256 (130→205, 3.66 miles) ; course 257 (43→151, 1.0 mile)
retour  : ride_duration 21.29 (course 256) ; 14.83 (course 257)
flux ride_predictions : 2 records, clés de partition '256' et '257'
```

Cette méthode porte le **même nom** que le handler de `lambda_function.py`, mais **n'est pas** le handler AWS : elle ne prend pas `context`. `lambda_function.lambda_handler` lui passe le relais.

### 8.9 `KinesisCallback` (l. 80-92) — *publier une prédiction*

```python
 80  class KinesisCallback:
 81      def __init__(self, kinesis_client, prediction_stream_name):
 82          self.kinesis_client = kinesis_client
 83          self.prediction_stream_name = prediction_stream_name
 84
 85      def put_record(self, prediction_event):
 86          ride_id = prediction_event['prediction']['ride_id']
 87
 88          self.kinesis_client.put_record(
 89              StreamName=self.prediction_stream_name,
 90              Data=json.dumps(prediction_event),
 91              PartitionKey=str(ride_id),
 92          )
```

| Lignes | Rôle |
|---|---|
| 81-83 | Ranger le client et le nom du flux **dans l'objet** : l'état dont `put_record` aura besoin. |
| 85 | La méthode prend **un seul** argument, le message : c'est la forme qu'attend `ModelService` (`callback(prediction_event)`). |
| 86 | `ride_id` servira de clé de partition. |
| 88-92 | Appel boto3 : quel flux, quelles données (le dictionnaire converti en texte JSON), quelle clé (une **chaîne**, d'où `str`). |

Pourquoi une classe ? Le callback a besoin du client et du nom du flux, mais `ModelService` ne lui passe que le message. L'objet **transporte** ces deux informations ; la méthode liée `kinesis_callback.put_record` les emporte avec elle (§6.3).

Pourquoi `ride_id` comme clé ? Il y a une prédiction par course : la clé sert surtout à **répartir** les prédictions entre les shards (des identifiants variés se répartissent à peu près uniformément).

### 8.10 `create_kinesis_client` (l. 95-101) — *vrai AWS ou faux ?*

```python
 95  def create_kinesis_client():
 96      endpoint_url = os.getenv('KINESIS_ENDPOINT_URL')
 97
 98      if endpoint_url is None:
 99          return boto3.client('kinesis')
100
101      return boto3.client('kinesis', endpoint_url=endpoint_url)
```

- Pas de `KINESIS_ENDPOINT_URL` → vrai Kinesis (région et identifiants trouvés par boto3, §1).
- Variable définie → le client parle à cette adresse. Dans `docker-compose.yaml` : `http://kinesis:4566/`, le conteneur LocalStack (`kinesis` est son nom de service Docker).

### 8.11 `init` (l. 104-116) — *l'assemblage*

```python
104  def init(prediction_stream_name: str, run_id: str, test_run: bool):
105      model = load_model(run_id)
106
107      callbacks = []
108
109      if not test_run:
110          kinesis_client = create_kinesis_client()
111          kinesis_callback = KinesisCallback(kinesis_client, prediction_stream_name)
112          callbacks.append(kinesis_callback.put_record)
113
114      model_service = ModelService(model=model, model_version=run_id, callbacks=callbacks)
115
116      return model_service
```

| Lignes | Rôle |
|---|---|
| 105 | Charger le modèle — **toujours**, même en `test_run`. |
| 107 | Liste de callbacks, vide au départ. |
| 109-112 | Hors mode test : créer le client, l'objet `KinesisCallback`, et ajouter **sa méthode liée** `put_record` (sans parenthèses : on range la fonction, on ne l'appelle pas). |
| 114 | Fabriquer le `ModelService` avec ses trois ingrédients ; la version est le `run_id`. |

`init` est le **seul** endroit qui connaît à la fois MLflow, Kinesis et `ModelService`.

Résultat : avec `TEST_RUN=True`, `model_service.callbacks` vaut `[]` ; sinon `[<bound method KinesisCallback.put_record of <model.KinesisCallback object …>>]`.

---

## 9. `lambda_function.py` ligne par ligne

```python
  1  import os
  2
  3  import model
  4
  5  PREDICTIONS_STREAM_NAME = os.getenv('PREDICTIONS_STREAM_NAME', 'ride_predictions')
  6  RUN_ID = os.getenv('RUN_ID')
  7  TEST_RUN = os.getenv('TEST_RUN', 'False') == 'True'
  8
  9
 10  model_service = model.init(
 11      prediction_stream_name=PREDICTIONS_STREAM_NAME,
 12      run_id=RUN_ID,
 13      test_run=TEST_RUN,
 14  )
 15
 16
 17  def lambda_handler(event, context):
 18      # pylint: disable=unused-argument
 19      return model_service.lambda_handler(event)
```

| Ligne | Quand | Rôle |
|---|---|---|
| 3 | INIT | Importe `model.py` (qui importe mlflow, boto3… : c'est lent). |
| 5 | INIT | Nom du flux de sortie, `'ride_predictions'` par défaut. |
| 6 | INIT | Le `run_id` MLflow. **Pas de défaut** → `None` s'il manque. |
| 7 | INIT | `os.getenv` renvoie une chaîne ; `== 'True'` en fait un booléen. Seul `'True'` exact donne `True` (`'true'` donne `False`). |
| 10-14 | INIT | Fabrique le `ModelService` **une fois**. Il reste en mémoire pour les appels suivants (§3.2). |
| 17 | INVOKE | Le handler AWS, signature imposée `(event, context)`. |
| 18 | — | `context` est imposé mais inutilisé ; ce commentaire, placé en première ligne du corps, fait taire l'avertissement de pylint pour toute la fonction. |
| 19 | INVOKE | Délègue à la méthode de `ModelService` et renvoie son résultat. |

---

## 10. Comment les deux fichiers interagissent

### 10.1 Répartition des rôles

| `lambda_function.py` | `model.py` |
|---|---|
| **Adaptateur** entre AWS Lambda et le code | La **logique** et les pièces |
| Lit la configuration (nom du flux, `RUN_ID`, `TEST_RUN`) | La reçoit en paramètres de `init` ; lit lui-même l'emplacement du modèle et l'adresse Kinesis |
| Appelle `model.init` une fois | Fabrique et renvoie le `ModelService` |
| Reçoit `(event, context)`, transmet `event` | Traite le lot, publie, renvoie |
| 19 lignes, **pas de test unitaire** | Testé par `tests/model_test.py` |

Pourquoi garder `lambda_function.py` aussi mince ? L'importer **déclenche** le chargement du modèle (ligne 10). Les tests unitaires n'importent donc que `model` : ils fabriquent un `ModelService` avec un faux modèle, sans variable d'environnement ni réseau.

### 10.2 Chronologie sur AWS

```
① INIT (1ᵉʳ événement dans un nouvel environnement)
   Lambda lance l'image, importe lambda_function
   ├─ lit PREDICTIONS_STREAM_NAME, RUN_ID, TEST_RUN
   └─ model.init(...)
        ├─ load_model → get_model_location → s3://…/<run_id>/artifacts/model → modèle
        ├─ create_kinesis_client → client (vrai AWS)
        ├─ KinesisCallback(client, 'stg_ride_predictions-mlops-zoomcamp')
        └─ ModelService(model, run_id, [kinesis_callback.put_record])  →  model_service

② INVOKE (chaque lot lu dans ride_events)
   lambda_function.lambda_handler(event, context)
   └─ model_service.lambda_handler(event)
        └─ pour chaque record : base64_decode → prepare_features → predict
                                → kinesis_callback.put_record → ride_predictions

③ Lot suivant : si l'environnement est réutilisé → directement ②
```

### 10.3 Trois contextes, un même code

| Contexte | Qui joue le rôle de Lambda | `lambda_function.py` utilisé ? | Publication |
|---|---|---|---|
| **Tests unitaires** | Personne : le test appelle `ModelService` directement | Non | Aucune (pas de callback) |
| **Test d'intégration** | Le RIE (§5.2) : `test_docker.py` envoie `event.json` en `POST` ; la valeur de retour du handler revient en réponse HTTP | Oui | Vers LocalStack ; `test_kinesis.py` relit le flux |
| **AWS** | Lambda + event source mapping | Oui | Vers le vrai flux |

D'un contexte à l'autre, **seules les variables d'environnement changent**. Lis ce tableau colonne par colonne :

| Variable | Lue par | Défaut | Test d'intégration (`docker-compose.yaml`) | AWS |
|---|---|---|---|---|
| `PREDICTIONS_STREAM_NAME` | `lambda_function` l. 5 | `ride_predictions` | `ride_predictions` (fixé par `run.sh`) | `stg_ride_predictions-mlops-zoomcamp` (Terraform) |
| `RUN_ID` | `lambda_function` l. 6 | `None` | `Test123` | ajouté par `deploy_manual.sh` |
| `TEST_RUN` | `lambda_function` l. 7 | `False` | absent → `False` | absent → `False` |
| `MODEL_LOCATION` | `get_model_location` | `None` | `/app/model` | absent |
| `MODEL_BUCKET` | `get_model_location` | `mlflow-models-alexey` | ignoré (`MODEL_LOCATION` prime) | bucket créé par Terraform |
| `MLFLOW_EXPERIMENT_ID` | `get_model_location` | `1` | ignoré | absent → `1` |
| `KINESIS_ENDPOINT_URL` | `create_kinesis_client` | `None` | `http://kinesis:4566/` (LocalStack) | absent → vrai AWS |
| Région, identifiants | boto3 | — | `eu-west-1`, `abc`/`xyz` (factices, acceptés par LocalStack) | fournis par Lambda (rôle IAM) |

Sur AWS, `deploy_manual.sh` (l. 22-25) **remplace l'ensemble** des variables de la Lambda (c'est le comportement de `aws lambda update-function-configuration --environment`) : c'est pourquoi il redonne aussi `PREDICTIONS_STREAM_NAME` et `MODEL_BUCKET`.

`test_run=True` sert à un 4ᵉ cas : lancer l'image seule, sans aucun Kinesis (commandes `docker run … -e TEST_RUN="True"` du `README.md` du module).

---

## 11. Pourquoi ces trois fonctions sont hors des classes

L'auteur ne l'explique pas dans le code ; voici les raisons que le code permet d'établir.

### 11.1 La règle de départ

En Python, contrairement à Java, **rien n'oblige** à tout mettre dans une classe. On crée une classe quand des **données** (un état) et des **opérations sur ces données** vont ensemble. Une fonction qui n'a besoin d'aucun état peut rester une fonction de module.

### 11.2 `get_model_location` et `load_model` : elles fabriquent un ingrédient de `ModelService`

C'est l'argument technique le plus solide. `ModelService` **reçoit** son modèle (l. 36). Pour le lui donner, il faut l'avoir chargé **avant** de créer l'objet. Ces deux fonctions travaillent donc **en amont**, appelées par `init`.

Contre-exemple, si le chargement était dans le constructeur :

```python
class ModelService:
    def __init__(self, run_id):
        self.model = mlflow.pyfunc.load_model(f's3://…/{run_id}/…')   # à éviter
```

**Chaque** test qui crée un `ModelService` tenterait alors de lire S3 : lent, dépendant du réseau et d'un compte AWS. Avec la version réelle, le test écrit simplement `model.ModelService(ModelMock(10.0))` (§8.5).

Nuance : ce raisonnement prouve que le chargement ne doit pas être dans `__init__`, pas qu'il doit être hors de la classe. Une « méthode de fabrication » attachée à la classe (`@classmethod`, ex. `ModelService.from_run_id(run_id)`) conserverait le même avantage. Le choix de simples fonctions relève donc aussi du style : c'est le plus simple.

Même logique pour `create_kinesis_client` et `KinesisCallback` : ce sont des pièces d'**infrastructure**, gardées hors de `ModelService` pour qu'il ne dépende ni de MLflow, ni de S3, ni de Kinesis.

### 11.3 `base64_decode` : une fonction pure

Elle ne dépend ni du modèle, ni de la version, ni des callbacks : texte base64 → dictionnaire. Hors classe, elle se teste sans rien construire (`model.base64_decode(...)`) et pourrait servir ailleurs, par exemple dans un script qui relit un flux. Elle **aurait pu** être une méthode : c'est un choix de style, pas une obligation.

### 11.4 La nuance : `prepare_features`

`prepare_features` n'utilise **pas** `self` non plus : pylint le confirme si on active son contrôle optionnel `no-self-use` (« Method could be a function »). La frontière n'est donc pas une règle stricte.

**Interprétation, non confirmée par l'auteur** : la préparation des features fait partie du « contrat » du modèle (un autre modèle attendrait d'autres features) ; elle vit donc avec le service qui utilise ce modèle. `base64_decode`, elle, dépend du format de **Kinesis**, pas du modèle.

---

## 12. Pièges, points de doute, remarques d'expert

### 12.1 Pièges (vérifiés en exécutant le code)

| Endroit | Piège |
|---|---|
| `lambda_function.py` l. 6 + `get_model_location` | Sans `RUN_ID`, le chemin contient `None` → le chargement du modèle échoue pendant l'INIT. Sur AWS, un INIT raté fait échouer **chaque** invocation ; avec les réessais infinis par défaut (§4.2), le shard reste bloqué jusqu'à la fin de la rétention (48 h). Le Terraform crée la Lambda sans `RUN_ID` : c'est `deploy_manual.sh` qui l'ajoute. |
| `lambda_function.py` l. 7 | `TEST_RUN=true` (minuscule) → `False` : la Lambda publiera. |
| `init` l. 105 | `test_run=True` n'évite **pas** le chargement du modèle : il faut quand même `MODEL_LOCATION` ou un `RUN_ID` valide. |
| `lambda_handler` l. 55-75 | Si un record du lot est invalide (JSON cassé, clé manquante), l'exception fait échouer **tout** le lot. Les prédictions des records précédents sont **déjà publiées** ; elles le seront **à nouveau à chaque réessai** → doublons dans `ride_predictions`. Lambda garantit « au moins une fois », pas « exactement une fois ». |

### 12.2 Points de doute (non vérifiés sur AWS)

1. **Mémoire.** Le Terraform ne fixe pas `memory_size` → 128 Mo par défaut. Mesuré en local : le processus Python atteint environ 140 Mo juste après `import lambda_function`. Risque probable d'erreur de mémoire sur AWS ; si c'est le cas, CloudWatch le dira, et `memory_size = 512` dans `modules/lambda/main.tf` est la correction habituelle.
2. **`terraform apply` après `deploy_manual.sh`.** Terraform gère le bloc `environment` de la Lambda, qui ne contient pas `RUN_ID` : un nouvel `apply` le supprimerait probablement. Non testé.
3. **Pourquoi l'auteur a laissé `prepare_features` dans la classe** : §11.4 est une interprétation.

### 12.3 Remarques d'expert (hors périmètre)

- `modules/lambda/main.tf` contient `maximum_retry_attempts = 0`, mais dans `aws_lambda_function_event_invoke_config`, qui règle les invocations **asynchrones** (où l'appelant n'attend pas la réponse). Il ne concerne pas l'event source mapping Kinesis, qui appelle la fonction de façon synchrone.
- Un appel `put_record` par prédiction : pour de gros lots, `put_records` (jusqu'à 500 records par appel) fait beaucoup moins de requêtes, mais il peut échouer **partiellement** : il faut lire `FailedRecordCount` et renvoyer les records refusés.
- Aucune gestion d'erreur par record : en production, on isole les records invalides (journalisés, ou envoyés dans une file de rebut, *dead-letter queue*) au lieu de faire échouer le lot, ou on active `BisectBatchOnFunctionError` / `ReportBatchItemFailures`.
- `ModelMock.predict` renvoie `[10.0, 10.0]` pour un seul dictionnaire, car `len(X)` compte ses **deux clés**. Le test passe quand même grâce au `pred[0]`.

---

## 13. Ce qui a été vérifié, et comment

- **Exécuté** en Python 3.9 avec les versions du `Pipfile.lock` (mlflow 1.27.0, boto3 1.24.21, scikit-learn 1.0.2, pylint 2.14.4), sur le modèle de `integration-test/model/` : les 4 tests unitaires, `lambda_function` avec `TEST_RUN=True` puis `False`, le lot de deux courses (§8.8), le chemin `None` (§8.2), `NoRegionError` sans `AWS_DEFAULT_REGION`, le piège de la liste par défaut, le contrôle `no-self-use`, la mémoire après import (§12.2).
- **Kinesis simulé** avec **moto**, une bibliothèque qui imite AWS à l'intérieur du processus Python. **Non testé** : vrai AWS, LocalStack.
- **Relu** par deux agents : un étudiant débutant (compréhension, angle pédagogique) et un expert (exactitude, avec exécution du code).
- **Documentation AWS** :
  - [Lambda + Kinesis Data Streams](https://docs.aws.amazon.com/lambda/latest/dg/with-kinesis.html) — lecture par lots d'un shard, invocation synchrone, `data` en base64.
  - [Records rejetés d'un lot Kinesis](https://docs.aws.amazon.com/lambda/latest/dg/kinesis-on-failure-destination.html) — réessais par défaut, blocage du shard, réglages.
  - [CreateEventSourceMapping](https://docs.aws.amazon.com/lambda/latest/api/API_CreateEventSourceMapping.html) — taille de lot, `LATEST` / `TRIM_HORIZON`.
  - [Cycle de vie de l'environnement d'exécution](https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtime-environment.html) — INIT, 10 s, réutilisation non garantie.
  - [Objet `context` en Python](https://docs.aws.amazon.com/lambda/latest/dg/python-context.html)
  - [Concepts de Kinesis Data Streams](https://docs.aws.amazon.com/streams/latest/dev/key-concepts.html) — shard, clé de partition, rétention, capacité.

---

## 14. Vérifie-toi

<details><summary>1. On déplace <code>model_service = model.init(...)</code> à l'intérieur de <code>lambda_handler</code>. Le code marche-t-il encore ? Qu'est-ce qui change ?</summary>
Il marche, mais le modèle est rechargé (depuis S3) et le client Kinesis recréé à chaque lot : chaque invocation devient lente et coûteuse. Hors du handler, c'est fait une fois par environnement (INIT).
</details>

<details><summary>2. Un lot contient 5 records ; le 3ᵉ a un JSON cassé. Que se passe-t-il, record par record, puis au réessai ?</summary>
Records 1 et 2 : prédits et publiés. Record 3 : exception, le lot échoue, 4 et 5 ne sont pas traités. Lambda réessaie tout le lot : 1 et 2 sont republiés (doublons), le 3 plante encore… jusqu'à expiration des records, le shard étant bloqué pendant ce temps.
</details>

<details><summary>3. Pourquoi <code>callbacks.append(kinesis_callback.put_record)</code> et pas <code>…put_record()</code> ?</summary>
Avec les parenthèses, on appellerait la méthode tout de suite, sans message : erreur. Sans, on range la fonction pour que <code>ModelService</code> l'appelle plus tard avec chaque prédiction.
</details>

<details><summary>4. Tu lances le conteneur avec <code>-e TEST_RUN=true</code> et sans Kinesis. Que se passe-t-il ?</summary>
<code>'true' == 'True'</code> est faux : <code>TEST_RUN</code> vaut <code>False</code>, un callback Kinesis vers le vrai AWS est créé, et la première publication échoue (pas de flux, pas d'identifiants).
</details>

<details><summary>5. Le test d'intégration ne lit pas le modèle sur S3. Quelle ligne de quel fichier l'explique, et quelle variable ?</summary>
<code>model.py</code> l. 12-13 : <code>MODEL_LOCATION=/app/model</code> est définie dans <code>docker-compose.yaml</code>, donc <code>get_model_location</code> la renvoie sans construire de chemin S3.
</details>

<details><summary>6. Tu veux aussi écrire chaque prédiction dans un fichier. Que modifies-tu ?</summary>
Rien dans <code>ModelService</code> : écrire une fonction <code>ecrire(prediction_event)</code> et l'ajouter à la liste <code>callbacks</code> dans <code>init</code>.
</details>

<details><summary>7. Pourquoi <code>tests/model_test.py</code> n'importe-t-il jamais <code>lambda_function</code> ?</summary>
L'importer exécuterait <code>model.init</code> (ligne 10) : chargement d'un vrai modèle, lecture des variables d'environnement, création éventuelle d'un client Kinesis. Le test ne serait plus isolé.
</details>

---

## 15. Récapitulatif

| Notion | En une phrase |
|---|---|
| AWS / région / boto3 | Le cloud d'Amazon ; les ressources vivent dans une région ; boto3 les pilote depuis Python. |
| `endpoint_url` | Change l'adresse du service : vrai AWS ou LocalStack, même code. |
| Kinesis Data Streams | Journal de messages qui découple producteurs et consommateurs. |
| Shard / clé de partition | Voie du flux / chaîne qui choisit la voie ; même clé → même voie. |
| Lambda | Exécute ta fonction à chaque événement, sans serveur à gérer. |
| Handler | `handler(event, context)`, désigné par `CMD` dans le `Dockerfile`. |
| INIT / INVOKE | Code hors handler : une fois par environnement ; handler : à chaque événement. |
| Event source mapping | Lambda interroge Kinesis et s'appelle avec des lots `event['Records']`. |
| base64 | Transporte des octets dans du JSON. |
| Callback | Fonction confiée à un code, qui l'appelle au bon moment. |
| Méthode liée | `objet.methode` sans `()` : une fonction qui emporte son objet. |
| Injection de dépendances | `ModelService` reçoit modèle et callbacks → testable avec des faux. |
| `init` | Seul endroit qui assemble MLflow, Kinesis et `ModelService`. |
| `lambda_function.py` | Adaptateur mince : configuration + délégation. |
