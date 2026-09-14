# Things to check when restart the codespace

conda activate mlopszoompcamp
check the kernel in VS code

MLflow UI activate : be careful to the absolute vs relative path --> when you activate MLflow UI, need to have the right adress to the .db file. It is in this .db file that all your experiments/runs are registered / saved

Note
- git command : no need to be in the mlopszoomcamp conda env
- for everything related to python : need to be in the right env


# Push on git remote

**Summary**

From VS-code, save all the modifed files. Then

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


# Mémo — Diagnostiquer un dépôt git qui "a l'air bizarre"
 
> Contexte : retrouvé un Codespace où seul `01-intro` apparaissait, alors que GitHub
> affichait bien tous les dossiers. Cause réelle : mauvais Codespace ouvert.
 
---
 
## 1. Les commandes de diagnostic
 
À lancer dans le terminal, dans le dossier du dépôt. Le terminal dit la vérité ;
l'explorateur de VS Code, lui, peut avoir un filtre d'affichage actif.
 
| Commande | Question à laquelle elle répond |
|---|---|
| `pwd` | Où suis-je sur le disque ? |
| `ls -la` | Qu'y a-t-il **réellement** dans le dossier (y compris les fichiers cachés comme `.git`) ? |
| `git status` | Quelle branche, et quelles modifications en attente ? |
| `git log --oneline -5` | Sur quel commit je suis, et quel est l'historique récent ? |
| `git remote -v` | À quels dépôts distants je suis relié (`origin`, `upstream`) ? |
| `git branch -vv` | Quelles branches locales, et à quelle branche distante chacune est rattachée ? |
| `git ls-tree --name-only HEAD` | Que contient **le commit** (indépendamment de ce qui est déplié sur le disque) ? |
 
### La commande la plus rentable
 
```bash
git log --oneline -5
```
 
Elle répond en une seconde à « suis-je au bon endroit ? ».
 
**L'indice qui a tout débloqué :** le log affichait 4 commits dont un
`Initial commit`, alors que GitHub en affichait 600.
 
→ Un **vrai fork** hérite de tout l'historique du dépôt d'origine (ici ~590 commits).
Un historique qui *démarre* par `Initial commit` a été créé à vide.
Ce n'étaient donc pas deux états du même dépôt, mais **deux dépôts différents**.
 
### Autre indice utile
 
`ls -la` affiche la **taille** et la **date** des fichiers. Un `README.md` de 36 octets
là où on attend plusieurs kilo-octets, ou une date bien plus ancienne que les autres,
signale un contenu qui n'est pas celui qu'on croit.
 
---
 
## 2. `origin/main` = une photo locale, pas une lecture en direct
 
C'est le point qui prête le plus à confusion.
 
Quand git affiche :
 
```
On branch main
Your branch is up to date with 'origin/main'.
```
 
il **ne vient pas d'interroger GitHub**.
 
`origin/main` est une *photo* de l'état du dépôt distant, prise lors du dernier
`git fetch` ou `git pull`, et stockée en local dans `.git`. Git dit donc :
 
> « Tu es à jour par rapport à la photo que j'ai dans mon tiroir. »
 
Si la photo date de trois semaines, le message est exact… et complètement trompeur.
 
### Rafraîchir la photo
 
```bash
git fetch origin
```
 
`fetch` va chercher une photo fraîche du distant. Il **ne touche pas** à tes fichiers
ni à ta branche locale : il met seulement à jour `origin/main`.
 
Pour comparer avant/après :
 
```bash
git log --oneline -5 origin/main
```
 
### Les 3 niveaux à distinguer
 
```
GitHub (le serveur)          ← la source de vérité
    ↓ git fetch
origin/main (photo locale)   ← ce que git croit savoir du serveur
    ↓ git merge / git reset
main (ma branche locale)     ← où j'en suis vraiment
    ↓ checkout
working tree (mes fichiers)  ← ce que je vois dans VS Code
```
 
`git pull` = `git fetch` + `git merge`. C'est pour ça qu'un `pull` "répare"
parfois ce qu'un `status` seul n'avait pas vu : il rafraîchit la photo au passage.
 
---
 
## 3. La séquence de resynchronisation
 
### Étape 1 — Sauvegarder (jamais sauter)
 
```bash
git status                                  # y a-t-il des modifs en attente ?
git add -A
git commit -m "sauvegarde avant resync"
git branch sauvegarde-ancien-etat           # marque-page sur l'historique actuel
```
 
`git branch <nom>` pose juste une étiquette sur le commit courant.
Tant qu'elle existe, cet état reste retrouvable — c'est le filet de sécurité.
 
### Étape 2 — Rafraîchir
 
```bash
git fetch origin
git log --oneline -5 origin/main            # vérifier que c'est bien le bon historique
```
 
### Étape 3 — Basculer
 
```bash
git reset --hard origin/main
ls -la
```
 
⚠️ `--hard` **écrase** le working tree et toute modification non commitée.
D'où l'étape 1.
 
---
 
## 4. Spécifique Codespaces
 
### Vérifier qu'on ouvre le bon
 
**github.com/codespaces** liste tous les Codespaces avec leur dépôt d'origine.
Avoir plusieurs Codespaces sur le même dépôt est la source de confusion n°1.
 
**Réflexe :** les renommer (menu `...` → Rename). `mlops-zoomcamp-main` est plus
parlant que `upgraded bassoon`.
 
### Ce qui N'EST PAS sur GitHub
 
Un Codespace éteint conserve son disque, mais certaines choses ne vivent QUE là
et ne sont donc pas récupérables via `git` :
 
- l'**environnement conda** (`mlopszoomcamp`)
- le fichier **`mlflow.db`** (tous les runs de tracking) — il est dans le `.gitignore`
- tout fichier ignoré par git en général
→ **Ne jamais supprimer un Codespace sans avoir vérifié lequel les contient.**
Un Codespace inutilisé consomme du quota de stockage même éteint : faire le ménage,
mais en connaissance de cause.
 
---
 
## 5. Fausse piste à écarter en premier
 
Si `ls -la` montre bien tous les fichiers mais que l'explorateur VS Code n'en
affiche qu'une partie :
 
1. Cliquer dans l'explorateur puis appuyer sur **Échap** — taper du texte avec
   l'explorateur sélectionné active un **filtre invisible** sur l'arborescence.
2. Bouton **Refresh Explorer** (icône circulaire en haut du panneau).
3. `Cmd+Shift+P` → **Developer: Reload Window**.
C'est gratuit à tester et ça règle un cas sur deux.
 
---
 
## À retenir en 3 lignes
 
1. `git log --oneline -5` avant toute autre hypothèse.
2. `origin/main` est une photo périmée jusqu'au prochain `git fetch`.
3. Sauvegarder (`commit` + `branch`) avant tout `reset --hard`.


# MLflow

Les experiment et run MLflow are saved in a .db file in a folder.
to retrieve the .db file when you relaucnh mlflow after having stop a codespace, you need to open MLFlow in the right folder --> you need to

`conda activate mlopszoomcamp`

`mlflow ui \`
 ` --backend-store-uri sqlite:////workspaces/mlops-zoomcamp/02-experiment-tracking/mlflow.db \`
 ` --default-artifact-root /workspaces/mlops-zoomcamp/02-experiment-tracking/mlruns`

 or just `mlflow ui --backend-store-uri sqlite:////workspaces/mlops-zoomcamp/02-experiment-tracking/mlflow.db `

 Indeed, in the jupyter notebook, we have written : `mlflow.set_tracking_uri("sqlite:///mlflow.db")` --> it is a relative path --> if I am in mlops-zoomcamp/01-Intro --> it will create a new mlflow.db file in mlops-zoomcamp/01-Intro --> it won't re-use the .db file in mlops-zoomcamp/02-experiment-tracking/mlflow.db `

pas besoin de ça : 

`mlflow ui --backend-store-uri sqlite:////workspaces/mlops-zoomcamp/02-experiment-tracking/mlflow.db --host 0.0.0.0 --port 5000 --allowed-hosts "*" --cors-allowed-origins "*" `

**Le tracking_uri de ton notebook**

C'est la cause la plus probable vu ton historique. Après le redémarrage du Codespace, quel set_tracking_uri as-tu exécuté ?

Si c'est encore sqlite:///mlflow.db (3 slashes, chemin relatif), ton run est écrit dans un fichier qui dépend du dossier courant du notebook — pas forcément celui que ton serveur lit.

La version robuste, celle que je te recommandais :

python
`mlflow.set_tracking_uri("http://127.0.0.1:5000")`
`mlflow.set_experiment("nyc-taxi-experiment")`

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
