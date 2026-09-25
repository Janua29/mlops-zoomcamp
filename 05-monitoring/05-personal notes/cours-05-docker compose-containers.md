# Module 05 — Docker Compose, cycle de vie des containers et stockage des données

> Contexte : [DataTalksClub/mlops-zoomcamp › 05-monitoring](https://github.com/DataTalksClub/mlops-zoomcamp/tree/main/05-monitoring), dans un GitHub Codespace.
> Prérequis : savoir ce qu'est une image Docker et avoir lancé au moins un `docker build` / `docker run` (module 04).
> Objectif : comprendre **ce que fait vraiment** Docker Compose, **où vivent tes fichiers**, **ce qui survit** à chaque commande, et **savoir choisir** où stocker une donnée et quoi mettre dans un container.

---

## 0. Carte du cours

Le cours monte en niveau progressivement. Chaque partie s'appuie sur la précédente.

| Niveau | Parties | Tu sauras… |
|---|---|---|
| Débutant | 1 → 4 | Lancer, arrêter, relancer un ensemble de containers sans perdre ton travail |
| Intermédiaire | 5 → 9 | Dire où vit chaque fichier et choisir le bon type de stockage |
| Avancé | 10 → 13 | Décider quoi containeriser, lire un setup mixte, éviter les pièges de production |
| Pratique | 14 → 16 | Vérifier ta compréhension, retrouver une commande, réviser |

Le fil rouge tient en une phrase, à relire à la fin :

> **Un container est jetable. Tout ce qui compte doit vivre ailleurs : dans l'image, dans un volume, ou dans un stockage externe.**

---

## 1. Docker Compose : où est le fichier de configuration ?

### 1.1 À quoi sert Docker Compose

Au module 04, tu avais **un seul** container : un `docker build`, puis un `docker run` avec toutes les options en ligne de commande. Au module 05, il y en a plusieurs (Postgres, Adminer, Grafana) qui doivent démarrer ensemble et communiquer entre eux. Écrire et retenir trois `docker run` avec leurs options devient vite ingérable.

Docker Compose résout ce problème : tu décris **tous les services** dans un fichier YAML (`docker-compose.yml`), et une seule commande les lance.

```bash
docker compose up --build
```

### 1.2 Pourquoi on ne précise pas où est le fichier

Docker Compose **cherche le fichier dans le dossier courant**, c'est-à-dire le dossier où se trouve ton terminal au moment où tu tapes la commande. Il essaie ces noms standards, dans cet ordre de préférence :

1. `compose.yaml`
2. `compose.yml`
3. `docker-compose.yaml`
4. `docker-compose.yml`

S'il n'en trouve aucun, il remonte dans les dossiers parents.

> **Analogie :** c'est le même principe que `git`. Tu ne dis jamais à `git status` où est ton dépôt : il le déduit de l'endroit où tu te trouves.

**Conséquence pratique : tu dois être dans le bon dossier.**

```bash
cd /workspaces/mlops-zoomcamp/05-monitoring
docker compose up --build
```

Si tu lances la commande depuis la racine du repo, tu obtiens une erreur du type `no configuration file provided: not found`. La commande est correcte, c'est l'endroit qui ne l'est pas : c'est un problème de **« où »**, pas de **« quoi »**.

### 1.3 Pointer vers un autre fichier : `-f`

Pour un fichier ailleurs ou avec un nom non standard :

```bash
docker compose -f chemin/vers/mon-fichier.yml up --build
```

### 1.4 Le nom de projet

Compose donne un **nom de projet** à l'ensemble de tes services. Par défaut, c'est le nom du dossier qui contient le fichier (en minuscules). Ce nom sert de préfixe partout :

| Objet | Nom généré | Exemple |
|---|---|---|
| Container | `<projet>-<service>-<numéro>` | `05-monitoring-grafana-1` |
| Volume nommé | `<projet>_<volume>` | `05-monitoring_grafana_data` |
| Réseau par défaut | `<projet>_default` | `05-monitoring_default` |

On peut le changer avec `-p mon_projet`. C'est ce préfixe qui permet à Compose de savoir quels containers lui « appartiennent » quand tu fais `stop` ou `down`.

---

## 2. De `docker run` à `docker compose up`

### 2.1 Correspondance des commandes

`docker compose up` est l'équivalent de `docker run`, mais **pour tous les services à la fois**, avec la configuration écrite dans le fichier plutôt qu'en options de la ligne de commande.

| Module 04 (un container) | Module 05 (Compose) |
|---|---|
| `docker build -t mon-image .` | `docker compose build` (ou `up --build`) |
| `docker run -p 9696:9696 -v ... -e ...` | `docker compose up`, avec `ports:`, `volumes:`, `environment:` dans le YAML |
| `docker stop <c>` | `docker compose stop` |
| `docker start <c>` | `docker compose start` |
| `docker rm <c>` | inclus dans `docker compose down` |
| `docker run --rm ...` (supprimé à l'arrêt) | équivalent de `stop` + `rm`, donc de `down` |

Exemple de traduction d'options en YAML :

```bash
docker run -p 3000:3000 -v ./config:/etc/grafana/provisioning -e GF_LOG_LEVEL=debug grafana/grafana
```

```yaml
services:
  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
    volumes:
      - ./config:/etc/grafana/provisioning
    environment:
      GF_LOG_LEVEL: debug
```

### 2.2 `--build` : quand est-ce nécessaire ?

- `docker compose up` **construit une image seulement si elle n'existe pas encore**. Sinon, il réutilise l'image existante.
- `docker compose up --build` **force la reconstruction** avant de démarrer.

Tu as besoin de `--build` quand tu as **modifié un Dockerfile ou un fichier copié dans une image** (`COPY`). Si rien n'a changé, il est inutile. En cas de doute, il ne fait pas de mal : grâce au cache, Docker ne refait que les étapes modifiées.

Pour les services qui utilisent une image toute faite (`image: grafana/grafana`, `image: postgres`), il n'y a rien à construire : `--build` ne les concerne pas.

### 2.3 Ce que `up` fait de plus que `run` : le réseau

`docker compose up` crée un **réseau commun** à tous les services du projet. Sur ce réseau, chaque service est joignable **par son nom de service**, comme un nom de domaine. Grafana peut joindre Postgres à l'adresse `db:5432` (si le service s'appelle `db`), sans connaître son adresse IP.

---

## 3. Anatomie d'un container

### 3.1 Un container, c'est deux choses

Un container n'est pas seulement un processus. C'est :

1. **Un processus** qui tourne (par exemple le serveur Grafana).
2. **Un système de fichiers en couches** :
   - les **couches de l'image**, en lecture seule, partagées par tous les containers issus de cette image ;
   - une **couche inscriptible** propre à ce container, posée par-dessus.

```
┌──────────────────────────────────────┐
│  Couche du container (lecture/écriture)│  ← propre à CE container
├──────────────────────────────────────┤
│  Couche image n°3 (lecture seule)     │
│  Couche image n°2 (lecture seule)     │  ← partagées, jamais modifiées
│  Couche image n°1 (lecture seule)     │
└──────────────────────────────────────┘
```

> **Analogie :** l'image est un livre imprimé que personne ne peut modifier. La couche inscriptible est une feuille de calque posée dessus, sur laquelle le container écrit ses annotations. Le processus voit les deux superposés, comme un seul système de fichiers.

### 3.2 Vocabulaire

- Dans la documentation Docker : **container layer** ou **writable layer**.
- À l'oral en français, on entend surtout « la couche writable » ou « la couche du container ». « Couche inscriptible » est compris, mais moins courant.

### 3.3 Niveau expert : le *copy-on-write*

Que se passe-t-il si le container modifie un fichier qui vient de l'image ? L'image est en lecture seule, donc Docker **copie d'abord le fichier dans la couche du container**, puis applique la modification sur la copie. L'original dans l'image reste intact. C'est le mécanisme de **copy-on-write** (copie à l'écriture), assuré par un pilote de stockage comme `overlay2`.

Deux conséquences :

- Plusieurs containers issus de la même image ne dupliquent pas ses fichiers : ils partagent les couches en lecture seule.
- Modifier un gros fichier de l'image est coûteux, car il est copié en entier la première fois.

---

## 4. Cycle de vie : arrêter n'est pas supprimer

### 4.1 Les étapes de la vie d'un container

```
  create ──► start ──► (tourne) ──► stop ──► (arrêté) ──► rm ──► (n'existe plus)
                ▲                               │
                └────────── start ◄─────────────┘
```

La distinction essentielle :

| Action | Processus | Mémoire vive | Couche du container |
|---|---|---|---|
| **Arrêter** (`stop`) | Arrêté | Perdue | **Conservée sur le disque** |
| **Supprimer** (`rm`, `down`) | Arrêté | Perdue | **Détruite** |

Après un arrêt, le container existe toujours. Au redémarrage, il retrouve tous ses fichiers. Après une suppression, relancer crée un **nouveau** container avec une couche vierge, posée sur la même image.

### 4.2 Les trois commandes Compose à connaître

| Commande | Containers | Couche du container | Réseau | Volumes nommés | Bind mounts |
|---|---|---|---|---|---|
| `docker compose stop` | Arrêtés | ✅ conservée | ✅ | ✅ | ✅ |
| `docker compose down` | Supprimés | ❌ détruite | ❌ supprimé | ✅ | ✅ |
| `docker compose down -v` | Supprimés | ❌ détruite | ❌ supprimé | ❌ supprimés | ✅ |

À retenir :

- `down -v` supprime les volumes **nommés déclarés dans le fichier compose** et les volumes anonymes. Il ne touche **jamais** aux bind mounts : ce sont des fichiers de ton projet, Docker ne les efface pas.
- `down` ne supprime pas les images. Pour ça, il existe `--rmi`, rarement utile.

### 4.3 Et Ctrl+C ?

Dans un terminal où `docker compose up` tourne au premier plan, **Ctrl+C fait un `stop`, pas un `down`**. Les containers sont arrêtés, pas supprimés.

Ce qui se passe en détail :

1. Compose affiche `Gracefully stopping...` et envoie à chaque container le signal **`SIGTERM`** : « arrête-toi proprement ». L'application peut finir son travail, par exemple Postgres qui termine d'écrire ses données sur le disque.
2. Si un container n'a pas fini au bout de **10 secondes** (délai par défaut, modifiable avec `-t`), Docker envoie **`SIGKILL`** et le tue de force.
3. Un **deuxième Ctrl+C** pendant l'attente force l'arrêt immédiat. Les containers restent présents, mais une application interrompue brutalement peut laisser des fichiers incohérents. Mieux vaut patienter quelques secondes.

Vérification :

```bash
docker ps      # rien : aucun container ne tourne
docker ps -a   # les containers apparaissent, statut "Exited"
```

### 4.4 Le mode détaché

```bash
docker compose up -d          # lance en arrière-plan, rend la main tout de suite
docker compose ps             # état des services du projet
docker compose logs -f grafana  # suivre les logs d'un service
```

En mode détaché, Ctrl+C n'a plus rien à arrêter. Dans `docker compose logs -f`, Ctrl+C arrête **seulement l'affichage des logs** : les containers continuent de tourner. Pour les arrêter, il faut `docker compose stop` ou `docker compose down`.

---

## 5. Les volumes : stocker en dehors du container

### 5.1 Le principe

Un **volume** est un emplacement de stockage qui **existe en dehors du container**, sur la machine hôte (ici, le Codespace), et que Docker « branche » sur un chemin précis à l'intérieur du container. Quand Grafana écrit dans `/var/lib/grafana` et qu'un volume y est monté, Grafana croit écrire chez lui, mais il écrit en réalité à l'extérieur.

> **Analogie :** une clé USB branchée sur un ordinateur. Si tu jettes l'ordinateur, la clé survit, et tu peux la brancher sur un autre.

C'est pour ça qu'un volume survit à la suppression du container : il n'en a jamais fait partie. Le cycle de vie du volume est **indépendant** de celui du container.

### 5.2 Les deux types principaux

| Type | Syntaxe dans le compose | Où sont les données | Géré par |
|---|---|---|---|
| **Bind mount** (de *to bind*, lier) | `./config/fichier.yaml:/chemin/dans/le/container` | Un chemin **que tu choisis**, en général dans ton projet | Toi |
| **Volume nommé** | `grafana_data:/var/lib/grafana` | Un dossier géré par Docker, dans sa zone de stockage | Docker |

Règle de lecture : si la partie gauche commence par `./`, `../` ou `/`, c'est un **chemin**, donc un bind mount. Si c'est un simple **nom**, c'est un volume nommé, et il doit être déclaré dans la section `volumes:` en bas du fichier.

```yaml
services:
  grafana:
    image: grafana/grafana
    volumes:
      - ./config/grafana_datasources.yaml:/etc/grafana/provisioning/datasources/datasource.yaml:ro  # bind mount
      - grafana_data:/var/lib/grafana                                                                 # volume nommé

volumes:
  grafana_data:   # déclaration du volume nommé
```

Le suffixe **`:ro`** (*read-only*) monte le fichier en lecture seule : le container ne peut pas le modifier. C'est une bonne protection quand le container n'a qu'à lire, **à condition d'être sûr qu'il n'a jamais besoin d'écrire**. Au module 04, monter le dossier d'artefacts MLflow en `:ro` avait fait planter le chargement du modèle, parce que MLflow écrivait des métadonnées au chargement.

### 5.3 Une différence subtile : initialisation vs masquage

Que se passe-t-il si l'image contient déjà des fichiers à l'endroit où l'on monte quelque chose ?

- **Volume nommé vide** : à sa première utilisation, Docker **copie** dans le volume les fichiers que l'image contenait à ce chemin. Le container démarre avec son contenu habituel.
- **Bind mount** : le dossier de l'hôte **masque** ce que l'image contenait à ce chemin. Si tu montes un dossier vide sur `/var/lib/grafana`, Grafana voit un dossier vide.

### 5.4 Niveau expert : les autres types de montage

- **Volume anonyme** : un volume sans nom (`- /var/lib/data` seul, sans partie gauche), créé par Docker avec un identifiant aléatoire. Difficile à retrouver, supprimé par `down -v`. On le rencontre surtout parce que certaines images en déclarent via l'instruction `VOLUME` du Dockerfile.
- **tmpfs** : un montage **en mémoire vive**, jamais écrit sur le disque, perdu à l'arrêt. Utile pour des données temporaires sensibles (secrets éphémères) ou pour la vitesse.

---

## 6. Diagnostiquer : où vit ce fichier ?

### 6.1 La règle

> **Si le chemin du fichier dans le container est couvert par un montage, le fichier vit dans ce montage. Sinon, il vit dans la couche du container.**

« Couvert » signifie que le chemin du fichier commence par le chemin de destination d'un montage. Si `/var/lib/grafana` est monté, alors `/var/lib/grafana/grafana.db` est dans le montage ; `/etc/grafana/grafana.ini`, non.

### 6.2 Les outils

**Lire le fichier compose**, section `volumes:` de chaque service (voir 5.2).

**Inspecter ce qui est réellement monté :**

```bash
docker inspect -f '{{json .Mounts}}' <nom_container>
```

Chaque montage indique son `Type` (`bind` ou `volume`), sa `Source` (sur l'hôte) et sa `Destination` (dans le container).

**Voir ce qui a été écrit dans la couche du container :**

```bash
docker diff <nom_container>
```

Chaque ligne commence par `A` (ajouté), `C` (modifié, *changed*) ou `D` (supprimé, *deleted*). Les fichiers écrits dans des volumes **n'apparaissent pas**, puisqu'ils ne sont pas dans la couche du container. C'est un excellent moyen de vérifier ta compréhension.

**Lister et localiser les volumes nommés :**

```bash
docker volume ls                          # tous les volumes nommés
docker volume inspect 05-monitoring_grafana_data   # le champ "Mountpoint" indique où sont les données sur l'hôte
```

Sur une installation classique, les données sont sous `/var/lib/docker/volumes/<nom>/_data`. Dans ton Codespace, le stockage interne de Docker n'est pas organisé exactement comme ça : fie-toi au `Mountpoint` renvoyé par `docker volume inspect` plutôt qu'à un chemin supposé.

---

## 7. Écrire un fichier à chaque endroit

| Emplacement | Comment écrire | Remarque |
|---|---|---|
| **Bind mount** | Modifier le fichier sur l'hôte, par exemple dans VS Code | Visible immédiatement dans le container : c'est littéralement **le même fichier** |
| **Couche du container** | L'application écrit elle-même ; ou `docker exec -it <c> bash` puis créer le fichier ; ou `docker cp monfichier <c>:/chemin/` | Pratique pour déboguer, à éviter pour tout ce qui compte |
| **Volume nommé** | Passer par un container qui le monte : `docker exec` ou `docker cp` vers le chemin monté | On ne modifie pas le dossier du volume à la main sur l'hôte |

Niveau avancé, **sauvegarder un volume nommé** grâce à un container temporaire qui monte à la fois le volume et un dossier de l'hôte :

```bash
docker run --rm \
  -v 05-monitoring_grafana_data:/data \
  -v "$(pwd)":/backup \
  alpine tar czf /backup/grafana_data.tgz -C /data .
```

Le container `alpine` (une image Linux minuscule) lit le volume dans `/data`, écrit l'archive dans `/backup`, c'est-à-dire dans ton dossier courant, puis se supprime tout seul (`--rm`). Le même principe, à l'envers, permet de restaurer ou d'injecter des fichiers dans un volume.

---

## 8. Choisir où stocker une donnée

### 8.1 La question centrale

> **Qui écrit le fichier, et qui doit le lire ?**

- **Un humain écrit le fichier**, le container se contente de le lire ; tu veux le modifier dans VS Code et le versionner dans git → **bind mount**.
- **L'application écrit le fichier**, personne n'y touche à la main, mais il doit survivre à la suppression du container → **volume nommé**.
- **Le fichier est jetable**, sa perte ne gêne personne → **couche du container**.
- **Le fichier fait partie de l'application** et ne change pas pendant qu'elle tourne → **l'image**, via `COPY` dans le Dockerfile.

### 8.2 Les quatre options

| Option | Pour quoi | Avantages | Inconvénients |
|---|---|---|---|
| **Image** (`COPY`) | Code et modèle en production, dépendances | Figé, versionné, reproductible : la même image donne partout le même résultat | Chaque modification demande un rebuild |
| **Bind mount** | Configuration, code en développement, notebooks, rapports à consulter | Modification instantanée depuis l'hôte, versionnable dans git | Dépend de la structure de dossiers de l'hôte ; le container peut modifier ou abîmer tes fichiers ; problèmes de permissions possibles |
| **Volume nommé** | Données produites par l'application : fichiers d'une base Postgres, base interne de Grafana | Géré par Docker, indépendant des chemins de l'hôte, performant, initialisé avec le contenu de l'image | Peu pratique à consulter ou éditer, pas dans git |
| **Couche du container** | Fichiers temporaires, caches | Rien à configurer | Tout disparaît au `down` |

### 8.3 L'arbre de décision

```
Le fichier fait partie de l'application et ne change pas pendant qu'elle tourne ?
  └─ oui → dans l'image (COPY dans le Dockerfile)
  └─ non ↓

C'est un humain qui l'écrit / le modifie, et il faut le versionner ?
  └─ oui → bind mount
  └─ non ↓

C'est l'application qui l'écrit, et il doit survivre à un "down" ?
  └─ oui → volume nommé
  └─ non → couche du container (rien à faire)
```

### 8.4 Le même fichier peut changer de catégorie

Le choix dépend du **contexte**, pas seulement du fichier. Ton code Python :

- **en développement** → souvent en **bind mount** : tu le modifies et tu testes sans rebuild ;
- **en production** → dans l'**image** : on veut quelque chose de figé et traçable.

### 8.5 La règle d'or : un container doit être jetable

Tu dois pouvoir faire `docker compose down` puis `up` **à tout moment, sans rien perdre d'important**. Si ce n'est pas le cas, une donnée précieuse vit dans la couche du container, là où elle n'a rien à faire.

Corollaire : **n'installe jamais rien avec `docker exec` en espérant que ça reste.** Un `pip install` dans un container en marche atterrit dans la couche du container : il disparaît au prochain `down`, et personne ne peut reproduire ton environnement. Tout ce qui doit être installé va dans le **Dockerfile**.

---

## 9. Cas pratique : le cycle de vie d'un modèle

Un script entraîne un modèle dans un container et sauvegarde `model.bin`. Tu veux l'examiner dans VS Code, puis le mettre en production dans un autre container.

**Pendant l'entraînement → bind mount.** Le script écrit dans un dossier de ton projet monté dans le container ; tu retrouves le fichier immédiatement sur l'hôte.

**En production → dans l'image** (et non dans un volume nommé) :

```dockerfile
COPY predict.py model.bin ./
```

Pourquoi l'image ?

1. **Reproductibilité.** L'image contient le code **et** le modèle qui vont ensemble. Le tag `duration-prediction:v3` désigne une version précise du service complet.
2. **Retour en arrière.** Si la v4 se comporte mal, tu relances la v3. Avec un volume nommé, l'ancien modèle aurait été écrasé.
3. **Pas d'étape cachée.** Un volume nommé est vide à sa création. Il faudrait une manipulation manuelle, écrite nulle part, pour y déposer le modèle.

Le volume nommé sert aux données que **le service produit**. Le modèle est produit par l'entraînement, pas par le service qui prédit.

**Alternative pour les modèles lourds ou changeant souvent** : ni image, ni volume, mais un **chargement au démarrage depuis un stockage central**, comme un model registry (MLflow, avec une URI `models:/...`) ou un stockage objet (S3). On évite un rebuild à chaque nouveau modèle tout en gardant la traçabilité : le service charge un modèle identifié par un nom et une version.

| Étape | Où mettre `model.bin` | Pourquoi |
|---|---|---|
| Entraînement | Bind mount | Récupérer le fichier sur l'hôte |
| Production (cas simple) | Image (`COPY`) | Figé, versionné avec le code, reproductible |
| Production (modèle lourd ou fréquemment mis à jour) | Model registry / stockage objet | Traçabilité sans rebuild |

---

## 10. Quoi mettre dans un container ?

### 10.1 Bibliothèque vs service

La distinction de départ :

- Un **service** est un programme qui tourne en continu et attend des requêtes, en général sur un **port**. Grafana (3000), Postgres (5432), Adminer (8080), le serveur MLflow (5000), l'interface Evidently (8000), ton API Flask (9696) sont des services.
- Une **bibliothèque** est du code que tu **importes** dans ton propre programme. Elle ne tourne pas seule : elle s'exécute à l'intérieur de ton script ou de ton notebook.

On ne met pas une bibliothèque dans son propre container. Elle s'installe **dans l'environnement du code qui l'utilise** : ton environnement conda en développement, ou l'image du service qui l'importe.

### 10.2 Les exemples du cours

**Evidently** est utilisé principalement **comme bibliothèque** : `from evidently.report import Report` dans le notebook ou le script. Rien à containeriser. Seule son interface web (`evidently ui`) est un service ; dans le cours, on la lance directement dans le terminal, car elle est facultative et Evidently est déjà installé dans l'environnement.

**Grafana et Postgres** ne sont **pas des paquets Python**. Les installer directement sur la machine demanderait le gestionnaire de paquets du système, des dépendances système, des fichiers de configuration, des services système. Avec Docker, une ligne suffit (`image: grafana/grafana`) : l'image officielle contient tout, et rien ne traîne sur ta machine après un `down`.

**MLflow** est un paquet Python déjà présent dans ton environnement `mlopszoomcamp`. Seul, en développement, `mlflow ui` dans un terminal est le plus simple. Pourtant, au module 03, MLflow **était** dans un container, au sein du Compose d'Airflow : là-bas, il devait tourner avec une dizaine d'autres services et communiquer avec eux sur le même réseau. **Même outil, choix différent : c'est le contexte qui décide.**

### 10.3 Les critères

| Critère | Plutôt container | Plutôt directement sur la machine |
|---|---|---|
| **Nature** | Service (tourne en continu, écoute sur un port) | Bibliothèque importée dans ton code |
| **Installation** | Logiciel non Python, dépendances système | Simple `pip install` dans ton environnement |
| **Interaction** | Doit communiquer avec d'autres services sur un réseau commun | Utilisé seul, en local |
| **Partage** | D'autres personnes doivent reproduire exactement ton setup | Tu es seul à t'en servir |
| **Contexte** | Production, livrable | Développement, exploration |
| **Versions** | Version précise imposée, ou plusieurs versions côte à côte | Une seule version suffit |

La tendance générale : **en production, presque tout tourne dans des containers** (ou dans des services gérés par un fournisseur cloud). **En développement, on est pragmatique** : on containerise ce qui est pénible à installer ou qui doit interagir avec d'autres services, on garde en local ce qui est déjà dans l'environnement.

### 10.4 Le coût d'un container

Containeriser n'est pas gratuit, et c'est pour ça qu'on ne le fait pas systématiquement :

- gérer les **ports** publiés ;
- gérer les **volumes** pour ne pas perdre de données ;
- gérer le **réseau** : `localhost` ne désigne plus la même machine selon qu'on est dedans ou dehors (voir 12.4) ;
- attendre les **builds** ;
- un **débogage** moins direct (logs, `exec`, fichiers invisibles depuis l'hôte).

---

## 11. Codespaces : reprendre son travail

### 11.1 Ce qui survit à l'arrêt du Codespace

Un Codespace s'arrête quand tu le fermes ou après une période d'inactivité (30 minutes par défaut). Pour Docker, c'est comme un `stop` généralisé :

| Élément | Après arrêt puis redémarrage du Codespace |
|---|---|
| Fichiers de ton projet (`/workspaces/...`), donc les bind mounts | ✅ Conservés |
| Images Docker | ✅ Conservées |
| Containers (et leur couche) | ✅ Conservés, mais **arrêtés** |
| Volumes nommés | ✅ Conservés |
| Processus en cours, mémoire vive | ❌ Perdus |

**Attention :** un *Rebuild Container* du Codespace, ou sa suppression, est bien plus radical. Les images, containers et volumes Docker risquent alors de disparaître, et le `--build` redevient nécessaire. Seuls les fichiers de ton repo poussés sur GitHub sont réellement à l'abri.

### 11.2 La routine de reprise

```bash
cd /workspaces/mlops-zoomcamp/05-monitoring   # 1. le bon dossier (partie 1)
conda activate py11-taximonitoring            # 2. le bon environnement pour les scripts Python
docker compose up -d                          # 3. relancer les services (sans --build si rien n'a changé)
docker compose ps                             # 4. vérifier qu'ils tournent
```

Puis ouvrir Grafana via l'onglet **PORTS** de VS Code (port 3000), et non via une URL tapée à la main.

### 11.3 Niveau avancé : les politiques de redémarrage

Un service peut déclarer une politique `restart:` dans le compose :

| Politique | Comportement |
|---|---|
| `no` (défaut) | Ne redémarre jamais automatiquement |
| `always` | Redémarre s'il s'arrête, **et** au redémarrage du démon Docker |
| `unless-stopped` | Comme `always`, sauf si tu l'as arrêté manuellement |
| `on-failure` | Redémarre seulement s'il plante (code de sortie non nul) |

Si certains services de ton compose ont `restart: always`, il est possible qu'ils redémarrent **tout seuls** quand le Codespace se rallume, avant même que tu tapes `up`. Vérifie dans ton fichier, et avec `docker ps`.

---

## 12. Relire le module 05 avec ces outils

### 12.1 Pourquoi l'instructrice fait `docker compose down` en 5.3

Dans la vidéo *5.3 – Prepare reference and model*, après avoir vérifié que `docker compose up --build` fonctionne, elle fait `docker compose down` avant de créer les dossiers `models/`, `data/` et le notebook. L'explication la plus probable :

- l'étape suivante (préparer les données, entraîner le modèle dans un notebook) **n'a pas besoin des services** : le notebook tourne sur l'hôte, pas dans un container. Couper les services libère mémoire et CPU, ce qui compte sur un Codespace modeste ;
- ce `down` est **sans risque** : rien d'important ne vit dans les containers à ce stade. La configuration de Grafana est dans des fichiers en bind mount, et `models/`, `data/` et le notebook sont de simples fichiers du projet sur l'hôte, sans rapport avec les containers.

C'est la règle d'or appliquée : des containers jetables, qu'on détruit sans y penser.

### 12.2 Ce qui est où dans le module

| Élément | Emplacement adapté | Raisonnement |
|---|---|---|
| Configuration des datasources Grafana (`config/`) | Bind mount | Écrite par toi, versionnée, lue par Grafana au démarrage |
| Dashboards créés à la main dans l'interface Grafana | Par défaut : couche du container → **perdus au `down`** | À exporter en JSON et fournir via bind mount, ou à protéger avec un volume nommé |
| Données de Postgres (métriques calculées par Evidently) | Volume nommé sur `/var/lib/postgresql/data` | Écrites par l'application, doivent survivre. Sans volume déclaré, elles disparaissent à chaque `down` : acceptable pour un exercice, pas en production |
| `models/lin_reg.bin`, `data/reference.parquet`, notebook | Fichiers du projet sur l'hôte | Produits par le notebook qui tourne sur l'hôte |

### 12.3 Les dashboards Grafana « as code »

Pour les dashboards, la solution la plus propre n'est pas le volume nommé, mais **l'export en JSON** : le dashboard devient un fichier du projet, versionné dans git, fourni à Grafana par bind mount au démarrage (c'est le mécanisme de *provisioning* de Grafana). N'importe qui peut alors recréer le dashboard à l'identique. C'est l'idée d'**infrastructure as code** : la configuration de ton système est décrite dans des fichiers, pas cliquée dans une interface.

### 12.4 Un setup mixte, et le sens de `localhost`

Le module 05 mélange les deux mondes, et ça fonctionne très bien :

```
┌──────────────── Hôte (Codespace) ─────────────────────────────┐
│                                                               │
│  Script Python + Evidently (env conda)                        │
│        │  écrit sur localhost:5432                            │
│        ▼                                                      │
│  ═══ port publié "5432:5432" ═══                              │
│        │                                                      │
│  ┌─────┼──────── Réseau Compose ───────────────────────┐      │
│  │     ▼                                               │      │
│  │  [ db : Postgres ] ◄──── db:5432 ──── [ grafana ]   │      │
│  │                                        port 3000 ───┼──► onglet PORTS
│  └─────────────────────────────────────────────────────┘      │
└───────────────────────────────────────────────────────────────┘
```

- Ton **script sur l'hôte** joint Postgres à `localhost:5432`, grâce au **port publié** : pour lui, Postgres est comme installé sur la machine.
- **Grafana, dans son container**, joint Postgres à `db:5432`, grâce au **réseau Compose** et au nom de service.
- Dans un container, **`localhost` désigne le container lui-même**, pas l'hôte. Si Grafana cherchait Postgres sur `localhost:5432`, il chercherait dans son propre container, et échouerait.

> **Piège classique :** une datasource Grafana configurée avec `localhost` au lieu du nom de service. Le symptôme : « connection refused », alors que Postgres tourne parfaitement.

---

## 13. Pour aller plus loin

**Permissions des bind mounts.** Un processus dans un container tourne avec un identifiant d'utilisateur (UID). L'image Grafana, par exemple, utilise un utilisateur dédié, pas `root`. Si ce processus doit **écrire** dans un dossier en bind mount qui appartient à ton utilisateur sur l'hôte, il peut recevoir un `permission denied`. Solutions : ajuster les droits du dossier, préciser `user:` dans le compose, ou utiliser un volume nommé (initialisé avec les bons droits par l'image).

**Espace disque.** Les images, containers arrêtés, volumes et surtout le **cache de build** s'accumulent au fil des itérations.

```bash
docker system df            # ce qui occupe de la place
docker builder prune        # vider le cache de build
docker system prune         # containers arrêtés, réseaux inutilisés, images orphelines
docker volume prune         # volumes non utilisés — attention, données définitives perdues
```

Toujours passer par ces commandes, **jamais** supprimer à la main les dossiers internes de Docker.

**Production.** En production, on ne compte ni sur la couche du container, ni souvent sur les volumes locaux : les bases de données sont des services gérés ou ont un stockage répliqué, les modèles viennent d'un registry, les logs partent vers un système centralisé (le container écrit sur sa sortie standard). Le container devient alors **totalement** jetable : on peut en lancer dix, en détruire cinq, sans rien perdre.

---

## 14. Erreurs de raisonnement fréquentes

| Idée fausse | Correction |
|---|---|
| « Arrêter un container efface ses fichiers » | Non : **arrêter** conserve la couche du container. C'est **supprimer** (`down`, `rm`) qui l'efface. |
| « Ctrl+C fait un `down` » | Non : Ctrl+C fait un **`stop`**. Les containers restent, statut `Exited`. |
| « `down -v` supprime aussi mes fichiers de config » | Non : `-v` supprime les **volumes nommés** (et anonymes), jamais les bind mounts. |
| « Il faut toujours `--build` » | Seulement si un Dockerfile ou un fichier copié dans l'image a changé. |
| « En production, le modèle va dans un volume nommé » | Par défaut, il va dans **l'image** (`COPY`), ou vient d'un model registry. |
| « Evidently doit être dans un container comme Grafana » | Evidently est surtout une **bibliothèque** : il s'installe dans l'environnement du code qui l'importe. |
| « `localhost` dans un container, c'est ma machine » | Non : c'est **le container lui-même**. Entre services, on utilise le **nom de service**. |
| « Un `pip install` via `docker exec` suffit » | Il disparaît au prochain `down`. Les installations vont dans le **Dockerfile**. |

---

## 15. Exercices et corrigés

**Exercice 1.** Tu tapes `docker compose up` depuis `/workspaces/mlops-zoomcamp` et tu obtiens `no configuration file provided`. Pourquoi, et comment corriger de deux façons ?

<details><summary>Corrigé</summary>

Compose cherche le fichier dans le dossier courant (et ses parents), or il est dans `05-monitoring/`. Correction 1 : `cd 05-monitoring` puis relancer. Correction 2 : `docker compose -f 05-monitoring/docker-compose.yml up`. C'est un problème de « où », pas de « quoi ».
</details>

**Exercice 2.** Tu crées un dashboard à la main dans l'interface Grafana, sans aucun volume sur `/var/lib/grafana`. (a) Tu éteins le Codespace, tu le rallumes, tu fais `docker compose up`. Le dashboard est-il là ? (b) Et si tu avais fait `docker compose down` avant d'éteindre ?

<details><summary>Corrigé</summary>

(a) Oui : l'arrêt du Codespace arrête le container sans le supprimer, sa couche est conservée, et `up` le redémarre. (b) Non : `down` supprime le container et sa couche, où vivait le dashboard. `up` crée un container neuf, sans le dashboard.
</details>

**Exercice 3.** Dans un compose, un service contient `- ./dashboards:/opt/grafana/dashboards` et `- pgdata:/var/lib/postgresql/data`. Identifie le type de chaque montage. Lequel survit à `docker compose down -v` ?

<details><summary>Corrigé</summary>

`./dashboards` commence par `./` → bind mount. `pgdata` est un simple nom → volume nommé. Après `down -v`, le bind mount survit (ce sont des fichiers de ton projet), le volume nommé est supprimé.
</details>

**Exercice 4.** Tu lances `docker diff` sur le container Grafana et tu vois `A /var/lib/grafana/grafana.db`. Qu'en conclus-tu ?

<details><summary>Corrigé</summary>

`docker diff` ne montre que la couche du container. Si le fichier y apparaît, c'est qu'**aucun volume n'est monté sur `/var/lib/grafana`** : la base interne de Grafana (dashboards, utilisateurs) disparaîtra au prochain `down`.
</details>

**Exercice 5.** Un script entraîne un modèle dans un container et sauvegarde `model.bin`. Tu veux l'examiner dans VS Code puis le déployer. Où le sauvegarder pendant l'entraînement, et comment le livrer en production ?

<details><summary>Corrigé</summary>

Pendant l'entraînement : **bind mount**, pour le retrouver sur l'hôte. En production : **dans l'image** via `COPY`, pour un service figé, versionné et reproductible, avec retour en arrière facile. Pour un modèle très lourd ou souvent mis à jour : chargement depuis un **model registry** ou un stockage objet. Un volume nommé n'est pas le bon choix par défaut (pas de traçabilité, étape manuelle cachée).
</details>

**Exercice 6.** Tu fais Ctrl+C dans le terminal où tourne `docker compose up`, puis `docker ps -a`. Que vois-tu ? Qu'aurait changé un second Ctrl+C immédiat ?

<details><summary>Corrigé</summary>

Les containers apparaissent avec le statut `Exited` : Ctrl+C a fait un `stop`. Un second Ctrl+C aurait forcé l'arrêt sans attendre la fin propre (`SIGKILL` au lieu d'attendre la réponse au `SIGTERM`). Les containers existeraient toujours, mais une application comme Postgres pourrait avoir laissé des fichiers incohérents.
</details>

**Exercice 7.** Au module 04, ton service Flask qui chargeait le modèle et renvoyait des prédictions était dans un container. Est-ce une bibliothèque ou un service ? Pourquoi le containeriser, alors que Flask est un simple paquet Python, comme MLflow qu'on lance directement dans le terminal ?

<details><summary>Corrigé</summary>

C'est un **service** : il tourne en continu et répond à des requêtes HTTP sur un port (9696). Flask est une bibliothèque, mais **ton application** qui l'utilise est un service. On le containerise parce que c'est **le livrable destiné à la production** : il faut figer ensemble le code, le modèle et les versions exactes des dépendances, pour que le service se comporte de la même façon sur n'importe quelle machine ou plateforme cloud. MLflow, en développement, est un **outil de travail** personnel : le critère « contexte » (production vs exploration) fait la différence, pas le fait d'être un paquet Python.
</details>

**Exercice 8.** Tu configures une datasource Grafana avec l'hôte `localhost:5432`. Grafana affiche « connection refused », alors que ton script Python écrit sans problème dans Postgres via `localhost:5432`. Explique.

<details><summary>Corrigé</summary>

Le script tourne sur l'hôte : pour lui, `localhost:5432` mène au port publié de Postgres. Grafana tourne dans un container : pour lui, `localhost` est **son propre container**, où rien n'écoute sur 5432. Il faut utiliser le nom de service sur le réseau Compose, par exemple `db:5432`.
</details>

---

## 16. Aide-mémoire des commandes

```bash
# Lancer / arrêter
docker compose up                 # lance au premier plan (Ctrl+C = stop)
docker compose up -d              # lance en arrière-plan
docker compose up --build         # reconstruit les images avant de lancer
docker compose stop               # arrête sans supprimer
docker compose start              # redémarre des containers arrêtés
docker compose down               # arrête et supprime containers + réseau
docker compose down -v            # idem + volumes nommés et anonymes
docker compose -f fichier.yml up  # utilise un autre fichier compose

# Observer
docker compose ps                 # état des services du projet
docker compose logs -f <service>  # suivre les logs (Ctrl+C = arrête l'affichage seulement)
docker ps                         # containers en marche
docker ps -a                      # tous les containers, y compris arrêtés

# Diagnostiquer le stockage
docker inspect -f '{{json .Mounts}}' <container>   # montages réels
docker diff <container>                            # ce qui est dans la couche du container
docker volume ls                                   # volumes nommés
docker volume inspect <volume>                     # où sont les données (Mountpoint)

# Intervenir
docker exec -it <container> bash  # ouvrir un shell dans le container
docker cp fichier <container>:/chemin/   # copier vers le container

# Faire le ménage
docker system df                  # occupation disque
docker builder prune              # cache de build
docker system prune               # objets inutilisés
```

---

## 17. Récapitulatif

| Notion | En une phrase |
|---|---|
| Recherche du fichier compose | Dans le dossier courant (puis les parents) : il faut être au bon endroit, ou utiliser `-f`. |
| Nom de projet | Le nom du dossier par défaut ; préfixe des containers, volumes et réseau. |
| `up` vs `run` | `up` = `run` pour tous les services, configuré par le YAML, avec un réseau commun en plus. |
| `--build` | Nécessaire seulement si un Dockerfile ou un fichier copié dans l'image a changé. |
| Container | Un processus + une couche writable posée sur les couches en lecture seule de l'image. |
| Copy-on-write | Modifier un fichier de l'image le copie d'abord dans la couche du container. |
| `stop` / Ctrl+C | Arrête le processus, conserve la couche du container. |
| `down` | Supprime containers et réseau ; la couche du container est détruite, les volumes restent. |
| `down -v` | Supprime aussi les volumes nommés ; jamais les bind mounts. |
| Volume | Stockage en dehors du container, branché sur un chemin ; cycle de vie indépendant. |
| Bind mount | Un chemin de l'hôte que tu choisis ; pour ce qu'un humain écrit et versionne. |
| Volume nommé | Stockage géré par Docker ; pour ce que l'application écrit et qui doit survivre. |
| Image (`COPY`) | Pour ce qui fait partie de l'application et ne change pas : code et modèle en production. |
| Où vit un fichier ? | Couvert par un montage → dans le montage ; sinon → couche du container. |
| Règle d'or | Un container est jetable : `down` + `up` ne doit jamais rien faire perdre d'important. |
| Service vs bibliothèque | On containerise des services, pas des bibliothèques. |
| Choix de containeriser | Dépend du contexte : installation, interactions, partage, production. |
| `localhost` | Dans un container, c'est le container lui-même ; entre services, on utilise le nom de service. |