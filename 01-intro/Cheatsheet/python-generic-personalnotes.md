# Question en vrac

## Ensemble et lsite vides

en python, comment initinier un dictionnair, tuple, list vide ?

En Python :

```python
mon_dict = {}        # ou dict()
mon_tuple = ()       # ou tuple()
ma_liste = []        # ou list()
```

Deux points à garder en tête :

- Un tuple est immuable, donc un tuple vide reste vide à vie. Il sert surtout de valeur par défaut ou de sentinelle. Pour un tuple à un seul élément, la virgule est obligatoire : `(1,)` et non `(1)`.
- Les littéraux (`{}`, `()`, `[]`) sont un peu plus rapides que les constructeurs (`dict()`, `tuple()`, `list()`), car ils évitent un lookup de nom. Négligeable sauf en boucle serrée.

Pour compléter, l'ensemble vide ne suit pas la logique attendue : `{}` crée un dictionnaire, donc il faut écrire `mon_set = set()`.

`set()` crée un **ensemble** vide. C'est un quatrième type de conteneur, à côté de la liste, du tuple et du dictionnaire.

Un ensemble a deux propriétés :
- pas de doublons : chaque valeur n'y apparaît qu'une fois
- pas d'ordre : il n'y a pas d'index, on ne peut pas écrire `mon_set[0]`

```python
mon_set = set()
mon_set.add("a")
mon_set.add("b")
mon_set.add("a")   # ignoré, "a" est déjà là
print(mon_set)     # {'a', 'b'}
```

On peut aussi le créer directement avec des accolades, à condition qu'il y ait au moins un élément :

```python
mon_set = {"a", "b"}
```

Et c'est précisément là qu'est le piège que je mentionnais : les accolades vides `{}` sont déjà prises par le dictionnaire. Donc pour un ensemble vide, il n'y a pas d'écriture courte, il faut passer par `set()`.

```python
type({})       # <class 'dict'>
type(set())    # <class 'set'>
```

L'usage typique : dédoublonner une liste (`set(ma_liste)`) ou tester rapidement l'appartenance (`if x in mon_set`), ce qui est bien plus rapide que sur une liste.

# Question à propos de pandas

**Oui aux trois questions !**

---

**1. Ce sont bien des colonnes du DataFrame**

Elles viennent directement du fichier CSV des taxis verts. Quand pandas lit le fichier, chaque colonne devient accessible via `df.nom_colonne` ou `df['nom_colonne']`.

---

**2. Les deux syntaxes sont équivalentes**

```python
# Syntaxe 1 - notation pointée (attribut)
df.lpep_dropoff_datetime = pd.to_datetime(df.lpep_dropoff_datetime)

# Syntaxe 2 - notation crochet
df['lpep_dropoff_datetime'] = pd.to_datetime(df['lpep_dropoff_datetime'])
```

Les deux font exactement la même chose. Cependant la notation crochet est **préférable** car :
- Elle fonctionne même si le nom de colonne contient des espaces ou des tirets
- Elle évite des conflits si le nom de colonne est le même qu'une méthode pandas (ex: `df.count` serait ambigu)
- Elle est recommandée par pandas pour les **modifications** (écriture)

---

**3. Oui, `df['duration']` crée une nouvelle colonne**

```python
df['duration'] = df.lpep_dropoff_datetime - df.lpep_pickup_datetime
```

Comme `duration` n'existe pas encore dans le DataFrame, pandas la **crée à la volée**. C'est le même mécanisme que :

```python
mon_dict = {}
mon_dict['nouvelle_cle'] = 42  # crée la clé si elle n'existe pas
```

Si la colonne avait déjà existé, elle aurait été **écrasée**. Pandas ne te demandera jamais confirmation, donc attention !

**Avantage de la syntaxe 1 (notation pointée)**

Honnêtement, son seul avantage est d'être **plus courte à écrire et plus lisible** :

```python
df.lpep_dropoff_datetime  # vs  df['lpep_dropoff_datetime']
```

C'est tout. C'est purement cosmétique, et comme dit précédemment, elle a plus d'inconvénients que d'avantages.

---

**Non, ce n'est pas du tout la même chose que `loc` / `iloc`**

Ce sont deux questions différentes :

| | Ce que ça résout |
|---|---|
| `df.col` vs `df['col']` | Comment **accéder à une colonne** par son nom |
| `loc` vs `iloc` | Comment **sélectionner des lignes** (et colonnes) |

`loc` et `iloc` sont vraiment différents l'un de l'autre :

```python
# loc → sélection par LABEL (nom de l'index)
df.loc[0:5]           # lignes dont l'index est entre 0 et 5
df.loc[df.duration > 30]   # lignes selon une condition

# iloc → sélection par POSITION (numéro entier)
df.iloc[0:5]          # les 5 premières lignes physiquement
df.iloc[0]            # la toute première ligne
```

La différence clé entre `loc` et `iloc` :

```python
# Si ton index est [10, 20, 30, 40, 50]
df.loc[0:2]    # cherche les labels 0, 1, 2 → probablement vide !
df.iloc[0:2]   # prend les lignes en position 0 et 1 → les deux premières
```

Donc :
- `df.col` vs `df['col']` → **style d'écriture**, même résultat
- `loc` vs `iloc` → **logique fondamentalement différente**, résultats potentiellement très différents