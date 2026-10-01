# Cours : workflow et flux d'information — Monitoring avec Evidently, PostgreSQL et Grafana (`05-monitoring`)

> **Dossier** : `05-monitoring/` : 2 notebooks, 2 scripts Python, `docker-compose.yml`, `config/` (2 fichiers YAML pour Grafana), `dashboards/data_drift.json`, `requirements.txt`, `data/` et `models/` (vides au départ), `post-evidently-0.7/` (variante), `README.md`.
> **Vidéos** : 5.1 à 5.9.
> **Ton fork et l'original** (comparés le 01/10/2026) : le code est identique (scripts, cellules de code des notebooks, `config/`, `dashboards/`, `requirements.txt`, `post-evidently-0.7/`). Chez toi, la ligne `version: '3.7'` de `docker-compose.yml` est commentée (Compose v2 la signale comme obsolète), et tu as ajouté tes notes (`05-personal notes/`, cellules d'explication dans le notebook baseline) et `workspace/`. L'original a réécrit son `README.md` en une page par vidéo (`01-ml-monitoring.md` … `10-monitoring-example.md`) : même déroulé, avec des conseils généraux en plus. La note sur Prefect (07:33-11:21) ne subsiste que dans ton README.
>
> **Convention** : le cours suit l'ordre des vidéos. Un encadré **▲ Ton fork** donne ce que tu tapes réellement dans ton Codespace.
>
> **Pour le détail** : tes notes de `05-personal notes/` (architecture, scripts, Grafana, réseaux Docker) et `cours-05-monitoring-baseline-notebook.md` (le notebook cellule par cellule). Ce cours-ci répond seulement à : **quoi lancer, où, dans quel ordre, et qu'est-ce qui circule**.

---

## 1. La vision globale

La vidéo 5.1 (théorie, rien à lancer) distingue 4 familles de métriques à surveiller : la santé du service, la performance du modèle, la qualité des données et la dérive. Le module calcule les deux dernières. La performance demanderait la vraie durée des courses, qu'on ne fournit pas à Evidently (`target=None`).

Le principe : chaque jour du 1er au 27 février 2022 joue le rôle d'un « lot de production ». On le compare à la **référence** (des données de janvier), on calcule 3 métriques, on les range dans une base, et Grafana les trace jour après jour. Les numéros entre crochets sont ceux des phases.

```
 SANS DOCKER : Python et fichiers du Codespace                    AVEC DOCKER : 3 conteneurs

 ┌─────────────────────────────────────────────┐
 │ [1-3] notebook baseline_model_nyc_taxi_data │
 └──────┬───────────────────────────────┬──────┘
        │ écrit                         │ écrit
        ▼                               ▼
 data/green_tripdata_2022-01.parquet    workspace/ ──lu par──▶ [3] evidently ui (port 8000)
 data/green_tripdata_2022-02.parquet
 data/reference.parquet
 models/lin_reg.bin
        │                                                          ┌───────────────────────┐
        │ lus par                                                  │ db : PostgreSQL       │
        ├──▶ [5] evidently_metrics_calculation.py ──────INSERT───▶ │   base test           │
        │                                                          │   table dummy_metrics │
        │    [4] dummy_metrics_calculation.py ──────────INSERT───▶ │                       │
        │        (valeurs aléatoires, ne lit aucun fichier)        └─────▲────────────▲────┘
        ▼                                                          SELECT│      SELECT│
 [7] notebook debugging_nyc_taxi_data                              ┌─────┴─────┐ ┌────┴──────┐
                                                                   │ grafana   │ │ adminer   │
                                                                   │ port 3000 │ │ port 8080 │
                                                                   └───────────┘ └───────────┘
```

| Phase | Qui | Fait quoi |
|---|---|---|
| 1 à 3 | Le notebook baseline | Télécharge janvier et février, entraîne une régression linéaire sur janvier, sauvegarde le modèle et la référence (la partie validation de janvier). Puis essaie Evidently en direct : un rapport, un dashboard. |
| 3 | `evidently ui` | Un petit serveur web qui affiche les rapports rangés dans `workspace/`. Ni base, ni Docker. |
| 4 | Le script factice | Insère des valeurs aléatoires : on teste le tuyau vers la base avant d'y mettre de vraies métriques. |
| 5 | Le script Evidently | Pour chaque jour : prédit, compare à la référence, insère 3 nombres dans PostgreSQL. |
| 4 à 6 | Grafana, Adminer | Lisent la base. Grafana trace les nombres dans le temps, Adminer montre les tables brutes. Aucun des deux ne calcule. |
| 7 | Le notebook debugging | Zoome sur un jour suspect avec des rapports Evidently détaillés. |

**L'idée à retenir** : deux mondes. À gauche, tout se passe dans Python et des fichiers. À droite, les métriques sont stockées dans une base et dessinées dans le temps : il faut PostgreSQL et Grafana, que Docker fournit. Le script de la phase 5 est le pont entre les deux.

### Les phases et leurs fichiers

| Phase | Vidéo | Ce qu'on lance | Fichiers du dossier | Docker ? |
|---|---|---|---|---|
| 0 | 5.2 | L'environnement Python, puis les 3 services | `requirements.txt`, `docker-compose.yml`, `config/grafana_datasources.yaml` | Démarrage |
| 1 | 5.3 | Notebook baseline, partie modèle | `baseline_model_nyc_taxi_data.ipynb` → `data/`, `models/` | Non |
| 2 | 5.4 | Même notebook, partie *Evidently Report* | idem | Non |
| 3 | 5.5 | Même notebook, partie *Evidently Dashboard*, puis `evidently ui` | idem → `workspace/` | Non |
| 4 | 5.6 | Le script factice | `dummy_metrics_calculation.py` | Oui |
| 5 | 5.7 | Le script Evidently, sans ou avec serveur Prefect | `evidently_metrics_calculation.py` | Oui |
| 6 | 5.8 | Sauvegarder le dashboard Grafana dans des fichiers | `config/grafana_dashboards.yaml`, `dashboards/data_drift.json` | Oui |
| 7 | 5.9 | Notebook debugging | `debugging_nyc_taxi_data.ipynb` | Non |
| — | — | La même chose avec Evidently ≥ 0.7 (§ 10) | `post-evidently-0.7/` | idem |

`meta.json` et `images/` servent au site du cours (liste des vidéos, miniatures) : rien à lancer.

### Les terminaux

- **Terminal 1** : les services Docker.
- **Terminal 2** : les scripts Python.
- **Terminal 3** : les serveurs d'appoint : `evidently ui` (phase 3), `prefect server start` (phase 5, optionnel).
- Les **notebooks** s'ouvrent dans VS Code.

> **Toujours depuis `05-monitoring/`** : `docker compose` y cherche `docker-compose.yml`, les scripts y cherchent `data/` et `models/`, `evidently ui` y cherche `workspace/`. Les chemins sont relatifs au dossier où tu tapes la commande.

### Six mots utilisés partout

| Mot | Sens ici |
|---|---|
| Dérive (*drift*) | Les données du jour ne se répartissent plus comme celles de la référence. Evidently mesure l'écart par un score (`drift_score`) et le compare à un seuil. |
| Référence | Le jeu « normal » auquel on compare : `data/reference.parquet`. |
| Montage (*bind mount*) | Un fichier ou dossier du Codespace rendu visible dans un conteneur, à un chemin choisi. |
| Volume | Un espace de stockage géré par Docker, qui survit à la suppression du conteneur. |
| Provisioning | Configurer Grafana par des fichiers lus au démarrage, plutôt qu'en cliquant. |
| Curseur | L'objet `psycopg` qui envoie les requêtes SQL sur une connexion ouverte. |

---

## 2. Phase 0 : préparer l'environnement (vidéo 5.2)

### Dans le terminal (vidéo et README)

```bash
cd 05-monitoring
conda create -n venv python=3.11 && conda activate venv   # ou : python -m venv venv && source ./venv/bin/activate
pip install -r requirements.txt
docker-compose up                                          # Terminal 1 : reste occupé, affiche les logs
```

La vidéo tape `docker-compose` (Compose v1, avec tiret). Ton Codespace a Compose v2 : `docker compose`, sans tiret. Les sous-commandes sont les mêmes ; la suite du cours utilise la forme v2.

### Ce que font les commandes

1. `pip install -r requirements.txt` installe, dans l'environnement Python **du Codespace** (pas dans Docker) : `evidently==0.6.7` (les calculs), `psycopg` et `psycopg_binary` (parler à PostgreSQL), `prefect` (phase 5), `pandas`, `pyarrow`, `scikit-learn`, `joblib` (données et modèle), `requests`, `tqdm` (téléchargement), `jupyter`, `matplotlib` (notebooks).
2. `docker compose up` lit `docker-compose.yml` dans le dossier courant et démarre 3 conteneurs :

| Service | Image | Port publié | Rôle |
|---|---|---|---|
| `db` | `postgres` | 5432 | La base des métriques. Utilisateur `postgres`, mot de passe `example`. |
| `adminer` | `adminer` | 8080 | Une page web pour regarder dans la base. |
| `grafana` | `grafana/grafana-enterprise` | 3000 | Les dashboards. |

3. Au démarrage, Grafana lit `config/grafana_datasources.yaml` (provisioning) : la connexion à PostgreSQL (`db:5432`, base `test`) est créée sans aucun clic. Les deux autres montages de Grafana, `config/grafana_dashboards.yaml` et `dashboards/`, arrivent à la vidéo 5.8.

### Vérifier

- `docker compose ps` : 3 services *Up*.
- **Grafana** (port 3000) : identifiants `admin` / `admin` ; il propose de changer le mot de passe, tu peux passer.
- **Adminer** (port 8080) : Système *PostgreSQL*, Serveur `db`, Utilisateur `postgres`, Mot de passe `example`. La base `test` n'existe pas encore : c'est le premier script (phase 4) qui la crée.

Les phases 1 à 3 n'utilisent pas ces services : tu peux aussi ne les démarrer qu'à la phase 4.

> **▲ Ton fork**
> Ton environnement pour ce module s'appelle **`py11-taximonitoring`** (Python 3.11, evidently 0.6.7, pandas 2.3.3, prefect 3.8.6 : voir `env-backups/py11-taximonitoring.yml`). Ne le recrée pas. **À chaque nouveau terminal** :
>
> ```bash
> conda activate py11-taximonitoring
> cd /workspaces/mlops-zoomcamp/05-monitoring
> python -c "import evidently, pandas; print(evidently.__version__, pandas.__version__)"   # → 0.6.7 2.3.3
> ```
>
> **Seulement si `conda env list` ne le montre plus** (nettoyage ou reconstruction du Codespace) : `conda env create -f /workspaces/mlops-zoomcamp/env-backups/py11-taximonitoring.yml`. À défaut : `conda create -n py11-taximonitoring python=3.11 -y`, l'activer, puis `pip install -r requirements.txt "pandas<3"`. `requirements.txt` ne fixe pas pandas, et pandas 3 casse Evidently 0.6.7 (§ 12).
>
> **Services** (Terminal 1) :
>
> ```bash
> docker compose up -d             # -d rend la main au terminal
> docker compose ps                # 3 services Up
> docker compose logs -f grafana   # au besoin, les logs d'un service (Ctrl+C quitte les logs, pas le service)
> ```
>
> **Navigateur** : onglet **PORTS** de VS Code (3000, 8080).
> **Ton dossier est dans son état final** : Grafana charge déjà le dashboard « New dashboard » de la vidéo 5.8. Ses 3 panneaux restent vides ou en erreur tant que la phase 5 n'a pas rempli la table.

---

## 3. Phase 1 : le modèle et la référence (vidéo 5.3), sans Docker

### Dans le terminal (vidéo)

```bash
jupyter notebook          # puis ouvrir baseline_model_nyc_taxi_data.ipynb
```

Exécuter les cellules jusqu'à la sauvegarde (`val_data.to_parquet('data/reference.parquet')`).

> **▲ Ton fork** : pas de `jupyter notebook`. Ouvre le notebook dans VS Code, *Select Kernel* (en haut à droite) → **py11-taximonitoring**, puis exécute les cellules.

### Ce que fait le notebook

1. **Télécharge** les courses de taxis verts new-yorkais de janvier et février 2022 dans `data/`.
2. **Prépare janvier** : calcule la durée de chaque course en minutes (la cible), garde les courses de 0 à 60 min et de 1 à 8 passagers.
3. **Découpe** : les 30 000 premières lignes pour entraîner (*train*), le reste pour valider.
4. **Entraîne** une régression linéaire sur 6 colonnes : 4 numériques (`passenger_count`, `trip_distance`, `fare_amount`, `total_amount`) et 2 identifiants de zone (`PULocationID`, `DOLocationID`, passés tels quels au modèle). Mesure l'erreur (MAE).
5. **Sauvegarde** le modèle dans `models/lin_reg.bin`, et la validation, avec sa colonne `prediction`, dans `data/reference.parquet`.

Février n'est pas touché : c'est la « production » simulée des phases 4 à 7.

### Vérifier

```bash
ls data models
# data:   green_tripdata_2022-01.parquet  green_tripdata_2022-02.parquet  reference.parquet
# models: lin_reg.bin
```

Ces fichiers sont ignorés par git : ils existent dans ton Codespace, pas dans ton fork sur GitHub.

---

## 4. Phase 2 : un rapport Evidently (vidéo 5.4), sans Docker

Même notebook, section *Evidently Report*.

```
 référence = train (30 000 premières lignes)  ──┐
                                                ├──▶ Report.run() ──┬──▶ report.show()    : affichage dans le notebook
 courant   = validation (reste de janvier)    ──┘                   └──▶ report.as_dict() : les chiffres, en dictionnaire Python
```

1. `ColumnMapping` dit à Evidently quelles colonnes sont numériques, catégorielles, et laquelle est la prédiction.
2. `Report` réunit 3 métriques : la dérive des prédictions (`ColumnDriftMetric`), le nombre de colonnes en dérive parmi les 6 features et la prédiction (`DatasetDriftMetric`), la part de valeurs manquantes (`DatasetMissingValuesMetric`).
3. `report.run()` calcule ; `show()` affiche ; `as_dict()` permet d'extraire les 3 nombres.

Ce sont les 3 métriques que le script de la phase 5 enverra dans PostgreSQL, un jour à la fois. Une différence : ici, la référence est le *train* ; le script, lui, compare à `reference.parquet`, c'est-à-dire la validation. Rien n'est écrit sur le disque.

---

## 5. Phase 3 : le dashboard Evidently (vidéo 5.5), sans Docker

Même notebook, section *Evidently Dashboard*, puis un terminal.

```
 notebook ──① écrit des fichiers JSON──▶ workspace/ ──② lu par──▶ evidently ui (port 8000) ──③──▶ navigateur
```

| N° | Ce qui se passe |
|---|---|
| ① | Le notebook crée le dossier `workspace/`, un **projet**, deux rapports datés du 28 et du 29 janvier et la configuration de 3 panneaux. Ces rapports décrivent la **qualité** des données de ces deux jours (nombre de lignes, valeurs manquantes), sans référence : ce n'est pas de la dérive. |
| ② | `evidently ui` lit ce dossier. |
| ③ | Tu ouvres le port 8000 : le projet *NYC Taxi Data Quality Project* et son dashboard. |

### Dans le terminal (Terminal 3)

```bash
evidently ui              # depuis 05-monitoring/ ; port 8000 ; Ctrl+C pour arrêter
```

Pendant les cellules des rapports, un avertissement `FutureWarning: 'H' is deprecated` s'affiche : normal avec pandas 2. Avec pandas 3, il devient l'erreur du § 12.

Deux dashboards différents dans ce module, à ne pas confondre :

| | Evidently UI (phase 3) | Grafana (phases 4 à 6) |
|---|---|---|
| Les données viennent de | Fichiers JSON dans `workspace/` | La base PostgreSQL |
| Docker | Non | Oui |
| Qui les remplit | Le notebook | Les scripts |

> **▲ Ton fork** : ton `workspace/` (versionné) contient **deux projets du même nom** : chaque exécution de la cellule `ws.create_project(...)` en crée un. Le premier est vide ; ouvre le second, celui qui a 3 panneaux. Pour repartir d'un seul projet : supprimer `workspace/` avant de relancer le notebook.

---

## 6. Phase 4 : monitoring factice (vidéo 5.6), avec Docker

Le but : tester le tuyau **script → PostgreSQL → Grafana** avec des valeurs aléatoires, avant d'y brancher Evidently. Si quelque chose casse ici, c'est l'infrastructure, pas le modèle.

```
 VM Codespace, Terminal 2 : python dummy_metrics_calculation.py
        │
        │ ① INSERT vers localhost:5432
        ▼
 db : PostgreSQL, base test, table dummy_metrics (timestamp, value1, value2, value3)      ← conteneur
        ▲                              ▲
        │                              │ ② SELECT vers db:5432
 grafana (port 3000)              adminer (port 8080)                                     ← conteneurs
        ▲                              ▲
        └──────────────────────────────┘ ③ ton navigateur, par l'onglet PORTS
```

| N° | Ce qui se passe |
|---|---|
| ① | Le script tourne dans la VM du Codespace. Il écrit `localhost:5432` : depuis la VM, c'est le port publié par Docker, qui mène au conteneur `db`. |
| ② | Grafana et Adminer tournent **dans** Docker. Pour eux, `localhost` serait leur propre conteneur : ils écrivent `db:5432`, le nom du service. Ça marche parce qu'ils sont branchés sur le même réseau Docker que `db` (`back-tier`). |
| ③ | Ton navigateur atteint Grafana et Adminer par la redirection de ports du Codespace. |

### Dans le terminal (Terminal 2)

```bash
python dummy_metrics_calculation.py      # 100 lignes × 10 s ≈ 17 min ; Ctrl+C pour arrêter avant
# 2026-10-01 14:19:10,867 [INFO]: data sent
# 2026-10-01 14:19:20,867 [INFO]: data sent
```

### Ce que fait le script

1. `prep_db()` se connecte au serveur PostgreSQL, crée la base `test` si elle n'existe pas, puis **supprime et recrée** la table `dummy_metrics`. Chaque lancement repart donc d'une table vide.
2. 100 fois : tire 3 valeurs au hasard (un entier de 0 à 1000, un identifiant texte, un décimal de 0 à 1), les insère avec l'heure actuelle, attend pour tenir le rythme d'une ligne toutes les 10 s, puis affiche `data sent`.

### Où regarder

- **Adminer** (port 8080), base `test`, table `dummy_metrics` : les lignes s'ajoutent.
- **Grafana** (port 3000), comme dans la vidéo : créer un dashboard à la main, source *PostgreSQL*, mode *Code*, par exemple :

  ```sql
  SELECT "timestamp" AS "time", value1
  FROM dummy_metrics
  WHERE $__timeFilter("timestamp")      -- Grafana remplace ceci par la fenêtre de temps affichée
  ORDER BY 1
  ```

  Fenêtre de temps *Last 5 minutes*, rafraîchissement automatique toutes les 5 s. (Le chemin exact des menus dépend de la version de Grafana.)

> **▲ Ton fork** : pendant cette phase, les panneaux du « New dashboard » provisionné affichent une erreur du type `column "prediction_drift" does not exist`. C'est normal : il est fait pour la table de la phase 5.

---

## 7. Phase 5 : les vraies métriques (vidéo 5.7), avec Docker

Même tuyau, mais les valeurs aléatoires sont remplacées par les 3 métriques Evidently de la phase 2, calculées jour par jour.

```
 Terminal 2 : python evidently_metrics_calculation.py

   au démarrage : lit data/reference.parquet, models/lin_reg.bin et data/green_tripdata_2022-02.parquet
                  prep_db : crée la base test si besoin, RECRÉE la table dummy_metrics
   pour i = 0 … 26, soit du 1er au 27 février :
     ① courses du jour i ─▶ ② prédiction ─▶ ③ Evidently ─▶ ④ 3 nombres
     ⑤ INSERT (date du jour i, 3 nombres) ─────▶ db : table dummy_metrics ◀───── ⑦ SELECT ── grafana (port 3000)
   ⑥ chaque étape est signalée à un serveur Prefect (temporaire, ou celui de « prefect server start »)
```

| N° | Ce qui se passe |
|---|---|
| ① | Le script isole les courses dont l'heure de départ tombe le jour `i`. |
| ② | Il prédit leur durée avec le modèle de la phase 1 (valeurs manquantes remplacées par 0 pour la prédiction). |
| ③ | Evidently compare ce jour à la référence, avec le même `Report` qu'à la phase 2. |
| ④ | `as_dict()` → dérive des prédictions, nombre de colonnes en dérive, part de valeurs manquantes. |
| ⑤ | Une ligne est insérée, **datée du jour des données** (2022-02-01, 2022-02-02…), pas de l'heure actuelle. |
| ⑥ | Les décorateurs `@flow` et `@task` font enregistrer chaque étape par Prefect. Ils ne changent aucune valeur calculée. |
| ⑦ | Grafana lit la table et trace les 3 courbes. |

La table garde le nom `dummy_metrics`, hérité de la phase 4, mais elle est recréée avec d'autres colonnes : les valeurs aléatoires de la phase 4 sont effacées.

### Variante A : sans serveur Prefect (ce que fait le README)

```bash
python evidently_metrics_calculation.py      # Terminal 2 ; environ 4 min 30
```

Ce que tu vois défiler (extrait) :

```
14:19:50.537 | INFO    | prefect - Starting temporary server on http://127.0.0.1:8150
14:19:59.053 | ERROR   | Task run 'calculate_metrics_postgresql-6eb' - Error encountered when computing cache key - result will not be persisted.
Traceback (most recent call last):            ← longue trace rouge, une fois par jour
14:19:59.417 | INFO    | Task run 'calculate_metrics_postgresql-6eb' - Finished in state Completed()
14:24:20.128 | INFO    | Flow run 'vermilion-terrier' - Finished in state Completed()
14:24:20.140 | INFO    | prefect - Stopping temporary server on http://127.0.0.1:8150
```

Trois surprises, toutes sans gravité :

1. **Les traces rouges `Error encountered when computing cache key`**, une par jour. Prefect essaie de mémoriser chaque tâche d'après ses arguments ; l'un d'eux est le curseur de la base, impossible à mémoriser. Prefect renonce et continue : chaque tâche finit en `Completed()` et la ligne est bien insérée.
2. **Pas de `data sent`** : Prefect prend la main sur l'affichage des messages Python, et le `logging.info("data sent")` du script n'est plus montré.
3. **Les jours arrivent par deux, toutes les 20 s environ** (10 s par jour en moyenne), à cause de la façon dont la boucle calcule ses pauses.

Tant que la variable `PREFECT_API_URL` n'est pas définie, Prefect démarre un serveur **temporaire** (sur un port tiré au hasard) pour la durée du script, puis l'arrête. C'est vrai même si un `prefect server start` tourne à côté : le script ne le trouve que par cette variable.

### Variante B : avec un serveur Prefect (optionnel, pour voir son interface)

```bash
# Terminal 3
prefect server start                     # interface sur le port 4200 ; Ctrl+C pour arrêter

# Terminal 2
PREFECT_API_URL=http://127.0.0.1:4200/api python evidently_metrics_calculation.py
```

Différence visible : plus de `Starting temporary server`, et une ligne `View at http://127.0.0.1:4200/runs/flow-run/...`. Dans l'interface (port 4200) : le flow `batch-monitoring-backfill` et ses tâches (1 `prep_db` + 27 jours).

`PREFECT_API_URL=...` placée devant la commande ne vaut que pour cette commande. Le serveur te suggère plutôt `prefect config set PREFECT_API_URL=...`, qui est **permanent** : si tu l'utilises, un lancement ultérieur sans serveur échouera avec `RuntimeError: Failed to reach API at http://127.0.0.1:4200/api/`. Pour revenir en arrière : `prefect config unset PREFECT_API_URL`.

Le **paquet** `prefect` est obligatoire (le script l'importe) ; le **serveur** ne l'est pas. Le README précise que la vidéo utilise Prefect de 07:33 à 11:21, que tu peux sauter ce passage, et que Prefect n'est pas officiellement couvert dans l'édition 2024.

### Où regarder

- **Adminer** : la table `dummy_metrics` a maintenant 27 lignes, du 2022-02-01 au 2022-02-27.
- **Grafana**, dans la vidéo : on crée à la main 3 panneaux (`prediction_drift`, `share_missing_values`, `num_drifted_columns`), sur une fenêtre de temps en **février 2022**, puisque les lignes sont datées du jour des données.

> **▲ Ton fork** : ouvre *Dashboards* → **New dashboard** : les 3 panneaux existent déjà. Deux réglages :
> - sa fenêtre de temps est enregistrée du 22 janvier au **18 février** 2022 : élargis-la jusqu'à fin février pour voir les 27 jours ;
> - il ne se rafraîchit pas tout seul : bouton ⟳, ou rafraîchissement automatique pendant que le script tourne.

---

## 8. Phase 6 : sauvegarder le dashboard Grafana (vidéo 5.8)

Le problème : un dashboard créé en cliquant est stocké **dans** le conteneur Grafana. Le fichier déclare bien un volume `grafana_data` (en tête de `docker-compose.yml`), mais aucun service ne l'utilise. `docker compose down` supprime le conteneur, donc le dashboard (et un mot de passe Grafana changé).

La solution : décrire le dashboard dans des fichiers du Codespace, que Grafana relit à chaque démarrage.

```
 Fichiers du Codespace                   Montés dans le conteneur grafana à          Ce que Grafana en fait
 ① config/grafana_datasources.yaml ───▶ /etc/grafana/provisioning/datasources/ ───▶ crée la source « PostgreSQL »
 ② config/grafana_dashboards.yaml  ───▶ /etc/grafana/provisioning/dashboards/  ───▶ « va lire /opt/grafana/dashboards »
 ③ dashboards/data_drift.json      ───▶ /opt/grafana/dashboards/               ───▶ affiche « New dashboard »
```

| N° | Ce qui se passe |
|---|---|
| ① | La connexion à la base (`db:5432`, base `test`), présente depuis la phase 0. Les panneaux du JSON désignent cette source par un identifiant : ne la renomme pas (détail dans tes notes `cours-05-overview-architecture.md`). |
| ② | Un « fournisseur » de dashboards : il dit à Grafana de scanner `/opt/grafana/dashboards` toutes les 10 s. |
| ③ | Le dashboard exporté : 3 panneaux, chacun une requête SQL sur la table `dummy_metrics`. |

### Les étapes (vidéo)

1. Dans Grafana, exporter le dashboard en JSON (sans cocher *Export for sharing externally*) et l'enregistrer sous `dashboards/data_drift.json`.
2. Créer `config/grafana_dashboards.yaml`.
3. Ajouter les deux montages au service `grafana` de `docker-compose.yml` :

   ```yaml
         - ./config/grafana_dashboards.yaml:/etc/grafana/provisioning/dashboards/dashboards.yaml:ro
         - ./dashboards:/opt/grafana/dashboards
   ```

4. Redémarrer, puis remplir à nouveau la base :

   ```bash
   docker compose down
   docker compose up -d
   python evidently_metrics_calculation.py      # Terminal 2
   ```

Pourquoi relancer le script : `db` n'a pas de volume déclaré dans le fichier. Après `down`, le nouveau conteneur repart d'une base vide (l'ancienne reste dans un volume anonyme orphelin, que `docker volume ls` liste). Le dashboard, lui, revient tout seul, puisqu'il est dans tes fichiers.

> **▲ Ton fork** : les étapes 1 à 3 sont déjà faites. Fais seulement l'étape 4 pour voir le provisioning en action.
> `config/grafana_dashboards.yaml` contient `allowUiUpdates: false` : Grafana refuse d'enregistrer depuis l'interface les modifications d'un dashboard provisionné. Pour le changer durablement, modifie `dashboards/data_drift.json` (Grafana le relit en 10 s).

---

## 9. Phase 7 : déboguer un jour suspect (vidéo 5.9), sans Docker

Grafana dit **quand** une métrique bouge. Le notebook debugging aide à comprendre **quoi**.

```
 data/reference.parquet ──────────────┐
 data/green_tripdata_2022-02.parquet ─┤ ① garder le 2 février, ② ajouter la prédiction
 models/lin_reg.bin ──────────────────┘
        │
        ├──▶ ③ TestSuite : un verdict réussi / échoué par test
        └──▶ ④ Report    : les distributions, colonne par colonne
```

| N° | Ce qui se passe |
|---|---|
| ① | Le notebook isole le **2 février 2022** (date écrite en dur dans la cellule). |
| ② | Il ajoute la colonne `prediction`, comme le script. |
| ③ | `TestSuite(tests=[DataDriftTestPreset()])` : un test sur la part de colonnes en dérive, puis un test de dérive par colonne (les 6 features et la prédiction). |
| ④ | `Report(metrics=[DataDriftPreset()])` : pour chaque colonne, les deux distributions superposées et le score. |

Il ne lit que des fichiers : Docker n'est pas nécessaire. En pratique, on garde Grafana ouvert à côté pour choisir le jour à étudier.

> **▲ Ton fork** : VS Code, noyau **py11-taximonitoring**, exécuter toutes les cellules.

### Arrêter les services

```bash
docker compose stop       # arrête sans supprimer : tout est retrouvé au prochain « docker compose up -d »
docker compose down       # arrête ET supprime les conteneurs : la base test est perdue (phase 6)
```

Si tu as lancé `docker compose up` sans `-d`, `Ctrl+C` dans le Terminal 1 équivaut à `stop`.

> **▲ Ton fork** : ta check-list de fin de séance (`06-best-practices/nettoyage-codespace.md`) recommande `stop`. Les 3 services ont `restart: always` : au réveil du Codespace, ils peuvent redémarrer tout seuls. Vérifie avec `docker compose ps`.

---

## 10. Variante : `post-evidently-0.7/` (l'API actuelle d'Evidently)

Evidently a changé d'API à la version 0.7 ; le README renvoie vers ce sous-dossier pour un exemple qui fonctionne avec Evidently ≥ 0.7. Les phases sont les mêmes et les classes changent de nom (`DataDefinition`, `Dataset`, `ValueDrift`, `DriftedColumnsCount`, `MissingValueCount`…). Ce qui change en pratique :

| | Racine `05-monitoring/` (vidéos) | `post-evidently-0.7/` |
|---|---|---|
| Version d'Evidently | `0.6.7`, fixée | Non fixée (0.7.23 au 01/10/2026) |
| pandas 3 | Casse le notebook baseline | Fonctionne |
| `docker-compose.yml`, `config/`, `dashboards/` | — | Identiques (à la ligne `version` près) |
| `data/`, `models/` | Présents, vides | Absents du dépôt : le notebook les crée (`! mkdir data`, `! mkdir models`) |
| Phase 3 : `evidently ui` | Lit le `workspace/` de la racine | À lancer depuis `post-evidently-0.7/`, avec l'environnement 0.7 : il ne sait pas lire un `workspace/` créé par la 0.6.7 |
| Phase 4 : script factice | Une ligne toutes les 10 s | Lignes par paires, toutes les 20 s (même boucle que le script Evidently) |
| Phase 5 : 3ᵉ métrique | Part des cellules vides, toutes colonnes | Valeurs manquantes de la seule colonne `prediction` : **toujours 0**, puisque la prédiction est calculée après remplacement des manquants par 0 |
| Phase 5 : traces rouges *cache key* | Une par jour | Aucune : le curseur n'est plus passé à la tâche Prefect |
| Phase 7 : notebook debugging | `TestSuite` puis `Report` | Un seul `Report(..., include_tests=True)` : les tests sont intégrés au rapport |

> **Écart repéré dans ce notebook debugging 0.7** (cellule 11) : `problematic_dataset = Dataset.from_pandas(ref_data, ...)` construit le jeu « courant » à partir de la **référence**. Le rapport compare donc la référence à elle-même et ne peut montrer aucune dérive. Pour étudier le 2 février, il faudrait `problematic_data` à la place de `ref_data` sur cette ligne. (Non modifié dans ton dépôt.)

### Dans le terminal

```bash
# Un environnement séparé : Evidently 0.6.7 et 0.7 ne cohabitent pas dans le même
conda create -n py11-evidently07 python=3.11 -y      # nom au choix ; cet environnement n'existe pas encore chez toi
conda activate py11-evidently07
cd /workspaces/mlops-zoomcamp/05-monitoring/post-evidently-0.7
pip install -r requirements.txt
# puis : notebook baseline (noyau py11-evidently07), evidently ui, scripts, notebook debugging, comme aux phases 1 à 7
```

Les services Docker sont les mêmes : garde ceux lancés depuis `05-monitoring/`. Le script vise `localhost:5432`, peu importe le dossier qui a démarré PostgreSQL. Relancer les services depuis `post-evidently-0.7/` échouerait : le port 5432 est déjà pris.

---

## 11. Ce que dit le README, et où c'est dans ce cours

| Partie du `README.md` (ton fork) | Page de l'original aujourd'hui | Section |
|---|---|---|
| 5.1 Intro to ML monitoring | `01-ml-monitoring.md` | § 1 |
| 5.2 Environment setup ; *Prerequisites* ; *Preparation* (environnement, `pip install`) ; *Starting services* | `02-monitoring-environment.md` | § 2 |
| 5.3 Prepare reference and model ; *Preparation* (notebook baseline) | `03-reference-model.md` | § 3 |
| 5.4 Evidently metrics calculation | `04-evidently-metrics.md` | § 4 |
| 5.5 Evidently Monitoring Dashboard | `05-evidently-dashboard.md` | § 5 |
| 5.6 Dummy monitoring | `06-dummy-monitoring.md` | § 6 |
| 5.7 Data quality monitoring ; note sur Prefect ; *Sending data* ; *Access dashboard* | `07-data-quality.md`, `10-monitoring-example.md` | § 7 |
| 5.8 Save Grafana Dashboard | `08-save-grafana-dashboard.md` | § 8 |
| 5.9 Debugging with test suites and reports ; *Ad-hoc debugging* ; *Stopping services* | `09-debugging-tests-reports.md`, `10-monitoring-example.md` | § 9 |
| Renvoi vers `post-evidently-0.7` | README, *Code and resources* | § 10 |
| *Homework* | Lien vers `cohorts/2025/05-monitoring/homework.md` | Hors de ce cours |

Les pages de l'original ajoutent des conseils sans commande à taper, que le code du dossier n'applique pas toujours : un volume pour la base (02), sauvegarder le rapport en HTML (04), Prefect remplaçable par cron (07), pas de mot de passe dans les fichiers de configuration (08, alors que `grafana_datasources.yaml` en contient un), des seuils versionnés (09).

---

## 12. Si ça casse

| Symptôme | Cause probable | Correction |
|---|---|---|
| `ValueError: Invalid frequency: H` (notebook baseline, cellules des rapports de qualité) | pandas 3 avec Evidently 0.6.7 | `pip install "pandas<3"`, puis redémarrer le noyau |
| `ImportError` sur un import Evidently | Code 0.6 avec Evidently 0.7, ou l'inverse | `pip show evidently` ; vérifier le dossier suivi (§ 10) |
| Script : `FileNotFoundError: data/reference.parquet` | Notebook baseline pas exécuté, ou script lancé depuis un autre dossier | Exécuter le notebook ; `cd` dans `05-monitoring/` |
| Script : `connection refused` sur le port 5432 | Services Docker arrêtés | `docker compose ps`, puis `docker compose up -d` |
| `port is already allocated` (5432, 3000 ou 8080) | Un autre conteneur occupe le port (autre chapitre, autre dossier) | `docker ps` pour le trouver, `docker compose down` dans son dossier |
| Adminer : `database "test" does not exist` ; Grafana : panneaux en erreur | Aucun script lancé depuis le démarrage du conteneur `db` | Lancer un script (phase 4 ou 5) |
| Grafana : `column "prediction_drift" does not exist` | La table est celle du script factice | Lancer le script de la phase 5 |
| Grafana : panneaux vides, ou arrêtés au 18 février | Fenêtre de temps hors février 2022, ou celle enregistrée dans `data_drift.json` | Régler la fenêtre sur tout février 2022 |
| Grafana : les courbes ne bougent pas pendant le script | Pas de rafraîchissement automatique | Bouton ⟳ ou rafraîchissement automatique |
| Après `down` : dashboard fait main disparu, données disparues | Ni Grafana ni `db` n'ont de volume | Dashboard : le sauvegarder en JSON (phase 6). Données : relancer le script de la phase 5. À l'avenir : `stop` plutôt que `down` |
| Adminer ou Grafana : `timeout expired` vers `db`, alors que le script écrit bien | Pare-feu du Codespace après une mise en veille (diagnostic dans tes notes `cours-05-pip conda-DiagnosticDocker.md`) | `sudo iptables-legacy -S FORWARD` ; si `-P FORWARD DROP` : `sudo iptables-legacy -P FORWARD ACCEPT` |
| Traces rouges `cache key`, ou plus de `data sent` | Prefect (§ 7, variante A) | Normal : suivre les lignes `Finished in state Completed()` |
| `RuntimeError: Failed to reach API at http://127.0.0.1:4200/api/` | `PREFECT_API_URL` configurée, serveur Prefect arrêté | Lancer `prefect server start`, ou `prefect config unset PREFECT_API_URL` |
| `evidently ui` : deux projets du même nom | La cellule `ws.create_project(...)` a été exécutée deux fois | Sans gravité ; supprimer `workspace/` pour repartir propre |

---

## 13. Reprise express (ton fork)

```bash
# Dans CHAQUE terminal
conda activate py11-taximonitoring
cd /workspaces/mlops-zoomcamp/05-monitoring

# Terminal 1 — services
docker compose up -d
docker compose ps

# Les fichiers sont-ils là ? (ils survivent à l'arrêt et à la mise en veille du Codespace, pas à sa suppression)
ls data models
# sinon : notebook baseline dans VS Code, noyau py11-taximonitoring

# Terminal 2 — métriques vers PostgreSQL (≈ 4 min 30)
python evidently_metrics_calculation.py

# Navigateur, onglet PORTS
#   3000 : Grafana (admin / admin) → Dashboards → New dashboard (fenêtre : février 2022)
#   8080 : Adminer (PostgreSQL, serveur db, postgres / example, base test)

# Au besoin, Terminal 3
evidently ui                 # port 8000

# Fin de séance
docker compose stop
```

---

## 14. Ce qui a été vérifié pour ce cours

- Comparaison fichier par fichier de `05-monitoring/` entre ton fork et l'original (01/10/2026), cellules de code des notebooks comprises.
- **Exécuté** avec les versions de `py11-taximonitoring` (Python 3.11, evidently 0.6.7, pandas 2.3.3, prefect 3.8.6, psycopg 3.3.6, scikit-learn 1.9.1) et un PostgreSQL 16 local à la place du conteneur `db` (même port, même utilisateur, même mot de passe) : les deux notebooks, `evidently ui`, le script factice, le script Evidently complet (27 lignes, environ 4 min 30, 28 tâches Prefect, traces *cache key*, aucun `data sent`, jours par paires), le même script avec `prefect server start` (ligne `View at`, exécution interrompue après 2 jours), et l'erreur `Failed to reach API` sans serveur. Variante 0.7 (evidently 0.7.23, pandas 3) : les deux notebooks et le script, pauses raccourcies (3ᵉ métrique toujours à 0, aucune trace *cache key*).
- **Données** : le serveur des données NYC était inaccessible depuis l'environnement de rédaction ; les exécutions ont utilisé des fichiers synthétiques au même schéma (mêmes 20 colonnes, mêmes types). Aucun résultat chiffré (erreur du modèle, scores de dérive) n'est donc cité.
- **Non exécuté** (Docker Hub inaccessible) : les conteneurs, donc Grafana, Adminer, le provisioning et le cycle `down` / `up`. Ces parties suivent les fichiers du dépôt et tes notes. Les deux `docker-compose.yml` ont été validés avec `docker compose config`. La recréation de l'environnement depuis `env-backups/` n'a pas été testée.
- Relecture par un agent indépendant, fichiers du dépôt à l'appui ; ses corrections sont intégrées.