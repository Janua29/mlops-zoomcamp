# Cours complet : Workflow et Flux d'Information MLOps Streaming (AWS Lambda & Kinesis)

Ce cours présente le cycle de vie complet des données dans une architecture MLOps de streaming, depuis le test local jusqu'à la consommation des résultats en production sur AWS.

---

## 1. La vision globale de l'architecture

Dans une architecture de streaming avec AWS, le flux de données en production suit ce parcours :

$$\text{Producteur (Terminal/Code)} \longrightarrow \text{Kinesis Entrée } (\texttt{ride\_events}) \longrightarrow \text{AWS Lambda } (\texttt{lambda\_function.py}) \longrightarrow \text{Kinesis Sortie } (\texttt{ride\_predictions}) \longrightarrow \text{Consommateur (Terminal/App)}$$

1. **Le Producteur :** Pousse des événements (données brutes d'un trajet en taxi) dans le flux d'entrée.
2. **Kinesis (`ride_events`) :** Stream d'entrée qui reçoit et stocke temporairement les données.
3. **AWS Lambda (`lambda_function.py`) :** Se déclenche automatiquement à chaque nouvel événement arrivant dans Kinesis, exécute le modèle de Machine Learning et génère une prédiction.
4. **Kinesis (`ride_predictions`) :** Stream de sortie qui reçoit les prédictions publiées par la fonction Lambda.
5. **Le Consommateur :** Lit le flux de sortie pour exploiter les prédictions (ex : affichage, stockage en base de données, facturation).

---

## 2. Phase 1 : Test local SANS Docker (Test unitaire Python)

L'objectif est de valider le fonctionnement de la logique métier et du modèle ML directement sur ton PC, sans utiliser d'infrastructures ou de réseaux complexes.

```
[test.py] --- (Appel direct Python) ---> [lambda_function.py] --- (Return Python) ---> [test.py]

```

### Étape 1 : Dans le terminal (Configuration)

Tu définis les variables d'environnement nécessaires :

```bash
export PREDICTIONS_STREAM_NAME="ride_predictions_test"
export TEST_RUN="True"

```

* **Rôle :** `PREDICTIONS_STREAM_NAME` fournit un nom de flux par défaut. `TEST_RUN="True"` sert de **bouclier de sécurité** pour empêcher le script de tenter d'envoyer des données réelles sur AWS pendant le test local.

### Étape 2 : Dans le terminal (Exécution)

Tu lances le script de test :

```bash
python test.py

```

### Étape 3 : Que font les scripts en arrière-plan ?

1. **`test.py` :** Crée un dictionnaire Python simulant un événement Kinesis (un *mock*).
2. **Importation :** `test.py` importe la fonction `lambda_handler` depuis `lambda_function.py` (`from lambda_function import lambda_handler`).
3. **Exécution :** `test.py` exécute directement `lambda_handler(event, context=None)`.
4. **Traitement :** `lambda_function.py` charge le modèle ML et calcule la durée estimée du trajet.
5. **Bouclier active :** La condition `if not TEST_RUN:` est évaluée. Comme `TEST_RUN` vaut `"True"`, le bloc `kinesis_client.put_record(...)` est **ignoré**. Aucune connexion réseau vers AWS n'est établie.
6. **Résultat :** `lambda_function.py` fait un `return` du dictionnaire contenant la prédiction. `test.py` intercepte ce retour et l'affiche dans ton terminal via un `print()`.

---

## 3. Phase 2 : Test local AVEC Docker (Simulation de l'environnement AWS Lambda)

L'objectif est d'émuler l'environnement exact d'AWS Lambda (serveur web HTTP) sur ta machine grâce à l'image Docker basée sur *AWS Lambda Runtime Interface Emulator (RIE)*.

```
[test_docker.py] -- (HTTP POST / JSON) --> [Port 8080 / Conteneur Docker]
                                                   │
                                            (Convertit en Dict)
                                                   ▼
[test_docker.py] <-- (HTTP 200 / JSON) <-- [lambda_function.py]

```

### Étape 1 : Dans le Terminal 1 (Construction et lancement du serveur)

1. **Construire l'image Docker :**
```bash
docker build -t mon_image_lambda .

```


2. **Lancer le conteneur en mode serveur :**
```bash
docker run -it --rm -p 8080:8080 \
  -e PREDICTIONS_STREAM_NAME="ride_predictions_test" \
  -e TEST_RUN="True" \
  mon_image_lambda

```



* **Ce qui se passe :**
* `-e` injecte les variables d'environnement dans le conteneur.
* `-p 8080:8080` mappe le port de ton PC vers celui de l'émulateur.
* Le terminal se bloque : l'émulateur AWS tourne dans Docker et écoute sur le port 8080.
* La ligne `CMD [ "lambda_function.lambda_handler" ]` du `Dockerfile` indique à l'émulateur quel fichier et quelle fonction exécuter à la réception d'un appel.



### Étape 2 : Dans le Terminal 2 (Envoi de la requête de test)

Tu lances le script client :

```bash
python test_docker.py

```

### Étape 3 : Que font les scripts en arrière-plan ?

1. **`test_docker.py` :** Prépare un dictionnaire Python avec les données du trajet.
2. **Envoi HTTP :** Il utilise la librairie `requests` pour effectuer une requête HTTP POST :
`requests.post('http://localhost:8080/2015-03-31/functions/function/invocations', json=event)`
L'argument `json=event` convertit automatiquement le dictionnaire Python en texte JSON.
3. **Réception Docker :** L'émulateur AWS dans Docker intercepte la requête sur le port 8080, extrait le texte JSON et le re-transforme en dictionnaire Python.
4. **Exécution Lambda :** L'émulateur transmet ce dictionnaire à `lambda_handler(event, context)`. Le modèle calcule la prédiction. Le bloc Kinesis est ignoré grâce à `TEST_RUN="True"`.
5. **Réponse HTTP :** La fonction fait un `return` du résultat. L'émulateur convertit ce `return` en texte JSON et le renvoie sous forme de réponse HTTP (code `200 OK`).
6. **Résultat :** `test_docker.py` reçoit la réponse HTTP et affiche le contenu JSON dépaqueté via `print(response.json())`.

---

## 4. Phase 3 : Production sur le vrai AWS Kinesis

En production, le code s'exécute directement sur les serveurs AWS. On interagit avec le système via AWS CLI (le terminal) et la librairie Python `boto3`.

### Étape 1 : Le Producteur envoie des données dans le stream d'entrée

Depuis le terminal, tu envoies un enregistrement dans le flux Kinesis `ride_events` :

```bash
KINESIS_STREAM_INPUT="ride_events"

aws kinesis put-record \
    --stream-name ${KINESIS_STREAM_INPUT} \
    --partition-key 1 \
    --data '{
        "ride": {
            "PULocationID": 130,
            "DOLocationID": 205,
            "trip_distance": 3.66
        }, 
        "ride_id": 156
    }'

```

* **Ce qui se passe :** La commande envoie le JSON brut à AWS. Kinesis encode automatiquement ce payload en **Base64** pour des raisons de performance et de transport.

### Étape 2 : AWS Lambda traite la donnée et publie la prédiction

Dès que la donnée arrive dans `ride_events`, AWS déclenche automatiquement `lambda_function.py` :

1. **Décodage Base64 :** `lambda_function.py` reçoit la charge utile Kinesis. Il extrait et décode la donnée encodée en Base64 :
```python
encoded_data = event['Records'][0]['kinesis']['data']
decoded_data = base64.b64decode(encoded_data).decode('utf-8')
ride_event = json.loads(decoded_data)

```


2. **Calcul :** Le modèle ML calcule la prédiction à partir des données transmises (`PULocationID`, `DOLocationID`, `trip_distance`).
3. **Envoi Kinesis (Production) :** En production, `TEST_RUN` vaut `False`. Le bloc suivant s'exécute :
```python
if not TEST_RUN:
    kinesis_client.put_record(
        StreamName=PREDICTIONS_STREAM_NAME,
        Data=json.dumps(prediction_event),
        PartitionKey=str(ride_id)
    )

```


La librairie `boto3` (`kinesis_client`) publie le résultat au format JSON directement dans le stream de sortie `ride_predictions`.

---

### Étape 3 : Le Consommateur lit les résultats dans le stream de sortie

Kinesis est un flux continu. Pour lire le résultat écrit par Lambda dans `ride_predictions`, il faut obtenir un pointeur de lecture (*Shard Iterator*), puis lire les enregistrements.

1. **Initialiser les variables et récupérer le Shard Iterator :**
```bash
KINESIS_STREAM_OUTPUT="ride_predictions"
SHARD="shardId-000000000000"

SHARD_ITERATOR=$(aws kinesis get-shard-iterator \
    --shard-id ${SHARD} \
    --shard-iterator-type TRIM_HORIZON \
    --stream-name ${KINESIS_STREAM_OUTPUT} \
    --query 'ShardIterator' \
    --output text)

```


* `--shard-iterator-type TRIM_HORIZON` positionne le curseur au tout début des données disponibles dans le stream.


2. **Lire les enregistrements dans le stream :**
```bash
aws kinesis get-records --shard-iterator ${SHARD_ITERATOR}

```


3. **Ce que retourne le terminal :**
Le terminal renvoie une structure JSON contenant les enregistrements :
```json
{
    "Records": [
        {
            "SequenceNumber": "496...",
            "ApproximateArrivalTimestamp": 165...,
            "Data": "eyJwcmVkaWN0aW9ucyI6IHsicmlkZV9kdXJhdGlvbiI6IDE3LjUsICJyaWRlX2lkIjogMTU2fX0=",
            "PartitionKey": "156"
        }
    ],
    "NextShardIterator": "AAAAAAAA..."
}

```


4. **Décodage du résultat final :**
La valeur du champ `"Data"` est la prédiction encodée en Base64. En décodant cette chaîne (ex: via la commande `echo "eyJwcmV..." | base64 --decode`), tu obtiens le JSON final écrit par la fonction Lambda :
```json
{
  "predictions": {
    "ride_duration": 17.5,
    "ride_id": 156
  }
}

```



---

## 5. Synthèse des configurations selon l'environnement

| Composant / Option | Test unitaire (Local) | Test Docker (Local) | Production (AWS) |
| --- | --- | --- | --- |
| **Variable `TEST_RUN**` | `"True"` | `"True"` | `"False"` (ou absente) |
| **Transport entrée** | Appel de fonction Python | Requête HTTP POST (`requests`) | AWS Kinesis Input Stream (`put-record`) |
| **Transport sortie** | `return` capturé par `test.py` | `return` converti en HTTP Response | AWS Kinesis Output Stream (`boto3.put_record`) |
| **Format donnée entrée** | Dictionnaire Python (*mock*) | Dictionnaire converti en JSON | JSON encodé en Base64 via Kinesis |
| **Méthode de lecture** | `print()` terminal | `print(response.json())` | AWS CLI `get-records` + décodage Base64 |


# A propos des noms

**Question** : Il faut forcément donner un nom différent au kinesis_stream_output et linesis_stream_input ?
L'utilisateur peut choisir n'importe quel nom ?


**Oui, il faut obligatoirement des noms différents** pour le stream d'entrée et le stream de sortie, et **oui, tu peux choisir n'importe quel nom**, tant que tu restes cohérent dans ta configuration.

---

### 1. Pourquoi deux noms différents sont obligatoires ?

Si tu utilisais le même nom pour l'entrée et la sortie (par exemple `ride_events` partout), tu créerais une **boucle infinie** :

1. Tu envoies un trajet dans `ride_events`.
2. Kinesis détecte la nouvelle donnée et **déclenche ta Lambda**.
3. Ta Lambda calcule la prédiction et réécrit le résultat dans `ride_events`.
4. Kinesis voit une nouvelle donnée arriver dans `ride_events` et **redéclenche ta Lambda**.
5. Le cycle se répète à l'infini jusqu'à faire exploser ton quota et ta facture AWS.

Le stream d'entrée (`ride_events`) et le stream de sortie (`ride_predictions`) doivent donc être deux tuyaux strictement séparés.

---

### 2. Peux-tu choisir n'importe quel nom ?

**Oui, totalement.** AWS Kinesis se fiche du nom métier que tu donnes à tes streams. Tu pourrais très bien appeler tes flux `tuyau_entree_taxis` et `resultats_predictions_v1`.

Il y a seulement deux contraintes à respecter :

* **Les contraintes AWS :** Le nom doit comporter entre 1 et 128 caractères (lettres, chiffres, tirets `-`, *underscores* `_` et points `.`).
* **La cohérence :** Le nom avec lequel tu créées le stream sur AWS (`aws kinesis create-stream --stream-name ...`) doit être **strictement identique** à celui que tu passes dans ta variable d'environnement (`PREDICTIONS_STREAM_NAME`).