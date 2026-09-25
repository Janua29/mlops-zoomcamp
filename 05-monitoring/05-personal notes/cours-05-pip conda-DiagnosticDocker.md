# Cours : pip dans conda, et diagnostic réseau Docker (Adminer ↔ Postgres)

---

## Partie 1 — Installer avec pip dans un environnement conda

### 1.1 Le point de départ

Le `requirements.txt` du module n'épingle pas pandas. `pip install -r requirements.txt` a donc installé la dernière version, pandas 3. Or Evidently 0.6.7 utilise en interne l'alias de fréquence `"H"`, que pandas 3 a supprimé (remplacé par `"h"`). Il fallait revenir à `pandas<3`, et la question s'est posée : avec pip ou avec conda ?

### 1.2 Ce qu'est vraiment un environnement conda

Un environnement conda est **un dossier** :

```
~/miniconda3/envs/py11-taximonitoring/
├── bin/
│   ├── python        ← son propre interpréteur Python
│   └── pip           ← son propre pip
├── lib/python3.11/site-packages/   ← là où vivent les paquets installés
└── conda-meta/       ← le registre de conda : ce qu'il a installé lui-même
```

`conda activate py11-taximonitoring` ne fait qu'une chose essentielle : placer ce `bin/` **en tête du PATH**, la liste des dossiers où le shell cherche les commandes. Dès lors, `python` et `pip` désignent ceux de l'environnement.

Voilà pourquoi pip fonctionne dans un environnement conda : **conda crée le contenant, et pip peut le remplir.** Les deux écrivent dans le même `site-packages`.

Pour vérifier que tu es au bon endroit :

```bash
which python              # → ~/miniconda3/envs/py11-taximonitoring/bin/python
python -m pip --version   # → pip 24.x from ~/miniconda3/envs/py11-taximonitoring/lib/python3.11/site-packages/pip
```

Si le chemin affiché ne contient pas `envs/py11-taximonitoring`, tu installes au mauvais endroit : c'est encore la question du « où ».

### 1.3 Pourquoi `python -m pip` plutôt que `pip`

`python -m <module>` signifie : « avec **ce** Python, exécute tel module ». Tu as donc la garantie que le pip utilisé appartient au Python que tu utilises. Avec `pip` tout seul, un PATH mal configuré peut faire tourner un autre pip que celui que tu crois.

`python -m conda`, en revanche, ne marche pas. Conda n'est pas un module de ton environnement Python : c'est un programme séparé, installé dans l'environnement `base`. On l'appelle directement : `conda install ...`.

### 1.4 Quel installateur choisir

**La règle : réinstaller un paquet avec l'outil qui l'a installé.**

Pour le savoir :

```bash
conda list pandas
```

| Colonne *Channel* | Installé par | Commande |
|---|---|---|
| `pypi` | pip | `python -m pip install "pandas<3"` |
| `conda-forge`, `defaults`… | conda | `conda install "pandas<3"` |

**Pourquoi ne pas mélanger ?** Conda tient son propre registre (`conda-meta/`), et pip ne le met pas à jour. Si pip change pandas dans le dos de conda, conda croit toujours avoir sa version à lui. Le jour où tu installes avec conda un paquet qui dépend de pandas, il peut écraser la version de pip ou en réinstaller une autre, et l'environnement devient incohérent. C'est le même problème de cohérence que Pipfile / Pipfile.lock au module 04 : deux sources de vérité qui divergent.

### 1.5 Deux détails qui font planter

- **Les guillemets dans `"pandas<3"`.** Sans eux, le shell lit `<` comme une redirection (« lis le contenu du fichier nommé `3` ») et pip ne reçoit jamais la contrainte de version.
- **Le redémarrage du kernel.** Le kernel Jupyter a chargé pandas 3 **en mémoire** au premier `import`. Changer la version sur le disque n'affecte pas un processus déjà lancé. C'est le même principe que `set_tracking_uri()` avec MLflow.

### 1.6 Pour que ça ne se reproduise pas

Épingle la contrainte dans `requirements.txt` :

```
pandas<3
```

---

## Partie 2 — Le diagnostic Adminer ↔ Postgres

### 2.1 L'architecture en jeu

```
Hôte Codespaces
│
├── script Python ── localhost:5432 ──► port publié ──► db            ✅ chemin 1
│
├── réseau back-tier (172.19.0.0/16)
│     ├── db        172.19.0.4
│     ├── adminer   ── db:5432 ──────────────────────► db            ❌ chemin 2
│     └── grafana
│
└── réseau front-tier (172.18.0.0/16)
      ├── adminer
      └── grafana
```

Il existe **deux chemins** pour atteindre Postgres. Le chemin 1 part de l'hôte et passe par le port publié. Le chemin 2 va d'un conteneur à l'autre, par le réseau interne de Docker.

### 2.2 Lire le message d'erreur mot par mot

```
connection to server at "db" (172.19.0.4), port 5432 failed: timeout expired
```

- `"db" (172.19.0.4)` : le nom a été traduit en adresse IP, donc **le DNS interne de Docker fonctionne**.
- `timeout expired` : Adminer a envoyé des paquets et n'a **jamais reçu de réponse**.

Le type d'erreur indique jusqu'où la connexion est allée :

| Message | Ce qui s'est passé | Où chercher |
|---|---|---|
| `timeout expired` | Les paquets se perdent, personne ne répond | Réseau, pare-feu |
| `connection refused` | La machine répond « personne n'écoute sur ce port » | Service arrêté, mauvais port |
| `password authentication failed` | Postgres a été atteint, mais les identifiants sont faux | Utilisateur, mot de passe |
| `database "x" does not exist` | Postgres atteint et connexion acceptée, mauvais nom de base | Nom de la base |

**Principe : plus l'erreur arrive tard, plus le chemin a fonctionné longtemps.** Un timeout est l'erreur la plus « précoce » : on n'a même pas atteint Postgres.

### 2.3 L'observation clé : partir de ce qui marche

Ton script affichait `data sent` toutes les 10 secondes. Donc **Postgres était vivant et acceptait les connexions** par le chemin 1. Le problème ne pouvait se trouver que sur le chemin 2. Ce seul constat a éliminé la moitié des pistes.

### 2.4 Les pistes explorées, dans l'ordre

On est allé du moins coûteux au plus coûteux, en ne changeant qu'une chose à la fois :

| # | Hypothèse | Test | Résultat | Conclusion |
|---|---|---|---|---|
| 1 | Adminer est dans un état bizarre | `docker compose restart adminer` | ❌ | Ce n'est pas l'état d'Adminer |
| 2 | Adminer vise une IP périmée | `docker inspect` → IP de `db` | 172.19.0.4, la bonne | L'adresse est correcte, rien ne répond |
| 3 | Réseaux Docker abîmés par la mise en veille | `docker compose down` / `up -d` | ❌ (logs : 30 s entre la demande et le `403`) | Même avec des réseaux neufs, ça bloque |
| 4 | Problème propre à Adminer ? | Conteneur jetable : `pg_isready -h db` | `no response` | **Aucun** conteneur ne joint `db` : Adminer est hors de cause |
| 5 | Le chemin via l'hôte est-il ouvert ? | `pg_isready -h 172.19.0.1` | `accepting connections` | Conteneur → hôte fonctionne |
| 6 | Le pare-feu bloque conteneur → conteneur | `sudo iptables -S FORWARD` | `ACCEPT` **+ un avertissement** | L'avertissement mène à la cause |
| 7 | L'ancien pare-feu refuse `FORWARD` | `sudo iptables-legacy -S FORWARD` | Politique `DROP` | **Cause trouvée** |

Deux remarques de méthode sur ce tableau :

- **Le test 4 est le tournant.** Le conteneur jetable reproduit la situation d'Adminer (même réseau, même cible) sans Adminer. Quand il échoue aussi, on sait qu'il faut chercher dans le réseau, pas dans l'application. C'est la technique de l'**isolation** : retirer un élément suspect pour voir si le problème persiste.
- **`db:5432 - no response` était un test réussi.** Le conteneur s'est bien lancé ; c'est sa réponse qui était négative. Il faut distinguer « la commande a échoué » de « la commande a répondu non ».

### 2.5 Un point resté ouvert

Le test 5 a réussi depuis le conteneur jetable, mais `172.19.0.1` a échoué depuis Adminer. Je n'ai pas d'explication certaine. La piste la plus probable : Adminer est branché sur **deux** réseaux, contrairement au conteneur jetable, et ses paquets n'empruntent pas le même chemin. Comme la vraie cause a été corrigée entre-temps, on ne l'a pas creusé.

La leçon : **un contournement validé sur un conteneur de test ne vaut que si le test reproduit fidèlement les conditions réelles**, ici la configuration réseau.

### 2.6 Les deux vigiles

Dans le noyau Linux, le filtrage réseau s'appelle **netfilter**. Deux outils permettent d'y écrire des règles :

| Outil | Âge | Qui l'utilisait chez toi |
|---|---|---|
| `iptables-legacy` | L'ancien système | L'installation Codespaces (docker-in-docker) |
| `iptables` (variante nft, basée sur nftables) | Le nouveau système | Docker 29 |

Les deux jeux de règles sont **actifs en même temps**, et un paquet doit être accepté par les deux. D'où l'image des deux vigiles à la même porte, chacun avec sa propre liste. Docker ne parlait qu'au nouveau vigile, qui laissait tout passer (`-P FORWARD ACCEPT`). L'ancien avait pour consigne par défaut de **tout refuser** sur `FORWARD`.

Pourquoi seul le trafic entre conteneurs était bloqué ? Parce que chaque type de trafic traverse des « chaînes » différentes du pare-feu :

| Trafic | Chaîne traversée | Bloqué par `FORWARD DROP` ? |
|---|---|---|
| Script (hôte) → `db` | Sortie de l'hôte (`OUTPUT`) | Non ✅ |
| Conteneur → hôte (`172.19.0.1`) | Entrée de l'hôte (`INPUT`) | Non ✅ |
| Conteneur → conteneur (Adminer → `db`) | Transit (`FORWARD`) | **Oui ❌** |

Tout le puzzle s'explique ainsi. Et c'est pour ça que `docker compose down` / `up` n'a rien changé : Docker a recréé proprement **ses** règles, côté nouveau vigile, sans toucher à celles de l'ancien, qu'il ne gère pas.

Une leçon de plus : **la cause était annoncée dans un avertissement** (`Warning: iptables-legacy tables present…`). Les avertissements sont des données, pas du bruit.

### 2.7 La solution

```bash
sudo iptables-legacy -P FORWARD ACCEPT
```

- `-P` : définit la **politique** (*policy*), c'est-à-dire ce qui s'applique aux paquets qu'aucune règle n'a traités.
- `FORWARD` : la chaîne du trafic en transit, celui qui passe entre conteneurs.
- `ACCEPT` : laisser passer.

Ce réglage **n'est pas persistant** : les règles de pare-feu vivent en mémoire et un redémarrage du Codespace les réinitialise. Hypothèse probable pour la panne d'aujourd'hui : la sortie de veille a remis la règle `DROP` en place.

**Réflexe après une mise en veille**, si des conteneurs ne se parlent plus :

```bash
# 1. Diagnostic
docker run --rm --network 05-monitoring_back-tier postgres pg_isready -h db -t 5

# 2. Si "no response" : vérifier l'ancien vigile
sudo iptables-legacy -S FORWARD

# 3. Si "-P FORWARD DROP" : corriger
sudo iptables-legacy -P FORWARD ACCEPT
```

### 2.8 Ce qu'il faut retenir de la méthode

1. **Lire l'erreur mot par mot**, et savoir quel type d'erreur correspond à quelle étape du chemin.
2. **Partir de ce qui marche** : le script a immédiatement innocenté Postgres.
3. **Aller du moins coûteux au plus coûteux**, un changement à la fois.
4. **Isoler avec un test minimal** : le conteneur jetable a sorti Adminer de l'équation.
5. **Distinguer « la commande a échoué » de « la commande a répondu non ».**
6. **Lire les avertissements.**
7. **Quoi vs où** : Postgres et Adminer fonctionnaient ; c'est le chemin entre eux qui était cassé.

---

## Partie 3 — Vérifie ta compréhension

1. Ton prompt affiche `(base)` et tu tapes `python -m pip install requests`. Dans quel environnement `requests` s'installe-t-il ?
2. Demain, Adminer affiche `password authentication failed`. Le problème de pare-feu est-il revenu ?
3. Après une mise en veille, ton script fonctionne mais Grafana n'arrive plus à joindre `db`. Quel est ton premier test ?
4. Pourquoi `docker compose down` / `up -d` n'a-t-il pas corrigé le problème ?

**Réponses**

1. Dans `base`. `python` désigne le Python de l'environnement actif, et `-m pip` utilise le pip de ce Python-là.
2. Non. Cette erreur signifie que Postgres a été atteint : le réseau fonctionne, ce sont les identifiants qui posent problème.
3. Le conteneur jetable `pg_isready -h db` sur le réseau `back-tier`. S'il répond `no response`, on passe à `iptables-legacy`.
4. Docker recrée ses réseaux et ses règles côté nftables, le nouveau vigile, mais ne touche pas aux règles `iptables-legacy`, l'ancien vigile, où se trouvait la politique `DROP`.

---

Si tu veux, je peux mettre ce cours dans un fichier `.md`, comme celui sur le notebook baseline.