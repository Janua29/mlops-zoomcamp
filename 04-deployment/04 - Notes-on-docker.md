# Daemon docker

## Question :

Je n'ai pas bien compris ce qu'c'est le build context. Et je ne sais pas ce qu'c'est le démon docker.
Avec ce que tu as écris, j'ai l'impression qu'il faut build l'image, forcément a partir du dossier 04-deployment/web-service, ce qui le paraît contradictoire avec la versatilité d'un conteneur docker (déploiement sur n'importe qu'elle machine).

## réponse

Tu as mis le doigt sur une vraie confusion, et elle vient du fait que **deux moments très différents** se retrouvent mélangés. Commençons par le démon, parce que le build context en découle directement.

## 1. Le démon Docker

Quand tu tapes `docker build`, tu imagines probablement qu'un seul programme fait tout le travail. En réalité, **Docker est composé de deux programmes distincts** :

| | Le client (`docker`) | Le démon (`dockerd`) |
|---|---|---|
| Rôle | Prend ta commande, la traduit en requête | Fait le vrai travail |
| Ce qu'il fait | Rien de concret | Construit les images, lance les conteneurs, gère le réseau et le stockage |
| Analogie | Le serveur qui prend ta commande au restaurant | La cuisine |

*(« Démon » est le terme Unix pour un programme qui tourne en permanence en arrière-plan, sans interface. Rien de diabolique — ça vient de « daemon », l'esprit serviteur de la mythologie grecque.)*

Ces deux programmes communiquent via une **API HTTP**. Le client envoie des requêtes, le démon répond. C'est exactement le même schéma client/serveur que ton `test.py` et ton `predict.py`.

**La conséquence décisive** : le client et le démon ne partagent pas forcément le même système de fichiers. Sur ta machine ils tournent côte à côte, donc l'illusion tient. Mais rien ne l'impose — le démon pourrait tourner sur un serveur distant, et c'est un usage courant en entreprise.

**Le démon ne peut donc pas simplement « aller lire » tes fichiers.** Il faut les lui *envoyer*.

## 2. Le build context

Voilà ce qu'est le build context : **le paquet de fichiers que le client envoie au démon pour qu'il puisse construire l'image.**

```bash
docker build -t mon-image:v1 .
                              ↑
                   « envoie-lui le contenu de ce dossier »
```

Quand tu lances cette commande, tu vois passer une ligne comme :

```
Sending build context to Docker daemon  4.096kB
```

C'est littéralement un transfert. Le client compresse le dossier, l'expédie au démon, et **le démon travaille sur sa copie**.

### Ce que ça implique concrètement

**Les `COPY` du Dockerfile lisent dans cette copie**, pas sur ton disque. Quand tu écris `COPY predict.py ./`, le démon cherche `predict.py` à la racine du contexte qu'il a reçu.

**Tu ne peux pas sortir du contexte.** Ceci échoue systématiquement :

```dockerfile
COPY ../data/model.bin ./     # ❌ erreur
```

Parce que `../data/` n'a jamais été envoyé au démon. Il n'existe pas dans sa copie. Ce n'est pas une règle arbitraire de Docker : le fichier est physiquement absent.

**C'est aussi pourquoi `.dockerignore` compte.** Si ton dossier contient 500 Mo de Parquet, ils sont transférés au démon à chaque build — même si aucun `COPY` ne les utilise. D'où des builds anormalement lents.

## 3. La contradiction que tu soulèves n'en est pas une

Tu as raison de dire que le build dépend d'un dossier précis. Mais il faut séparer **deux moments de vie** complètement distincts :

```
┌─────────────────────────── CONSTRUCTION ───────────────────────────┐
│  UNE FOIS, sur TA machine de développement                          │
│                                                                     │
│  Dossier web-service/          docker build          Image          │
│  ├── Dockerfile          ──────────────────────►   figée et         │
│  ├── Pipfile.lock         (a besoin du contexte)   autonome         │
│  ├── predict.py                                                     │
│  └── lin_reg.bin                                                    │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                          docker push (registry)
                                   │
                                   ▼
┌─────────────────────────── EXÉCUTION ──────────────────────────────┐
│  N FOIS, sur N'IMPORTE QUELLE machine                               │
│                                                                     │
│  docker pull mon-registry/ride-duration:v1                          │
│  docker run -p 9696:9696 ride-duration:v1                           │
│                                                                     │
│  ➜ Aucun besoin du dossier source. Aucun besoin du Dockerfile.     │
│    Aucun besoin de Python, de pipenv, de scikit-learn installés.   │
└─────────────────────────────────────────────────────────────────────┘
```

**Le build context est un ingrédient de la recette, pas du plat.**

Tu as besoin de farine, d'un four et de ta cuisine pour faire le pain. Une fois le pain cuit, tu peux l'emporter partout — personne n'a besoin de ta cuisine pour le manger.

L'image contient **déjà tout** : l'OS minimal, Python 3.9.7, scikit-learn 1.0.2, gunicorn, `predict.py`, `lin_reg.bin`, et la commande de démarrage. Le serveur de production ne verra jamais ton dossier `04-deployment/web-service/`. Il ne verra jamais ton `Dockerfile` non plus.

La portabilité de Docker porte sur **l'exécution**, pas sur la construction.

## 4. Et le build lui-même n'est pas si rigide

Dernière chose, pour lever le reste de l'impression de contrainte : tu n'es pas obligé d'être *dans* le dossier. Le `.` n'est qu'un raccourci pour « le dossier courant ». Tu peux passer n'importe quel chemin :

```bash
# Depuis la racine du repo, sans y entrer
cd /workspaces/mlops-zoomcamp
docker build -t ride-duration:v1 04-deployment/web-service
```

Le dernier argument est **toujours** le contexte. Et si le Dockerfile est ailleurs que dans le contexte, `-f` le précise :

```bash
docker build -t ride-duration:v1 -f docker/Dockerfile ./web-service
                                    └── où est la recette   └── quels fichiers envoyer
```

La seule vraie règle est donc : **le contexte doit contenir tous les fichiers que le Dockerfile veut copier.** Le répertoire depuis lequel tu tapes la commande, lui, n'a aucune importance.

C'est d'ailleurs pour ça qu'en CI/CD (GitHub Actions, GitLab CI), le build se fait depuis la racine du dépôt avec des chemins explicites — personne ne fait de `cd` dans un pipeline.

# commande COPY dans docker file

## Question :

La commande COPY indiqué au daemon de copier les fichiers vers l'image, ou lui dit juste de lire ces fichier depuis le context build ?

## Answer :

C'est bien une **copie**, pas une lecture.

`COPY predict.py ./` crée une nouvelle couche de l'image contenant un exemplaire du fichier. Ce fichier existe désormais **dans le système de fichiers de l'image**, à `/app/predict.py`, indépendamment de tout ce qui se passe ailleurs.

Tu peux le vérifier directement :

```bash
docker run -it --rm ride-duration-prediction-service:v1 ls -la /app
```

Le fichier est là. Et il y sera toujours sur un serveur à Singapour qui n'a jamais vu ton Codespace.

**Pourquoi c'est forcément une copie :** le build context est éphémère. Une fois le build terminé, le démon le jette. Si `COPY` n'était qu'une lecture, l'image se retrouverait avec des références vers des fichiers qui n'existent plus — elle serait inutilisable dès la fin de la construction. Or l'image doit être **autonome**, c'est tout son intérêt.

Le mot juste pour décrire la séquence complète :

```
ton disque  ──(1) envoi──►  build context  ──(2) COPY──►  couche de l'image
                            (copie temporaire         (copie permanente,
                             chez le démon)            fait partie de l'image)
```

Deux copies successives, donc. Et la seconde est celle qui compte : c'est elle qui voyage.

**Une conséquence pratique qui surprend souvent :** modifier `predict.py` sur ton disque après le build ne change **rien** à l'image. Elle est figée. Il faut reconstruire. C'est déroutant au début — tu corriges un bug, tu relances `docker run`, et l'ancien comportement persiste. Le réflexe à acquérir : **tout changement de code = rebuild**.

*(Il existe bien un mécanisme pour lire des fichiers de l'hôte en direct, les `volumes` — `docker run -v`. Mais ça se passe au `run`, pas au `build`, et ça sert typiquement à monter des données ou du code en développement pour éviter justement de reconstruire à chaque modification. Tu croiseras ça au module 5.)*

# Mettre des fichiers inutiles dans le context building ?

## Question :

A quoi ça sert d'envoyer au daemon un contexte build qui contient autre chose que les fichier que l'on va copier ensuite, via la commande COPY ?

## Answer :

Excellente question — et la réponse honnête est : **la plupart du temps, ça ne sert à rien.** C'est du gaspillage pur, et c'est exactement pour ça que `.dockerignore` existe.

Mais il y a deux raisons pour lesquelles Docker fonctionne comme ça.

## 1. Le démon ne peut pas savoir à l'avance ce dont il aura besoin

C'est la raison technique principale. Rappelle-toi l'ordre des opérations :

```
1. Le client envoie le contexte  ──►  2. Le démon lit le Dockerfile  ──►  3. Il exécute les COPY
```

Le Dockerfile est *dans* le contexte. Pour savoir quels fichiers copier, il faudrait déjà avoir lu le Dockerfile — donc avoir déjà reçu le contexte. L'œuf et la poule.

On pourrait imaginer que le client analyse le Dockerfile lui-même avant d'envoyer, pour n'expédier que le nécessaire. Mais ce serait fragile, parce que les chemins ne sont pas toujours connus statiquement :

```dockerfile
COPY *.py ./                    # un glob : quels fichiers exactement ?
COPY ${APP_DIR}/ ./             # une variable de build
```

Docker a choisi le comportement simple et prévisible : **envoyer d'abord, décider ensuite.**

## 2. Certaines instructions ont besoin de fichiers que tu n'avais pas anticipés

`COPY` n'est pas la seule instruction qui touche au contexte :

```dockerfile
RUN ./scripts/setup.sh          # un script exécuté depuis le contexte
ADD archive.tar.gz ./           # ADD décompresse automatiquement
```

Et surtout, dans les builds multi-étapes ou les Dockerfiles complexes, les fichiers utilisés dépendent de conditions. Le contexte est la *réserve* dans laquelle le démon pioche.

## La vraie réponse pratique : `.dockerignore`

Ta question sous-entend une bonne intuition, alors autant la valider : **envoyer des fichiers inutiles est un problème réel**, et Docker te donne l'outil pour le corriger.

Crée un `.dockerignore` à la racine de ton contexte (même syntaxe que `.gitignore`) :

```
__pycache__/
*.pyc
.git/
.ipynb_checkpoints/
*.ipynb
data/
*.parquet
mlruns/
README.md
```

Le client filtre **avant** l'envoi. Sur ton dossier `04-deployment/web-service/`, la ligne

```
Sending build context to Docker daemon  4.096kB
```

resterait à quelques kilo-octets au lieu de grimper à plusieurs centaines de méga-octets si tu y avais laissé traîner des Parquet.

## Pourquoi ça compte vraiment

Trois impacts concrets :

- **Vitesse.** Le transfert prend du temps, surtout si le démon est distant (CI/CD, Docker Desktop sur macOS où le démon tourne dans une VM).
- **Cache.** Docker calcule un hash du contexte. Un fichier non ignoré qui change — un `.pyc` régénéré, un checkpoint Jupyter — peut invalider le cache et déclencher un rebuild complet des dépendances. Tu perds 3 minutes pour rien.
- **Sécurité.** Si tu as un `.env` avec des credentials ou une clé AWS dans le dossier, un `COPY . .` distrait les embarque dans l'image. Et une couche d'image est **permanente** : même si tu supprimes le fichier dans une instruction suivante, il reste récupérable dans l'historique des couches. C'est une fuite de secrets classique.

Ce dernier point mérite d'être retenu : **`.dockerignore` n'est pas qu'une optimisation, c'est un garde-fou.** Sur un projet ML où le dossier contient souvent des données, des credentials cloud et des artefacts MLflow, c'est un fichier qu'on écrit dès le début.