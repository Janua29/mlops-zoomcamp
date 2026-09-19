## La subtilité MLflow 3

Dans le notebook du cours, tu vas logger le modèle comme ça :

```python
mlflow.sklearn.log_model(pipeline, artifact_path="model")
```

puis le recharger dans `predict.py` avec :

```python
logged_model = f'runs:/{RUN_ID}/model'
model = mlflow.pyfunc.load_model(logged_model)
```

Ce `runs:/<run_id>/model` repose sur une hypothèse de MLflow 2 : **le modèle est un sous-dossier dans les artifacts du run**. MLflow 3 a cassé ça. Un modèle y est devenu une **entité de premier ordre**, indépendante du run : il reçoit son propre identifiant (`model_id`) et s'adresse par `models:/m-<hash>`. Le run ne fait plus que le *référencer*.

Concrètement :
- `artifact_path=` est déprécié → le paramètre s'appelle maintenant **`name=`**
- après le `log_model`, récupère l'URI propre plutôt que de la reconstruire à la main :

```python
with mlflow.start_run():
    ...
    model_info = mlflow.sklearn.log_model(pipeline, name="model")
    print(model_info.model_uri)   # → models:/m-xxxxxxxx
```

C'est ce `model_info.model_uri` que tu passes à `mlflow.pyfunc.load_model()` dans `predict.py`, à la place du `runs:/...`.

Vérifie d'abord ta version, parce que le comportement dépend d'elle :

```bash
python -c "import mlflow; print(mlflow.__version__)"
```

Si tu es en 3.x, applique ce qui précède. Si tu es en 2.x, le code du cours marche tel quel.

## Un bonus qui va te tomber dessus aussi

Le notebook contient probablement :

```python
rmse = mean_squared_error(y_pred, y_val, squared=False)
```

Avec ton scikit-learn 1.9, ça lèvera une `TypeError` : l'argument `squared` a été supprimé en 1.6. Remplace par :

```python
from sklearn.metrics import root_mean_squared_error
rmse = root_mean_squared_error(y_val, y_pred)
```

Lance le notebook, et remonte-moi la traceback si autre chose casse.