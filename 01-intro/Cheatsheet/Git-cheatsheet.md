# Push on git remote

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