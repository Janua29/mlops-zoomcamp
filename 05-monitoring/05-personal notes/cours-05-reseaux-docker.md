# MLOps Zoomcamp — Module 05 : les réseaux Docker (`front-tier`, `back-tier`)

> Complément du cours `cours-05-overview-architecture.md` (§4.5 et §5.2).
> Question de départ : dans `docker-compose.yml`, le formateur déclare deux « réseaux », `front-tier` et `back-tier`. Est-ce vraiment des réseaux ? Combien en faut-il ? Qui décide quel service va dans quel réseau ?

---

## 1. Ce sont vraiment des réseaux ?

Oui : ce sont des **réseaux virtuels**. Ils n'existent que sous forme logicielle, mais se comportent comme de vrais réseaux. Pour chaque réseau déclaré, Docker crée dans la VM :

| Élément créé | Rôle | Équivalent physique |
|---|---|---|
| Un **commutateur virtuel** (*bridge*) | Relie entre eux les conteneurs du réseau | La box à laquelle on branche des appareils |
| Une **plage d'adresses IP** (ex. `172.18.0.0/16`) | Espace d'adresses propre au réseau | Les adresses `192.168.1.x` de ta box |
| Une **carte réseau virtuelle** par conteneur rattaché, avec une IP dans la plage | Branche le conteneur sur le réseau | Le câble ou le Wi-Fi d'un appareil |
| Un **DNS interne** | Traduit un nom de service (`db`) en adresse IP | Un annuaire |

Les noms `front-tier` et `back-tier` ont été choisis par le formateur. Pour Docker, ce ne sont **que des étiquettes** : il leur donne exactement le même rôle. On aurait pu les appeler `a` et `b`.

**Vérification** (dans le Codespace, services lancés) :

```bash
docker network ls                                # le nom exact, préfixé par le projet (ex. 05-monitoring_back-tier)
docker network inspect 05-monitoring_back-tier   # "Subnet" : la plage d'adresses ; "Containers" : qui est branché, avec son IP
```

---

## 2. Définition générale d'un réseau

Un **réseau** est un ensemble de machines qui peuvent s'échanger des données directement, parce qu'elles partagent le même espace d'adresses. Exemple : les appareils branchés sur la même box chez toi.

Pour Docker, une seule règle en découle :

> **Deux conteneurs peuvent communiquer si et seulement s'ils partagent au moins un réseau.**

Deux conséquences :

- Un conteneur branché sur deux réseaux a **deux cartes réseau** et donc deux IP, une par réseau.
- Il ne sert **pas de passerelle** entre ces réseaux : Docker bloque le passage d'un réseau à l'autre. Un conteneur placé seulement sur `front-tier` ne pourrait donc pas joindre `db` en « passant par » Grafana, même si Grafana est sur les deux réseaux.

```
      front-tier                         back-tier
   ┌───────────────┐                ┌────────────────┐
   │   (vide ici)  │                │       db       │
   │               │   grafana      │                │
   │               ├── 2 cartes ────┤                │
   │               │   adminer      │                │
   │               ├── 2 cartes ────┤                │
   └───────────────┘                └────────────────┘
   Un conteneur seul sur front-tier ne verrait ni db, ni back-tier.
```

---

## 3. Automatique ou choix de l'ingénieur ?

Les deux, selon ce que contient le fichier :

| Situation | Ce que fait Compose |
|---|---|
| Aucun `networks:` dans le fichier | **Automatique** : il crée un réseau `<projet>_default` et y branche tous les services. Tout le monde peut parler à tout le monde. |
| `networks:` déclarés, puis listés dans un service | **Choix de l'ingénieur** : le service est branché **uniquement** sur les réseaux listés (et plus sur `default`). |

Pour du développement local, le réseau par défaut suffit presque toujours. Découper en plusieurs réseaux est un **choix de sécurité**.

---

## 4. Comment choisir le nombre de réseaux et l'appartenance de chaque service

On applique le **principe du moindre privilège** : chaque service ne doit pouvoir joindre que ce dont il a besoin.

La méthode :

1. **Lister les flux entre conteneurs** (qui appelle qui). Exemple : la table des flux du §4.3 du cours.
2. **Condition nécessaire** : si A doit appeler B, A et B partagent un réseau.
3. **Condition de sécurité** : si A n'a pas besoin de joindre B, ils ne partagent **aucun** réseau. C'est surtout vrai quand B est sensible (une base de données) et A exposé (une interface web). Si A est piraté, l'attaquant ne peut alors pas atteindre la base.
4. **Nombre de réseaux = nombre de « zones de confiance » distinctes**, pas plus. Chaque réseau en plus ajoute de la complexité.

Le découpage classique reprend l'architecture dite « 3 tiers » :

| Zone | Contenu typique |
|---|---|
| **front** | Ce qui est exposé aux utilisateurs (proxy web, interface) |
| **app** | La logique applicative (API, jobs de calcul) |
| **data** | Les bases de données |

Option utile : `internal: true` crée un réseau **sans accès à Internet**. Les conteneurs peuvent s'y parler entre eux, mais ne peuvent pas sortir.

```yaml
networks:
  back-tier:
    internal: true
```

---

## 5. Appliqué à ce projet

Les flux **entre conteneurs** se résument à Grafana → db et Adminer → db.

Le navigateur n'entre pas par les réseaux Docker. Il arrive par les **ports publiés** (`ports:`), qui ne dépendent pas des réseaux. C'est le point à retenir :

> **Publier un port contourne le cloisonnement réseau.** `"5432:5432"` rend la base accessible depuis la VM, quel que soit le réseau où elle se trouve.

Donc ici :

- **Un seul réseau suffirait.** Grafana et Adminer n'ont besoin de `front-tier` pour rien.
- **`back-tier` n'isole pas vraiment la base**, puisque son port est publié. C'est pourtant indispensable : le script Python, qui tourne hors Docker, doit pouvoir y écrire.

### Quand le découpage prendrait son sens

Exemple d'illustration, **à ne pas appliquer au projet** (extrait : seules les lignes utiles sont montrées) :

```yaml
services:
  proxy:            # seul point d'entrée, exposé
    image: nginx
    ports: ["443:443"]
    networks: [front-tier]
  grafana:          # joignable par le proxy ET peut joindre la base
    networks: [front-tier, back-tier]
  metrics-job:      # le script Python, mis en conteneur
    networks: [back-tier]
  db:               # AUCUN port publié : joignable uniquement via back-tier
    networks: [back-tier]
```

- `proxy` ne peut pas atteindre `db` : ils ne partagent aucun réseau.
- La base n'est plus accessible que par les deux services qui en ont besoin (`grafana`, `metrics-job`).
- C'est la configuration que les noms `front-tier` / `back-tier` du formateur laissent prévoir.

---

## 6. Récapitulatif

| Notion | En une phrase |
|---|---|
| Réseau Docker | Réseau virtuel : commutateur, plage d'IP, cartes réseau et DNS créés par Docker. |
| `front-tier` / `back-tier` | De simples noms choisis par le formateur ; Docker les traite de la même façon. |
| Règle de communication | Deux conteneurs se parlent si et seulement s'ils partagent un réseau. |
| Conteneur sur deux réseaux | Deux cartes réseau, mais pas de passerelle entre les réseaux. |
| Réseau `default` | Créé automatiquement si aucun réseau n'est déclaré ; tout le monde y est branché. |
| Choisir les réseaux | Moindre privilège : partager un réseau seulement si un flux l'exige. |
| Nombre de réseaux | Autant que de zones de confiance distinctes, pas plus. |
| `internal: true` | Réseau sans accès à Internet. |
| Ports publiés | Contournent le cloisonnement : un port publié est joignable depuis la VM, quel que soit le réseau. |
