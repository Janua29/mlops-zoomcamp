# URI definition

Un **URI** (Uniform Resource Identifier) est simplement une chaîne de caractères qui identifie une ressource de façon non ambiguë. Sa forme générale :

```
schéma://hôte:port/chemin?paramètres
```

Le **schéma** (avant les `://`) dit *quel type de ressource et comment y accéder*, le reste dit *où elle se trouve*. Une URL n'est qu'un cas particulier d'URI (celui où la ressource est localisable sur un réseau).

Dans ton exemple :

```python
mlflow.set_tracking_uri("sqlite:///mlflow.db")
```

- `sqlite` → le schéma : « les données sont dans une base SQLite »
- `///mlflow.db` → le chemin du fichier

Le triple slash surprend souvent. C'est la convention SQLAlchemy : `sqlite://` + `/` + chemin. Avec un chemin relatif tu as trois slashes (`sqlite:///mlflow.db` = fichier `mlflow.db` dans le dossier courant), avec un chemin absolu tu en as quatre (`sqlite:////home/user/mlflow.db`).

Les autres tracking URIs que tu croiseras dans le cours :

| URI | Signification |
|---|---|
| `sqlite:///mlflow.db` | base SQLite locale (fichier) |
| `http://127.0.0.1:5000` | un serveur MLflow qui tourne en local |
| `http://10.0.0.5:5000` | un serveur MLflow distant (ex. sur une VM EC2) |
| `postgresql://user:pwd@host:5432/mlflow` | backend Postgres |
| `file:///home/user/mlruns` | stockage dans des fichiers locaux (le défaut si tu ne configures rien) |

Un point de vocabulaire : MLflow utilise plusieurs URIs distinctes. Le *tracking URI* pointe vers le **backend store** (paramètres, métriques, tags — les données structurées). Les artefacts (modèles, graphiques, fichiers) vont ailleurs, dans l'*artifact store*, qui a sa propre URI (`./mlruns` par défaut, ou `s3://mon-bucket/...`). C'est pour ça qu'avec SQLite tu vois quand même apparaître un dossier `mlruns/` à côté de ton `mlflow.db`.

Petite précision au passage : c'est bien **MLflow** qui enregistre les paramètres et métriques dans cette base, pas Airflow. Airflow orchestre les tâches (il déclenche ton script d'entraînement), MLflow suit les expériences. Les deux sont indépendants même s'ils sont souvent utilisés ensemble.

# URL vs URI

La distinction est surtout théorique, mais elle est utile à comprendre.

**URI** = identifiant. Il désigne une ressource de façon unique.
**URL** = localisateur. Il désigne une ressource *et* dit comment y accéder (où elle est, via quel protocole).

Toute URL est une URI. L'inverse n'est pas vrai. URL est donc un sous-ensemble de URI.

Le troisième terme du trio, rarement utilisé en pratique : **URN** (Uniform Resource Name), qui identifie sans localiser. Par exemple `urn:isbn:0-486-27557-4` identifie *Roméo et Juliette* sans dire où trouver un exemplaire. C'est un nom, pas une adresse.

```
        URI (identifiant)
       /                 \
     URL                 URN
  (où + comment)       (nom seul)
  https://exemple.fr   urn:isbn:0-486-27557-4
```

**En pratique**

Quand tu tapes `https://github.com/DataTalksClub/mlops-zoomcamp` dans ton navigateur, c'est à la fois une URI et une URL. Les deux termes sont corrects. Dans la vie de tous les jours on dit « URL » parce que 99 % des identifiants qu'on manipule sont aussi des adresses.

Le W3C a d'ailleurs plus ou moins abandonné la distinction : la spec actuelle (RFC 3986) recommande de dire « URI » pour tout, et considère « URL » comme un terme informel désignant les URIs qui sont dérefençables.

**Pourquoi MLflow dit « URI » et pas « URL »**

Parce que la valeur passée n'est pas toujours une adresse réseau. `sqlite:///mlflow.db` pointe vers un fichier local, `http://127.0.0.1:5000` vers un serveur. « URI » est le terme qui couvre les deux cas sans être faux. C'est le même raisonnement dans SQLAlchemy, JDBC, Docker, etc. — dès qu'un paramètre peut recevoir plusieurs types de backends, la doc parle d'URI.

### HTTP vs HTTPS

Non, l'inverse : `http://...` et `https://...` sont des URLs **et** des URIs. Comme URL est un sous-ensemble de URI, toute URL est automatiquement une URI. Une adresse web est le cas le plus typique de l'URL : elle localise la ressource (`github.com`) et indique le protocole pour y accéder (`https`).

La règle simple : si l'adresse permet d'aller chercher la ressource, c'est une URL. `sqlite:///mlflow.db` aussi, d'ailleurs — c'est bien un localisateur. Le mot « URI » dans MLflow n'est pas là parce que ce ne sont pas des URLs, mais parce que c'est le terme générique qui évite de se poser la question.

**Le message de sécurité, c'est autre chose**

Ça n'a rien à voir avec le vocabulaire URI/URL. Ça concerne le protocole. Deux cas distincts :

| Situation | Ce que dit le navigateur | Cause |
|---|---|---|
| `http://` sans le S | « Non sécurisé » dans la barre d'adresse | Le trafic circule en clair, sans chiffrement |
| `https://` mais avertissement rouge en plein écran | « Votre connexion n'est pas privée », `NET::ERR_CERT_...` | Le certificat pose problème : expiré, auto-signé, ou émis pour un autre domaine |

Le `s` de HTTPS = TLS. Le contenu est chiffré entre ton navigateur et le serveur, et un certificat prouve que le serveur est bien celui qu'il prétend être. Avec du HTTP simple, n'importe qui sur le réseau (ton FAI, le wifi du café) peut lire ou modifier ce qui passe. D'où l'avertissement systématique aujourd'hui.

**Dans ton cas concret**

Quand tu lances `mlflow ui` et que tu ouvres `http://127.0.0.1:5000`, tu verras peut-être « Non sécurisé ». C'est normal et sans risque : le trafic ne quitte jamais la machine, il n'y a personne entre le navigateur et le serveur pour l'intercepter.

Sur Codespaces c'est encore plus simple : quand tu lances MLflow, GitHub détecte le port et crée une URL publique temporaire du genre `https://ton-codespace-5000.app.github.dev`, en HTTPS avec un vrai certificat. Tu passes par le panneau « Ports » de VS Code pour l'ouvrir. Attention par contre au niveau de visibilité du port (`Private` par défaut, ce qui est le bon réglage — évite de le passer en `Public` sans raison).

# What is a port ?

## Le Port Forwarding dans VS Code / Codespaces

### C'est quoi un port ?

Un port c'est comme une **porte numérotée** sur une machine. Quand un programme "écoute" sur un port, il attend des connexions sur cette porte précise. Par exemple, MLflow démarre un serveur web sur le port 5000 — toute requête qui arrive sur ce port lui est transmise.

### Pourquoi le forwarding est nécessaire ?

Dans ton cas, il y a deux machines :

```
Ton Mac (navigateur) ──── Internet ──── VM Codespace (MLflow tourne ici)
```

La VM est dans le cloud de GitHub, donc `localhost:5000` sur ton Mac n'existe pas — c'est le localhost **de la VM**. VS Code crée un tunnel chiffré entre les deux, et remappe les ports :

```
Ton Mac localhost:5000  ──tunnel SSH──►  VM Codespace:5000 (MLflow)
```

C'est pour ça que ça marche en cliquant sur l'adresse dans VS Code : il sait faire ce pont automatiquement, alors que copier-coller `127.0.0.1:5000` dans ton navigateur pointait vers **ton propre Mac**, où rien n'écoute.

---

### Pourquoi autant de ports ?

Voici ce que tu vois probablement :

| Port | Correspond à |
|------|-------------|
| **5000** | **MLflow UI** — le serveur que tu viens de lancer |
| **9000–9004** | Les **workers Uvicorn** de MLflow. MLflow 3.5+ utilise un serveur FastAPI multi-processus : 1 processus parent + plusieurs workers pour gérer les requêtes en parallèle |
| **45627** | Port éphémère, probablement la connexion VS Code Desktop ↔ Codespace elle-même (SSH ou protocole interne) |

Les ports 9000–9004 expliquent d'ailleurs ce que tu voyais dans les logs au démarrage :

```
Started server process [3893]   ← worker 1
Started server process [3896]   ← worker 2
Started server process [3895]   ← worker 3
Started server process [3894]   ← worker 4
```

En pratique, **tu n'interagis qu'avec le port 5000** — c'est le point d'entrée. Les autres sont de la plomberie interne que MLflow gère tout seul.

### What is a proxy, secure proxy ?

## Le principe

Un **proxy** est un intermédiaire qui se place entre un client et un serveur. Au lieu de se parler directement, les deux passent par lui :

```
Sans proxy :   Navigateur ──────────────► Serveur

Avec proxy :   Navigateur ──► Proxy ──► Serveur
```

L'analogie du standard téléphonique d'entreprise marche bien. Tu appelles un numéro unique, une opératrice décroche, et c'est elle qui te met en relation avec la bonne personne. Ton interlocuteur ne voit pas ton numéro, il voit celui du standard. Et l'opératrice peut filtrer les appels, en refuser certains, ou noter qui a appelé.

Ce déplacement du point de vue est essentiel : **le serveur ne voit plus le client, il voit le proxy**. C'est exactement la cause de ton problème initial.

## Deux familles

On distingue les proxys selon le côté où ils se placent.

Un **forward proxy** protège le client. Il est placé devant toi, et le serveur ne sait pas qui tu es. C'est ce que fait un VPN, ou le proxy d'un réseau d'entreprise qui bloque certains sites.

Un **reverse proxy** protège le serveur. Il est placé devant lui, et c'est toi qui ne sais pas quelle machine te répond réellement. C'est le cas qui te concerne.

## Le cas de GitHub Codespaces

Quand tu ouvres un port dans un Codespace via le navigateur, GitHub met un reverse proxy devant ta VM :

```
Ton navigateur ──► xxx-5000.app.github.dev ──► ta VM:5000
                   (proxy GitHub)
```

Le qualificatif **secure** vient de ce que ce proxy ajoute par-dessus le simple relai :

- **Chiffrement HTTPS** — ta VM parle en HTTP tout simple, le proxy présente au navigateur un certificat valide et chiffre le trafic
- **Authentification** — il vérifie que tu es bien connecté au compte GitHub propriétaire du Codespace avant de laisser passer quoi que ce soit, ce qui explique la mention `Private` dans ta colonne Visibility
- **Point d'entrée unique** — ta VM n'a aucune adresse publique, elle n'est joignable qu'à travers lui

## Pourquoi MLflow râlait

Chaque requête HTTP transporte un en-tête `Host` qui indique le nom du site demandé. Sans proxy, MLflow reçoit `Host: 127.0.0.1:5000`. À travers le proxy GitHub, il reçoit `Host: xxx-5000.app.github.dev`.

Or le middleware de MLflow n'accepte par défaut que les Host de type localhost. D'où le rejet — et d'où l'utilité de `--allowed-hosts` dans ce scénario.

## Et ton setup actuel ?

VS Code Desktop n'utilise pas ce proxy. Il crée un **tunnel SSH**, ce qui est différent :

```
localhost:5001 (ton Mac) ══tunnel chiffré══ VM:5000
```

La nuance : le tunnel ne réécrit pas la requête, il la transporte telle quelle. MLflow reçoit donc bien `Host: 127.0.0.1`, comme si tout se passait en local. C'est précisément pour ça que ta commande courte fonctionne, et que les flags de sécurité sont inutiles chez toi.

# pip vs conda

`pip` est le gestionnaire de paquets de Python. C'est l'outil qui va chercher une librairie sur internet (sur PyPI, le dépôt officiel) et l'installe dans ton environnement pour que tu puisses l'`import`er dans ton code.

```bash
pip install pandas      # installe
pip list                # liste ce qui est installé
pip uninstall pandas    # désinstalle
pip install -r requirements.txt   # installe tout ce qu'un projet demande
```

L'analogie : PyPI est un magasin d'applications pour Python (environ 500 000 librairies), et pip est le bouton "Installer".

Deux choses à savoir dans ton cas :

**pip vs conda** — tu as deux gestionnaires disponibles. `conda install` et `pip install` font le même travail, mais puisent dans des dépôts différents. La convention est de privilégier conda quand le paquet existe, et pip sinon (c'est le cas de beaucoup de librairies MLOps comme `mlflow` ou `prefect`). Le cours zoomcamp utilise surtout pip, donc suis simplement les instructions du cours.

**Il y a un pip par environnement** — c'est le point qui rejoint ta question précédente. Chaque env conda a son propre `pip` et son propre dossier de librairies. Le `pip` de `mlopszoomcamp` installe dans `mlopszoomcamp`, celui de `base` installe dans `base`. D'où l'importance du `which pip` quand quelque chose ne marche pas.

# Kernel et environnement

Un **kernel** est le processus qui exécute réellement ton code quand tu utilises un notebook.

Quand tu ouvres un `.ipynb`, il y a deux choses distinctes :
- **l'interface** (VS Code ou Jupyter) : elle affiche les cellules, le texte, les graphiques
- **le kernel** : un processus Python lancé en arrière-plan, qui reçoit le code d'une cellule, l'exécute, et renvoie le résultat

C'est aussi lui qui garde en mémoire tes variables entre les cellules. D'où le comportement que tu connais déjà : redémarrer le kernel = tuer ce processus et en lancer un neuf, donc mémoire vide.

**Plusieurs kernels pour un environnement ?**

Oui, c'est possible. Un kernel est déclaré par un petit fichier `kernel.json` qui dit essentiellement : « pour me lancer, exécute tel interpréteur avec telles options ». Rien n'empêche d'enregistrer deux déclarations pointant vers le même env, sous des noms différents. C'est rare en pratique. Le vrai cas d'usage, c'est plutôt d'avoir des kernels de langages différents (Python + R) installés dans le même env conda.

**Plusieurs environnements pour un kernel ?**

Non. Un kernel pointe vers un unique chemin d'interpréteur (`.../envs/mlopszoomcamp/bin/python`). Il est donc lié à un et un seul environnement — c'est justement ce qui fait tout son intérêt.

En pratique la relation est donc : **1 env conda ↔ 1 kernel**, et c'est le modèle mental à garder.

**Le piège qui te concerne directement**

Le kernel sélectionné dans un notebook est *indépendant* de l'environnement activé dans ton terminal. Tu peux très bien avoir `(mlopszoomcamp)` affiché dans le terminal, et un notebook qui tourne sur le kernel `base` → `ModuleNotFoundError: No module named 'mlflow'` alors que tu viens de l'installer.

Le sélecteur de kernel est en haut à droite du notebook dans VS Code. Vérifie qu'il affiche bien `mlopszoomcamp`.

Et pour qu'un env apparaisse dans cette liste, il faut que le paquet `ipykernel` y soit installé :

```bash
conda activate mlopszoomcamp
pip install ipykernel
```

Deux commandes utiles pour inspecter :

```bash
jupyter kernelspec list     # liste les kernels déclarés et leurs chemins
```

Et dans une cellule du notebook, pour savoir sur quoi tu tournes vraiment :

```python
import sys
print(sys.executable)
```

# Shell, terminak et environnement

Excellente question, et c'est le bon moment pour la poser : tout ce qu'on vient de vivre en découle.

## La définition

Un **shell** est un programme qui lit ce que tu tapes, l'interprète, et lance les programmes correspondants. C'est un interpréteur de commandes. Sur ton Codespace, c'est `bash`.

Attention à ne pas le confondre avec le **terminal**, qui n'est que la fenêtre — le clavier et l'écran. Le terminal affiche, le shell comprend et agit. Même distinction qu'entre un navigateur et le site web qu'il affiche.

Le nom vient de l'image de la « coquille » : la couche par laquelle tu t'adresses au noyau du système, sans jamais lui parler directement.

## Ce qu'un shell transporte avec lui

Un shell n'est pas qu'un lecteur de commandes. C'est un **processus** vivant, qui maintient un état :

- un répertoire courant (ce que `cd` modifie)
- un ensemble de **variables d'environnement**, dont la plus importante ici : `PATH`

`PATH` est une simple liste de dossiers, séparés par `:`. Quand tu tapes `python`, le shell parcourt cette liste **de gauche à droite** et exécute le **premier** fichier `python` qu'il trouve. Il s'arrête là. Les autres, s'ils existent, sont ignorés.

Regarde la tienne :

```bash
echo $PATH | tr ':' '\n'
```

Et voilà la révélation du chapitre : **activer un environnement, ce n'est rien d'autre que mettre son dossier `bin/` en tête de cette liste**. `conda activate`, `pipenv shell`, `source venv/bin/activate` — tous font fondamentalement la même chose. Aucune magie, aucune installation. Juste une réécriture de PATH.

## Shell parent, shell enfant (cf. 04 - deployment)

Un shell peut en lancer un autre. Le nouveau est un processus **enfant**, et il reçoit une **copie** de l'environnement du parent.

Le mot « copie » est le cœur du sujet. Deux conséquences :

- ce que l'enfant modifie ne remonte jamais au parent. C'est pourquoi, en tapant `exit`, tu retrouves ton shell d'avant exactement dans l'état où tu l'avais laissé.
- l'enfant hérite du PATH du parent, mais peut le réécrire à sa guise.

Ton cas concret, étape par étape :

```
shell parent          PATH = [conda/mlopszoomcamp/bin, ...]
│                     prompt : (mlopszoomcamp)
│
└─ pipenv shell  →  shell enfant
                      1. bash démarre et relit ~/.bashrc
                      2. ~/.bashrc contient le hook conda → conda active base
                      3. pipenv ajoute le virtualenv en tête
                      prompt : (web-service) (base)
```

Les deux préfixes ne sont que l'affichage de ce double passage. Ce qui compte réellement, c'est **qui a écrit en dernier en tête de PATH**. D'où l'arbitrage par `which python`, qui te dit quel fichier sera effectivement exécuté — pas ce que le prompt prétend.

## Pourquoi `pipenv run` évite tout ça

`pipenv run python ...` ne lance pas de shell enfant. Il exécute directement le programme avec le bon PATH, sans relire `~/.bashrc`. Conda n'a donc aucune occasion de s'interposer.

C'est plus sûr, et c'est la forme que tu retrouveras dans les scripts et les Dockerfiles — où il n'y a de toute façon personne pour taper `activate`.