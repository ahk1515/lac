#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exploitation : les MOTS-CLÉS DISTINCTIFS d'un pays.

Principe : pour un pays donné, on ne cherche pas les mots les plus FRÉQUENTS
(ce seraient des mots banals présents partout), mais les mots SUR-REPRÉSENTÉS
dans les articles de ce pays PAR RAPPORT à l'ensemble. C'est l'idée du TF-IDF :
faire ressortir le caractéristique, pas le fréquent.

Se branche sur la couche enrichie (lac/enrichi/articles.json), qui contient
déjà la métadonnée "pays" de chaque article. On n'a rien à re-repérer.

Usage :
    python motscles.py            -> le fait pour TOUS les pays présents
    python motscles.py USA        -> seulement pour les USA
"""

import json, os, re, sys, math, unicodedata
from collections import Counter, defaultdict

DOSSIER_ENRICHI = "lac/enrichi"
DOSSIER_ANALYSE = "lac/analyse"

# Mots vides : mots trop courants pour être informatifs, qu'on ignore.
MOTS_VIDES = set("""
le la les un une des du de d au aux a à et ou où mais donc or ni car que qui quoi
dont ce cet cette ces son sa ses leur leurs mon ma mes ton ta tes notre nos votre vos
je tu il elle on nous vous ils elles se sy en y ne pas plus moins tres très
dans sur sous vers avec sans pour par entre chez contre selon apres après avant
est sont etait était ete été sera seront a ont avait avaient
il elle cela ca ça comme aussi meme même encore deja déjà lors alors puis ensuite
son ses leur un deux trois quatre premier premiere première nouveau nouvelle
apres selon face pres près lors afin
""".split())


def sans_accent(t):
    t = t.lower()
    t = unicodedata.normalize("NFD", t)
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def mots_de(texte):
    # découpe en mots, garde ceux de 3 lettres et plus, retire les mots vides
    t = sans_accent(texte)
    bruts = re.findall(r"[a-z]{3,}", t)
    return [m for m in bruts if m not in MOTS_VIDES]


def charger_articles():
    chemin = os.path.join(DOSSIER_ENRICHI, "articles.json")
    if not os.path.exists(chemin):
        print(f"[!] {chemin} introuvable — lance d'abord collecte.py puis traitement.py")
        return []
    with open(chemin, encoding="utf-8") as f:
        return json.load(f)


def motscles_distinctifs(articles, pays_cible, top=15):
    """
    Score TF-IDF simplifié :
      - TF  : fréquence du mot dans les articles du pays cible
      - IDF : rareté du mot dans l'ensemble (un mot présent partout est pénalisé)
    Score = TF_dans_pays * log(N_total / N_articles_contenant_le_mot)
    """
    # compter, pour chaque mot, dans combien d'articles au total il apparaît
    docs_par_mot = Counter()
    N_total = len(articles)
    for a in articles:
        contenu = a.get("titre", "") + " " + a.get("texte", "")
        for mot in set(mots_de(contenu)):
            docs_par_mot[mot] += 1

    # compter la fréquence des mots dans les articles du pays cible
    freq_pays = Counter()
    n_articles_pays = 0
    for a in articles:
        if pays_cible in a.get("pays", []):
            n_articles_pays += 1
            contenu = a.get("titre", "") + " " + a.get("texte", "")
            for mot in mots_de(contenu):
                freq_pays[mot] += 1

    if n_articles_pays == 0:
        return None, 0

    # calculer le score TF-IDF pour chaque mot
    scores = {}
    for mot, tf in freq_pays.items():
        idf = math.log(N_total / docs_par_mot[mot])   # rare = idf élevé
        scores[mot] = tf * idf

    classement = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return classement[:top], n_articles_pays


def main():
    articles = charger_articles()
    if not articles:
        return

    # quels pays traiter ?
    if len(sys.argv) > 1:
        pays_a_traiter = [sys.argv[1].upper()]
    else:
        # tous les pays présents dans l'enrichi
        tous = set()
        for a in articles:
            tous.update(a.get("pays", []))
        pays_a_traiter = sorted(tous)

    os.makedirs(DOSSIER_ANALYSE, exist_ok=True)
    resultat = {}

    for pays in pays_a_traiter:
        classement, n = motscles_distinctifs(articles, pays)
        if classement is None:
            print(f"\n[{pays}] aucun article — pays absent de l'enrichi.")
            continue
        resultat[pays] = [{"mot": m, "score": round(s, 2)} for m, s in classement]
        print(f"\n[{pays}] mots-clés distinctifs ({n} articles) :")
        for m, s in classement:
            print(f"    {m:<20} {s:.2f}")

    # ranger le résultat dans la couche analyse
    with open(os.path.join(DOSSIER_ANALYSE, "motscles_par_pays.json"), "w", encoding="utf-8") as f:
        json.dump(resultat, f, ensure_ascii=False, indent=2)
    print(f"\n=== Rangé dans {DOSSIER_ANALYSE}/motscles_par_pays.json ===")


if __name__ == "__main__":
    main()
