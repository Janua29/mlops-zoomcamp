DictVectoiser transform une liste de dictionnaire en des matrice one hot encoding

X_train :
col_130_85 | col_41_74 | col_22_53 | trip_distance
    1      |     0     |     0     |     2.3        ← trajet zone 130_85
    0      |     1     |     0     |     5.1        ← trajet zone 41_74
    0      |     0     |     1     |     1.8        ← trajet zone 22_53

X_val :
col_130_85 | col_41_74 | col_22_53 | trip_distance
    0      |     1     |     0     |     3.2        ← trajet zone 41_74
    1      |     0     |     0     |     7.5        ← trajet zone 130_85
    0      |     1     |     0     |     2.1        ← trajet zone 41_74




X_val contient moins d'exemple que X_train --> la matrice correspondante va avoir des lignes avec que des zeros 

Exemple : Si la zone 130_85 n'apparaît jamais dans la validation :

X_val :
col_130_85 | col_41_74 | col_22_53 | trip_distance
    0      |     1     |     0     |     3.2    
    0      |     0     |     1     |     7.5    
    0      |     1     |     0     |     2.1    
  ↑
cette colonne existe bien, mais elle vaut 0 partout

La colonne col_130_85 est bien présente (pour garder la compatibilité), mais remplie de 0 puisqu'aucun trajet de la validation ne part de cette zone.

Résumé final clair

	X_train	X_val
Nombre de colonnes	N	N (identique)
Nombre de lignes	Grand	Plus petit
Colonnes absentes	Non	Non, mais peuvent valoir 0 partout