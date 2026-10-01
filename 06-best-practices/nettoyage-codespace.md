# Cours — Nettoyer l'espace disque d'un Codespace GitHub

Oct 1, 2026 · @Pierre

Un Codespace se nettoie en deux temps : on mesure d'abord, niveau par niveau, puis on supprime ce qui se retélécharge ou se reconstruit. Ce cours reprend le nettoyage réel du Codespace `mlops-zoomcamp` : de 24 Go utilisés à environ 15 Go.

## 1. Pourquoi nettoyer : le quota en Go-mois

GitHub ne facture pas l'espace occupé à un instant donné, mais l'espace occupé **multiplié par la durée**. L'unité est le Go-mois : 1 Go conservé pendant un mois entier. Un compte gratuit dispose de 15 Go-mois de stockage et de 120 heures-cœur de calcul par mois.

Un Codespace qui occupe 30 Go consomme donc tout le quota en 15 jours environ, **même arrêté**. Une fois le quota atteint, GitHub bloque l'accès jusqu'au début du cycle suivant. Supprimer des fichiers après coup ne rembourse rien : cela ralentit seulement la consommation à venir.

| Situation | Ce qui est plein | Effet | Solution |
| --- | --- | --- | --- |
| Disque plein | Les 32 Go du Codespace | Les commandes échouent (« No space left on device ») | Nettoyer depuis le Codespace |
| Quota épuisé | Les 15 Go-mois du compte | Impossible d'ouvrir le Codespace | Attendre le cycle suivant, ou ajouter un budget payant |

Le travail reste récupérable même quota épuisé : sur github.com/codespaces, menu « … », puis *Export changes to a branch*.

La règle à retenir : **chaque Go laissé sur le disque coûte du quota chaque jour**.

## 2. Diagnostic : voir ce qui occupe la place

Trois commandes suffisent pour une vue d'ensemble. On ne supprime **rien** avant d'avoir mesuré.

```bash
# Combien est utilisé sur le disque principal ?
df -h /

# Combien occupe Docker (images, conteneurs, volumes, cache de build) ?
docker system df

# Quels sont les plus gros dossiers du disque ?
sudo du -xh --max-depth=1 / 2>/dev/null | sort -rh | head -15
```

Ce que fait chaque morceau de la dernière commande :

- `du` (*disk usage*) additionne la taille des fichiers sous un dossier.
- `-x` reste sur le même disque : il ignore `/proc` et les autres montages, comme celui de Docker.
- `-h` affiche des tailles lisibles (`7.8G` plutôt que `8178452`).
- `--max-depth=1` ne détaille qu'un niveau sous le dossier de départ.
- `sort -rh` trie du plus gros au plus petit, en comprenant les suffixes G et M.
- `head -15` garde les 15 premières lignes.
- `sudo` et `2>/dev/null` évitent les erreurs « Permission denied » qui pollueraient l'affichage.

**Pourquoi `df` et `du` ne donnent pas le même total.** `df` mesure tout le disque physique. `du -x` ignore les autres montages, dont les données de Docker. Dans notre cas : `df` affichait 24 Go et `du` 17 Go. L'écart correspondait aux \~5,5 Go de Docker.

**Cas réel : répartition des 24 Go du Codespace**

| Zone | Taille | Supprimable ? |
| --- | --- | --- |
| `/usr` + `/opt` (image système) | 8,3 Go | Non : outils préinstallés, probablement non facturés |
| Docker | 5,5 Go | En partie : 2,5 Go d'images inutilisées |
| `~/miniconda3` | 4,6 Go | En partie : environnements + cache `pkgs/` |
| `~/.local` | 1,4 Go | En partie : virtualenvs pipenv |
| `~/.cache` | 1,4 Go | Oui, entièrement |
| `~/.vscode-remote` | 0,4 Go | Non : serveur VS Code |

## 3. Nettoyer Docker

Docker accumule quatre types d'objets, du moins risqué au plus risqué à supprimer. La colonne RECLAIMABLE de `docker system df` indique ce qui peut partir sans casser un conteneur actif.

**Cache de build : sans risque.** Ce sont les couches intermédiaires gardées pour accélérer les `docker build` suivants. Les supprimer rend seulement le prochain build plus lent. C'est souvent le plus gros consommateur après des séances de débogage avec des builds répétés.

```bash
docker builder prune -af
```

**Conteneurs arrêtés : à confirmer.** Supprimer un conteneur détruit sa couche d'écriture, comme `docker compose down`. Exemple : un dashboard Grafana sauvegardé depuis l'interface, sans provisioning, disparaît.

```bash
docker ps -a --filter status=exited      # voir d'abord
docker container prune -f                # supprimer
```

**Images inutilisées : à confirmer.** `-a` supprime toutes les images qu'aucun conteneur n'utilise, même arrêté. Elles seront retéléchargées ou reconstruites au prochain `docker compose up`.

```bash
docker images                            # toutes les images
docker ps -a --format '{{.Image}}'       # celles réellement utilisées
docker image prune -af                   # supprimer les autres
```

**Images encore utilisées par une stack Compose.** Docker refuse de supprimer une image tant qu'un conteneur s'appuie dessus, même arrêté. L'ordre est donc toujours le même : arrêter les conteneurs, les supprimer, puis supprimer les images. Pour une stack lancée avec Compose (conteneurs nommés `05-monitoring-*`, par exemple), une seule commande fait les trois étapes, depuis le dossier qui contient le `docker-compose.yml` :

```bash
cd /workspaces/mlops-zoomcamp/05-monitoring
docker compose down --rmi all     # conteneurs + réseau + images des services
docker image prune -a             # puis les images restées sans conteneur
```

- `down` arrête et supprime les conteneurs, ainsi que le réseau créé par Compose.
- `--rmi all` supprime les images utilisées par les services du fichier (ici `adminer`, `grafana/grafana-enterprise` et `postgres`).
- Les volumes sont conservés. Il faudrait ajouter `-v` pour les supprimer aussi.

Un dashboard Grafana créé depuis l'interface, sans fichier de provisioning, disparaît avec le conteneur. Un futur `docker compose up` retéléchargera simplement les images.

**Volumes : jamais en automatique.** Ils contiennent les données persistantes, comme la base PostgreSQL du module 05. On les supprime un par un, en connaissance de cause.

```bash
docker volume ls
docker volume rm <nom>
```

À éviter : `docker system prune -a --volumes`. Cette commande supprime tout d'un coup, volumes compris.

## 4. Nettoyer les environnements conda

Un environnement conda avec scikit-learn, XGBoost, MLflow et pandas pèse 1 à 3 Go. Supprimer ceux qui ne servent plus est le gain le plus net après Docker.

**Étape 1 : mesurer.**

```bash
conda env list
conda info --base                       # où est installé conda
du -sh "$(conda info --base)"/envs/* "$(conda info --base)"/pkgs | sort -rh
```

**Étape 2 : exporter la recette dans le dépôt avant de supprimer.** Le fichier `.yml` pèse quelques Ko et permet de recréer l'environnement à l'identique. On le range dans le dépôt plutôt que dans `~`, qui disparaît si le Codespace est supprimé. Une fois poussé sur GitHub, il est versionné et à l'abri.

```bash
cd /workspaces/mlops-zoomcamp
mkdir -p env-backups
conda env export -n mlopszoomcamp --no-builds > env-backups/mlopszoomcamp.yml
git add env-backups
git commit -m "Sauvegarde de l'environnement conda mlopszoomcamp"
git push
```

`--no-builds` retire les numéros de build propres à la machine, ce qui rend la recette plus facile à réinstaller ailleurs. Pour recréer l'environnement plus tard : `conda env create -f env-backups/mlopszoomcamp.yml`.

**Étape 3 : supprimer, puis vider le cache.**

```bash
conda activate base                     # on ne peut pas supprimer l'env actif
conda env remove -n mlopszoomcamp
conda clean --all -y
```

**Pourquoi `conda clean` est indispensable.** conda n'installe pas deux fois le même fichier. Il garde l'original dans `pkgs/` et crée dans chaque environnement un **lien physique** vers ce fichier. Un lien physique est un deuxième nom pour les mêmes données sur le disque. Les données ne sont libérées que quand **tous** les noms ont disparu : supprimer l'environnement retire l'un, `conda clean` retire l'autre.

**Étape 4 : retirer les noyaux Jupyter orphelins.** Sinon, ils restent proposés dans VS Code et plantent au lancement.

```bash
jupyter kernelspec list
jupyter kernelspec remove <nom>
```

## 5. Vider les caches (`~/.cache`)

`~/.cache` peut être vidé entièrement, sans risque. Il contient des copies de fichiers téléchargés : paquets pip et pipenv, environnements pre-commit, etc. Chaque outil retélécharge ce dont il a besoin au prochain usage.

```bash
du -sh ~/.cache/* 2>/dev/null | sort -rh   # voir ce qui pèse
rm -rf ~/.cache/*                          # tout vider
```

Pour pip seulement, l'équivalent officiel est `python -m pip cache purge`.

## 6. Nettoyer `~/.local`

`~/.local` mélange des contenus très différents : on l'explore avant de toucher quoi que ce soit.

```bash
du -h --max-depth=3 ~/.local 2>/dev/null | sort -rh | head -10
```

**`~/.local/share/virtualenvs/` : les environnements pipenv, supprimables.** pipenv nomme chaque environnement d'après le nom du dossier du projet, suivi d'un hash de son chemin complet. Exemple : `web-service-mlflow-WCFAIHla` correspond à `04-deployment/web-service-mlflow`. Un virtualenv est un dossier autonome, qu'on peut supprimer directement :

```bash
rm -rf ~/.local/share/virtualenvs/web-service-mlflow-WCFAIHla
```

Pour le recréer, il suffit de lancer `pipenv install` dans le dossier du projet : le `Pipfile.lock` garantit les mêmes versions. `pipenv --rm`, lancé depuis ce dossier, fait la même chose que le `rm -rf`, mais il échoue si le dossier du projet a été déplacé, car le hash ne correspond plus.

**`~/.local/lib/python3.x/` : les paquets `pip install --user`, à garder.** Ils ont été installés par le Python système, hors conda. pipenv lui-même est souvent installé là. Avant toute suppression, vérifie :

```bash
which pipenv          # ~/.local/bin/pipenv → pipenv vit dans ~/.local
```

**`~/.local/share/jupyter/` : réglages Jupyter, à garder.** Quelques dizaines de Mo seulement.

## 7. Méthode de deep-dive : descendre, puis supprimer

La méthode est toujours la même : partir de la racine, descendre dans le plus gros dossier, et recommencer jusqu'à trouver quelque chose d'identifiable. C'est ce qu'on a fait en partant de `/`, puis `/home/codespace`, puis `~/.local`, jusqu'à `virtualenvs/`.

1. Lancer `du` sur le dossier courant, à un seul niveau de profondeur :

   ```bash
   du -xh --max-depth=1 <dossier> 2>/dev/null | sort -rh | head -10
   ```
2. Repérer la plus grosse ligne, hors la première, qui est le total du dossier lui-même.
3. Relancer la même commande sur ce sous-dossier.
4. S'arrêter quand le nom est identifiable : un environnement, un cache, un jeu de données, des images Docker.
5. Se poser une seule question : **est-ce que ça se retélécharge ou se reconstruit ?** Oui → supprimable. Non, ou je ne sais pas → on garde, ou on demande.
6. Regarder avant de supprimer : `ls <chemin>`, puis `du -sh <chemin>`.
7. Supprimer avec l'outil propre au contenu (`conda env remove`, `docker image prune`…). À défaut, utiliser `rm -rf <chemin>`.
8. Remesurer avec `df -h /` pour vérifier le gain réel.

**Précautions avec `rm -rf`.** La commande ne demande aucune confirmation et ne passe pas par une corbeille. Écris toujours le chemin complet, jamais avec une variable qui pourrait être vide. Par exemple, `rm -rf $DOSSIER/*` devient `rm -rf /*` si `$DOSSIER` est vide.

**Variante interactive.** L'outil `ncdu` affiche la même descente dans une interface navigable au clavier. Installation : `sudo apt install ncdu`. Lancement : `ncdu -x /`.

## 8. Récapitulatif

Le nettoyage a libéré environ 9 Go. Le tableau sert d'aide-mémoire, classé du moins risqué au plus risqué.

| Cible | Commande | Risque | Gain constaté |
| --- | --- | --- | --- |
| Cache de build Docker | `docker builder prune -af` | Aucun : builds plus lents | 0 Go (déjà vide) |
| Caches pip / pipenv / pre-commit | `rm -rf ~/.cache/*` | Aucun : retéléchargement | 1,4 Go |
| Cache de paquets conda | `conda clean --all -y` | Aucun : retéléchargement | 0,7 Go |
| Virtualenvs pipenv | `rm -rf ~/.local/share/virtualenvs/<nom>` | Faible : `pipenv install` les recrée | 1,15 Go |
| Environnements conda | `conda env remove -n <nom>` | Faible si `.yml` exporté | 3,6 Go |
| Images Docker inutilisées | `docker image prune -af` | Faible : retéléchargement | 2,5 Go |
| Conteneurs arrêtés | `docker container prune -f` | Moyen : perte de la couche d'écriture | — |
| Volumes Docker | `docker volume rm <nom>` | **Élevé : perte de données** | jamais en automatique |
| Image système (`/usr`, `/opt`) | — | Ne pas toucher | — |

Le script `cleanup.sh`, à la racine du dépôt, enchaîne automatiquement les étapes sans risque et demande confirmation pour les autres.

**Check-list de fin de session**

- [ ] Commiter et pousser son travail : `git push`
- [ ] Lancer `bash cleanup.sh`
- [ ] Vérifier `df -h /` : rester sous \~15 Go utilisés
- [ ] Arrêter les conteneurs avec `docker compose stop` (pas `down`, qui détruit leur couche d'écriture)
- [ ] Vérifier sur github.com/codespaces qu'il n'existe qu'un seul Codespace
- [ ] Une fois par semaine : consulter la consommation dans *Settings → Billing and plans*
