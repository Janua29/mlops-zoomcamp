### Résumé de ce qu'on voit dans 02 - Experiment tracking

**Question**

Dans le module 02-experiment trackin, on a un doossier /models contenant lin_reg.bin et preprocessor.b
e fichier lin_reg.bin a à priori été créé via

```python

with open('models/lin_reg.bin', 'wb') as f_out:
    pickle.dump((dv, lr), f_out)


```

puis


```python
with mlflow.start_run():

    

    mlflow.set_tag("developer", "cristian")

    mlflow.log_param("train-data-path", "./data/green_tripdata_2021-01.csv")
    mlflow.log_param("valid-data-path", "./data/green_tripdata_2021-02.csv")

    #C'est pas une régression linéaire mais un Lasso, pas une LinearRegression. C'est une régression linéaire avec régularisation L1
    #alpha est ici le paramètr ed erégularsation (le lambda de Andrew Ng., pas le learning rate)
    alpha = 0.1
    mlflow.log_param("alpha", alpha)
    lr = Lasso(alpha)
    lr.fit(X_train, y_train)

    y_pred = lr.predict(X_val)
    #rmse = mean_squared_error(y_val, y_pred, squared=False)
    rmse = np.sqrt(mean_squared_error(y_val, y_pred))
    mlflow.log_metric("rmse", rmse)

    mlflow.log_artifact(local_path="models/lin_reg.bin", artifact_path="models_pickle")
```


et preprocessor.b via : 

```python

```python
   with open("models/preprocessor.b", "wb") as f_out:
        pickle.dump(dv, f_out)
mlflow.log_artifact("models/preprocessor.b", artifact_path="preprocessor")

```

Dans ce cas, pour enregistrer le model, on n'a pas utilisé la méthode log_model c'est bien ça ? On l'a enregsitré manuellement dans un artifact ?


**Réponse de Claude**

Exactement. Dans le module 2, aucune flavor n'est utilisée pour ce modèle : tu sérialises toi-même avec `pickle`, puis `log_artifact` se contente de copier le fichier dans le store du run. MLflow ne sait pas qu'il s'agit d'un modèle — pour lui c'est un fichier binaire quelconque, au même titre qu'un CSV ou un PNG.

## Une nuance importante sur `lin_reg.bin`

```python
pickle.dump((dv, lr), f_out)
```

Les parenthèses créent un **tuple**. Tu ne sérialises pas deux choses à la suite, tu sérialises un unique objet qui contient les deux. Donc `lin_reg.bin` embarque **à la fois le vectorizer et le modèle**. Au rechargement, il faut déballer symétriquement :

```python
with open('models/lin_reg.bin', 'rb') as f_in:
    dv, lr = pickle.load(f_in)
```

C'est d'ailleurs le point où l'on se plante le plus souvent : si tu fais `lr = pickle.load(f_in)`, tu récupères le tuple entier et `lr.predict(...)` explose avec un `AttributeError: 'tuple' object has no attribute 'predict'`.

Conséquence : dans ce dossier `/models`, tes deux fichiers se chevauchent. `preprocessor.b` contient le `dv` seul, qui est déjà à l'intérieur de `lin_reg.bin`. Ce n'est pas une erreur, c'est l'histoire du notebook : le bloc `preprocessor.b` correspond à la partie XGBoost, plus tard dans le module, où le modèle passe par `mlflow.xgboost.log_model` et où le préprocesseur doit donc être loggé à part. Les deux conventions cohabitent dans le même dossier.

## Ce que le module 2 te fait vivre, dans l'ordre

C'est une progression pédagogique délibérée :

1. **`pickle` + `log_artifact`** — la méthode « à la main ». Ça marche, c'est transparent, tu comprends exactement ce qui est écrit sur disque.
2. **`mlflow.xgboost.autolog()`** — MLflow intercepte l'appel à `xgb.train` et logge automatiquement paramètres, métriques et modèle.
3. **`mlflow.<flavor>.log_model()`** — le logging explicite avec flavor, qui est ce que tu retrouves dans le script du module 3.

Le but est de te faire sentir ce que tu perds avec l'approche pickle nue :

- **aucune trace de l'environnement** — rien ne dit avec quelle version de scikit-learn ce `Lasso` a été entraîné. Un pickle chargé avec une version différente peut lever un warning, se charger avec un comportement subtilement différent, ou refuser de se charger ;
- **aucun contrat d'interface** — pour recharger, il faut *savoir* que c'est un tuple `(dv, lr)`. Cette information n'existe nulle part dans l'artefact, seulement dans la tête de celui qui a écrit le code ;
- **pas de `mlflow.pyfunc.load_model`**, donc pas de code de déploiement générique ;
- **pas de `mlflow models serve`**, pas de Model Registry — impossible d'enregistrer, versionner et promouvoir ce fichier en Staging/Production.

## Un dernier détail

Les extensions `.bin` et `.b` n'ont aucune signification technique. `pickle` produit le même format quel que soit le nom du fichier ; tu pourrais l'appeler `truc.pkl` ou `truc.txt`, ça fonctionnerait pareil. C'est une pure convention de lisibilité du cours. Le seul élément qui compte réellement est le `"wb"` / `"rb"` à l'ouverture — *binary*, car pickle écrit des octets, pas du texte.