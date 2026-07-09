#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Traitement en DEUX temps, comme prévu en conception :

  1) ENRICHIR   : lire la couche exploitable, repérer les PAYS mentionnés
                  dans chaque article -> produit de la MÉTADONNÉE DÉRIVÉE
                  (rangée dans lac/enrichi/)

  2) EXPLOITER  : à partir de l'enrichi, calculer deux vues ->
                  - fréquence : quels pays sont les plus cités
                  - matrice   : quels pays sont cités ENSEMBLE (liens)
                  (rangées dans lac/analyse/)

Le repérage des pays est fait UNE fois (enrichi). Les comptages sont des
lectures de cet enrichi -> on n'a pas un script par comptage.

Rien à installer de spécial (que du Python standard).
"""

import json, os, re, unicodedata
from itertools import combinations
from collections import Counter

DOSSIER_EXPLOITABLE = "lac/exploitable"
DOSSIER_ENRICHI = "lac/enrichi"
DOSSIER_ANALYSE = "lac/analyse"
REFERENTIEL = "referentiel_pays.txt"


# --- Outil : normaliser un texte (minuscule, sans accent) pour comparer ---
def sans_accent(texte):
    texte = texte.lower()
    texte = unicodedata.normalize("NFD", texte)
    texte = "".join(c for c in texte if unicodedata.category(c) != "Mn")
    return texte


# --- Charger le référentiel pays -> {code: [variantes]} ---
def charger_referentiel():
    ref = {}
    with open(REFERENTIEL, encoding="utf-8") as f:
        for ligne in f:
            ligne = ligne.strip()
            if not ligne or ligne.startswith("#"):
                continue
            if "|" in ligne:
                code, variantes = ligne.split("|", 1)
                code = code.strip()
                liste = [sans_accent(v.strip()) for v in variantes.split(",") if v.strip()]
                ref[code] = liste
    return ref


# --- Repérer les pays présents dans un texte ---
# On cherche chaque variante comme un MOT entier (bordures de mot),
# pour éviter que "mali" matche dans "formalisme", par exemple.
def reperer_pays(texte, ref):
    t = sans_accent(texte)
    trouves = set()
    for code, variantes in ref.items():
        for v in variantes:
            # \b = bordure de mot ; on échappe les espaces/traits d'union
            motif = r"\b" + re.escape(v) + r"\b"
            if re.search(motif, t):
                trouves.add(code)
                break  # une variante suffit pour ce pays
    return sorted(trouves)


# ============ ÉTAPE 1 : ENRICHIR ============
def enrichir(ref):
    os.makedirs(DOSSIER_ENRICHI, exist_ok=True)
    articles_enrichis = []

    if not os.path.isdir(DOSSIER_EXPLOITABLE):
        print(f"[!] Pas de dossier {DOSSIER_EXPLOITABLE} — lance d'abord la collecte.")
        return articles_enrichis

    for fichier in sorted(os.listdir(DOSSIER_EXPLOITABLE)):
        if not fichier.endswith(".json"):
            continue
        with open(os.path.join(DOSSIER_EXPLOITABLE, fichier), encoding="utf-8") as f:
            items = json.load(f)

        for item in items:
            # on repère les pays dans titre + texte
            contenu = (item.get("titre", "") + " " + item.get("texte", ""))
            pays = reperer_pays(contenu, ref)

            enrichi = dict(item)                 # on garde tout l'item
            enrichi["pays"] = pays               # + la MÉTADONNÉE DÉRIVÉE
            articles_enrichis.append(enrichi)

    # on range l'enrichi (une seule fois)
    with open(os.path.join(DOSSIER_ENRICHI, "articles.json"), "w", encoding="utf-8") as f:
        json.dump(articles_enrichis, f, ensure_ascii=False, indent=2)

    avec_pays = sum(1 for a in articles_enrichis if a["pays"])
    print(f"[ENRICHIR] {len(articles_enrichis)} articles traités, "
          f"{avec_pays} avec au moins un pays repéré.")
    return articles_enrichis


# ============ ÉTAPE 2 : EXPLOITER ============
def exploiter(articles):
    os.makedirs(DOSSIER_ANALYSE, exist_ok=True)

    # --- Vue 1 : fréquence des pays ---
    freq = Counter()
    for a in articles:
        for pays in a["pays"]:
            freq[pays] += 1
    frequence = [{"pays": p, "citations": n} for p, n in freq.most_common()]

    with open(os.path.join(DOSSIER_ANALYSE, "frequence_pays.json"), "w", encoding="utf-8") as f:
        json.dump(frequence, f, ensure_ascii=False, indent=2)

    # --- Vue 2 : matrice de co-citations (liens entre pays) ---
    # pour chaque article citant >= 2 pays, on compte chaque PAIRE.
    paires = Counter()
    for a in articles:
        pays = a["pays"]
        if len(pays) >= 2:
            for p1, p2 in combinations(pays, 2):
                paire = tuple(sorted((p1, p2)))
                paires[paire] += 1
    matrice = [{"pays_a": p[0], "pays_b": p[1], "co_citations": n}
               for p, n in paires.most_common()]

    with open(os.path.join(DOSSIER_ANALYSE, "matrice_liens.json"), "w", encoding="utf-8") as f:
        json.dump(matrice, f, ensure_ascii=False, indent=2)

    # --- Affichage lisible ---
    print("\n[EXPLOITER — Vue 1 : pays les plus cités]")
    for row in frequence[:10]:
        print(f"    {row['pays']} : {row['citations']}")

    print("\n[EXPLOITER — Vue 2 : liens les plus forts entre pays]")
    if matrice:
        for row in matrice[:10]:
            print(f"    {row['pays_a']} <-> {row['pays_b']} : {row['co_citations']}")
    else:
        print("    (aucune paire — il faut des articles citant au moins 2 pays)")


if __name__ == "__main__":
    print("=== TRAITEMENT : enrichir puis exploiter ===\n")
    ref = charger_referentiel()
    print(f"Référentiel chargé : {len(ref)} pays.\n")
    articles = enrichir(ref)
    if articles:
        exploiter(articles)
    print("\n=== Terminé. Résultats dans lac/enrichi/ et lac/analyse/ ===")
