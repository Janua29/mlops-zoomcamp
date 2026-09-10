# Push on git remote

**Summary**

cd /workspaces/mlops-zoomcamp
git add .
git commit -m "mon message"
git push

git status  (pour voir si aucun nouveaux fichiers n'a été oublié, même avec git add ., ça m'aie déjà arrivé)

**1. Aller dans le repo**

`cd /workspaces/mlops-zoomcamp`

**2. Voir ce qui a changé**

`git status`

**3a. Cas normal - ajouter fichier par fichier**

`git add fichier1`

`git add fichier2`

`git commit -m "mon message"`

**3b. Raccourci - commiter TOUTES les modifications connues de git**

`git commit -am "mon message"`

**3c. Raccourci - commiter TOUTES les modifications connues de git+tous les nouveaux fichier non trackées par git pour le moment**

`git add .`

**résumé de spossibilité**

Commande	Fichiers modifiés connus	Nouveaux fichiers (untracked)
git add .	✅	✅
git commit -am	✅	❌
git add fichier	✅ un seul	✅ un seul

**⚠️ Ne prend PAS les nouveaux fichiers (untracked)**

**4. Pousser**

`git push origin main`

### git push vs git git oush origin main

Tu es explicite — tu précises :

`origin` → le nom du dépôt distant (ton fork sur GitHub)

`main` → la branche que tu veux pousser
`git push`

Git utilise la configuration par défaut — il sait déjà vers où pousser car ta branche main est liée à origin/main depuis le début.

Dans ton cas

Les deux sont équivalents car ton repo a été cloné par Codespaces qui a configuré automatiquement origin et le lien entre main local et main distant.

Tu peux vérifier ça avec :

bash

`git remote -v`

Tu devrais voir :

`origin  https://github.com/Janua29/mlops-zoomcamp (fetch)
origin  https://github.com/Janua29/mlops-zoomcamp (push)`

# MLflow

Les experiment et run MLflow are saved in a .db file in a folder.
to retrieve the .db file when you relaucnh mlflow after having stop a codespace, you need to open MLFlow in the right folder --> you need to

`conda activate mlopszoomcamp`
`mlflow ui \`
 ` --backend-store-uri sqlite:////workspaces/mlops-zoomcamp/02-experiment-tracking/mlflow.db \`
 ` --default-artifact-root /workspaces/mlops-zoomcamp/02-experiment-tracking/mlruns`

pas besoin de ça : `mlflow ui --backend-store-uri sqlite:////workspaces/mlops-zoomcamp/02-experiment-tracking/mlflow.db --host 0.0.0.0 --port 5000 --allowed-hosts "*" --cors-allowed-origins "*" `

In the notebook, you also need to have these two line + be sure to choose the **right kernel** (mlopszoomcamp)

`mlflow.set_tracking_uri("http://127.0.0.1:5000")`
`mlflow.set_experiment("nyc-taxi-experiment")`

Sinon, recommandations de clAUDE

vaut mieux le régler une fois pour toutes. Le principe : un seul endroit qui fait autorité. Dans le notebook, ne pointe jamais vers le fichier SQLite — pointe vers le serveur :

`mlflow.set_tracking_uri("http://127.0.0.1:5000")`

OU

Plutôt que de recoller une longue commande (avec les risques de guillemet manquant que tu viens de vivre), crée un fichier une fois pour toutes :

bash
cat > /workspaces/mlops-zoomcamp/start_mlflow.sh << 'EOF'
#!/bin/bash
source ~/miniconda3/etc/profile.d/conda.sh
conda activate mlopszoomcamp
mlflow ui \
  --backend-store-uri sqlite:////workspaces/mlops-zoomcamp/02-experiment-tracking/mlflow.db \
  --default-artifact-root /workspaces/mlops-zoomcamp/02-experiment-tracking/mlruns \
  --host 0.0.0.0 --port 5000 \
  --allowed-hosts "*" --cors-allowed-origins "*"
EOF
chmod +x /workspaces/mlops-zoomcamp/start_mlflow.sh

Ensuite, à chaque session : ./start_mlflow.sh. Comme le fichier est dans le repo, il survit aussi à une reconstruction du Codespace, contrairement à un alias dans ~/.bashrc.

J'ai ajouté --default-artifact-root avec un chemin absolu : ça règle le problème d'artifact_location='./mlruns/1' que je te signalais. Les nouveaux runs écriront leurs modèles et pickles à un endroit fixe au lieu de suivre le dossier courant du notebook.
