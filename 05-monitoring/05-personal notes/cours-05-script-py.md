# MLOps Zoomcamp — Chapitre 5 : les scripts de calcul de métriques

> Complément de `cours-05-overview-architecture.md`, qui couvre l'architecture, Docker et Grafana. Ce cours-ci porte sur le **code Python** des deux scripts qui **produisent** les métriques.
> Fichiers : `05-monitoring/dummy_metrics_calculation.py` (vidéo 5.6) et `05-monitoring/evidently_metrics_calculation.py` (vidéo 5.7), version racine (`evidently==0.6.7`), lus sur ton fork le 25/09/2026.
> Prérequis : §1 et §4 du cours principal. Les objets Evidently (`ColumnMapping`, `Report`, `as_dict()`) sont détaillés dans l'explication du notebook baseline (projet claude.ai, `cours-05-monitoring-baseline-notebook.md`, §6). Ici, on ne fait que les rappeler.
> Légende : **[vérifié]** = exécuté dans un environnement de test (PostgreSQL 16 réglé en UTC, comme le conteneur). Sans mention = déduit de la lecture du code et de la documentation.

---

## 0. À quoi servent ces deux scripts

### 0.1 Leur place dans le pipeline

Dans toute la chaîne, ces scripts sont **la seule pièce qui écrit dans la base**. Grafana ne fait que lire.

```
notebook baseline ──► data/reference.parquet + models/lin_reg.bin
                                   │
                                   ▼
              ┌───────── script *_metrics_calculation.py ─────────┐
              │  1. prépare la base (une fois)                    │
              │  2. boucle : calcule → INSERT → attend ~10 s      │
              └─────────────────────────┬─────────────────────────┘
                                        │  localhost:5432 (INSERT)
                                        ▼
                          PostgreSQL : base test, table dummy_metrics
                                        ▲
                                        │  db:5432 (SELECT)
                                     Grafana
```

### 0.2 Pourquoi deux scripts ?

Un plombier qui pose une installation fait d'abord couler **de l'eau claire** pour vérifier qu'il n'y a pas de fuite, avant d'y faire passer le vrai produit.

- **`dummy_metrics_calculation.py`, c'est l'eau claire.** Il envoie des nombres **aléatoires**, sans modèle ni données. S'ils s'affichent dans Grafana, la tuyauterie Python → PostgreSQL → Grafana fonctionne.
- **`evidently_metrics_calculation.py`, c'est le vrai produit.** Il envoie de vraies métriques de monitoring, calculées par Evidently.

L'intérêt est d'**isoler les problèmes**. Si le script Evidently échoue alors que la chaîne a déjà été validée avec le script factice, tu sais que le problème vient d'Evidently ou des données, pas de la base ni de Grafana.

| | `dummy_metrics_calculation.py` | `evidently_metrics_calculation.py` |
|---|---|---|
| Vidéo | 5.6 | 5.7 |
| Ce qu'il envoie | 3 valeurs aléatoires | 3 métriques de monitoring |
| Il faut avoir exécuté le notebook baseline avant ? | Non | Oui (il lit `data/` et `models/`) |
| Colonnes de la table | `timestamp`, `value1`, `value2`, `value3` | `timestamp`, `prediction_drift`, `num_drifted_columns`, `share_missing_values` |
| Horodatage d'une ligne | l'heure actuelle | la date des données (1er → 27 février 2022) |
| Nombre de tours de boucle | 100 | 27 (un jour de février par tour) |
| Durée totale | ≈ 16 min 40 | ≈ 4 min 30 |
| Prefect | Non | Oui (`@task`, `@flow`) |
| Fenêtre de temps dans Grafana | *Last 5 minutes* | février 2022 |

Attention au nom : `dummy_metrics_calculation.py`, sans « s » à *calculation*.

### 0.3 Le squelette commun

Les deux scripts ont la même structure :

```
imports
configuration        → logs, constantes, texte SQL de création de la table
prep_db()            → crée la base "test" si besoin, recrée la table
fonction de calcul   → produit 3 valeurs et les insère (INSERT)
fonction principale  → prep_db(), puis boucle : calcul → attente → message de log
point d'entrée       → if __name__ == '__main__': ...
```

**Méthode de lecture** : comprends `dummy` en entier (§2). Le script Evidently ne sera ensuite qu'une liste de différences (§3).

### 0.4 Pourquoi un script, et pas le notebook ?

Techniquement, rien n'y oblige : le code psycopg fonctionne tel quel dans une cellule de notebook, c'est le même Python. Le script est un **choix d'industrialisation** :

| | Notebook | Script `.py` |
|---|---|---|
| Qui le lance | Toi, en cliquant sur *Run* | N'importe quoi : terminal, `cron`, Prefect, un conteneur, la CI (tests automatiques) |
| Ordre d'exécution | Les cellules peuvent être lancées dans le désordre, avec un état caché | Toujours de haut en bas, donc reproductible |
| Boucle de 16 min | Bloque le notebook | Tourne dans son terminal |
| Dans git | Du JSON avec les sorties, des diffs illisibles | Du texte, des diffs clairs |

Un monitoring doit tourner tous les jours **sans que personne n'ouvre Jupyter** : seul un script le permet. Le module suit le parcours MLOps classique :

- **notebook** : on prototype (vidéos 5.3 à 5.5) ;
- **script** : on automatise (vidéos 5.6 et 5.7) ;
- **pipeline planifié** : l'étape suivante, avec Prefect (§5, point 9).

### 0.5 Pourquoi pas via un service ?

Chaque pièce de l'architecture n'a qu'un rôle, et **aucune n'a celui d'écrire les métriques dans PostgreSQL** :

| Pièce | Son rôle | Pourquoi elle n'écrit pas les métriques |
|---|---|---|
| Evidently | **Calcule** | C'est une librairie, pas un service. Elle renvoie des nombres (`as_dict()`) mais ne sait rien de PostgreSQL. Son interface (`evidently ui`) garde ses rapports dans ses propres fichiers, pas dans ta base. |
| PostgreSQL | **Stocke** | Il ne va chercher aucune donnée lui-même. Il attend qu'on lui en envoie. |
| Grafana | **Affiche** | Il ne fait que lire, avec des `SELECT`. Il ne sait pas calculer du drift. |
| Adminer | **Explore** | Tu pourrais y taper un `INSERT` à la main. C'est possible, mais manuel : l'inverse d'un monitoring. |
| Prefect | **Orchestre** | Il lance ton code Python et le suit, mais ne le remplace pas. |

Le script est donc **la colle** entre ces pièces : il lit les données, appelle Evidently, puis passe les nombres à PostgreSQL grâce à psycopg. Sans lui, rien ne relie le calcul au stockage.

Ce découpage a un avantage : chaque pièce est **remplaçable** sans toucher aux autres. Tu pourrais passer de Grafana à un autre outil de visualisation, ou d'Evidently à une autre librairie de métriques, sans changer le reste de la chaîne.

---

## 1. Les librairies

### 1.1 Deux familles

- **Bibliothèque standard** : livrée avec Python, rien à installer (`datetime`, `time`, `random`, `logging`, `uuid`, `io`).
- **Paquets externes** : installés par `pip install -r requirements.txt` (`pandas`, `psycopg`, `pytz`, `joblib`, `prefect`, `evidently`).

Les trois formes d'import des scripts :

```python
import pandas as pd                    # importe le module sous l'alias pd  → pd.read_parquet(...)
from prefect import task, flow         # importe seulement ces deux noms     → @task, sans préfixe
from evidently.report import Report    # evidently.report = un sous-module (un fichier du paquet)
```

### 1.2 Vue d'ensemble

| Librairie | Famille | Rôle en une phrase | Ce que les scripts en utilisent | `dummy` | `evidently` |
|---|---|---|---|---|---|
| `datetime` | standard | Dates, heures, durées | `datetime.datetime.now()`, `datetime.datetime(2022, 2, 1)`, `datetime.timedelta(...)` | ✓ | ✓ |
| `time` | standard | Mettre le programme en pause | `time.sleep(s)` | ✓ | ✓ |
| `random` | standard | Nombres pseudo-aléatoires | `random.Random()`, `.randint()`, `.random()` | ✓ | importé, inutilisé |
| `logging` | standard | Messages de suivi horodatés | `logging.basicConfig()`, `logging.info()` | ✓ | ✓ |
| `uuid` | standard | Identifiants uniques | `uuid.uuid4()` | ✓ | importé, inutilisé |
| `io` | standard | Flux de données en mémoire | rien | inutilisé | inutilisé |
| `pytz` | externe | Fuseaux horaires | `pytz.timezone('Europe/London')` | ✓ | importé, inutilisé |
| `pandas` | externe | Tableaux de données (*DataFrame*) | `read_parquet`, filtrage, `fillna` | inutilisé | ✓ |
| `psycopg` | externe | Parler à PostgreSQL depuis Python | `connect`, `execute`, `cursor` | ✓ | ✓ |
| `joblib` | externe | Recharger le modèle sauvegardé | `joblib.load` | – | ✓ |
| `prefect` | externe | Orchestrer et suivre l'exécution | `@task`, `@flow` | – | ✓ |
| `evidently` | externe | Calculer les métriques de drift et de qualité | `ColumnMapping`, `Report`, 3 métriques | – | ✓ |

Les imports inutilisés sont des **restes de copier-coller** : le script Evidently a été écrit à partir du script factice. Python ne dit rien ; un *linter* (outil d'analyse du code, comme `ruff` ou `flake8`) les signalerait.

Deux paquets travaillent **en coulisse**, sans être importés :

- `pyarrow` : pandas s'en sert pour lire les fichiers Parquet.
- `scikit-learn` : `joblib.load` reconstruit un objet `LinearRegression`. Pour ça, la classe doit exister, donc scikit-learn doit être installé.

### 1.3 `psycopg` : la notion la plus importante des deux scripts

`psycopg` (version 3) est le **pilote** PostgreSQL : le traducteur entre Python et le serveur de base de données.

**Serveur, base, table : de quoi parle-t-on ?** PostgreSQL range les données sur quatre niveaux, comme des boîtes les unes dans les autres :

```
serveur PostgreSQL (le conteneur db, port 5432)
├── base (database) "postgres"   ← créée d'office par l'image Docker
└── base (database) "test"       ← créée par prep_db()
    └── table dummy_metrics
        └── lignes (une par jour ou par envoi)
```

Un seul serveur peut héberger plusieurs bases indépendantes. Dans ce cours, **« la base » désigne la base `test`**, sur le serveur PostgreSQL du service `db`. Seule exception : dans `prep_db()`, la première connexion vise la base `postgres`, celle qui existe par défaut (§2.4).

| Notion | Ce que c'est | Analogie |
|---|---|---|
| **Connexion** | Un canal ouvert entre Python et le serveur, vers **une** base précise | Un appel téléphonique vers un service |
| **Curseur** (*cursor*) | L'objet qui envoie une requête SQL et récupère sa réponse | Le combiné : on parle, on écoute |
| **Transaction** | Un groupe de modifications appliquées toutes ensemble, ou pas du tout | Un panier au supermarché |
| **Commit** | La validation : les modifications deviennent définitives et **visibles des autres connexions** | Passer en caisse |
| **Rollback** | L'annulation de la transaction | Reposer le panier |

Par défaut, psycopg ouvre une transaction dès la première requête. Tant qu'elle n'est pas validée, **personne d'autre ne voit les modifications**, Grafana compris.

`autocommit=True` change ce comportement : chaque requête est validée immédiatement (on paie chaque article dès qu'on le prend). Les scripts en ont besoin à deux endroits :

1. `CREATE DATABASE` refuse de s'exécuter à l'intérieur d'une transaction. C'est une règle de PostgreSQL.
2. Chaque `INSERT` doit être visible de Grafana tout de suite, pas à la fin du script.

**La chaîne de connexion**

```python
"host=localhost port=5432 dbname=test user=postgres password=example"
```

C'est le format « clé=valeur » de PostgreSQL. Forme équivalente, en URL : `postgresql://postgres:example@localhost:5432/test`. Les valeurs viennent de `docker-compose.yml` : mot de passe `POSTGRES_PASSWORD: example`, port publié `5432`, utilisateur `postgres` créé par l'image.

**Le bloc `with`**

```python
with psycopg.connect("...") as conn:
    ...
```

`with` garantit un nettoyage automatique à la sortie du bloc, même en cas d'erreur. Pour une connexion psycopg, la sortie du bloc fait trois choses :

1. **commit** si tout s'est bien passé, **rollback** si une erreur a interrompu le bloc ;
2. fermeture de la connexion ;
3. libération des ressources côté serveur.

[vérifié] La table créée par une connexion *sans* autocommit existe bien après la sortie du bloc : le commit a eu lieu.

**Deux façons d'exécuter du SQL**

```python
res = conn.execute("SELECT ...")      # raccourci : crée un curseur, exécute, renvoie le curseur
with conn.cursor() as curr:           # forme explicite : on crée le curseur soi-même
    curr.execute("INSERT ...")
```

**Les requêtes paramétrées**

```python
curr.execute(
    "insert into dummy_metrics(timestamp, value1, value2, value3) values (%s, %s, %s, %s)",
    (instant, 42, "abc", 0.5)
)
```

Les `%s` sont des **emplacements**. psycopg les remplit avec les valeurs du tuple, dans l'ordre, en les convertissant au bon type SQL (`datetime` → `timestamp`, `float` → `double precision`, etc.).

Ne jamais construire la requête avec une f-string (`f"... values ({x})"`) :

- Si `x` contient un texte malveillant comme `0); DROP TABLE dummy_metrics; --`, il devient du SQL exécuté. C'est l'**injection SQL**, une des failles les plus répandues du web.
- Tu devrais gérer toi-même les guillemets, les dates, les décimales.

### 1.4 `datetime`, `pytz`, `time` : le temps

- **`datetime.datetime`** : un **instant** (date + heure). **`datetime.timedelta`** : une **durée**.
- L'arithmétique suit le bon sens : instant + durée = instant ; instant − instant = durée ; `durée.total_seconds()` la convertit en secondes.
- `datetime.timedelta(3)` = 3 **jours** (le premier argument, sans nom, compte des jours). `datetime.timedelta(seconds=10)` = 10 secondes.
- Piège de nommage : `import datetime` importe le **module**, qui contient une **classe** du même nom. D'où `datetime.datetime.now()` : le module, puis la classe, puis la méthode.

**Instant « naïf » ou « conscient »** :

| | Exemple | Contient un fuseau horaire ? |
|---|---|---|
| Naïf (*naive*) | `datetime.datetime.now()`, `datetime.datetime(2022, 2, 1)` | Non : « 14 h 00 », sans préciser où |
| Conscient (*aware*) | `datetime.datetime.now(pytz.timezone('Europe/London'))` | Oui : « 14 h 00 à Londres, soit UTC+1 en été » |

`pytz` fournit la base des fuseaux horaires du monde. Depuis Python 3.9, la bibliothèque standard fait la même chose avec `zoneinfo` ; `pytz` reste très répandu dans le code existant.

**`time.sleep(x)`** met le programme en pause pendant `x` secondes (`x` peut être décimal : `time.sleep(7.3)`).

### 1.5 `logging` : des messages de suivi

Pourquoi pas `print()` ? Un message de log porte un **niveau** et une **date**, et le format se règle une seule fois pour tout le programme.

```python
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s]: %(message)s")
logging.info("data sent")
```

- Niveaux, du plus bavard au plus grave : `DEBUG` < `INFO` < `WARNING` < `ERROR` < `CRITICAL`. `level=logging.INFO` affiche `INFO` et au-dessus, et masque `DEBUG`.
- `format` : les `%(...)s` sont remplacés par l'heure (`asctime`), le niveau (`levelname`) et le texte (`message`).

[vérifié] Résultat : `2026-09-25 18:37:54,558 [INFO]: data sent`. L'heure affichée est celle de la machine qui exécute le script (ton Codespace), dans son fuseau horaire.

### 1.6 `random` et `uuid` : du faux, mais du vraisemblable

- `rand = random.Random()` crée un **générateur** de nombres pseudo-aléatoires.
  - `rand.randint(0, 1000)` : un entier entre 0 et 1000, **les deux bornes incluses**.
  - `rand.random()` : un décimal entre 0 (inclus) et 1 (exclu).
  - « Pseudo » : la suite est calculée. Avec une **graine** fixe, `random.Random(42)`, on obtient la même suite à chaque exécution. Utile pour les tests reproductibles.
- `uuid.uuid4()` : un identifiant aléatoire de 128 bits, pratiquement unique au monde, par exemple `89fac0d4-507c-45cc-bfc2-ed58a5601e69`. `str(...)` le convertit en texte. Ici, il sert seulement à remplir une colonne de type texte.

### 1.7 `pandas`, `joblib`, `evidently` : rappels

| Librairie | Rappel | Détails |
|---|---|---|
| `pandas` | Manipule des tableaux (*DataFrame*) : lire un fichier, filtrer des lignes, sélectionner des colonnes | Doc baseline, §3 |
| `joblib` | `dump` sauvegarde un objet Python sur disque, `load` le reconstruit (*sérialisation*) | Doc baseline, §5 |
| `evidently` | Décrire les colonnes (`ColumnMapping`) → choisir les métriques (`Report`) → calculer (`run`) → exporter (`as_dict`) | Doc baseline, §6 |

### 1.8 `prefect` : l'orchestrateur

Un **orchestrateur** lance des workflows (enchaînements d'étapes), les planifie, les relance en cas d'échec et garde l'historique de chaque exécution. Tu l'as vu au chapitre 3.

Ici, Prefect ne sert qu'à **instrumenter** : il enregistre chaque exécution (début, fin, statut, logs) pour qu'on puisse la suivre dans son interface. Il ne planifie rien et ne relance rien. Le README le signale comme optionnel depuis 2024. Le mécanisme des décorateurs `@task` / `@flow` est expliqué au §3.5.

---

## 2. `dummy_metrics_calculation.py`, bloc par bloc

### 2.1 Imports (lignes 1 à 9)

```python
import datetime
import time
import random
import logging
import uuid
import pytz
import pandas as pd
import io
import psycopg
```

Voir §1. `pandas` et `io` ne servent à rien dans ce script.

### 2.2 Configuration (lignes 11 à 14)

```python
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s]: %(message)s")

SEND_TIMEOUT = 10
rand = random.Random()
```

- `logging.basicConfig(...)` : voir §1.5.
- `SEND_TIMEOUT = 10` : un nom en MAJUSCULES signale par convention une **constante**, une valeur qu'on ne modifie pas pendant l'exécution. Le nom est trompeur : ce n'est pas un *timeout* (un délai maximal d'attente), c'est l'**intervalle visé entre deux envois**, en secondes.
- `rand` : le générateur aléatoire (§1.6).

### 2.3 Le SQL de création de la table (lignes 16 à 24)

```python
create_table_statement = """
drop table if exists dummy_metrics;
create table dummy_metrics(
	timestamp timestamp,
	value1 integer,
	value2 varchar,
	value3 float
)
"""
```

- Les triples guillemets `"""` délimitent une **chaîne sur plusieurs lignes**. Pour Python, ce n'est que du texte ; c'est PostgreSQL qui l'interprétera.
- Elle contient **deux instructions** SQL, séparées par `;` :
  - `drop table if exists dummy_metrics;` supprime la table, **données comprises**, si elle existe. Chaque lancement repart donc de zéro.
  - `create table dummy_metrics(...)` recrée la table avec 4 colonnes.

| Colonne | Type écrit | Type réel dans PostgreSQL [vérifié] | Contenu |
|---|---|---|---|
| `timestamp` | `timestamp` | `timestamp without time zone` | Date et heure, sans fuseau horaire |
| `value1` | `integer` | `integer` | Entier |
| `value2` | `varchar` | `character varying` | Texte de longueur libre |
| `value3` | `float` | `double precision` | Décimal sur 64 bits |

La colonne s'appelle `timestamp`, comme le type. C'est permis, mais ambigu : c'est pourquoi les requêtes du dashboard l'écrivent entre guillemets doubles, `"timestamp"`.

### 2.4 `prep_db()` : préparer la base (lignes 26 à 32)

```python
def prep_db():
	with psycopg.connect("host=localhost port=5432 user=postgres password=example", autocommit=True) as conn:
		res = conn.execute("SELECT 1 FROM pg_database WHERE datname='test'")
		if len(res.fetchall()) == 0:
			conn.execute("create database test;")
		with psycopg.connect("host=localhost port=5432 dbname=test user=postgres password=example") as conn:
			conn.execute(create_table_statement)
```

Ligne par ligne :

1. **Connexion sans `dbname`.** Quand on ne précise pas de base, PostgreSQL en prend une qui porte le nom de l'utilisateur : `postgres`. Elle existe toujours, car l'image la crée. On ne peut pas se connecter à `test` avant qu'elle existe. `autocommit=True` est obligatoire pour le `CREATE DATABASE` qui suit (§1.3).
2. **`SELECT 1 FROM pg_database WHERE datname='test'`.** `pg_database` est un **catalogue système** : une table interne de PostgreSQL qui liste les bases, une ligne par base. `SELECT 1` ne demande aucune donnée : on veut seulement savoir **si une ligne existe**.
3. **`res.fetchall()`** récupère toutes les lignes de la réponse, sous forme de liste : `[(1,)]` si la base existe, `[]` sinon. `len(...) == 0` signifie donc « la base n'existe pas ».
4. **`create database test;`** la crée dans ce cas.
5. **Deuxième connexion, cette fois vers `test`.** Une connexion PostgreSQL est liée à une seule base ; pour changer de base, il faut ouvrir une nouvelle connexion. Celle-ci n'est pas en autocommit : le `DROP` et le `CREATE` forment une seule transaction, validée à la sortie du `with`. Le texte SQL contient deux instructions ; psycopg l'accepte parce que la requête n'a pas de paramètres `%s`.

Deux remarques :

- La seconde connexion réutilise le nom `conn` : elle **masque** la première à l'intérieur du bloc. Ça fonctionne (la première ne sert plus), mais c'est source de confusion. Un nom distinct (`conn_test`) serait plus clair.
- La fonction est **idempotente** : l'exécuter une ou dix fois donne le même résultat (une base `test` avec une table vide). C'est une propriété recherchée en data engineering : on peut relancer sans crainte.

### 2.5 `calculate_dummy_metrics_postgresql(curr)` : produire une ligne (lignes 34 à 42)

```python
def calculate_dummy_metrics_postgresql(curr):
	value1 = rand.randint(0, 1000)
	value2 = str(uuid.uuid4())
	value3 = rand.random()

	curr.execute(
		"insert into dummy_metrics(timestamp, value1, value2, value3) values (%s, %s, %s, %s)",
		(datetime.datetime.now(pytz.timezone('Europe/London')), value1, value2, value3)
	)
```

- La fonction **reçoit** le curseur en paramètre au lieu d'ouvrir sa propre connexion. C'est l'appelant (`main`) qui gère la connexion : chaque fonction n'a qu'une responsabilité.
- Trois valeurs aléatoires : un entier, un texte, un décimal. Trois types différents pour tester que la chaîne gère chacun d'eux.
- `INSERT` paramétré : 4 emplacements `%s`, 4 valeurs dans le tuple, **dans le même ordre** que la liste des colonnes (§1.3).
- **L'horodatage.** `datetime.now(pytz.timezone('Europe/London'))` est l'heure actuelle à Londres, avec son décalage (instant *conscient*). Or la colonne est *sans* fuseau. PostgreSQL convertit donc l'instant dans le fuseau de sa session, UTC dans le conteneur, puis retire le décalage.
  [vérifié] Inséré à 17 h 37 heure de Londres (UTC+1 en été), la ligne contient `16:37`, soit l'heure UTC.
  Grafana interprète une colonne `timestamp` sans fuseau comme de l'UTC et l'affiche dans le fuseau de ton navigateur : les points tombent à la bonne heure. Le choix de Londres n'a aucune importance ici ; `datetime.datetime.now(datetime.timezone.utc)` dirait la même chose plus clairement.
- Le nom de la fonction est trompeur : elle ne calcule rien, elle tire au sort.

### 2.6 `main()` : la boucle métronome (lignes 44 à 57)

```python
def main():
	prep_db()
	last_send = datetime.datetime.now()
	with psycopg.connect("host=localhost port=5432 dbname=test user=postgres password=example", autocommit=True) as conn:
		for _ in range(100):
			with conn.cursor() as curr:
				calculate_dummy_metrics_postgresql(curr)

			new_send = datetime.datetime.now()
			seconds_elapsed = (new_send - last_send).total_seconds()
			if seconds_elapsed < SEND_TIMEOUT:
				time.sleep(SEND_TIMEOUT - seconds_elapsed)
			last_send = last_send + datetime.timedelta(seconds=10)
			logging.info("data sent")
```

**La connexion.** Une seule connexion pour toute la boucle : en ouvrir une à chaque tour coûterait une authentification à chaque fois. `autocommit=True` : chaque `INSERT` est validé, donc visible de Grafana, immédiatement.

**La boucle.** `for _ in range(100)` : 100 tours. `_` est la convention pour « une variable dont je ne me sers pas » (on n'a pas besoin du numéro du tour). À chaque tour, `with conn.cursor() as curr` crée un curseur neuf, fermé à la fin du bloc.

**Le rythme.** Les 4 lignes suivantes visent **un envoi toutes les 10 secondes**, quelle que soit la durée du calcul :

| Ligne | Rôle |
|---|---|
| `last_send = datetime.datetime.now()` (avant la boucle) | Heure **prévue** du dernier envoi. Au départ : maintenant. |
| `seconds_elapsed = (new_send - last_send).total_seconds()` | Temps écoulé depuis l'heure prévue. |
| `if seconds_elapsed < SEND_TIMEOUT: time.sleep(SEND_TIMEOUT - seconds_elapsed)` | Dormir juste ce qu'il faut pour atteindre 10 s. |
| `last_send = last_send + datetime.timedelta(seconds=10)` | Avancer l'heure prévue de 10 s **exactement**, et non `= now()`. |

Pourquoi « + 10 s » plutôt que « maintenant » ? Compare avec la version naïve, `time.sleep(10)` après chaque envoi :

| Stratégie | Si le calcul prend 0,5 s, les envois ont lieu à… |
|---|---|
| `time.sleep(10)` après chaque calcul | 0,5 · 11 · 21,5 · 32 · … : la période est de 10,5 s, le retard s'accumule |
| Heure prévue + 10 s (le script) | 0,5 · 10,5 · 20,5 · 30,5 · … : la durée du calcul est absorbée |

C'est le principe d'un **métronome** : on se cale sur une grille de temps fixe, pas sur la fin de la tâche précédente.

Deux détails :

- Le message `data sent` s'affiche **après** la pause, donc environ 10 s après l'`INSERT` correspondant. [vérifié]
- Si un calcul durait plus de 10 s, il n'y aurait plus de pause : le script enchaînerait les tours aussi vite que possible, sans jamais rattraper sa grille.

**Durée totale** : 100 × 10 s ≈ 16 min 40. Le script s'arrête tout seul. Ctrl+C l'interrompt avant : Python lève une exception `KeyboardInterrupt`, le `with` ferme proprement la connexion, et les lignes déjà insérées restent (autocommit).

### 2.7 Le point d'entrée (lignes 59-60)

```python
if __name__ == '__main__':
	main()
```

Python remplit automatiquement la variable `__name__` :

- `python dummy_metrics_calculation.py` → `__name__ == '__main__'` → `main()` s'exécute ;
- `import dummy_metrics_calculation` depuis un autre fichier → `__name__ == 'dummy_metrics_calculation'` → rien ne se lance, mais les fonctions deviennent réutilisables.

C'est la façon standard d'écrire un fichier Python qui est à la fois **un script** et **un module**.

### 2.8 Voir le résultat

- **Terminal** : une ligne `... [INFO]: data sent` toutes les 10 s.
- **Adminer** (port 8080, serveur `db`, base `test`) : *Commande SQL* →
  ```sql
  SELECT * FROM dummy_metrics ORDER BY "timestamp" DESC;
  ```
- **Grafana** : le dashboard provisionné (`data_drift.json`) interroge `prediction_drift`, `num_drifted_columns` et `share_missing_values`. Ces colonnes **n'existent pas** dans la table du script factice : ses panels affichent une erreur du type *column "prediction_drift" does not exist*. C'est normal, il est fait pour le script Evidently.
  Pour voir les données factices, crée un panel dans un nouveau dashboard (*Dashboards → New → New dashboard → Add visualization*, source `PostgreSQL`, mode *Code*) :
  ```sql
  SELECT "timestamp" AS "time", value1
  FROM dummy_metrics
  WHERE $__timeFilter("timestamp")
  ORDER BY 1
  ```
  Fenêtre *Last 5 minutes*, rafraîchissement automatique à 5 s. `value2` est du texte : impossible à tracer. `value1` (0 à 1000) et `value3` (0 à 1) n'ont pas la même échelle : un panel chacun.
  (Chemin de menus non vérifié : il varie selon la version de Grafana.)

---

## 3. `evidently_metrics_calculation.py` : ce qui change

### 3.1 Carte des différences

| Bloc | Lignes | Par rapport à `dummy` |
|---|---|---|
| Imports | 1-16 | + `joblib`, `prefect`, `evidently` |
| Logs, constantes | 18-21 | Identique |
| SQL de création de la table | 23-31 | Nouvelles colonnes |
| Chargement des données et du modèle | 33-37 | **Nouveau** |
| Configuration d'Evidently | 39-53 | **Nouveau** |
| `prep_db()` | 55-62 | Identique, + `@task` |
| Fonction de calcul | 64-84 | **Réécrite** |
| Fonction principale | 86-101 | Même squelette ; 27 tours ; rythme modifié ; `@flow` |
| Point d'entrée | 103-104 | Identique (appelle la nouvelle fonction principale) |

### 3.2 Les imports ajoutés (lignes 10 à 16)

```python
import joblib

from prefect import task, flow

from evidently.report import Report
from evidently import ColumnMapping
from evidently.metrics import ColumnDriftMetric, DatasetDriftMetric, DatasetMissingValuesMetric
```

Ces chemins d'import n'existent que dans Evidently 0.6.x. Avec la 0.7, ils ont déménagé sous `evidently.legacy` : `ImportError` (voir le §0 du cours principal).

### 3.3 La nouvelle table (lignes 23 à 31)

```sql
drop table if exists dummy_metrics;
create table dummy_metrics(
	timestamp timestamp,
	prediction_drift float,
	num_drifted_columns integer,
	share_missing_values float
)
```

- Même nom de table que le script factice (héritage) : lancer l'un **efface** les données de l'autre.
- Ces noms de colonnes sont exactement ceux que lisent les requêtes de `data_drift.json`. C'est un **contrat** entre le script (qui écrit) et le dashboard (qui lit) : renomme une colonne d'un côté seulement, et le panel correspondant tombe en erreur.

### 3.4 Charger les données et le modèle (lignes 33 à 37)

```python
reference_data = pd.read_parquet('data/reference.parquet')
with open('models/lin_reg.bin', 'rb') as f_in:
	model = joblib.load(f_in)

raw_data = pd.read_parquet('data/green_tripdata_2022-02.parquet')
```

- Ce code est écrit **hors de toute fonction**. Il s'exécute donc une seule fois, dès que Python lit le fichier, avant même le lancement du flow. Les données sont chargées en mémoire une fois pour les 27 jours ; relire le Parquet à chaque tour serait du gaspillage.
- `reference_data` : la validation de janvier, avec sa colonne `prediction`, produite par le notebook. C'est le « normal ».
- `open(..., 'rb')` : ouverture en lecture (*read*) **binaire** (le fichier n'est pas du texte). `joblib.load` reconstruit le modèle entraîné.
- `raw_data` : **tout** février, brut, non nettoyé (voir §5, point 1).
- **Chemins relatifs** : `'data/...'` est relatif au **dossier courant du terminal**, pas à l'emplacement du script. Lance le script depuis `05-monitoring/`, sinon `FileNotFoundError`.
- Ces variables sont **globales** : les fonctions plus bas les utilisent sans les recevoir en paramètre. Quand Python ne trouve pas un nom dans la fonction, il le cherche au niveau du module. Pratique dans un petit script ; dans un projet plus gros, on préfère passer les données en paramètre, ce qui rend les fonctions testables séparément.

### 3.5 Configurer Evidently (lignes 39 à 53)

```python
begin = datetime.datetime(2022, 2, 1, 0, 0)
num_features = ['passenger_count', 'trip_distance', 'fare_amount', 'total_amount']
cat_features = ['PULocationID', 'DOLocationID']
column_mapping = ColumnMapping(
    prediction='prediction',
    numerical_features=num_features,
    categorical_features=cat_features,
    target=None
)

report = Report(metrics = [
    ColumnDriftMetric(column_name='prediction'),
    DatasetDriftMetric(),
    DatasetMissingValuesMetric()
])
```

- `begin` : l'**origine du temps** du rejeu, le 1er février 2022 à minuit. Le jour `i` commencera à `begin + i jours`. Instant naïf, cohérent avec la colonne sans fuseau.
- `num_features` / `cat_features` : **copies exactes** des listes du notebook. Le modèle doit recevoir les mêmes colonnes, dans le même ordre, qu'à l'entraînement : scikit-learn vérifie les noms et l'ordre, et lève une erreur s'ils diffèrent.
- `column_mapping` et `report` : identiques au notebook (doc baseline, §6.1 et §6.2). Le `Report` est créé **une fois** ; chaque appel à `run()` recalcule tout et remplace le résultat précédent.

Rappel des trois métriques et de leur lecture :

| Position dans la liste | Métrique | Ce qu'on en extrait | Lecture |
|---|---|---|---|
| 0 | `ColumnDriftMetric(column_name='prediction')` | `drift_score` | Écart entre les prédictions du jour et celles de la référence. Plus haut = plus de dérive ; seuil 0,1 |
| 1 | `DatasetDriftMetric()` | `number_of_drifted_columns` | Combien des 7 colonnes analysées (6 features + prédiction) ont dérivé |
| 2 | `DatasetMissingValuesMetric()` | `current.share_of_missing_values` | Part des cellules vides du jour, sur toutes les colonnes |

### 3.6 Les décorateurs `@task` et `@flow`

**Qu'est-ce qu'un décorateur ?** Une fonction qui en **enveloppe** une autre pour lui ajouter un comportement, sans toucher à son code. Exemple fait maison :

```python
def chronometre(fonction):
    def enveloppe(*args, **kwargs):          # accepte n'importe quels arguments…
        debut = time.time()
        resultat = fonction(*args, **kwargs) # …et les transmet à la fonction d'origine
        print(f"{fonction.__name__} : {time.time() - debut:.2f} s")
        return resultat
    return enveloppe

@chronometre              # strictement équivalent à : prep_db = chronometre(prep_db)
def prep_db():
    ...
```

Désormais, chaque appel à `prep_db()` affiche sa durée. Le `@` n'est qu'un raccourci d'écriture.

`@task` et `@flow` de Prefect suivent le même principe, en plus riche. Avant et après chaque appel, ils enregistrent auprès du serveur Prefect le début, la fin, le statut (*Completed*, *Failed*), les logs et les paramètres :

| Décorateur | Posé sur | Produit à chaque exécution du script |
|---|---|---|
| `@flow` | `batch_monitoring_backfill` | 1 *flow run* (l'exécution du workflow complet) |
| `@task` | `prep_db`, `calculate_metrics_postgresql` | 1 + 27 *task runs* (une par étape) |

La preuve que c'est de l'instrumentation pure : retire les décorateurs et l'import de Prefect, le script calcule et insère exactement les mêmes valeurs.

**La trace rouge `Error encountered when computing cache key`** (§7 du cours principal). Par défaut, Prefect 3 calcule une « empreinte » des arguments de chaque tâche pour éviter de recalculer un appel identique : c'est le **cache**. Or `calculate_metrics_postgresql` reçoit un curseur de base de données, qui ne peut pas être converti en empreinte. Prefect signale l'erreur, renonce au cache et continue. Correction possible (non testée ici) : `from prefect.cache_policies import NO_CACHE`, puis `@task(cache_policy=NO_CACHE)`.

### 3.7 `calculate_metrics_postgresql(curr, i)` : le cœur, en 5 étapes (lignes 64 à 84)

```python
@task
def calculate_metrics_postgresql(curr, i):
	current_data = raw_data[(raw_data.lpep_pickup_datetime >= (begin + datetime.timedelta(i))) &
		(raw_data.lpep_pickup_datetime < (begin + datetime.timedelta(i + 1)))]

	#current_data.fillna(0, inplace=True)
	current_data['prediction'] = model.predict(current_data[num_features + cat_features].fillna(0))

	report.run(reference_data = reference_data, current_data = current_data,
		column_mapping=column_mapping)

	result = report.as_dict()

	prediction_drift = result['metrics'][0]['result']['drift_score']
	num_drifted_columns = result['metrics'][1]['result']['number_of_drifted_columns']
	share_missing_values = result['metrics'][2]['result']['current']['share_of_missing_values']

	curr.execute(
		"insert into dummy_metrics(timestamp, prediction_drift, num_drifted_columns, share_missing_values) values (%s, %s, %s, %s)",
		(begin + datetime.timedelta(i), prediction_drift, num_drifted_columns, share_missing_values)
	)
```

Nouveauté par rapport à `dummy` : la fonction reçoit `i`, le **numéro du jour** (0 = 1er février).

#### Étape 1 : isoler les courses du jour `i`

```python
current_data = raw_data[(raw_data.lpep_pickup_datetime >= (begin + datetime.timedelta(i))) &
	(raw_data.lpep_pickup_datetime < (begin + datetime.timedelta(i + 1)))]
```

À lire de l'intérieur vers l'extérieur :

1. `begin + datetime.timedelta(i)` : minuit du jour `i`. Pour `i = 3` : le 4 février à 00:00.
2. `raw_data.lpep_pickup_datetime >= ...` : compare **chaque ligne** à cet instant. Le résultat est une *Series* de `True`/`False`, une valeur par course : un **masque**.
3. `&` : « ET » ligne à ligne entre les deux masques. Le mot-clé `and` ne marche pas ici : il attend deux valeurs simples, pas deux colonnes, et lève `ValueError: The truth value of a Series is ambiguous`.
4. Les parenthèses autour de chaque comparaison sont **obligatoires** : `&` est prioritaire sur `>=` et `<`. Sans elles, Python calculerait d'abord le `&` au milieu.
5. `raw_data[masque]` ne garde que les lignes à `True`.

L'intervalle est **semi-ouvert** : [minuit du jour `i` ; minuit du jour `i+1`[. Une course à minuit pile compte pour le jour qui commence, jamais pour les deux. C'est l'équivalent de `.between(..., inclusive="left")` dans le notebook.

`lpep_pickup_datetime` est l'heure de prise en charge du client (colonne du jeu de données NYC).

#### Étape 2 : prédire

```python
#current_data.fillna(0, inplace=True)
current_data['prediction'] = model.predict(current_data[num_features + cat_features].fillna(0))
```

- `current_data[num_features + cat_features]` : les 6 colonnes du modèle (concaténation des deux listes).
- `.fillna(0)` remplace les valeurs manquantes (NaN) par 0 **dans une copie**. `LinearRegression` refuse les NaN (`ValueError: Input X contains NaN`).
- `model.predict(...)` renvoie un tableau numpy, une prédiction par course, rangé dans une nouvelle colonne `prediction`.

**Pourquoi la ligne `fillna(0, inplace=True)` est-elle commentée ?** `inplace=True` modifierait `current_data` lui-même, **toutes colonnes comprises**. Les cellules vides disparaîtraient avant qu'Evidently ne les compte, et `share_missing_values` tomberait à 0 : le monitoring deviendrait aveugle au problème qu'il doit détecter.

C'est la leçon clé du bloc : **le modèle a besoin de données propres, le monitoring a besoin des données telles qu'elles arrivent.** On nettoie donc une copie pour le modèle, et on laisse l'original intact pour Evidently.

Avec pandas < 3, cette ligne affiche un `SettingWithCopyWarning` : `current_data` est un extrait de `raw_data`, et pandas ne sait pas si tu veux aussi modifier l'original. Sans conséquence ici ; la bonne pratique serait d'ajouter `.copy()` à la fin de l'étape 1.

#### Étape 3 : calculer

```python
report.run(reference_data = reference_data, current_data = current_data, column_mapping=column_mapping)
```

Evidently compare les ~25 000 lignes de la référence aux ~2 000 courses du jour, colonne par colonne. Méthodes et seuils : doc baseline, §6.3.

#### Étape 4 : extraire trois nombres

```python
result = report.as_dict()
prediction_drift     = result['metrics'][0]['result']['drift_score']
num_drifted_columns  = result['metrics'][1]['result']['number_of_drifted_columns']
share_missing_values = result['metrics'][2]['result']['current']['share_of_missing_values']
```

`as_dict()` convertit le rapport en dictionnaire Python. On y descend niveau par niveau :

```
result                                    ← dictionnaire
└── 'metrics'                             ← liste, dans l'ordre du Report
    ├── [0]  ColumnDriftMetric
    │   └── 'result' → 'drift_score'
    ├── [1]  DatasetDriftMetric
    │   └── 'result' → 'number_of_drifted_columns'
    └── [2]  DatasetMissingValuesMetric
        └── 'result' → 'current' → 'share_of_missing_values'
```

`[0]`, `[1]`, `[2]` sont des **positions** : elles dépendent de l'ordre des métriques dans `Report(metrics=[...])`. Change cet ordre sans changer l'extraction, et le script lira silencieusement la mauvaise métrique, ou plantera sur une clé absente (`KeyError`).

#### Étape 5 : insérer, daté du jour des données

```python
curr.execute("insert into dummy_metrics(...) values (%s, %s, %s, %s)",
	(begin + datetime.timedelta(i), prediction_drift, num_drifted_columns, share_missing_values))
```

L'horodatage est `begin + i jours`, la date **des données**, pas l'heure actuelle. D'où les courbes en février 2022 dans Grafana.

Deux notions de temps à distinguer :

| Notion | Définition | Ici |
|---|---|---|
| *Event time* | Quand les faits ont eu lieu | Le jour de février des courses |
| *Processing time* | Quand on les traite | Aujourd'hui, pendant l'exécution |

En production normale, les deux sont proches : on calcule le matin les métriques de la veille. Dans un rejeu du passé, ils sont très éloignés, et c'est l'*event time* qu'on veut sur l'axe des X.

### 3.8 `batch_monitoring_backfill()` : la boucle (lignes 86 à 101)

```python
@flow
def batch_monitoring_backfill():
	prep_db()
	last_send = datetime.datetime.now() - datetime.timedelta(seconds=10)
	with psycopg.connect("host=localhost port=5432 dbname=test user=postgres password=example", autocommit=True) as conn:
		for i in range(0, 27):
			with conn.cursor() as curr:
				calculate_metrics_postgresql(curr, i)

			new_send = datetime.datetime.now()
			seconds_elapsed = (new_send - last_send).total_seconds()
			if seconds_elapsed < SEND_TIMEOUT:
				time.sleep(SEND_TIMEOUT - seconds_elapsed)
			while last_send < new_send:
				last_send = last_send + datetime.timedelta(seconds=10)
			logging.info("data sent")
```

- **Le nom.** *Backfill* : remplir après coup un historique manquant, en calculant en une fois les métriques de jours passés. Ici, on s'en sert pour **simuler** la production en rejouant février.
- **`for i in range(0, 27)`** : `i` prend les valeurs 0 à 26 (la borne de fin est exclue), soit du 1er au 27 février. Le 28 n'est pas traité (§5).
- **Ce qui change dans le rythme** par rapport à `dummy` :
  - `last_send = now − 10 s` : l'heure prévue est « déjà passée », donc le premier jour part sans attendre.
  - `while last_send < new_send: last_send += 10 s` remplace le simple `+ 10 s`. L'intention : si le calcul d'un jour a pris du retard, faire avancer la grille jusqu'au présent au lieu de rester en retard.

**Le rythme réel n'est pas régulier** [vérifié en exécutant la même boucle avec un calcul simulé de 1 s] :

```
jour 0 inséré à t =  1 s
jour 1 inséré à t =  2 s
jour 2 inséré à t = 21 s
jour 3 inséré à t = 22 s
jour 4 inséré à t = 41 s
jour 5 inséré à t = 42 s
```

Les jours arrivent **par paires, toutes les 20 s**. La cause : `new_send` est mesuré **avant** la pause, et le `while` pousse la grille d'un cran de trop un tour sur deux. En moyenne, on garde bien un jour toutes les 10 s, donc ≈ 4 min 30 au total. Sans conséquence pour la démo : dans Grafana, les points apparaissent deux par deux. Le phénomène se produit tant que le calcul d'un jour prend moins de 5 s environ. Au-delà (entre 5 et 10 s), le rythme redevient régulier.

### 3.9 Voir le résultat

- **Terminal** : les logs de Prefect (nom du *flow run*, début et fin de chaque *task run*), 27 lignes `data sent`, et éventuellement la trace rouge de cache (§3.6).
- **Grafana** : dashboard *New dashboard*, fenêtre du 1er au 28 février 2022, rafraîchissement automatique. Les 3 panels se remplissent.
- **Adminer** : même requête qu'au §2.8 ; les colonnes ont changé.

---

## 4. Le trajet d'une valeur, de bout en bout

Suivons le `drift_score` du 4 février (`i = 3`) :

```
data/green_tripdata_2022-02.parquet
    │  pd.read_parquet (une fois, au chargement du script)
    ▼
raw_data : tout février
    │  masque : 4 février 00:00 ≤ prise en charge < 5 février 00:00
    ▼
current_data : ~2 000 courses
    │  model.predict(6 colonnes, NaN → 0 dans une copie)
    ▼
current_data + colonne 'prediction'
    │  report.run(reference_data, current_data)
    ▼
report.as_dict()['metrics'][0]['result']['drift_score']  →  un nombre, ex. 0,0x
    │  INSERT ('2022-02-04 00:00:00', drift, nb_colonnes, part_manquante) via localhost:5432
    ▼
PostgreSQL : une ligne de plus dans dummy_metrics
    │  Grafana : SELECT ... WHERE $__timeFilter("timestamp"), via db:5432
    ▼
un point sur la courbe « Prediction Drift », à la date du 4 février
```

---

## 5. Remarques d'expert

Ces points viennent de la lecture du code. Ils ne sont pas traités dans les vidéos et **ne demandent aucune correction pour suivre le cours**.

1. **Référence nettoyée, février brut.** Le notebook filtre janvier (durées de 0 à 60 min, 1 à 8 passagers, ce qui supprime aussi les lignes sans nombre de passagers). Le script ne filtre **pas** février. Evidently compare donc du propre à du brut : une partie du drift et des valeurs manquantes mesurés vient de cette asymétrie, pas d'un vrai changement. En production, on applique la même préparation aux deux jeux, en gardant brut ce qu'on veut surveiller (les valeurs manquantes, par exemple). C'est un arbitrage.
2. **Le 28 février n'est jamais traité.** `range(0, 27)` couvre 27 jours ; février 2022 en compte 28. `range(0, 28)` le couvrirait.
3. **Rythme en rafales** (§3.8).
4. **Nombres « magiques ».** Le script factice compare à `SEND_TIMEOUT` mais avance la grille de `timedelta(seconds=10)` écrit en dur. Le script Evidently a le même défaut aux lignes 89 et 100. Changer la constante ne change donc pas grand-chose (exercice 2).
5. **Imports inutilisés** (§1.2).
6. **Chaîne de connexion répétée 3 fois, mot de passe en clair.** À factoriser dans une constante, et à lire depuis une variable d'environnement (`os.getenv("POSTGRES_PASSWORD")`), en cohérence avec le §8 du cours principal (fichier `.env`).
7. **Extraction par position** (§3.7, étape 4). Plus robuste : vérifier `result['metrics'][k]['metric']`, qui contient le nom de la métrique, avant de lire la valeur.
8. **`DROP TABLE` à chaque lancement.** Parfait pour une démo, désastreux en production : tout l'historique est perdu. En production : `CREATE TABLE IF NOT EXISTS`, une contrainte d'unicité sur `timestamp` et `INSERT ... ON CONFLICT ("timestamp") DO UPDATE ...`. Relancer le calcul d'un jour remplace alors sa ligne au lieu de créer un doublon (idempotence, comme `prep_db`).
9. **La boucle avec `sleep` est un artifice de démo.** En production, pas de boucle : un planificateur (un *deployment* Prefect avec un *schedule*, ou `cron`) lance le flow une fois par jour pour traiter la veille. La fonction `@flow` est déjà la bonne unité pour ça ; il suffirait qu'elle prenne la date à traiter en paramètre.

---

## 6. Exercices

Du plus simple au plus avancé. Les réponses sont repliées.

**1. (débutant)** Pendant que le script factice tourne, lance `SELECT count(*) FROM dummy_metrics;` dans Adminer, puis relance-le une minute plus tard. Quel écart attends-tu ?

<details><summary>Réponse</summary>

Environ 6 lignes de plus : une toutes les 10 s.
</details>

**2. (débutant)** Dans le script factice, passe `SEND_TIMEOUT` à `2`. À quel rythme partent les envois ?

<details><summary>Réponse</summary>

Deux premiers envois à 2 s d'intervalle, puis de nouveau un toutes les 10 s. La grille avance toujours de `timedelta(seconds=10)`, écrit en dur (§5, point 4). Il faudrait écrire `timedelta(seconds=SEND_TIMEOUT)`.
</details>

**3. (intermédiaire)** Retire `autocommit=True` de la connexion de `main()` dans le script factice. Que voit Grafana pendant les 16 minutes ? Et si tu fais Ctrl+C au bout de 5 minutes ?

<details><summary>Réponse</summary>

Rien pendant 16 minutes : les `INSERT` restent dans une transaction non validée, invisible des autres connexions. Tout apparaît d'un coup au commit, à la sortie du `with`. Avec Ctrl+C, le `with` sort sur une exception, donc **rollback** : aucune ligne n'est conservée.
</details>

**4. (intermédiaire)** Pourquoi `fillna(0)` est-il appliqué *dans* l'appel à `predict` plutôt que sur `current_data` ?

<details><summary>Réponse</summary>

Pour que le modèle reçoive des données sans NaN, tout en laissant `current_data` intact pour qu'Evidently compte les vraies valeurs manquantes (§3.7, étape 2).
</details>

**5. (avancé)** Ajoute une 4ᵉ métrique : le drift de `trip_distance`. Liste tous les endroits à modifier.

<details><summary>Réponse</summary>

Cinq endroits, preuve que les blocs sont liés par des « contrats » :

1. SQL de création : ajouter `trip_distance_drift float`.
2. `Report` : ajouter `ColumnDriftMetric(column_name='trip_distance')` **en fin de liste**, pour ne pas décaler les positions 0 à 2.
3. Extraction : `result['metrics'][3]['result']['drift_score']`.
4. `INSERT` : ajouter la colonne, un 5ᵉ `%s` et la valeur dans le tuple.
5. Grafana : un nouveau panel qui lit `trip_distance_drift`, puis export du JSON dans `dashboards/` (vidéo 5.8).
</details>

**6. (avancé)** Fais traiter le 28 février, et rends l'extraction indépendante de l'ordre des métriques.

<details><summary>Réponse</summary>

`range(0, 28)`. Pour l'extraction, indexer les résultats par nom :

```python
par_nom = {m['metric']: m['result'] for m in result['metrics']}
prediction_drift = par_nom['ColumnDriftMetric']['drift_score']
```

Limite : si le `Report` contient deux métriques du même type (deux `ColumnDriftMetric`), la seconde écrase la première dans le dictionnaire. Il faut alors aussi vérifier `column_name`.
</details>

---

## 7. Récapitulatif

| Notion | En une phrase |
|---|---|
| Script factice | Teste la chaîne Python → PostgreSQL → Grafana avec des valeurs aléatoires, avant d'y brancher le ML. |
| Script vs notebook | Le notebook sert à prototyper ; le script tourne sans humain, donc il peut être automatisé. |
| Le script, « colle » de l'architecture | Evidently calcule, PostgreSQL stocke, Grafana affiche : seul le script relie le calcul au stockage. |
| Serveur > base > table | Le serveur `db` héberge les bases `postgres` et `test` ; la table `dummy_metrics` est dans `test`. |
| Connexion / curseur | Le canal vers une base / l'objet qui y envoie les requêtes. |
| Transaction, commit, autocommit | Les modifications ne sont visibles des autres qu'une fois validées ; autocommit valide chaque requête. |
| Requête paramétrée (`%s`) | psycopg insère les valeurs lui-même : types corrects, pas d'injection SQL. |
| Idempotence | Relancer donne le même résultat (`prep_db`). |
| Boucle métronome | Se caler sur une grille de temps fixe plutôt que sur la fin de la tâche précédente. |
| `if __name__ == '__main__'` | Le code ne s'exécute que si le fichier est lancé directement. |
| Code au niveau du module | S'exécute une fois, au chargement du fichier (données, modèle, `Report`). |
| Masque booléen + `&` | Filtrer les lignes d'un DataFrame ; parenthèses obligatoires. |
| Intervalle semi-ouvert | [début ; fin[ : chaque course comptée une seule fois. |
| `fillna` sur une copie | Données propres pour le modèle, données brutes pour le monitoring. |
| `as_dict()[...]` | Chemin vers un nombre dans le rapport ; les positions suivent l'ordre du `Report`. |
| *Event time* vs *processing time* | Horodater avec la date des données, pas l'heure du calcul. |
| Décorateur (`@task`, `@flow`) | Enveloppe une fonction pour lui ajouter un comportement, ici le suivi par Prefect. |
| *Backfill* | Calculer après coup les métriques de périodes passées. |
