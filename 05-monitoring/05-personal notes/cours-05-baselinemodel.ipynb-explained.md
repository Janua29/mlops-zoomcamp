# Module 05 — Monitoring : le notebook `baseline_model_nyc_taxi_data.ipynb` expliqué

> Source : [DataTalksClub/mlops-zoomcamp › 05-monitoring](https://github.com/DataTalksClub/mlops-zoomcamp/tree/main/05-monitoring)
> Prérequis : Python, bases de numpy/pandas. Tout le reste est expliqué ici.

> **Versions — à lire avant d'exécuter**
> - Le module fixe `evidently==0.6.7`. **Installe cette version.** À partir de la 0.7, Evidently a une nouvelle API : les imports de ce notebook n'y existent plus que sous `evidently.legacy` (ex. `evidently.legacy.report`).
> - `pandas` n'est pas épinglé : un environnement récent installera pandas 3, et la cellule 34 plante alors (`ValueError: Invalid frequency: H`). Installe `pandas<3`.

---

## 0. Le problème que ce notebook résout

Un modèle en production se dégrade **sans faire de bruit** : pas de plantage, juste des prédictions de moins en moins bonnes. La cause la plus fréquente : les données qui arrivent aujourd'hui ne ressemblent plus à celles qui ont servi à l'entraînement. C'est le **drift** (la « dérive »).

Deux mots de vocabulaire utilisés partout :

- **Feature** : une variable d'entrée du modèle (distance, nombre de passagers…).
- **Distribution** d'une colonne : la répartition de ses valeurs — ce que montre son histogramme. « La distribution a changé » = l'histogramme n'a plus la même forme.

Le monitoring consiste à comparer les distributions de deux jeux de données :

| Terme Evidently | Rôle | Dans ce notebook | Dans la suite du module |
|---|---|---|---|
| `reference_data` | Ce qui est « normal » : le point de comparaison | Train (janvier, lignes 0 → 29 999) | Validation (`reference.parquet`) |
| `current_data` | Ce qu'on veut surveiller | Validation (janvier, lignes 30 000 → fin) | Février, jour par jour |

Le notebook se déroule en 3 temps :

```
1. Préparer        2. Entraîner le modèle         3. Surveiller avec Evidently
─────────────      ──────────────────────         ─────────────────────────────────
télécharger   →    régression linéaire      →     a) Report  : un diagnostic ponctuel
nettoyer           mesurer l'erreur (MAE)         b) Workspace + Dashboard : un suivi dans le temps
                   sauvegarder modèle + référence
```

C'est une **baseline** : il pose les pièces (modèle, référence, premier rapport) que les scripts suivants réutilisent (`evidently_metrics_calculation.py` recharge `models/lin_reg.bin` et `data/reference.parquet`).

---

## 1. Imports (cellule 1)

```python
import requests
import datetime
import pandas as pd

from evidently import ColumnMapping
from evidently.report import Report
from evidently.metrics import ColumnDriftMetric, DatasetDriftMetric, DatasetMissingValuesMetric

from joblib import load, dump
from tqdm import tqdm

from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error
```

| Package | À quoi il sert ici |
|---|---|
| `requests` | Faire des requêtes HTTP (télécharger un fichier depuis une URL). |
| `datetime` | Module standard Python pour les dates et heures. |
| `evidently` | Bibliothèque de **monitoring ML** : calcule drift et qualité des données, affiche rapports et dashboards. Le cœur du module. |
| `joblib` | Sauvegarder (`dump`) / recharger (`load`) un objet Python sur disque — ici le modèle. |
| `tqdm` | Afficher une barre de progression autour d'une boucle. |
| `sklearn` | scikit-learn : le modèle (`LinearRegression`) et les métriques d'erreur. |

Les classes Evidently sont expliquées en section 6. `load` et `mean_absolute_percentage_error` sont importés mais jamais utilisés.

---

## 2. Téléchargement des données (cellule 2)

```python
files = [('green_tripdata_2022-02.parquet', './data'), ('green_tripdata_2022-01.parquet', './data')]

print("Download files:")
for file, path in files:
    url=f"https://d37ci6vzurychx.cloudfront.net/trip-data/{file}"
    resp=requests.get(url, stream=True)
    save_path=f"{path}/{file}"
    with open(save_path, "wb") as handle:
        for data in tqdm(resp.iter_content(),
                        desc=f"{file}",
                        postfix=f"save to {save_path}",
                        total=int(resp.headers["Content-Length"])):
            handle.write(data)
```

On télécharge deux mois de courses de taxis verts new-yorkais : **janvier** (modèle + référence) et **février** (données « de production » surveillées plus tard).

- `requests.get(url, stream=True)` — envoie la requête. `stream=True` : ne charge pas tout le fichier en mémoire, on le lira morceau par morceau.
- `resp.iter_content()` — itère sur ces morceaux. Sans argument, un morceau = **1 octet**.
- `tqdm(..., total=int(resp.headers["Content-Length"]))` — la barre de progression. `Content-Length` = taille du fichier en octets, annoncée par le serveur. Comme un tour de boucle = 1 octet, `total` = nombre de tours attendus. `desc` / `postfix` = textes affichés à gauche / à droite.
- `open(save_path, "wb")` — écriture **binaire** : un parquet n'est pas du texte.

> **Piège** : les dossiers `./data` et `./models` (cellule 18) doivent exister avant, sinon `FileNotFoundError`.
> **Perf** : 1 octet par tour = ~2,7 millions de tours au total. En pratique : `iter_content(chunk_size=8192)` et faire avancer la barre de `len(data)`.

---

## 3. Préparation des données (cellules 3 → 10)

```python
jan_data = pd.read_parquet('data/green_tripdata_2022-01.parquet')
jan_data.describe()
jan_data.shape          # (62495, 20)
```

`read_parquet` lit un fichier **Parquet** : format en colonnes, compressé et typé (les dates restent des dates, contrairement au CSV). Nécessite `pyarrow` (dans `requirements.txt`).

### Créer la cible (cellule 6)

```python
jan_data["duration_min"] = jan_data.lpep_dropoff_datetime - jan_data.lpep_pickup_datetime
jan_data.duration_min = jan_data.duration_min.apply(lambda td : float(td.total_seconds())/60)
```

- Date − date = une **`Timedelta`** (une durée, ex. `0 days 00:17:30`).
- `.apply(lambda td: ...)` applique à chaque valeur une **fonction anonyme** d'une ligne : « pour chaque durée `td`, renvoie `td` en minutes ».

→ C'est la **cible** : ce que le modèle devra prédire, la durée d'une course en minutes. (Équivalent vectorisé, plus rapide : `.dt.total_seconds() / 60`.)

### Filtrer les valeurs aberrantes (cellule 7)

On garde les courses de 0 à 60 min et de 1 à 8 passagers → 55 211 lignes.
Effet de bord discret : `passenger_count > 0` est faux quand la valeur est manquante (NaN), donc ce filtre supprime aussi les ~6 300 lignes sans nombre de passagers (`describe()` en compte 56 200 sur 62 495).

`jan_data.duration_min.hist()` (cellule 8) trace l'histogramme de la cible via **matplotlib**.

### Déclarer le rôle des colonnes (cellule 9)

```python
target = "duration_min"
num_features = ["passenger_count", "trip_distance", "fare_amount", "total_amount"]
cat_features = ["PULocationID", "DOLocationID"]
```

- **Numérique** : la valeur a un sens quantitatif (3 km > 2 km).
- **Catégorielle** : une étiquette. `PULocationID` (zone de prise en charge, *Pick-Up*) et `DOLocationID` (zone de dépose, *Drop-Off*) sont des numéros de zone : la zone 140 n'est pas « plus grande » que la zone 70.

Ces listes servent au modèle (section 4) et à Evidently (section 6).

---

## 4. Le modèle (cellules 11 → 16)

### Découper train / validation (cellule 11)

```python
train_data = jan_data[:30000]
val_data = jan_data[30000:]
```

30 000 lignes pour **entraîner**, le reste (25 211) pour **valider** : mesurer l'erreur sur des données jamais vues par le modèle.

### Entraîner (cellules 12-13)

```python
model = LinearRegression()
model.fit(train_data[num_features + cat_features], train_data[target])
```

Le schéma universel de scikit-learn :

1. **Instancier** : `LinearRegression()` crée un modèle « vide ».
2. **`fit(X, y)`** : l'entraîner. `X` = les features (tableau 2D), `y` = la cible (1D).

La régression linéaire cherche `a₁…a₆` et `b` tels que
`durée ≈ a₁·passenger_count + a₂·trip_distance + … + a₆·DOLocationID + b`,
en minimisant la somme des erreurs au carré. (`num_features + cat_features` = concaténation des deux listes.)

### Prédire (cellules 14-15)

```python
train_preds = model.predict(train_data[num_features + cat_features])
train_data['prediction'] = train_preds

val_preds = model.predict(val_data[num_features + cat_features])
val_data['prediction'] = val_preds
```

`predict(X)` renvoie un tableau numpy, une prédiction par ligne. On le range dans une colonne `prediction` des deux jeux : Evidently en aura besoin pour surveiller les prédictions.

> Avec pandas < 3, ces lignes affichent un `SettingWithCopyWarning` : `train_data` est un morceau de `jan_data`, et pandas ne sait pas si tu veux aussi modifier l'original. Sans conséquence ici (pandas 3 ne l'affiche plus). Bonne pratique : `train_data = jan_data[:30000].copy()`.

### Évaluer (cellule 16)

```python
print(mean_absolute_error(train_data.duration_min, train_data.prediction))  # 3.80
print(mean_absolute_error(val_data.duration_min, val_data.prediction))      # 4.14
```

**MAE** (*Mean Absolute Error*) = moyenne de |réel − prédit|, dans l'unité de la cible → le modèle se trompe en moyenne de **~4 minutes**.
Erreur validation un peu > erreur train : normal. L'écart est faible → pas de **sur-apprentissage** marqué (sur-apprentissage = le modèle a appris le train « par cœur » et généralise mal).

---

## 5. Sauvegarder modèle et référence (cellules 18-19)

```python
with open('models/lin_reg.bin', 'wb') as f_out:
    dump(model, f_out)

val_data.to_parquet('data/reference.parquet')
```

- `joblib.dump(objet, fichier)` **sérialise** le modèle : transforme l'objet Python en octets sur disque. `joblib.load(fichier)` fera l'inverse dans un autre script. (Même principe que `pickle`, optimisé pour les gros tableaux numpy.)
- `val_data` (avec sa colonne `prediction`) devient la **référence** officielle de la suite du module (voir tableau du §0 et §8.3).

---

## 6. Evidently Report : un diagnostic ponctuel (cellules 21 → 29)

### 6.1 `ColumnMapping` : dire à Evidently qui est qui (cellule 21)

```python
column_mapping = ColumnMapping(
    target=None,
    prediction='prediction',
    numerical_features=num_features,
    categorical_features=cat_features
)
```

Evidently ne devine pas le sens de tes colonnes. `ColumnMapping` le lui dit :

| Paramètre | Signification |
|---|---|
| `target=None` | On ne fournit pas la vraie valeur. C'est **réaliste** : en production, la vraie durée n'est connue qu'après la course — souvent trop tard. On surveille donc les entrées et les prédictions, pas l'erreur. |
| `prediction='prediction'` | Nom de la colonne des prédictions. |
| `numerical_features` / `categorical_features` | Type de chaque feature → Evidently choisit le test statistique adapté (6.3). |

Les colonnes non listées ne sont **pas** analysées pour le drift, mais restent visibles pour les métriques qui regardent tout le tableau (valeurs manquantes, qualité). Les colonnes de dates sont même détectées automatiquement.

### 6.2 `Report` : choisir les métriques (cellule 22)

```python
report = Report(metrics=[
    ColumnDriftMetric(column_name='prediction'),
    DatasetDriftMetric(),
    DatasetMissingValuesMetric()
])
```

Un `Report` est un conteneur auquel on donne une **liste de métriques**. Rien n'est encore calculé : on décrit le rapport.

| Métrique | Question à laquelle elle répond |
|---|---|
| `ColumnDriftMetric(column_name='prediction')` | La distribution des **prédictions** a-t-elle changé ? (*prediction drift*) |
| `DatasetDriftMetric()` | Combien de colonnes (features + prédiction) ont dérivé ? Le jeu entier a-t-il dérivé ? |
| `DatasetMissingValuesMetric()` | Combien de valeurs manquantes, et où ? |

> Pourquoi surveiller la prédiction ? Faute de vraie valeur, c'est le meilleur signal disponible : si le modèle se met soudain à prédire des durées très différentes, c'est que les entrées ont changé.

### 6.3 `run` : calculer (cellule 23)

```python
report.run(reference_data=train_data, current_data=val_data, column_mapping=column_mapping)
```

Pour chaque colonne, Evidently compare la distribution **référence** à la distribution **courante** et produit un **score de drift**, comparé à un seuil. Le calcul dépend du type de colonne. Avec plus de 1 000 lignes de référence (notre cas) :

| Type de colonne | Mesure utilisée | Drift si |
|---|---|---|
| Numérique | **Distance de Wasserstein normalisée** | score ≥ 0,1 |
| Catégorielle (ou numérique à ≤ 5 valeurs distinctes) | **Distance de Jensen-Shannon** | score ≥ 0,1 |

- **Wasserstein** (*earth mover's distance*) : vois les deux histogrammes comme deux tas de terre. La distance = l'effort minimal pour transformer l'un en l'autre. Evidently la divise par l'écart-type de la référence → un score sans unité. **0,03 ≈ les distributions diffèrent de 3 % d'un écart-type** : négligeable.
- **Jensen-Shannon** : compare les proportions de chaque catégorie dans les deux jeux. 0 = proportions identiques ; plus c'est grand, plus elles diffèrent.

> **Et avec ≤ 1 000 lignes ?** Evidently passe à des **tests statistiques** (Kolmogorov-Smirnov pour le numérique, khi-deux pour le catégoriel). Un test répond à : « cet écart peut-il s'expliquer par le hasard de l'échantillonnage ? ». Il renvoie une **p-value** : la probabilité d'observer un écart au moins aussi grand si les deux jeux venaient de la même distribution. p-value ≤ 0,05 → drift.
> Pourquoi ne pas utiliser les tests partout ? Avec beaucoup de données, ils deviennent **hypersensibles** : le moindre écart, même sans importance pratique, devient « statistiquement significatif ». Au-delà de 1 000 lignes, une distance + un seuil donne des alertes plus utiles.

### 6.4 Afficher et exploiter (cellules 24 → 29)

```python
report.show(mode='inline')   # affiche le rapport HTML interactif dans Jupyter
result = report.as_dict()     # le même contenu en dictionnaire Python
```

`as_dict()` rend l'automatisation possible : on extrait des chiffres pour les stocker (dans une base de données, plus loin dans le module) ou déclencher une alerte.

Structure : `result['metrics']` est une **liste**, dans le **même ordre** que les métriques déclarées dans `Report(...)`. Chaque élément a une clé `'result'` qui contient les chiffres. D'où :

```python
result['metrics'][0]['result']['drift_score']                         # 0.0305
result['metrics'][1]['result']['number_of_drifted_columns']           # 0
result['metrics'][2]['result']['current']['share_of_missing_values']  # 0.0455
```

Lecture :

- **`drift_score = 0.0305`** (prédiction) : sous le seuil de 0,1 → `drift_detected: False`.
- **`number_of_drifted_columns = 0`** sur 7 colonnes analysées (4 numériques + 2 catégorielles + prédiction). Le jeu entier serait déclaré en drift si **≥ 50 %** des colonnes dérivaient (`drift_share = 0.5` par défaut).
- **`share_of_missing_values = 0.0455`** = valeurs manquantes / (lignes × colonnes). Evidently compte comme manquant : NaN/None, chaîne vide `""`, `inf` et `-inf`. **Toutes** les colonnes du tableau comptent : 22 (les 20 d'origine + `duration_min` + `prediction`). La seule concernée est `ehail_fee`, **entièrement vide** : 25 211 / (25 211 × 22) = 1/22 ≈ 4,5 %.
- Le `['current']` : cette métrique calcule ses chiffres séparément pour `current` et `reference`.

**Zéro drift : est-ce attendu ?** Oui. Train et validation viennent du même mois, tirés du même fichier : c'est un **contrôle de cohérence**. Le vrai test viendra avec février, dans la suite du module.

---

## 7. Evidently Dashboard : suivre dans le temps (cellules 31 → 38)

Un `Report` est une photo. Un **dashboard** est un film : il empile les rapports successifs (un par jour, par exemple) et trace l'évolution des métriques.

### 7.1 Imports (cellule 31)

```python
from evidently.metric_preset import DataDriftPreset, DataQualityPreset
from evidently.ui.workspace import Workspace
from evidently.ui.dashboards import DashboardPanelCounter, DashboardPanelPlot, CounterAgg, PanelValue, PlotType, ReportFilter
from evidently.renderers.html_widgets import WidgetSize
```

- **Preset** = un paquet de métriques pré-assemblé. `DataQualityPreset` contient : un résumé du jeu (`DatasetSummaryMetric`), un résumé par colonne (`ColumnSummaryMetric`), les valeurs manquantes (`DatasetMissingValuesMetric`). `DataDriftPreset` est importé mais pas utilisé.
- Les autres classes construisent le dashboard (7.4).

### 7.2 Workspace et Project (cellules 32-33)

```python
ws = Workspace("workspace")
project = ws.create_project("NYC Taxi Data Quality Project")
project.description = "My project descriotion"
project.save()
```

| Concept | Définition |
|---|---|
| `Workspace` | Un **dossier local** (ici `./workspace`, créé s'il n'existe pas) où Evidently stocke projets et rapports. |
| `Project` | Un regroupement de rapports + la configuration d'un dashboard. Typiquement : un projet par modèle surveillé. Identifiant unique : `project.id` (un UUID). |
| `save()` | Écrit les modifications du projet sur disque. Sans ça, elles restent en mémoire. |

### 7.3 Un rapport daté par jour (cellules 34-35 puis 37-38)

```python
regular_report = Report(
    metrics=[DataQualityPreset()],
    timestamp=datetime.datetime(2022,1,28)
)

regular_report.run(reference_data=None,
                  current_data=val_data.loc[val_data.lpep_pickup_datetime.between('2022-01-28', '2022-01-29', inclusive="left")],
                  column_mapping=column_mapping)

ws.add_report(project.id, regular_report)
```

- **`timestamp=`** : la date **attribuée** au rapport. Elle sert d'**axe X** dans le dashboard. On simule ici un historique en datant le rapport du 28 janvier. Sans elle, la date serait celle de l'appel à `run()`.
  ⚠️ En 0.6.7, passer `timestamp` au constructeur est **déprécié** (un avertissement s'affiche). Forme recommandée : `regular_report.run(..., timestamp=datetime.datetime(2022,1,28))`.
- **`reference_data=None`** : autorisé car un rapport de *qualité* décrit un seul jeu (comptages, valeurs manquantes…). Un rapport de *drift* exige une référence — et l'erreur ne surgit qu'à `show()` / `as_dict()`, pas à `run()`.
- **`.between(a, b, inclusive="left")`** : garde les lignes où `a ≤ date < b`, soit exactement la journée du 28. `"left"` = borne gauche incluse, droite exclue : aucune course n'est comptée deux fois d'un jour à l'autre.
- **`ws.add_report(project.id, rapport)`** : enregistre le rapport dans le projet (fichier JSON dans `./workspace`).

La cellule 37 refait la même chose pour le 29 janvier → le dashboard aura 2 points. En production, une boucle ou un job planifié (Prefect, dans la suite du module) génère un rapport par période.

### 7.4 Configurer les panneaux (cellule 36)

Un dashboard est une liste de **panneaux** (*panels*). Deux types ici.

**Panneau compteur** — affiche un chiffre ou un texte :

```python
project.dashboard.add_panel(
    DashboardPanelCounter(
        filter=ReportFilter(metadata_values={}, tag_values=[]),
        agg=CounterAgg.NONE,
        title="NYC taxi data dashboard"
    )
)
```

- `ReportFilter(metadata_values={}, tag_values=[])` : quels rapports du projet le panneau utilise. Filtres vides = **tous**.
- `agg` : comment agréger une valeur sur les rapports — `SUM` (somme), `LAST` (dernière valeur), `NONE` (aucune). Avec `NONE` et sans valeur, le panneau n'affiche que son titre : c'est **un simple bandeau-titre** en haut du dashboard.

**Panneau graphique** — trace une valeur au fil des rapports :

```python
project.dashboard.add_panel(
    DashboardPanelPlot(
        filter=ReportFilter(metadata_values={}, tag_values=[]),
        title="Inference Count",
        values=[
            PanelValue(
                metric_id="DatasetSummaryMetric",
                field_path="current.number_of_rows",
                legend="count"
            ),
        ],
        plot_type=PlotType.BAR,
        size=WidgetSize.HALF,
    ),
)
```

- **`PanelValue`** = l'adresse de la valeur à aller chercher dans chaque rapport :
  - `metric_id="DatasetSummaryMetric"` : dans quelle métrique (elle vient du `DataQualityPreset`).
  - `field_path="current.number_of_rows"` : le chemin **à l'intérieur du `'result'` de cette métrique**, écrit avec des points. Dans `as_dict()`, ce serait `result['metrics'][0]['result']['current']['number_of_rows']`.
  - `legend` : le libellé de la légende.
- `plot_type` : `BAR` (barres), `LINE` (courbe), `SCATTER` (nuage de points), `HISTOGRAM`.
- `size` : `WidgetSize.HALF` (demi-largeur, deux panneaux côte à côte) ou `FULL`.
- `values` est une **liste** : on peut superposer plusieurs séries dans un panneau.

« Inference Count » = nombre de lignes par jour = nombre de prédictions faites ce jour-là. Le 3ᵉ panneau suit de la même façon `current.number_of_missing_values`, en courbe (`PlotType.LINE`).

`project.save()` enregistre la configuration du dashboard.

### 7.5 Voir le dashboard

Le notebook ne l'affiche pas. Dans un **terminal**, depuis le dossier qui contient `workspace/` :

```bash
evidently ui
```

puis ouvrir http://localhost:8000 (défauts : `--workspace workspace`, `--port 8000`).

---

## 8. Remarques d'expert (hors périmètre du notebook)

Le notebook vise à apprendre le monitoring, pas à faire un bon modèle. À garder en tête :

1. **IDs de zone traités comme des nombres.** `PULocationID` est catégoriel pour Evidently, mais `LinearRegression` le reçoit comme un nombre : elle apprend « +1 au numéro de zone = +a₅ minutes », ce qui n'a pas de sens. Un vrai modèle utiliserait un **one-hot encoding** (une colonne 0/1 par zone), par ex. avec `DictVectorizer` vu au module 1.
2. **Fuite d'information (*data leakage*).** `fare_amount` et `total_amount` ne sont connus qu'**à la fin** de la course : inutilisables pour prédire la durée avant le départ. La MAE est donc flatteuse.
3. **Référence = train dans le rapport du §6.** Sur le train, le modèle a été ajusté : ses prédictions y sont un peu « trop bonnes » et leur distribution n'est pas représentative de ce qu'il produit sur des données neuves. D'où le choix de `val_data` comme référence dans la suite du module.
4. **Découpage par position.** `jan_data[:30000]` suppose que l'ordre des lignes a un sens. Pour du monitoring, un découpage **par date** (ex. 1ᵉʳ-20 / 21-31 janvier) est plus fidèle à la réalité.
5. **Seuils par défaut.** 0,1 pour les distances et 50 % de colonnes pour le drift global sont des conventions : ils se règlent (`stattest_threshold`, `drift_share`) selon le coût d'une fausse alerte.

---

## 9. Récapitulatif

| Notion | En une phrase |
|---|---|
| Drift | La distribution des données actuelles s'écarte de celle de la référence. |
| Reference / current | Le « normal » vs ce qu'on surveille. |
| `ColumnMapping` | Dit à Evidently le rôle et le type de chaque colonne. |
| `Report` + métriques | Un calcul ponctuel : `run()` calcule, `show()` affiche, `as_dict()` exporte. |
| Preset | Paquet de métriques prêt à l'emploi. |
| Wasserstein / Jensen-Shannon | Distances entre distributions (numériques / catégorielles) ; drift si ≥ 0,1 (référence > 1 000 lignes). |
| `Workspace` / `Project` | Stockage local des rapports / regroupement par modèle. |
| `timestamp` | Date du rapport = axe X du dashboard. |
| `PanelValue(metric_id, field_path)` | Adresse d'une valeur à tracer dans chaque rapport. |
| `evidently ui` | Lance le dashboard web sur le port 8000. |