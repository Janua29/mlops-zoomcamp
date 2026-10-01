# Module 6 — Best Practices, vidéo par vidéo

> **Ce que contient ce cours** : le chapitre 6 dans l'**ordre où les instructeurs construisent le code**. Alexey Grigorev présente les vidéos 6.1 à 6.6, Sejal Vaidya les vidéos 6.7 à 6.13. Un chapitre du cours correspond à une vidéo.
>
> **Sources** : [dépôt original › 06-best-practices](https://github.com/DataTalksClub/mlops-zoomcamp/tree/main/06-best-practices) · [ton fork](https://github.com/Janua29/mlops-zoomcamp/tree/main/06-best-practices) (au 30/09/2026, le dossier `code/` est identique à l'original) · l'historique git du dépôt original · les notes de la communauté. L'annexe D explique comment l'ordre a été reconstitué et ce qui n'a pas été vérifié.
>
> **Compléments**, à ouvrir seulement en cas de besoin : `cours-06-best-practices-v2.md` (chaque fichier de configuration expliqué, liste des bugs) et `cours-06-model-et-lambda-function.md` (`model.py` et `lambda_function.py` ligne par ligne).
>
> État au 30/09/2026.

---

## Comment lire ce cours

### Le fil rouge

Le module 6 ne crée **pas** de nouveau service. Il reprend le service de **streaming** du module 4 (vidéo 4.4) : une fonction AWS Lambda qui lit des courses de VTC dans un flux Kinesis, prédit leur durée et publie la prédiction dans un second flux. Le module 6 entoure ce service de **bonnes pratiques** : tests, qualité du code, automatisation, infrastructure décrite dans des fichiers, déploiement automatique.

Comme tu n'as pas suivi la vidéo 4.4, la **Partie 0** la reprend. Elle répond à tes trois questions : où le flux d'événements est défini, comment il arrive à Lambda, et où Lambda envoie ses résultats. Commence par elle, sinon la suite restera floue.

### La structure de chaque chapitre

| Rubrique | Contenu |
|---|---|
| **Le but** | Le problème que la vidéo résout, en deux ou trois phrases. |
| **Ce que fait l'instructeur** | Les étapes dans l'ordre de la vidéo, avec des repères de temps approximatifs, comme `[~11:00]`. |
| **Schéma + récit** | Un schéma, puis le récit numéroté de ce qui se passe : qui envoie quoi à qui, qui calcule, ce qui revient. |
| **Dans ton Codespace** | **Toutes** les commandes à taper, dans l'ordre, avec le terminal et le dossier. Les pièges connus sont signalés. |
| **État en fin de vidéo** | À quoi ressemblent les fichiers à ce moment. Compare-les avec les tiens. |
| **Vérifie-toi** | Quelques questions, réponses repliées. |

Les repères de temps viennent de notes de la communauté générées automatiquement. Ils marquent des blocs d'environ 3 minutes et non le début exact d'un sujet : utilise-les pour te situer dans la vidéo.

### Les blocs de commandes

Chaque bloc de commandes commence par une ligne de commentaire qui dit **où** le taper :

```bash
# [Terminal A] dossier mon-code, environnement pipenv actif
pytest tests/
```

- **Terminal A, Terminal B** : dans VS Code, *Terminal → New Terminal* en ouvre un nouveau (ou l'icône « split » pour deux côte à côte). Il en faut deux quand un programme occupe le premier : par exemple un conteneur lancé au premier plan (sans l'option `-d`, « détaché »), qui garde le terminal tant qu'il tourne.
- Les lignes qui commencent par `#` sont des commentaires : le shell les ignore. Tu peux copier le bloc entier.
- `→` dans un commentaire indique ce que la commande doit afficher.

### Légende des schémas

| Symbole | Sens |
|---|---|
| `A ──► B` ou `B ◄── A` | Quelque chose va de A vers B : **la pointe désigne le destinataire**. Le texte près de la flèche dit s'il s'agit d'une demande (« put-record », « du nouveau ? ») ou d'une réponse (« réponse : … »). |
| `═══` | Un dossier **partagé** entre ton Codespace et un conteneur (un *volume*). Ce n'est pas un échange réseau. |
| ①②③ | Les étapes du récit sous le schéma. |
| `[ nom ]` | Un flux Kinesis. |

### Le plan

| Partie | Vidéo | Sujet | AWS nécessaire ? |
|---|---|---|---|
| 0 | 4.4 (rattrapage) | Le streaming : Kinesis → Lambda → Kinesis | Non (explications seulement) |
| 1 | — | Préparer ton Codespace | Non |
| A | 6.1 | Tests unitaires avec pytest | Non |
| A | 6.2 | Tests d'intégration avec docker-compose | Non |
| A | 6.3 | Simuler Kinesis avec LocalStack | Non |
| A | 6.4 | Qualité du code : pylint, black, isort | Non |
| A | 6.5 | Hooks git pre-commit | Non |
| A | 6.6 | Makefile et `make` | Non |
| B | 6.7 à 6.10 | Terraform : décrire l'infrastructure AWS dans des fichiers | **Oui, payant** |
| C | 6.11 à 6.13 | CI/CD avec GitHub Actions | **Oui, payant** |
| Annexes | — | Carte des fichiers, commandes, pièges, sources | — |

Sur YouTube, les vidéos des parties B et C s'intitulent **6B.1 à 6B.7**. Le dépôt les numérote aujourd'hui 6.7 à 6.13. Les deux numérotations sont indiquées.

---

# Partie 0 — Rattrapage : le streaming du module 4 (vidéo 4.4)

> Sources : [`04-deployment/streaming/`](https://github.com/DataTalksClub/mlops-zoomcamp/tree/main/04-deployment/streaming) (code et `README.md` de l'instructeur), [la vidéo 4.4](https://www.youtube.com/watch?v=TCqr9HNcrsI) et les notes détaillées d'un participant de 2024 ([Ch4_Notes_ML.md](https://github.com/mleiwe/mlops-zoomcamp/blob/NotesBranch/cohorts/2024/04-deployment/Ch4_Notes_ML.md)) pour les clics dans la console AWS.

Cette partie ne demande aucune commande : dans la vidéo 4.4, tout se passe sur le vrai AWS. Il s'agit de comprendre le service que le module 6 va tester.

## 0.1 Le scénario

Une application de VTC. Chaque fois qu'une course commence, le serveur de l'application **publie un événement** : « course n° 156, départ zone 130, arrivée zone 205, 3,66 miles ». Plusieurs services veulent réagir à cet événement : le nôtre, qui prédit la **durée** ; un autre qui pourrait prédire le pourboire ; un troisième qui détecte la fraude…

Au module 4.2, tu as vu l'autre façon de faire : un **web service** (Flask). Le client envoie une requête et **attend** la réponse. Avec plusieurs services, le serveur de l'application devrait tous les appeler un par un et les attendre.

Le **streaming** change cela : l'application dépose l'événement dans un **flux**, et chaque service intéressé vient le lire quand il veut. L'application n'attend personne et ne sait même pas qui lit.

> **Analogie.** Un flux est un **tapis roulant de colis**. Celui qui dépose un colis ne sait pas qui le ramassera. Les colis restent sur le tapis un certain temps (24 h par défaut), même si personne ne les prend tout de suite. Plusieurs ramasseurs peuvent lire le même tapis.

```text
                ①                                                   ④
 Appli VTC ─────────────► [ ride_events ]       [ ride_predictions ] ─────────► applis qui
 (producteur)  dépose            │                        ▲                       lisent les
               une course        │ ②                      │ ③                     prédictions
                                 ▼                        │ publie la prédiction
                     ┌───────────────────────────┐        │
                     │ AWS Lambda                │────────┘
                     │ ta fonction lambda_handler│
                     │ décode, prédit la durée   │
                     └───────────────────────────┘
```

**Récit.**

1. L'application (le **producteur**) dépose chaque nouvelle course dans le flux `ride_events`.
2. Le service AWS Lambda récupère les nouvelles courses dans ce flux et appelle **ta** fonction Python avec elles. Ta fonction décode chaque course, calcule les features et prédit la durée avec le modèle entraîné aux modules 1 et 2.
3. Ta fonction dépose chaque prédiction dans un **second** flux, `ride_predictions`.
4. Les applications qui ont besoin des prédictions (afficher l'heure d'arrivée au client, par exemple) lisent ce second flux.

Il y a donc **deux flux** : un d'entrée, un de sortie. Ta fonction est **consommatrice** du premier et **productrice** du second.

## 0.2 Les pièces du puzzle

| Pièce | Ce que c'est | Dans ce service |
|---|---|---|
| **Kinesis Data Streams** | Le service AWS de flux de messages. | Les deux flux. |
| **Flux** (*stream*) | Un tapis roulant nommé. Techniquement : un **nom**, un nombre de **shards** et une **durée de conservation**. | `ride_events`, `ride_predictions` |
| **Shard** | Une voie du tapis. Plus de shards = plus de débit. | 1 shard par flux au module 4 |
| **Record** (message) | Un colis : des octets (Kinesis ne les lit pas), une **clé de partition** (qui choisit le shard) et un **numéro de séquence** (attribué par Kinesis). | Une course, ou une prédiction |
| **API** | L'ensemble des requêtes qu'un service accepte (« crée un flux », « dépose un record »…). Les services AWS se pilotent par des requêtes HTTPS envoyées à leur API. | — |
| **AWS Lambda** | Un service qui **exécute ta fonction Python à ta place**, chaque fois qu'il y a quelque chose à traiter. Tu ne lances jamais le programme toi-même. | La fonction de prédiction |
| **Handler** | La fonction qu'AWS Lambda appelle : `lambda_handler(event, context)`. `event` contient les données reçues ; `context` des informations sur l'exécution (temps restant, identifiant de l'appel…), inutilisées ici mais imposées par Lambda. | Dans `lambda_function.py` |
| **Trigger** (déclencheur), ou **event source mapping** | Le **branchement** entre un flux et une fonction Lambda. C'est un mécanisme du service Lambda qui surveille le flux et appelle la fonction. | `ride_events` → la fonction |
| **IAM, rôle, policy** | Les droits. Un **rôle** est une identité que la fonction endosse ; les **policies** listent ce qu'elle a le droit de faire. | Lire `ride_events`, écrire dans `ride_predictions`, lire S3, écrire des logs |
| **CloudWatch Logs** | Les journaux. Tout `print` de la fonction y arrive. | Déboguer |
| **S3** | Le stockage de fichiers d'AWS. | Le modèle MLflow du module 2 |
| **ECR** | Le dépôt d'images Docker d'AWS. | L'image de la fonction |
| **AWS CLI** (`aws`) | Un **programme** installé sur ta machine, qui envoie des requêtes à AWS depuis le terminal. | Envoyer une course, lire les prédictions |
| **boto3** | La bibliothèque Python qui fait la même chose depuis du code. | `kinesis_client.put_record(...)` |

## 0.3 Comment l'instructeur construit le service (ordre de la vidéo 4.4)

Le `README.md` de `04-deployment/streaming` annonce le plan : *Scenario, Creating the role, Create a Lambda function and test it, Create a Kinesis stream, Connect the function to the stream, Send the records*. Voici toutes les étapes, dans l'ordre.

| # | Où | Action | Résultat |
|---|---|---|---|
| 1 | Console AWS › IAM | Créer le rôle `lambda-kinesis-role` avec la policy fournie par AWS `AWSLambdaKinesisExecutionRole` | La future fonction pourra **lire** Kinesis et **écrire des logs** |
| 2 | Console › Lambda | Créer une fonction (Python 3.9, rôle ci-dessus), dont le code se contente de `print(json.dumps(event))`. La tester dans la console avec un faux événement | Une fonction qui affiche ce qu'elle reçoit |
| 3 | Console › Kinesis | Créer le flux `ride_events`, 1 shard | **Le flux d'entrée existe** |
| 4 | Console › Lambda | *Add trigger* → Kinesis → `ride_events` | **Le branchement flux → fonction existe** (l'event source mapping) |
| 5 | Terminal | `aws kinesis put-record --stream-name ride_events --partition-key 1 --data "Hello, this is a test."` | Dans CloudWatch, on voit l'événement reçu : `data` est **illisible** (base64) |
| 6 | Code de la fonction | Décoder le base64, envoyer une vraie course en JSON, écrire `prepare_features` et un `predict` qui renvoie d'abord une valeur fixe (10) | La logique marche, sans modèle |
| 7 | Console › Kinesis + code | Créer le flux `ride_predictions` ; ajouter `kinesis_client.put_record(...)` dans la fonction | **Refusé** (*AccessDenied*) : le rôle n'a pas le droit d'écrire |
| 8 | Console › IAM | Créer une policy « `PutRecord`, `PutRecords` sur le flux `ride_predictions` » et l'attacher au rôle | La fonction peut publier |
| 9 | Terminal | Lire `ride_predictions` : `get-shard-iterator`, puis `get-records`, puis décoder | On voit la prédiction |
| 10 | Local (VS Code) | Copier le code dans `lambda_function.py`, charger le vrai modèle MLflow depuis S3 (variable `RUN_ID`), tester avec `test.py` et `TEST_RUN=True` | La fonction prédit pour de vrai |
| 11 | Local | `Pipfile` et `Dockerfile` basé sur l'image Lambda officielle ; `docker run` puis `test_docker.py` | La fonction tourne dans un conteneur, comme sur AWS |
| 12 | Terminal + console | Pousser l'image dans ECR ; créer une nouvelle fonction Lambda **à partir de l'image** ; lui donner ses variables d'environnement, plus de mémoire et de temps, le trigger `ride_events`, et le droit de lire S3 | Le service final |

Retiens surtout les étapes **3, 4, 7 et 8** : elles répondent à tes questions. Au module 6, Terraform (partie B) refera ces clics sous forme de fichiers.

## 0.4 Question 1 — Où est défini le flux d'événements ?

« Le flux d'événements » recouvre **trois** choses différentes. Il faut les séparer.

### a) Le tuyau : le flux Kinesis `ride_events`

Au module 4, il est **créé à la main dans la console AWS** (étape 3). Il n'est écrit dans **aucun fichier** du dépôt. Sa définition complète tient en trois informations : un **nom** (`ride_events`), un **nombre de shards** (1) et une **durée de conservation** (24 h par défaut). L'équivalent en ligne de commande serait :

```bash
aws kinesis create-stream --stream-name ride_events --shard-count 1
```

Un flux n'a **pas de schéma** : ni colonnes, ni types, contrairement à une table PostgreSQL du module 5. Il transporte des octets quelconques.

### b) Le format de l'événement : une convention

Puisque le flux ne vérifie rien, le format est une **convention** entre celui qui écrit et celui qui lit. Ici, une course est ce JSON :

```json
{
    "ride": {
        "PULocationID": 130,
        "DOLocationID": 205,
        "trip_distance": 3.66
    },
    "ride_id": 156
}
```

Cette convention n'est écrite nulle part en tant que telle. Elle existe à **deux endroits qui doivent concorder** :

- chez le **producteur** : ce qu'il met dans `--data` (étape 5) ;
- chez le **consommateur** : le code de la fonction, qui lit `ride_event['ride']`, `ride_event['ride_id']`, puis `ride['PULocationID']`, `ride['DOLocationID']` et `ride['trip_distance']`.

Si le producteur renomme un champ, la fonction plante (`KeyError`) : c'est ce genre de rupture que les tests du module 6 aident à repérer.

### c) Le producteur : c'est toi

Dans la vraie vie, le producteur serait le serveur de l'application VTC, qui appellerait `put_record` avec boto3. **Dans le cours, aucun programme producteur n'est écrit** : c'est toi qui joues ce rôle, depuis le terminal, avec l'AWS CLI (commande du `README.md` du module 4) :

```bash
KINESIS_STREAM_INPUT=ride_events
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

- `KINESIS_STREAM_INPUT=ride_events` crée une variable **du shell** ; `${KINESIS_STREAM_INPUT}` la remplace par sa valeur dans la commande suivante.
- `--partition-key 1` : la clé de partition choisit le shard (avec 1 seul shard, peu importe).
- `--data` : le contenu du record, ici le JSON de la course.

> **Piège AWS CLI v2.** L'instructeur utilisait visiblement la version 1 de l'AWS CLI (son `README.md` emploie aussi `aws ecr get-login`, une commande qui n'existe plus en version 2). Avec la **version 2** (celle qu'on installe aujourd'hui), `--data` est interprété par défaut comme du **base64 déjà encodé** : un JSON en clair provoque une erreur. Il faut ajouter `--cli-binary-format raw-in-base64-out` (« ce que je donne est brut, encode-le toi-même »). C'est ce que fera `scripts/test_cloud_e2e.sh` au module 6.

Au fil du module 6, le rôle du producteur sera tenu par des acteurs différents : voir le récapitulatif du §0.9.

## 0.5 Question 2 — Comment l'événement arrive-t-il à Lambda ?

**Idée clé : Kinesis n'envoie rien à personne.** Un flux est un stockage **passif**. C'est le **service Lambda** qui vient chercher les messages, grâce au **trigger** créé à l'étape 4. Ce trigger s'appelle techniquement un **event source mapping** (« branchement d'une source d'événements »).

```text
 Toi (terminal)        Kinesis              Service Lambda              Ta fonction
 AWS CLI               ride_events          (event source mapping)      lambda_handler
    │                     │                       │                          │
    │ ① put-record ──────►│                       │                          │
    │ ◄── n° de shard,    │ range la course       │                          │
    │     n° de séquence  │ dans son shard        │                          │
    │                     │                       │                          │
    │                     │◄── ② « du nouveau ? » │   (environ 1 fois par    │
    │                     │─── les records ──────►│    seconde, par shard)   │
    │                     │                       │                          │
    │                     │                       │ ③ met les records dans   │
    │                     │                       │   une enveloppe JSON,    │
    │                     │                       │   data encodé en base64  │
    │                     │                       │                          │
    │                     │                       │ ④ appelle ──────────────►│
    │                     │                       │   lambda_handler(event,  │
    │                     │                       │   context)               │ ⑤ décode,
    │                     │                       │                          │   prédit
    │                     │                       │◄── ⑥ valeur renvoyée ────│
    │                     │                       │   (jetée : personne      │
    │                     │                       │    ne la lit)            │
```

**Récit.**

1. **Tu déposes** la course avec `aws kinesis put-record`. Le programme `aws`, sur ta machine, envoie une requête HTTPS à Kinesis. Kinesis range la course dans un shard du flux `ride_events` et répond avec le numéro du shard et un numéro de séquence. C'est tout : Kinesis ne prévient personne.
2. **Le service Lambda interroge** le flux, environ une fois par seconde et par shard (*polling*, « sondage »). C'est lui qui demande « y a-t-il du nouveau ? ». Il récupère les nouveaux records.
3. **Il prépare l'enveloppe.** Il regroupe les records reçus en un **lot** (*batch* : jusqu'à 100 records par défaut, tous du même shard) et les place dans un dictionnaire `{"Records": [...]}`. Le contenu de chaque record y est encodé en **base64** (explication juste après).
4. **Il appelle ta fonction** : `lambda_handler(event, context)`, où `event` est cette enveloppe. Il attend la fin de l'appel avant de passer au lot suivant du même shard.
5. **Ta fonction calcule.** C'est le seul endroit où l'on calcule. Elle boucle sur `event['Records']` (d'où le `for record in event['Records']` du code), décode chaque course et prédit sa durée.
6. **La valeur renvoyée est ignorée.** Avec un trigger Kinesis, Lambda ne fait rien du `return` (sauf si l'on active une option, `ReportBatchItemFailures`, qui permet de signaler les records en échec ; elle n'est pas utilisée ici). Le résultat utile doit donc partir **ailleurs** : c'est la question 3.

Pour que l'étape 2 soit permise, le rôle de la fonction doit avoir le droit de **lire** le flux : c'est ce qu'apporte la policy `AWSLambdaKinesisExecutionRole` de l'étape 1.

### L'enveloppe : ce que tu envoies et ce que la fonction reçoit

Tu as envoyé le JSON de la course. La fonction, elle, reçoit ceci (le fichier `integration-test/event.json` du module 6 en est une copie) :

```json
{
    "Records": [
        {
            "kinesis": {
                "kinesisSchemaVersion": "1.0",
                "partitionKey": "1",
                "sequenceNumber": "49630081666084879290581185630324770398608704880802529282",
                "data": "ewogICAgICAgICJyaWRlIjogewogICAgICAgICAgICAiUFVMb2NhdGlvbklE...",
                "approximateArrivalTimestamp": 1654161514.132
            },
            "eventSource": "aws:kinesis",
            "eventID": "shardId-000000000000:49630081666084879290581185630324770398608704880802529282",
            "eventName": "aws:kinesis:record",
            "invokeIdentityArn": "arn:aws:iam::387546586013:role/lambda-kinesis-role",
            "awsRegion": "eu-west-1",
            "eventSourceARN": "arn:aws:kinesis:eu-west-1:387546586013:stream/ride_events"
        }
    ]
}
```

(`data` est tronqué ici ; `eventVersion` a été omis.)

- `Records` : une **liste**, car un appel peut contenir plusieurs courses.
- `kinesis.data` : **ta course**, encodée en base64. Tout le reste (`partitionKey`, `sequenceNumber`, `eventSourceARN`…) est ajouté par Kinesis et Lambda. Le code n'utilise que `data`.
- **Pourquoi du base64 ?** Un record contient des **octets** quelconques. Or l'enveloppe est du JSON, qui ne transporte que du **texte**. Le base64 écrit n'importe quels octets avec 64 caractères sûrs (`A-Z a-z 0-9 + /`). La fonction doit donc **décoder** :

```text
"ewogICAg..."  ── b64decode ──►  b'{\n        "ride": {...'  ── .decode("utf-8") ──►  texte JSON  ── json.loads ──►  dictionnaire
 texte base64                     octets                                                                                 {'ride': {...}, 'ride_id': 256}
```

Les champs qui finissent par `ARN` contiennent des **ARN** (*Amazon Resource Name*) : l'identifiant unique d'une ressource AWS. `arn:aws:kinesis:eu-west-1:387546586013:stream/ride_events` se lit « le flux Kinesis `ride_events`, région `eu-west-1`, compte `387546586013` ».

**D'où vient ce fichier ?** C'est un **vrai** événement : on y lit le numéro de compte AWS de l'auteur (`387546586013`), son flux `ride_events` et son rôle `lambda-kinesis-role`. D'après les notes de la communauté, c'est ce qu'affiche le `print(json.dumps(event))` de l'étape 2, relevé dans CloudWatch après l'envoi d'une course en JSON (étape 6), puis réutilisé comme **événement de test**. La course qu'il contient porte le `ride_id` 256 (et non 156 comme dans la commande du §0.4) : elle vient d'un autre envoi. Détail qui le confirme : décodé, `data` contient `\n` et de nombreux espaces, car la course avait été tapée sur plusieurs lignes dans le terminal. On retrouvera cet événement dans `test.py` et `test_docker.py` (module 4), puis dans `event.json` et `tests/data.b64` (module 6).

## 0.6 Question 3 — Où Lambda envoie-t-il les prédictions ?

Nulle part automatiquement : **c'est ta fonction elle-même** qui écrit dans le second flux, avec boto3. Extrait de `04-deployment/streaming/lambda_function.py` :

```python
kinesis_client = boto3.client('kinesis')                                        # client Kinesis, créé une fois
PREDICTIONS_STREAM_NAME = os.getenv('PREDICTIONS_STREAM_NAME', 'ride_predictions')  # nom du flux de sortie
...
        if not TEST_RUN:                                   # en mode test, on ne publie pas
            kinesis_client.put_record(
                StreamName=PREDICTIONS_STREAM_NAME,        # dans quel flux
                Data=json.dumps(prediction_event),         # le message : la prédiction en JSON
                PartitionKey=str(ride_id)                  # la clé de partition : l'identifiant de la course
            )
```

Le message publié :

```json
{"model": "ride_duration_prediction_model", "version": "123",
 "prediction": {"ride_duration": 21.29, "ride_id": 256}}
```

`ride_id` est recopié pour que le lecteur sache **à quelle course** correspond la prédiction. (`version` vaut `'123'`, codé en dur au module 4 ; le module 6 y mettra le `RUN_ID` du modèle.)

```text
 Ta fonction                Kinesis                     Toi (terminal)
 lambda_handler             ride_predictions            AWS CLI
    │                          │                           │
    │ ⑦ put_record ───────────►│                           │
    │   (boto3, HTTPS)         │ range la prédiction       │
    │                          │                           │
    │                          │◄── ⑧ get-shard-iterator ──│
    │                          │─── un marque-page ───────►│
    │                          │◄── ⑨ get-records ─────────│
    │                          │─── les records ──────────►│ ⑩ décode le base64
    │                          │    (Data en base64)       │    et lit la prédiction
```

**Récit.**

7. Pour chaque course, ta fonction appelle `put_record` : boto3 envoie une requête HTTPS à Kinesis, qui range la prédiction dans `ride_predictions`. Il faut pour cela le **droit d'écrire** dans ce flux : c'est la policy ajoutée à l'étape 8 du §0.3 (sans elle : *AccessDenied*).
8. Pour lire un flux, on demande d'abord un **marque-page** (*shard iterator*) : « place-toi au début du shard `shardId-000000000000` » (`TRIM_HORIZON` = le plus ancien message encore conservé ; `LATEST` = seulement les messages à venir).
9. Avec ce marque-page, `get-records` renvoie les records. Dans la sortie de l'AWS CLI, `Data` est à nouveau en base64 (pour la même raison : c'est du JSON).
10. Tu décodes et tu lis la prédiction. Dans la vraie vie, ce serait une autre application qui lirait ce flux.

Les commandes du `README.md` du module 4 pour ces étapes 8 à 10 :

```bash
KINESIS_STREAM_OUTPUT='ride_predictions'
SHARD='shardId-000000000000'

SHARD_ITERATOR=$(aws kinesis \
    get-shard-iterator \
        --shard-id ${SHARD} \
        --shard-iterator-type TRIM_HORIZON \
        --stream-name ${KINESIS_STREAM_OUTPUT} \
        --query 'ShardIterator' \
)

RESULT=$(aws kinesis get-records --shard-iterator $SHARD_ITERATOR)

echo ${RESULT} | jq -r '.Records[0].Data' | base64 --decode
```

`$( … )` exécute la commande et met sa sortie dans la variable. `jq` extrait un champ d'un JSON ; `base64 --decode` décode.

### Les trois sorties de ta fonction

| Sortie | Destination | Qui la lit |
|---|---|---|
| `put_record(...)` | Le flux `ride_predictions` | Les applications intéressées (dans le cours : toi, avec `get-records`) |
| `print(...)` | CloudWatch Logs | Toi, pour déboguer |
| `return {...}` | Nulle part avec un trigger Kinesis | Personne en production. Le RIE (§0.8) et les tests, eux, la récupèrent |

`TEST_RUN=True` coupe la première sortie : pratique pour tester sans publier.

## 0.7 Le code du module 4, zone par zone

Voici `04-deployment/streaming/lambda_function.py` complet, découpé en trois zones. Les commentaires `# ←` sont des annotations de cours.

```python
import os
import json
import boto3
import base64

import mlflow

# ─── ZONE 1 : exécutée UNE fois, au démarrage du conteneur Lambda (« INIT ») ───
kinesis_client = boto3.client('kinesis')                  # ← crée un client AWS : il faut une région
PREDICTIONS_STREAM_NAME = os.getenv('PREDICTIONS_STREAM_NAME', 'ride_predictions')
RUN_ID = os.getenv('RUN_ID')
logged_model = f's3://mlflow-models-alexey/1/{RUN_ID}/artifacts/model'
model = mlflow.pyfunc.load_model(logged_model)            # ← télécharge le modèle depuis S3
TEST_RUN = os.getenv('TEST_RUN', 'False') == 'True'

# ─── ZONE 2 : des fonctions, qui utilisent les variables globales ci-dessus ───
def prepare_features(ride):
    features = {}
    features['PU_DO'] = '%s_%s' % (ride['PULocationID'], ride['DOLocationID'])
    features['trip_distance'] = ride['trip_distance']
    return features

def predict(features):
    pred = model.predict(features)                        # ← utilise la variable globale model
    return float(pred[0])

# ─── ZONE 3 : exécutée à CHAQUE lot reçu (« INVOKE ») ───
def lambda_handler(event, context):
    predictions_events = []
    for record in event['Records']:                       # ← un lot = plusieurs records
        encoded_data = record['kinesis']['data']
        decoded_data = base64.b64decode(encoded_data).decode('utf-8')   # ← décodage
        ride_event = json.loads(decoded_data)
        ride = ride_event['ride']
        ride_id = ride_event['ride_id']
        features = prepare_features(ride)
        prediction = predict(features)
        prediction_event = {
            'model': 'ride_duration_prediction_model',
            'version': '123',
            'prediction': {'ride_duration': prediction, 'ride_id': ride_id}
        }
        if not TEST_RUN:
            kinesis_client.put_record(                    # ← publication dans le flux de sortie
                StreamName=PREDICTIONS_STREAM_NAME,
                Data=json.dumps(prediction_event),
                PartitionKey=str(ride_id)
            )
        predictions_events.append(prediction_event)
    return {'predictions': predictions_events}
```

- **Zone 1** : Lambda réutilise son conteneur d'un lot à l'autre tant qu'il reste actif ; charger le modèle ici évite de le recharger à chaque course.
- **Zone 3** : une seule fonction fait **tout** (décoder, préparer, prédire, formater, publier).

Garde ce code en tête : c'est exactement ce que la vidéo 6.1 va réorganiser. Le problème, en une phrase : **importer ce fichier dans un test suffit à exécuter la zone 1**, donc à contacter AWS et S3.

## 0.8 Le passage à Docker : le RIE joue le rôle de Lambda

À la fin de la vidéo 4.4, la fonction est emballée dans une image Docker construite à partir de l'image officielle `public.ecr.aws/lambda/python:3.9`. Cette image contient le **RIE** (*Runtime Interface Emulator*, « émulateur de l'interface d'exécution ») : un petit **serveur HTTP** qui écoute sur le port 8080 et **joue le rôle du service Lambda**. On peut donc tester la fonction sur sa machine, sans AWS.

```text
 test_docker.py (ton terminal)                     Conteneur Docker (image Lambda)
                                                  ┌──────────────────────────────────┐
 ① POST localhost:8080/2015-03-31/  ─────────────►│ RIE (serveur HTTP, port 8080)    │
    functions/function/invocations                │    │                             │
    corps : l'enveloppe {"Records": [...]}        │    │ ② lambda_handler(event, …)  │
                                                  │    ▼                             │
                                                  │ ta fonction : ③ décode, prédit   │
 ◄──── ④ réponse HTTP = la valeur du return ──────│                                  │
       {"predictions": [...]}                     └──────────────────────────────────┘
```

**Récit.**

1. `test_docker.py` envoie une requête HTTP `POST` au port 8080. Le **corps** de la requête est l'enveloppe complète, déjà en base64, telle que Lambda la fabriquerait. `2015-03-31` est la version de l'API Lambda : ce chemin est fixe.
2. Le RIE reçoit la requête et appelle `lambda_handler(event, context)`, exactement comme le ferait AWS.
3. Ta fonction calcule la prédiction.
4. Le RIE renvoie la valeur du `return` dans la réponse HTTP. Contrairement au vrai trigger Kinesis, ici **le `return` est lu**, par `test_docker.py`.

Dans ce montage, `test_docker.py` remplace à lui seul **le producteur, le flux `ride_events` et le trigger**. C'est la base de la vidéo 6.2.

## 0.9 Récapitulatif : tes trois questions dans chaque contexte

Le même service sera exécuté dans quatre contextes. Ce tableau est la carte de tout le module :

| | Module 4 (console AWS) | 6.1 — tests unitaires | 6.2-6.3 — test d'intégration (local) | 6.7-6.10 — cloud (Terraform) |
|---|---|---|---|---|
| **Le flux d'entrée est défini…** | à la main dans la console | il n'existe pas | il n'existe pas | dans `infrastructure/main.tf` (module `source_kinesis_stream`) → `stg_ride_events-mlops-zoomcamp`. Ce nom est assemblé : `stg_ride_events` vient de `vars/stg.tfvars`, `mlops-zoomcamp` de `variables.tf` (`project_id`) |
| **La course (le format)** | tapée dans `put-record --data` | une chaîne base64 écrite dans le test (dans `tests/data.b64` à partir de 6.4) | dans `test_docker.py`, puis `integration-test/event.json` à partir de 6.4 (enveloppe complète) | tapée dans `scripts/test_cloud_e2e.sh` |
| **Le producteur est…** | toi, avec l'AWS CLI | le test pytest | `test_docker.py` | toi, avec `test_cloud_e2e.sh` (ou sa commande `put-record` tapée à la main) |
| **La course arrive à la fonction par…** | le trigger ajouté dans la console | un appel Python direct : `model_service.lambda_handler(event)` | un `POST` HTTP au RIE (`localhost:8080`) | l'event source mapping décrit dans `modules/lambda/main.tf` |
| **La fonction publie dans…** | `ride_predictions`, créé dans la console | rien (aucune publication) | 6.2 : rien (`TEST_RUN=True`) ; 6.3 : `ride_predictions` dans **LocalStack** (faux AWS), créé par `run.sh` | `stg_ride_predictions-mlops-zoomcamp`, créé par Terraform |
| **Le nom du flux de sortie est fixé par…** | la valeur par défaut de `PREDICTIONS_STREAM_NAME` dans le code (`ride_predictions`), ou une variable de la fonction | — | `run.sh` (`export PREDICTIONS_STREAM_NAME=…`), transmis au conteneur par `docker-compose.yaml` | Terraform (bloc `environment`), puis `deploy_manual.sh` (`update-function-configuration`) |
| **Qui lit les prédictions ?** | toi : `get-records` | le test lit le `return` | `test_docker.py` lit le `return` ; à partir de 6.3, `test_kinesis.py` lit le flux | toi : `get-records` ou CloudWatch |

### Vérifie-toi

<details><summary>1. Tu crées le flux <code>ride_events</code> et la fonction, mais tu oublies le trigger. Tu envoies une course. Que se passe-t-il ?</summary>
La course est rangée dans le flux et y reste (24 h par défaut). La fonction n'est jamais appelée : Kinesis ne prévient personne, et sans trigger, le service Lambda ne sonde pas ce flux.
</details>

<details><summary>2. Pourquoi <code>data</code> est-il illisible dans l'événement reçu par la fonction ?</summary>
Parce que l'enveloppe est du JSON (du texte), alors qu'un record contient des octets quelconques. Lambda encode ces octets en base64 ; la fonction doit décoder (<code>b64decode</code>, puis <code>.decode('utf-8')</code>, puis <code>json.loads</code>).
</details>

<details><summary>3. La fonction marche, mais <code>ride_predictions</code> reste vide et CloudWatch affiche <i>AccessDenied</i>. Que manque-t-il ?</summary>
Le droit d'écrire dans <code>ride_predictions</code> : une policy qui autorise <code>kinesis:PutRecord</code> sur ce flux, attachée au rôle de la fonction (étape 8 du §0.3).
</details>

<details><summary>4. Où va la valeur renvoyée par <code>lambda_handler</code> en production ? Et dans <code>test_docker.py</code> ?</summary>
En production (trigger Kinesis) : nulle part, Lambda l'ignore. Avec le RIE : dans la réponse HTTP, lue par <code>test_docker.py</code>.
</details>

---

# Partie 1 — Préparer ton Codespace (une seule fois)

## 1.1 Deux façons de suivre, une recommandée

Ton fork contient déjà le code **final** du module, dans `06-best-practices/code/`. Si tu le lis tel quel, tu vois le résultat sans voir comment on y arrive, et c'est ce qui rend le module difficile à suivre.

**Recommandation : refais le chemin de l'instructeur** dans un nouveau dossier, `06-best-practices/mon-code/`. Tu pars du code du module 4, comme lui, et tu ajoutes les pièces vidéo après vidéo. Le dossier `code/` te sert de **corrigé** : à la fin de chaque chapitre, compare.

## 1.2 L'environnement Python

Le code exige **Python 3.9** (et `scikit-learn==1.0.2`, la version qui a sauvegardé le modèle de test). conda fournit l'interpréteur Python 3.9, pipenv installe les paquets. Cette recette a été testée pour le cours précédent (`cours-06-best-practices-v2.md`, §0).

```bash
# [Terminal A] n'importe quel dossier — une seule fois
conda create -n mlops-06 python=3.9 -y
conda activate mlops-06
pip install "pipenv==2023.12.1"
```

**Pourquoi `pipenv==2023.12.1` ?** Le `Pipfile.lock` du module fige `mlflow==1.27.0`. Les versions récentes de pipenv utilisent un pip récent qui refuse d'installer cette version (`No matching distribution found for mlflow==1.27.0`). La version 2023.12.1 fonctionne.

## 1.3 Créer ton dossier de travail

```bash
# [Terminal A] environnement conda mlops-06 actif
cd /workspaces/mlops-zoomcamp/06-best-practices      # ← adapte si ton chemin diffère (pwd l'affiche)
mkdir mon-code
cd mon-code

# Le point de départ de l'instructeur : le code du module 4
cp ../../04-deployment/streaming/lambda_function.py .
cp ../../04-deployment/streaming/Dockerfile .
cp ../../04-deployment/streaming/test_docker.py .

# Les dépendances : les fichiers FINAUX du module 6 (explication ci-dessous)
cp ../code/Pipfile ../code/Pipfile.lock .

pipenv install --dev --python "$(which python)"      # installe tout, une fois (plusieurs minutes)
pipenv shell                                          # entre dans l'environnement
```

- `..` désigne le dossier parent : depuis `mon-code/`, `../..` remonte à la racine du dépôt.
- `--dev` installe aussi les outils de développement (pytest, pylint…). `--python "$(which python)"` : utiliser le Python 3.9 de conda. `$(which python)` est remplacé par le chemin de ce Python.

**Pourquoi copier le `Pipfile` final ?** Dans les vidéos, l'instructeur ajoute les outils un par un : `pipenv install --dev pytest` (6.1), `deepdiff` (6.2), `pylint`, `black`, `isort` (6.4), `pre-commit` (6.5). À chaque fois, pipenv **recalcule** tout le `Pipfile.lock` : c'est lent, et tu obtiendrais des versions plus récentes que celles du cours (mlflow 2.x…). Le `Pipfile` final contient les mêmes paquets principaux que celui du module 4 (`boto3`, `mlflow`, `scikit-learn==1.0.2`), plus ces outils. Quand la vidéo tape `pipenv install --dev <outil>`, **tu sautes la commande** : l'outil est déjà là.

**Dans VS Code** : `Ctrl+Shift+P` → *Python: Select Interpreter* → le chemin affiché par `pipenv --venv` (il finit par `…/virtualenvs/mon-code-xxxx`).

**À chaque nouveau terminal** (l'installation, elle, est faite une fois pour toutes) :

```bash
# [tout nouveau terminal]
conda activate mlops-06
cd /workspaces/mlops-zoomcamp/06-best-practices/mon-code
pipenv shell
```

## 1.4 Rappel : les variables du shell

Le module utilise beaucoup de **variables d'environnement** : `PREDICTIONS_STREAM_NAME`, `LOCAL_IMAGE_NAME`, `AWS_DEFAULT_REGION`… Quatre règles évitent la plupart des erreurs.

**Règle 1 — `export` rend une variable visible aux programmes lancés ensuite.**

```bash
NOM=ride_predictions            # variable du shell seulement : python, docker-compose… ne la voient pas
export NOM=ride_predictions     # variable d'environnement : visible par les programmes lancés depuis ce terminal
echo $NOM                       # → ride_predictions   (vérifier une valeur)
env | grep NOM                  # → NOM=ride_predictions   (vérifier qu'elle est bien exportée)
```

En Python, `os.getenv('NOM')` lit une variable d'environnement : elle doit avoir été **exportée**.

**Règle 2 — Une variable vit dans UN terminal, jusqu'à sa fermeture.** Un nouveau terminal ne la connaît pas : il faut refaire l'`export`. C'est la cause la plus fréquente de « ça marchait tout à l'heure ».

**Règle 3 — `VAR=valeur commande` passe une variable à cette seule commande.**

```bash
TEST_RUN=True python test.py    # TEST_RUN n'existe que pour ce python-là
```

**Règle 4 — `bash script.sh` ou `. script.sh` ?**

| Commande | Ce qui se passe | Les `export` du script… |
|---|---|---|
| `bash script.sh` (ou `./script.sh`) | Le script tourne dans un **nouveau** shell, qui disparaît à la fin | …disparaissent avec lui |
| `. script.sh` (ou `source script.sh`) | Le script tourne **dans ton** shell | …restent dans ton terminal |

`integration-test/run.sh` se lance avec `bash` : ses `export` ne te polluent pas. `scripts/deploy_manual.sh` se lance avec `.` (partie B) : on veut garder ses variables.

## 1.5 Vérifier les outils

```bash
# [Terminal A] n'importe où
docker --version                 # → Docker version …
docker-compose --version         # si « command not found », essaie la ligne suivante
docker compose version           # Compose v2 : alors remplace « docker-compose » par « docker compose » partout
aws --version                    # → aws-cli/2.… ; nécessaire à partir de la vidéo 6.3
```

`docker-compose` (avec un tiret) est la version 1 de l'outil, un programme séparé ; `docker compose` (avec une espace) est la version 2, intégrée à Docker. Les deux lisent les mêmes fichiers. Le cours écrit `docker-compose`, comme les scripts de l'instructeur.

Si `aws` est absent (à installer avant la vidéo 6.3) :

```bash
# [Terminal A] dossier personnel
cd ~
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o awscliv2.zip
unzip awscliv2.zip
sudo ./aws/install
aws --version
```

Enfin, le module 5 lançait un conteneur `adminer` sur le port **8080**, que le module 6 utilise aussi. Vérifie qu'il est arrêté :

```bash
# [Terminal A]
docker ps                        # si un conteneur publie 0.0.0.0:8080, arrête-le :
# cd /workspaces/mlops-zoomcamp/05-monitoring && docker compose down
```

---

# Partie A — Tout en local, gratuit (Alexey Grigorev)

---

## Vidéo 6.1 — Tests unitaires avec pytest

> [Vidéo](https://www.youtube.com/watch?v=CJp1eFQP5nk) · fichiers : `model.py`, `lambda_function.py`, `tests/model_test.py` · commit de l'instructeur : `88783bd` « unit tests » (27/06/2022).

### Le but

Pouvoir vérifier **en une seconde, sans AWS**, que la logique est juste : décoder une course, préparer les features, prédire, formater le résultat. Avec le code du module 4, c'est impossible (§0.7) : la vidéo **refactore** le code, c'est-à-dire qu'elle le réorganise sans changer ce qu'il fait, pour le rendre testable.

### Les notions de la vidéo

- **Test unitaire** : une petite fonction qui appelle **un morceau** de ton code avec une entrée connue et vérifie la sortie. Pas de réseau, pas de fichier externe : quelques millisecondes.
- **`assert condition`** : si la condition est fausse, Python lève une erreur `AssertionError` et le test échoue. Si elle est vraie, rien ne se passe.
- **pytest** : l'outil qui trouve et lance les tests. Il cherche les fichiers nommés `test_*.py` ou `*_test.py`, et dans ces fichiers, les fonctions nommées `test_*`. Il affiche un point par test réussi, un `F` par test raté.
- **Mock** (« imitation ») : un faux objet qui a la même forme que le vrai. Ici, un faux modèle qui renvoie toujours 10.0, pour tester sans charger le vrai modèle.
- **Injection de dépendances** : au lieu qu'un objet fabrique lui-même ses outils (le modèle, le client Kinesis), on les lui **donne**. On peut alors lui donner des faux.
- **Callback** : une fonction qu'on **confie** à un objet pour qu'il l'**appelle plus tard**. Ici : « après chaque prédiction, appelle cette fonction » (publier dans Kinesis, ou rien).

### Ce que fait l'instructeur

**Étape 1 `[0:00]` — Le plan.** Rappel de l'architecture du module 4 (§0.1) et du programme du module.

**Étape 2 `[~2:46]` — Installer pytest et le brancher sur VS Code.**
- Il copie le code du module 4 (`04-deployment/streaming`) dans `06-best-practices/code`, puis `pipenv install` et `pipenv install --dev pytest`. `--dev` : pytest sert à développer, pas à faire tourner le service ; il n'ira pas dans l'image Docker.
- Dans VS Code, il sélectionne l'interpréteur de l'environnement pipenv, puis ouvre le panneau **Testing** (l'icône en forme de fiole) → *Configure Python Tests* → **pytest** → dossier **tests**. VS Code écrit alors `.vscode/settings.json` :

```json
{
    "python.testing.pytestArgs": ["tests"],
    "python.testing.unittestEnabled": false,
    "python.testing.pytestEnabled": true
}
```

**Étape 3 `[~5:32]` — Un premier test, pour vérifier que tout est branché.**
- Il crée le dossier `tests/`, un fichier **vide** `tests/__init__.py` et `tests/model_test.py` avec un test trivial (`assert 1 == 1`). Il le lance depuis VS Code et avec `pytest tests/`.
- **Pourquoi `__init__.py` ?** Ce fichier vide fait de `tests/` un *package* Python. Grâce à lui, pytest ajoute le dossier **parent** (`code/`) au chemin où Python cherche les modules, et `import model` fonctionne dans les tests. Sans lui : `ModuleNotFoundError: No module named 'model'` (vérifié).
- Il reconstruit aussi l'image Docker du module 4 sous le nom `stream-model-duration:v2` (`v2` est le *tag* : une étiquette de version de l'image), la lance et vérifie avec `test_docker.py` qu'elle répond : c'est le point de départ, qui marche.

**Étape 4 `[~8:14]` — Le problème : variables globales et fonction trop longue.**
Pour tester `prepare_features`, il faudrait écrire `import lambda_function` dans le test. Mais importer ce fichier **exécute sa zone 1** (§0.7) :

```text
 pytest ──► import lambda_function
                 │
                 ├─ boto3.client('kinesis') ────────► exige une région AWS configurée
                 ├─ mlflow.pyfunc.load_model(s3://mlflow-models-alexey/…) ──► réseau + identifiants
                 │                                                             + accès au bucket de l'auteur
                 └─ (seulement après) les fonctions à tester
```

**Récit.** Au moment de l'`import`, Python exécute tout le code qui n'est pas dans une fonction : il crée un client Kinesis (erreur sans région AWS) et télécharge le modèle depuis S3 (erreur sans réseau ni droits). Le test échoue avant même d'avoir commencé. De plus, `predict` utilise la variable globale `model` et `lambda_handler` fait tout d'un bloc : impossible de tester un morceau isolément.

**Étape 5 `[~11:07]` — Créer `model.py` et la classe `ModelService`.**
Il déplace la logique dans un nouveau fichier, `model.py`, autour d'une classe `ModelService` qui **reçoit** le modèle au lieu de le charger :

```python
class ModelService():
    def __init__(self, model, model_version=None, callbacks=None):
        self.model = model                     # ← le modèle est DONNÉ (injection de dépendances)
        self.model_version = model_version
        self.callbacks = callbacks or []       # ← voir l'étape 10

    def prepare_features(self, ride):
        features = {}
        features['PU_DO'] = '%s_%s' % (ride['PULocationID'], ride['DOLocationID'])
        features['trip_distance'] = ride['trip_distance']
        return features
```

Le constructeur est montré ici dans sa version de fin de vidéo : `model_version` et `callbacks` servent aux étapes 9 et 10.

Premier vrai test : `prepare_features` n'utilise pas le modèle, on peut donc créer le service avec `None` à la place.

```python
import model

def test_prepare_features():
    model_service = model.ModelService(None)      # pas besoin de modèle ici

    ride = {"PULocationID": 130, "DOLocationID": 205, "trip_distance": 3.66}

    actual_features = model_service.prepare_features(ride)
    expected_fetures = {"PU_DO": "130_205", "trip_distance": 3.66}   # (sic : « fetures »)

    assert actual_features == expected_fetures
```

Le schéma **actuel / attendu** (*actual / expected*) sera utilisé partout : on calcule le résultat réel, on écrit le résultat attendu, on les compare.

**Étape 6 `[~13:58]` — `init()` et un `lambda_function.py` minuscule.**
- Le chargement du modèle et la création du client Kinesis partent dans des **fonctions** de `model.py` : `load_model(run_id)` et `init(...)`. `init` assemble un `ModelService` prêt à l'emploi.
```python
def load_model(run_id):
    logged_model = f's3://mlflow-models-alexey/1/{run_id}/artifacts/model'   # ← encore en dur (→ 6.2)
    model = mlflow.pyfunc.load_model(logged_model)
    return model
```

- `lambda_function.py` ne fait plus que lire la configuration et **déléguer** : il devient un **adaptateur**, qui traduit l'appel d'AWS en appel de notre code, sans logique propre :

```python
import os
import model

PREDICTIONS_STREAM_NAME = os.getenv('PREDICTIONS_STREAM_NAME', 'ride_predictions')
RUN_ID = os.getenv('RUN_ID')
TEST_RUN = os.getenv('TEST_RUN', 'False') == 'True'

model_service = model.init(                  # ← exécuté une fois, au démarrage du conteneur
    prediction_stream_name=PREDICTIONS_STREAM_NAME,
    run_id=RUN_ID,
    test_run=TEST_RUN
)

def lambda_handler(event, context):          # ← exécuté à chaque lot
    return model_service.lambda_handler(event)
```

- Les tests unitaires n'importent **jamais** `lambda_function` : ils importent `model` et fabriquent eux-mêmes un `ModelService`.
- Le `Dockerfile` copie désormais aussi `model.py` : `COPY [ "lambda_function.py", "model.py", "./" ]`. Il reconstruit l'image et relance `test_docker.py` pour vérifier que rien n'est cassé.

**Étape 7 `[~17:01]` — Tester le décodage.**
Le décodage base64 devient une fonction à part, `base64_decode`, testée avec le `data` de l'événement du module 4 (§0.5). C'est une fonction **pure** : la même entrée donne toujours la même sortie, et elle ne modifie rien d'autre. Ce sont les plus faciles à tester. À ce stade, la longue chaîne base64 est écrite **dans** le test (elle partira dans `tests/data.b64` en 6.4).

```python
def base64_decode(encoded_data):                      # dans model.py
    decoded_data = base64.b64decode(encoded_data).decode('utf-8')
    ride_event = json.loads(decoded_data)
    return ride_event
```

```python
def test_base64_decode():                             # dans tests/model_test.py
    base64_input = "ewogICAgICAgICJyaWRlIjogewogICAg...Q=="     # (tronqué ici)
    actual_result = model.base64_decode(base64_input)
    expected_result = {
        "ride": {"PULocationID": 130, "DOLocationID": 205, "trip_distance": 3.66},
        "ride_id": 256,
    }
    assert actual_result == expected_result
```

**Étape 8 `[~19:42]` — Tester `predict` avec un faux modèle.**
`predict` a besoin d'un modèle. Plutôt que de charger le vrai, on en fabrique un faux qui a la même méthode `predict` :

```python
class ModelMock:
    def __init__(self, value):
        self.value = value

    def predict(self, X):
        n = len(X)
        return [self.value] * n          # renvoie toujours la même valeur

def test_predict():
    model_mock = ModelMock(10.0)
    model_service = model.ModelService(model_mock)     # ← on injecte le faux

    features = {"PU_DO": "130_205", "trip_distance": 3.66}

    actual_prediction = model_service.predict(features)
    expected_prediction = 10.0

    assert actual_prediction == expected_prediction
```

`ModelService` ne voit pas la différence : il appelle `.predict()`, c'est tout ce qu'il demande. C'est l'intérêt de l'injection de dépendances.

**Étape 9 `[~22:26]` — Tester `lambda_handler` en entier.**
`lambda_handler` devient une méthode de `ModelService`. Le test construit une enveloppe minimale (seul `data` est utile) et vérifie tout le parcours : décodage → features → prédiction → format du message.

```python
def test_lambda_handler():
    model_mock = ModelMock(10.0)
    model_version = 'Test123'
    model_service = model.ModelService(model_mock, model_version)

    event = {"Records": [{"kinesis": {"data": "ewogICAg...Q=="}}]}

    actual_predictions = model_service.lambda_handler(event)
    expected_predictions = {
        'predictions': [{
            'model': 'ride_duration_prediction_model',
            'version': model_version,
            'prediction': {'ride_duration': 10.0, 'ride_id': 256},
        }]
    }
    # ⚠ dans le commit de la vidéo, la ligne suivante manque : elle est ajoutée le lendemain (6.2)
    assert actual_predictions == expected_predictions
```

Remarque : **un test sans `assert` passe toujours**. Il vérifie seulement que le code ne plante pas.

**Étape 10 `[~25:11]` — Les callbacks : sortir la publication de la logique.**
Au module 4, la publication était écrite **dans** le handler (`if not TEST_RUN: kinesis_client.put_record(...)`). Désormais, `ModelService` reçoit une **liste de fonctions** et les appelle toutes après chaque prédiction, sans savoir ce qu'elles font :

```python
            for callback in self.callbacks:
                callback(prediction_event)
```

- En production : la liste contient une fonction qui publie dans Kinesis.
- Dans les tests : la liste est vide → rien n'est publié, sans toucher au reste du code.

**Étape 11 `[~28:03]` — La classe `KinesisCallback`.**
Le callback a besoin du client Kinesis et du nom du flux, mais `ModelService` ne lui passe que le message. Une petite classe **transporte** ces deux informations :

```python
class KinesisCallback():
    def __init__(self, kinesis_client, prediction_stream_name):
        self.kinesis_client = kinesis_client
        self.prediction_stream_name = prediction_stream_name

    def put_record(self, prediction_event):
        ride_id = prediction_event['prediction']['ride_id']
        self.kinesis_client.put_record(
            StreamName=self.prediction_stream_name,
            Data=json.dumps(prediction_event),
            PartitionKey=str(ride_id)
        )
```

`init()` la fabrique (sauf en mode test) et ajoute **sa méthode** à la liste, sans parenthèses : `callbacks.append(kinesis_callback.put_record)`. Sans parenthèses, on range la fonction pour plus tard ; avec, on l'appellerait tout de suite. Cette méthode « emporte » son objet (on parle de **méthode liée**) : quand `ModelService` l'appellera, elle connaîtra le client et le nom du flux.

**Étape 12 `[~31:02]` — Bilan et transition.** Les tests unitaires vérifient la logique, mais pas que l'image Docker se construit, que le modèle se charge ou que le RIE appelle bien la fonction : ce sera le rôle des tests d'intégration (6.2).

### Schéma : avant et après le refactoring

```text
 AVANT (module 4) : un seul fichier              APRÈS (fin de 6.1) : deux fichiers

 lambda_function.py                              lambda_function.py  (adaptateur, ~15 lignes)
 ┌───────────────────────────────────┐           ┌──────────────────────────────────────┐
 │ client Kinesis (global)           │           │ lit la config (os.getenv)            │
 │ modèle chargé depuis S3 (global)  │           │ model_service = model.init(...)  ──┐ │
 │ prepare_features, predict         │           │ lambda_handler → délègue ────────┐ │ │
 │ lambda_handler : TOUT             │           └──────────────────────────────────│─│─┘
 │  décode, prédit, publie           │                                              │ │
 └───────────────────────────────────┘           model.py                           │ │
                                                 ┌──────────────────────────────────▼─▼─┐
                                                 │ init() : charge le modèle, crée le   │
                                                 │          callback Kinesis, assemble  │
                                                 │ base64_decode()   (fonction pure)    │
                                                 │ ModelService(model, version,         │
                                                 │              callbacks)              │
                                                 │   prepare_features, predict,         │
                                                 │   lambda_handler → appelle callbacks │
                                                 │ KinesisCallback.put_record           │
                                                 └──────────────────────────────────────┘
```

**Récit.**

1. **Avant** : tout est dans `lambda_function.py`, et l'import exécute des appels à AWS.
2. **Après** : `lambda_function.py` ne fait que lire la configuration, appeler `model.init(...)` une fois, puis déléguer chaque lot à `model_service.lambda_handler`.
3. `init()` est le **seul** endroit qui touche à l'infrastructure : charger le modèle (MLflow/S3) et créer le client Kinesis.
4. `ModelService` ne contient que de la logique : il ne sait pas d'où vient son modèle ni ce que font ses callbacks. C'est ce qui le rend testable.

### Schéma : ce que fait `pytest tests/`

```text
 [Terminal A]  pytest ──► tests/model_test.py ──► import model ──► ModelService(ModelMock(10.0))
                          (un seul programme Python, tout en mémoire :
                           pas de Docker, pas d'AWS, pas de fichier modèle)
```

**Récit.** `pytest` est un **seul** programme Python. Il importe `model.py` (qui ne fait rien d'autre que définir des fonctions et des classes), fabrique des `ModelService` avec de faux modèles et appelle leurs méthodes directement. Aucun serveur, aucune requête réseau : les 4 tests s'exécutent en quelques secondes au plus, l'essentiel du temps servant à importer mlflow.

### Dans ton Codespace

Tu as déjà pytest (Partie 1). Trois fichiers à écrire, dans `mon-code/` :

- **`model.py`** : le fichier complet est donné plus bas, dans « État en fin de vidéo ». C'est la version de la vidéo, **bug compris** : ne le corrige pas encore, la vidéo 6.2 le trouvera.
- **`tests/model_test.py`** : la ligne `import model`, puis les blocs des étapes 5, 7, 8 et 9, dans cet ordre (`ModelMock` avant `test_predict`). Remplace chaque `"ewogICAg...Q=="` par la chaîne complète, que cette commande affiche sur une seule ligne : `cat ../code/tests/data.b64`.
- **`lambda_function.py`** : le bloc de l'étape 6, qui remplace tout le contenu copié du module 4.

```bash
# [Terminal A] dossier mon-code, environnement pipenv actif
mkdir tests
touch tests/__init__.py          # fichier vide, indispensable (voir étape 3)
touch tests/model_test.py model.py
cat ../code/tests/data.b64       # la chaîne base64 complète, à copier dans les tests
# … écris model.py, tests/model_test.py et lambda_function.py …

pytest tests/                    # → 4 passed
pytest tests/ -v                 # -v : le nom de chaque test et son résultat
```

Pour le panneau **Testing** de VS Code (étape 2) : ouvre `mon-code/` comme dossier de travail (*File → Open Folder…* → `/workspaces/mlops-zoomcamp/06-best-practices/mon-code`), sélectionne l'interpréteur pipenv, puis *Configure Python Tests* → pytest → `tests`. VS Code crée alors `mon-code/.vscode/settings.json`. Le terminal suffit si tu préfères.

Ajoute `model.py` à la ligne `COPY` du `Dockerfile`, comme à l'étape 6 :

```dockerfile
COPY [ "lambda_function.py", "model.py", "./" ]
```

**L'étape Docker de la vidéo, tu la sautes.** L'instructeur lance l'image avec un `RUN_ID` qui pointe vers **son** bucket S3 (`mlflow-models-alexey`), auquel tu n'as pas accès. Tu feras ce test en 6.2, avec un modèle local.

### État en fin de vidéo (commit `88783bd`)

| Fichier | État |
|---|---|
| `lambda_function.py` | Version courte (étape 6), déjà presque finale |
| `model.py` | `load_model`, `base64_decode`, `ModelService`, `KinesisCallback`, `init`. **Différences avec la version finale** : le chemin S3 est écrit en dur dans `load_model` (→ 6.2) ; `init` crée le client avec `boto3.client('kinesis')` directement (→ 6.3) ; `'%s_%s' %` au lieu d'une f-string et `class ModelService():` avec parenthèses (→ 6.4) ; et un **bug** dans `init` (→ 6.2) |
| `tests/model_test.py` | Les 4 tests, chaînes base64 écrites en dur ; `test_lambda_handler` sans `assert` final |
| `tests/__init__.py` | Vide |
| `test_docker.py` | Encore à la racine, et il se contente d'**afficher** la réponse |
| `Dockerfile` | Copie `model.py` en plus |
| `Pipfile` | `pytest` en `[dev-packages]` |
| `.vscode/settings.json` | Réglages pytest |

`model.py` complet en fin de vidéo (commit `88783bd` ; seuls les espaces en fin de ligne ont été retirés) :

```python
import os
import json
import boto3
import base64

import mlflow

# kinesis_client = boto3.client('kinesis')


def load_model(run_id):
    logged_model = f's3://mlflow-models-alexey/1/{run_id}/artifacts/model'
    # logged_model = f'runs:/{RUN_ID}/model'
    model = mlflow.pyfunc.load_model(logged_model)
    return model


def base64_decode(encoded_data):
    decoded_data = base64.b64decode(encoded_data).decode('utf-8')
    ride_event = json.loads(decoded_data)
    return ride_event


class ModelService():

    def __init__(self, model, model_version=None, callbacks=None):
        self.model = model
        self.model_version = model_version
        self.callbacks = callbacks or []

    def prepare_features(self, ride):
        features = {}
        features['PU_DO'] = '%s_%s' % (ride['PULocationID'], ride['DOLocationID'])
        features['trip_distance'] = ride['trip_distance']
        return features

    def predict(self, features):
        pred = self.model.predict(features)
        return float(pred[0])

    def lambda_handler(self, event):
        # print(json.dumps(event))

        predictions_events = []

        for record in event['Records']:
            encoded_data = record['kinesis']['data']
            ride_event = base64_decode(encoded_data)

            # print(ride_event)
            ride = ride_event['ride']
            ride_id = ride_event['ride_id']

            features = self.prepare_features(ride)
            prediction = self.predict(features)

            prediction_event = {
                'model': 'ride_duration_prediction_model',
                'version': self.model_version,
                'prediction': {
                    'ride_duration': prediction,
                    'ride_id': ride_id
                }
            }

            for callback in self.callbacks:
                callback(prediction_event)

            predictions_events.append(prediction_event)

        return {
            'predictions': predictions_events
        }


class KinesisCallback():

    def __init__(self, kinesis_client, prediction_stream_name):
        self.kinesis_client = kinesis_client
        self.prediction_stream_name = prediction_stream_name

    def put_record(self, prediction_event):
        ride_id = prediction_event['prediction']['ride_id']

        self.kinesis_client.put_record(
            StreamName=self.prediction_stream_name,
            Data=json.dumps(prediction_event),
            PartitionKey=str(ride_id)
        )


def init(prediction_stream_name: str, run_id: str, test_run: bool):
    model = load_model(run_id)


    callbacks = []

    if not test_run:
        kinesis_client = boto3.client('kinesis')
        kinesis_callback = KinesisCallback(
            kinesis_client,
            prediction_stream_name
        )
        callbacks.append(kinesis_callback.put_record)


    model_service = ModelService(model)
    return model_service
```

**Exercice** : trouve le bug de `init` avant de lire la vidéo 6.2. Pourquoi les 4 tests unitaires ne peuvent-ils pas le détecter ?

### Vérifie-toi

<details><summary>1. Pourquoi <code>test_prepare_features</code> peut-il écrire <code>ModelService(None)</code> ?</summary>
Parce que <code>prepare_features</code> n'utilise pas <code>self.model</code>. Le constructeur se contente de ranger ce qu'on lui donne, sans rien charger.
</details>

<details><summary>2. Pourquoi les tests unitaires n'importent-ils jamais <code>lambda_function</code> ?</summary>
L'importer exécuterait <code>model.init(...)</code> : chargement d'un vrai modèle (S3) et création d'un client Kinesis. Le test dépendrait du réseau et d'un compte AWS.
</details>

<details><summary>3. Réponse à l'exercice : le bug de <code>init</code></summary>
<code>ModelService(model)</code> ne transmet ni <code>model_version=run_id</code> ni <code>callbacks=callbacks</code>. La liste de callbacks, soigneusement construite juste au-dessus, est perdue : même en production, rien ne serait publié, et la version vaudrait <code>None</code>. Les tests unitaires ne le voient pas car ils construisent eux-mêmes leur <code>ModelService</code> et n'appellent jamais <code>init</code>. Il faut un test qui passe par <code>init</code> : c'est le test d'intégration de la vidéo 6.2.
</details>

<details><summary>4. Pourquoi <code>callbacks.append(kinesis_callback.put_record)</code> et pas <code>…put_record()</code> ?</summary>
Avec les parenthèses, la méthode serait appelée tout de suite, sans message : erreur. Sans parenthèses, on range la fonction, que <code>ModelService</code> appellera plus tard avec chaque prédiction.
</details>

---

## Vidéo 6.2 — Tests d'intégration avec docker-compose

> [Vidéo](https://www.youtube.com/watch?v=lBX0Gl7Z1ck) · fichiers : `integration-test/test_docker.py`, `run.sh`, `docker-compose.yaml`, `model/` · commit de l'instructeur : `dca082d` « integration tests » (28/06/2022).

### Le but

Les tests unitaires ne prouvent pas que l'**image Docker** se construit, que ses dépendances sont installées, que le modèle se charge ni que le RIE appelle bien la fonction. Un **test d'intégration** lance le vrai conteneur et l'interroge **de l'extérieur**, en HTTP, comme le ferait Lambda. La vidéo transforme `test_docker.py` en vrai test, supprime la dépendance à S3, puis automatise le tout dans un script.

### Ce que fait l'instructeur

**Étape 1 `[0:00]` — Rappel du refactoring de 6.1.**

**Étape 2 `[~2:41]` — Faire de `test_docker.py` un vrai test.**
Il crée le dossier **`integraton-test/`** (faute de frappe d'origine, corrigée en 2025 : le dossier s'appelle aujourd'hui `integration-test/`, mais le `Makefile` et la CI ont gardé l'ancienne orthographe, voir l'annexe C). Il y déplace `test_docker.py`, qui jusqu'ici se contentait d'**afficher** la réponse. Il ajoute la réponse **attendue** et la compare à la réponse réelle.

**Étape 3 `[~5:22]` — Comparer avec deepdiff.**
`pipenv install --dev deepdiff`. Pourquoi pas un simple `==` ? Le modèle prédit 21,29 minutes, et un `==` contre 21,3 échouerait. Surtout, `==` répond seulement vrai ou faux, alors que `DeepDiff` décrit **où** deux structures diffèrent :

```python
diff = DeepDiff(actual_response, expected_response, significant_digits=1)
print(f'diff={diff}')                  # → diff={}  si tout concorde
assert 'type_changes' not in diff      # un champ a changé de type (ex. nombre → texte)
assert 'values_changed' not in diff    # un champ a changé de valeur
```

`significant_digits=1` : chaque nombre est arrondi à une décimale avant la comparaison. 21,29 arrondi donne 21,3 : égal. (21,24 donnerait 21,2 : différent.)

**Étape 4 `[~8:03]` — Le test révèle le bug de `init`.**
La comparaison échoue : dans la réponse, `version` vaut `None` au lieu du `run_id` attendu. En cause, le bug de 6.1 : `ModelService(model)` ne transmettait ni la version ni les callbacks. Le commit de la vidéo le corrige :

```python
    model_service = ModelService(
        model=model,
        model_version=run_id,
        callbacks=callbacks
    )
```

Le même commit ajoute le `assert` qui manquait à la fin de `test_lambda_handler`. **Leçon** : `init` n'était couvert par aucun test unitaire ; il a fallu un test qui passe par le vrai point d'entrée pour le voir.

**Étape 5 `[~10:55]` — Supprimer la dépendance à S3.**
Un test ne doit pas dépendre d'un bucket distant (réseau, droits, et le modèle peut y changer). Il **télécharge** le dossier du modèle MLflow depuis son bucket dans `integraton-test/model/` : `MLmodel` (comment charger le modèle), `model.pkl` (le pipeline `DictVectorizer` + `RandomForestRegressor`), `conda.yaml`, `python_env.yaml`, `requirements.txt`.

**Étape 6 `[~13:42]` puis `[~16:24]` — Une variable pour l'emplacement du modèle.**
Nouvelle fonction dans `model.py`, appelée par `load_model` :

```python
def get_model_location(run_id):
    model_location = os.getenv('MODEL_LOCATION')

    if model_location is not None:          # ← si MODEL_LOCATION est définie : l'utiliser telle quelle
        return model_location

    model_bucket = os.getenv('MODEL_BUCKET', 'mlflow-models-alexey')     # ← sinon : S3, comme avant,
    experiment_id = os.getenv('MLFLOW_EXPERIMENT_ID', '1')               #   mais configurable

    model_location = f's3://{model_bucket}/{experiment_id}/{run_id}/artifacts/model'
    return model_location


def load_model(run_id):
    model_path = get_model_location(run_id)
    model = mlflow.pyfunc.load_model(model_path)
    return model
```

Il relance le conteneur à la main avec deux nouveautés (commande du `README.md` de `code/`) :
- `-v $(pwd)/model:/app/model` : un **volume**. Le dossier `model/` du Codespace apparaît **dans** le conteneur sous `/app/model`. Rien n'est copié : c'est le même dossier, vu des deux côtés.
- `-e MODEL_LOCATION="/app/model"` : `get_model_location` renvoie ce chemin et ne va plus sur S3.
- `-e RUN_ID="Test123"` : le modèle n'est plus cherché avec le `run_id`, qui devient une simple **étiquette** recopiée dans le champ `version` des prédictions.

**Étape 7 `[~19:14]` — Automatiser : `run.sh`.**
Construire l'image, démarrer le conteneur, lancer le test, arrêter le conteneur : quatre commandes qu'on ne veut pas taper à chaque fois. Il les écrit dans `integraton-test/run.sh` (version complète dans « État en fin de vidéo »).

**Étape 8 `[~22:00]` — Étiqueter l'image avec la date.**
Chaque image construite reçoit un tag du type `stream-model-duration:2022-06-28-09-41`. Pourquoi pas l'identifiant du commit git ? Parce que tant que tu n'as pas committé, tes modifications ne changent pas cet identifiant : deux images différentes porteraient le même nom.

**Étape 9 `[~24:54]` — Remplacer le long `docker run` par `docker-compose.yaml`.**
Les options `-p`, `-e` et `-v` passent dans un fichier **YAML** (un format texte de configuration, où l'indentation indique l'imbrication, comme en Python). `run.sh` lance `docker-compose up -d`, qui lit ce fichier.

**Étape 10 `[~27:46]` — Codes de sortie et gestion d'erreur.**
Tout programme renvoie un **code de sortie** : 0 = succès, autre chose = échec. `$?` contient celui de la dernière commande. Quand un `assert` échoue, Python sort avec le code 1. Le script mémorise ce code (`ERROR_CODE=$?`), affiche les logs du conteneur en cas d'échec, arrête **toujours** le conteneur, puis sort avec ce code. L'alternative `set -e` (« arrête le script à la première erreur ») est évoquée : elle arrêterait le script avant `docker-compose down` et laisserait le conteneur tourner.

**Étape 11 `[~30:37]` puis `[~33:14]` — Bilan et transition.** Le conteneur tourne avec `TEST_RUN=True` : la publication dans Kinesis, donc `KinesisCallback`, n'est **jamais** testée. Ce sera la vidéo 6.3.

### Schéma : le test d'intégration à la fin de 6.2

```text
 CODESPACE (hôte)                                  │  DOCKER
                                                   │
 run.sh ──① docker build ──────────────────────────┼──► image stream-model-duration:<date>
        ──② docker-compose up -d ──────────────────┼──► démarre le conteneur « backend »
                                                   │   ┌─ backend ─────────────────────────────┐
 integration-test/model/ ═══════ volume ═══════════╪═══╪══► /app/model                          │
                                                   │   │                                       │
 test_docker.py ──③ POST localhost:8080/… ─────────┼──►│ RIE :8080 ──► lambda_handler          │
                ◄──④ réponse HTTP : la prédiction ─┼───│   charge /app/model, prédit 21,29     │
                                                   │   │   TEST_RUN=True : aucune publication  │
 run.sh ──⑤ si échec : docker-compose logs         │   └───────────────────────────────────────┘
        ──⑥ docker-compose down ───────────────────┼──► arrête et supprime le conteneur
```

**Récit.**

1. `run.sh` construit l'image à partir du `Dockerfile` (dossier parent `..`) et lui donne un tag daté.
2. `docker-compose up -d` démarre le conteneur `backend` en arrière-plan (`-d`). Docker publie son port 8080 sur le port 8080 du Codespace, et fait apparaître le dossier `model/` sous `/app/model`. Le RIE se met à attendre des requêtes.
3. `test_docker.py`, qui tourne **dans le Codespace**, envoie l'enveloppe en `POST` à `localhost:8080`. Docker transmet la requête au conteneur. Le RIE appelle `lambda_handler` : au premier appel, `lambda_function.py` est importé et `model.init()` charge le modèle depuis `/app/model` (grâce à `MODEL_LOCATION`). La fonction prédit **21,29 minutes**. Comme `TEST_RUN=True`, aucun callback n'est créé : rien n'est publié.
4. Le RIE renvoie le `return` dans la réponse HTTP. `test_docker.py` le compare à la réponse attendue avec `DeepDiff`. Si les `assert` passent, il sort avec le code 0 ; sinon, avec le code 1.
5. En cas d'échec, `run.sh` affiche les logs du conteneur (les `print` et les erreurs Python) : c'est là qu'on trouve la cause.
6. Dans tous les cas, `docker-compose down` arrête et supprime le conteneur.

Qui joue quel rôle : `test_docker.py` joue le **producteur + le flux `ride_events` + le trigger** ; le RIE joue le **service Lambda** ; le dossier monté joue **S3**.

### Dans ton Codespace

**a) Préparer le dossier et le modèle.** Le bucket de l'auteur t'est inaccessible, mais le modèle de test est déjà dans le corrigé :

```bash
# [Terminal A] dossier mon-code, environnement pipenv actif
mkdir integration-test                       # orthographe correcte
mv test_docker.py integration-test/
cp -r ../code/integration-test/model integration-test/
ls integration-test/model                    # → MLmodel  conda.yaml  model.pkl  python_env.yaml  requirements.txt
```

**b) Corriger le `Dockerfile` (obligatoire).** À la ligne 4, `pip install pipenv` installe la dernière version de pipenv, qui refuse `mlflow==1.27.0` : `docker build` échouerait à la ligne `pipenv install --system --deploy`. Remplace la ligne 4 par :

```dockerfile
RUN pip install "pipenv==2023.12.1"
```

En une commande (le ` *` tolère l'espace qui traîne en fin de ligne dans le fichier du module 4) :

```bash
# [Terminal A] dossier mon-code
sed -i 's/^RUN pip install pipenv *$/RUN pip install "pipenv==2023.12.1"/' Dockerfile
grep pipenv Dockerfile | head -1          # → RUN pip install "pipenv==2023.12.1"
```

**c) Écrire le code et les deux nouveaux fichiers.**
- `model.py` : `get_model_location` et le nouveau `load_model` (étape 6). **Garde le bug d'`init` pour l'instant** si tu veux le voir apparaître (étape d), sinon corrige-le tout de suite (étape 4).
- `tests/model_test.py` : l'`assert` final de `test_lambda_handler`.
- `integration-test/test_docker.py` : garde le bloc `event = {...}` du fichier copié du module 4, et remplace la fin (`response = …` et `print(…)`) par la réponse attendue, `DeepDiff` et les `assert` (version complète dans « État en fin de vidéo »).
- `integration-test/docker-compose.yaml` et `integration-test/run.sh` : à créer, contenu complet dans « État en fin de vidéo ». Ils servent aux étapes e) et f).

**d) Tester à la main, comme la vidéo, avec deux terminaux.**

```bash
# [Terminal A] dossier mon-code
docker build -t stream-model-duration:v2 .   # plusieurs minutes la première fois
pytest tests/                                # → 4 passed (rien de cassé)
```

```bash
# [Terminal B] nouveau terminal — pas besoin de pipenv : on ne lance que Docker
cd /workspaces/mlops-zoomcamp/06-best-practices/mon-code/integration-test
docker run -it --rm \
    -p 8080:8080 \
    -e PREDICTIONS_STREAM_NAME="ride_predictions" \
    -e RUN_ID="Test123" \
    -e MODEL_LOCATION="/app/model" \
    -e TEST_RUN="True" \
    -e AWS_DEFAULT_REGION="eu-west-1" \
    -v $(pwd)/model:/app/model \
    stream-model-duration:v2
# → le terminal reste occupé : c'est le conteneur qui attend des requêtes
```

- `-it --rm` : mode interactif (tu vois les logs, `Ctrl+C` arrête) ; le conteneur est supprimé à l'arrêt.
- `\` en fin de ligne : la commande continue à la ligne suivante.
- `$(pwd)` : le dossier courant. D'où le `cd` : `$(pwd)/model` doit être le dossier du modèle.

```bash
# [Terminal A] dossier mon-code, environnement pipenv actif
cd integration-test
python test_docker.py
# → actual response: { "predictions": [ { …, "version": "Test123", "prediction": { "ride_duration": 21.29…, "ride_id": 256 } } ] }
# → diff={}
```

Si tu as gardé le bug de `init`, tu verras `diff={'type_changes': {"root['predictions'][0]['version']": {…, 'old_value': None, 'new_value': 'Test123'}}}` puis une `AssertionError` : c'est exactement l'étape 4 (`type_changes`, car `None` et `'Test123'` ne sont pas du même type). Arrête le conteneur (`Ctrl+C` dans le Terminal B), corrige `init`, **reconstruis l'image** (elle contient une copie de l'ancien `model.py`) et relance :

```bash
# [Terminal A] dossier mon-code/integration-test
cd ..                                        # retour dans mon-code, où est le Dockerfile
docker build -t stream-model-duration:v2 .
cd integration-test
# … relance le docker run dans le Terminal B, puis : …
python test_docker.py                        # → diff={}
```

Arrête ensuite le conteneur : `Ctrl+C` dans le Terminal B.

**e) Tester avec docker-compose, sans le script.** `docker-compose.yaml` contient `image: ${LOCAL_IMAGE_NAME}` : docker-compose remplace `${LOCAL_IMAGE_NAME}` par la variable d'environnement du même nom. **Il faut donc l'exporter avant** (sinon : image vide, erreur) :

```bash
# [Terminal A] dossier mon-code/integration-test, environnement pipenv actif
export LOCAL_IMAGE_NAME=stream-model-duration:v2
docker-compose up -d                  # → le conteneur du service backend démarre (« Started » ou « done »)
docker-compose ps                     # → le service backend est « Up »
python test_docker.py                 # → diff={}
docker-compose logs                   # les logs du conteneur (utile en cas d'échec)
docker-compose down                   # arrête et supprime
```

**f) Tester avec le script, comme à la fin de la vidéo.** `run.sh` fait tout seul l'`export`, le `build`, le `up`, le test et le `down` :

```bash
# [Terminal A] dossier mon-code/integration-test (où t'a laissé l'étape e), environnement pipenv actif
cd ..                                  # retour dans mon-code
chmod +x integration-test/run.sh       # rendre le script exécutable (une fois)
./integration-test/run.sh              # équivalent : bash integration-test/run.sh
echo $?                                # → 0 : tout est passé
```

### État en fin de vidéo (commit `dca082d`)

`integration-test/docker-compose.yaml` (première version : un seul service, pas de Kinesis) :

```yaml
services:
  backend:
    image: ${LOCAL_IMAGE_NAME}                 # le nom exporté par run.sh
    ports:
      - "8080:8080"                            # "port du Codespace:port du conteneur"
    environment:
      - PREDICTIONS_STREAM_NAME=ride_predictions
      - TEST_RUN=True                          # ← pas de publication (disparaîtra en 6.3)
      - RUN_ID=Test123
      - AWS_DEFAULT_REGION=eu-west-1
      - MODEL_LOCATION=/app/model
    volumes:
      - "./model:/app/model"                   # le volume, chemin relatif au fichier
```

`integration-test/run.sh` (première version) :

```bash
#!/usr/bin/env bash

cd "$(dirname "$0")"                          # se placer dans le dossier du script

LOCAL_TAG=`date +"%Y-%m-%d-%H-%M"`            # ex. 2026-09-30-14-05
export LOCAL_IMAGE_NAME="stream-model-duration:${LOCAL_TAG}"

docker build -t ${LOCAL_IMAGE_NAME} ..        # .. = le dossier parent, où est le Dockerfile

docker-compose up -d

sleep 1                                       # laisser le conteneur démarrer

pipenv run python test_docker.py

ERROR_CODE=$?                                 # code de sortie du test : 0 = OK

if [ ${ERROR_CODE} != 0 ]; then
    docker-compose logs
fi

docker-compose down

exit ${ERROR_CODE}                            # le script échoue si le test a échoué
```

- `#!/usr/bin/env bash` (le *shebang*) : dit au système d'exécuter ce fichier avec bash quand on tape `./run.sh`.
- `` `date …` `` (entre accents graves) : exécute `date` et met sa sortie à cette place.
- `pipenv run python …` : exécute une commande dans l'environnement pipenv, même si tu n'as pas fait `pipenv shell`.

`integration-test/test_docker.py` : l'événement est encore écrit **dans** le fichier (il partira dans `event.json` en 6.4).

```python
import json
import requests

from deepdiff import DeepDiff

event = {"Records": [{"kinesis": {"data": "ewogICAg...Q==", ...}, ...}]}     # (tronqué : l'enveloppe du §0.5)

url = 'http://localhost:8080/2015-03-31/functions/function/invocations'
actual_response = requests.post(url, json=event).json()
print('actual response:')
print(json.dumps(actual_response, indent=2))

expected_response = {
    'predictions': [{
        'model': 'ride_duration_prediction_model',
        'version': 'Test123',
        'prediction': {'ride_duration': 21.3, 'ride_id': 256},
    }]
}

diff = DeepDiff(actual_response, expected_response, significant_digits=1)
print(f'diff={diff}')

assert 'type_changes' not in diff
assert 'values_changed' not in diff
```

Autres changements : `model.py` gagne `get_model_location` et la correction de `init` ; `tests/model_test.py` gagne l'`assert` final ; `Pipfile` gagne `deepdiff`.

### Vérifie-toi

<details><summary>1. Pourquoi le test d'intégration trouve-t-il le bug de <code>init</code> alors que les tests unitaires ne le voient pas ?</summary>
Il passe par le vrai point d'entrée : le RIE importe <code>lambda_function</code>, qui appelle <code>model.init</code>. Les tests unitaires construisent directement un <code>ModelService</code> et ne passent jamais par <code>init</code>.
</details>

<details><summary>2. Que se passe-t-il si tu lances <code>docker-compose up</code> dans un nouveau terminal sans <code>export LOCAL_IMAGE_NAME=…</code> ?</summary>
docker-compose remplace <code>${LOCAL_IMAGE_NAME}</code> par une chaîne vide : il avertit que la variable n'est pas définie et ne sait pas quelle image lancer. Une variable exportée n'existe que dans le terminal où tu l'as exportée (§1.4).
</details>

<details><summary>3. À quoi sert <code>RUN_ID=Test123</code>, puisque le modèle est chargé depuis <code>/app/model</code> ?</summary>
À rien pour le chargement (<code>MODEL_LOCATION</code> est prioritaire). C'est une étiquette recopiée dans <code>version</code> ; le test vérifie qu'elle arrive bien dans la réponse.
</details>

<details><summary>4. Pourquoi ne pas écrire <code>set -e</code> en tête de <code>run.sh</code> ?</summary>
Le script s'arrêterait dès l'échec du test, sans exécuter <code>docker-compose down</code> : le conteneur continuerait de tourner et occuperait le port 8080.
</details>

---

## Vidéo 6.3 — Tester les services cloud avec LocalStack

> [Vidéo](https://www.youtube.com/watch?v=9yMO86SYvuI) · fichiers : `docker-compose.yaml`, `run.sh`, `test_kinesis.py`, `model.py` · commit de l'instructeur : `0dcf58a` « kinesis test » (30/06/2022).

### Le but

Tester le dernier morceau : la **publication** de la prédiction dans Kinesis, donc `KinesisCallback`. Sans compte AWS et sans frais, grâce à **LocalStack**, un faux AWS qui tourne dans un conteneur.

### La notion clé : l'*endpoint*

Un client AWS (l'AWS CLI, boto3) envoie ses requêtes à une **adresse** (*endpoint*). Par défaut, c'est celle d'Amazon, par exemple `https://kinesis.eu-west-1.amazonaws.com`. On peut la remplacer :

- AWS CLI : option `--endpoint-url=http://localhost:4566` ;
- boto3 : paramètre `boto3.client('kinesis', endpoint_url='http://localhost:4566')`.

LocalStack répond sur le port 4566 **avec les mêmes API qu'AWS**. Le code ne voit pas la différence, et aucune requête ne part chez Amazon.

### Ce que fait l'instructeur

**Étape 1 `[0:00]` — Rappel.** Tests unitaires, test d'intégration avec Docker… et ce qui manque : la connexion à Kinesis.

**Étape 2 `[~2:35]` — Ajouter LocalStack à `docker-compose.yaml`.**

```yaml
  kinesis:                              # nom du service = son nom sur le réseau Docker
    image: localstack/localstack
    ports:
      - "4566:4566"                     # le port unique de LocalStack, pour tous les services AWS
    environment:
      - SERVICES=kinesis                # ne démarrer que le faux Kinesis
```

Il démarre ce seul service : `docker-compose up kinesis`.

**Étape 3 `[~5:21]` — Parler à LocalStack avec l'AWS CLI.**

```bash
aws --endpoint-url=http://localhost:4566 kinesis list-streams          # → aucun flux
aws --endpoint-url=http://localhost:4566 \
    kinesis create-stream \
    --stream-name ride_predictions \
    --shard-count 1
aws --endpoint-url=http://localhost:4566 kinesis list-streams          # → ride_predictions
```

Sans `--endpoint-url`, la même commande `list-streams` interroge le vrai AWS : le flux n'y est pas. **C'est ici qu'est défini le flux `ride_predictions` du test local** : un nom et 1 shard, rien d'autre (§0.4).

**Étape 4 — Rendre l'endpoint configurable dans le code.** Nouvelle fonction dans `model.py`, appelée par `init` à la place de `boto3.client('kinesis')` :

```python
def create_kinesis_client():
    endpoint_url = os.getenv('KINESIS_ENDPOINT_URL')

    if endpoint_url is None:                       # variable absente → le vrai AWS
        return boto3.client('kinesis')

    return boto3.client('kinesis', endpoint_url=endpoint_url)    # sinon → cette adresse (LocalStack)
```

Même principe que `get_model_location` en 6.2 : **une variable d'environnement choisit l'infrastructure**, le code reste le même partout.

**Étape 5 `[~8:14]` — Configurer le conteneur `backend`.** Trois changements dans `docker-compose.yaml` :

- `TEST_RUN=True` **disparaît** : `TEST_RUN` vaut alors `False`, le callback Kinesis est créé, et la fonction **publie**. C'est ce qu'on veut tester.
- `KINESIS_ENDPOINT_URL=http://kinesis:4566/` : `kinesis` est le **nom du service** LocalStack. Sur le réseau que docker-compose crée, chaque conteneur joint les autres par leur nom de service.
- `PREDICTIONS_STREAM_NAME=${PREDICTIONS_STREAM_NAME}` : le nom du flux vient maintenant de la variable exportée par `run.sh`.

Dans `run.sh` : `export PREDICTIONS_STREAM_NAME="ride_predictions"` en haut, et la commande `create-stream` juste après `docker-compose up -d`.

**Étape 6 — Vérifier à la main que la prédiction est bien arrivée.** Après `test_docker.py`, il lit le flux avec l'AWS CLI : `get-shard-iterator` (le marque-page), puis `get-records` (commandes dans « Dans ton Codespace »).

**Étape 7 `[~10:56]` — Automatiser la lecture : `test_kinesis.py`.** Le même enchaînement, en Python avec boto3, suivi d'une comparaison. Le fichier complet (version de la vidéo, commit `0dcf58a`, avant les retouches de style de 6.4 ; annotations `#` ajoutées) :

```python
import os
import boto3
import json

from pprint import pprint

from deepdiff import DeepDiff


kinesis_endpoint = os.getenv('KINESIS_ENDPOINT_URL', "http://localhost:4566")
kinesis_client = boto3.client('kinesis', endpoint_url=kinesis_endpoint)

stream_name = os.getenv('PREDICTIONS_STREAM_NAME', 'ride_predictions')
shard_id = 'shardId-000000000000'                  # le nom du premier (et seul) shard


shard_iterator_response = kinesis_client.get_shard_iterator(
    StreamName=stream_name,
    ShardId=shard_id,
    ShardIteratorType='TRIM_HORIZON',              # depuis le plus ancien message
)

shard_iterator_id = shard_iterator_response['ShardIterator']


records_response = kinesis_client.get_records(
    ShardIterator=shard_iterator_id,
    Limit=1
)


records = records_response['Records']
pprint(records)


assert len(records) == 1                           # il y a bien UN message


actual_record = json.loads(records[0]['Data'])     # boto3 a déjà décodé le base64 : ce sont des octets JSON
pprint(actual_record)

expected_record = {
    'model': 'ride_duration_prediction_model',
    'version': 'Test123',
    'prediction': {
        'ride_duration': 21.3,
        'ride_id': 256
    }
}

diff = DeepDiff(actual_record, expected_record, significant_digits=1)
print(f'diff={diff}')

assert 'values_changed' not in diff
assert 'type_changes' not in diff


print('all good')
```

**Étape 8 `[~13:52]` — Compléter `run.sh`.** `test_kinesis.py` s'exécute après `test_docker.py`, avec la même gestion d'erreur (logs, `down`, sortie avec le code d'erreur).

**Étape 9 `[~16:41]` — Bilan du bloc « tests ».** La suite : la qualité du code, puis `make`.

**Ajouts faits après la vidéo** (visibles dans le code final, pas dans la vidéo) :
- `AWS_ACCESS_KEY_ID=abc` et `AWS_SECRET_ACCESS_KEY=xyz` dans le service `backend` (proposition d'un participant, 27/07/2022). boto3 refuse d'envoyer une requête sans identifiants (`Unable to locate credentials`), même vers LocalStack, qui ne les vérifie pas.
- `sleep 5` au lieu de `sleep 1`, et le `if [[ -z "${GITHUB_ACTIONS}" ]]` en tête de `run.sh` : ajoutés par Sejal Vaidya pour la CI (vidéo 6.12).

### Schéma : le test d'intégration complet

```text
 CODESPACE (hôte)                        │  RÉSEAU DOCKER (créé par docker-compose)
                                         │
 ① docker-compose up -d ─────────────────┼──► démarre les conteneurs kinesis et backend
                                         │
                                         │  ┌─ kinesis (LocalStack) :4566 ─────┐
 ② aws … create-stream ──────────────────┼─►│ flux « ride_predictions »        │◄─────┐
   (vers localhost:4566)                 │  │   [ la prédiction ]              │      │
                                         │  └──────────────────────────────────┘      │
                                         │                                            │  ④ put_record
 integration-test/model/ ══ volume ══════┼═════════════╗                              │  (vers kinesis:4566)
                                         │  ┌─ backend ─▼──────────────────────┐      │
 ③ test_docker.py                        │  │ RIE :8080                        │      │
   POST localhost:8080/… ────────────────┼─►│  └► lambda_handler : charge      │      │
                                         │  │     /app/model, prédit 21,29,    │      │
                                         │  │     appelle le callback ─────────┼──────┘
   ◄── ⑤ réponse : la prédiction ────────┼──│                                  │
                                         │  └──────────────────────────────────┘
 ⑥ test_kinesis.py : get_records ────────┼─► kinesis (via localhost:4566) : relit le flux
   ◄── le message ───────────────────────┼──
```

**Récit.** Le schéma se lit de haut en bas, dans l'ordre des numéros.

1. **Démarrer.** `docker-compose up -d` lance deux conteneurs sur un réseau privé : `kinesis` (LocalStack, qui attend sur le port 4566) et `backend` (ton service ; son RIE attend sur le port 8080). Les ports publiés `"4566:4566"` et `"8080:8080"` les rendent joignables depuis le Codespace par `localhost`.
2. **Créer la boîte aux lettres.** Le programme `aws` (dans le Codespace) demande à `localhost:4566` de créer le flux `ride_predictions`. Docker transmet la requête à LocalStack, qui crée un flux **vide**.
3. **Envoyer une course.** `test_docker.py` envoie l'enveloppe en `POST` à `localhost:8080`. Le RIE appelle `lambda_handler`. Au premier appel, `init()` charge le modèle depuis `/app/model` et, puisque `TEST_RUN` est faux, crée un client Kinesis pointé vers `http://kinesis:4566` (grâce à `KINESIS_ENDPOINT_URL`). La fonction prédit 21,29 minutes.
4. **Publier.** Le **callback** (`KinesisCallback.put_record`) envoie la prédiction à `kinesis:4566` : LocalStack la range dans `ride_predictions`. C'est le morceau que la vidéo veut tester.
5. **Répondre.** La fonction renvoie aussi la prédiction ; le RIE la transmet à `test_docker.py` dans la réponse HTTP. `test_docker.py` vérifie le **calcul**.
6. **Relire le flux.** `test_kinesis.py` demande à `localhost:4566` le plus ancien message de `ride_predictions`, reçoit celui déposé à l'étape 4 et vérifie son contenu : il vérifie la **publication**.

Enfin, `docker-compose down` arrête et supprime les deux conteneurs ; le flux disparaît avec LocalStack.

**Pourquoi deux adresses pour le même LocalStack ?** Depuis le **Codespace**, on passe par le port publié : `localhost:4566`. Depuis le conteneur `backend`, `localhost` désignerait `backend` **lui-même** : il faut le nom du service, `kinesis:4566`.

**Tes trois questions, dans ce test** :

| Question | Réponse ici |
|---|---|
| Où est défini le flux ? | Le flux d'entrée **n'existe pas**. Le flux de sortie `ride_predictions` est créé par `run.sh` (`aws … create-stream`), à partir du nom exporté en haut du script. |
| Comment la course arrive-t-elle à la fonction ? | `test_docker.py` l'envoie directement au RIE, en HTTP. Il remplace le producteur, le flux d'entrée et le trigger. |
| Où la fonction envoie-t-elle la prédiction ? | Dans `ride_predictions`, **dans LocalStack**, via `KinesisCallback.put_record` → `kinesis:4566`. `test_kinesis.py` la relit. |

Le nom `ride_predictions` doit être **le même** à trois endroits : `run.sh` (création du flux), la variable `PREDICTIONS_STREAM_NAME` passée au conteneur (où publier), et `test_kinesis.py` (où lire, avec la même valeur par défaut).

### Dans ton Codespace

**a) Épingler la version de LocalStack (obligatoire).** Depuis le 23/03/2026, l'image `localstack/localstack` sans numéro de version exige un compte LocalStack et un jeton. Sans jeton, le conteneur s'arrête aussitôt (code de sortie 55, *License activation failed*). La version `4.14.0` est la dernière publiée avant ce changement ([source](https://ddz.dev/blog/localstack-license-activation-failed/)). Dans ton `docker-compose.yaml` :

```yaml
    image: localstack/localstack:4.14.0
```

(Non testé dans un Codespace. Autre solution : créer un compte LocalStack gratuit et ajouter `- LOCALSTACK_AUTH_TOKEN=${LOCALSTACK_AUTH_TOKEN}` dans `environment`.)

**b) Écrire le code** : `create_kinesis_client` (étape 4) et son appel dans `init` à la place de `boto3.client('kinesis')`, `integration-test/test_kinesis.py` (étape 7, fichier complet), et les ajouts à `run.sh` (version complète dans « État en fin de vidéo »). Ton `integration-test/docker-compose.yaml` complet, avec la version épinglée et les identifiants factices :

```yaml
services:
  backend:
    image: ${LOCAL_IMAGE_NAME}
    ports:
      - "8080:8080"
    environment:
      - PREDICTIONS_STREAM_NAME=${PREDICTIONS_STREAM_NAME}
      - RUN_ID=Test123
      - AWS_DEFAULT_REGION=eu-west-1
      - MODEL_LOCATION=/app/model
      - KINESIS_ENDPOINT_URL=http://kinesis:4566/
      - AWS_ACCESS_KEY_ID=abc
      - AWS_SECRET_ACCESS_KEY=xyz
    volumes:
      - "./model:/app/model"
  kinesis:
    image: localstack/localstack:4.14.0
    ports:
      - "4566:4566"
    environment:
      - SERVICES=kinesis
```

**c) Reconstruire l'image.** `model.py` a changé : l'image construite en 6.2 contient l'ancienne version.

```bash
# [Terminal A] dossier mon-code, environnement pipenv actif
docker build -t stream-model-duration:v3 .
```

**d) Les variables du terminal.** Le programme `aws` et `test_kinesis.py` tournent **dans le Codespace**, pas dans un conteneur : ils ont besoin d'une région et d'identifiants, même factices (LocalStack ne les vérifie pas, mais sans eux les clients refusent de partir : `You must specify a region` / `Unable to locate credentials`). docker-compose, lui, a besoin de `LOCAL_IMAGE_NAME` et `PREDICTIONS_STREAM_NAME` pour remplir le fichier YAML.

```bash
# [Terminal A] dossier mon-code, environnement pipenv actif
cd integration-test
export LOCAL_IMAGE_NAME=stream-model-duration:v3     # l'image à lancer (docker-compose.yaml)
export PREDICTIONS_STREAM_NAME=ride_predictions      # le nom du flux (docker-compose.yaml, test_kinesis.py)
export AWS_DEFAULT_REGION=eu-west-1                  # pour aws et boto3 dans le Codespace
export AWS_ACCESS_KEY_ID=abc                         # identifiants factices
export AWS_SECRET_ACCESS_KEY=xyz
env | grep -E "LOCAL_IMAGE|PREDICTIONS|AWS_"         # vérifier : les 5 variables apparaissent
```

Ces cinq variables disparaissent si tu fermes le terminal (§1.4).

**e) Refaire la vidéo à la main.**

```bash
# [Terminal A] même terminal (les variables ci-dessus sont définies)
docker-compose up -d kinesis                         # d'abord LocalStack seul
docker-compose logs kinesis                          # attendre la ligne « Ready. »

aws --endpoint-url=http://localhost:4566 kinesis list-streams
# → { "StreamNames": [] }
aws --endpoint-url=http://localhost:4566 kinesis create-stream \
    --stream-name ${PREDICTIONS_STREAM_NAME} \
    --shard-count 1
aws --endpoint-url=http://localhost:4566 kinesis list-streams
# → { "StreamNames": [ "ride_predictions" ] }

docker-compose up -d                                 # démarre aussi backend
python test_docker.py                                # → diff={}
```

Lire le flux avec l'AWS CLI (étape 6) :

```bash
# [Terminal A] même terminal
SHARD=shardId-000000000000
SHARD_ITERATOR=$(aws --endpoint-url=http://localhost:4566 kinesis get-shard-iterator \
    --shard-id ${SHARD} \
    --shard-iterator-type TRIM_HORIZON \
    --stream-name ${PREDICTIONS_STREAM_NAME} \
    --query 'ShardIterator' \
    --output text)
echo ${SHARD_ITERATOR}                               # → une longue chaîne : le marque-page

aws --endpoint-url=http://localhost:4566 kinesis get-records \
    --shard-iterator ${SHARD_ITERATOR} \
    --query 'Records[0].Data' \
    --output text | base64 --decode
# → {"model": "ride_duration_prediction_model", "version": "Test123", "prediction": {"ride_duration": 21.29…, "ride_id": 256}}
```

- `--query 'ShardIterator'` extrait un seul champ de la réponse JSON ; `--output text` l'affiche sans guillemets, ce qui est plus propre pour le ranger dans une variable (le `README.md` de l'instructeur s'en passe).
- `Data` arrive en base64 dans la sortie de l'AWS CLI (c'est du JSON), d'où `| base64 --decode`. Le symbole `|` (« pipe ») envoie la sortie d'une commande en entrée de la suivante.

Puis la version automatisée, et le nettoyage :

```bash
# [Terminal A] même terminal
python test_kinesis.py                               # → … all good
docker-compose down
```

**Facultatif, la preuve qu'on ne touche pas au vrai AWS** : `aws kinesis list-streams`, sans `--endpoint-url`, part chez Amazon, qui refuse les identifiants factices (`UnrecognizedClientException`).

**f) Avec le script.** Il enchaîne tout seul : `export` de `PREDICTIONS_STREAM_NAME`, `build`, `up`, `create-stream`, les deux tests, `down`. Les identifiants factices et la région, en revanche, doivent être exportés dans ton terminal (étape d), car `aws` et `test_kinesis.py` en héritent.

```bash
# [Terminal A] dossier mon-code/integration-test (où t'a laissé l'étape e), variables AWS_* de l'étape d exportées
cd ..                                               # retour dans mon-code
./integration-test/run.sh
echo $?                                              # → 0
```

Si la création du flux échoue au premier lancement, LocalStack n'était pas encore prêt : passe `sleep 1` à `sleep 5` (comme la version finale) et relance.

### État en fin de vidéo (commit `0dcf58a`)

`docker-compose.yaml` :

```yaml
services:
  backend:
    image: ${LOCAL_IMAGE_NAME}
    ports:
      - "8080:8080"
    environment:
      - PREDICTIONS_STREAM_NAME=${PREDICTIONS_STREAM_NAME}   # ← vient de run.sh
      - RUN_ID=Test123
      - AWS_DEFAULT_REGION=eu-west-1
      - MODEL_LOCATION=/app/model
      - KINESIS_ENDPOINT_URL=http://kinesis:4566/            # ← nouveau ; TEST_RUN a disparu
      # (ajout du 27/07/2022, absent de la vidéo : AWS_ACCESS_KEY_ID=abc, AWS_SECRET_ACCESS_KEY=xyz)
    volumes:
      - "./model:/app/model"
  kinesis:                                                   # ← nouveau service
    image: localstack/localstack                             # ← toi : localstack/localstack:4.14.0
    ports:
      - "4566:4566"
    environment:
      - SERVICES=kinesis
```

`run.sh` : la version finale du dépôt, **moins** trois ajouts postérieurs (le `if` sur `GITHUB_ACTIONS` et `sleep 5`, vidéo 6.12 ; la construction conditionnelle de l'image, vidéo 6.6).

```bash
#!/usr/bin/env bash

cd "$(dirname "$0")"

LOCAL_TAG=`date +"%Y-%m-%d-%H-%M"`
export LOCAL_IMAGE_NAME="stream-model-duration:${LOCAL_TAG}"
export PREDICTIONS_STREAM_NAME="ride_predictions"          # ← nouveau

docker build -t ${LOCAL_IMAGE_NAME} ..

docker-compose up -d

sleep 1

aws --endpoint-url=http://localhost:4566 \
    kinesis create-stream \
    --stream-name ${PREDICTIONS_STREAM_NAME} \
    --shard-count 1                                         # ← nouveau : créer le flux de sortie

pipenv run python test_docker.py

ERROR_CODE=$?

if [ ${ERROR_CODE} != 0 ]; then
    docker-compose logs
    docker-compose down
    exit ${ERROR_CODE}
fi

pipenv run python test_kinesis.py                           # ← nouveau : relire le flux

ERROR_CODE=$?

if [ ${ERROR_CODE} != 0 ]; then
    docker-compose logs
    docker-compose down
    exit ${ERROR_CODE}
fi

docker-compose down
```

`model.py` gagne `create_kinesis_client`. `test_kinesis.py` est créé.

### Vérifie-toi

<details><summary>1. Pourquoi retirer <code>TEST_RUN=True</code> du conteneur <code>backend</code> ?</summary>
Avec <code>TEST_RUN=True</code>, <code>init</code> ne crée aucun callback : rien n'est publié, et <code>KinesisCallback</code> n'est jamais exécuté. On veut justement tester la publication.
</details>

<details><summary>2. Dans <code>docker-compose.yaml</code>, pourquoi <code>http://kinesis:4566</code> et pas <code>http://localhost:4566</code> ?</summary>
Le client Kinesis tourne dans le conteneur <code>backend</code>. Pour lui, <code>localhost</code>, c'est <code>backend</code> lui-même. Les autres conteneurs se joignent par leur nom de service sur le réseau Docker.
</details>

<details><summary>3. Tu ouvres un nouveau terminal et lances <code>python test_kinesis.py</code>. Erreur : <code>NoRegionError</code>. Pourquoi ?</summary>
Les <code>export</code> de l'étape d n'existent que dans le terminal où tu les as tapés. Le nouveau terminal ne connaît pas <code>AWS_DEFAULT_REGION</code>, et boto3 refuse de créer un client sans région.
</details>

<details><summary>4. Que prouve <code>test_kinesis.py</code> que <code>test_docker.py</code> ne prouve pas ?</summary>
<code>test_docker.py</code> vérifie la valeur renvoyée (le calcul). <code>test_kinesis.py</code> vérifie que la prédiction a réellement été publiée dans le flux, au bon format (la publication).
</details>

---

## Vidéo 6.4 — Qualité du code : pylint, black, isort

> [Vidéo](https://www.youtube.com/watch?v=uImvWE-iSDQ) · fichiers : `pyproject.toml`, `tests/data.b64`, `integration-test/event.json`, et retouches partout · commits de l'instructeur : `fadc8fc` « added linting and fixed some of the the issues » (sic) puis `c4d8c8a` « linting and formatting » (30/06/2022).

### Le but

Les tests vérifient que le code **fait** ce qu'il doit. Les outils de qualité vérifient qu'il est **lisible** et signalent des erreurs probables avant même de l'exécuter. Trois outils, dans l'ordre de la vidéo :

| Outil | Rôle | Modifie tes fichiers ? |
|---|---|---|
| **pylint** | *Linter* : lit le code **sans l'exécuter** et signale erreurs et mauvaises pratiques (import inutile, variable jamais utilisée, ligne trop longue…). Donne une note sur 10. | Non, il signale |
| **black** | *Formateur* : réécrit la mise en page (espaces, retours à la ligne, guillemets) selon un style unique, non négociable. | Oui |
| **isort** | Trie les `import` et les regroupe (bibliothèque standard, puis paquets installés, puis ton code). | Oui |

### Ce que fait l'instructeur

**Étape 1 `[0:00]` — Qu'est-ce que le linting ?** Une analyse **statique** : le code est lu, pas exécuté.

**Étape 2 `[~2:36]` — Lancer pylint.** `pipenv install --dev pylint` (la version est épinglée dans le `Pipfile` : `pylint = "==2.14.4"`), puis :

```bash
pylint model.py                  # un fichier
pylint --recursive=y .           # tout le dossier et ses sous-dossiers
```

Chaque message a la forme `fichier:ligne:colonne: CODE: explication (nom-du-message)`. Sur le code tel qu'il est à la fin de la vidéo 6.3, pylint produit une cinquantaine de messages et une note d'environ **6/10** (mesuré pour ce cours avec pylint 2.14.4).

**Étape 3 `[~5:20]` — Voir les messages dans VS Code.** Il active le linting dans `.vscode/settings.json` (`"python.linting.pylintEnabled": true`, `"python.linting.enabled": true`) : les problèmes apparaissent soulignés dans l'éditeur.

**Étapes 4 et 5 `[~8:08]` puis `[~10:48]` — Choisir les règles dans `pyproject.toml`.** Certaines règles ne conviennent pas au projet. On les désactive **pour tout le projet** dans un fichier de configuration, `pyproject.toml`, lu automatiquement par pylint (et plus tard par black et isort) :

```toml
[tool.pylint.messages_control]

disable = [
    "missing-function-docstring",     # pas de docstring (texte d'explication) sur une fonction
    "missing-final-newline",          # pas de saut de ligne à la fin du fichier
    "missing-class-docstring",
    "missing-module-docstring",
    "invalid-name",                   # noms comme X, n, url, shard_id (voir le tableau)
    "too-few-public-methods"          # une classe avec une seule méthode publique
]
```

**Étapes 6 et 7 `[~13:36]` puis `[~16:30]` — Corriger le reste.** Voici **tous** les types de messages que pylint affiche sur le code de fin de 6.3 (liste mesurée), et ce que la vidéo en fait :

| Message pylint | Où | Traitement dans la vidéo |
|---|---|---|
| `missing-*-docstring` (C0114, C0115, C0116) | partout | Désactivé (`pyproject.toml`) |
| `missing-final-newline` (C0304) | plusieurs fichiers | Désactivé |
| `invalid-name` (C0103) | `X` et `n` dans `ModelMock`, `url` et `shard_id` dans les scripts de test | Désactivé |
| `too-few-public-methods` (R0903) | `KinesisCallback`, `ModelMock` | Désactivé |
| `consider-using-f-string` (C0209) | `'%s_%s' % (…)` dans `prepare_features` | **Corrigé** : `f"{ride['PULocationID']}_{ride['DOLocationID']}"` |
| `unused-argument` (W0613) | `context` dans `lambda_handler` | Désactivé **localement** : `# pylint: disable=unused-argument`, sur sa propre ligne en tête de la fonction. `context` est imposé par Lambda, on ne peut pas le supprimer |
| `line-too-long` (C0301) | les longues chaînes base64 dans les tests et `test_docker.py` | **Corrigé** : les données partent dans des fichiers (ci-dessous) |
| `duplicate-code` (R0801) | `test_docker.py` et `test_kinesis.py` ont des blocs presque identiques (le dictionnaire attendu) | Désactivé en tête des deux fichiers : `# pylint: disable=duplicate-code` |
| `wrong-import-order` (C0411) | `import boto3` au milieu des imports de la bibliothèque standard | Corrigé plus tard par **isort** (étape 9) |
| `trailing-whitespace` (C0303) | espaces en fin de ligne | Corrigé plus tard par **black** (étape 8) |

Le déplacement des données, en détail :

- `tests/data.b64` : une ligne, la chaîne base64 de la course. Les tests la lisent avec une petite fonction :

```python
from pathlib import Path

def read_text(file):
    test_directory = Path(__file__).parent            # le dossier de CE fichier de test : tests/

    with open(test_directory / file, 'rt', encoding='utf-8') as f_in:
        return f_in.read().strip()                    # .strip() : enlève le saut de ligne final

def test_base64_decode():
    base64_input = read_text('data.b64')
    ...
```

  **Pourquoi `Path(__file__).parent` ?** Un chemin relatif comme `'data.b64'` est cherché à partir du **dossier courant**, celui d'où tu lances pytest (`mon-code/`, ou `tests/`, ou la racine du dépôt…). `__file__` est le chemin du fichier Python lui-même : le chemin obtenu ne dépend plus de l'endroit d'où tu lances la commande. `encoding='utf-8'` évite un autre message pylint (`unspecified-encoding`).

- `integration-test/event.json` : l'enveloppe complète du §0.5. `test_docker.py` la charge au lieu de l'écrire en dur :

```python
with open('event.json', 'rt', encoding='utf-8') as f_in:
    event = json.load(f_in)
```

  Ici, le chemin est relatif au dossier courant : ça marche parce que `run.sh` fait `cd` dans `integration-test/` avant de lancer le test.

**Étape 8 `[~19:19]` à `[~24:52]` — black.** `pipenv install --dev black`, puis d'abord **voir** sans modifier, ensuite appliquer :

```bash
black --diff . | less            # les changements proposés ; q pour quitter less
black .                          # appliquer
```

Réglages ajoutés à `pyproject.toml` :

```toml
[tool.black]
line-length = 88                     # longueur maximale d'une ligne
target-version = ['py39']            # écrire du code compatible Python 3.9
skip-string-normalization = true     # garder les guillemets simples '…' (black mettrait des "…")
```

Ce que black change sur ce projet : il supprime les espaces en fin de ligne, recolle sur une ligne les dictionnaires courts (`'prediction': {'ride_duration': prediction, 'ride_id': ride_id}`), et remplace `class ModelService():` par `class ModelService:` (vérifié avec black 22.6.0).

**Étape 9 `[~27:38]` — isort.** `pipenv install --dev isort`, puis `isort --diff .` et `isort .`. Réglages :

```toml
[tool.isort]
multi_line_output = 3                # imports trop longs : un nom par ligne, entre parenthèses
length_sort = true                   # trier par LONGUEUR de ligne, pas par ordre alphabétique
```

D'où l'ordre, curieux au premier regard, en tête de `model.py` : `import os`, `import json`, `import base64` (du plus court au plus long), puis une ligne vide, puis `import boto3`, `import mlflow`.

**Étape 10 `[~30:43]` — L'ordre des commandes, et la suite.** isort, puis black, puis pylint, puis les tests. La vidéo suivante les fera lancer automatiquement par git.

### Schéma : ce que fait chaque outil

```text
 tes fichiers .py
        │
        ▼
  ┌──────────┐
  │  isort   │  réécrit les imports                    ─┐
  └────┬─────┘                                          │
       ▼                                                │
  ┌──────────┐                                          │  tous les trois lisent
  │  black   │  réécrit la mise en page                 ├─ pyproject.toml
  └────┬─────┘                                          │  (dans le dossier courant)
       ▼                                                │
  ┌──────────┐                                          │
  │  pylint  │  lit sans modifier ; messages + note     ─┘
  └────┬─────┘
       ▼
  ┌──────────┐
  │  pytest  │  vérifie que rien n'est cassé
  └──────────┘
```

**Récit.**

1. **isort** range les imports. Il passe en premier car black pourrait ensuite remettre en forme les lignes d'import qu'il a produites.
2. **black** refait la mise en page de chaque fichier. Après lui, le style ne se discute plus.
3. **pylint** lit le résultat et signale ce qui reste. Il ne modifie rien : les corrections sont à faire à la main, ou à désactiver en connaissance de cause.
4. **pytest** vérifie que rien n'a été cassé.

Les trois outils de qualité lisent `pyproject.toml`. pylint 2.14 ne le trouve **que dans le dossier courant** : lance-les depuis `mon-code/` (vérifié pour le cours précédent : lancé depuis `tests/`, pylint ne voit plus les règles désactivées).

### Dans ton Codespace

Les trois outils sont déjà installés (Partie 1).

```bash
# [Terminal A] dossier mon-code, environnement pipenv actif
pylint --recursive=y .                    # avant : ~6/10 et une cinquantaine de messages
# … crée pyproject.toml (section pylint), fais les corrections du tableau,
#   crée tests/data.b64 et integration-test/event.json …
cp ../code/tests/data.b64 tests/                          # ou recopie-les depuis le corrigé
cp ../code/integration-test/event.json integration-test/
pylint --recursive=y .                    # il reste wrong-import-order et trailing-whitespace

# … ajoute les sections [tool.black] et [tool.isort] à pyproject.toml …
isort --diff .                            # voir
isort .                                   # appliquer
black --diff . | less                     # voir ; q pour quitter
black .                                   # appliquer
pylint --recursive=y .                    # → Your code has been rated at 10.00/10
pytest tests/                             # → 4 passed
```

Si la note n'est pas 10/10, lis le nom du message entre parenthèses et retrouve-le dans le tableau.

**VS Code aujourd'hui.** Les deux lignes `python.linting.*` de `settings.json` ne font plus rien depuis 2023 : le linting est passé dans des extensions séparées. Installe l'extension **Pylint** (éditeur : Microsoft). Et VS Code ne lit le `.vscode/settings.json` de `mon-code/` que si **`mon-code/` est le dossier ouvert** (*File → Open Folder…*).

### État en fin de vidéo (commits `fadc8fc` et `c4d8c8a`)

- `pyproject.toml` : les trois sections, dans leur version finale.
- `tests/data.b64` et `integration-test/event.json` : créés. `tests/model_test.py` utilise `read_text`.
- `test_docker.py` charge `event.json` ; `test_docker.py` et `test_kinesis.py` commencent par `# pylint: disable=duplicate-code`.
- `model.py` : f-string, imports triés, `class ModelService:` sans parenthèses. À ce stade, `model.py` est **identique à sa version finale**.
- `lambda_function.py` : `# pylint: disable=unused-argument`. Version finale.
- `Pipfile` : `pylint`, `black`, `isort` en `[dev-packages]`.
- Un fichier `plan.md` apparaît, la liste des sujets du module, cochée au fur et à mesure.

### Vérifie-toi

<details><summary>1. Pourquoi désactiver <code>unused-argument</code> dans la fonction plutôt que dans <code>pyproject.toml</code> ?</summary>
Parce que c'est une exception justifiée à un seul endroit (<code>context</code>, imposé par Lambda). Désactivé pour tout le projet, le message ne signalerait plus les vrais arguments oubliés ailleurs.
</details>

<details><summary>2. Tu lances <code>pytest</code> depuis la racine du dépôt : <code>pytest 06-best-practices/mon-code/tests</code>. <code>read_text('data.b64')</code> trouve-t-il le fichier ?</summary>
Oui : le chemin est construit à partir de <code>Path(__file__).parent</code>, le dossier du fichier de test, et non du dossier courant.
</details>

<details><summary>3. Pourquoi lancer isort avant black ?</summary>
isort réécrit les lignes d'import ; black passe ensuite pour que la mise en page finale soit la sienne. Dans l'autre ordre, isort pourrait défaire une partie du travail de black.
</details>

---

## Vidéo 6.5 — Hooks git pre-commit

> [Vidéo](https://www.youtube.com/watch?v=lmMZ7Axk2T8) · fichiers : `.pre-commit-config.yaml`, `.gitignore` · commit de l'instructeur : `b56359f` « best practices continued » (01/07/2022).

### Le but

Tu finiras par oublier de lancer isort, black, pylint et pytest avant de committer. Un **hook git** les lance à ta place, automatiquement, **à chaque `git commit`**, et **refuse le commit** si l'un d'eux échoue. Le code cassé ou mal formaté n'entre plus dans l'historique.

### Les notions

- **Hook git** (« crochet ») : un script que git exécute lui-même à certains moments. Ils se trouvent dans le dossier caché `.git/hooks/` du dépôt. Le hook **`pre-commit`** s'exécute juste **avant** la création d'un commit : s'il se termine par un code d'erreur (différent de 0), git **annule** le commit.
- **`pre-commit`** (l'outil, un paquet Python) : il écrit ce script pour toi et le pilote à partir d'un fichier de configuration, `.pre-commit-config.yaml`. Chaque vérification y est un *hook* ; beaucoup sont téléchargés depuis des dépôts GitHub.
- **Racine du dépôt** : le dossier qui contient `.git/`. pre-commit s'exécute **toujours depuis la racine**.

### Ce que fait l'instructeur

**Étape 1 `[0:00]` — Pourquoi des hooks.**

**Étape 2 `[~2:38]` — Un dépôt git pour ce seul dossier.** Le dossier de travail de l'instructeur est à l'intérieur du dépôt du cours, dont la racine est bien plus haut. Pour la démonstration, il crée un dépôt git **dans** `code/` : `git init`. Ainsi, la racine du dépôt est `code/`, où se trouvent `tests/` et `pyproject.toml`. Puis `pipenv install --dev pre-commit`.

**Étape 3 `[~5:19]` — Générer une configuration de départ.**

```bash
pre-commit sample-config > .pre-commit-config.yaml
```

`sample-config` affiche un exemple ; `>` l'écrit dans le fichier. C'est pourquoi le fichier final commence par ces deux lignes de commentaires et utilise `rev: v3.2.0` : c'est ce que produit pre-commit 2.19 (vérifié ; seule l'indentation diffère, l'instructeur l'a retouchée) :

```yaml
# See https://pre-commit.com for more information
# See https://pre-commit.com/hooks.html for more hooks
repos:
- repo: https://github.com/pre-commit/pre-commit-hooks   # dépôt GitHub qui fournit les hooks
  rev: v3.2.0                                             # sa version (un tag git)
  hooks:
    - id: trailing-whitespace        # supprime les espaces en fin de ligne
    - id: end-of-file-fixer          # ajoute le saut de ligne final manquant
    - id: check-yaml                 # vérifie que les fichiers .yaml sont valides
    - id: check-added-large-files    # refuse l'ajout d'un fichier de plus de 500 Ko
```

Puis il installe le hook dans git :

```bash
pre-commit install                   # → pre-commit installed at .git/hooks/pre-commit
```

**Étape 4 `[~8:04]` — Premier commit : les hooks corrigent… et refusent.**
- Il crée un `.gitignore` contenant `__pycache__` (les fichiers compilés que Python crée tout seul ne doivent pas entrer dans le dépôt).
- `git add .` puis `git commit -m "…"`. Les hooks s'exécutent : `trailing-whitespace` et `end-of-file-fixer` **modifient** des fichiers et affichent `Failed`. Le commit est refusé : « j'ai corrigé des fichiers, vérifie-les ».
- `git add .` à nouveau (pour inclure les corrections), puis `git commit` : cette fois, tout est `Passed` et le commit est créé.

Le commit de la vidéo porte la trace de ce passage : il ajoute un saut de ligne final à une dizaine de fichiers (`event.json`, `data.b64`, `pyproject.toml`, `run.sh`…).

**Étape 5 `[~10:47]` — Ajouter les outils de la vidéo 6.4.** Deux sortes de hooks :

```yaml
- repo: https://github.com/pycqa/isort       # hooks téléchargés : pre-commit installe l'outil
  rev: 5.10.1                                #   dans SON propre environnement isolé
  hooks:
    - id: isort
      name: isort (python)
- repo: https://github.com/psf/black
  rev: 22.6.0
  hooks:
    - id: black
      language_version: python3.9
- repo: local                                # hook « local » : rien n'est téléchargé
  hooks:
    - id: pylint
      name: pylint
      entry: pylint                          # la commande lancée…
      language: system                       # …prise dans TON environnement (celui de pipenv)
      types: [python]                        # seulement sur les fichiers .py
      args: [
        "-rn", # Only display messages       # pas de rapport détaillé
        "-sn", # Don't display the score     # pas de note
        "--recursive=y"
      ]
- repo: local
  hooks:
    - id: pytest-check
      name: pytest-check
      entry: pytest
      language: system
      pass_filenames: false                  # ne pas donner à pytest la liste des fichiers modifiés
      always_run: true                       # lancer même si aucun .py n'a changé
      args: [
        "tests/"
      ]
```

Pourquoi pylint et pytest en `local` ? Ils doivent voir **tous les paquets du projet** (mlflow, boto3…) pour analyser les imports et exécuter les tests. Un environnement isolé ne les aurait pas. Conséquence : ces deux hooks ne marchent que si l'environnement pipenv est actif au moment du `git commit`.

**Étape 6 `[~13:57]` — Vérifier.** `pre-commit run --all-files` lance tous les hooks sans committer. Il casse volontairement quelque chose (un test, un import) pour montrer qu'un commit est alors refusé.

**Étape 7 `[~16:42]` — Transition** vers les Makefiles.

### Schéma : ce qui se passe quand tu tapes `git commit`

```text
 toi ──① git commit -m "…" ──► git
                                │ ② avant de créer le commit, exécute .git/hooks/pre-commit
                                ▼
                         pre-commit (lit .pre-commit-config.yaml)
                                │ ③ lance chaque hook sur les fichiers ajoutés (git add)
                                ▼
          trailing-whitespace → end-of-file-fixer → check-yaml → check-added-large-files
                 → isort → black → pylint → pytest tests/
                                │
                 ┌──────────────┴───────────────┐
         ④ tous « Passed »              ④ au moins un « Failed »
                 │                              │
       ⑤ git crée le commit          ⑤ le commit n'est PAS créé ;
                                        les fichiers corrigés par les
                                        hooks restent modifiés :
                                        git add, puis recommence
```

**Récit.**

1. Tu tapes `git commit`.
2. Avant de créer quoi que ce soit, git exécute le script `.git/hooks/pre-commit`, écrit par `pre-commit install`.
3. Ce script lance l'outil pre-commit, qui lit `.pre-commit-config.yaml` et exécute chaque hook dans l'ordre du fichier, sur les fichiers que tu as ajoutés avec `git add` (sauf pytest, lancé dans tous les cas grâce à `always_run`).
4. Chaque hook affiche `Passed`, `Failed` ou `Skipped` (aucun fichier concerné).
5. Si tout passe, git crée le commit. Sinon, il l'annule. Les hooks qui **corrigent** (espaces, saut de ligne final, isort, black) ont déjà modifié tes fichiers : vérifie, `git add`, recommence.

### Dans ton Codespace : un bac à sable

**Ne fais pas `git init` dans `mon-code/`.** Ton dossier est dans ton fork, un dépôt git dont la racine est `/workspaces/mlops-zoomcamp`. Un dépôt git **dans** un dépôt git (*embedded repository*) empêcherait le fork de suivre les fichiers de `mon-code/`, qui ne seraient plus sauvegardés sur GitHub. Et si tu utilisais le dépôt du fork, pre-commit s'exécuterait depuis sa racine : `pytest tests/` ne trouverait pas le dossier `tests/` (constaté pour le cours précédent).

Fais donc comme l'instructeur, mais dans une **copie** hors du fork (recette testée pour le cours précédent) :

```bash
# [Terminal A] environnement conda mlops-06 actif (sors d'abord du pipenv shell de mon-code : exit)
cp -r /workspaces/mlops-zoomcamp/06-best-practices/mon-code ~/m6-precommit
cd ~/m6-precommit
pipenv install --dev --python "$(which python)"      # pipenv crée un environnement PAR dossier
pipenv shell
cp /workspaces/mlops-zoomcamp/06-best-practices/code/.pre-commit-config.yaml .
sed -i 's/rev: 5.10.1/rev: 5.12.0/' .pre-commit-config.yaml   # correctif isort (ci-dessous)
echo "__pycache__" > .gitignore

git init                                             # la racine du dépôt = ce dossier
pre-commit install                                   # → pre-commit installed at .git/hooks/pre-commit
git add .
pre-commit run --all-files                           # 1er passage : quelques « Failed » (fichiers corrigés)
git add .
pre-commit run --all-files                           # 2e passage : tout « Passed »
git commit -m "premier commit"                       # les hooks tournent à nouveau, puis le commit est créé
```

- **Le correctif isort** : la version `5.10.1` indiquée dans le fichier ne s'installe plus aujourd'hui (`RuntimeError: The Poetry configuration is invalid`). La `5.12.0` fonctionne. `sed -i 's/avant/après/' fichier` remplace un texte dans un fichier.
- **`git add .` avant `--all-files`** : `--all-files` ne traite que les fichiers **suivis par git**. Dans un dépôt neuf, sans `git add`, tous les hooks sauf pytest affichent `Skipped`.
- Si git demande ton nom et ton e-mail au premier commit : `git config user.name "Pierre"` et `git config user.email "…"` (dans ce dépôt seulement).
- Le premier passage télécharge les hooks depuis GitHub : compte une ou deux minutes.

**Pour voir un refus** :

```bash
# [Terminal A] dossier ~/m6-precommit, environnement pipenv actif
sed -i 's/expected_prediction = 10.0/expected_prediction = 11.0/' tests/model_test.py   # casser un test
git add .
git commit -m "test cassé"            # → pytest-check … Failed ; aucun commit créé
git checkout HEAD -- tests/model_test.py   # annuler la modification (fichier ET git add), depuis le dernier commit
```

Ce bac à sable ne sera pas poussé sur GitHub : c'est voulu, il ne sert qu'à pratiquer.

### État en fin de vidéo (commit `b56359f`)

- `.pre-commit-config.yaml` : version finale (celle de l'étape 5).
- `.gitignore` : `__pycache__`.
- `Pipfile` : `pre-commit` en `[dev-packages]`.
- Une dizaine de fichiers reçoivent un saut de ligne final (le passage de `end-of-file-fixer`).

### Vérifie-toi

<details><summary>1. Pourquoi les hooks pylint et pytest sont-ils déclarés en <code>repo: local</code> avec <code>language: system</code> ?</summary>
Pour être exécutés avec l'environnement du projet (pipenv), qui contient mlflow, boto3, etc. Dans un environnement isolé créé par pre-commit, pylint signalerait des imports introuvables et les tests ne pourraient pas importer <code>model</code>.
</details>

<details><summary>2. Tu fais <code>git commit</code>, black reformate un fichier et le commit est refusé. Que fais-tu ?</summary>
Regarder la modification (<code>git diff</code>), l'ajouter (<code>git add</code>), puis refaire <code>git commit</code>. Au second passage, black n'a plus rien à changer.
</details>

<details><summary>3. Les hooks remplacent-ils la CI ?</summary>
Non. Ils sont installés sur ta machine seulement, et <code>git commit --no-verify</code> les contourne. La CI (vidéo 6.12) relance une partie de ces vérifications (pytest, pylint, plus le test d'intégration) sur GitHub, pour tout le monde.
</details>

---

## Vidéo 6.6 — Makefile et `make`

> [Vidéo](https://www.youtube.com/watch?v=F6DZdvbRZQQ) · fichiers : `Makefile`, `integration-test/run.sh`, `scripts/publish.sh` · commits de l'instructeur : `dc7598b` « linting and makefiles (started) », `adaff82` « makefile finished », `b2c6066` « make setup » (02/07/2022).

### Le but

Le projet compte maintenant beaucoup de commandes : `isort .`, `black .`, `pylint --recursive=y .`, `pytest tests/`, `docker build …`, `run.sh`… Un **Makefile** leur donne des **noms courts** (`make test`, `make build`) et déclare leurs **dépendances** : « avant de construire l'image, lance les contrôles et les tests ».

### Les notions

`make` est un outil de 1976, présent sur presque toutes les machines Linux. Il lit un fichier nommé `Makefile` dans le dossier courant. Ce fichier contient des **cibles** (*targets*) :

```makefile
cible: dépendance1 dépendance2
	commande 1
	commande 2
```

- `make cible` exécute d'abord les dépendances (qui sont elles-mêmes des cibles), puis les commandes de la cible.
- **Les commandes doivent commencer par une tabulation**, pas par des espaces. Sinon : `Makefile:5: *** missing separator. Stop.`
- `make` affiche chaque commande avant de l'exécuter, et s'arrête à la première qui échoue.

### Ce que fait l'instructeur

**Étape 1 `[0:00]` — Pourquoi make.** Taper la même suite de commandes à chaque fois est source d'oublis.

**Étape 2 `[~2:43]` — Première version : construire, tester, publier avec des dépendances** (commit `dc7598b`).

```makefile
LOCAL_TAG=`date +"%Y-%m-%d-%H-%M"`
LOCAL_IMAGE_NAME="stream-model-duration:${LOCAL_TAG}"

test:
	pytest tests/

quality_checks:
	isort .
	black .
	pylint --recursive=y .

build: quality_checks test               # avant build : quality_checks, puis test
	docker build -t ${LOCAL_IMAGE_NAME} ..

integration_test: build
	bash integraton-test/run.sh

publish: build
```

**Étapes 3 et 4 `[~5:34]` puis `[~8:19]` — Deux problèmes de nom d'image, et leur correction.**

*Problème 1 : l'image testée n'est pas l'image construite.* `make integration_test` exécute `build` (qui construit une image), puis `run.sh`… qui **reconstruit** sa propre image, avec son propre tag. On construit deux fois, et on ne teste pas l'image produite par `make build`.

*Correction* : `make` **transmet** le nom de l'image au script, et le script ne construit plus que si on ne lui a rien transmis :

```makefile
integration_test: build
	LOCAL_IMAGE_NAME=${LOCAL_IMAGE_NAME} bash integraton-test/run.sh
```

```bash
# en tête de run.sh (version finale)
if [ "${LOCAL_IMAGE_NAME}" == "" ]; then          # rien reçu : lancé seul, sans make
    LOCAL_TAG=`date +"%Y-%m-%d-%H-%M"`
    export LOCAL_IMAGE_NAME="stream-model-duration:${LOCAL_TAG}"
    echo "LOCAL_IMAGE_NAME is not set, building a new image with tag ${LOCAL_IMAGE_NAME}"
    docker build -t ${LOCAL_IMAGE_NAME} ..
else                                              # reçu de make : l'image existe déjà
    echo "no need to build image ${LOCAL_IMAGE_NAME}"
fi
```

`VAR=valeur commande` passe la variable à cette seule commande (§1.4, règle 3).

*Problème 2 : le tag peut changer en cours de route.* Dans la première version, `` LOCAL_TAG=`date …` `` ne calcule rien : `make` recopie le texte **avec** les accents graves dans chaque commande, et c'est le shell qui exécute `date`… **à chaque commande**. Si `docker build` dure trois minutes, la commande suivante calcule un autre tag et ne trouve pas l'image. Vérifié pour ce cours avec un petit Makefile : deux commandes successives obtiennent deux valeurs différentes.

*Correction* :

```makefile
LOCAL_TAG:=$(shell date +"%Y-%m-%d-%H-%M")
LOCAL_IMAGE_NAME:=stream-model-duration:${LOCAL_TAG}
```

- `$(shell …)` : c'est `make` qui exécute la commande ;
- `:=` : la valeur est calculée **une seule fois**, au démarrage de `make`. Toutes les cibles d'un même `make` utilisent le même tag.

Dernière correction : `docker build … ..` devient `docker build … .`, car le `Makefile` est dans le même dossier que le `Dockerfile`.

**Étape 5 `[~10:55]` — La cible `publish`.** Elle dépend de `build` et `integration_test`, et lance `scripts/publish.sh`. Ce script n'est qu'un emplacement réservé (`echo "publishing image ${LOCAL_IMAGE_NAME} to ECR..."`) : la vraie publication arrivera avec la CD (vidéo 6.13).

**Étape 6 `[~13:46]` — La cible `setup`,** pour préparer le projet en une commande sur une nouvelle machine (commit `b2c6066`) :

```makefile
setup:
	pipenv install --dev
	pre-commit install
```

### Le `Makefile` final

```makefile
LOCAL_TAG:=$(shell date +"%Y-%m-%d-%H-%M")
LOCAL_IMAGE_NAME:=stream-model-duration:${LOCAL_TAG}

test:
	pytest tests/

quality_checks:
	isort .
	black .
	pylint --recursive=y .

build: quality_checks test
	docker build -t ${LOCAL_IMAGE_NAME} .

integration_test: build
	LOCAL_IMAGE_NAME=${LOCAL_IMAGE_NAME} bash integraton-test/run.sh   # faute d'origine : integration-test (annexe C)

publish: build integration_test
	LOCAL_IMAGE_NAME=${LOCAL_IMAGE_NAME} bash scripts/publish.sh

setup:
	pipenv install --dev
	pre-commit install
```

### Schéma : ce que déclenche `make publish`

```text
 make publish
   │  calcule LOCAL_IMAGE_NAME une fois : stream-model-duration:2026-09-30-14-05
   │
   ├─① quality_checks : isort . → black . → pylint --recursive=y .
   ├─② test           : pytest tests/
   ├─③ build          : docker build -t stream-model-duration:2026-09-30-14-05 .
   ├─④ integration_test : LOCAL_IMAGE_NAME=… bash integration-test/run.sh
   │                     (run.sh ne reconstruit pas : il reçoit le nom de l'image)
   └─⑤ publish        : LOCAL_IMAGE_NAME=… bash scripts/publish.sh
```

**Récit.**

1. `make` lit le `Makefile`, calcule le tag une fois, puis remonte les dépendances : `publish` dépend de `build` et `integration_test` ; `build` dépend de `quality_checks` et `test`.
2. Il exécute les cibles dans l'ordre : les contrôles de qualité (qui **modifient** tes fichiers : isort et black réécrivent), puis les tests unitaires.
3. Il construit l'image avec le tag calculé.
4. Il lance le test d'intégration **sur cette image-là**, en lui passant son nom.
5. Il lance la publication.

`integration_test` dépend aussi de `build`, mais `make` n'exécute chaque cible **qu'une fois** par appel. Si une étape échoue (un test rouge, une note pylint trop basse), `make` s'arrête là : on ne publie jamais une image non testée.

### Dans ton Codespace

**a) Écrire le `Makefile`** dans `mon-code/`, avec des **tabulations**. Dans VS Code, la barre d'état en bas à droite affiche « Spaces: 4 » ou « Tab Size: 4 » : pour un fichier nommé `Makefile`, VS Code utilise normalement des tabulations. Ou copie le corrigé et corrige-le :

```bash
# [Terminal A] dossier mon-code, environnement pipenv actif
cp ../code/Makefile .
sed -i 's#integraton-test/run.sh#integration-test/run.sh#' Makefile   # la faute de frappe d'origine (annexe C)
mkdir -p scripts
cp ../code/scripts/publish.sh scripts/
cat -A Makefile | grep "pytest"             # → ^Ipytest tests/$   (^I = une tabulation : c'est bon)
```

**b) Mettre à jour `run.sh`** avec la construction conditionnelle (étape 3). Passe aussi `sleep 1` à `sleep 5`.

Attention à une variable restée d'avant : si tu as fait `export LOCAL_IMAGE_NAME=stream-model-duration:v3` dans ce terminal (vidéo 6.3), le nouveau `run.sh`, lancé seul, ne reconstruira **plus** l'image et testera l'ancienne. Supprime-la :

```bash
# [Terminal A]
unset LOCAL_IMAGE_NAME            # supprime la variable de ce terminal
echo "[$LOCAL_IMAGE_NAME]"        # → []  (vide)
```

**c) Lancer les cibles.**

```bash
# [Terminal A] dossier mon-code, environnement pipenv actif
make test                                   # → pytest tests/ … 4 passed
make quality_checks                         # → isort, black, pylint 10.00/10
make build                                  # → contrôles, tests, puis docker build

# le test d'intégration a besoin des variables AWS factices (vidéo 6.3, étape d)
export AWS_DEFAULT_REGION=eu-west-1 AWS_ACCESS_KEY_ID=abc AWS_SECRET_ACCESS_KEY=xyz
make integration_test                       # → … no need to build image stream-model-duration:… ; all good
make publish                                # → … publishing image stream-model-duration:… to ECR...
```

**d) Ne lance pas `make setup` dans ton fork.** Sa seconde commande, `pre-commit install`, installe le hook dans le dépôt git du fork (racine `/workspaces/mlops-zoomcamp`). Deux cas, vérifiés avec pre-commit 2.19 :
- depuis `mon-code/` (pas encore de `.pre-commit-config.yaml` à cet endroit) : chaque `git commit` du fork échoue ensuite avec « No .pre-commit-config.yaml file was found » ;
- depuis `code/` (qui a ce fichier) : le hook s'exécute depuis la racine du fork, où `pytest tests/` ne trouve pas le dossier `tests/`, et échoue aussi.

Si c'est déjà fait : `pre-commit uninstall`, depuis le même dossier. Dans le bac à sable `~/m6-precommit` de la vidéo 6.5, en revanche, `make setup` est sans danger.

### État en fin de vidéo

- `Makefile` : version finale (ci-dessus), avec la faute `integraton-test`.
- `integration-test/run.sh` : construction conditionnelle de l'image. Il ne lui manquera plus que les ajouts de la CI (vidéo 6.12).
- `scripts/publish.sh` : l'emplacement réservé.
- `plan.md` : les six premiers sujets sont cochés. **Fin de la partie A.** Tout ce qui suit demande un compte AWS.

### Vérifie-toi

<details><summary>1. Tu lances <code>make build</code> et pylint signale un problème. L'image est-elle construite ?</summary>
Non. <code>build</code> dépend de <code>quality_checks</code> ; pylint sort avec un code d'erreur, et <code>make</code> s'arrête à la première commande qui échoue.
</details>

<details><summary>2. Pourquoi <code>:=</code> et <code>$(shell …)</code> plutôt que <code>=</code> et des accents graves ?</summary>
Avec les accents graves, <code>date</code> est exécuté par le shell à chaque commande : le tag peut changer entre <code>docker build</code> et le test. Avec <code>:=</code> et <code>$(shell …)</code>, <code>make</code> calcule le tag une fois au démarrage.
</details>

<details><summary>3. Tu lances <code>bash integration-test/run.sh</code> directement, sans make. Une image est-elle construite ?</summary>
Oui : <code>LOCAL_IMAGE_NAME</code> est vide (à moins que tu l'aies exporté dans ce terminal !), donc le script construit sa propre image avec un tag daté.
</details>

---

# Partie B — L'infrastructure en fichiers : Terraform (Sejal Vaidya)

> Vidéos [6.7 / 6B.1](https://www.youtube.com/watch?v=zRcLgT7Qnio), [6.8 / 6B.2](https://www.youtube.com/watch?v=-6scXrFcPNk), [6.9 / 6B.3](https://www.youtube.com/watch?v=JVydd1K6R7M), [6.10 / 6B.4](https://www.youtube.com/watch?v=YWao0rnqVoI) · dossiers : `infrastructure/`, `scripts/` · commits de l'instructrice : `f3cf3dc` « demo-code » (16/07/2022), retouché par `6789e73` (29/07/2022).

## Avant de commencer : coût et choix

- Il faut **ton propre compte AWS**, et l'infrastructure **coûte de l'argent tant qu'elle existe**. Ordre de grandeur, surtout dû aux flux Kinesis : 4 shards (2 par flux) avec une conservation de 48 h, soit environ 0,14 $ de l'heure, ou 3 à 4 $ par jour (tarifs US-East, eu-west-1 un peu plus cher ; vérifie sur la [page de prix de Kinesis](https://aws.amazon.com/kinesis/data-streams/pricing/)). **Détruis tout à la fin de chaque séance** (`terraform destroy`, vidéo 6.10).
- Tu peux aussi **regarder sans faire** : le plus important est de comprendre comment Terraform remplace les clics du module 4.
- La présentatrice change : Sejal Vaidya. Son code n'a pas été reconstitué commit par commit comme celui d'Alexey : il arrive en **deux blocs**, `f3cf3dc` (Terraform, 16/07/2022) puis `6789e73` (CI/CD, 29/07/2022), qui retouche aussi le Terraform. L'ordre ci-dessous suit les repères de temps des vidéos.
- **Les extraits de cette partie montrent l'état final des fichiers**, donc avec les retouches de `6789e73` : `force_destroy = true` (module S3), `force_delete = true` (module ECR), le nom du bucket du modèle dans `stg.tfvars` (`stg-mlflow-models-code-owners`, au lieu de `stg-mlflow-models`), le nom du rôle IAM (`iam_${var.lambda_function_name}`), la seconde moitié de `deploy_manual.sh` et la ligne `KINESIS_STREAM_OUTPUT` de `test_cloud_e2e.sh`. Les vidéos 6.9 et 6.10 peuvent donc montrer quelques lignes différentes.
- **Staging et production** : deux copies de la même infrastructure. Le *staging* (préfixe `stg_`) sert à tester en conditions réelles ; la *production* (préfixe `prod_`) sert les vrais utilisateurs. Même code Terraform, fichiers de valeurs différents.

## Pourquoi Terraform ? Les clics du module 4 deviennent des fichiers

Au module 4, l'infrastructure a été créée **à la main dans la console** (§0.3) : impossible à relire, à refaire à l'identique, ou à dupliquer pour un environnement de test. **Terraform** est un outil d'*Infrastructure as Code* : tu **décris** l'infrastructure voulue dans des fichiers `.tf` ; Terraform compare avec ce qui existe, **affiche** les différences (`plan`), puis les **applique** (`apply`).

| Clic du module 4 (§0.3) | Équivalent Terraform au module 6 |
|---|---|
| 1. Rôle IAM `lambda-kinesis-role` + policy de lecture Kinesis | `modules/lambda/iam.tf` : `aws_iam_role` + policies |
| 2. Créer la fonction Lambda | `modules/lambda/main.tf` : `aws_lambda_function` |
| 3. Créer le flux `ride_events` | `main.tf` : module `source_kinesis_stream` (`modules/kinesis/`) |
| 4. *Add trigger* → Kinesis | `modules/lambda/main.tf` : `aws_lambda_event_source_mapping` |
| 7. Créer le flux `ride_predictions` | `main.tf` : module `output_kinesis_stream` (même module, réutilisé) |
| 8. Policy « PutRecord sur `ride_predictions` » | `modules/lambda/iam.tf` : `aws_iam_role_policy` « LambdaInlinePolicy » |
| 12. Dépôt ECR + `docker push` | `modules/ecr/main.tf` : `aws_ecr_repository` + `null_resource` qui construit et pousse |
| 12. Droit de lire S3, droit d'écrire des logs | `modules/lambda/iam.tf` |
| 12. Variables d'environnement de la fonction | bloc `environment` de `aws_lambda_function` + `scripts/deploy_manual.sh` pour `RUN_ID` |
| (module 2) Le bucket S3 des modèles | `main.tf` : module `s3_bucket` (un **nouveau** bucket) |

## Le vocabulaire Terraform

| Mot | Sens |
|---|---|
| **provider** | Le plugin qui sait parler à un fournisseur. Ici `aws`. |
| **resource** | Un objet à **créer et gérer** : un flux, un bucket, une fonction… |
| **data** | Un objet à **lire seulement** : par exemple, « quel est mon numéro de compte AWS ? » |
| **variable** / fichier `.tfvars` | Un paramètre d'entrée / les valeurs de ces paramètres pour un environnement (staging, prod). |
| **locals** | Des valeurs intermédiaires calculées dans le fichier. |
| **output** | Une valeur **exposée** après `apply`, lisible par un autre module ou par la CD. |
| **module** | Un dossier de fichiers `.tf` réutilisable, appelé avec des paramètres : l'équivalent d'une fonction. |
| **state** (`.tfstate`) | La **mémoire** de Terraform : la liste de ce qu'il a créé. Rangé ici dans un bucket S3, le **backend**. |
| `init` / `plan` / `apply` / `destroy` | Préparer (télécharger le provider, se connecter au backend) / afficher les changements / les appliquer / tout supprimer. |

Attention aux homonymes : ce « backend » (où Terraform range son state) n'a rien à voir avec le conteneur `backend` de docker-compose, et ce « module » n'est ni un module Python ni un module du cours.

---

## Vidéo 6.7 (6B.1) — Introduction

**Ce que fait l'instructrice.**

1. `[0:00]` Présentation de l'architecture à construire ([`AWS-stream-pipeline.png`](https://github.com/DataTalksClub/mlops-zoomcamp/blob/main/06-best-practices/AWS-stream-pipeline.png)) : deux flux Kinesis, une fonction Lambda, un bucket S3 pour le modèle, un dépôt ECR pour l'image.
2. `[~2:40]` Prérequis : l'AWS CLI configurée avec **ta clé d'accès** (créée dans la console › IAM), et Terraform installé.
3. `[~5:50]` Annonce de la suite : les modules. Pour les bases de Terraform, elle renvoie aux vidéos du *Data Engineering Zoomcamp* (liens dans [`docs/extra-material.md`](https://github.com/DataTalksClub/mlops-zoomcamp/blob/main/06-best-practices/docs/extra-material.md)).

**Dans ton Codespace** (seulement si tu passes à la pratique) :

```bash
# [Terminal A] n'importe où — installer Terraform (méthode officielle HashiCorp pour Ubuntu)
wget -O- https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" \
    | sudo tee /etc/apt/sources.list.d/hashicorp.list
sudo apt update && sudo apt install terraform
terraform -version                           # → Terraform v1.…
```

```bash
# [Terminal A] configurer l'AWS CLI avec TES clés (et non plus les valeurs factices abc/xyz)
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY  # ← indispensable si tu les avais exportées pour LocalStack :
                                               #   les variables d'environnement passent avant ~/.aws
aws configure
# AWS Access Key ID [None]: <ta clé>
# AWS Secret Access Key [None]: <ton secret>
# Default region name [None]: eu-west-1
# Default output format [None]:               ← Entrée
aws sts get-caller-identity                    # → ton numéro de compte : la connexion fonctionne
```

`aws configure` écrit tes clés dans `~/.aws/credentials`. Ne les mets **jamais** dans un fichier du dépôt.

---

## Vidéo 6.8 (6B.2) — Modules et variables de sortie

### Ce que fait l'instructrice

1. `[0:03]` **Ce qu'est un module** : une boîte noire réutilisable, avec des entrées (variables) et des sorties (outputs). Utile pour ne pas répéter la même infrastructure en staging et en prod.
2. Elle crée `infrastructure/` avec `main.tf` (le point d'entrée) et `variables.tf` (les paramètres).
3. `[~3:28]` **Le backend** : le state sera rangé dans un bucket S3, **à créer à la main avant** (Terraform ne peut pas ranger sa mémoire dans un bucket qu'il n'a pas encore créé).

```hcl
# Make sure to create state bucket beforehand
terraform {
  required_version = ">= 1.0"
  backend "s3" {
    bucket  = "tf-state-mlops-zoomcamp"         # ← le bucket du state (nom à changer : voir plus bas)
    key     = "mlops-zoomcamp-stg.tfstate"      # ← le nom du fichier de state
    region  = "eu-west-1"
    encrypt = true
  }
}
```

4. `[~6:17]` puis `[~9:21]` **Le provider et les premières variables** :

```hcl
provider "aws" {
  region = var.aws_region          # « var.x » = la variable x, déclarée dans variables.tf
}
```

```hcl
# variables.tf
variable "aws_region" {
  description = "AWS region to create resources"
  default     = "eu-west-1"
}

variable "project_id" {
  description = "project_id"
  default = "mlops-zoomcamp"       # suffixe ajouté à tous les noms
}
```

5. `[~12:42]` **Lire son numéro de compte** avec une source `data`, rangé dans `locals` (il servira à l'adresse du dépôt ECR) :

```hcl
data "aws_caller_identity" "current_identity" {}

locals {
  account_id = data.aws_caller_identity.current_identity.account_id
}
```

6. `[~15:48]` Retour au schéma d'architecture, puis `[~18:54]` **le module Kinesis**, dans `modules/kinesis/` :

```hcl
# modules/kinesis/main.tf
resource "aws_kinesis_stream" "stream" {       # type de ressource "aws_kinesis_stream", nom interne "stream"
  name             = var.stream_name
  shard_count      = var.shard_count
  retention_period = var.retention_period
  shard_level_metrics = var.shard_level_metrics
  tags = {
    CreatedBy = var.tags
  }
}

output "stream_arn" {                           # ce que le module expose : l'identifiant AWS du flux
  value = aws_kinesis_stream.stream.arn
}
```

`modules/kinesis/variables.tf` déclare `stream_name`, `shard_count`, `retention_period`, `shard_level_metrics` (une liste de métriques CloudWatch, avec une valeur par défaut) et `tags`.

Un **ARN** (*Amazon Resource Name*) est l'identifiant unique d'une ressource AWS, par exemple `arn:aws:kinesis:eu-west-1:123456789012:stream/stg_ride_events-mlops-zoomcamp`. Les droits IAM et les liens entre ressources l'utilisent.

7. `[~22:02]` **Appeler le module** depuis `main.tf`, une fois par flux :

```hcl
# ride_events
module "source_kinesis_stream" {
  source = "./modules/kinesis"
  retention_period = 48                                           # heures
  shard_count = 2
  stream_name = "${var.source_stream_name}-${var.project_id}"     # → stg_ride_events-mlops-zoomcamp
  tags = var.project_id
}

# ride_predictions
module "output_kinesis_stream" {
  source = "./modules/kinesis"                                    # le MÊME module, réutilisé
  retention_period = 48
  shard_count = 2
  stream_name = "${var.output_stream_name}-${var.project_id}"     # → stg_ride_predictions-mlops-zoomcamp
  tags = var.project_id
}
```

8. `[~25:16]` à `[~31:45]` **Initialiser et appliquer** : `terraform init`, puis `terraform plan` et `terraform apply`. Les variables sans valeur par défaut (les noms des flux) sont passées sur la ligne de commande avec `-var="nom=valeur"`, ou demandées par Terraform. Elle vérifie ensuite dans la console Kinesis que les flux existent.

**C'est ici qu'est défini le flux d'événements dans le cloud** : `main.tf`, module `source_kinesis_stream`. Même définition minimale qu'au §0.4 (un nom, un nombre de shards, une durée de conservation), mais écrite dans un fichier versionné.

### Schéma : un module appelé deux fois

```text
 main.tf                                              modules/kinesis/
 ┌─────────────────────────────────────┐             ┌───────────────────────────────┐
 │ module "source_kinesis_stream"      │── entrées ─►│ variables : stream_name,      │
 │   stream_name = stg_ride_events-…   │             │   shard_count, retention…     │
 │   ◄── sortie : stream_arn ──────────│◄────────────│ resource aws_kinesis_stream   │
 │                                     │             │ output stream_arn             │
 │ module "output_kinesis_stream"      │── entrées ─►│ (le même dossier, une seconde │
 │   stream_name = stg_ride_predictions│◄────────────│  fois, avec d'autres valeurs) │
 │   ◄── sortie : stream_arn           │             └───────────────────────────────┘
 └─────────────────────────────────────┘
```

**Récit.** `main.tf` appelle **deux fois** le même module avec des valeurs différentes, comme on appelle deux fois une fonction. Chaque appel crée **un** flux et renvoie son ARN (`module.source_kinesis_stream.stream_arn`). Ces ARN serviront en 6.9 à brancher la fonction Lambda sur les flux et à lui donner ses droits.

### Dans ton Codespace (pratique, payante)

```bash
# [Terminal A] AWS CLI configurée avec tes clés (vidéo 6.7)
# 1. Le bucket du state : les noms de buckets sont UNIQUES sur tout AWS → ajoute un suffixe à toi
aws s3 mb s3://tf-state-mlops-zoomcamp-pierre --region eu-west-1
# 2. Reporter ce nom dans code/infrastructure/main.tf (ligne 5)
cd /workspaces/mlops-zoomcamp/06-best-practices/code/infrastructure
sed -i 's/"tf-state-mlops-zoomcamp"/"tf-state-mlops-zoomcamp-pierre"/' main.tf
sed -n 5p main.tf                            # affiche la ligne 5 → bucket  = "tf-state-mlops-zoomcamp-pierre"
```

Travaille dans `code/infrastructure/` (le corrigé) plutôt que de tout réécrire : les fichiers Terraform de l'instructrice sont arrivés en bloc, et c'est leur lecture qui compte. Le lancement complet est à la vidéo 6.9.

---

## Vidéo 6.9 (6B.3) — Le pipeline complet : S3, ECR, Lambda

### Ce que fait l'instructrice

1. `[0:03]` à `[~7:13]` **Le module S3** et une convention de nommage : chaque nom est `<valeur de la variable>-<project_id>`.

```hcl
# modules/s3/main.tf
resource "aws_s3_bucket" "s3_bucket" {
  bucket = var.bucket_name
  acl    = "private"
  force_destroy = true             # autorise « destroy » même si le bucket contient des fichiers
}

output "name" {
  value = aws_s3_bucket.s3_bucket.bucket
}
```

```hcl
# main.tf
module "s3_bucket" {
  source = "./modules/s3"
  bucket_name = "${var.model_bucket}-${var.project_id}"     # → stg-mlflow-models-code-owners-mlops-zoomcamp
}
```

2. `[~10:58]` à `[~23:56]` **Le module ECR.** Un dépôt d'images, et une astuce : une fonction Lambda de type « image » **ne peut pas être créée sans image existante**. Le module construit donc et pousse une première image pendant l'`apply` :

```hcl
# modules/ecr/main.tf
resource "aws_ecr_repository" "repo" {
  name                 = var.ecr_repo_name
  image_tag_mutability = "MUTABLE"          # on pourra réécrire le tag « latest »
  image_scanning_configuration {
    scan_on_push = false
  }
  force_delete = true
}

resource null_resource ecr_image {           # une « fausse » ressource, qui exécute des commandes
   triggers = {                              # à relancer si l'un de ces fichiers change
     python_file = md5(file(var.lambda_function_local_path))
     docker_file = md5(file(var.docker_image_local_path))
   }
   provisioner "local-exec" {                # exécuté SUR LA MACHINE qui lance terraform (ton Codespace)
     command = <<EOF
             aws ecr get-login-password --region ${var.region} | docker login --username AWS --password-stdin ${var.account_id}.dkr.ecr.${var.region}.amazonaws.com
             cd ../
             docker build -t ${aws_ecr_repository.repo.repository_url}:${var.ecr_image_tag} .
             docker push ${aws_ecr_repository.repo.repository_url}:${var.ecr_image_tag}
         EOF
   }
}

data aws_ecr_image lambda_image {            # attendre que l'image existe dans ECR
 depends_on = [null_resource.ecr_image]
 repository_name = var.ecr_repo_name
 image_tag       = var.ecr_image_tag         # « latest » par défaut
}

output "image_uri" {
  value     = "${aws_ecr_repository.repo.repository_url}:${data.aws_ecr_image.lambda_image.image_tag}"
}
```

`md5(file(…))` calcule une **empreinte** du fichier : une courte chaîne qui change dès que le fichier change. Si `lambda_function.py` ou le `Dockerfile` changent, l'empreinte change, et Terraform relance la construction de l'image.

`[~17:56]` Les chemins `lambda_function_local_path = "../lambda_function.py"` et `docker_image_local_path = "../Dockerfile"` sont relatifs à `infrastructure/` : l'infrastructure et le code vivent dans le même dépôt (*monorepo*). `[~20:48]` Rappel : le `CMD` du `Dockerfile` désigne le handler.

3. `[~27:12]` **Les fichiers de valeurs** : `vars/stg.tfvars`, choisi avec `-var-file=vars/stg.tfvars`.

```hcl
source_stream_name = "stg_ride_events"
output_stream_name = "stg_ride_predictions"
model_bucket = "stg-mlflow-models-code-owners"
lambda_function_local_path = "../lambda_function.py"
docker_image_local_path = "../Dockerfile"
ecr_repo_name = "stg_stream_model_duration"
lambda_function_name = "stg_prediction_lambda"
```

(`prod.tfvars`, avec le préfixe `prod_`, arrivera avec la CI, vidéo 6.12.)

4. `[~30:25]` à `[~37:41]` **Le module Lambda** (`modules/lambda/main.tf`) : la fonction et son branchement.

```hcl
resource "aws_lambda_function" "kinesis_lambda" {
  function_name = var.lambda_function_name
  image_uri = var.image_uri                    # l'image poussée par le module ECR
  package_type = "Image"
  role          = aws_iam_role.iam_lambda.arn  # le rôle défini dans iam.tf
  tracing_config {
    mode = "Active"                            # suivi X-Ray (facultatif)
  }
  environment {
    variables = {
      PREDICTIONS_STREAM_NAME = var.output_stream_name   # ← OÙ PUBLIER (question 3)
      MODEL_BUCKET = var.model_bucket                    # ← où chercher le modèle
    }
  }
  timeout = 180                                # secondes
}

resource "aws_lambda_function_event_invoke_config" "kinesis_lambda_event" {
  function_name                = aws_lambda_function.kinesis_lambda.function_name
  maximum_event_age_in_seconds = 60
  maximum_retry_attempts       = 0
}

resource "aws_lambda_event_source_mapping" "kinesis_mapping" {   # ← LE TRIGGER (question 2)
  event_source_arn  = var.source_stream_arn                      #   quel flux surveiller
  function_name     = aws_lambda_function.kinesis_lambda.arn     #   quelle fonction appeler
  starting_position = "LATEST"                                   #   ignorer les messages déjà présents
  depends_on = [
    aws_iam_role_policy_attachment.kinesis_processing            #   attendre que le droit de lire existe
  ]
}
```

5. `[~41:00]` à `[~48:09]` **Les droits** (`modules/lambda/iam.tf`) : un rôle que la fonction endosse, et des policies attachées :
   - lire les flux Kinesis (policy `allow_kinesis_processing`, attachée par `kinesis_processing`) ;
   - écrire dans le flux de sortie (`LambdaInlinePolicy` : `kinesis:PutRecord` et `PutRecords` sur `output_stream_arn`) ;
   - écrire des logs CloudWatch (`allow_logging`) ;
   - lire le bucket du modèle (`lambda_s3_policy_…`).

6. `[~51:40]` à `[~1:04:10]` **Tout brancher dans `main.tf`** : les sorties des modules deviennent les entrées des autres.

```hcl
module "ecr_image" {
   source = "./modules/ecr"
   ecr_repo_name = "${var.ecr_repo_name}_${var.project_id}"
   account_id = local.account_id
   lambda_function_local_path = var.lambda_function_local_path
   docker_image_local_path = var.docker_image_local_path
}

module "lambda_function" {
  source = "./modules/lambda"
  image_uri = module.ecr_image.image_uri                           # sortie du module ECR
  lambda_function_name = "${var.lambda_function_name}_${var.project_id}"
  model_bucket = module.s3_bucket.name                             # sortie du module S3
  output_stream_name = "${var.output_stream_name}-${var.project_id}"
  output_stream_arn = module.output_kinesis_stream.stream_arn      # sortie du module Kinesis (sortie)
  source_stream_name = "${var.source_stream_name}-${var.project_id}"
  source_stream_arn = module.source_kinesis_stream.stream_arn      # sortie du module Kinesis (entrée)
}
```

7. `[~1:08:41]` `terraform apply`, et correction d'erreurs dans les policies et les noms.

### Schéma : qui dépend de qui

Ici, une flèche `A ──► B` signifie « A **fournit une valeur** (une de ses sorties) à B ».

```text
            ┌──────────────────────┐   stream_arn   ┌──────────────────────────────────────────┐
            │ source_kinesis_stream│───────────────►│                                          │
            │ stg_ride_events-…    │                │ lambda_function                          │
            └──────────────────────┘                │  aws_lambda_function (image, variables)  │
            ┌──────────────────────┐   stream_arn   │  aws_lambda_event_source_mapping         │
            │ output_kinesis_stream│───────────────►│    (source_stream_arn → la fonction)     │
            │ stg_ride_predictions…│                │  iam.tf : rôle + policies                │
            └──────────────────────┘                │    (lire la source, écrire la sortie,    │
            ┌──────────────────────┐   name         │     logs, S3)                            │
            │ s3_bucket            │───────────────►│                                          │
            └──────────────────────┘                │                                          │
            ┌──────────────────────┐   image_uri    │                                          │
            │ ecr_image            │───────────────►│                                          │
            │ (+ docker build/push)│                └──────────────────────────────────────────┘
            └──────────────────────┘
```

**Récit.**

1. Terraform lit tous les fichiers `.tf` et repère les **références** : `module.ecr_image.image_uri`, `module.s3_bucket.name`, les deux `stream_arn`.
2. Il en déduit l'**ordre de création** : les deux flux, le bucket et le dépôt ECR d'abord (dans n'importe quel ordre, en parallèle) ; pendant ce temps, le `null_resource` construit et pousse l'image depuis ton Codespace.
3. Puis le module Lambda : le rôle et ses policies, la fonction (qui a besoin de l'image), et enfin l'event source mapping (qui a besoin de la fonction, du flux d'entrée et du droit de lecture).
4. Il range dans le state la liste de tout ce qu'il a créé, pour pouvoir le modifier ou le détruire plus tard.

**Tes trois questions, dans le cloud** :

| Question | Réponse |
|---|---|
| Où est défini le flux ? | `main.tf`, module `source_kinesis_stream` → `stg_ride_events-mlops-zoomcamp` (2 shards, 48 h) |
| Comment la course arrive-t-elle à la fonction ? | `aws_lambda_event_source_mapping` (`modules/lambda/main.tf`) : le trigger du module 4, écrit en Terraform |
| Où la fonction publie-t-elle ? | Dans le flux dont le nom est donné par la variable `PREDICTIONS_STREAM_NAME` (bloc `environment`) → `stg_ride_predictions-mlops-zoomcamp`, avec le droit donné par `LambdaInlinePolicy` |

### Dans ton Codespace (pratique, payante)

Deux noms doivent être **uniques sur tout AWS** : le bucket du state (fait en 6.8) et le bucket du modèle. Et l'image est construite à partir de `code/Dockerfile` : il faut la correction de pipenv (annexe C, n° 1), sinon la construction échoue pendant l'`apply`.

```bash
# [Terminal A] dossier code/infrastructure — AWS CLI configurée avec tes clés, Docker disponible
cd /workspaces/mlops-zoomcamp/06-best-practices/code/infrastructure
sed -i 's/^model_bucket = .*/model_bucket = "stg-mlflow-models-pierre"/' vars/stg.tfvars
sed -i 's/^RUN pip install pipenv *$/RUN pip install "pipenv==2023.12.1"/' ../Dockerfile
grep model_bucket vars/stg.tfvars                # → model_bucket = "stg-mlflow-models-pierre"
grep pipenv ../Dockerfile | head -1              # → RUN pip install "pipenv==2023.12.1"

terraform init                                # → Terraform has been successfully initialized!
terraform plan -var-file=vars/stg.tfvars      # → Plan: N to add, 0 to change, 0 to destroy. Rien n'est créé.
terraform apply -var-file=vars/stg.tfvars     # affiche le plan, demande confirmation : tape yes
terraform output                              # → ecr_repo, lambda_function, model_bucket, predictions_stream_name
```

Ces quatre sorties ne sont ajoutées qu'à la vidéo 6.13 : ton `code/` contenant la version finale, tu les as déjà.

---

## Vidéo 6.10 (6B.4) — Tester le pipeline de bout en bout

### Ce que fait l'instructrice

1. `[0:03]` **Ce que Terraform ne fait pas : le contenu.** L'infrastructure existe, mais le bucket du modèle est vide et la fonction ne connaît pas le `RUN_ID`. C'est le rôle de `scripts/deploy_manual.sh` :

```bash
AWS_REGION="eu-west-1"

# Dynamically generated by TF
export MODEL_BUCKET_PROD="stg-mlflow-models-code-owners-mlops-zoomcamp"
export PREDICTIONS_STREAM_NAME="stg_ride_predictions-mlops-zoomcamp"
export LAMBDA_FUNCTION="stg_prediction_lambda_mlops-zoomcamp"

# Model artifacts bucket from the previous weeks (MLflow experiments)
export MODEL_BUCKET_DEV="mlflow-models-alexey"

# le RUN_ID = le dossier du dernier objet modifié du bucket MLflow (« NOT FOR PRODUCTION! »)
export RUN_ID=$(aws s3api list-objects-v2 --bucket ${MODEL_BUCKET_DEV} \
--query 'sort_by(Contents, &LastModified)[-1].Key' --output=text | cut -f2 -d/)

# copier les modèles du bucket de développement vers le bucket créé par Terraform
aws s3 sync s3://${MODEL_BUCKET_DEV} s3://${MODEL_BUCKET_PROD}

# donner les variables à la fonction
variables="{PREDICTIONS_STREAM_NAME=${PREDICTIONS_STREAM_NAME}, MODEL_BUCKET=${MODEL_BUCKET_PROD}, RUN_ID=${RUN_ID}}"
aws lambda update-function-configuration --function-name ${LAMBDA_FUNCTION} --environment "Variables=${variables}"
```

- `update-function-configuration --environment` **remplace toutes** les variables de la fonction : c'est pourquoi le script redonne aussi `PREDICTIONS_STREAM_NAME` et `MODEL_BUCKET`.
- Le `README.md` de `code/` explique pourquoi `RUN_ID` n'est pas simplement écrit dans le `Dockerfile` : fixé par `ENV` ou `ARG`, il disparaissait à l'exécution de la Lambda.
- Il se lance avec un point : `. ./scripts/deploy_manual.sh`, pour que ses `export` restent dans ton terminal (§1.4, règle 4).

2. `[~2:50]` Récupérer le `RUN_ID` et mettre à jour les variables (le script ci-dessus). Dans une vraie équipe, le `RUN_ID` viendrait du *Model Registry* de MLflow (module 2).

3. `[~6:11]` **La démonstration** : `scripts/test_cloud_e2e.sh` envoie une course dans le flux d'entrée, puis on regarde les logs CloudWatch et le flux de sortie.

```bash
export KINESIS_STREAM_INPUT="stg_ride_events-mlops-zoomcamp"
export KINESIS_STREAM_OUTPUT="stg_ride_predictions-mlops-zoomcamp"

SHARD_ID=$(aws kinesis put-record  \
        --stream-name ${KINESIS_STREAM_INPUT}   \
        --partition-key 1  --cli-binary-format raw-in-base64-out  \
        --data '{"ride": {
            "PULocationID": 130,
            "DOLocationID": 205,
            "trip_distance": 3.66
        },
        "ride_id": 156}'  \
        --query 'ShardId'
    )
```

`--cli-binary-format raw-in-base64-out` : le piège de l'AWS CLI v2 vu au §0.4.

4. `[~9:27]` **Bilan de l'Infrastructure as Code** : l'infrastructure est versionnée, reproductible, identique d'un environnement à l'autre.

### Schéma : une course traverse le système

```text
 CODESPACE                               │ AWS eu-west-1
                                         │
 ① test_cloud_e2e.sh                     │    ┌────────────────────────────────┐
   aws kinesis put-record ──HTTPS ───────┼──► │ [ stg_ride_events-… ]  2 shards│
                                         │    └───────────────▲────────────────┘
                                         │                    │ ② interroge (≈ 1 fois/s)
                                         │    ┌───────────────┴────────────────┐
                                         │    │ event source mapping           │
                                         │    └───────────────┬────────────────┘
                                         │                    │ ③ appelle avec un lot
                                         │    ┌───────────────▼────────────────┐
                                         │    │ Lambda : ton image (via ECR)   │◄─ ④ modèle ── S3
                                         │    │ ⑤ décode, prédit               │─ ⑦ print ─► CloudWatch ─┐
                                         │    └───────────────┬────────────────┘                         │
                                         │                    │ ⑥ put_record                             │
 ⑧ aws kinesis get-records ──HTTPS ──────┼──► ┌───────────────▼────────────────┐                         │
   ◄── la prédiction ────────────────────┼─── │ [ stg_ride_predictions-… ]     │                         │
                                         │    └────────────────────────────────┘                         │
 ⑧ aws logs tail … ◄── les logs ─────────┼───────────────────────────────────────────────────────────────┘
```

**Récit.**

1. **Envoi.** Le programme `aws` (dans ton Codespace) dépose la course dans `stg_ride_events-mlops-zoomcamp`. Tu joues le producteur.
2. **Détection.** L'event source mapping, créé par Terraform, interroge ce flux et trouve le nouveau record.
3. **Appel.** Il appelle la fonction avec l'enveloppe `{"Records": [...]}` (même format que `event.json`). Si aucun conteneur n'est prêt, AWS en démarre un à partir de ton image.
4. **Chargement du modèle** (au démarrage du conteneur seulement). `init()` construit le chemin `s3://<MODEL_BUCKET>/1/<RUN_ID>/artifacts/model` et télécharge le modèle. Le rôle IAM donne le droit de lire le bucket : aucune clé à fournir.
5. **Calcul.** `lambda_handler` décode, prépare les features, prédit. Toujours le seul endroit où l'on calcule.
6. **Publication.** Le callback publie la prédiction dans `stg_ride_predictions-mlops-zoomcamp` (nom lu dans `PREDICTIONS_STREAM_NAME`).
7. **Journaux.** Les `print` et les erreurs arrivent dans CloudWatch Logs.
8. **Lecture.** Toi, depuis le Codespace : les logs, ou le flux de sortie.

Même chaîne qu'en local (6.3), avec les vrais services : la vraie Lambda remplace le RIE, le vrai Kinesis remplace LocalStack, S3 remplace le dossier monté, et un vrai flux d'entrée remplace `test_docker.py`.

### Dans ton Codespace (pratique, payante)

Tu n'as pas accès à `mlflow-models-alexey` : `deploy_manual.sh` échouerait. Remplace-le par ces commandes, qui déposent le **modèle de test** dans ton bucket, au chemin attendu par `get_model_location` (`1` = `MLFLOW_EXPERIMENT_ID` par défaut, `Test123` = le `RUN_ID` choisi) :

```bash
# [Terminal A] dossier code/infrastructure, après terraform apply (vidéo 6.9)
export MODEL_BUCKET=$(terraform output -raw model_bucket)
export LAMBDA_FUNCTION=$(terraform output -raw lambda_function)
export PREDICTIONS_STREAM_NAME=$(terraform output -raw predictions_stream_name)
echo ${MODEL_BUCKET} ${LAMBDA_FUNCTION} ${PREDICTIONS_STREAM_NAME}      # vérifier les trois valeurs

aws s3 cp --recursive ../integration-test/model s3://${MODEL_BUCKET}/1/Test123/artifacts/model

aws lambda update-function-configuration --function-name ${LAMBDA_FUNCTION} \
  --environment "Variables={PREDICTIONS_STREAM_NAME=${PREDICTIONS_STREAM_NAME},MODEL_BUCKET=${MODEL_BUCKET},RUN_ID=Test123}"
```

`terraform output -raw nom` affiche une sortie sans guillemets, prête à être rangée dans une variable. Un `terraform apply` ultérieur **retire** `RUN_ID` (absent du Terraform) : refais alors la dernière commande.

Envoyer une course (c'est la commande de `test_cloud_e2e.sh`, tapée à la main pour voir chaque étape), puis lire le résultat :

```bash
# [Terminal A] même terminal
export KINESIS_STREAM_INPUT="stg_ride_events-mlops-zoomcamp"
aws kinesis put-record \
    --stream-name ${KINESIS_STREAM_INPUT} \
    --partition-key 1 --cli-binary-format raw-in-base64-out \
    --data '{"ride": {"PULocationID": 130, "DOLocationID": 205, "trip_distance": 3.66}, "ride_id": 156}'

# les logs de la fonction (le groupe de logs d'une Lambda s'appelle /aws/lambda/<nom de la fonction>)
aws logs tail /aws/lambda/${LAMBDA_FUNCTION} --since 10m      # --follow pour suivre en direct ; Ctrl+C

# le flux de sortie : 2 shards, et la prédiction est dans l'un des deux
for SHARD in shardId-000000000000 shardId-000000000001; do
  IT=$(aws kinesis get-shard-iterator --stream-name ${PREDICTIONS_STREAM_NAME} \
       --shard-id ${SHARD} --shard-iterator-type TRIM_HORIZON --query 'ShardIterator' --output text)
  aws kinesis get-records --shard-iterator ${IT} --query 'Records[].Data' --output text \
    | tr '\t' '\n' | while read D; do echo ${D} | base64 --decode; echo; done
done
```

- La boucle `for` essaie les deux shards : la prédiction a pour clé de partition `"156"` (le `ride_id`), et c'est cette clé qui décide de son shard. (Les lignes commentées en fin de `test_cloud_e2e.sh` réutilisent le shard de la course **d'entrée**, dont la clé était `1` : elles peuvent viser le mauvais shard.)
- Si rien ne s'affiche, relance la boucle : Kinesis renvoie parfois une première réponse vide. Et comme l'event source mapping démarre à `LATEST` (il ignore les messages déjà présents), une course envoyée avant qu'il soit actif ne sera jamais traitée : si rien n'arrive au bout d'une minute, renvoie une course. Le premier appel de la fonction peut aussi prendre plusieurs secondes (démarrage du conteneur, téléchargement du modèle).
- Si la prédiction n'arrive toujours pas, les logs disent pourquoi (modèle introuvable, droits…). Un cas probable, non vérifié : le Terraform ne fixe pas la mémoire de la fonction (`memory_size`), qui vaut alors 128 Mo, peut-être trop peu pour charger mlflow et scikit-learn. Au module 4, l'instructeur avait augmenté la mémoire dans la console. Si les logs l'indiquent, ajoute `memory_size = 512` dans `aws_lambda_function` (`modules/lambda/main.tf`) et relance `terraform apply`.

**À la fin de chaque séance :**

```bash
# [Terminal A] dossier code/infrastructure
terraform destroy -var-file=vars/stg.tfvars     # tape yes → supprime tout ce que Terraform a créé
```

(Le `README.md` écrit `terraform destroy` sans `-var-file` : Terraform demanderait alors les variables une par une.) Le bucket du state, créé à la main, reste ; il ne coûte presque rien.

### Vérifie-toi

<details><summary>1. Pourquoi le bucket du state doit-il être créé à la main, avant <code>terraform init</code> ?</summary>
Terraform y range sa mémoire (le state) dès le début. Il ne peut pas la ranger dans un bucket qu'il n'a pas encore créé.
</details>

<details><summary>2. Pourquoi un <code>null_resource</code> qui fait <code>docker build</code> et <code>docker push</code> dans le module ECR ?</summary>
Une fonction Lambda de type image ne peut pas être créée sans image existante dans ECR. Le <code>null_resource</code> pousse une première image pendant l'<code>apply</code>, avant la création de la fonction. Le commentaire du fichier le rappelle : en pratique, c'est la CI/CD qui construit les images.
</details>

<details><summary>3. Quelle ressource Terraform correspond au bouton <i>Add trigger</i> de la console ?</summary>
<code>aws_lambda_event_source_mapping</code>, dans <code>modules/lambda/main.tf</code>.
</details>

<details><summary>4. Tu lances <code>bash scripts/deploy_manual.sh</code> puis <code>echo $RUN_ID</code> : vide. Pourquoi ?</summary>
Avec <code>bash</code>, le script tourne dans un autre shell, qui disparaît à la fin avec ses <code>export</code>. Il faut <code>. ./scripts/deploy_manual.sh</code>.
</details>

---

# Partie C — CI/CD avec GitHub Actions (Sejal Vaidya)

> Vidéos [6.11 / 6B.5](https://www.youtube.com/watch?v=OMwwZ0Z_cdk), [6.12 / 6B.6](https://www.youtube.com/watch?v=xkTWF9c33mU), [6.13 / 6B.7](https://www.youtube.com/watch?v=jCNxqXCKh2s) · fichiers : `.github/workflows/ci-tests.yml`, `.github/workflows/cd-deploy.yml` (à la **racine** du dépôt), `infrastructure/vars/prod.tfvars`, les `output` de `infrastructure/main.tf` · commit de l'instructrice : `6789e73` « Feature/week6b ci/cd » (29/07/2022).

## Vidéo 6.11 (6B.5) — Introduction

### Le but

Tout ce que tu as fait à la main dans les parties A et B (tests, contrôles, `terraform plan`, `apply`, `docker push`, mise à jour de la fonction), GitHub le fera **tout seul**, à chaque modification du code.

- **CI** (*Continuous Integration*, intégration continue) : **vérifier** chaque proposition de changement avant de l'accepter. Réponse attendue : « ce changement est-il sûr ? »
- **CD** (*Continuous Delivery*, livraison continue) : **déployer** automatiquement un changement accepté.

### Le vocabulaire de GitHub Actions

| Mot | Sens |
|---|---|
| **Workflow** | Un fichier YAML dans `.github/workflows/`, **à la racine du dépôt** (GitHub ne regarde pas ailleurs). |
| **`on:`** | L'événement qui déclenche le workflow : une *pull request*, un *push*… |
| **Job** | Un groupe d'étapes exécuté sur **une** machine. Plusieurs jobs tournent **en parallèle** par défaut. |
| **Runner** | La machine Linux temporaire que GitHub fournit pour un job, puis détruit. Rien ne tourne dans ton Codespace. |
| **Step** | Une étape d'un job : soit `uses:` (une **action**, un bloc réutilisable publié sur GitHub), soit `run:` (des commandes shell). |
| **Secret** | Une valeur chiffrée stockée par GitHub (tes clés AWS), lisible par les workflows via `${{ secrets.NOM }}`, jamais écrite dans le code. |
| **Branche, pull request (PR), merge** | Une copie de travail du code ; une demande de fusionner ta branche dans une autre, que quelqu'un relit ; la fusion elle-même. |

### Ce que montre l'instructrice

`[0:00]` et `[~2:55]` : l'architecture cible ([`ci_cd_zoomcamp.png`](https://github.com/DataTalksClub/mlops-zoomcamp/blob/main/06-best-practices/ci_cd_zoomcamp.png)).

```text
 ① git push feature-x ──► ② Pull Request vers « develop »
                              │   (seulement si des fichiers de 06-best-practices/code/ changent)
                              ▼
                   ③ ci-tests.yml, deux jobs en parallèle :
                      ├─ test    : pipenv install → pytest → pylint → run.sh (avec LocalStack)
                      └─ tf-plan : terraform init + plan sur la PROD (n'applique rien)
                              │
                   ④ résultat vert/rouge affiché sur la PR → relecture → merge
                              ▼
 ⑤ push sur « develop » ──► ⑥ cd-deploy.yml : terraform apply (prod) → docker build + push ECR
                                               → copie du modèle → variables de la Lambda
```

**Récit.**

1. Tu modifies le code sur une **branche** (`feature-x`) et tu la pousses sur GitHub.
2. Tu ouvres une **pull request** vers la branche `develop`.
3. GitHub lance le workflow de **CI**. Deux jobs, sur deux runners : le premier refait la partie A (tests unitaires, pylint, test d'intégration avec LocalStack, **sur le runner**), le second calcule ce que Terraform changerait en production, sans rien modifier.
4. Le résultat s'affiche sur la PR. Un relecteur la valide et la fusionne.
5. La fusion est un **push sur `develop`**.
6. GitHub lance le workflow de **CD**, qui refait la partie B, en production : appliquer le Terraform, construire et pousser l'image, déposer le modèle, configurer la fonction.

---

## Vidéo 6.12 (6B.6) — L'intégration continue : `ci-tests.yml`

### Ce que fait l'instructrice

**Étape 1 `[0:01]` — Le déclencheur.**

```yaml
name: CI-Tests
on:
  pull_request:
    branches:
      - 'develop'                          # les PR qui visent develop…
    paths:
      - '06-best-practices/code/**'        # …et modifient ce dossier (** = tout, sous-dossiers compris)

env:                                       # variables communes à tous les jobs
  AWS_DEFAULT_REGION: 'eu-west-1'
  AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
  AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
```

**Étape 2 `[~3:47]` — Le job `test` : refaire la partie A sur une machine neuve.**

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2                        # récupérer le code du dépôt sur le runner
      - name: Set up Python 3.9
        uses: actions/setup-python@v2
        with:
          python-version: 3.9

      - name: Install dependencies
        working-directory: "06-best-practices/code"      # « cd » pour cette étape
        run: pip install pipenv && pipenv install --dev

      - name: Run Unit tests                             # = make test
        working-directory: "06-best-practices/code"
        run: pipenv run pytest tests/

      - name: Lint                                       # = la fin de make quality_checks
        working-directory: "06-best-practices/code"
        run: pipenv run pylint --recursive=y .

      - name: Configure AWS Credentials
        uses: aws-actions/configure-aws-credentials@v1
        with:
          aws-access-key-id: ${{ env.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ env.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ env.AWS_DEFAULT_REGION }}

      - name: Integration Test                           # = run.sh, LocalStack compris
        working-directory: '06-best-practices/code/integraton-test'   # faute d'origine (annexe C, n° 13)
        run: |
          . run.sh
```

Le runner est une machine **vide** : chaque job commence par récupérer le code (`checkout`) et installer ses outils.

**Étape 3 `[~7:36]` puis `[~11:31]` — Le job `tf-plan`, et un state pour la prod.**

```yaml
  tf-plan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Configure AWS Credentials
        uses: aws-actions/configure-aws-credentials@v1
        with:
          aws-access-key-id: ${{ env.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ env.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ env.AWS_DEFAULT_REGION }}

      - uses: hashicorp/setup-terraform@v2               # installer Terraform sur le runner

      - name: TF plan
        id: plan
        working-directory: '06-best-practices/code/infrastructure'
        run: |
          terraform init -backend-config="key=mlops-zoomcamp-prod.tfstate" --reconfigure && terraform plan --var-file vars/prod.tfvars
```

- `-backend-config="key=…prod.tfstate"` **remplace**, au moment de l'`init`, le `key` écrit dans `main.tf` (`…stg.tfstate`) : même code Terraform, mais un **autre fichier de state**. Staging et production ont chacun leur mémoire.
- `vars/prod.tfvars` est créé à ce moment : les mêmes variables que `stg.tfvars`, avec le préfixe `prod_`.
- `plan` n'applique rien : le job montre, sur la PR, ce que le merge changerait en production.

**Étape 4 `[~15:08]` — Les secrets.** Dans le dépôt GitHub : *Settings → Secrets and variables → Actions → New repository secret*, pour `AWS_ACCESS_KEY_ID` et `AWS_SECRET_ACCESS_KEY`.

**Étape 5 `[~19:47]` — Dépanner LocalStack sur le runner.** Deux modifications de `run.sh`, visibles dans le commit :
- `sleep 1` devient `sleep 5` : sur le runner, LocalStack met plus de temps à démarrer.
- `cd "$(dirname "$0")"` est entouré de `if [[ -z "${GITHUB_ACTIONS}" ]]; then … fi`. Sur un runner, GitHub définit la variable `GITHUB_ACTIONS=true`. Et dans le workflow, le script est lancé avec un **point** (`. run.sh`) : il s'exécute dans le shell courant. Or, sur un runner, chaque étape `run:` est elle-même un script temporaire créé par GitHub (dans un dossier `_temp`) : `$0` y désigne **ce script temporaire**, pas `run.sh`. `cd "$(dirname "$0")"` partirait donc dans `_temp`. Comme `working-directory` a déjà placé l'étape dans le bon dossier, on saute ce `cd` en CI.

**Démo.** Une branche, une modification dans `06-best-practices/code/`, une PR vers `develop` : les deux jobs se lancent dans l'onglet *Actions*.

---

## Vidéo 6.13 (6B.7) — La livraison continue : `cd-deploy.yml`

### Ce que fait l'instructrice

**Étape 1 `[0:04]` — Le déclencheur** : un push sur `develop`, c'est-à-dire le merge d'une PR.

```yaml
name: CD-Deploy
on:
  push:
    branches:
      - 'develop'
```

**Étape 2 `[~4:08]` — Des `output` Terraform pour la CD.** Les étapes suivantes ont besoin des noms réels des ressources. Elle ajoute à la fin de `infrastructure/main.tf` :

```hcl
# For CI/CD
output "lambda_function" {
  value     = "${var.lambda_function_name}_${var.project_id}"
}

output "model_bucket" {
  value = module.s3_bucket.name
}

output "predictions_stream_name" {
  value     = "${var.output_stream_name}-${var.project_id}"
}

output "ecr_repo" {
  value = "${var.ecr_repo_name}_${var.project_id}"
}
```

**Étape 3 — Définir l'infrastructure : `plan`, puis `apply`, puis lire les sorties.**

```yaml
jobs:
  build-push-deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Check out repo
        uses: actions/checkout@v3
      - name: Configure AWS Credentials
        uses: aws-actions/configure-aws-credentials@v1
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: "eu-west-1"
      - uses: hashicorp/setup-terraform@v2
        with:
          terraform_wrapper: false

      - name: TF plan
        id: tf-plan
        working-directory: '06-best-practices/code/infrastructure'
        run: |
          terraform init -backend-config="key=mlops-zoomcamp-prod.tfstate" -reconfigure && terraform plan -var-file=vars/prod.tfvars

      - name: TF Apply
        id: tf-apply
        working-directory: '06-best-practices/code/infrastructure'
        if: ${{ steps.tf-plan.outcome }} == 'success'
        run: |
          terraform apply -auto-approve -var-file=vars/prod.tfvars
          echo "::set-output name=ecr_repo::$(terraform output ecr_repo | xargs)"
          echo "::set-output name=predictions_stream_name::$(terraform output predictions_stream_name | xargs)"
          echo "::set-output name=model_bucket::$(terraform output model_bucket | xargs)"
          echo "::set-output name=lambda_function::$(terraform output lambda_function | xargs)"
```

- `-auto-approve` : pas de confirmation `yes` (personne n'est là pour la taper).
- `::set-output name=X::valeur` publie une valeur que les étapes suivantes lisent avec `${{ steps.tf-apply.outputs.X }}`. `| xargs` retire les guillemets. (Cette syntaxe est dépréciée : aujourd'hui, `echo "X=valeur" >> "$GITHUB_OUTPUT"`.)

**Étape 4 `[~8:40]` — Construire et pousser l'image.**

```yaml
      - name: Login to Amazon ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v1

      - name: Build, tag, and push image to Amazon ECR
        id: build-image-step
        working-directory: "06-best-practices/code"
        env:
          ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
          ECR_REPOSITORY: ${{ steps.tf-apply.outputs.ecr_repo }}
          IMAGE_TAG: "latest"   # ${{ github.sha }}
        run: |
          docker build -t ${ECR_REGISTRY}/${ECR_REPOSITORY}:${IMAGE_TAG} .
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG
          echo "::set-output name=image_uri::$ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG"
```

Le commentaire `# ${{ github.sha }}` montre l'alternative discutée : étiqueter chaque image avec l'identifiant du commit, pour garder plusieurs versions et pouvoir revenir en arrière (déploiement *blue/green*). La vidéo garde `latest`.

**Étape 5 — Déposer le modèle.** Même logique que `deploy_manual.sh` : le dernier `RUN_ID` du bucket MLflow de développement, puis copie vers le bucket de prod.

```yaml
      - name: Get model artifacts
        id: get-model-artifacts
        working-directory: "06-best-practices/code"
        env:
          MODEL_BUCKET_DEV: "mlflow-models-alexey"
          MODEL_BUCKET_PROD: ${{ steps.tf-apply.outputs.model_bucket }}
        run: |
          export RUN_ID=$(aws s3api list-objects-v2 --bucket ${MODEL_BUCKET_DEV} \
          --query 'sort_by(Contents, &LastModified)[-1].Key' --output=text | cut -f2 -d/)
          aws s3 sync s3://${MODEL_BUCKET_DEV} s3://${MODEL_BUCKET_PROD}
          echo "::set-output name=run_id::${RUN_ID}"
```

**Étape 6 `[~12:59]` — Configurer la fonction, après avoir attendu qu'elle soit prête.** Juste après un `apply`, la fonction peut être encore en cours de mise à jour (`InProgress`) et refuser une nouvelle modification. Le script attend :

```yaml
      - name: Update Lambda
        env:
          LAMBDA_FUNCTION: ${{ steps.tf-apply.outputs.lambda_function }}
          PREDICTIONS_STREAM_NAME: ${{ steps.tf-apply.outputs.predictions_stream_name }}
          MODEL_BUCKET: ${{ steps.tf-apply.outputs.model_bucket }}
          RUN_ID: ${{ steps.get-model-artifacts.outputs.run_id }}
        run: |
          variables="{ \
                    PREDICTIONS_STREAM_NAME=$PREDICTIONS_STREAM_NAME, MODEL_BUCKET=$MODEL_BUCKET, RUN_ID=$RUN_ID \
                    }"

          STATE=$(aws lambda get-function --function-name $LAMBDA_FUNCTION --region "eu-west-1" --query 'Configuration.LastUpdateStatus' --output text)
              while [[ "$STATE" == "InProgress" ]]
              do
                  echo "sleep 5sec ...."
                  sleep 5s
                  STATE=$(aws lambda get-function --function-name $LAMBDA_FUNCTION --region "eu-west-1" --query 'Configuration.LastUpdateStatus' --output text)
                  echo $STATE
              done

          aws lambda update-function-configuration --function-name $LAMBDA_FUNCTION \
                    --environment "Variables=${variables}"
```

**Étape 7 `[~18:02]` — Démo et bilan.** Merge d'une PR → le workflow de CD tourne → dans le bucket du state, il y a maintenant **deux** fichiers : `mlops-zoomcamp-stg.tfstate` (créé par Terraform lors de ton `apply` de staging, en 6.9) et `mlops-zoomcamp-prod.tfstate` (créé par la CD). La production se teste comme le staging : une course dans `prod_ride_events-mlops-zoomcamp`.

### Schéma : les étapes de la CD, et ce qu'elles se passent

```text
 runner GitHub (job build-push-deploy)
   ① checkout, identifiants AWS, Terraform
   ② terraform plan + apply (prod) ──► AWS : flux, bucket, ECR, Lambda, droits
        └─ outputs : ecr_repo, model_bucket, predictions_stream_name, lambda_function
                         │          │                  │                    │
   ③ docker build + push ◄┘          │                  │                    │
        └─ image « latest » ──► ECR  │                  │                    │
   ④ RUN_ID + aws s3 sync ◄──────────┘                  │                    │
        └─ run_id                                       │                    │
   ⑤ attendre la fonction, puis update-function-configuration ◄──────────────┘
        (PREDICTIONS_STREAM_NAME, MODEL_BUCKET, RUN_ID)
```

**Récit.**

1. Le runner récupère le code, reçoit tes identifiants AWS (secrets) et installe Terraform.
2. Terraform met l'infrastructure de production à jour et publie les **noms** des ressources (ses `output`).
3. L'étape Docker lit le nom du dépôt ECR, construit l'image depuis `06-best-practices/code/` et la pousse.
4. L'étape suivante lit le nom du bucket de prod, y copie les modèles et publie le `RUN_ID`.
5. La dernière étape lit le nom de la fonction, du flux et du bucket, plus le `RUN_ID`, attend que la fonction soit disponible, puis lui donne ses variables d'environnement.

### Dans ton Codespace (pratique, payante)

La CD **crée la production** (flux Kinesis payants) et la CI a besoin de ton bucket de state : fais-le seulement si tu as fait la partie B.

**Piège : la CD se déclenche au moindre push sur `develop`**, y compris quand tu **crées** la branche en la poussant (son filtre `paths` est commenté). D'où l'ordre ci-dessous : créer `develop` **avant** d'activer les workflows (GitHub les désactive par défaut sur un fork), puis désactiver la CD tant que tu ne veux tester que la CI.

1. **Appliquer les corrections** de l'annexe C aux fichiers de `code/` et aux workflows (sinon la CI échoue : faute `integraton-test`, pipenv, LocalStack, `docker-compose`), et les committer sur `main`. Pour la CD, deux corrections de plus :
   - le bucket du modèle de production doit avoir un nom à toi : `sed -i 's/^model_bucket = .*/model_bucket = "prod-mlflow-models-pierre"/' 06-best-practices/code/infrastructure/vars/prod.tfvars` (depuis la racine du fork) ;
   - l'étape *Get model artifacts* de `cd-deploy.yml` lit `mlflow-models-alexey`, inaccessible : la CD s'arrêterait là. Remplace son bloc `env:` et `run:` par le dépôt du modèle de test (même idée qu'en 6.10) :

```yaml
        env:
          MODEL_BUCKET_PROD: ${{ steps.tf-apply.outputs.model_bucket }}
        run: |
          aws s3 cp --recursive integration-test/model s3://${MODEL_BUCKET_PROD}/1/Test123/artifacts/model
          echo "run_id=Test123" >> "$GITHUB_OUTPUT"
```

   (`echo "nom=valeur" >> "$GITHUB_OUTPUT"` est la syntaxe actuelle qui remplace `::set-output`.)
2. **Créer la branche `develop`** (les workflows sont encore désactivés : rien ne se lance) :

```bash
# [Terminal A] racine du fork
cd /workspaces/mlops-zoomcamp
git checkout main && git pull
git checkout -b develop
git push -u origin develop                        # la branche develop existe sur GitHub
```

3. **Activer les workflows** : onglet *Actions* du fork → *I understand my workflows, go ahead and enable them*. Puis, pour ne tester que la CI : *Actions* → **CD-Deploy** (colonne de gauche) → menu `⋯` → *Disable workflow*.
4. **Ajouter les deux secrets** (étape 4 de 6.12).
5. **Une branche de travail et une PR** :

```bash
# [Terminal A] racine du fork, sur la branche develop
git checkout -b feature-test-ci                   # une branche de travail, partie de develop
# … modifie un fichier de 06-best-practices/code/ (par exemple un commentaire dans model.py) …
git add 06-best-practices/code/model.py
git commit -m "Test de la CI"
git push -u origin feature-test-ci
```

6. Sur GitHub, ouvre la PR : **base repository = `Janua29/mlops-zoomcamp`**, **base = `develop`**, compare = `feature-test-ci`. Par défaut, GitHub propose le dépôt d'origine (DataTalksClub) : change-le.
7. Onglet *Actions* : les jobs `test` et `tf-plan` tournent. Clique sur une étape pour voir ses logs.
8. Pour tester aussi la CD : réactive **CD-Deploy**, puis fusionne la PR. Ensuite, détruis la production depuis `code/infrastructure/` :

```bash
# [Terminal A] racine du fork, AWS CLI configurée avec tes clés
cd /workspaces/mlops-zoomcamp/06-best-practices/code/infrastructure
terraform init -backend-config="key=mlops-zoomcamp-prod.tfstate" -reconfigure    # se brancher sur le state de prod
terraform destroy -var-file=vars/prod.tfvars                                      # yes
terraform init -reconfigure                                                       # revenir au state de staging
```

### Vérifie-toi

<details><summary>1. Pourquoi deux jobs dans la CI, et pourquoi chacun commence-t-il par <code>checkout</code> ?</summary>
Les jobs tournent en parallèle, chacun sur son propre runner, une machine vide. Chacun doit récupérer le code et installer ses outils.
</details>

<details><summary>2. Comment la CI et la CD utilisent-elles le même code Terraform que toi, sans toucher à ton staging ?</summary>
<code>-backend-config="key=mlops-zoomcamp-prod.tfstate"</code> choisit un autre fichier de state, et <code>vars/prod.tfvars</code> d'autres noms (préfixe <code>prod_</code>). Même code, autre environnement.
</details>

<details><summary>3. Pourquoi <code>run.sh</code> saute-t-il son <code>cd</code> sur GitHub Actions ?</summary>
Le workflow le lance avec <code>. run.sh</code> (dans le shell courant) : <code>$0</code> y désigne le script temporaire de l'étape, créé par GitHub, et non <code>run.sh</code> ; <code>cd "$(dirname "$0")"</code> partirait dans un mauvais dossier. <code>working-directory</code> a déjà placé l'étape dans <code>integration-test/</code>.
</details>

---

# Annexes

## Annexe A — Carte des fichiers : quelle vidéo crée ou modifie quoi

Chemins relatifs à `06-best-practices/code/` (sauf `.github/`). « 4.4 » = hérité du module 4.

| Fichier | Créé en | Modifié en | Rôle |
|---|---|---|---|
| `lambda_function.py` | 4.4 | 6.1 (réduit à un adaptateur), 6.4 | Point d'entrée appelé par Lambda |
| `model.py` | 6.1 | 6.2 (`get_model_location`, bug d'`init`), 6.3 (`create_kinesis_client`), 6.4 (style) | Toute la logique |
| `Dockerfile` | 4.4 | 6.1 (copie `model.py`) | L'image du service |
| `Pipfile`, `Pipfile.lock` | 4.4 | 6.1 (pytest), 6.2 (deepdiff), 6.4 (pylint, black, isort), 6.5 (pre-commit) | Dépendances |
| `.vscode/settings.json` | 6.1 | 6.4 | Réglages VS Code (pytest, linting) |
| `tests/__init__.py` | 6.1 | — | Fait de `tests/` un package (import de `model`) |
| `tests/model_test.py` | 6.1 | 6.2 (`assert` final), 6.4 (`read_text`, style) | Les 4 tests unitaires |
| `tests/data.b64` | 6.4 | — | La course en base64, pour les tests |
| `integration-test/test_docker.py` | 4.4 (à la racine) | 6.2 (déplacé, devient un test), 6.4 (lit `event.json`) | Envoie la course au RIE, vérifie la réponse |
| `integration-test/model/` | 6.2 | — | Le modèle MLflow de test |
| `integration-test/docker-compose.yaml` | 6.2 | 6.3 (LocalStack), 27/07/2022 (identifiants factices) | Les conteneurs du test |
| `integration-test/run.sh` | 6.2 | 6.3 (flux, `test_kinesis`), 6.6 (build conditionnel), 6.12 (CI) | Orchestre le test d'intégration |
| `integration-test/test_kinesis.py` | 6.3 | 6.4 | Relit le flux de sortie |
| `integration-test/event.json` | 6.4 | — | L'enveloppe Lambda complète |
| `pyproject.toml` | 6.4 | — | Réglages de pylint, black, isort |
| `plan.md` | 6.4 | 6.5, 6.6 | La liste des sujets, cochée au fil des vidéos |
| `.pre-commit-config.yaml`, `.gitignore` | 6.5 | — | Hooks git |
| `Makefile`, `scripts/publish.sh` | 6.6 | — | Raccourcis ; publication fictive |
| `infrastructure/` (`main.tf`, `variables.tf`, `modules/`, `vars/stg.tfvars`) | 6.8-6.9 (commit `f3cf3dc`) | 6.12-6.13 (commit `6789e73` : `output` de `main.tf`, retouches des modules S3, ECR et IAM, nom du bucket dans `stg.tfvars`) | L'infrastructure AWS |
| `scripts/deploy_manual.sh`, `scripts/test_cloud_e2e.sh` | 6.10 (commit `f3cf3dc`) | 6.12-6.13 (commit `6789e73`) | Contenu (modèle, `RUN_ID`) ; test de bout en bout |
| `infrastructure/vars/prod.tfvars` | 6.12-6.13 | — | Valeurs de production |
| `.github/workflows/ci-tests.yml` | 6.12 | — | CI |
| `.github/workflows/cd-deploy.yml` | 6.13 | — | CD |
| `README.md` | 6.1 | à chaque vidéo | Les commandes de l'instructeur, dans l'ordre |

## Annexe B — Aide-mémoire des commandes

Dans le dossier `mon-code/`, environnement pipenv actif, sauf mention contraire.

**Chaque nouveau terminal**

```bash
conda activate mlops-06
cd /workspaces/mlops-zoomcamp/06-best-practices/mon-code
pipenv shell
```

**Tests unitaires (6.1)**

```bash
pytest tests/                    # -v pour le détail
```

**Test d'intégration à la main (à partir de 6.3)**

```bash
docker build -t stream-model-duration:v3 .
cd integration-test
export LOCAL_IMAGE_NAME=stream-model-duration:v3
export PREDICTIONS_STREAM_NAME=ride_predictions
export AWS_DEFAULT_REGION=eu-west-1 AWS_ACCESS_KEY_ID=abc AWS_SECRET_ACCESS_KEY=xyz
docker-compose up -d
aws --endpoint-url=http://localhost:4566 kinesis create-stream --stream-name ${PREDICTIONS_STREAM_NAME} --shard-count 1
python test_docker.py
python test_kinesis.py
docker-compose logs              # en cas d'échec
docker-compose down
```

**Test d'intégration avec le script (6.2-6.6)**

```bash
export AWS_DEFAULT_REGION=eu-west-1 AWS_ACCESS_KEY_ID=abc AWS_SECRET_ACCESS_KEY=xyz
unset LOCAL_IMAGE_NAME           # pour que run.sh construise une image neuve
./integration-test/run.sh ; echo $?
```

**Qualité (6.4)**

```bash
isort . && black . && pylint --recursive=y .
```

**pre-commit (6.5), dans le bac à sable `~/m6-precommit` uniquement**

```bash
pre-commit install
git add . && pre-commit run --all-files
```

**make (6.6)**

```bash
make test
make quality_checks
make build
make integration_test
make publish
```

**Terraform (6.8-6.10), dans `code/infrastructure/`, AWS CLI configurée avec tes vraies clés**

```bash
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY   # retirer les valeurs factices de LocalStack
terraform init
terraform plan    -var-file=vars/stg.tfvars
terraform apply   -var-file=vars/stg.tfvars
terraform output
terraform destroy -var-file=vars/stg.tfvars
```

**Diagnostic**

```bash
env | grep -E "AWS_|LOCAL_IMAGE|PREDICTIONS"   # quelles variables sont définies dans CE terminal ?
docker ps                                        # quels conteneurs tournent ? (port 8080 occupé ?)
pipenv --venv                                    # où est l'environnement pipenv ?
which python pipenv                              # quel Python, quel pipenv ?
```

## Annexe C — Pièges et corrections

Relevé seulement : **aucun fichier de ton fork n'a été modifié** pour écrire ce cours. Les corrections sont à appliquer par toi, au moment indiqué.

| # | Fichier (ligne) | Problème | Correction proposée | Nécessaire dès |
|---|---|---|---|---|
| 1 | `Dockerfile` (4), et celui copié du module 4 | `pip install pipenv` installe la dernière version, qui refuse `mlflow==1.27.0` : `docker build` échoue | `RUN pip install "pipenv==2023.12.1"` | 6.2 |
| 2 | `integration-test/docker-compose.yaml` (17) | Depuis le 23/03/2026, `localstack/localstack` sans version exige un jeton ; sans lui, le conteneur s'arrête (code 55) | `image: localstack/localstack:4.14.0` (non testé dans un Codespace), ou un compte gratuit et `LOCALSTACK_AUTH_TOKEN` | 6.3 |
| 3 | Ton terminal | L'AWS CLI et `test_kinesis.py` exigent une région et des identifiants, même pour LocalStack | `export AWS_DEFAULT_REGION=eu-west-1 AWS_ACCESS_KEY_ID=abc AWS_SECRET_ACCESS_KEY=xyz` | 6.3 |
| 4 | `integration-test/run.sh` (20) | `sleep 5` peut être trop court au premier démarrage de LocalStack | Relancer, ou attendre que `curl -s localhost:4566/_localstack/health` réponde | 6.3 |
| 5 | `.pre-commit-config.yaml` (12) | isort `rev: 5.10.1` ne s'installe plus (`The Poetry configuration is invalid`) | `rev: 5.12.0` | 6.5 |
| 6 | pre-commit dans le fork | Les hooks s'exécutent depuis la racine du dépôt ; un `git init` dans le fork crée un dépôt imbriqué | Bac à sable hors du fork (6.5) | 6.5 |
| 7 | `Makefile` (16) | `integraton-test` : il manque un « i » ; le dossier a été renommé en 2025 | `integration-test/run.sh` | 6.6 |
| 8 | `Makefile` (23), cible `setup` | Lancé dans le fork, `pre-commit install` installe un hook sans configuration à la racine : tous les commits du fork échouent | Ne pas lancer `make setup` dans le fork ; sinon `pre-commit uninstall` | 6.6 |
| 9 | `infrastructure/main.tf` (5), `vars/stg.tfvars` (3) et `vars/prod.tfvars` (3) | Noms de buckets S3 : uniques sur tout AWS, ceux du cours sont pris | Tes propres noms (commandes `sed` en 6.8, 6.9 et 6.13) ; le bucket du state est à créer à la main avant `init` | 6.8 |
| 10 | `scripts/deploy_manual.sh` (9) et `cd-deploy.yml` (70) | `mlflow-models-alexey` est le bucket de l'auteur, inaccessible | Déposer le modèle de test à la main (6.10) ; dans la CD, remplacer l'étape *Get model artifacts* (6.13) | 6.10 |
| 11 | `scripts/test_cloud_e2e.sh` (16) | La ligne commentée lit le flux de **sortie** avec le shard de la course d'**entrée** ; avec 2 shards, ce n'est pas forcément le bon | Essayer les deux shards (boucle de 6.10) | 6.10 |
| 12 | `.github/workflows/ci-tests.yml` (26) | Même cause que le n° 1 : `pip install pipenv` sans version | `pip install "pipenv==2023.12.1" && pipenv install --dev` | 6.12 |
| 13 | `.github/workflows/ci-tests.yml` (44) | Même faute `integraton-test` dans `working-directory` | `06-best-practices/code/integration-test` | 6.12 |
| 14 | `integration-test/run.sh` (18, 32-33, 43-44, 49), en CI | GitHub a retiré `docker-compose` (v1) de ses runners Ubuntu en 2024 : `command not found` probable | `docker compose` (v2) | 6.12 |
| 15 | `.github/workflows/cd-deploy.yml` (2-7) | Déclenché par **tout** push sur `develop`, y compris la création de la branche | Créer `develop` avant d'activer les workflows ; désactiver CD-Deploy tant qu'on ne teste que la CI (6.13) | 6.13 |
| 16 | `.vscode/settings.json` (7-8) | `python.linting.*` ignorés par VS Code depuis 2023 | Extension Pylint de Microsoft | 6.4 |
| 17 | Module 5 encore lancé | `adminer` publie aussi le port 8080 | `docker compose down` dans `05-monitoring/` | 6.2 |
| 18 | `README.md` du module 4 (`put-record`) | Avec l'AWS CLI v2, `--data` est lu comme du base64 déjà encodé | Ajouter `--cli-binary-format raw-in-base64-out` | 6.10 |
| 19 | `.github/workflows/cd-deploy.yml` (38-41, 58, 76) | `::set-output` est dépréciée par GitHub ; si elle a été désactivée, les étapes suivantes reçoivent des valeurs vides (non vérifié) | `echo "nom=valeur" >> "$GITHUB_OUTPUT"` | 6.13 |

**Remarques d'expert** (hors du périmètre du cours, détaillées au §10 de `cours-06-best-practices-v2.md`) :

- Les droits IAM sont très larges (`s3:*`, `kinesis:*` sur tout) : en production, on n'accorde que le nécessaire (*moindre privilège*).
- La CD pousse l'image sous le même tag `latest` puis ne change que la **configuration** de la fonction : d'après la documentation AWS, Lambda ne suit pas un tag qui change, il faudrait `aws lambda update-function-code`. Non testé.
- Dans `cd-deploy.yml`, `if: ${{ steps.tf-plan.outcome }} == 'success'` est toujours vrai (forme correcte : `if: steps.tf-plan.outcome == 'success'`).
- `maximum_retry_attempts = 0` (`modules/lambda/main.tf`) ne concerne que les appels **asynchrones**, pas la lecture de Kinesis. Par défaut, un lot Kinesis qui fait planter la fonction est réessayé jusqu'à l'expiration des messages (48 h), et bloque son shard pendant ce temps.

## Annexe D — Sources et méthode

**Comment l'ordre de construction a été établi**

- **L'historique git du dépôt original** montre les étapes d'Alexey Grigorev commit par commit : `88783bd` *unit tests* (27/06/2022), `dca082d` *integration tests* (28/06), `0dcf58a` *kinesis test* (30/06), `fadc8fc` *added linting and fixed some of the the issues* (30/06, sic), `c4d8c8a` *linting and formatting* (30/06), `b56359f` *best practices continued* (01/07, pre-commit), `dc7598b`, `adaff82` et `b2c6066` (02/07, Makefile). L'état des fichiers « en fin de vidéo » vient de ces commits. La partie de Sejal Vaidya arrive en deux blocs : `f3cf3dc` *demo-code* (16/07/2022, Terraform) et `6789e73` *Feature/week6b ci/cd* (29/07/2022).
- **Les repères de temps** viennent des résumés de vidéos de [dimzachar/mlops-zoomcamp › notes/Week_6](https://github.com/dimzachar/mlops-zoomcamp/tree/master/notes/Week_6). L'ordre des étapes de 6.1 et 6.3 est confirmé par les notes de [Muhongfan](https://github.com/Muhongfan/MLops/blob/main/06-best-practice/README.md).
- **Le module 4** : le code et le `README.md` de `04-deployment/streaming`, et les notes de [mleiwe (2024)](https://github.com/mleiwe/mlops-zoomcamp/blob/NotesBranch/cohorts/2024/04-deployment/Ch4_Notes_ML.md) pour les clics dans la console.
- **LocalStack** : [annonce du changement de LocalStack](https://blog.localstack.cloud/2026-upcoming-pricing-changes/), [version 4.14.0 et code de sortie 55](https://ddz.dev/blog/localstack-license-activation-failed/).

**Vérifié pour ce cours**, en exécutant du code :

- la liste des messages pylint 2.14.4 sur le code de fin de 6.3, et la note d'environ 6/10 ;
- black 22.6.0 retire les parenthèses de `class ModelService():` ;
- `DeepDiff` signale `type_changes` quand `version` vaut `None` au lieu de `'Test123'` ;
- `pre-commit sample-config` (version 2.19) produit exactement l'en-tête et le `rev: v3.2.0` du fichier du cours ;
- dans un `Makefile`, une valeur entre accents graves est recalculée à chaque commande, `:=` avec `$(shell …)` une seule fois ;
- sans `tests/__init__.py`, `pytest tests/` échoue sur `import model`.

Relu par deux agents : un expert (exactitude, avec exécution de code et lecture des commits) et un étudiant débutant (clarté, commandes manquantes) ; leurs remarques ont été intégrées.

Reprises du cours précédent (vérifiées alors) : la recette conda + pipenv 2023.12.1, les 4 tests unitaires, la note pylint 10/10 sur le code final, la prédiction 21,29, la correction isort 5.12.0, le comportement de pre-commit dans le fork.

**Non vérifié**

- **Le contenu exact des vidéos** : leurs transcriptions n'étaient pas accessibles depuis l'environnement de travail. L'ordre à l'intérieur d'une vidéo est reconstitué à partir des commits et des notes ci-dessus ; les formulations « la comparaison révèle le bug » (6.2) ou « deux problèmes de nom d'image » (6.6) sont des déductions de ces sources.
- Les noms exacts des policies créées dans la console au module 4.
- Les commandes Docker, LocalStack, AWS, Terraform et GitHub Actions de ce cours n'ont pas été exécutées dans un Codespace ; les coûts AWS sont un ordre de grandeur.

---

## Récapitulatif

| Notion | En une phrase |
|---|---|
| Flux Kinesis | Un nom, des shards, une durée de conservation ; pas de schéma : le format du message est une convention entre producteur et consommateur. |
| Trigger / event source mapping | C'est Lambda qui interroge le flux et appelle ta fonction avec un lot `{"Records": [...]}`, `data` en base64 ; Kinesis n'envoie rien. |
| Publication | Ta fonction écrit elle-même dans le flux de sortie avec `put_record` ; son `return` est ignoré en production (sans l'option `ReportBatchItemFailures`, non utilisée ici). |
| Refactoring (6.1) | Séparer la logique (`ModelService`) de l'infrastructure (`init`), pour tester sans AWS. |
| Mock, injection de dépendances | Donner à la classe un faux modèle et une liste de callbacks vide. |
| Test d'intégration (6.2) | Lancer le vrai conteneur et l'interroger en HTTP via le RIE ; il trouve ce que les tests unitaires ne voient pas (le bug d'`init`). |
| Variables d'environnement | `MODEL_LOCATION`, `KINESIS_ENDPOINT_URL`, `TEST_RUN`… : le même code tourne partout, seule la configuration change. |
| LocalStack (6.3) | Un faux AWS sur le port 4566 ; `--endpoint-url` / `endpoint_url` pour s'y connecter. |
| Qualité (6.4) | isort, black, pylint, réglés dans `pyproject.toml`, lancés depuis le dossier du projet. |
| pre-commit (6.5) | Les contrôles lancés par git avant chaque commit, depuis la racine du dépôt. |
| make (6.6) | Des noms courts et des dépendances entre étapes ; `:=` pour un tag calculé une fois. |
| Terraform (6.7-6.10) | Les clics de la console du module 4 écrits en fichiers : `init` → `plan` → `apply` → `destroy`. |
| CI / CD (6.11-6.13) | Vérifier chaque PR sur un runner GitHub ; déployer automatiquement après le merge. |
