# Module 4 — Partie 1 : web-service - déployer un modèle en web service

---

## 1. Le problème de départ

Tout ce chapitre découle d'une seule difficulté : **un modèle entraîné n'est pas un fichier autonome.**

Quand tu fais `pickle.dump(model, f)`, Python n'écrit pas « une régression linéaire avec ces coefficients ». Il écrit des références aux classes telles qu'elles existaient dans la version de scikit-learn installée à ce moment-là. Le pickle est une photographie qui suppose que le décor n'a pas bougé.

Trois conséquences en cascade :

1. L'environnement qui **sert** le modèle doit ressembler à celui qui l'a **entraîné**
2. Mais cet environnement de service n'a pas les mêmes besoins que ton environnement de travail
3. Et il doit être reproductible à l'identique, sur ta machine comme sur un serveur

Le reste du module est la réponse à ces trois points : isolation, épinglage des versions, conteneurisation.

---

## 2. Les fondations : shell, PATH, environnements

### Le shell

Un **shell** est le programme qui lit tes commandes et lance les programmes correspondants. Sur ton Codespace, c'est `bash`. À ne pas confondre avec le **terminal**, qui n'est que la fenêtre (clavier + écran).

Un shell est un processus vivant qui maintient un état : un répertoire courant, et un jeu de variables d'environnement.

### PATH, la variable qui explique tout

`PATH` est une liste de dossiers séparés par `:`. Quand tu tapes `python`, le shell parcourt cette liste **de gauche à droite** et exécute le **premier** exécutable trouvé. Il s'arrête là.

```bash
echo $PATH | tr ':' '\n'
```

**Activer un environnement, ce n'est rien d'autre que mettre son dossier `bin/` en tête de cette liste.** `conda activate`, `pipenv shell`, `source venv/bin/activate` : tous font la même chose. Aucune magie.

### Shell parent, shell enfant

Un shell peut en lancer un autre. L'enfant reçoit une **copie** de l'environnement du parent.

- Ce que l'enfant modifie ne remonte jamais au parent (d'où `exit` qui te rend ton shell intact)
- L'enfant peut réécrire son PATH librement

C'est ce qui explique ton `(web-service) (base)` :

```
shell parent           PATH = [conda/mlopszoomcamp/bin, ...]
│                      prompt : (mlopszoomcamp)
│
└─ pipenv shell  →  shell ENFANT
                       1. bash démarre, relit ~/.bashrc
                       2. ~/.bashrc contient le hook conda → active base
                       3. pipenv ajoute le virtualenv en tête
                       prompt : (web-service) (base)
```

Les deux préfixes ne disent pas où tu es. Ils disent quels activateurs sont passés. **Seul `which python` fait foi.**

### Les trois environnements de ce chapitre

| Environnement | Rôle | Python | scikit-learn |
|---|---|---|---|
| `mlopszoomcamp` (conda) | ton atelier : notebooks, exploration, MLflow | 3.11 | 1.9.0 |
| `py310` (conda) | fournisseur d'interpréteur, jamais utilisé directement | 3.10 | — |
| `web-service` (pipenv) | le service à livrer | 3.10 | 1.0.2 |

Ils ne sont **pas imbriqués**. Ils sont côte à côte. Le virtualenv pipenv ne voit aucun paquet de conda.

> Une seule dépendance réelle : le virtualenv ne copie pas la bibliothèque standard, il pointe vers `py310` via son fichier `pyvenv.cfg`. Supprimer `py310` casserait le virtualenv.

---

## 3. pipenv : Pipfile et Pipfile.lock

### Pourquoi pas conda ?

Conda est excellent pour explorer. Il est mauvais pour livrer : lourd, difficile à faire entrer dans une image Docker légère. Pipenv produit deux fichiers texte que le Dockerfile sait exploiter directement.

### Pipfile : l'intention

```toml
[[source]]
url = "https://pypi.org/simple"

[packages]
scikit-learn = "==1.0.2"
flask = "*"
gunicorn = "*"
numpy = "<2"

[dev-packages]
requests = "*"

[requires]
python_version = "3.10"
```

C'est un fichier **écrit par un humain**, éditable à la main. Il exprime des contraintes, pas des versions exactes (`*` = n'importe laquelle).

La distinction `[packages]` / `[dev-packages]` est conceptuelle et importante :

- `predict.py` tourne **dans** le service → flask, scikit-learn, gunicorn → `[packages]` → partent dans l'image Docker
- `test.py` tourne **en face** du service, c'est le client → requests → `[dev-packages]` → le Dockerfile ne l'installe pas

Une image livrée ne contient que ce qui sert à répondre. Pas ce qui sert à interroger.

### Pipfile.lock : la résolution figée

C'est un fichier **généré par la machine**, jamais édité à la main. Il contient :

- la version exacte de chaque paquet, y compris les **dépendances transitives** (celles que tes dépendances entraînent sans que tu les demandes)
- les empreintes SHA256 de chaque fichier téléchargé
- une empreinte du Pipfile dont il dérive

C'est cette photographie complète qui rend la reconstruction identique sur n'importe quelle machine.

> **La leçon la plus coûteuse de la session** : `numpy==1.22.4` était dans le lock d'origine sans être dans le Pipfile. En lançant `pipenv lock`, tu as re-résolu depuis le Pipfile seul, qui ne contraignait pas numpy. Pipenv a pris une 2.x, et le code C de scikit-learn 1.0.2 s'est cassé dessus.

---

## 4. Les versions : la matrice de compatibilité

C'est le vrai contenu technique du chapitre. Quatre contraintes qui s'enchaînent :

| Contrainte | Pourquoi |
|---|---|
| sklearn du service = sklearn du pickle (1.0.2) | sinon dépicklage douteux ou cassé |
| Python ≤ 3.10 | sklearn 1.0.2 ne publie des wheels que jusqu'à cp310 |
| Python ≥ 3.10 | pip 26 a abandonné le support de 3.9 |
| numpy < 2 | sklearn 1.0.2 est compilé contre l'ABI numpy 1.x |

**Python 3.10 est la seule valeur qui satisfait tout.** Le cours date de 2022 et proposait 3.9 ; cette fenêtre s'est fermée quand Python 3.9 est arrivé en fin de vie en octobre 2025.

### Trouver la version qui a créé un pickle

scikit-learn inscrit sa version dans le pickle lui-même :

```bash
strings lin_reg.bin | grep -A2 _sklearn_version
```

On lit les octets du fichier, on ne désérialise rien. Aucun besoin d'avoir scikit-learn installé.

Pour un modèle MLflow, ne cherche pas dans le pickle : le dossier d'artefacts contient un `requirements.txt` et un `conda.yaml` qui donnent la réponse directement.

### Les deux erreurs de version rencontrées

**Erreur pip / Python 3.9**
```
This version of pip does not support python 3.9 (requires >=3.10)
```
Un outil moderne refuse un Python trop ancien. Solution : monter en 3.10.

**Erreur ABI numpy**
```
ValueError: numpy.dtype size changed... Expected 96 from C header, got 88
```
Ce n'est pas une erreur Python, c'est une incompatibilité **binaire**. Le code C compilé de sklearn lit une structure mémoire à des décalages qui ont changé entre numpy 1.x et 2.x. Solution : `pipenv install "numpy<2"`.

> Numpy garantit la compatibilité ABI à l'intérieur d'une même majeure. Du code compilé contre 1.21 tourne avec 1.26. C'est le passage à 2.0 qui rompt le contrat.

---

## 5. Flask et Gunicorn

### Ce n'est pas « l'un ou l'autre »

Flask fait deux choses distinctes :

1. **Le framework** : `@app.route`, parsing JSON, `jsonify`. Ton code métier. Tu le gardes.
2. **Le serveur de développement** : ce que déclenche `app.run()`. C'est lui seul qu'on remplace.

Gunicorn ne remplace pas Flask, il l'**exécute** :

```bash
gunicorn --bind=0.0.0.0:9696 predict:app
```

`predict:app` se lit : « dans le module `predict.py`, prends l'objet `app` ».

### Le contrat : WSGI

Une norme Python (PEP 3333) définit comment un serveur et une application se parlent. Flask expose une app conforme WSGI ; Gunicorn est un serveur WSGI. N'importe quel serveur WSGI pourrait exécuter ton app Flask, et Gunicorn pourrait exécuter du Django.

Flask écrit le contenu, Gunicorn est l'imprimerie.

### Pourquoi le serveur de dev ne suffit pas

| Serveur de dev Flask | Gunicorn |
|---|---|
| mono-processus, une requête à la fois | plusieurs workers en parallèle |
| un crash = tout tombe | worker redémarré automatiquement |
| pas de timeouts | timeouts et limites configurables |

La distinction n'est **pas** local/distant. Tu fais tourner Gunicorn en local dans ce module. La distinction est robustesse et concurrence.

> Point à retenir pour plus tard : chaque worker charge sa **propre copie** du modèle en mémoire. Avec un modèle de 400 Ko, sans importance. Avec un modèle d'un Go sur un Codespace à 8 Go, le nombre de workers (`-w`) devient un calcul.

---

## 6. Docker

### Le Dockerfile

```dockerfile
FROM python:3.10.21-slim          # image de base

RUN pip install -U pip
RUN pip install pipenv

WORKDIR /app                       # répertoire de travail dans le conteneur

COPY [ "Pipfile", "Pipfile.lock", "./" ]
RUN pipenv install --system --deploy

COPY [ "predict.py", "lin_reg.bin", "./" ]

EXPOSE 9696
ENTRYPOINT [ "gunicorn", "--bind=0.0.0.0:9696", "predict:app" ]
```

Deux détails qui comptent :

**`--system`** : on installe dans le Python de l'image, sans créer de virtualenv. Le conteneur *est* déjà l'isolation ; en rajouter une serait redondant.

**`--deploy`** : mode strict. Il refuse de construire si le Pipfile et le Pipfile.lock ont divergé, ou si la version de Python ne correspond pas. C'est ce qui a provoqué ton `DeployException`. C'est pénible sur le moment, et c'est exactement ce que tu veux avant d'envoyer une image en production.

**L'ordre des COPY n'est pas arbitraire.** Docker met en cache chaque instruction. Les dépendances changent rarement, le code souvent. En copiant le Pipfile avant le code, une modification de `predict.py` ne réinstalle pas tout.

### Le contexte de build

```bash
docker build -t ride-duration-prediction-service:v1 .
```

Ce point final n'est pas décoratif. Docker ne construit pas sur ta machine : il envoie un dossier au **daemon Docker**, un processus séparé. Le point dit : « le dossier à envoyer est le répertoire courant ».

C'est aussi la racine de tous les `COPY`. Le Dockerfile ne peut copier que ce qui est dans le contexte. Un `COPY ../ailleurs/fichier` est refusé, même si le fichier existe.

> Le dossier entier est transféré. Négligeable ici (445 kB), mais le jour où tu construiras depuis un répertoire contenant `mlruns/` ou des données, tu enverras des gigaoctets pour rien. La parade : un fichier `.dockerignore`, qui fonctionne comme un `.gitignore`.

### Lancer le conteneur

```bash
docker run -it --rm -p 9696:9696 ride-duration-prediction-service:v1
```

- `-it` : mode interactif, tu vois les logs et peux faire `Ctrl+C`
- `--rm` : supprime le conteneur à l'arrêt, pas d'accumulation
- `-p 9696:9696` : publie le port. `hôte:conteneur`. Sans ça, le conteneur écoute dans le vide.

---

## 7. Cheat sheet des commandes

### pipenv

| Commande | Effet |
|---|---|
| `pipenv install` | reconstruit l'env depuis le `Pipfile.lock` (sans argument = pas d'ajout) |
| `pipenv install --dev` | idem + les `[dev-packages]` |
| `pipenv install --python /chemin/vers/python` | idem, en imposant l'interpréteur (le **trouve**, ne l'installe pas) |
| `pipenv install <paquet>` | ajoute au Pipfile et re-résout le lock |
| `pipenv lock` | régénère le lock depuis le Pipfile. **Jamais anodin sur un projet ancien** |
| `pipenv run <commande>` | exécute une commande dans l'env, sans subshell. **À privilégier** |
| `pipenv shell` | lance un subshell. Conda peut s'y réinviter |
| `pipenv --rm` | supprime le virtualenv du projet |
| `pipenv --venv` | affiche le chemin du virtualenv |

Comment pipenv trouve ses fichiers : il cherche un `Pipfile` dans le répertoire courant, puis remonte de parent en parent. D'où l'importance du `cd`. Le nom du virtualenv (`web-service-ToH4o1-o`) combine le nom du dossier et une empreinte de son chemin absolu.

### Diagnostic

```bash
which python                                    # quel binaire sera exécuté
python -c "import sys; print(sys.executable)"   # confirmation depuis Python
python -m pip freeze                            # le -m force le pip de l'interpréteur courant
pipenv run python -c "import sklearn; print(sklearn.__version__)"
lsof -t -i:9696                                 # qui occupe le port
kill $(lsof -t -i:9696)                         # le libérer
```

> `pip freeze` lit les métadonnées du gestionnaire de paquets. `import sklearn` interroge le module réellement chargé. En cas de désaccord, **c'est l'import qui dit la vérité**. D'où le réflexe `python -m pip` plutôt que `pip`.

### Docker

```bash
docker build -t nom:tag .
docker run -it --rm -p 9696:9696 nom:tag
docker images                                   # lister les images
docker ps                                       # conteneurs en cours
docker run -it --rm --entrypoint=bash nom:tag   # inspecter l'image de l'intérieur
```

---

## 8. Les erreurs rencontrées, et ce qu'elles enseignent

| Erreur | Cause | Leçon |
|---|---|---|
| `pip does not support python 3.9` | outil moderne, Python en fin de vie | le matériel de cours vieillit, pas l'écosystème |
| `requires 1 argument` | point de contexte oublié | Docker construit ailleurs, il faut lui envoyer le dossier |
| `DeployException` | Pipfile en 3.9, image en 3.10 | `--deploy` garantit la cohérence des trois artefacts |
| `Address already in use` | serveur Flask encore lancé | un port = un processus |
| `numpy.dtype size changed` | numpy 2.x contre sklearn compilé pour 1.x | le lock file protège les dépendances transitives |

### Le fil rouge

Trois fichiers doivent rester cohérents : le **Pipfile** (l'intention), le **Pipfile.lock** (la résolution figée), le **Dockerfile** (l'interpréteur). Dès que l'un dérive, `--deploy` refuse de construire.

Et un piège plus vicieux que tu as frôlé : lancer `gunicorn` depuis `(mlopszoomcamp)` au lieu du virtualenv. La commande fonctionne, le service répond, mais avec scikit-learn 1.9.0 face à un pickle 1.0.2. **Dans ce dossier, un prompt `(mlopszoomcamp)` est un signal d'alerte.** Passe par `pipenv run`.

---

Si tu veux, je peux transformer ce récapitulatif en document que tu gardes et annotes au fil du cours.


# qu'es-ce que ./bashrc ?

`~/.bashrc` est un **fichier de configuration** — un simple script bash que le shell exécute automatiquement à son démarrage.

Décomposons le nom :
- `~` = ton répertoire personnel, ici `/home/codespace`
- le `.` initial = fichier caché (invisible avec `ls`, il faut `ls -a`)
- `rc` = *run commands*, une convention Unix ancienne qu'on retrouve partout (`.vimrc`, `.condarc`, `.npmrc`)

Le chemin complet chez toi : `/home/codespace/.bashrc`.

## Ce qu'il contient

Tout ce que tu veux voir appliqué à chaque nouveau shell : des alias, des modifications de `PATH`, la personnalisation du prompt, des variables d'environnement. Comme c'est un script bash ordinaire, il peut contenir n'importe quelle commande.

Regarde le tien :

```bash
cat ~/.bashrc
```

Tu y trouveras un bloc de ce genre, ajouté par conda lors de son installation :

```bash
# >>> conda initialize >>>
__conda_setup="$('/home/codespace/miniconda3/bin/conda' 'shell.bash' 'hook' ...)"
...
# <<< conda initialize <
```

C'est ce bloc — le « hook conda » — qui rend la commande `conda` disponible et qui active `base` automatiquement.

## Pourquoi c'est la clé de ton `(web-service) (base)`

Voilà la chaîne complète :

1. tu tapes `pipenv shell`
2. un **shell enfant** démarre
3. étant un nouveau bash, il lit `~/.bashrc` **depuis le début**
4. le hook conda s'exécute → `base` est activée, son `bin/` passe en tête du `PATH`
5. pipenv ajoute ensuite son virtualenv en tête

Chaque nouveau shell relit ce fichier. Il n'hérite pas de l'état « conda déjà initialisé » du parent : il refait la manœuvre depuis zéro. D'où le préfixe qui réapparaît alors que tu croyais en être sorti.

C'est exactement pour contourner ça que `pipenv run` est préférable : il n'ouvre pas de shell, donc `~/.bashrc` n'est jamais relu, donc conda n'a aucune occasion de s'interposer.

## Une nuance utile

Bash distingue deux types de session et deux fichiers :

- **shell interactif** (un terminal ouvert) → lit `~/.bashrc`
- **shell de connexion** (SSH, console) → lit `~/.bash_profile` ou `~/.profile`

Dans la pratique, `~/.bash_profile` contient souvent une ligne qui source `~/.bashrc`, pour que les deux cas se comportent pareil. Sur ton Codespace, tu peux t'en tenir à `~/.bashrc`.

## À savoir pour la suite

Si tu modifies `~/.bashrc`, le changement ne s'applique pas aux shells déjà ouverts. Il faut soit ouvrir un nouveau terminal, soit forcer la relecture :

```bash
source ~/.bashrc
```

Et une mise en garde : c'est un fichier qu'on casse facilement. Une erreur de syntaxe peut rendre tes terminaux inutilisables. Fais-en une copie avant toute modification :

```bash
cp ~/.bashrc ~/.bashrc.backup
```