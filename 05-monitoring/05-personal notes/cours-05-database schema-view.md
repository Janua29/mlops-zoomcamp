## Le schéma : un dossier à l'intérieur d'une base

Un **schéma** est un **espace de noms** à l'intérieur d'une base de données : un conteneur qui regroupe des tables (et aussi des vues, des fonctions…). C'est l'équivalent d'un **dossier** dans lequel on range des fichiers.

Ton fil d'Ariane dans Adminer montre justement toute la hiérarchie :

```
PostgreSQL  »  db  »  test  »  public  »  dummy_metrics
   │           │       │        │          │
 moteur     serveur   base    schéma     table
```

| Niveau | Dans ton cas | Analogie système de fichiers |
|---|---|---|
| Serveur | `db` | L'ordinateur |
| Base de données | `test` | Un disque |
| Schéma | `public` | Un dossier sur ce disque |
| Table | `dummy_metrics` | Un fichier dans ce dossier |

Attention à un piège : ici, `db` n'est **pas** une base de données. C'est le nom du **service Docker** Postgres dans ton `docker-compose.yml`. C'est le nom d'hôte du serveur sur le réseau Docker, et c'est ce que tu as tapé dans le champ « Server » d'Adminer. La base, c'est `test`.

## Pourquoi `public` ?

Chaque base Postgres est créée avec un schéma nommé **`public`**, et c'est le schéma utilisé **par défaut**. Dans le script du module (`dummy_metrics_calculation.py`), la table est créée sans préciser de schéma :

```sql
create table dummy_metrics(...)
```

Postgres l'a donc rangée dans `public`. Le nom complet de ta table est en réalité `public.dummy_metrics`. Tu peux écrire simplement `dummy_metrics` grâce à un réglage appelé **`search_path`** : c'est la liste des schémas où Postgres cherche une table quand tu ne précises pas lequel, et par défaut `public` en fait partie. C'est le même principe que le `PATH` de ton terminal, qui permet de taper `python` sans donner le chemin complet de l'exécutable.

Il existe aussi des schémas **système** dans chaque base : `pg_catalog` et `information_schema`. Ils contiennent les métadonnées, c'est-à-dire la liste des tables, des colonnes, etc. Tu peux voir tous les schémas avec :

```sql
SELECT schema_name FROM information_schema.schemata;
```

## À quoi ça sert concrètement ?

Un schéma sert d'abord à **organiser** les tables. Une équipe data sépare souvent les étapes d'un pipeline, par exemple `raw.trips` pour les données brutes, `staging.trips` pour les données nettoyées et `monitoring.drift_metrics` pour les métriques. Les deux premières tables portent le même nom `trips`, et elles coexistent sans conflit parce qu'elles sont dans des schémas différents, comme deux fichiers de même nom dans deux dossiers.

Un schéma sert aussi à gérer des **permissions** : on peut donner à un utilisateur le droit de lire `monitoring` sans qu'il puisse toucher à `raw`. Grafana, par exemple, pourrait n'avoir accès qu'au schéma des métriques.

## Base ou schéma : quelle différence ?

Les deux regroupent des tables, alors pourquoi deux niveaux ? La différence clé est la suivante : dans Postgres, **une requête peut joindre des tables de schémas différents, mais pas de bases différentes**.

```sql
-- OK : deux schémas de la même base
SELECT * FROM raw.trips JOIN monitoring.drift_metrics ...

-- Impossible nativement : la base "test" et une autre base "prod"
```

Une base est donc un espace **isolé**. Les schémas sont des compartiments **dans** un même espace, qui peuvent communiquer entre eux. On choisit des bases séparées pour isoler complètement des projets, et des schémas pour organiser un même projet.

Dans le module 05, tout tient dans `test.public`, ce qui suffit largement. Les schémas deviennent utiles quand une base grossit et héberge plusieurs usages.

---

**Petite vérification de compréhension :** si demain tu crées une table `evidently_metrics` dans la base `test` sans préciser de schéma, puis une autre table `evidently_metrics` dans un schéma `monitoring` que tu aurais créé, les deux peuvent-elles exister en même temps ? Et laquelle obtiens-tu avec `SELECT * FROM evidently_metrics;` ?


## L'idée centrale : table vs view

Une **table** stocke des données. Une **view** (vue) ne stocke aucune donnée : c'est une **requête `SELECT` enregistrée sous un nom**, que Postgres réexécute chaque fois que tu l'interroges.

Une analogie culinaire : la table est un **plat préparé rangé au frigo** (il existe physiquement, tu le sors quand tu veux). La view est une **recette** : elle ne prend presque pas de place, et chaque fois que tu la demandes, on cuisine le plat à partir des ingrédients frais, c'est-à-dire des tables.

Ou en pandas : une table, c'est un DataFrame sauvegardé en parquet ; une view, c'est une fonction qui lit ce parquet et renvoie un DataFrame filtré ou agrégé, recalculé à chaque appel.

## Un exemple avec ta table du module 05

`dummy_metrics` reçoit une ligne toutes les 10 secondes. Imaginons que tu veuilles souvent les moyennes par minute :

```sql
CREATE VIEW metrics_per_minute AS
SELECT
    date_trunc('minute', timestamp) AS minute,
    avg(value1) AS avg_value1,
    count(*)    AS n_rows
FROM dummy_metrics
GROUP BY 1;
```

Ensuite, tu l'interroges exactement comme une table :

```sql
SELECT * FROM metrics_per_minute ORDER BY minute DESC;
```

En coulisses, Postgres remplace `metrics_per_minute` par sa définition et exécute la vraie requête sur `dummy_metrics`. Si le script vient d'insérer une nouvelle ligne, la view en tient compte immédiatement : elle est **toujours à jour**, puisqu'elle ne garde rien en mémoire.

## Les différences en un tableau

| | Table | View |
|---|---|---|
| Ce qui est stocké | Les données (lignes sur disque) | Seulement la définition (le texte du `SELECT`) |
| Origine des données | Remplie par des `INSERT` | Calculée à partir d'une ou plusieurs tables |
| Fraîcheur | Ce qu'on y a inséré | Toujours le reflet actuel des tables sous-jacentes |
| Coût à la lecture | Lecture directe | La requête est réexécutée à chaque fois |
| Écriture (`INSERT`, `UPDATE`) | Oui | Seulement pour les views simples (une seule table, sans agrégation ni `GROUP BY`) ; sinon impossible |
| Si on supprime la table source | — | Postgres refuse de supprimer la table tant qu'une view en dépend (sauf `DROP ... CASCADE`, qui supprime aussi la view) |

## Pourquoi utiliser une view ?

Une view sert d'abord à **simplifier** : une jointure compliquée ou une agrégation que tu réécris souvent est définie une fois, puis tout le monde l'interroge avec un simple `SELECT *`. Dans Grafana, par exemple, un panneau pourrait lire `metrics_per_minute` au lieu de contenir lui-même la requête d'agrégation.

Elle sert aussi à **contrôler l'accès** : tu peux donner à quelqu'un le droit de lire une view qui ne montre que certaines colonnes, sans lui donner accès à la table complète.

Enfin, elle offre une **interface stable** : si la structure des tables change (une colonne renommée, une table découpée en deux), tu adaptes la définition de la view, et les outils qui la lisent ne voient aucune différence. C'est le même principe que `test.py` dans le module 04 : il parle à une adresse fixe sans savoir ce qui tourne derrière.

## Le cas intermédiaire : la view matérialisée

Le défaut d'une view, c'est qu'elle recalcule tout à chaque lecture. Sur une table de plusieurs millions de lignes avec une agrégation lourde, ça peut devenir lent.

Postgres propose donc la **view matérialisée**, qui **stocke le résultat** comme une table :

```sql
CREATE MATERIALIZED VIEW metrics_per_minute_mat AS
SELECT ...;   -- même requête

REFRESH MATERIALIZED VIEW metrics_per_minute_mat;  -- à relancer pour mettre à jour
```

La lecture est rapide, mais les données ne sont plus automatiquement fraîches : elles datent du dernier `REFRESH`. On retombe sur l'analogie du plat : on a cuisiné la recette une fois et rangé le résultat au frigo, et il faut le refaire quand les ingrédients changent. En pratique, un job planifié (Prefect ou Airflow, par exemple) lance le `REFRESH` régulièrement.

| | View | View matérialisée | Table |
|---|---|---|---|
| Stocke les données | Non | Oui (le résultat de la requête) | Oui |
| Toujours à jour | Oui | Non, jusqu'au `REFRESH` | Selon les `INSERT` |
| Lecture rapide | Dépend de la requête | Oui | Oui |

---

**Pour vérifier :** si tu crées la view `metrics_per_minute` ci-dessus, puis que tu fais `DROP TABLE dummy_metrics;` sans `CASCADE`, que se passe-t-il selon toi ?