#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Petit ETL : importe un flux RSS, le normalise, le range dans le lac.
E = Extract (lire le flux)  |  T = Transform (normaliser)  |  L = Load (ranger)

Se lance tout seul sur GitHub Actions. Rien à installer chez toi.
Pour ajouter/changer des sources : édite le fichier  sources.txt
"""

import feedparser        # lit les flux RSS
import json, os, hashlib
from datetime import datetime, timezone

# --- Où ranger les données (le "lac") ---
DOSSIER_BRUT = "lac/brut"
DOSSIER_EXPLOITABLE = "lac/exploitable"

# --- Lire la liste des sources depuis sources.txt ---
# Format d'une ligne :  nom_court | url_du_flux
def lire_sources():
    sources = []
    if not os.path.exists("sources.txt"):
        return sources
    with open("sources.txt", encoding="utf-8") as f:
        for ligne in f:
            ligne = ligne.strip()
            if not ligne or ligne.startswith("#"):   # ignore vides et commentaires
                continue
            if "|" in ligne:
                nom, url = ligne.split("|", 1)
                sources.append((nom.strip(), url.strip()))
    return sources

def identifiant(lien):
    return hashlib.md5(lien.encode("utf-8")).hexdigest()[:12]

def deja_vu(aid):
    # évite de re-stocker un article déjà collecté (déduplication simple)
    return os.path.exists(os.path.join(DOSSIER_BRUT, f"{aid}.json"))

def collecter(nom, url):
    print(f"\n[E] Lecture de « {nom} » : {url}")
    flux = feedparser.parse(url)
    print(f"    {len(flux.entries)} articles dans le flux")

    os.makedirs(DOSSIER_BRUT, exist_ok=True)
    os.makedirs(DOSSIER_EXPLOITABLE, exist_ok=True)

    items_propres = []
    nouveaux = 0

    for article in flux.entries:
        lien = article.get("link", "")
        aid = identifiant(lien)

        if deja_vu(aid):
            continue   # déjà collecté, on passe
        nouveaux += 1

        # [L brut] on garde l'article TEL QUEL, avec sa carte d'identité
        enveloppe = {
            "_source": nom,
            "_url_collecte": url,
            "_capte_le": datetime.now(timezone.utc).isoformat(),
            "_id": aid,
            "brut": dict(article),
        }
        with open(os.path.join(DOSSIER_BRUT, f"{aid}.json"), "w", encoding="utf-8") as f:
            json.dump(enveloppe, f, ensure_ascii=False, indent=2, default=str)

        # [T] on normalise au schéma commun
        items_propres.append({
            "date":   article.get("published", ""),
            "source": nom,
            "type":   "news",
            "titre":  article.get("title", "").strip(),
            "texte":  article.get("summary", "").strip(),
            "url":    lien,
            "id":     aid,
        })

    # [L exploitable] on ajoute les items propres au fichier de la source
    if items_propres:
        chemin = os.path.join(DOSSIER_EXPLOITABLE, f"{nom}.json")
        anciens = []
        if os.path.exists(chemin):
            with open(chemin, encoding="utf-8") as f:
                anciens = json.load(f)
        tout = anciens + items_propres
        with open(chemin, "w", encoding="utf-8") as f:
            json.dump(tout, f, ensure_ascii=False, indent=2)

    print(f"    [T+L] {nouveaux} nouveaux articles rangés (schéma commun)")
    return nouveaux

if __name__ == "__main__":
    sources = lire_sources()
    if not sources:
        print("Aucune source dans sources.txt — ajoute une ligne : nom | url")
    else:
        print(f"=== ETL RSS — {len(sources)} source(s) ===")
        total = sum(collecter(nom, url) for nom, url in sources)
        print(f"\n=== Terminé : {total} nouveaux articles au total ===")
