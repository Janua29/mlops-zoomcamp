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

# What is a proxy, secure proxy ?

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

# Adresse 127.0.0.1, ports et machines

Excellent question, et ta confusion est parfaitement légitime — c'est un des points les plus contre-intuitifs du réseau. On reprend depuis zéro.

Deux corrections de vocabulaire d'abord :
- C'est **`127.0.0.1`**, pas `127.0.0.0`. Le dernier chiffre compte.
- En français on dit **hébergé** plutôt que "hosté". Et surtout : le serveur est hébergé *sur une machine*, pas *à une adresse*. L'adresse, c'est la façon de le joindre.

---

## Étape 1 — Il y a deux machines, pas une

C'est la base de tout. Dans ton setup il existe **deux ordinateurs physiquement distincts** :

1. **Ton Mac**, posé sur ton bureau
2. **Le Codespace**, une machine virtuelle qui tourne dans un datacenter Microsoft, quelque part dans le monde

VS Code Desktop te donne l'illusion d'une seule machine, mais c'est une illusion. Ton terminal VS Code, ton Jupyter, ton serveur MLflow : **tout ça tourne sur le Codespace**. Sur ton Mac, il n'y a que deux choses : la fenêtre VS Code et ton navigateur.

## Étape 2 — L'adresse IP désigne une machine

Une adresse IP, c'est comme une adresse postale : elle identifie **une machine** sur un réseau.

`142.250.75.238` → un serveur Google
`192.168.1.14` → ton Mac sur ton réseau WiFi domestique

## Étape 3 — `127.0.0.1` est une adresse très particulière

Voilà la clé de ta deuxième incompréhension.

`127.0.0.1` (appelée *loopback* ou *localhost*) ne désigne pas une machine précise dans le monde. Elle signifie : **« moi-même, la machine qui pose la question »**.

C'est exactement comme le mot **« chez moi »**. Si tu dis « chez moi », ça désigne Roubaix. Si je le dis, ça désigne autre chose. Le mot est identique, le lieu est différent. Ce n'est pas un nom propre, c'est un **mot relatif au locuteur**.

Donc :
- Ton Mac dit `127.0.0.1` → il parle de **ton Mac**
- Le Codespace dit `127.0.0.1` → il parle du **Codespace**

**Toutes** les machines du monde ont un `127.0.0.1`, et chez chacune il pointe vers elle-même. Ce n'est donc pas « deux adresses identiques vers deux serveurs différents » : c'est **un même mot prononcé par deux locuteurs différents**.

## Étape 4 — Le port désigne un programme sur cette machine

Une machine fait tourner plusieurs serveurs en même temps. L'adresse IP amène jusqu'à la machine, mais il faut encore savoir à qui parler.

> **Adresse IP = l'immeuble. Port = le numéro d'appartement.**

Un port est un nombre entre 1 et 65535. Un programme qui veut recevoir des connexions **réserve un port** et « écoute » dessus. Un seul programme à la fois par port — d'où l'erreur si tu relances MLflow sur un port déjà pris.

Petite correction sur ta formulation : tu as écrit « les ports du serveur MLflow » et « les ports de ma machine ». En réalité **les ports appartiennent toujours à une machine**. MLflow ne possède pas le port 5000 ; il *occupe* le port 5000 **du Codespace**. Le port 5000 **de ton Mac** est un port complètement différent, sur une autre machine, occupé par AirPlay.

## Étape 5 — Qui tourne où## Étape 6 — Les deux chemins vers MLflow

![Texte](/workspaces/mlops-zoomcamp/01-intro/images/URL-ports.png)

**Chemin A — le notebook (interne, aucun tunnel)**

Jupyter tourne *sur le Codespace*, juste à côté de MLflow. Quand le notebook dit `127.0.0.1:5000`, il dit : « chez moi, porte 5000 ». Comme « chez moi » = le Codespace, il trouve MLflow immédiatement. Le trafic ne quitte jamais la machine distante.

**Chemin B — ton navigateur (externe, tunnel obligatoire)**

Ton navigateur tourne sur ton Mac. S'il disait `127.0.0.1:5000`, il chercherait « chez moi (le Mac), porte 5000 » → il tomberait sur AirPlay, pas sur MLflow.

Et il ne peut pas non plus joindre le Codespace directement : celui-ci n'a pas d'adresse publique, il est derrière un pare-feu. Il n'existe aucune route.

D'où le **tunnel** : VS Code ouvre une porte sur ton Mac (le port 5001, puisque 5000 était pris par AirPlay) et fait passer tout ce qui y arrive à travers la connexion SSH déjà établie, jusqu'au port 5000 du Codespace.

**Réponse à ta question : le tunnel pointe vers MLflow**, pas vers Jupyter. Le port 5000 distant, c'est MLflow. Jupyter a son propre tunnel, avec son propre numéro — c'est sûrement l'un des 9 ports que tu vois listés.

## Étape 7 — Le récapitulatif

| Qui parle | Ce qu'il écrit | Ce que ça veut dire | Où ça arrive |
|---|---|---|---|
| Notebook (Codespace) | `127.0.0.1:5000` | Codespace, porte 5000 | MLflow ✅ |
| Navigateur (Mac) | `127.0.0.1:5000` | Mac, porte 5000 | AirPlay ❌ |
| Navigateur (Mac) | `127.0.0.1:5001` | Mac, porte 5001 → tunnel | MLflow ✅ |

**La règle pratique :** demande-toi toujours *sur quelle machine tourne le programme qui écrit l'adresse*. Ton code Python tourne sur le Codespace → il utilise les ports du Codespace. Ton navigateur tourne sur le Mac → il utilise les ports forwardés. Tu ne touches donc pas à ton `set_tracking_uri("http://127.0.0.1:5000")`.

---

Petit bonus qui va faire le lien avec ce que tu as vu en Docker au module 04. Quand tu as lancé MLflow avec `--host 127.0.0.1`, tu lui as dit : « n'accepte que les connexions venant de ta propre machine ». Ça suffit ici, parce que le tunnel SSH *aboutit* sur le Codespace — de son point de vue, la requête vient bien de l'intérieur.

Si tu avais mis `--host 0.0.0.0`, tu aurais dit : « accepte les connexions arrivant par n'importe quelle interface réseau ». C'est exactement pour ça que tu as dû le faire dans ton conteneur Docker : le processus à l'intérieur du conteneur devait accepter des requêtes venant de *l'extérieur* du conteneur. Même concept, deux frontières différentes.

Dis-moi si un point reste flou — sinon, lance le notebook et on attaque le `log_model`.

Mon récapitulatif : Donc dans mon navigateur, qui tourne sur mon mac, l'adresse uri (dans la barre d'adresse du navigateur) est 127.0.0.1:5001, mais grâce au tunnel SSH créé de VS code, il accède a 127.0.0.1:5000 c'est a dire le port qu'écouter et occupe MLFlow sur la machine "codespace". C'est bien ça ?

Réponse claude : 

Exactement, c'est ça. Tu as le mécanisme.

Deux précisions de détail pour affiner :

**Sur le vocabulaire.** Dans la barre d'adresse, on parle plutôt d'**URL**. Et elle est complète : `http://127.0.0.1:5001`. Le `http://` n'est pas décoratif — c'est le **protocole**, la langue que les deux programmes vont parler. L'adresse dit *quelle machine*, le port dit *quel programme*, le protocole dit *comment lui parler*.

**Sur ce que "voit" MLflow.** Le tunnel ne fait pas que transporter la requête, il la fait **ressortir depuis l'intérieur** du Codespace. MLflow reçoit donc une connexion qui, de son point de vue, provient de `127.0.0.1` — de sa propre machine. C'est précisément pour ça que `--host 127.0.0.1` suffit : MLflow n'a jamais conscience qu'une requête a traversé l'Atlantique.

Une image qui marche bien : le tunnel est un **standard téléphonique**. Ton navigateur appelle le numéro local 5001. Le standardiste (VS Code) décroche, transfère l'appel jusqu'au Codespace, et le fait sonner sur le poste interne 5000. MLflow décroche et voit un appel interne — il ignore complètement l'existence de l'appelant d'origine.

Le reste est juste. Tu peux lancer le notebook.



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

# pip vs conda vs pipenv

Les trois créent des environnements isolés et installent des paquets, mais ils viennent d'époques différentes et ne visent pas le même problème.

**conda** (2012, Anaconda) est un gestionnaire de paquets généraliste, pas seulement Python. Il a ses propres dépôts de paquets précompilés (le canal `defaults` d'Anaconda et le canal communautaire `conda-forge`) et peut installer des dépendances système : bibliothèques C, CUDA, MKL, GDAL, voire R. C'est sa vraie force, et la raison de son succès dans le monde scientifique à une époque où installer numpy ou scipy avec pip voulait souvent dire compiler du C. Ses environnements sont nommés et globaux (`conda activate ml`), au lieu d'être rattachés à un projet. Il est plus lourd et historiquement lent, même si son solveur s'est nettement amélioré. Attention aussi aux conditions d'Anaconda : le canal `defaults` est payant pour les organisations de plus de 200 personnes. Miniforge, qui utilise uniquement `conda-forge`, est gratuit.

**pipenv** (2017) a voulu donner à Python ce que npm apporte à JavaScript : un fichier de dépendances (`Pipfile`), un fichier de verrouillage (`Pipfile.lock`) et un environnement virtuel géré automatiquement. Il a été un temps mis en avant par la communauté officielle de packaging Python, mais il est resté lent à résoudre les dépendances, ne gère pas les versions de Python lui-même et utilise un format propre au lieu du standard `pyproject.toml`. Il a ensuite été dépassé par Poetry, puis par uv. On le croise encore dans des projets existants, mais rarement dans un nouveau projet.

**uv** (2024, Astral, les auteurs de Ruff) est écrit en Rust et réunit en un seul outil pip, venv, pip-tools, pipx, pyenv et l'essentiel de Poetry. Il est beaucoup plus rapide que pip, installe lui-même les versions de Python (c'est ce que fait `--python 3.12`), utilise le standard `pyproject.toml` et produit un `uv.lock` valable sur toutes les plateformes. L'environnement est rattaché au projet (le dossier `.venv`). Sa limite est celle de PyPI : il ne gère pas les dépendances système. C'est pour ça que tu as dû installer le programme Graphviz avec Homebrew, uv ne s'occupant que du paquet Python qui l'appelle.

En pratique, en 2026, uv est le choix par défaut pour un projet Python, et c'est le bon choix pour le cours de Karpathy : les paquets torch de PyPI contiennent déjà tout ce qu'il faut, y compris le support MPS sur Mac. conda reste pertinent quand on dépend de bibliothèques natives complexes absentes de PyPI ou mal empaquetées, par exemple certains outils de géospatial, de bio-informatique, ou sur des clusters de calcul. Pour ce cas d'usage, il existe aussi **pixi**, qui apporte l'ergonomie de uv (projet, lockfile, rapidité) à l'écosystème conda-forge. pipenv n'a plus vraiment de raison d'être choisi aujourd'hui.

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

# Dossier /tmp

En IT et en data engineering, un dossier nommé `/tmp` (pour *temporary*) sert à stocker des fichiers éphémères et des données intermédiaires qui n'ont pas vocation à être conservés. Sur les systèmes d'exploitation (comme Linux), ce répertoire est généralement vidé automatiquement lors d'un redémarrage ou via des règles de nettoyage périodiques.

Dans le contexte spécifique du data engineering, `/tmp` est utilisé pour les opérations suivantes :

* **Traitements ETL/ELT :** Le stockage temporaire de fichiers bruts en transit. Par exemple, un script Python télécharge un fichier CSV depuis un bucket S3 ou une API, le place dans `/tmp`, le nettoie, l'insère dans une base de données, puis supprime le fichier local pour libérer de l'espace.
* **Débordement de mémoire (Spill to disk) :** Lors de calculs intensifs avec des frameworks comme Apache Spark ou Pandas, si la mémoire vive (RAM) est saturée, le système utilise `/tmp` pour écrire temporairement des partitions de données sur le disque afin d'éviter un crash de type *Out of Memory* (OOM).
* **Opérations de tri et de shuffle :** Les bases de données et les systèmes distribués utilisent ce dossier pour stocker les résultats partiels lorsqu'ils doivent trier ou réorganiser de très grands volumes de données entre plusieurs nœuds de calcul.
* **Gestion des pipelines :** L'hébergement de fichiers de verrouillage (*lock files*) pour empêcher un script ou une tâche cron de se lancer deux fois en même temps, ou la création d'archives ZIP/TAR intermédiaires avant un transfert.

La règle d'or concernant `/tmp` est de ne jamais y placer de données critiques ou de production, car son contenu peut être écrasé ou supprimé à tout instant sans préavis par le système.

# récap : serveur, service, logiciel, adresse IP, port

Ce wording est globalement compréhensible, mais il contient quelques raccourcis. En informatique, la terminologie requiert une distinction claire entre la couche matérielle, la couche réseau et la couche logicielle.

Voici l'analyse et la correction de chaque affirmation :

* **"Un port appartient toujours à une machine" : Presque exact, mais imprécis.**
* **La nuance :** Un port réseau (TCP ou UDP) appartient plus précisément à une **adresse IP** (et donc à une interface réseau). Une même machine physique ou virtuelle peut posséder plusieurs cartes réseau (et donc plusieurs adresses IP), chacune disposant de ses propres ports (de 1 à 65535).
* **Meilleur wording :** "Un port réseau est associé à l'adresse IP d'une machine."


* **"Un service technique s'exécute/tourne/run sur un server" : Correct.**
* **La nuance :** Les trois termes sont utilisés. "S'exécute" est le terme formel. "Tourne" est très courant à l'oral ("le service tourne en tâche de fond"). "Run" est du franglais typique. Un service technique (ou *daemon* sous Linux) s'exécute effectivement sur le système d'exploitation du serveur.
* **Meilleur wording :** "Un service s'exécute sur un serveur."


* **"Un server est hébergé sur une machine" : Ambigü (problème de polysémie).**
* **La nuance :** En IT, le mot "serveur" a deux sens. Il désigne soit le **matériel** (la machine physique elle-même), soit le **logiciel** (un serveur Web comme Apache, un serveur de base de données). Si vous parlez du logiciel, on dira plutôt qu'il s'exécute sur une machine (physique ou machine virtuelle/VM). Si vous parlez du matériel, le serveur *est* la machine.
* **Meilleur wording :** "Un serveur logiciel (ou applicatif) est hébergé et s'exécute sur une machine (physique ou virtuelle)."


* **"Une adresse URI pointe sur un server" : Inexact.**
* **La nuance :** Une URI (Uniform Resource Identifier) pointe vers une **ressource** précise (une page HTML, une image, un endpoint d'API, une vidéo), pas juste vers un serveur. C'est le nom de domaine (ou l'adresse IP) contenu *à l'intérieur* de l'URI qui pointe vers le serveur.
* **Meilleur wording :** "Une URI identifie et pointe vers une ressource spécifique hébergée sur un serveur."



---

**La synthèse avec le bon wording :**

Une **machine** (physique ou virtuelle) possède une adresse IP. Sur cette machine, s'exécute un **serveur logiciel** (ou service technique) qui écoute sur un **port** réseau spécifique de cette adresse IP. Enfin, un client utilise une **URI** pour interroger ce service et accéder à une ressource précise.

## Adresse IP 127.0.0.1

Oui, absolument. **127.0.0.1** est bien une adresse IP.

Plus précisément, c'est une adresse IP spéciale appelée **adresse de boucle locale** (ou *loopback* en anglais). Elle est presque toujours associée au nom de domaine **localhost**.

Voici comment elle s'intègre dans les concepts que nous venons de voir :

* **Le circuit fermé :** Toute machine (votre ordinateur, un serveur cloud) possède cette adresse IP interne par défaut. Elle permet à la machine de s'envoyer des requêtes réseau à elle-même, sans jamais que la donnée ne sorte sur le câble réseau ou le Wifi.
* **Dans votre exemple MLOps :** Si votre application Gunicorn et votre service MLFlow s'exécutent sur la **même** machine physique ou virtuelle, l'application Python peut utiliser l'URI `[http://127.0.0.1:5000/](http://127.0.0.1:5000/)...` pour récupérer le modèle. La machine comprend instantanément : *"Je dois envoyer cette requête au port 5000 de mon propre système"*.
* **Le piège classique avec Docker :** C'est ici que la distinction "un conteneur = une machine isolée" prend tout son sens. Si votre script Python tourne dans un conteneur A, l'adresse `127.0.0.1` désigne **uniquement l'intérieur du conteneur A**. Si vous essayez de contacter MLFlow situé dans un conteneur B (ou sur la machine hôte) en utilisant `127.0.0.1`, la requête échouera, car le conteneur A cherchera MLFlow chez lui-même.

En résumé, `127.0.0.1` est l'adresse IP qui signifie "moi-même" du point de vue du système d'exploitation qui l'utilise.

# la commande curl

La commande `curl` (pour *Client URL*) est l'équivalent d'un navigateur web (comme Chrome), mais qui fonctionne entièrement en mode texte dans votre terminal. Elle sert à interroger une URI et à récupérer la réponse brute du serveur.

Quand vous tapez `curl [http://127.0.0.1:5000](http://127.0.0.1:5000)`, voici exactement ce que vous demandez à votre machine :

* **`curl` :** Le programme client qui va émettre la requête.
* **`http://` :** Le protocole utilisé pour la communication (le langage commun).
* **`127.0.0.1` :** L'adresse IP de destination (ici, la machine s'adresse à elle-même).
* **`:5000` :** Le port spécifique sur lequel le service (par exemple, votre serveur MLFlow) est censé écouter.

**La différence avec un navigateur classique :**
Si vous tapez `[http://127.0.0.1:5000](http://127.0.0.1:5000)` dans Chrome, le navigateur va récupérer la réponse du serveur et l'interpréter pour dessiner une page visuelle.
Avec `curl`, le terminal va simplement afficher le **texte brut** renvoyé par le serveur. S'il s'agit d'une API, cela s'affichera souvent sous forme de données brutes (comme du format JSON). S'il s'agit d'une page web classique, `curl` crachera tout le code source HTML directement sur votre écran.

C'est l'outil de diagnostic numéro 1 des développeurs. Il permet de vérifier très rapidement si un service technique tourne correctement sur un port précis et s'il renvoie bien la donnée attendue.


# Faire communiquer 3 conteneur docker entre eux ? Adresseq IP et ports sont les seuls moyens de faire communiquer des services entre eux ? Une API permet a un logiciel d'exposer ses endpoint et d'y accéder --> ça ne necessite pas d'adresse IP ? Comment définir un endpoint d'un service?

C'est une excellente série de questions qui touche au cœur de l'architecture logicielle moderne. Vous avez mis le doigt sur une confusion très courante concernant les API et les adresses IP.

Reprenons point par point pour démêler tout cela.

### 1. Les API se passent-elles d'adresses IP ? (La grande illusion)

**Non, c'est une illusion d'optique !** Une API web (REST, GraphQL, etc.) utilise **toujours** une adresse IP et un port en coulisses.

L'API n'est pas une technologie réseau, c'est juste un **contrat de communication** (un format de message, souvent du texte ou du JSON). Pour que ce message voyage de l'application A à l'application B, il doit emprunter le réseau informatique, et le réseau ne comprend *que* les adresses IP.

**Pourquoi avez-vous l'impression qu'il n'y a pas d'IP ?**
À cause du **DNS (Domain Name System)**. Le DNS est l'annuaire du réseau. Quand votre application appelle l'API de Stripe via `[https://api.stripe.com](https://api.stripe.com)`, votre système d'exploitation interroge d'abord un serveur DNS : *"Quelle est l'adresse IP de api.stripe.com ?"*. Le DNS répond *"C'est 3.14.25.12"*. Et votre machine fait en réalité sa requête vers cette adresse IP sur le port 443 (HTTPS).

### 2. Comment faire communiquer 3 conteneurs Docker entre eux ?

C'est ici que la magie du "DNS interne" de Docker opère. Vous n'avez pas besoin de coder des adresses IP en dur (ce qui serait un cauchemar, car les IP des conteneurs changent à chaque redémarrage).

**La solution : Le réseau Docker (Docker Network)**

1. Vous créez un réseau virtuel : `docker network create mon-reseau-app`.
2. Vous lancez vos 3 conteneurs en les attachant à ce réseau.
3. **Le principe clé :** Docker intègre son propre petit serveur DNS. Il associe automatiquement le **nom du conteneur** à son adresse IP interne.

**Exemple :**

* Conteneur 1 (nommé `frontend`)
* Conteneur 2 (nommé `backend-api` qui écoute sur le port 8000)
* Conteneur 3 (nommé `base-de-donnees` qui écoute sur le port 5432)

Pour que le frontend contacte l'API, vous n'utiliserez pas `127.0.0.1` ni une IP complexe, mais directement le nom du conteneur dans l'URI :
`curl http://backend-api:8000`

### 3. Les adresses IP et ports sont-ils le SEUL moyen de faire communiquer des services ?

Sur un réseau (entre plusieurs machines ou conteneurs), **oui**, le couple IP/Port (protocole TCP ou UDP) est incontournable. Mais si on sort du réseau pur, il existe d'autres méthodes de communication en informatique :

* **Les Sockets Unix (IPC - Inter-Process Communication) :** Si deux services tournent sur la *même* machine Linux, ils peuvent communiquer non pas par le réseau (IP/Port), mais en lisant et écrivant dans un fichier spécial sur le disque dur (un socket, ex: `/var/run/mysqld/mysqld.sock`). C'est extrêmement rapide. (D'ailleurs, Docker lui-même utilise un socket Unix pour que votre terminal puisse lui donner des ordres !).
* **Les files de messages (Message Brokers comme Kafka ou RabbitMQ) :** Les services ne se parlent plus directement. Le service A envoie un message au "facteur" (Kafka), et le service B vient lire le message quand il a le temps. (Cependant, pour parler à Kafka, les services A et B utiliseront... une IP et un port !).

### 4. Qu'est-ce qu'un "endpoint" et comment le définir ?

Un **endpoint** (point de terminaison), c'est l'extrémité d'un tuyau de communication dans une API. C'est le croisement entre une **action** (verbe HTTP) et une **route** (le chemin dans l'URI).

Si le serveur est un bâtiment (l'adresse IP) et le port est la porte d'entrée principale, les endpoints sont les **guichets à l'intérieur du bâtiment**, chacun ayant une fonction précise.

**Comment définit-on un endpoint ?**
On le définit dans le code du serveur (le code Python/Gunicorn dont on parlait plus tôt, souvent avec des frameworks comme Flask ou FastAPI). Il est constitué de deux parties :

1. **La méthode HTTP :** L'action voulue (`GET` pour lire, `POST` pour créer, `PUT` pour modifier, `DELETE` pour supprimer).
2. **Le chemin (Path) :** La ressource ciblée.

**Exemples d'endpoints pour une API de gestion d'utilisateurs :**

* `GET /api/utilisateurs` : (C'est un endpoint). Son rôle est de lister tous les utilisateurs.
* `GET /api/utilisateurs/42` : (C'est un autre endpoint). Son rôle est de donner les infos de l'utilisateur n°42.
* `POST /api/utilisateurs` : (Encore un autre endpoint). Son rôle est de créer un nouvel utilisateur avec les données envoyées.

Quand vous tapez `curl http://backend-api:8000/api/utilisateurs/42`, vous contactez la machine `backend-api` sur le port `8000`, et vous visez l'endpoint précis `/api/utilisateurs/42` en lecture (`GET` par défaut avec curl).

### Autres information sur le endpoint

Un **endpoint** (ou point de terminaison) est une adresse (une URL) spécifique qu'une application met à disposition pour qu'on puisse venir interagir avec l'une de ses ressources. C'est la porte d'entrée exacte d'une fonction précise d'une API.

Si le serveur est un bâtiment (trouvable via son IP) et le port est la porte d'entrée, les endpoints sont les **guichets spécialisés** à l'intérieur du bâtiment. Il y a un guichet pour s'inscrire, un guichet pour modifier son profil, et un autre pour supprimer son compte.

Techniquement, un endpoint est toujours le croisement de deux éléments :

1. **Un chemin (le "Path") :** qui désigne la cible ou la donnée (ex: `/utilisateurs` ou `/utilisateurs/42`).
2. **Une méthode HTTP (le "Verbe") :** qui indique l'action que l'on veut effectuer sur cette donnée (ex: `GET` pour lire, `POST` pour créer).

### Exemple concret avec une API de blog

Imaginons que votre application soit hébergée sur `[https://api.monblog.com](https://api.monblog.com)` (l'URL de base). Voici 4 endpoints différents que le développeur a pu définir :

* **Endpoint 1 :** `GET /articles`
* *Rôle :* Consulter la liste de tous les articles.


* **Endpoint 2 :** `GET /articles/15`
* *Rôle :* Consulter uniquement le contenu de l'article numéro 15.


* **Endpoint 3 :** `POST /articles`
* *Rôle :* Créer un nouvel article (en envoyant le texte de l'article dans la requête).


* **Endpoint 4 :** `DELETE /articles/15`
* *Rôle :* Supprimer l'article numéro 15.


**À noter :** Même si le chemin est strictement identique pour les endpoints 2 et 4 (`/articles/15`), le fait de changer le verbe HTTP (`GET` au lieu de `DELETE`) en fait **deux endpoints totalement distincts** aux yeux du serveur. Chaque endpoint déclenchera une fonction différente dans le code (Python, Node.js, etc.) de l'application.
_______________________________________________

**Question** : Le path d'un endpoint correspondant nd a une url ou a une url + un port ?

Le **path** (chemin) n'est ni l'URL complète, ni l'URL + le port. Il correspond **uniquement à la partie finale** de l'adresse, celle qui vient *après* l'IP (ou le nom de domaine) et le port.

Pour bien comprendre, décortiquons une adresse complète (une URL) :

`[http://127.0.0.1:8000/api/utilisateurs/42](http://127.0.0.1:8000/api/utilisateurs/42)`

Voici l'anatomie exacte :

* **`http://`** = Le protocole de communication.
* **`127.0.0.1`** = L'hôte (l'adresse IP de la machine ou le nom de domaine).
* **`:8000`** = Le port (la porte d'entrée du service).
* **`/api/utilisateurs/42`** = **Le Path (le chemin).**

### La nuance dans le langage courant

Dans la réalité du monde du développement, vous entendrez deux façons d'en parler :

1. **Côté code (strict) :** Quand un développeur écrit le code de son API (avec Python, Node.js, etc.), il ne définit **que le path**. Le serveur connaît déjà son port et sa machine. Dans le code, l'endpoint est simplement défini comme : `GET /api/utilisateurs/42`.
2. **Côté client (courant) :** Quand on vous donne la documentation d'une API pour l'utiliser, on vous donne souvent l'URL complète (avec l'IP ou le domaine, et parfois le port) pour que vous sachiez comment joindre la machine. On dira alors par abus de langage : *"L'endpoint est `[http://api.monblog.com/articles](http://api.monblog.com/articles)`"*.

En résumé, le **path** est la route interne au serveur (`/articles`), tandis que l'**URL complète** inclut la machine et le port pour trouver ce serveur sur le réseau.