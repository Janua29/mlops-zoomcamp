## Question 1

Question : 

* dans lambda_function.py, pour quoi les les 3 fonctions (get_model_location, load_model, base64_decode) ; 
   -  pourquoi elles sont définis en dehors de la class ModelService ou kinesis call back ?
   - pourquoi elle n'ont pas besoin d'un état self ? 
   - Pourquoi on ne les mets pas dans lambda_funtion.py au lieu de model.Py
* même question pour les fonction create_kinesis_client et init


Par ailleurs, tu as écris : `lambda_function.py` est le point d'entrée qu'AWS Lambda appelle

* on peut considérer que AWS lambda est un service de AWS ? Ou quand dit AWS lambda, il s'agit de la fonction lambda_function.py ?
* comment sais tu que "`lambda_function.py` est le point d'entrée qu'AWS Lambda appelle", où tu le vois ?
* je ne comprends pas comment AWS peut appeler lambda_handler car je ne vois pas le liens qui lie AWS et lambda_handler.py

**Answer**

Les 3 fonctions hors des classes. ModelService reçoit un modèle déjà chargé. Le chargement se fait donc avant que l'objet existe, dans init() : c'est le rôle de get_model_location et load_model. Grâce à ça, les tests peuvent donner un faux modèle, sans S3. base64_decode n'a besoin d'aucun état. Deux nuances sont écrites dans le cours (§11) :
- une méthode de classe qui fabrique l'objet aurait aussi marché, donc c'est en partie un choix de style ;
- prepare_features n'utilise pas self non plus.


### 1. Pourquoi ces fonctions n'ont pas besoin de `self`

`self` sert à **garder une information entre plusieurs appels**. Pour savoir si une fonction en a besoin, demande-toi d'où vient chaque information qu'elle utilise.

| Fonction | Ce dont elle a besoin | D'où ça vient |
|---|---|---|
| `get_model_location(run_id)` | `run_id`, bucket, expérience | Argument + variables d'environnement |
| `load_model(run_id)` | `run_id` | Argument |
| `base64_decode(encoded_data)` | Le texte à décoder | Argument |
| `create_kinesis_client()` | L'adresse de Kinesis | Variable d'environnement |
| `init(stream, run_id, test_run)` | Les 3 paramètres | Arguments |

Aucune ne réutilise une valeur donnée **plus tôt**. Elles reçoivent tout, calculent, renvoient, puis oublient.

Compare avec `predict(features)` : elle utilise `self.model`. Ce modèle a été donné **une fois**, à la création de l'objet, et sert à **chaque** appel. C'est ça, un état.

`init` est un cas à part : elle n'a pas d'état, elle le **fabrique**. C'est elle qui range le modèle et les callbacks dans le `ModelService`.

### 2. Pourquoi ne pas les mettre dans `lambda_function.py` ?

Il faut distinguer deux cas.

**`base64_decode` : il y a une vraie raison technique.** Importer `lambda_function.py` exécute sa ligne 10, `model.init(...)`, donc charge un vrai modèle. Si `base64_decode` était dans ce fichier, `test_base64_decode` devrait l'importer : le test deviendrait lent et dépendrait de MLflow et des variables d'environnement.

**`get_model_location`, `load_model`, `create_kinesis_client`, `init` : rien ne l'interdit.** Elles ne servent qu'au démarrage, et le code marcherait aussi dans `lambda_function.py`. L'auteur ne s'en explique pas. Voici mon interprétation :

- **Isoler la dépendance à AWS Lambda.** `lambda_function.py` est le seul fichier qui en dépend, à cause de la signature `(event, context)`. Le jour où tu sers le même modèle autrement (par exemple avec le serveur web Flask du module 4, ou un script batch), tu réécris ces 19 lignes, pas tout l'assemblage.
- **Pouvoir tester `init` un jour.** On pourrait importer `model` et appeler `init` avec `MODEL_LOCATION`, sans ce chargement au moment de l'import. Aujourd'hui, aucun test ne le fait.

### 3. « AWS Lambda » : le service ou le fichier ?

Il y a trois niveaux distincts :

| Terme | Ce que c'est | Ici |
|---|---|---|
| **AWS Lambda** | Le **service** d'AWS, comme S3 ou Kinesis | — |
| **Une fonction Lambda** | Une **ressource** que tu crées dans ce service : un nom, du code, des réglages | `stg_prediction_lambda_mlops-zoomcamp`, créée par Terraform |
| **Le handler** | La fonction Python, dans ton code, que la fonction Lambda exécute | `lambda_handler`, dans `lambda_function.py` |

Donc `lambda_function.py` n'est pas « AWS Lambda » : c'est un fichier du code de ta fonction Lambda. Son nom n'a rien de magique. C'est la convention par défaut d'AWS pour Python, rien de plus.

### 4. Où je vois que c'est le point d'entrée

À la dernière ligne du `Dockerfile` :

```dockerfile
FROM public.ecr.aws/lambda/python:3.9                 # image de base officielle d'AWS Lambda
COPY [ "lambda_function.py", "model.py", "./" ]
CMD [ "lambda_function.lambda_handler" ]              # ← ici
```

Cette ligne se lit « module `lambda_function`, fonction `lambda_handler` ». Si tu renommais le fichier `app.py` et la fonction `handle`, tu écrirais `CMD ["app.handle"]`, et tout marcherait pareil.

### 5. Le lien entre AWS et `lambda_handler`

Tu ne vois pas le lien parce qu'il n'est pas dans le code Python. C'est une **chaîne de quatre maillons**, répartie entre Terraform, le Dockerfile et un programme caché dans l'image de base :

```
① Terraform, aws_lambda_event_source_mapping
   « quand des messages arrivent dans ride_events, appelle la fonction stg_prediction_lambda_… »
        ↓
② Terraform, aws_lambda_function  (image_uri, package_type = "Image")
   « cette fonction exécute cette image Docker, stockée dans ECR »
        ↓
③ Dockerfile : FROM public.ecr.aws/lambda/python:3.9  +  CMD ["lambda_function.lambda_handler"]
   « dans cette image, le handler s'appelle lambda_function.lambda_handler »
        ↓
④ Le RIC (Runtime Interface Client), un programme Python fourni par l'image de base
   Au démarrage du conteneur, il reçoit la valeur de CMD et appelle ton handler
```

Le maillon ④ est celui qui manquait. Voici le cœur du RIC (bibliothèque `awslambdaric`, que j'ai téléchargée et lue), simplifié :

```python
modname, fname = "lambda_function.lambda_handler".rsplit(".", 1)  # → "lambda_function", "lambda_handler"
m = importlib.import_module(modname)      # = import lambda_function → INIT : charge le modèle
request_handler = getattr(m, fname)       # = récupère lambda_function.lambda_handler

while True:                               # boucle infinie
    event = attendre_prochain_evenement() # requête HTTP au service Lambda : « as-tu un événement ? »
    reponse = request_handler(event, context)
    renvoyer(reponse)                     # renvoie la réponse au service Lambda
```

Donc AWS n'appelle pas directement ton fichier. Le service Lambda démarre ton conteneur, où le RIC tourne. Le RIC importe ton module (c'est l'INIT), puis attend les événements en boucle et appelle ton handler à chaque fois (c'est l'INVOKE).

Au test d'intégration, c'est la même chaîne en plus court : le RIE (l'émulateur local) joue le rôle du service Lambda, et le RIC de l'image appelle ton handler.

J'ai lu le RIC dans sa version actuelle (4.1.0). L'image Python 3.9 du cours en contient une version plus ancienne. Je n'ai pas vérifié son code, mais le principe (importer le module, puis boucler sur les événements) est celui que décrit AWS.

Veux-tu que j'ajoute ces explications au cours ? Ce serait une nouvelle section « Du service Lambda à `lambda_handler` », plus un complément au §11 sur la question du fichier. Je ne touche à rien sans ton accord.

## Question 2

Tu as écris " Importer lambda_function . py exécute sa ligne 10, model.init(. . .),"
Ce la signifie qu'a chaque fois qu'on importe un script .py (exemple import model, import lambda_function), on exécute toutes les commandes/fonctions qui sont dans ce script ?

**Answer**

Oui : importer un fichier exécute tout le code **au niveau du module**, c'est-à-dire tout ce qui n'est pas indenté dans une fonction ou une classe, de haut en bas. Deux précisions changent tout :

**1. Exécuter un `def`, ce n'est pas exécuter la fonction.** Quand Python lit un `def`, il **crée** la fonction et la range sous son nom, sans exécuter son contenu. Le contenu ne s'exécute que lors d'un **appel**, avec des parenthèses. C'est pareil pour `class` : Python crée le moule, mais aucun objet.

**2. Ça n'arrive qu'une fois par programme.** Au premier `import`, Python exécute le fichier et garde le module en mémoire. Les `import` suivants réutilisent ce module sans rien ré-exécuter.

Démonstration, que j'ai exécutée :

```python
# outils.py
print("A. début de outils.py")

def saluer():
    print("C. dans saluer()")

print("B. fin de outils.py")

if __name__ == "__main__":
    print("D. lancé directement")
```

```python
# main.py
import outils
import outils          # 2e import : rien ne se passe
print("--- après les deux imports")
outils.saluer()        # l'appel : là, le contenu de saluer s'exécute
```

```
$ python main.py
A. début de outils.py
B. fin de outils.py
--- après les deux imports
C. dans saluer()
```

`A` et `B` s'affichent **une seule fois**, malgré deux `import`. `C` ne s'affiche qu'à l'appel. `D` n'apparaît pas (voir plus bas).

**Appliqué à nos deux fichiers :**

| Fichier | Ce que l'import exécute | Effet |
|---|---|---|
| `model.py` | Les `import`, puis des `def` et des `class` | Rien de coûteux : les fonctions et classes sont **créées**, aucune n'est **appelée** |
| `lambda_function.py` | `import model`, trois `os.getenv(...)`, puis `model_service = model.init(...)` | La ligne 10 est un **appel** (parenthèses), au niveau du module : `init` s'exécute, charge le modèle et crée le client Kinesis |

C'est pour ça que les tests peuvent faire `import model` sans risque, mais jamais `import lambda_function`.

**Comment empêcher du code de s'exécuter à l'import :** avec `if __name__ == "__main__":`. Python donne à `__name__` la valeur `"__main__"` quand tu lances le fichier directement (`python outils.py`), et le nom du module (`"outils"`) quand il est importé. Le bloc ne s'exécute donc qu'en lancement direct :

```
$ python outils.py
A. début de outils.py
B. fin de outils.py
D. lancé directement
```

Dans `lambda_function.py`, on ne met **pas** `model.init` sous ce `if`. On veut justement qu'il s'exécute quand Lambda importe le fichier : c'est la phase INIT, qui charge le modèle une fois pour toutes les invocations suivantes.

## Question 3

Tu as aussi écrit dans le cours
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

La fonction de callback est ici la fonction afficher. Mais on l'appelle via des crochets. C'est assez inhabituel non ?

**Answer**

Les crochets n'**appellent** pas `afficher` : ils fabriquent une **liste** qui contient la fonction. L'appel a lieu plus tard, ailleurs.

Découpons `calculer(21, callbacks=[afficher])` :

| Morceau | Ce que c'est |
|---|---|
| `afficher` | La fonction elle-même, **sans parenthèses** : on la désigne sans l'exécuter |
| `[afficher]` | Une liste d'un élément, comme `[42]` ou `["a"]`, sauf que l'élément est une fonction |
| `callbacks=[afficher]` | On passe cette liste à `calculer` |

L'appel, avec des parenthèses, se fait **dans** `calculer` :

```python
for cb in callbacks:   # 1er tour : cb = afficher
    cb(r)              # ← ici : afficher(42)
```

**Le vrai signal, ce sont les parenthèses, pas les crochets :**

```python
afficher              # la fonction (un objet)
afficher(42)          # un appel : exécute le contenu
[afficher]            # une liste contenant la fonction
[afficher(42)]        # appelle d'abord afficher, puis range son résultat (None) dans la liste
```

**Pourquoi une liste ?** Pour pouvoir passer **plusieurs** callbacks, ou **aucun** :

```python
calculer(21, callbacks=[afficher, sauvegarder])   # les deux seront appelés
calculer(21, callbacks=[])                        # aucun
```

C'est exactement le choix de `model.py` : `ModelService` reçoit une liste (`self.callbacks`), `init` la remplit avec `callbacks.append(kinesis_callback.put_record)`, et les tests la laissent vide.

**La forme courante, un seul callback, sans liste :**

```python
def calculer(x, callback):
    r = x * 2
    callback(r)
    return r

calculer(21, callback=afficher)
```

C'est la forme la plus répandue, par exemple `sorted(noms, key=len)`, où `len` est un callback. La liste est un choix de l'auteur pour permettre zéro, un ou plusieurs callbacks.

Ton étonnement est légitime : le cours montre la liste sans expliquer ce choix. Veux-tu que j'ajoute ce paragraphe au §6.2 ?