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