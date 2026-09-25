Cours — Docker & espace disque dans un Codespace
Sep 23, 2026 · @Pierre
Introduction
Ce cours t'apprend à garder un Codespace propre en maîtrisant Docker : comprendre ce qui prend de la place, le mesurer, le supprimer sans rien casser, et ne plus le laisser s'accumuler.
Il part d'un cas réel : un Codespace de 32 Go rempli à 93 %, ramené à 77 % (7 Go libres) en vidant 4,7 Go de cache de build Docker. Ton projet mlops-zoomcamp ne pesait que 111 Mo : tout le reste venait des outils autour.
À la fin, tu sauras :
• expliquer la différence entre une image, un conteneur, une couche, un cache et un volume ;
• diagnostiquer n'importe quel disque plein avec df, du, ncdu et docker system df ;
• choisir la bonne commande prune selon ce que tu veux supprimer et le risque accepté ;
• écrire des Dockerfiles et des habitudes de travail qui n'empilent plus rien ;
• reprendre ton travail d'un jour à l'autre sans rebuilder.
Les parties 1 à 3 posent les bases, les parties 4 à 7 sont le cœur pratique, la partie 8 t'emmène vers le niveau expert. La partie 9 est l'antisèche à garder sous la main.
Partie 1 — Comprendre ce que Docker stocke
Docker stocke cinq types d'objets sur ton disque, et chacun se nettoie avec une commande différente. Les confondre est la première cause d'erreur.
L'analogie de la pâtisserie
• Le Dockerfile est la recette écrite.
• L'image est le moule fabriqué à partir de la recette. Elle est figée : on ne la modifie pas, on en fabrique une nouvelle.
• Le conteneur est un gâteau sorti du moule. On peut en faire plusieurs avec le même moule, et chacun peut être « mangé » (modifié) sans toucher au moule.
• Le cache de build est le stock d'ingrédients déjà préparés : il accélère la prochaine fabrication.
• Le volume est une boîte de rangement externe, qui garde des données même quand le gâteau est jeté.
Les cinq objets en détail
Objet
Ce que c'est
Créé par
Exemple dans le cours
Image
Modèle figé, en lecture seule, fait de couches empilées
docker build, docker pull
ride-duration-prediction-service:v1, apache/airflow
Conteneur
Instance d'une image, avec une petite couche modifiable par-dessus
docker run, docker compose up
Ton serveur Gunicorn en train de tourner
Couche (layer)
Une étape du Dockerfile (RUN, COPY...) enregistrée sur disque
Chaque instruction du Dockerfile
La couche pipenv install de 400 Mo
Cache de build
Couches intermédiaires gardées pour réutilisation
Chaque docker build
Tes 26 entrées de 4,7 Go
Volume
Dossier de données géré par Docker, hors de l'image
docker volume create, Compose
La base Postgres d'Airflow (41 Mo)
Pourquoi les couches comptent
Une image est un empilement de couches, comme des calques transparents. Deux images qui partent de python:3.10-slim partagent la couche de base : elle n'est stockée qu'une fois.
Quand tu modifies une ligne du Dockerfile, Docker réutilise les couches du dessus depuis le cache et reconstruit tout ce qui suit. Les anciennes couches ne sont pas effacées : elles restent dans le cache ou dans l'ancienne image.
L'image orpheline (dangling)
C'est le mécanisme exact de l'empilement. Tu lances docker build -t ride-duration:v1 . une première fois : l'image A reçoit l'étiquette v1.
Tu corriges numpy et relances la même commande : l'image B est créée et vole l'étiquette v1. L'image A n'est pas supprimée, elle devient <none>:<none>, une image orpheline.
Dix rebuilds pour corriger numpy, skops et le Pipfile.lock font donc jusqu'à neuf images orphelines, plus leur cache.
Où Docker range tout ça
• Anciennes versions de Docker : /var/lib/docker.
• Versions récentes (ton cas) : /var/lib/containerd, avec io.containerd.snapshotter.v1.overlayfs pour les couches décompressées et io.containerd.content.v1.content pour les couches compressées téléchargées.
Ces dossiers sont gérés par Docker lui-même. On les observe, on ne les touche jamais à la main (partie 3).
Partie 2 — Diagnostiquer l'espace disque
On diagnostique toujours en entonnoir : quel disque est plein, puis quel dossier, puis quel objet Docker. L'explorateur de VS Code ne suffit pas, car il ne montre que /workspaces et cache les dossiers système.
Étape 1 — Quel disque est plein : df -h
df -h
df (disk free) liste chaque disque monté ; -h affiche en Go/Mo lisibles. Regarde les colonnes Use% et Mounted on.
Voici ton Codespace après nettoyage :
Filesystem      Size  Used Avail Use% Mounted on
overlay          32G   23G  7.0G  77% /
/dev/root        29G   14G   16G  46% /vscode
/dev/sda1        44G  4.5G   38G  11% /tmp
/dev/loop5       32G   23G  7.0G  77% /workspaces
Comment le lire :
• / et /workspaces affichent exactement les mêmes chiffres : c'est le même disque de 32 Go vu sous deux noms. Ton projet, ton home, conda et Docker partagent ces 32 Go.
• /vscode est un disque séparé, réservé au serveur VS Code. Tu n'y touches pas.
• /tmp est un autre disque de 44 Go. Il est vidé lorsque le Codespace est reconstruit : n'y garde rien d'important.
• tmpfs et shm sont en mémoire vive, pas sur le disque.
Étape 2 — Quel dossier est gros : du
du (disk usage) mesure la taille des dossiers. On le combine avec sort -h, qui trie des tailles lisibles du plus petit au plus gros : les coupables arrivent en bas.
# Taille de chaque dossier dans /workspaces
du -sh /workspaces/* 2>/dev/null | sort -h

# Sous-dossiers directs de ton home (caches, conda, pipenv...)
du -h --max-depth=1 ~ 2>/dev/null | sort -h

# Tout le système, les 20 plus gros
sudo du -h --max-depth=1 / 2>/dev/null | sort -h | tail -20
Morceau
Rôle
-s
Un seul total par argument (summary)
-h
Tailles lisibles (Go, Mo)
--max-depth=1
Descendre d'un seul niveau
2>/dev/null
Masquer les erreurs « Permission denied »
sudo
Lire aussi les dossiers système
sort -h
Trier des tailles lisibles
tail -20
Ne garder que les 20 dernières lignes
Ton résultat sur ~ montrait miniconda3 à 5,0 Go, .cache à 2,1 Go et .local à 1,4 Go, sur 8,9 Go au total.
Étape 3 — Naviguer visuellement : ncdu
ncdu est un explorateur de disque interactif dans le terminal. C'est l'outil le plus confortable pour débuter.
sudo apt update && sudo apt install -y ncdu   # installation, une seule fois
sudo ncdu /                                    # analyser tout le disque
ncdu ~                                         # analyser seulement ton home
Touche
Action
Flèches haut/bas
Se déplacer
Entrée
Entrer dans un dossier
Flèche gauche
Remonter
?
Aide
d
Supprimer (à éviter, voir partie 3)
q
Quitter
Le préfixe e devant une ligne signifie « dossier vide ». C'est avec ncdu que tu as trouvé /var/lib/containerd, le stockage de Docker.
Étape 4 — Le détail Docker : docker system df
docker system df        # résumé par type
docker system df -v     # détail image par image, conteneur par conteneur
TYPE            TOTAL     ACTIVE    SIZE      RECLAIMABLE
Images          5         3         5.357GB   2.51GB (46%)
Containers      3         3         2.081MB   0B (0%)
Local Volumes   1         1         40.91MB   0B (0%)
Build Cache     0         0         0B        0B
• TOTAL : nombre d'objets existants.
• ACTIVE : ceux utilisés par un conteneur. Ici 3 images servent aux 3 conteneurs.
• RECLAIMABLE : ce que tu peux libérer sans toucher à ce qui est actif. Ici 2,51 Go d'images restent récupérables.
Piège classique : ncdu et docker system df montrent les mêmes octets de deux façons. Les 8,4 Go de /var/lib/containerd ne s'ajoutent pas aux 10 Go d'images et de cache, ils les contiennent. Les couches partagées entre images expliquent les petits écarts.
Étape 5 — Lister ce qui existe
docker ps              # conteneurs en cours d'exécution
docker ps -a           # tous les conteneurs, y compris arrêtés
docker images          # images avec leur étiquette et leur taille
docker images -f dangling=true   # seulement les images orphelines <none>
docker volume ls       # volumes
Partie 3 — Les règles de sécurité avant de supprimer
Cinq règles évitent 99 % des catastrophes. Elles valent pour Docker comme pour Python.
Règle 1 — Ne jamais supprimer à la main un dossier géré par un outil
Cela vise /var/lib/containerd, /var/lib/docker, ~/miniconda3/envs, mlruns/. Chaque outil tient un registre de ce qu'il stocke : le fichier bolt pour Docker, mlflow.db pour MLflow.
Supprimer un fichier à la main revient à arracher des pages d'un livre sans mettre à jour le catalogue de la bibliothèque. L'outil croit que l'objet existe encore et plante au prochain usage avec des erreurs incompréhensibles.
La règle : on supprime avec l'outil qui a créé l'objet.
Objet
Supprimer avec
Jamais avec
Images, conteneurs, cache, volumes
docker ... prune, docker rm, docker rmi
rm -rf /var/lib/containerd/...
Environnement conda
conda env remove -n <nom>
rm -rf ~/miniconda3/envs/<nom>
Environnement pipenv
pipenv --rm
rm -rf ~/.local/share/virtualenvs/...
Runs MLflow
Interface MLflow puis mlflow gc
rm -rf mlruns/...
Seule exception : les caches et les logs, qui ne sont référencés par aucun registre. Même là, préfère la commande dédiée quand elle existe.
Règle 2 — Regarder ce qui tourne avant de nettoyer
docker ps        # ce qui tourne
docker ps -a     # ce qui existe, y compris arrêté
docker images    # les images et leur étiquette
Docker protège ce qui est utilisé par un conteneur, même arrêté. Si tu supprimes d'abord les conteneurs arrêtés, leurs images deviennent supprimables : l'ordre compte.
Pose-toi la question : ce conteneur arrêté contient-il quelque chose d'utile, comme un fichier créé à l'intérieur ? Si oui, récupère-le avec docker cp <conteneur>:/chemin ./ avant de le supprimer.
Règle 3 — Mesurer avant, mesurer après
df -h / && docker system df
# ... nettoyage ...
df -h / && docker system df
Tu sais ainsi ce que chaque commande t'a rapporté, et tu évites de lancer une commande radicale pour gagner 50 Mo.
Règle 4 — Aller du plus sûr au plus radical
Commence par ce qui se reconstruit tout seul (caches, orphelins), puis ce qui se reconstruit avec un peu de temps (images), et en dernier ce qui contient des données (volumes). La partie 4 classe chaque commande selon ce niveau.
Règle 5 — Ne jamais supprimer un volume sans savoir ce qu'il contient
Un volume est le seul objet Docker qui contient tes données : base Postgres d'Airflow, historique des runs, connexions configurées. Une image se reconstruit, un volume perdu est perdu.
docker volume ls                     # lister
docker volume inspect <nom>          # voir où il est et qui l'a créé
Ce qu'on peut supprimer, par niveau de risque
Niveau
Quoi
Conséquence
Commande (partie 4 ou 5)
Sans risque
Cache de build
Prochain build plus lent
docker builder prune -a
Sans risque
Images orphelines <none>
Aucune
docker image prune
Sans risque
Conteneurs arrêtés sans données utiles
Aucune
docker container prune
Sans risque
Caches pip et conda
Paquets retéléchargés si besoin
pip cache purge, conda clean --all
Sans risque
Logs Airflow
Historique des logs perdu
vider logs/
Modéré
Toutes les images inutilisées
Rebuild ou pull à refaire
docker image prune -a
Modéré
Virtualenvs pipenv d'exercices finis
pipenv install à refaire
pipenv --rm
Risqué
Volumes
Perte des données
docker volume prune -a
Risqué
Runs MLflow
Perte des expériences
mlflow gc après suppression dans l'UI
Interdit
Dossiers internes de Docker
Docker corrompu
aucune
Partie 4 — Les commandes de suppression Docker
Chaque commande prune (« élaguer ») cible un seul type d'objet et ne supprime que ce qui est inutilisé. L'option -a (all) élargit toujours la cible : c'est elle qu'il faut surveiller.
Vue d'ensemble
Commande
Supprime
Ne touche pas
Risque
docker container prune
Tous les conteneurs arrêtés
Conteneurs qui tournent
Faible : perte des fichiers créés dans ces conteneurs
docker image prune
Images orphelines <none>:<none>
Images étiquetées
Nul
docker image prune -a
Toutes les images non utilisées par un conteneur
Images des conteneurs existants, même arrêtés
Modéré : rebuild ou pull à refaire
docker builder prune
Cache de build orphelin
Cache encore référencé
Nul
docker builder prune -a
Tout le cache de build
Rien d'autre
Faible : prochain build plus lent
docker network prune
Réseaux non utilisés
Réseaux par défaut
Nul
docker volume prune
Volumes anonymes non utilisés
Volumes nommés
Faible
docker volume prune -a
Tous les volumes non utilisés, nommés compris
Volumes attachés à un conteneur
Élevé : perte de données
docker system prune
Conteneurs arrêtés + réseaux inutilisés + images orphelines + cache orphelin
Images étiquetées, volumes
Faible
docker system prune -a
Idem + toutes les images inutilisées + tout le cache
Volumes
Modéré
docker system prune -a --volumes
Idem + volumes anonymes inutilisés
Volumes nommés
Modéré à élevé
Toutes ces commandes demandent une confirmation [y/N]. L'option -f (force) la saute : ne l'utilise que dans un script que tu maîtrises.
Les conteneurs
docker container prune          # supprime tous les conteneurs arrêtés
docker rm <nom_ou_id>           # supprime un conteneur arrêté précis
docker rm -f <nom_ou_id>        # l'arrête puis le supprime
Où elle agit : sur la petite couche modifiable de chaque conteneur. Un conteneur pèse souvent quelques Mo (tes 3 conteneurs faisaient 2 Mo), mais il bloque la suppression de son image. C'est pourquoi on le nettoie en premier.
Les images
docker image prune              # seulement les <none>:<none>
docker image prune -a           # toutes les images sans conteneur
docker rmi <image:tag>          # une image précise
La différence clé :
• Sans -a : seulement les orphelines, qui n'ont plus de nom et ne servent à rien. Toujours sans risque.
• Avec -a : aussi les images nommées dont aucun conteneur ne se sert, par exemple ride-duration:v1 si tu n'as pas de conteneur lancé dessus. Tu devras la rebuilder.
Où elle agit : dans /var/lib/containerd, sur les couches qui ne sont plus partagées par aucune autre image.
Le cache de build
docker builder prune            # le cache orphelin seulement
docker builder prune -a         # tout le cache
Où elle agit : sur les couches intermédiaires gardées par BuildKit, le moteur de build. C'est souvent le plus gros poste après une série de rebuilds : 4,7 Go dans ton cas, 0 image impactée.
Les volumes
docker volume ls                # lister d'abord
docker volume prune             # anonymes inutilisés seulement
docker volume prune -a          # nommés inutilisés aussi
docker volume rm <nom>          # un volume précis
Depuis Docker 23, volume prune sans -a épargne les volumes nommés. Le volume Postgres d'Airflow est nommé : il n'est menacé que par -a, et seulement si ses conteneurs ont été supprimés.
Le grand ménage : docker system prune
system prune enchaîne plusieurs prune d'un coup. Pratique, mais on perd la visibilité sur ce qui part. En apprentissage, préfère les commandes séparées : tu vois ce que chacune rapporte.
docker system prune             # le ménage sûr
docker system prune -a          # le ménage profond, sans les volumes
Les commandes de Docker Compose
Compose a ses propres commandes, qui agissent seulement sur les objets du projet (le dossier contenant docker-compose.yaml).
Commande
Conteneurs
Réseaux
Volumes
Images
docker compose stop
Arrêtés, gardés
Gardés
Gardés
Gardées
docker compose down
Supprimés
Supprimés
Gardés
Gardées
docker compose down -v
Supprimés
Supprimés
Supprimés
Gardées
docker compose down --rmi all
Supprimés
Supprimés
Gardés
Supprimées
Pour Airflow : stop ou down au quotidien, down -v uniquement pour repartir de zéro.
Filtrer pour être précis
# Seulement ce qui a plus de 24 h
docker image prune -a --filter "until=24h"
docker container prune --filter "until=24h"
docker builder prune --filter "until=24h"
Utile pour garder ce que tu viens de construire et effacer les essais de la veille.
Partie 5 — Nettoyer l'environnement Python
Hors Docker, ton home pesait 8,9 Go : conda 5,0 Go, caches 2,1 Go, .local 1,4 Go. Une bonne partie se récupère sans toucher à tes environnements.
Voir le détail d'abord
du -h --max-depth=1 ~/.cache | sort -h                 # quels caches
du -h --max-depth=3 ~/.local 2>/dev/null | sort -h | tail -10
du -sh ~/miniconda3/pkgs ~/miniconda3/envs/*          # cache conda vs environnements
conda env list                                        # environnements conda existants
Le cache pip : sans risque
pip cache info      # taille du cache
pip cache purge     # le vider
pip garde chaque paquet téléchargé dans ~/.cache/pip. Le vider ne désinstalle rien : pip retéléchargera seulement si tu réinstalles.
Le cache conda : sans risque
conda clean --all --dry-run    # voir ce qui partirait, sans rien supprimer
conda clean --all              # vider
Il vide ~/miniconda3/pkgs, qui contient les archives des paquets déjà installés et les versions devenues inutiles. Tes environnements base et mlopszoomcamp restent intacts.
Les environnements pipenv : à choisir un par un
Chaque dossier où tu as lancé pipenv install possède son propre virtualenv, rangé dans ~/.local/share/virtualenvs/. Le cours en crée plusieurs (un par variante de web service).
ls ~/.local/share/virtualenvs/          # lister
cd 04-deployment/web-service            # aller dans le projet concerné
pipenv --venv                           # afficher le chemin de son virtualenv
pipenv --rm                             # le supprimer proprement
Le Pipfile et le Pipfile.lock restent dans ton projet : pipenv install recrée l'environnement à l'identique. Le cache pipenv, lui, se vide sans risque :
rm -rf ~/.cache/pipenv
Un environnement conda entier : seulement si tu n'en as plus besoin
conda env remove -n <nom>
Ne supprime jamais base, ni mlopszoomcamp tant que le cours continue.
Les runs MLflow : avec l'outil MLflow
Chaque mlflow.log_model sauvegarde un modèle complet dans l'artifact store. Avec hyperopt qui lance 50 essais, les modèles s'additionnent.
1. Supprime les runs inutiles depuis l'interface MLflow : ils passent à l'état « deleted » mais restent sur le disque.
2. Purge-les physiquement :
mlflow gc --backend-store-uri sqlite:////workspaces/mlops-zoomcamp/02-experiment-tracking/mlflow.db
Adapte le chemin à ta base, avec quatre slashes pour un chemin absolu. mlflow gc supprime à la fois les métadonnées et les artefacts, en gardant mlflow.db cohérent.
Les logs Airflow : sans risque
du -sh logs/                 # dans ton dossier Airflow
rm -rf logs/*                # vider le contenu, garder le dossier
Airflow écrit un fichier de log par exécution de tâche : le dossier grossit en continu. Garde le dossier lui-même, car Docker Compose le monte dans les conteneurs.
Partie 6 — Bonnes pratiques au build
Un bon build produit une image petite, réutilise au maximum le cache, et ne laisse pas d'orphelins derrière lui. Six pratiques suffisent.
Pratique 1 — Ordonner le Dockerfile du plus stable au plus changeant
Docker reconstruit tout ce qui suit la première ligne modifiée. Place donc les dépendances (qui changent rarement) avant ton code (qui change souvent).
FROM python:3.10-slim

# 1. Outils : ne change presque jamais
RUN pip install --no-cache-dir -U pip pipenv

WORKDIR /app

# 2. Dépendances : change quand tu modifies le Pipfile
COPY ["Pipfile", "Pipfile.lock", "./"]
RUN pipenv install --system --deploy && rm -rf /root/.cache

# 3. Code et modèle : change à chaque correction
COPY ["predict.py", "lin_reg.bin", "./"]

EXPOSE 9696
ENTRYPOINT ["gunicorn", "--bind=0.0.0.0:9696", "predict:app"]
Avec cet ordre, corriger une ligne de predict.py ne reconstruit que la dernière couche, de quelques Ko. Si tu copiais tout le dossier avant pipenv install, chaque correction réinstallerait toutes les dépendances : 400 Mo de nouvelle couche à chaque fois.
Pratique 2 — Ajouter un .dockerignore
Le .dockerignore fonctionne comme un .gitignore : il exclut des fichiers du contexte envoyé à Docker. Crée-le à côté du Dockerfile :
.git
__pycache__/
*.pyc
.ipynb_checkpoints/
mlruns/
mlflow.db
data/
*.parquet
.venv/
Deux bénéfices : le build démarre plus vite, et un COPY . . n'embarque pas par erreur tes données ou tes runs MLflow dans l'image.
Pratique 3 — Partir d'une image de base légère
Image de base
Taille approximative
Usage
python:3.10
~1 Go
Rarement nécessaire
python:3.10-slim
~150 Mo
Le bon choix par défaut, celui du cours
python:3.10-alpine
~50 Mo
Piège pour le ML : numpy et scikit-learn s'y compilent mal
Garde la même image de base pour tous tes services : sa couche n'est stockée qu'une fois et partagée.
Pratique 4 — Ne pas laisser de caches dans l'image
• pip install --no-cache-dir ... : pip ne garde pas les archives téléchargées.
• && rm -rf /root/.cache dans le même RUN : supprimer dans un RUN suivant ne réduit rien, car la couche précédente contient déjà les fichiers.
• Pour les paquets système : RUN apt-get update && apt-get install -y <paquet> && rm -rf /var/lib/apt/lists/*.
C'est la règle d'or des couches : ce qu'une couche a écrit reste dans l'image, même si une couche suivante l'efface.
Pratique 5 — Choisir une stratégie d'étiquettes
Stratégie
Commande
Avantage
Inconvénient
Réutiliser la même étiquette
docker build -t ride-duration:dev .
Une seule image nommée
Crée un orphelin à chaque rebuild
Versionner
docker build -t ride-duration:v2 .
Retour arrière possible
Les anciennes versions s'accumulent
Pendant le débogage, réutilise une étiquette dev et nettoie les orphelins. Quand une version marche, étiquette-la (docker tag ride-duration:dev ride-duration:v1) et supprime les versions obsolètes avec docker rmi.
Pratique 6 — Nettoyer après une série de builds
docker image prune       # les orphelins créés par les rebuilds
docker builder prune     # le cache devenu inutile
Fais-le à la fin de chaque session de débogage, pas une fois que le disque est plein.
Bonus — Inspecter une image
docker history ride-duration:v1     # taille de chaque couche, instruction par instruction
Si une couche pèse anormalement lourd, tu sais quelle ligne du Dockerfile optimiser.
Partie 7 — Build une fois, run ensuite
Une image construite reste sur le disque du Codespace : tu peux quitter, revenir le lendemain et simplement la relancer, sans rebuild. On ne rebuilde que lorsque ce qui est dans l'image change.
Ce qui survit quand tu quittes le Codespace
Événement
Images
Conteneurs
Volumes
Processus (mlflow ui, serveurs)
Fermer VS Code, Codespace arrêté (manuellement ou par inactivité)
Gardées
Arrêtés, gardés
Gardés
Arrêtés
Rouvrir le Codespace
Présentes
À relancer
Présents
À relancer
« Rebuild container » du Codespace
Peuvent disparaître
Perdus
Peuvent disparaître
Arrêtés
Codespace supprimé (manuellement ou après la période de rétention d'inactivité)
Perdues
Perdus
Perdus
—
Seul le code poussé sur GitHub survit à tout. Pense à git push régulièrement : le Dockerfile, le Pipfile et le Pipfile.lock suffisent à tout reconstruire.
Quand faut-il rebuilder ?
Tu as modifié...
Rebuild ?
predict.py ou un autre fichier copié par COPY
Oui
Le modèle .bin copié dans l'image
Oui
Le Pipfile ou le Pipfile.lock
Oui
Le Dockerfile
Oui
Rien, tu reprends simplement ton travail
Non : juste run
Un fichier monté avec -v (volume)
Non
Une variable passée avec -e
Non
flowchart TD
    A[J'ouvre le Codespace] --> B{Mon image existe ?<br/>docker images}
    B -- Oui --> C{Ai-je modifié le code,<br/>le Pipfile ou le Dockerfile ?}
    B -- Non --> D[docker build]
    C -- Non --> E[docker run]
    C -- Oui --> D
    D --> F[docker image prune]
    F --> E
Reprendre un service simple (web service Flask/Gunicorn)
Étape 1, vérifier que l'image est là :
docker images
Étape 2, la lancer. Deux façons de travailler, choisis-en une et tiens-t'y.
Façon A — conteneur jetable (recommandée) : un nouveau conteneur à chaque run, effacé à l'arrêt.
docker run -it --rm -p 9696:9696 ride-duration-prediction-service:v1
# Ctrl+C pour arrêter : le conteneur disparaît tout seul
Façon B — conteneur nommé et réutilisé : créé une fois, redémarré ensuite.
# Première fois seulement : création en arrière-plan (-d = detached)
docker run -d --name ride-duration -p 9696:9696 ride-duration-prediction-service:v1

# Les fois suivantes
docker start ride-duration      # redémarrer
docker logs -f ride-duration    # suivre les logs (Ctrl+C quitte l'affichage, pas le conteneur)
docker stop ride-duration       # arrêter
Piège de la façon B : relancer docker run --name ride-duration ... échoue avec une erreur « name already in use ». Le conteneur existe déjà : utilise docker start.
Option
Rôle
-it
Mode interactif, logs affichés, Ctrl+C fonctionne
--rm
Supprimer le conteneur à l'arrêt
-d
Lancer en arrière-plan
--name
Donner un nom fixe au conteneur
-p 9696:9696
Relier le port du Codespace (gauche) au port du conteneur (droite)
Étape 3, tester avec ton script habituel (python test.py) ou curl.
Reprendre la variante web-service-mlflow
Ce conteneur dépend d'un service extérieur : le serveur MLflow, qui est un processus du Codespace et non un conteneur. Il est arrêté à chaque redémarrage.
1. Relance d'abord le serveur MLflow avec ta commande habituelle (liaison sur 0.0.0.0 et --allowed-hosts, comme lors du débogage).
2. Vérifie qu'il répond, via l'icône globe de l'onglet PORTS.
3. Lance ensuite le conteneur avec le même docker run qu'avant, montage :ro compris.
L'ordre compte : un conteneur lancé avant MLflow échoue au chargement du modèle.
Reprendre un projet Docker Compose (Airflow)
cd <ton dossier airflow>
docker compose up -d        # démarrer (recrée ce qui manque, réutilise les images)
docker compose ps           # vérifier l'état des services
docker compose logs -f      # suivre les logs
Pour quitter proprement :
docker compose stop         # arrêter, tout garder, redémarrage rapide avec docker compose start
docker compose down         # supprimer conteneurs et réseaux, garder volumes et images
Piège Airflow : si ton docker-compose.yaml contient restart: always, les conteneurs arrêtés avec stop redémarrent tout seuls quand Docker redémarre, donc à la réouverture du Codespace. Sur 8 Go de RAM, ça peut ralentir tout le reste. Préfère docker compose down avant de quitter si tu ne comptes pas utiliser Airflow à la prochaine session.
Le petit rituel de fin de session
docker ps                       # qu'est-ce qui tourne encore ?
docker compose down             # dans le dossier Airflow, si lancé
docker image prune              # orphelins de la session
git add . && git commit -m "..." && git push
Partie 8 — Niveau expert : aller plus loin
Ces techniques sont celles des équipes MLOps en production. Tu n'en as pas besoin pour le cours, mais elles répondent aux limites que tu as rencontrées.
Monter le code au lieu de rebuilder
Pendant le développement, monte ton fichier dans le conteneur avec un bind mount : une modification de predict.py est visible sans rebuild.
docker run -it --rm -p 9696:9696 \
  -v "$(pwd)/predict.py:/app/predict.py:ro" \
  ride-duration-prediction-service:v1
Redémarre le conteneur pour que Gunicorn relise le fichier. En production, on rebuilde toujours : l'image doit contenir exactement ce qui tourne.
Le cache BuildKit monté
Une instruction RUN --mount=type=cache garde le cache pip hors de l'image, dans le cache de build. L'image reste légère et les réinstallations sont rapides.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -U pip pipenv
Contrepartie : ce cache compte dans docker builder prune. C'est normal et voulu.
Le build multi-étapes (multi-stage)
On installe les outils lourds dans une première étape, puis on ne copie que le résultat dans une image finale propre. pipenv lui-même n'est pas embarqué dans l'image finale.
FROM python:3.10-slim AS builder
RUN pip install --no-cache-dir pipenv
WORKDIR /app
COPY ["Pipfile", "Pipfile.lock", "./"]
RUN pipenv requirements > requirements.txt

FROM python:3.10-slim
WORKDIR /app
COPY --from=builder /app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY ["predict.py", "lin_reg.bin", "./"]
EXPOSE 9696
ENTRYPOINT ["gunicorn", "--bind=0.0.0.0:9696", "predict:app"]
L'étape builder reste dans le cache de build : un docker builder prune la fait partir.
Étiqueter ses images pour nettoyer finement
Un label permet de cibler ses propres images sans toucher aux autres, comme Airflow.
docker build --label project=mlops-zoomcamp -t ride-duration:dev .
docker image prune -a --filter "label=project=mlops-zoomcamp"
docker images --filter "label=project=mlops-zoomcamp"
Explorer une image couche par couche
docker history --no-trunc ride-duration:v1
docker image inspect ride-duration:v1
L'outil open source dive va plus loin : il affiche les fichiers ajoutés par chaque couche et estime l'espace gaspillé.
Faire survivre une image à la suppression du Codespace
Une image n'existe que sur le disque du Codespace. Pour la conserver, pousse-la sur un registre, par exemple GitHub Container Registry.
docker tag ride-duration:v1 ghcr.io/janua29/ride-duration:v1
docker push ghcr.io/janua29/ride-duration:v1     # après authentification à ghcr.io
docker pull ghcr.io/janua29/ride-duration:v1     # depuis n'importe quelle machine
C'est le fonctionnement réel d'un pipeline MLOps : la CI construit l'image, la pousse, et le serveur de production la tire. Tu y reviendras dans les modules sur le déploiement et la CI/CD.
Surveiller automatiquement
Une ligne dans ~/.zshrc affiche l'espace libre à chaque ouverture de terminal :
echo 'df -h / | tail -1 | awk "{print \"Disque : \" \$4 \" libres (\" \$5 \" utilisés)\"}"' >> ~/.zshrc
Partie 9 — Routine de nettoyage et antisèche
Le nettoyage complet se fait en sept étapes, du plus sûr au plus radical. Mesure avant et après.
La routine complète
# 0. Mesurer
df -h / && docker system df

# 1. Observer ce qui existe et tourne
docker ps -a && docker images

# 2. Docker, sans risque
docker container prune
docker image prune
docker builder prune -a

# 3. Python, sans risque
pip cache purge
conda clean --all
rm -rf ~/.cache/pipenv

# 4. Docker, modéré (rebuild ou pull à refaire)
docker image prune -a

# 5. Au cas par cas : virtualenvs pipenv d'exercices finis, logs Airflow
#    (dans le dossier concerné) pipenv --rm   |   rm -rf logs/*

# 6. Mesurer à nouveau
df -h / && docker system df
Jamais dans la routine : docker volume prune -a, docker compose down -v, suppression manuelle dans /var/lib/containerd.
Antisèche — Mesurer
Commande
Ce qu'elle montre
df -h
Remplissage de chaque disque
du -sh /workspaces/* 2>/dev/null | sort -h
Taille des dossiers du projet
du -h --max-depth=1 ~ 2>/dev/null | sort -h
Taille des dossiers du home
sudo du -h --max-depth=1 / 2>/dev/null | sort -h | tail -20
Les 20 plus gros dossiers système
sudo ncdu /
Exploration interactive du disque
docker system df / -v
Espace Docker, résumé / détaillé
docker history <image>
Taille de chaque couche d'une image
Antisèche — Observer Docker
Commande
Ce qu'elle montre
docker ps
Conteneurs qui tournent
docker ps -a
Tous les conteneurs
docker images
Images et étiquettes
docker images -f dangling=true
Images orphelines
docker volume ls
Volumes
docker compose ps
Services du projet Compose
Antisèche — Supprimer
Commande
Cible
Risque
docker container prune
Conteneurs arrêtés
Faible
docker image prune
Images orphelines
Nul
docker image prune -a
Images sans conteneur
Modéré
docker builder prune / -a
Cache de build orphelin / tout
Nul / faible
docker volume prune
Volumes anonymes inutilisés
Faible
docker volume prune -a
Tous les volumes inutilisés
Élevé
docker system prune / -a
Plusieurs cibles à la fois
Faible / modéré
docker rm <c> / docker rmi <i>
Un conteneur / une image précis
Selon l'objet
pip cache purge
Cache pip
Nul
conda clean --all
Cache conda
Nul
pipenv --rm
Virtualenv du dossier courant
Faible
mlflow gc --backend-store-uri <uri>
Runs MLflow déjà supprimés dans l'UI
Élevé si mal ciblé
Antisèche — Build et run
Commande
Usage
docker build -t <nom>:<tag> .
Construire une image
docker tag <nom>:dev <nom>:v1
Donner une étiquette de version
docker run -it --rm -p 9696:9696 <image>
Lancer un conteneur jetable
docker run -d --name <n> -p 9696:9696 <image>
Créer un conteneur nommé en arrière-plan
docker start / stop <n>
Redémarrer / arrêter un conteneur nommé
docker logs -f <n>
Suivre les logs
docker compose up -d
Démarrer un projet Compose
docker compose stop / start
Arrêter / relancer en gardant tout
docker compose down
Supprimer conteneurs et réseaux, garder les volumes
Les cinq réflexes
1. Mesurer avant de supprimer.
2. Supprimer avec l'outil qui a créé l'objet, jamais à la main.
3. --rm sur les conteneurs de test.
4. docker image prune après chaque série de rebuilds.
5. git push avant de quitter : le code reconstruit tout, le disque non.
Testez-vous
Réponds de tête avant de lire la réponse. Si tu bloques, la partie concernée est indiquée entre parenthèses.
1. df -h affiche / et /workspaces à 77 % tous les deux. Combien de disques pleins as-tu ?
Un seul. Les deux lignes montrent le même disque de 32 Go sous deux points de montage (partie 2).
2. ncdu montre 8,4 Go dans /var/lib/containerd et docker system df montre 10 Go d'images et de cache. Combien Docker occupe-t-il ?
Environ 8 à 10 Go, pas 18. Ce sont les mêmes octets vus de deux façons ; les couches partagées expliquent l'écart (partie 2).
3. Tu rebuildes quatre fois ride-duration:dev. Que contient docker images ?
Une image ride-duration:dev et trois images <none>:<none>, les orphelines. docker image prune les supprime sans risque (partie 1).
4. docker image prune -a ne supprime pas une vieille image que tu n'utilises plus. Pourquoi ?
Un conteneur arrêté l'utilise encore. Lance docker container prune d'abord, puis relance la commande (partie 3).
5. Quelle commande peut effacer la base de données d'Airflow ?
docker compose down -v, ou docker volume prune -a après un docker compose down. Aucune autre commande de ce cours ne touche aux volumes nommés (partie 4).
6. Tu modifies une ligne de predict.py. Le rebuild réinstalle toutes les dépendances. Qu'est-ce qui cloche ?
Le Dockerfile copie le code avant pipenv install. Copie d'abord Pipfile et Pipfile.lock, installe, puis copie le code (partie 6).
7. Un RUN rm -rf /root/.cache placé après le RUN pipenv install réduit-il l'image ?
Non. La couche précédente contient déjà le cache. Il faut le supprimer dans le même RUN, avec && (partie 6).
8. Tu rouvres ton Codespace le lendemain. Que dois-tu faire pour relancer le web service ?
Vérifier docker images, puis docker run -it --rm -p 9696:9696 <image>. Aucun rebuild si le code, le Pipfile et le Dockerfile n'ont pas changé (partie 7).
9. docker run --name ride-duration ... renvoie « name already in use ». Que faire ?
Le conteneur existe déjà : docker start ride-duration. Ou supprime-le avec docker rm ride-duration avant de relancer docker run (partie 7).
10. Comment garder une image si le Codespace est supprimé ?
La pousser sur un registre (docker push ghcr.io/...). À défaut, le Dockerfile et le Pipfile.lock poussés sur GitHub permettent de la reconstruire (partie 8).