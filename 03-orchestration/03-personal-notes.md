# homework and airflow

In the homewark, we are asked to use an orchestrator (like Airflow) to build the pipeline. Here is a tutorial from a former sutdents :
- airflow :  https://github.com/calatre/mlops-zoomcamp/tree/main/03-orchestration
- prefect : https://github.com/DataTalksClub/mlops-zoomcamp/blob/main/cohorts/2023/03-orchestration/prefect/README.md

### Comparaison : Apache Airflow vs Prefect

Apache Airflow et Prefect sont deux outils majeurs d'orchestration de données en Python, mais ils reposent sur des philosophies différentes. Airflow privilégie une approche déclarative et statique pour les grands volumes de traitements par lots (batch), tandis que Prefect propose une approche native, dynamique et moderne orientée Python.

### Comparaison des fonctionnalités

* **Approche du code** : 
  * **Airflow** utilise des graphes orientés acycliques (DAGs) déclaratifs souvent rigides et planifiés à l'avance.
  * **Prefect** traite les flux comme des fonctions Python standard avec une gestion native des dépendances dynamiques.
* **Architecture et infrastructure** :
  * **Airflow** nécessite une configuration plus lourde (scheduler, serveur web et base de données relationnelle).
  * **Prefect** offre une mise en place plus légère et flexible, adaptée au développement local rapide comme aux environnements cloud.
* **Interface et ergonomie** :
  * **Airflow** dispose d'une interface puissante mais historique.
  * **Prefect** intègre un tableau de bord moderne et épuré, idéal pour le suivi quotidien des tâches.

### Lequel choisir ?

* **Choisissez Apache Airflow** si vous gérez des volumes massifs de données historiques et des batchs complexes au sein d'une grande entreprise disposant déjà d'une équipe dédiée.
* **Choisissez Prefect** si vous développez des pipelines de données ou de machine learning agiles, nécessitant une prise en main rapide et des flux hautement dynamiques.



# Questions about the python script

je suis passer au 3eme module de MLOPs zoomcamp
On a transformé le jupuyter notebook en un script.py

Dans ce script on a écrit


```python
def run(year, month):
    df_train = read_dataframe(year=year, month=month)

    next_year = year if month < 12 else year + 1
    next_month = month + 1 if month < 12 else 1
    df_val = read_dataframe(year=next_year, month=next_month)

    X_train, dv = create_X(df_train)
    X_val, _ = create_X(df_val, dv)

    target = 'duration'
    y_train = df_train[target].values
    y_val = df_val[target].values

    run_id = train_model(X_train, y_train, X_val, y_val, dv)
    print(f"MLflow run_id: {run_id}")
    return run_id
```

la fonction create est défini comme ci-dessous : 

```python
def create_X(df, dv=None):
    categorical = ['PU_DO']
    numerical = ['trip_distance']
    dicts = df[categorical + numerical].to_dict(orient='records')

    if dv is None:
        dv = DictVectorizer(sparse=True)
        X = dv.fit_transform(dicts)
    else:
        X = dv.transform(dicts)

    return X, dv

```

Si je comprends bien, la ligne "X_train, dv = create_X(df_train)" signifie

* l'input est le dataframe df_train
* on transforme ce dataframe en dictionnary
* on transforme ce dictionnary en one hot encoding matrix via DictVectorizer
* on enregsitre la matrice one hot encoding X_train et la méthode (fonction ? je ne sais connais oas le bon terme) dv


Question : pour la ligne "X_val, _ = create_X(df_val, dv)"

* que signifie le "_"
* pourquoi on enregistre pas dv ? Par ce qu'on réutilise le dv défini pour créer X_train ?


Question : que fait l'argument sparse=True dans DictVectorizer(sparse=True) ?

____________________________________________________________________________________________________________

Ta lecture de `create_X(df_train)` est bonne, avec deux précisions :

- **`dv` est un objet**, pas une fonction — une instance de `DictVectorizer` (en vocabulaire scikit-learn : un *transformer*). Pendant le `fit`, il apprend un **vocabulaire** : la correspondance `nom_de_feature → index de colonne`. C'est cet état appris qu'on garde.
- **Ce n'est pas du one-hot partout.** `DictVectorizer` n'encode en one-hot que les valeurs *string* (`PU_DO`). `trip_distance` est numérique, donc il reste une seule colonne avec sa valeur. Tu obtiens une matrice = [des milliers de colonnes 0/1 pour PU_DO] + [1 colonne trip_distance].

## `X_val, _ = create_X(df_val, dv)`

**Le `_`** n'a aucune syntaxe spéciale : c'est un nom de variable ordinaire, utilisé par convention pour dire « je dois déballer ce tuple, mais cette valeur-là ne m'intéresse pas ». `create_X` retourne toujours `(X, dv)`, donc tu es obligé de recevoir deux valeurs. Tu pourrais écrire `X_val, poubelle = ...`, ça marcherait pareil — `_` est juste le signal conventionnel « ignoré ».

**Pourquoi on ne le réassigne pas** : oui, exactement ton intuition. Dans la branche `else`, `dv` n'est ni modifié ni recréé — l'objet retourné est littéralement le même que celui passé en argument. Le réassigner serait un no-op.

Mais le point important est en amont : il **faut** passer `dv` plutôt que d'en créer un nouveau. Si tu faisais `create_X(df_val)` sans `dv`, tu referais un `fit_transform` sur la validation, et le vocabulaire serait appris sur *ses* données. Conséquences :

- la colonne 42 ne désignerait plus la même paire PU_DO dans `X_train` et dans `X_val` → le modèle lirait n'importe quoi ;
- le nombre de colonnes différerait probablement → crash au `predict`.

C'est la règle générale de scikit-learn : `fit_transform` sur le train, `transform` seul partout ailleurs (val, test, production). Le `dv` est d'ailleurs sauvegardé dans MLflow avec le modèle pour cette raison — au moment de servir le modèle, il faut le même vocabulaire.

## `sparse=True`

`PU_DO` a des milliers de modalités (toutes les paires pickup/dropoff observées) → des milliers de colonnes. Or sur chaque ligne, **une seule** de ces colonnes vaut 1, toutes les autres valent 0. La matrice est donc à ~99,99 % des zéros.

- `sparse=False` → un `numpy.ndarray` dense qui stocke *tous* les zéros. Avec ~3 M de trajets × ~10 000 colonnes × 8 octets, tu es à plusieurs centaines de Go. Impossible.
- `sparse=True` → une `scipy.sparse.csr_matrix`, qui ne stocke que les valeurs non nulles et leurs positions. Ici ≈ 2 valeurs par ligne au lieu de 10 000. Quelques dizaines de Mo.

Les modèles concernés (régression linéaire, Lasso, XGBoost) acceptent nativement ce format, donc aucune conversion n'est nécessaire. C'est d'ailleurs la valeur par défaut de `DictVectorizer` — l'écrire explicitement est une question de lisibilité.

Petit réflexe utile en debug : `X_train.shape` marche comme sur un array dense, mais pour regarder le contenu il faut `X_train[:5].toarray()` (attention à ne jamais faire `.toarray()` sur la matrice entière).

_________________________________________________________________________________

A la fin du script, on écrit


```python
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Train a model to predict taxi trip duration.')
    parser.add_argument('--year', type=int, required=True, help='Year of the data to train on')
    parser.add_argument('--month', type=int, required=True, help='Month of the data to train on')
    args = parser.parse_args()

    run_id = run(year=args.year, month=args.month)

    with open("run_id.txt", "w") as f:
        f.write(run_id)
```

Explique-moi ce que fait ce bloc de code. Je ne connais pas du tout la librairie argparse


____________________________________________________________________________________

Ce bloc transforme le script en **outil en ligne de commande** : au lieu d'éditer le code pour changer l'année, tu lances `python duration-prediction.py --year 2023 --month 3`.

## `if __name__ == "__main__":`

Python définit automatiquement une variable `__name__` dans chaque fichier. Sa valeur dépend de **comment le fichier est chargé** :

- tu lances `python mon_script.py` → dans ce fichier, `__name__` vaut `"__main__"` ;
- un autre fichier fait `import mon_script` → dans `mon_script.py`, `__name__` vaut `"mon_script"`.

Donc ce `if` signifie : « exécute ce bloc **seulement si** ce fichier est le point d'entrée, pas s'il est importé ».

L'intérêt est réel ici : quand tu importeras `from duration_prediction import run` depuis un autre script (ou un notebook, ou plus tard un DAG Prefect/Airflow), tu veux récupérer la fonction **sans** déclencher un entraînement et sans crasher sur des arguments CLI absents. Sans ce garde-fou, le simple `import` lancerait tout le pipeline.

## `argparse`

C'est le module standard de Python pour lire les arguments de la ligne de commande. Ligne par ligne :

```python
parser = argparse.ArgumentParser(description='Train a model...')
```
Crée l'objet qui va décrire et lire les arguments. Le `description` sert uniquement à l'affichage de l'aide.

```python
parser.add_argument('--year', type=int, required=True, help='Year of the data...')
```
Déclare un argument attendu :
- `'--year'` → un argument **nommé** (avec les deux tirets), donc appelé par `--year 2023`. Sans les tirets (`'year'`), ce serait un argument **positionnel**, appelé par la position : `python script.py 2023 3`. Les arguments nommés sont plus verbeux mais bien plus lisibles — tu ne risques pas d'inverser année et mois.
- `type=int` → ce qui arrive de la ligne de commande est **toujours une chaîne de caractères**. `argparse` convertit `"2023"` en entier `2023`. Sans ça, ton `month < 12` comparerait une string à un int et planterait.
- `required=True` → si tu oublies l'argument, le script s'arrête immédiatement avec un message d'erreur clair, au lieu d'échouer 3 minutes plus tard au milieu du téléchargement. On peut aussi mettre `default=2023` à la place pour une valeur par défaut.
- `help='...'` → le texte affiché par `--help`.

```python
args = parser.parse_args()
```
Lit réellement `sys.argv` (la liste des mots tapés dans le terminal), valide, convertit, et renvoie un petit objet `Namespace` dont les attributs portent les noms des arguments : `args.year`, `args.month`.

Bonus gratuit : `argparse` te génère l'aide tout seul.

```
$ python duration-prediction.py --help
usage: duration-prediction.py [-h] --year YEAR --month MONTH

Train a model to predict taxi trip duration.

options:
  -h, --help     show this help message and exit
  --year YEAR    Year of the data to train on
  --month MONTH  Month of the data to train on
```

Et si tu oublies un argument :
```
$ python duration-prediction.py --year 2023
error: the following arguments are required: --month
```

## Le `run_id.txt`

```python
run_id = run(year=args.year, month=args.month)
with open("run_id.txt", "w") as f:
    f.write(run_id)
```

`run()` retourne l'identifiant MLflow du run qui vient d'être enregistré. On l'affiche (le `print` dans `run`) **et** on l'écrit dans un fichier.

Pourquoi un fichier ? Parce que c'est la façon la plus simple de passer une information d'un script à l'étape suivante d'un pipeline. L'étape « entraînement » écrit le `run_id` ; l'étape « déploiement » le lit pour savoir quel modèle charger depuis MLflow. En bash tu peux directement faire :

```bash
python duration-prediction.py --year 2023 --month 3
RUN_ID=$(cat run_id.txt)
```

C'est le fil conducteur du module 3 : le notebook avait un état implicite en mémoire ; là, chaque exécution produit un artefact identifiable et traçable, et le lien entre les étapes devient explicite.

Le `with open(...) as f` est la forme idiomatique pour ouvrir un fichier : il garantit la fermeture du fichier même si une erreur survient. Le `"w"` signifie *write* — le fichier est écrasé à chaque exécution (`"a"` pour *append* ajouterait à la suite).