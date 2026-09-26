# Savuegarder un dashboard grafana

Tu as bien compris le principe général. Il y a une nuance importante sur `stop` que je corrige d'abord, parce que tout le reste en découle.

---

## 1. Où va un dashboard quand tu cliques sur « Save » dans l'UI Grafana ?

Grafana a sa **propre base de données interne**, distincte de ton PostgreSQL. Par défaut, c'est un fichier SQLite situé **dans le container** : `/var/lib/grafana/grafana.db`. Quand tu cliques sur *Save*, le dashboard est écrit dans ce fichier.

Aucun volume n'est monté sur `/var/lib/grafana` dans ton `docker-compose.yml`. Ce fichier vit donc dans la **couche inscriptible du container**. C'est bien ton intuition.

**Correction importante** : la couche inscriptible **survit à `docker compose stop`**. C'est la distinction `stop` / `down` que tu as déjà rencontrée. Un container arrêté garde sa couche inscriptible. Un container **supprimé** la perd.

| Commande | Le container est… | Dashboards sauvés via l'UI |
|---|---|---|
| `docker compose stop` puis `start` | arrêté puis relancé | ✅ conservés |
| `docker compose restart` | redémarré | ✅ conservés |
| `docker compose down` puis `up` | **supprimé** puis recréé | ❌ perdus |
| `docker compose up` après avoir **modifié le service** dans le YAML | **recréé** automatiquement | ❌ perdus |

La dernière ligne est le piège le plus sournois. Compose compare la définition du service à celle du container existant. Si tu as changé quelque chose, par exemple ajouté des lignes `volumes:`, il **détruit et recrée** le container sans te prévenir. C'est probablement ce qui arrive dans la vidéo : on ajoute les volumes, on relance, et les dashboards créés à la main disparaissent.

### Deux façons de résoudre le problème

| Approche | Principe | Avantage | Limite |
|---|---|---|---|
| Volume nommé sur `/var/lib/grafana` | On rend persistante la base interne de Grafana | Tout ce que tu fais dans l'UI est conservé | Le dashboard reste enfermé dans un fichier binaire, sur une seule machine |
| **Provisioning** (choix du cours) | On décrit le dashboard dans des **fichiers texte** que Grafana charge au démarrage | Versionné dans Git, reproductible partout. Un collègue qui clone le repo obtient le même dashboard. | Modifier le dashboard demande de mettre à jour le fichier |

La vraie motivation de l'instructrice va donc au-delà de « survivre à un redémarrage ». C'est le principe du **dashboard *as code***, le même que l'*infrastructure as code* : ce qui compte doit exister sous forme de fichier dans le repo.

---

## 2. Pourquoi deux fichiers ? `data_drift.json` ne suffit-il pas ?

### L'analogie de la bibliothèque

- `data_drift.json` est **le livre** : le contenu du dashboard (panneaux, requêtes SQL, couleurs, axes).
- `grafana_dashboards.yaml` est **la consigne donnée au bibliothécaire** : « va chercher les livres sur telle étagère, range-les dans tel rayon, et repasse toutes les 10 secondes voir s'il y en a de nouveaux ».

Un livre ne dit pas sur quelle étagère il est rangé. De même, le JSON ne contient **aucune information sur la façon de le charger**.

### Pourquoi Grafana ne lit-il pas directement le JSON ?

Au démarrage, Grafana ne fouille qu'**un seul endroit** : `/etc/grafana/provisioning/`, avec un sous-dossier par type de ressource.

```
/etc/grafana/provisioning/
├── datasources/   ← "à quelles bases de données je me connecte ?"
├── dashboards/    ← "où sont les fichiers de dashboards, et comment les traiter ?"
├── alerting/
└── plugins/
```

Dans `dashboards/`, Grafana attend des **YAML de configuration**, pas des dashboards. Ce YAML déclare un *provider* (un fournisseur de dashboards). C'est lui qui indique où se trouvent les JSON :

```yaml
apiVersion: 1
providers:
  - name: 'Evidently Dashboards'
    orgId: 1
    folder: ''
    type: file                    # les dashboards viennent de fichiers
    disableDeletion: false
    updateIntervalSeconds: 10     # re-scanne le dossier toutes les 10 s
    allowUiUpdates: false         # interdit de sauver les modifs depuis l'UI
    options:
      path: /opt/grafana/dashboards        # ← l'étagère
      foldersFromFilesStructure: true      # sous-dossiers → dossiers Grafana
```

Séparer les deux fichiers apporte trois avantages :

1. **Un provider, N dashboards.** Tu écris la consigne une fois. Ensuite tu ajoutes autant de JSON que tu veux.
2. **Le JSON reste portable.** C'est exactement le format que Grafana produit quand tu exportes un dashboard. Tu peux aussi l'importer à la main dans n'importe quel autre Grafana.
3. **Séparation des responsabilités.** C'est le même schéma que pour `grafana_datasources.yaml`, qui décrit la connexion à PostgreSQL sans rien dire des dashboards.

### Où trouver les « templates » ?

- **Pour le YAML** : dans la documentation officielle de Grafana, page *Provision Grafana*, section *Dashboards* (grafana.com/docs/grafana/latest/administration/provisioning/). Le fichier du cours en est une copie presque conforme. Les commentaires du type `# <string> an unique provider name` viennent directement de l'exemple de la doc. C'est pour ça que l'instructrice parle de fichier « par défaut ».
- **Pour le JSON** : on ne l'écrit jamais à la main. On construit le dashboard dans l'UI, puis on l'exporte : icône *Share/Export* → *Export* → *Export as JSON*, ou bien *Dashboard settings* → *JSON Model*.

> ⚠️ **Piège à l'export** : n'active pas l'option *Export for sharing externally*. Elle remplace la datasource par des variables `${DS_...}` que le provisioning ne sait pas résoudre. Tu obtiendrais des panneaux vides.

---

## 3. La syntaxe des volumes : `SOURCE:CIBLE:MODE`

```
./config/grafana_datasources.yaml : /etc/grafana/provisioning/datasources/datasource.yaml : ro
└───────────── SOURCE ──────────┘   └──────────────────── CIBLE ───────────────────────┘   └MODE┘
   chemin dans ta Codespace            chemin DANS le container                             lecture seule
```

Un container a son **propre système de fichiers**, isolé de celui de ta Codespace. Un *bind mount* ouvre une fenêtre entre les deux : le fichier de gauche **apparaît** à l'emplacement de droite, à l'intérieur du container. Il n'y a pas de copie. C'est le même fichier, vu depuis deux endroits.

| Morceau | Signification |
|---|---|
| `./config/...` | Chemin **relatif au dossier du `docker-compose.yml`** |
| `/etc/grafana/provisioning/datasources/` | Le dossier que Grafana scanne au démarrage. C'est une **convention imposée par Grafana**. |
| `datasource.yaml` | Le nom du fichier **vu depuis le container**. Il change ici (`grafana_datasources.yaml` devient `datasource.yaml`) et ça n'a aucune importance : Grafana lit **tous** les `.yaml` du dossier. |
| `:ro` | *read-only* : le container peut lire le fichier mais pas le modifier. C'est une bonne pratique pour la configuration. |

La logique est la même pour `grafana_dashboards.yaml`, qui atterrit dans `provisioning/dashboards/`.

### Chemin imposé ou chemin choisi ?

C'est le point qui relie tout :

| Cible dans le container | Qui décide ? |
|---|---|
| `/etc/grafana/provisioning/datasources/` | **Grafana**. Tu dois utiliser ce chemin. |
| `/etc/grafana/provisioning/dashboards/` | **Grafana**. Tu dois utiliser ce chemin. |
| `/opt/grafana/dashboards` | **Toi**. Il est arbitraire. Tu aurais pu écrire `/mes/tableaux`. |

La seule contrainte sur le troisième : il doit être **identique** au `path:` du provider. La chaîne complète est donc :

```
docker-compose.yml
  │ monte ./config/grafana_dashboards.yaml
  ▼
/etc/grafana/provisioning/dashboards/dashboards.yaml   ← Grafana le trouve (chemin imposé)
  │ contient : path: /opt/grafana/dashboards
  ▼
/opt/grafana/dashboards/                               ← chemin choisi, doit correspondre
  │ monté depuis ./dashboards (docker-compose.yml)
  ▼
data_drift.json                                        ← le dashboard est chargé
```

Si tu changes le chemin à un seul des deux endroits, Grafana démarre sans erreur visible, mais sans dashboard.

---

## 4. Pourquoi monter un dossier pour les dashboards, et des fichiers pour les YAML ?

**Pour les dashboards, un dossier est le plus pratique :**

1. **Le provider pointe vers un dossier** et charge tous les `.json` qu'il contient. Pour ajouter un dashboard, tu déposes un fichier dans `./dashboards`, sans toucher au `docker-compose.yml`. Grafana le détecte dans les 10 secondes (`updateIntervalSeconds`).
2. **`foldersFromFilesStructure: true`** transforme tes sous-dossiers en dossiers Grafana. `./dashboards/drift/…` devient un dossier « drift » dans l'UI.
3. **Point d'expert** : un bind mount sur un **fichier unique** est fragile. Beaucoup d'éditeurs, dont VS Code parfois, sauvegardent en écrivant un nouveau fichier qui remplace l'ancien. Le container reste alors accroché à l'ancienne version et ne voit pas tes modifications. Monter le **dossier** évite ce problème, ce qui compte pour des fichiers qu'on modifie souvent comme les dashboards.

**Pour les YAML, on monte fichier par fichier** parce que les deux fichiers sont dans le même dossier local `./config`, mais doivent atterrir dans **deux dossiers différents** du container (`datasources/` et `dashboards/`). Monter `./config` en entier ne permettrait pas cette répartition.

---

## 5. Conséquence pratique : comment modifier un dashboard « provisionné »

Avec `allowUiUpdates: false`, si tu modifies le dashboard dans l'UI et cliques *Save*, Grafana refuse : un dashboard provisionné est « possédé » par son fichier. Il te propose de copier le JSON. Le flux de travail devient :

```
modifier dans l'UI  →  exporter le JSON  →  remplacer ./dashboards/data_drift.json  →  (git commit)
```

Grafana recharge le fichier tout seul.

> 💡 Si un jour tu obtiens « *Datasource … was not found* » sur tes panneaux : le JSON référence la datasource par un identifiant (`uid`). Si ce `uid` n'est pas fixé dans `grafana_datasources.yaml`, Grafana en génère un nouveau à chaque recréation du container, et le JSON pointe dans le vide. La solution est d'ajouter une ligne `uid: ...` fixe dans la déclaration de la datasource.

---

## Questions pour vérifier ta compréhension

1. Tu crées un dashboard dans l'UI **sans provisioning**, tu fais `docker compose stop` puis `docker compose start`. Le dashboard est-il toujours là ? Et si tu avais fait `down` / `up` ?
2. Tu veux ranger ton dashboard dans `/data/grafana` au lieu de `/opt/grafana/dashboards`. Quels **deux** endroits dois-tu modifier ?
3. Pourquoi ne pourrait-on pas renommer la cible `/etc/grafana/provisioning/datasources/` en `/etc/grafana/mes_sources/` sans configuration supplémentaire ?

Si tu veux, je peux te faire une fiche récapitulative sur le provisioning Grafana, dans le même format que ta fiche sur le notebook baseline.

**My answer**

1. avec docker compose stop puis up --> le dashboard est tours là. Par contre si je fais docker compose down ou docker compose start, il s'efface
2. je dois changer le chemin dans grafana_dashboard.yaml et dans le docker-compose.yaml
3. par ce que par défaut grafana est configuré pour aller chercher les provider (fichier Yaml indiquant où sont els data source) dans /etc/grafana/provisioning/datasources/

**Claude answer**

Deux réponses sur trois sont justes, et la troisième ne demande qu'une petite correction.

## 1. Presque, mais il y a une confusion sur `start`

`docker compose start` ne supprime rien. Il relance un container **arrêté**, avec sa couche inscriptible intacte. C'est l'inverse de `stop`.

La seule commande qui efface ici, c'est `down`, parce qu'elle **supprime** le container.

| Séquence | Résultat |
|---|---|
| `stop` → `start` | ✅ dashboard conservé (même container, remis en marche) |
| `stop` → `up` | ✅ conservé, **à condition** de ne pas avoir modifié le service dans le YAML. Sinon Compose recrée le container. |
| `down` → `up` | ❌ perdu (container supprimé, puis un neuf est créé) |
| `down` → `start` | ⚠️ ne fait rien : il n'existe plus de container à démarrer, Compose te le signale |

Pour t'en souvenir, pense aux paires de verbes :

- **`stop` / `start`** : mettre en pause et reprendre. On ne touche pas au container.
- **`down` / `up`** : détruire et construire. Le container repart de zéro, à partir de l'image.

(`up` est un peu hybride : si un container existe déjà et que sa définition n'a pas changé, il le réutilise simplement.)

## 2. ✅ Exact

Pour être précis sur les deux endroits :

- dans `config/grafana_dashboards.yaml` : la ligne `path:` sous `options:` ;
- dans `docker-compose.yml` : **la partie droite** de `./dashboards:/opt/grafana/dashboards`.

La partie gauche (`./dashboards`) ne change pas. C'est ton dossier local, et il n'a rien à voir avec l'emplacement dans le container.

## 3. ✅ Le raisonnement est juste, avec une nuance de vocabulaire

Oui, c'est une **convention par défaut** de Grafana. Deux précisions pour passer au niveau supérieur :

**a) Le fichier datasource n'indique pas « où sont » les datasources, il les définit.** Le mot *provider* s'applique au YAML des **dashboards** :

| Fichier | Rôle |
|---|---|
| `grafana_datasources.yaml` | **est** la déclaration de la datasource : type PostgreSQL, adresse `db:5432`, utilisateur, mot de passe… Il n'y a pas d'étape intermédiaire. |
| `grafana_dashboards.yaml` | déclare un **provider** : il dit **où aller chercher** les dashboards (les JSON). Il y a une indirection. |

Cette asymétrie explique pourquoi on a deux fichiers pour les dashboards et un seul pour la datasource. Une connexion à une base tient en quelques lignes de YAML. Un dashboard, avec ses dizaines de panneaux, est un gros document JSON qu'on préfère garder à part.

**b) « Par défaut » veut dire que c'est modifiable.** La racine `/etc/grafana/provisioning` est un réglage de Grafana. On peut la changer avec la variable d'environnement `GF_PATHS_PROVISIONING` dans le `docker-compose.yml`. En revanche, les noms des sous-dossiers (`datasources/`, `dashboards/`…) sont **codés en dur** dans Grafana.

Donc, pour ta question : `/etc/grafana/mes_sources/` ne marcherait jamais, même avec de la configuration, parce que le nom `datasources` est imposé. Par contre `/mon/provisioning/datasources/` fonctionnerait avec `GF_PATHS_PROVISIONING=/mon/provisioning`.

---

Une dernière question pour ancrer le point 1 :

> Tu ajoutes une ligne `environment: - GF_PATHS_PROVISIONING=/mon/provisioning` au service Grafana, sans provisioning des dashboards et avec un dashboard créé à la main dans l'UI. Tu lances `docker compose up -d`. Que devient ton dashboard, et pourquoi ?