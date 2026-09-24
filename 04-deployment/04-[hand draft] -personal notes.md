
# web-service-mlflow : MLflow server

cd /workspaces/mlops-zoomcamp/04-deployment/web-service-mlflow
conda activate mlopszoomcamp

mlflow server \
  --backend-store-uri sqlite:////workspaces/mlops-zoomcamp/04-deployment/web-service-mlflow/mlflow.db \
  --default-artifact-root /workspaces/mlops-zoomcamp/04-deployment/web-service-mlflow/artifacts \
  --host 127.0.0.1 \
  --port 5000

# web service : pipenv (related to the folder )

first thing we need to do : be sure that to create the web sevice, we'll use the same scikit learn version that the one used to create the pickle file in the duration-prediction.py we used before

To do that, go to the termina 

```bash
(base) @Janua29 ➜ /workspaces/mlops-zoomcamp/04-deployment/web-service (main) $ conda activate mlopszoomcamp
(mlopszoomcamp) @Janua29 ➜ /workspaces/mlops-zoomcamp/04-deployment/web-service (main) $ pip freeze | grep scikit-learn
scikit-learn==1.9.0
```

### Do I need to create a new environnement as the instrcutor does ?

Short answer: **yes, do the equivalent — but for a different reason than you might think, and you don't have to use `pipenv` if you don't want to.**

**Why the instructor does this**

A pickled scikit-learn model is not a neutral file. It stores references to Python classes as they existed in the version that created it. If you `pickle.load()` it with a different scikit-learn version, you get at best a noisy `InconsistentVersionWarning`, at worst a crash or — the nasty case — a model that loads but predicts subtly differently. So the rule is: **the environment that serves the model must have the same scikit-learn version as the environment that trained it.**

That's step one, and it applies to you exactly the same way.

**Why he creates a *new* environment instead of reusing his existing one**

This is the part that's easy to miss. He's not creating a fresh env because his conda env is "wrong". He's doing it because the deployment env has a completely different job:

- your `mlopszoomcamp` conda env = your workshop. Jupyter, pandas, matplotlib, xgboost, hyperopt, mlflow... dozens of packages you need to *explore*.
- the web-service env = the crate you ship. Flask + scikit-learn + gunicorn. Nothing else.

And crucially, `pipenv` produces a `Pipfile` and a `Pipfile.lock` sitting in `04-deployment/web-service/`. In two videos, the Dockerfile will do `COPY Pipfile Pipfile.lock ./` then `RUN pipenv install --system --deploy`. That lock file is what makes the container byte-for-byte reproducible. A conda env can't be copied into a slim Docker image nearly as cleanly.

**What to actually do**

First, find the version your model was trained with, from your conda env:

```bash
conda activate mlopszoomcamp
python -c "import sklearn; print(sklearn.__version__)"
```

Then create the deployment env in the web-service folder:

```bash
cd ~/mlops-zoomcamp/04-deployment/web-service   # adapt to your repo path
pip install pipenv                               # probably not installed in your Codespace yet
pipenv install scikit-learn==<YOUR_VERSION> flask --python 3.11
```

Two adjustments compared to the video:
- pin **your** scikit-learn version, not his `1.0.2`
- use `--python 3.11` (your conda env's Python) rather than `3.9`, unless you specifically want to install 3.9. Matching sklearn matters; matching Python minor version doesn't, as long as the version you pick supports your sklearn.

One thing to watch: `pipenv` creates a virtualenv that is completely *separate* from conda. Once you run `pipenv shell`, you're no longer in `mlopszoomcamp` — that's expected and correct. Your prompt will change to something like `(web-service-U2PKm5NQ)`. Same diagnostic reflex as before: `which python` / `sys.executable` tells you where you really are.

**Could you skip pipenv entirely?**

Yes. You could write a `requirements.txt` with pinned versions and have the Dockerfile do `pip install -r requirements.txt`. That works fine and is arguably more common in industry. But I'd suggest following the course here — when the Docker video arrives, the commands will match what you have on disk, and you'll have one less thing to debug. You can always redo it your own way afterwards.

____________________________________________________________

Oui, dans ton cas elles donnent le même résultat — mais elles ne posent pas exactement la même question. La nuance vaut le coup d'être comprise, parce que c'est précisément le genre de piège que tu as déjà rencontré avec les kernels Jupyter.

**`pip freeze | grep scikit-learn`** interroge les *métadonnées* du gestionnaire de paquets : « qu'est-ce que pip a enregistré comme installé ? ». C'est une lecture de catalogue.

**`python -c "import sklearn; print(sklearn.__version__)"`** importe réellement le module et lui demande de se présenter. C'est une lecture de terrain : c'est exactement ce que ton script Flask obtiendra quand il fera `import sklearn`.

**Quand les deux divergent**

- Le `pip` de ton PATH n'est pas celui de ton Python actif. Classique en conda : tu actives `mlopszoomcamp` mais un `pip` de `(base)` traîne devant dans le PATH. `pip freeze` te décrit alors un environnement... qui n'est pas celui qui exécutera ton code.
- Un paquet installé en mode éditable (`pip install -e`) ou depuis les sources : les métadonnées peuvent rester figées sur une ancienne version.
- Un dossier `sklearn/` local dans ton répertoire courant qui masque le vrai paquet (`sys.path` commence par le répertoire courant).

Dans ces cas-là, c'est toujours l'`import` qui dit la vérité. D'où le réflexe à prendre : **`python -m pip freeze`** plutôt que `pip freeze`. Le `-m` force pip à s'exécuter *dans* l'interpréteur courant — plus de décalage possible.

Petit détail sur `grep` : il matche par sous-chaîne. C'est pourquoi l'instructeur voit aussi `scikit-learn-intelex` remonter dans sa capture. Ce n'est pas un doublon, c'est juste un autre paquet dont le nom contient `scikit-learn`.

**Un point à vérifier avant de figer 1.9.0**

La version à épingler n'est pas « celle de mon environnement », c'est **celle qui a créé le pickle que tu vas servir**. Deux cas :

- tu sers un modèle que *tu* as entraîné dans les modules 1–3 avec cet environnement → 1.9.0 est bien la bonne, tu peux y aller.
- tu récupères le `lin_reg.bin` fourni par le cours → il a été pickled avec la version de l'époque (1.0.2), et c'est *celle-là* qu'il faudrait pinner pour éviter les avertissements au chargement.

Regarde ce que tu as dans `04-deployment/web-service/` avant de lancer le `pipenv install`. Si tu comptes servir ton propre modèle issu du module 2 (via MLflow), on aura de toute façon un petit détour à faire pour récupérer l'artefact proprement.

_______________________________________________________________________________-


```bash
(mlopszoomcamp) @Janua29 ➜ /workspaces/mlops-zoomcamp/04-deployment/web-service (main) $ ls -la /workspaces/mlops-zoomcamp/04-deployment/web-service/
total 452
drwxrwxrwx+ 2 codespace root   4096 Sep  7 19:36 .
drwxrwxrwx+ 7 codespace root   4096 Sep 18 06:41 ..
-rw-rw-rw-  1 codespace root    286 Sep  7 19:36 Dockerfile
-rw-rw-rw-  1 codespace root    205 Sep  7 19:36 Pipfile
-rw-rw-rw-  1 codespace root  17139 Sep  7 19:36 Pipfile.lock
-rw-rw-rw-  1 codespace root    340 Sep  7 19:36 README.md
-rw-rw-rw-  1 codespace root 411402 Sep  7 19:36 lin_reg.bin
-rw-rw-rw-  1 codespace root    803 Sep  7 19:36 predict.py
-rw-rw-rw-  1 codespace root    203 Sep  7 19:36 test.py
(mlopszoomcamp) @Janua29 ➜ /workspaces/mlops-zoomcamp/04-deployment/web-service (main) $ strings lin_reg.bin | grep -A2 _sklearn_version
_sklearn_version
1.0.2
sklearn.linear_model._base
```


Excellente observation, et la réponse va clarifier tout le chapitre.

**Les deux versions ne sont pas en conflit, elles vivent dans deux mondes différents**

- **1.9.0** = la version installée dans ton env conda `mlopszoomcamp`. C'est celle qui a servi à entraîner *tes* modèles dans les modules 1 à 3.
- **1.0.2** = la version qui a créé `lin_reg.bin`, le modèle fourni par le cours. Ce fichier a été pickled par l'instructeur en 2022.

Ces deux nombres n'ont aucune raison d'être égaux, et c'est exactement pour ça que l'instructeur commence le module par cette vérification. Le `lin_reg.bin` est un objet étranger qui arrive avec ses propres exigences. Si tu tentes de le charger avec scikit-learn 1.9.0, tu t'exposes aux problèmes de dépickling dont on parlait.

Une image : un fichier `.docx` créé avec Word 2010. Ta version de Word n'a pas d'importance tant que tu écris tes propres documents. Le jour où tu veux ouvrir *celui-là* fidèlement, c'est la version d'origine qui commande.

Donc pour le web service : tu pinnes **1.0.2**, pas 1.9.0. Ton env conda reste en 1.9.0, intact, pour ton travail de data scientist.

**Attention : un `Pipfile` existe déjà**

Tu as `Pipfile` et `Pipfile.lock` datés du 7 septembre — ils viennent du repo du cours. Regarde ce qu'ils contiennent avant de lancer quoi que ce soit :

```bash
cat Pipfile
```

Si scikit-learn 1.0.2 et flask y sont déjà, tu n'as pas besoin de refaire le `pipenv install <paquets>`. Un simple :

```bash
pipenv install
```

suffit — il lira le `Pipfile.lock` et recréera l'environnement à l'identique. C'est d'ailleurs tout l'intérêt d'un lock file. Un point de vigilance : le Pipfile du cours demande probablement Python 3.9, que ton Codespace n'a peut-être pas. Si ça coince là-dessus, on ajustera.

**(mlopszoomcamp) @Janua29 ➜ /workspaces/mlops-zoomcamp/04-deployment/web-service (main) $ pip install pipenv.  --> environnement pipenv est dans l'environnement conda ? Ce sont des environnements imbriqués ?**
**Environnements imbriqués ?**

Non, et c'est important de bien le voir. Ils ne sont pas imbriqués, ils sont **côte à côte**. Ce qui te donne l'impression d'imbrication, c'est le `PATH` du shell.

Quand tu actives conda, ton shell met le dossier `bin/` de `mlopszoomcamp` en tête du PATH. `python`, `pip`, `pipenv` pointent vers conda.

Quand tu fais `pipenv shell`, un *nouveau* shell démarre et met le dossier `bin/` du virtualenv pipenv en tête du PATH — **devant** celui de conda. Donc `python` pointe maintenant vers `~/.local/share/virtualenvs/web-service-XXXX/bin/python`, un interpréteur totalement distinct, avec son propre `site-packages`.

Il n'y a pas d'héritage : les paquets de conda ne sont pas visibles depuis le virtualenv pipenv. Ce n'est pas une poupée russe, c'est un empilement de chemins de recherche où le dernier arrivé gagne.

Ton réflexe habituel reste le bon juge de paix :

```bash
which python
python -c "import sys; print(sys.executable)"
```

Ce que ça donne concrètement :

| Contexte | `which python` |
|---|---|
| `(base)` | `~/anaconda3/bin/python` |
| `(mlopszoomcamp)` | `~/anaconda3/envs/mlopszoomcamp/bin/python` |
| `pipenv shell` | `~/.local/share/virtualenvs/web-service-XXXX/bin/python` |

Le seul vrai effet de l'imbrication apparente : c'est le `pipenv` de conda qui a *fabriqué* le virtualenv. Une fois créé, celui-ci ne dépend plus de conda pour fonctionner. Et c'est précisément ce qu'on veut pour Docker — le conteneur final n'aura jamais entendu parler de conda.

Lance le `cat Pipfile` et dis-moi ce qu'il y a dedans.


_____________________________________________________________________________

Ce fichier est la « facture » de ton service web. Décortiquons-le, c'est court et chaque section compte.

**`[[source]]`** — où chercher les paquets. PyPI, le registre public standard. Rien à voir ici.

**`[packages]`** — les dépendances qui partiront dans l'image Docker :
- `scikit-learn = "==1.0.2"` — épinglé au strict, pour matcher le pickle. Confirmation de ce qu'on a trouvé avec `strings`.
- `flask = "*"` — le `*` signifie « la plus récente ». C'est acceptable ici parce que le `Pipfile.lock` fige de toute façon la version exacte.
- `gunicorn = "*"` — un serveur WSGI de production. Le serveur intégré de Flask est mono-thread et affiche un avertissement en clair quand tu le lances : il est fait pour développer, pas pour encaisser du trafic. L'instructeur y viendra en fin de module.

**`[dev-packages]`** — `requests`, utilisé par `test.py` pour taper sur ton service. Le Dockerfile ne l'installera pas : on ne met pas les outils de test dans le conteneur livré.

**`[requires]`** — et voilà le point qui va te bloquer : `python_version = "3.9"`.

**Le vrai problème**

Ce n'est pas un caprice du Pipfile. scikit-learn 1.0.2 date de décembre 2021 et ne publie de wheels que jusqu'à Python 3.10. Sur Python 3.11, pip tenterait de compiler depuis les sources et échouerait. Tu as donc réellement besoin d'un interpréteur 3.9 (ou 3.10).

Regarde ce dont tu disposes :

```bash
ls /usr/bin/python3*
conda env list
```

Si aucun 3.9 n'apparaît, le plus simple est d'en fabriquer un avec conda — non pas pour y travailler, juste pour fournir l'interpréteur à pipenv :

```bash
conda create -n py39 python=3.9 -y
```

Puis récupère son chemin et passe-le explicitement à pipenv :

```bash
conda env list          # relève le chemin de py39
pipenv install --python /chemin/vers/py39/bin/python
```

Note bien : `pipenv install` **sans argument de paquet**. Il lit le `Pipfile.lock` déjà présent et reconstruit l'environnement à l'identique. Tu n'as rien à réinstaller à la main.

Une remarque sur l'enchaînement : tu utilises conda pour obtenir un Python 3.9, mais l'environnement final reste un virtualenv pipenv classique, indépendant. Conda ne sert ici que de fournisseur d'interpréteur. Un peu comme emprunter un moteur pour construire une voiture qui roulera ensuite toute seule.

Envoie-moi le résultat des deux premières commandes.

## setuop de l'environnement avec le bon python etc...

Non, ne rejoue pas la commande de l'instructeur. Lui partait d'un dossier vide et devait créer le `Pipfile`. Toi, tu l'as déjà — avec les versions exactes et un `Pipfile.lock`. Relancer `pipenv install scikit-learn==1.0.2 flask` ne ferait que réécrire ce qui existe, et risquerait de régénérer le lock file pour rien.

Il te manque une seule chose : **un interpréteur Python 3.9**. Ton Codespace n'a que du 3.12 système, et tes deux envs conda sont en 3.11/3.12.

Point important sur `--python=3.9` : ce drapeau demande à pipenv de *trouver* un Python 3.9 déjà présent sur la machine. Il ne l'installe pas. Chez l'instructeur ça marchait parce que son Anaconda embarquait un 3.9 (visible dans ta capture : `Using /home/ubuntu/anaconda3/bin/python3.9`). Chez toi, la commande échouerait.

**La marche à suivre**

```bash
conda create -n py39 python=3.9 -y
```

Puis, sans activer `py39` (on ne veut pas y travailler, juste emprunter son interpréteur) :

```bash
cd /workspaces/mlops-zoomcamp/04-deployment/web-service
pipenv install --dev --python /home/codespace/miniconda3/envs/py39/bin/python
```

Deux précisions sur cette commande :
- **aucun nom de paquet** : pipenv lit le `Pipfile.lock` et reconstruit l'environnement à l'identique.
- **`--dev`** : installe aussi `requests`, dont tu auras besoin pour lancer `test.py` depuis ta machine. Le Dockerfile, lui, l'omettra — c'est bien la distinction entre outillage de développement et contenu livré.

Ensuite, vérifie que tu as atterri au bon endroit :

```bash
pipenv shell
python -c "import sys, sklearn; print(sys.executable, sklearn.__version__)"
```

Tu dois voir un chemin dans `~/.local/share/virtualenvs/` et `1.0.2`. Ton prompt aura changé — tu n'es plus dans `mlopszoomcamp`, et c'est normal.

Si le lock file résiste (il a été généré sur une autre plateforme, ça arrive), replie-toi sur `pipenv install --dev --skip-lock` et on regardera ensemble.


Deux bonnes questions, et l'erreur est en fait très instructive. Reprenons dans l'ordre.

## Ce que fait `conda create -n py39 python=3.9 -y`

Exactement ce que tu dis. Conda télécharge un interpréteur Python 3.9 complet et le pose dans `/home/codespace/miniconda3/envs/py39/`. On ne travaillera jamais dedans — on s'en sert comme d'un **fournisseur de moteur**. C'est un détournement assumé de conda : il est ici le seul outil disponible dans ton Codespace capable de te procurer une version de Python que le système n'a pas.

## Ce que fait `pipenv install --dev --python <chemin>`

Le mot `install` est trompeur. Sans nom de paquet derrière, il ne signifie pas « ajoute quelque chose » mais **« matérialise l'environnement décrit par les fichiers présents »**. C'est une reconstruction, pas un ajout.

Deux étapes se sont enchaînées dans ta sortie :
1. création du virtualenv (`Successfully created virtual environment!`) — c'est là que le `--python` intervient
2. `Installing dependencies from Pipfile.lock (4bcd75)...` — la reconstruction proprement dite

**Comment pipenv trouve le `Pipfile.lock` ?** Il regarde dans le répertoire courant, puis remonte de parent en parent jusqu'à trouver un `Pipfile`. D'où l'importance du `cd` avant. Le nom du virtualenv créé, `web-service-ToH4o1-o`, est d'ailleurs révélateur : nom du dossier + empreinte de son chemin absolu. C'est ainsi que pipenv retrouve « son » environnement quand tu reviens dans ce dossier.

**Pourquoi le `.lock` et pas le `Pipfile` ?** Le `Pipfile` exprime des *intentions* (`flask = "*"`, soit « n'importe quelle version »). Le `.lock` contient le *résultat figé* de la résolution : versions exactes et empreintes SHA256. Tant que l'empreinte du Pipfile correspond à celle enregistrée dans le lock (`4bcd75`), pipenv installe depuis le lock. Les `--hash=sha256:...` qui inondent ton message d'erreur en sont la preuve visible — ce sont les empreintes de vérification, tirées du lock.

## L'erreur

Une seule ligne compte dans tout ce pavé :

```
This version of pip does not support python 3.9 (requires >=3.10)
```

Le virtualenv a bien été créé, mais il a été amorcé avec `pip==26.0.1`. Or pip 26 a abandonné le support de Python 3.9. Résultat : un environnement avec un pip qui refuse de démarrer. Rien n'a été installé.

La cause profonde : **Python 3.9 est en fin de vie depuis octobre 2025**. Le matériel du cours date de 2022, quand 3.9 était le choix par défaut. L'écosystème a avancé, pas le Pipfile. C'est un décalage que tu vas rencontrer souvent avec des cours MLOps — et savoir le diagnostiquer fait partie du métier.

## La solution : passer en Python 3.10

C'est la version la plus haute que scikit-learn 1.0.2 supporte (il publie des wheels jusqu'à `cp310`), et la plus basse que pip 26 accepte. La seule fenêtre qui reste ouverte.

```bash
pipenv --rm
conda create -n py310 python=3.10 -y
pipenv install --dev --python /home/codespace/miniconda3/envs/py310/bin/python
```

Le `pipenv --rm` supprime le virtualenv cassé — indispensable, sinon pipenv le réutilisera tel quel.

Si pipenv proteste parce que le `Pipfile` réclame `python_version = "3.9"`, corrige simplement cette ligne en `"3.10"`. Le `Pipfile` est un fichier texte ordinaire, fait pour être édité.

Ensuite, contrôle :

```bash
pipenv shell
python -c "import sys, sklearn; print(sys.executable, sklearn.__version__)"
```

Tu peux aussi supprimer `py39`, il ne servira plus : `conda env remove -n py39`.

_______________________________________________________________________________-

Deux questions qui touchent à des points réellement importants. Prenons-les dans l'ordre.

## Supprimer `py39`

Oui, tu peux — mais fais-le depuis un shell normal plutôt que depuis le subshell pipenv. Tape `exit` d'abord, puis :

```bash
conda env remove -n py39 -y
```

**En revanche, ne supprime surtout pas `py310`.** Et voici pourquoi, parce que c'est contre-intuitif.

Quand virtualenv crée un environnement, il ne copie pas tout Python. Il copie (ou lie) le binaire, mais la **bibliothèque standard reste à son emplacement d'origine**. Un fichier `pyvenv.cfg` dans le virtualenv contient une ligne `home = /home/codespace/miniconda3/envs/py310/bin` qui pointe vers la source. Supprime `py310`, et ton virtualenv perd sa stdlib — il devient inutilisable.

Tu peux vérifier :

```bash
cat /home/codespace/.local/share/virtualenvs/web-service-*/pyvenv.cfg
```

C'est d'ailleurs une différence notable avec Docker : dans le conteneur, tout sera autonome. Ici, ton virtualenv reste locataire de `py310`.

## `(web-service) (base)` : le point sensible

Voilà ce qui se passe. `pipenv shell` ne modifie pas ton shell actuel — il **lance un shell enfant**. Ce nouveau shell relit `~/.bashrc`, qui contient le hook d'initialisation de conda, lequel active automatiquement `base`. D'où le second préfixe.

Le problème potentiel n'est pas cosmétique : **conda a pu réinsérer son `bin/` en tête du PATH, devant celui du virtualenv**. Dans ce cas, `python` pointerait vers le Python 3.12 de `base`, pas vers ton 3.10 avec scikit-learn 1.0.2.

Vérifie immédiatement :

```bash
which python
python -c "import sys, sklearn; print(sys.executable, sklearn.__version__)"
```

(Ta commande précédente n'a pas donné de résultat visible : elle a été avalée au moment où le subshell démarrait. Relance-la.)

Tu dois voir un chemin contenant `.local/share/virtualenvs/web-service-...` et `1.0.2`. Si tu vois `miniconda3` à la place, c'est que conda est passé devant.

**Le contournement propre** — et c'est ce que je te recommande d'adopter comme réflexe : évite `pipenv shell`, utilise `pipenv run`.

```bash
pipenv run python predict.py
pipenv run python -c "import sklearn; print(sklearn.__version__)"
```

`pipenv run` exécute une commande unique dans le bon environnement, sans lancer de subshell, donc sans donner à conda l'occasion de s'interposer. C'est aussi la forme que tu verras dans les scripts et les Dockerfiles.

## Dernier détail à régler

Le warning est légitime : ton `Pipfile` réclame toujours 3.9. Corrige-le, sinon il te suivra à chaque commande :

```bash
exit                                    # sortir du subshell
sed -i 's/python_version = "3.9"/python_version = "3.10"/' Pipfile
cat Pipfile
```

Envoie-moi le résultat du `which python` — c'est lui qui nous dira si l'environnement est réellement opérationnel.