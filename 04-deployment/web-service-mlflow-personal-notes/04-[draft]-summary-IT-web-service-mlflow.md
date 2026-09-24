# AWS S3 bucket vs trakcing server (mlflow) : what is the diffrence ?

**Question**

Question : l'instructeur dit qu'avec ce qu'on a fait, on se passe du tracking server (c'est bien MLFlow?)
Si j'ai bien compris c'est grâce au load_model dans predict.py : on charge le.model une fois au démarrage et comme.tu l'as indiqué, ensuite ce modèle vit dans le processus, donc on n'a plus besoin du tracking server. C'est bien ça ?

**Answer**

Ton observation est juste — le modèle vit bien en mémoire après le chargement — mais ce n'est pas ce que veut dire l'instructeur. Il y a un décalage entre ton setup et le sien.

## Ce que tu décris : « on s'en passe pendant l'exécution »

Vrai. Le `load_model` est au niveau du module, donc exécuté une fois au démarrage. Ensuite le modèle est en RAM, et les requêtes n'entraînent aucun appel à MLflow. Tu peux éteindre le serveur de tracking après le démarrage, ton service continuera à prédire.

Mais ça reste insuffisant : **au prochain redémarrage, il faudra que MLflow soit là**. Or un service redémarre constamment — déploiement, crash, montée en charge, redémarrage machine. Un service qui ne peut pas redémarrer sans MLflow dépend toujours de MLflow. La dépendance n'est pas éliminée, elle est juste décalée dans le temps.

## Ce que veut dire l'instructeur : « on s'en passe même au démarrage »

Compare les deux URI :

```python
# Ton cas
mlflow.set_tracking_uri("http://127.0.0.1:5000")
MODEL_URI = 'models:/m-5e276730...'
```

```python
# Le cas de l'instructeur — pas de set_tracking_uri
MODEL_URI = 's3://mlflow-models-alexey/1/<run_id>/artifacts/model'
```

La différence est dans la nature de l'adresse :

| | `models:/m-...` | `s3://bucket/...` |
|---|---|---|
| Type | référence **indirecte** | adresse **complète** |
| Étape supplémentaire | demander au serveur « où est ce modèle ? » | aucune |
| Tracking server au démarrage | **obligatoire** | **inutile** |

Avec `models:/`, MLflow ne sait pas où est le fichier. Il doit interroger le serveur, qui consulte sa base de données et répond avec le chemin réel. Le serveur est un **annuaire** indispensable.

Avec `s3://`, l'adresse contient déjà tout. La bibliothèque MLflow va chercher le fichier directement sur S3. Elle n'a besoin d'aucun serveur — juste des droits d'accès au stockage.

C'est pour ça qu'Alexey écrit un chemin S3 en dur : ce n'est pas du bricolage, c'est **le point du chapitre**.

## Le schéma mental

```
Ton setup  : service → serveur MLflow → stockage → modèle
Son setup  : service ──────────────────→ stockage → modèle
```

On supprime un maillon. Chaque maillon retiré est un point de panne en moins.

## Pourquoi c'est important en production

Le serveur MLflow est un outil de **data scientist** : lancer des expériences, comparer des runs, explorer l'UI. Il n'est pas conçu pour être dans le chemin critique d'un service de production.

S'il est nécessaire au démarrage, alors : MLflow tombe → aucun de tes services ne peut redémarrer → tu ne peux plus déployer ni encaisser un incident. Un outil d'exploration devient une infrastructure critique. C'est un mauvais couplage.

## Ta contrepartie

Tu n'as pas de bucket S3, et le cours ne te demande pas d'en créer un. Ton `models:/` est le bon choix pédagogique — mais garde en tête que **tu conserves la dépendance au démarrage**.

Petit exercice de vérification, qui vaut mieux qu'une explication :

1. Ton service tourne, `test.py` fonctionne
2. Arrête MLflow (Ctrl+C dans le terminal 1)
3. Relance `test.py` → **ça marche encore** (ton point : le modèle est en mémoire)
4. Arrête le service et relance `python predict.py` → **ça plante** (le point de l'instructeur)

Cinq minutes, et tu auras la distinction gravée.


**Question**

Quand tu parles du service, tu parles bien du web service créé avec flask ?
Si oui, comment faire pour l'arrêter ?

**Answer**

Oui, exactement. « Le service », c'est le processus lancé par `python predict.py` (ou par gunicorn) — celui qui écoute sur le port 9696.

## Pour l'arrêter

Va dans le **terminal 2**, celui où tu l'as lancé et où il occupe l'affichage, puis :

```
Ctrl+C
```

C'est `Ctrl` sur Mac aussi, pas `Cmd` — les raccourcis de terminal suivent la convention Unix.

Tu récupères ton invite de commande, et le port 9696 est libéré. Même méthode pour MLflow dans le terminal 1.

## Ce que fait vraiment Ctrl+C

Ce n'est pas un « bouton stop » : c'est l'envoi d'un **signal** au processus, appelé `SIGINT` (*signal interrupt*). Le système dit poliment au programme : « on te demande de t'arrêter ». Le programme peut alors fermer proprement ses connexions avant de quitter.

Bon à savoir pour la suite : c'est ce même signal qui pose problème dans un conteneur Docker mal configuré, où il n'atteint parfois pas le bon processus.

## Si jamais ça résiste

Rare avec Flask, mais utile à connaître. Depuis un **autre** terminal :

```bash
lsof -i :9696     # qui occupe le port ?
kill <PID>        # demande d'arrêt
kill -9 <PID>     # arrêt forcé, en dernier recours
```

Le `-9` envoie `SIGKILL`, que le processus ne peut pas intercepter : il est tué net, sans possibilité de fermer quoi que ce soit. À réserver aux cas désespérés.

## Une remarque sur ton test

Un détail va t'intéresser à l'étape 4. Tu as lancé avec `app.run(debug=True, ...)`. Le mode debug active le **rechargement automatique** : Flask surveille tes fichiers et redémarre tout seul dès que tu en sauvegardes un.

Conséquence : si tu modifies `predict.py` pendant que MLflow est éteint, Flask va tenter de redémarrer, échouera à charger le modèle, et tu verras l'erreur apparaître **sans avoir rien relancé toi-même**. Ce n'est pas un bug — c'est même une démonstration gratuite de ce que tu cherches à prouver.