# Programmation orientée objet

## Les classes en python : https://courspython.com/classes-et-objets.html

Les classes sont un moyen de réunir des données et des fonctionnalités. Créer une nouvelle classe crée un nouveau type d'objet et ainsi de nouvelles instances de ce type peuvent être construites. Chaque instance peut avoir ses propres attributs, ce qui définit son état. Une instance peut aussi avoir des méthodes (définies par la classe de l'instance) pour modifier son état.

ne classe définit des attributs et des méthodes. Par exemple, imaginons une classe Voiture qui servira à créer des objets qui sont des voitures. Cette classe va pouvoir définir un attribut couleur, un attribut vitesse, etc. Ces attributs correspondent à des propriétés qui peuvent exister pour une voiture. La classe Voiture pourra également définir une méthode rouler(). Une méthode correspond en quelque sorte à une action, ici l’action de rouler peut être réalisée pour une voiture.

### Définition d’une classe Point

Voici comment définir une classe appelée ici Point.

```python
class Point:
    "Definition d'un point geometrique"
```

Par convention en Python, le nom identifiant une classe (qu’on appelle aussi son identifiant) débute par une majuscule. Ici Point débute par un P majuscule.

### Création d’un objet de type Point
```python
Point()
```
Ceci crée un objet de type Point. En POO, on dit que l’on crée une instance de la classe Point.

Une phrase emblématique de la POO consiste à dire qu”un objet est une instance de classe.

Il faut bien noter que pour créer une instance, on utilise le nom de la classe suivi de parenthèses. Nous verrons par la suite qu’il peut y avoir des arguments entre ces parenthèses.

### Affectation à une variable de la référence à un objet

Nous venons de définir une classe Point. Nous pouvons dès à présent nous en servir pour créer des objets de ce type, par instanciation. Créons par exemple un nouvel objet et mettons la référence à cet objet dans la variable p :

```python
p = Point()
```

Avertissement

> Comme pour les fonctions, lors de l’appel à une classe dans une instruction pour créer un objet, il faut toujours indiquer des parenthèses (même si aucun argument n’est transmis). Nous verrons un peu plus loin que ces appels peuvent se faire avec des arguments (voir la notion de constructeur).
> 
> Remarquez bien cependant que la définition d’une classe ne nécessite pas de parenthèses (contrairement à ce qui de règle lors de la définition des fonctions), sauf si nous souhaitons que la classe en cours de définition dérive d’une autre classe préexistante (ceci sera expliqué plus loin).


### Définition des attributs

```python
class Point:
    "Definition d'un point geometrique"

p = Point()
p.x = 1
p.y = 2
print("p : x =", p.x, "y =", p.y)
```

L’objet dont la référence est dans p possède deux attributs : x et y.

La syntaxe pour accéder à un attribut est la suivante : on va utiliser la variable qui contient la référence à l’objet et on va mettre un point . puis le nom de l’attribut.

Exemple

```python
class Point:
    "Definition d'un point geometrique"

a = Point()
a.x = 1
a.y = 2
b = Point()
b.x = 3
b.y = 4
print("a : x =", a.x, "y =", a.y)
print("b : x =", b.x, "y =", b.y)
```

On a 2 instances de la classe Point, c’est-à-dire 2 objets de type Point. Pour chacun d’eux, les attributs prennent des valeurs qui sont propres à l’instance.

> Avertissement
> 
> Par abus de langage on parlera parfois de l’objet a alors qu’il s’agira en fait de l’objet auquel a fait référence.


### Définition des méthodes

```python
class Point:
    def deplace(self, dx, dy):
        self.x = self.x + dx
        self.y = self.y + dy
Cette classe possède une méthode : deplace().
```

Pour définir une méthode, il faut :

- indiquer son nom (ici ```deplace()```).
- indiquer les arguments entre des parenthèses. Le premier argument d’une méthode doit être self.

Pour accéder aux méthodes d’un objet, on indique :

- le nom de la variable qui fait référence à cet objet
- un point
- le nom de la méthode


```python
a.deplace(3, 5)
```

> Avertissement
> 
> Lors de l’appel de la méthode, le paramètre self n’est pas utilisé et la valeur qu’il prend est la référence à l’objet. Il y a donc toujours un paramètre de moins que lors de la définition de la méthode.

Exemple

```python
class Point:
    def deplace(self, dx, dy):
        self.x = self.x + dx
        self.y = self.y + dy

a = Point()
a.x = 1
a.y = 2
print("a : x =", a.x, "y =", a.y)
a.deplace(3, 5)
print("a : x =", a.x, "y =", a.y)
```
### La notion de constructeur

Si lors de la création d’un objet nous voulons qu’un certain nombre d’actions soit réalisées (par exemple une initialisation), nous pouvons utiliser un constructeur.

Un constructeur n’est rien d’autre qu’une méthode, sans valeur de retour, qui porte un nom imposé par le langage Python : __init__(). Ce nom est constitué de init entouré avant et après par __ (deux fois le symbole underscore _, qui est le tiret sur la touche 8). Cette méthode sera appelée lors de la création de l’objet. Le constructeur peut disposer d’un nombre quelconque de paramètres, éventuellement aucun.

Exemple sans paramètre


```python
class Point:
    def __init__(self):
        self.x = 0
        self.y = 0

a = Point()
print("a : x =", a.x, "y =", a.y)
a.x = 1
a.y = 2
print("a : x =", a.x, "y =", a.y)
```

Dans cet exemple, nous avons pu définir des valeurs par défaut pour les attributs grâce au constructeur.

Exemple avec paramètres

```python
class Point:
    def __init__(self, abs, ord):
        self.x = abs
        self.y = ord

a = Point(1, 2)
print("a : x =", a.x, "y =", a.y)
```

Autre exemple avec paramètres

Dans l’exemple suivant, on utilise les mêmes noms pour les paramètres du constructeur et les attributs. Ceci ne pose pas de problème car ces variables ne sont pas dans le même espace de noms. Les paramètres du constructeur sont des variables locales, comme c’est habituellement le cas pour une fonction. Les attributs de l’objet sont eux dans l’espace de noms de l’instance. Les attributs se distinguent facilement car ils ont self devant.

```python
class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

a = Point(1, 2)
print("a : x =", a.x, "y =", a.y)
```

Exemple complet

```python
class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def deplace(self, dx, dy):
        self.x = self.x + dx
        self.y = self.y + dy

a = Point(1, 2)
b = Point(3, 4)
print("a : x =", a.x, "y =", a.y)
print("b : x =", b.x, "y =", b.y)
a.deplace(3, 5)
b.deplace(-1, -2)
print("a : x =", a.x, "y =", a.y)
print("b : x =", b.x, "y =", b.y)
```
autre info (encapsulation, attributs privé, accesseur et mutateur, propriété, accesseurs et mutateurs,...)

## Comment créer une classe et des objets en Python ? https://www.docstring.fr/formations/faq/oriente-objet/comment-creer-une-classe-et-des-objets-en-python/

En Python, une classe est un modèle pour créer des objets (une instance particulière de données et de méthodes). Pour définir une classe, on utilise le mot-clé class. Un objet est une instance de la classe et peut accéder aux attributs et méthodes définies dans la classe.

Voici comment créer une classe avec une méthode et un attribut:

```python
class MaClasse:
    attribut = "Ceci est un attribut"

    def ma_methode(self):
        return "Ceci est une méthode"
```

Création d'un objet et accès à ses attributs et méthodes:

```python
objet = MaClasse()
print(objet.attribut)            # Affiche 'Ceci est un attribut'
print(objet.ma_methode())        # Affiche 'Ceci est une méthode'
```

Pour initialiser un attribut dans un objet, utilisez la méthode spéciale `__init__`:

```python
class Personne:
    def __init__(self, prenom, nom):
        self.prenom = prenom
        self.nom = nom

    def saluer(self):
        return f"Bonjour, je suis {self.prenom} {self.nom}"

individu = Personne("Alex", "Dupont")
print(individu.saluer())         # Affiche 'Bonjour, je suis Alex Dupont'
```
## Réponse Claude

Voilà l'essentiel, dans l'ordre où ça sert.

**Une classe est un moule, une instance est l'objet fabriqué.**

```python
class Voiture:
    def __init__(self, marque, modele, prix):
        self.marque = marque
        self.modele = modele
        self.prix = prix

    def prix_ttc(self, taux=0.2):
        return self.prix * (1 + taux)

v = Voiture('Nissan', 'Stanza', 2000)
v.marque        # 'Nissan'
v.prix_ttc()    # 2400.0
```

**`__init__`** est appelé automatiquement quand tu écris `Voiture(...)`. C'est là qu'on pose les attributs, c'est-à-dire les données propres à chaque objet.

**`self`** est l'objet courant. Python le passe tout seul : `v.prix_ttc()` exécute en réalité `Voiture.prix_ttc(v)`. Tu dois l'écrire en premier paramètre de chaque méthode, mais jamais à l'appel. C'est la seule bizarrerie syntaxique qui surprend au début.

**Attribut d'instance vs attribut de classe** : ce qui est défini dans `__init__` appartient à l'objet, ce qui est défini directement dans le corps de la classe est partagé par tous.

```python
class Voiture:
    nb_roues = 4          # partagé
    def __init__(self, marque):
        self.marque = marque   # propre à l'instance
```

**Méthodes spéciales (« dunder »)** : elles branchent ton objet sur la syntaxe de Python. Les deux utiles tout de suite :

```python
class Voiture:
    def __init__(self, marque, prix):
        self.marque, self.prix = marque, prix
    def __repr__(self):
        return f'Voiture({self.marque!r}, {self.prix})'
    def __eq__(self, autre):
        return self.marque == autre.marque and self.prix == autre.prix
```

`__repr__` donne l'affichage dans la console, `__eq__` fait marcher `==`. C'est le même mécanisme qui fait que `df['Engine HP'] * 2` fonctionne dans Pandas : la classe `Series` définit `__mul__`.

Ce qui est magique, c'est la courte liste de noms que Python s'est réservée (__init__, __repr__, __eq__, __len__…)

repr() doit rendre une chaîne, __len__ un entier positif, __bool__ un True/False. En revanche __eq__, __add__, __getitem__ acceptent n'importe quoi — libre à toi de décider ce que veut dire « additionner deux voitures ».
D'où la vraie règle, qui est un contrat social plutôt qu'une règle du langage : implémente le sens attendu. __eq__ compare, __len__ compte, __repr__ décrit. Deux conventions valent la peine d'être connues :

__repr__ vise le développeur. L'idéal est une chaîne qu'on pourrait recoller dans le code : Voiture('Nissan', 'Stanza', 2000). D'où le !r dans le f-string, qui met les guillemets autour des chaînes.
__eq__ et __hash__ vont ensemble. Si tu redéfinis l'égalité, ton objet devient non-hachable et ne peut plus servir de clé de dictionnaire ni entrer dans un set, à moins de définir aussi __hash__. Python te force la main là-dessus parce que deux objets égaux doivent avoir le même hash.

Et un raccourci qui rend tout ça inutile dans 80 % des cas :

```python
from dataclasses import dataclass

@dataclass
class Voiture:
    marque: str
    modele: str
    prix: int

    def prix_ttc(self, taux=0.2):
        return self.prix * (1 + taux)

Ça génère __init__, __repr__ et __eq__ corrects pour toi. En data science c'est ce qu'on utilise le plus souvent pour les objets « porteurs de données ».
```

### Différence entre méthode spéciale et méthode classique

La différence n'est pas dans ce que fait ta méthode, elle est dans **qui peut l'appeler**.

Une méthode classique, il faut connaître son nom pour s'en servir. Donc seul du code qui connaît ta classe peut l'utiliser. Une méthode spéciale, le nom est connu d'avance par tout le monde — par l'interpréteur, mais aussi par la bibliothèque standard et par toutes les bibliothèques tierces, écrites avant que ta classe existe.

Concrètement :

```python
class A:
    def __init__(self, prix): self.prix = prix
    def egal(self, autre): return self.prix == autre.prix

class B:
    def __init__(self, prix): self.prix = prix
    def __eq__(self, autre): return self.prix == autre.prix

a1, a2 = A(2000), A(2000)
b1, b2 = B(2000), B(2000)

a1.egal(a2)        # True
b1 == b2           # True
```

Jusqu'ici, match nul. Maintenant tu passes tes objets à du code que tu n'as pas écrit :

```python
A(2000) in [A(2000)]     # False  ← `in` utilise ==, qui compare les adresses mémoire
B(2000) in [B(2000)]     # True

sorted(liste_de_A)       # TypeError: '<' not supported
```

Le `in` de Python, `sorted`, `max`, `sum`, `set`, `dict`, l'affichage d'un débogueur, `assert x == y` dans tes tests, l'inspection d'un DataFrame : tout ce code a été écrit sans rien savoir de ta classe. Il ne peut fonctionner avec elle que s'ils ont un vocabulaire commun. Les `__x__` sont ce vocabulaire. Ta méthode `egal` est parfaitement valable, mais elle est muette pour tout le reste de l'écosystème.

C'est exactement le mécanisme qui rend Pandas agréable. Les auteurs ont défini `__mul__`, `__ge__`, `__getitem__`, `__len__` sur `Series` et `DataFrame`. Résultat, tu écris `df['Year'] >= 2015` au lieu de `df.colonne('Year').superieur_ou_egal(2015)`, et le `df[...]` du filtrage marche avec la même syntaxe que les listes et les dictionnaires que tu connais déjà.

Il y a un second bénéfice, plus discret : **l'uniformité pour le lecteur humain**. Sans ce protocole, chaque bibliothèque inventerait son propre nom — `egal`, `is_equal`, `same_as`, `equals` — et tu passerais ta vie dans la documentation. Avec, tu sais que `==` compare, quel que soit l'objet.

La règle qui tombe de là : méthode spéciale quand l'opération correspond à un concept déjà existant dans Python (comparer, additionner, mesurer, indexer, afficher, itérer). Méthode classique pour tout ce qui est propre à ton métier. `prix_ttc` n'a aucun équivalent dans la syntaxe du langage, donc méthode classique. Comparer deux voitures, si — donc `__eq__`.

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