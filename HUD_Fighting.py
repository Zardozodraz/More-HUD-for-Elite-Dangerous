"""
SYSTEME DE DECISION RAPIDE :
ANALYSE LE JOURNAL ET EXTRAIT LES INFORMATIONS REQUISES POUR LE HUD DE COMBAT.

TRAITE LES INFO POUR DEFINIR LE NIVEAU DE DANGER :
ANALYSE LES DEGATS AU BOUCLIER, A LA COQUE, AUX MODULES DU JOUEUR ET ENNEMIS
COMPTE LE NOMBRE D'ENNEMIS ET LEURS RANGS DE COMBAT
CALCULE LA VITESSE DE DESTRUCTION DES BOUCLIERS ET DE LA COQUE JOUEUR ET ENNEMIS : Δ% / Δt
Si la vitesse de destruction des boucliers ou de la coque est supérieure à un seuil, le HUD affiche un message d'alerte.

Faire un calcul pondéré en fonction de toutes les info : (à ajuster)
Joueur : degat au bouclier = *0.5, degat à la coque = *0.7, degat aux modules = *0.3
Ennemis : degat au bouclier = *0.5, degat à la coque = *0.7, degat aux modules = *0.3, nombre d'ennemis = *0.4, rang de combat = *0.8

On obtient un score de danger global qui est affiché sur le HUD.
AFFICHE LE NIVEAU DE DANGER SUR LE HUD
"""

import os
import json
import time
import ctypes
import threading
import tkinter as tk
from pathlib import Path
from string import ascii_uppercase
from datetime import datetime
from dataclasses import dataclass
import math

ListVaisseaux = []  # Liste globale pour stocker les vaisseaux détectés

@dataclass
class Rates:
    rS_in: float = 0.0   # perte bouclier joueur (%/s) si mesurable, sinon 0
    rH_in: float = 1e-6  # perte coque joueur (%/s), évite la division par 0
    
rates = Rates()

@dataclass(frozen=True)
class Params:
    lmbd: float = 1.5   # coefficient pour le poids intrinsèque des ennemis
    delta: float = 0.7  # force de l'effet de surnombre
    kappa: float = 3.0  # saturation pour l'effet de surnombre
    alpha: float = 0.4  # malus si bouclier du joueur désactivé
    beta: float = 0.6   # malus si coque < 50%
    g: float = 3.0      # "gain" de la sigmoïde (sensibilité)
    eps: float = 1e-3   # epsilon anti-division par zéro

DEFAULT_PARAMS = Params()  # DEFAULT_PARAMS = {"lmbd":1.5, "delta":0.7, "kappa":3.0, "alpha":0.4, "beta":0.6, "g":3.0, "eps":1e-3}

# ==================================== SHIPs CLASSES ====================================
class Vaisseau:
    def __init__(self, nom_cible, PilotRank, ShieldHealth, HullHealth, ship_type, bounty):
        self.nom = nom_cible
        self.PilotRank = PilotRank
        self.ShieldHealth = ShieldHealth
        self.HullHealth = HullHealth
        self.ShipType = ship_type
        self.Bounty = bounty
        
        self.rS_out = 0.0
        self.rH_out = 0.0

    def __str__(self):
        return f"{self.nom} ({self.PilotRank}), Bouclier: {self.ShieldHealth}, Coque: {self.HullHealth}, Type: {self.ShipType}, Bounty: {self.Bounty}"

class Joueur:
    def __init__(self, hull_health, shield_up):
        self.hull_health = hull_health
        self.shield_up = shield_up # bool

    def __str__(self):
        return f"Joueur - Santé: {self.hull_health}, Bouclier: {'Actif' if self.shield_up else 'Inactif'}"

joueur = Joueur(1, True)  # Initialisation du joueur avec des valeurs par défaut

# ==================================== HUD ====================================
class CombatHUD:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("HUD Combat")
        self.root.geometry("500x100+1620+10")
        self.root.configure(bg="black")
        self.root.wm_attributes("-topmost", True)
        self.root.attributes("-alpha", 0.85)
        #self.root.wm_attributes("-transparentcolor", "black")
        self.root.overrideredirect(True)

        self.text = tk.Text(
            self.root,
            fg="lime",
            bg="black",
            font=("Consolas", 12, "bold"),
            wrap="word",
            state="disabled",
            borderwidth=0,
            highlightthickness=0
        )
        self.text.pack(fill="both", expand=True)

        self.make_click_through()

    def make_click_through(self):
        hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
        extended_style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
        ctypes.windll.user32.SetWindowLongW(hwnd, -20, extended_style | 0x80000 | 0x20)

    def update(self, bounty):
        text_content = f"Bounty : {bounty}\n"

        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", text_content)
        self.text.config(state="disabled")

    def run(self):
        self.root.mainloop()

# ==================================== Journal ====================================

def find_latest_journal():
    # Recherche sur tous les disques montés (Windows uniquement)
    candidate_dirs = []
    for drive_letter in ascii_uppercase:
        root = Path(f"{drive_letter}:\\") # Exemple : C:\, D:\, ...
        test_path = root / "Users" # Vérifie s'il existe un dossier "Users"
        if test_path.exists():
            for user_dir in test_path.iterdir(): # Parcours de tous les dossiers utilisateurs trouvés
                journal_dir = user_dir / "Saved Games" / "Frontier Developments" / "Elite Dangerous" # Construit le chemin vers le journal pour chaque utilisateur
                if journal_dir.exists():
                    candidate_dirs.append(journal_dir) # Si le dossier existe, on l’ajoute à la liste des candidats

    journal_files = []
    for d in candidate_dirs: # Rassemble tous les fichiers Journal .log dans chaque dossier candidat
        journal_files += list(d.glob("Journal.*.log"))

    if not journal_files: # Si aucun fichier journal n’a été trouvé, on lève une erreur
        raise FileNotFoundError("Aucun fichier journal Elite Dangerous trouvé sur les disques.")

    latest_file = max(journal_files, key=os.path.getmtime) # Retourne le fichier le plus récent (le dernier modifié)

    return latest_file

# ==================================== MAJ VAISSEAUX ====================================

def maj_vaiseaux(nom_cible, PilotRank, ShieldHealth, HullHealth, ship_type, bounty):
    global ListVaisseaux
    is_modified = False
    # Fonction pour créer un vaisseau à partir des données du journal
    for i in range(len(ListVaisseaux)):
        if ListVaisseaux[i].nom == nom_cible:
            # Si le vaisseau existe déjà, on met à jour ses informations
            ListVaisseaux[i].PilotRank = PilotRank
            ListVaisseaux[i].ShieldHealth = ShieldHealth
            ListVaisseaux[i].HullHealth = HullHealth
            ListVaisseaux[i].ShipType = ship_type
            ListVaisseaux[i].Bounty = bounty
            is_modified = True
            print(f"Vaisseau mis à jour : {ListVaisseaux[i]}")
        
    if not is_modified:
        # Si le vaisseau n'existe pas, on le crée et l'ajoute à la liste
        vaisseau = Vaisseau(nom_cible, PilotRank, ShieldHealth, HullHealth, ship_type, bounty)
        ListVaisseaux.append(vaisseau)
        print(f"Nouveau vaisseau détecté : {nom_cible} ({PilotRank}), Bouclier: {ShieldHealth}, Coque: {HullHealth}, Type: {ship_type}, Bounty: {bounty}")

def maj_joueur(hull_health, shield_up):
    # Fonction pour mettre à jour les informations du joueur
    global joueur
    joueur.hull_health = hull_health
    joueur.shield_up = shield_up
    print(f"Joueur mis à jour : {joueur}")

def cible_detruite(nom_cible_detruite):
    # Fonction pour traiter la destruction d'une cible
    global ListVaisseaux
    for i in range(len(ListVaisseaux)):
        if ListVaisseaux[i].nom == nom_cible_detruite:
            print(f"Cible détruite : {ListVaisseaux[i]} ({ListVaisseaux[i].PilotRank}), {ListVaisseaux[i].ShipType}")
            del ListVaisseaux[i]  # Supprime le vaisseau de la liste
            break  # Sort de la boucle après avoir trouvé et supprimé le vaisseau

# ==================================== TRAITEMENT ====================================

def parse_timestamp(timestamp):
    """Parse le timestamp du journal et retourne une durée."""
    
    dt = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ")
    minutes = dt.minute
    secondes = dt.second
    dt = (minutes, secondes)
    print(f"[INFO] Timestamp analysé : minutes: {dt[0]}, secondes: {dt(1)})")
    
    return dt

def calcul_vitesse_degats():
    """Calcul la vitesse de destruction des boucliers et de la coque du joueur et des ennemis en fonction du timestamp."""
    global joueur, ListVaisseaux
    
    pass

def traitement():
    # 1. mettre à jour vitesses (remplir rates.rH_in, rS_in, et rS_out/rH_out pour chaque vaisseau)
    calcul_vitesse_degats()

    # 2. calcul du score de menace
    global rates
    score = menace(
        enemies=ListVaisseaux,
        player=joueur,
        rates=rates,
        params=DEFAULT_PARAMS
    )

    # 3. renvoyer le score
    return score


def menace(enemies, player, rates, params):
    eps = 1e-3
    # TTD joueur
    S, H, U = player.S, player.H, player.shield_up  # [0..1], bool
    rSi, rHi = max(eps, rates.rS_in), max(eps, rates.rH_in)
    TTD = (U*S)/rSi + H/rHi

    # TTK effectif
    TTKs = []
    for e in enemies:
        r_star = (e.rank-1)/8.0
        t_star = (e.ship-1)/2.0
        w = 1 + params.lmbd * (0.6*r_star + 0.4*t_star)

        rSo = max(eps, e.rS_out)  # 0 si non ciblé, sinon valeur mesurée
        rHo = max(eps, e.rH_out)
        TTKs.append(w * (e.s / rSo + e.h / rHo))
    TTK_eff = min(TTKs) if TTKs else 0.0

    # Contexte
    N = len(enemies)
    C = 1 + params.delta * ((N-1) / (1 + (N-1)/params.kappa))
    Vp = (1 + params.alpha*(1-int(U))) * (1 + params.beta*max(0.0, (0.5-H)/0.5))

    R = (TTK_eff / max(eps, TTD)) * C * Vp
    menace = 100.0 * (1.0 / (1.0 + math.exp(-params.g*(R-1.0))))
    print("Menace calculée :", menace)
    return max(0.0, min(100.0, menace))  # Clamp entre 0 et 100

# ==================================== SURVEILLANCE DU JOURNAL ====================================
def monitor_journal(hud: CombatHUD):
    journal_path = find_latest_journal()
    print(f"[INFO] Lecture du journal : {journal_path}")
    
    ship_type = ""
    nom_cible = ""
    PilotRank = ""
    ShieldHealth = 1
    HullHealth = 1
    bounty = 0
    time_stamp = ""
    
    player_hull_health = 1 # Valeur par défaut pour la santé du joueur
    shield_up = True
    
    maj_vaisseau_ennemis = False
    maj_vaisseau_joueur = False

    with open(journal_path, 'r', encoding='utf-8') as f:
        f.seek(0, os.SEEK_END)

        while True:
            line = f.readline()
            if not line:
                time.sleep(0.1)
                continue

            try:
                data = json.loads(line)
                # Ennemis
                if data.get("event") == "ShipTargeted" and data.get("TargetLocked"): # TargetLocked est un bool
                    """if data.get("ScanStage") == 0:
                        ship_type = data.get("Ship_Localised")
                        nom_cible = ""
                        PilotRank = ""
                        ShieldHealth = 0
                        HullHealth = 0
                        bounty = 0
                        time_stamp = data.get("timestamp")
                        maj_vaisseau_ennemis = True"""
                    
                    if data.get("ScanStage") == 1:
                        ship_type = data.get("Ship_Localised")
                        nom_cible = data.get("PilotName_Localised")
                        PilotRank = data.get("PilotRank")
                        time_stamp = data.get("timestamp")
                        maj_vaisseau_ennemis = True
                    
                    elif data.get("ScanStage") == 2:
                        ship_type = data.get("Ship_Localised")
                        nom_cible = data.get("PilotName_Localised")
                        PilotRank = data.get("PilotRank")
                        ShieldHealth = data.get("ShieldHealth")
                        HullHealth = data.get("HullHealth")
                        time_stamp = data.get("timestamp")
                        maj_vaisseau_ennemis = True
                    
                    elif data.get("ScanStage") == 3:
                        bounty = data.get("Bounty", 0)
                        nom_cible = data.get("PilotName_Localised")
                        PilotRank = data.get("PilotRank")
                        ShieldHealth = data.get("ShieldHealth")
                        HullHealth = data.get("HullHealth")
                        ship_type = data.get("Ship_Localised")
                        time_stamp = data.get("timestamp")
                        maj_vaisseau_ennemis = True
                
                if data.get("event") == "Bounty": # cible (recherchée) détruite
                    nom_cible_detruite = data.get("PilotName_Localised")
                    total_reward = data.get("TotalReward")
                    time_stamp = data.get("timestamp")
                    cible_detruite(nom_cible_detruite)
                
                # Joueur
                if data.get("event") == "HullDamage":
                    if data.get("PlayerPilot"): # bool
                        player_hull_health = data.get("Health")
                        time_stamp = data.get("timestamp")
                        maj_vaisseau_joueur = True
                
                if data.get("event") == "ShieldState":
                    shield_up = data.get("ShieldsUp") # bool
                    time_stamp = data.get("timestamp")
                    maj_vaisseau_joueur = True
                
            except json.JSONDecodeError:
                continue
            
            # Assiciation des rangs de combat
            if PilotRank == "Harmless":
                PilotRank = 1
            elif PilotRank == "Mostly Harmless":
                PilotRank = 2
            elif PilotRank == "Novice":
                PilotRank = 3
            elif PilotRank == "Competent":
                PilotRank = 4
            elif PilotRank == "Expert":
                PilotRank = 5
            elif PilotRank == "Master":
                PilotRank = 6
            elif PilotRank == "Dangerous":
                PilotRank = 7
            elif PilotRank == "Deadly":
                PilotRank = 8
            elif PilotRank == "Elite":
                PilotRank = 9
            
            # Association des types de vaisseaux
            vaisseau_niveau_1 = ["Adder", "Beluga", "Liner", "Cobra Mk III", "Cobra Mk IV", "Cobra MK V", "Dolphin", "Eagle", "Hauler", "Imperial Eagle", "Keelback", "Type-6 Transporter", "Type-7 Transporter", "Type-8 Transporter", "Orca", "Sidewinder", "Viper MkIII", "Viper Mk IV"]
            vaisseau_niveau_2 = ["Alliance Challenger", "Alliance Crusader", "Asp Explorer", "Asp Scout", "Alliance Chieftain", "Corsair", "Diamondback Explorer", "Diamondback Scout", "Federal Assault Ship", "Federal Dropship", "Federal Gunship", "Fer-de-Lance", "Imperial Clipper", "Imperial Courier", "Krait Mk II", "Krait Phantom", "Mamba", "Mandalay", "Python", "Python Mk II", "Vulture"]
            vaisseau_niveau_3 = ["Anaconda", "Federal Corvette", "Imperial Cutter", "Type-9 Heavy", "Type-10 Defender"]
            
            if ship_type in vaisseau_niveau_1:
                ship_type = 1
            elif ship_type in vaisseau_niveau_2:
                ship_type = 2
            elif ship_type in vaisseau_niveau_3:
                ship_type = 3
            
            # Mise à jour des vaisseaux et du joueur
            if maj_vaisseau_ennemis:
                maj_vaiseaux(nom_cible, PilotRank, ShieldHealth, HullHealth, ship_type, bounty)
                maj_vaisseau_ennemis = False
            if maj_vaisseau_joueur:
                maj_joueur(player_hull_health, shield_up)
                maj_vaisseau_joueur = False
            
            # Calcul du score de menace et mise à jour du HUD
            score = traitement()
            hud.update(f"Menace : {score:.1f}")


# ==================================== MAIN ====================================
def main():
    hud = CombatHUD()
    threading.Thread(target=monitor_journal, args=(hud,), daemon=True).start()
    
    hud.update("")
    hud.run()

if __name__ == "__main__":
    main()