# Push on git remote

**1. Aller dans le repo**

<code>cd /workspaces/mlops-zoomcamp<code>

**2. Voir ce qui a changé**

<code>git status<code>

**3a. Cas normal - ajouter fichier par fichier**

git add fichier1

git add fichier2

git commit -m "mon message"

**3b. Raccourci - commiter TOUTES les modifications connues de git**

git commit -am "mon message"

**⚠️ Ne prend PAS les nouveaux fichiers (untracked)**

**4. Pousser**

git push origin main

### git push vs git git oush origin main

Tu es explicite — tu précises :

<code>origin<code> → le nom du dépôt distant (ton fork sur GitHub)

<code>main<code> → la branche que tu veux pousser
<code>git push<code>

Git utilise la configuration par défaut — il sait déjà vers où pousser car ta branche main est liée à origin/main depuis le début.

Dans ton cas

Les deux sont équivalents car ton repo a été cloné par Codespaces qui a configuré automatiquement origin et le lien entre main local et main distant.

Tu peux vérifier ça avec :

bash

<code>git remote -v<code>

Tu devrais voir :

<code>origin  https://github.com/Janua29/mlops-zoomcamp (fetch)<code>
<code>origin  https://github.com/Janua29/mlops-zoomcamp (push)<code>