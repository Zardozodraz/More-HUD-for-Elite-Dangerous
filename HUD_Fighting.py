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
from collections import deque

ListVaisseaux = []  # Liste globale pour stocker les vaisseaux détectés

@dataclass
class Rates:
    rS_in: float = 0.0   # perte bouclier joueur (%/s) si mesurable, sinon 0
    rH_in: float = 1e-6  # perte coque joueur (%/s), évite la division par 0
    
rates = Rates()

# historiques (mémoire courte) — on garde juste les derniers échantillons
player_history = deque(maxlen=5)      # éléments: (epoch_seconds, shield_fraction, hull_fraction)
enemy_histories = {}                  # clé = nom_vaisseau -> deque des mêmes tuples

@dataclass(frozen=True)
class Params:
    """
    Paramètres globaux pour le calcul de menace.
    Ajuste ces valeurs pour régler la sensibilité / le comportement.
    """
    lmbd: float = 1.5            # force du poids intrinsèque (rank/ship)
    delta: float = 0.7           # intensité de l'effet de surnombre
    kappa: float = 3.0           # saturation pour l'effet de surnombre
    alpha: float = 0.4           # malus si bouclier joueur désactivé
    beta: float = 0.6            # malus si coque joueur < 50%
    g: float = 3.0               # gain de la sigmoïde (sensibilité autour de R=1)
    eps: float = 1e-3            # epsilon anti-division par zéro

    # détection "combat actif" (seuils en fraction %/s, ex: 0.005 = 0.5%/s)
    combat_threshold_in: float = 0.005
    combat_threshold_out: float = 0.005

    # paramètres pour menace passive (quand aucun tir n'est détecté)
    passive_base: float = 45.0         # base (pour intrinsic=1.0 et 1 ennemi full HP)
    passive_cap: float = 70.0          # plafond pour la menace passive

    # pondération pour eHP = hull_weight * hull + shield_weight * shield
    passive_hull_weight: float = 0.7
    passive_shield_weight: float = 0.3


DEFAULT_PARAMS = Params()

# ==================================== SHIPs CLASSES ====================================
class Vaisseau:
    def __init__(self, nom_cible, PilotRank, ShieldHealth, HullHealth, ship_type, bounty):
        self.nom = nom_cible
        self.PilotRank = PilotRank
        self.ShieldHealth = ShieldHealth
        self.HullHealth = HullHealth
        self.ShipType = ship_type
        self.Bounty = bounty
        
        self.rateShield_out = 0.0
        self.rateHull_out = 0.0

    def __str__(self):
        return f"{self.nom} ({self.PilotRank}), Bouclier: {self.ShieldHealth}, Coque: {self.HullHealth}, Type: {self.ShipType}, Bounty: {self.Bounty}"

class Joueur:
    def __init__(self, hull_health=1.0, shield_up=True, shield_health=1.0):
        # hull_health et shield_health attendus en [0..1]
        self.hull_health = float(hull_health)
        self.shield_up = bool(shield_up)
        self.shield_health = float(shield_health)

    def __str__(self):
        return f"Joueur - Coque: {self.hull_health:.2f}, Bouclier: {self.shield_health:.2f} ({'Actif' if self.shield_up else 'Inactif'})"

joueur = Joueur(1.0, True, 1.0)

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

    def update(self, menace):
        text_content = f"Menace : {menace}\n"

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

def maj_vaiseaux(nom_cible, PilotRank, ShieldHealth, HullHealth, ship_type, bounty, timestamp=None):
    """
    Met à jour (ou crée) l'objet Vaisseau et enregistre un échantillon horodaté
    pour le calcul des vitesses.
    timestamp : chaîne ISO provenant du journal (ex: "2025-08-03T16:39:32Z")
    """
    global ListVaisseaux, enemy_histories

    # normalisation en 0..1 si l'input est en pourcentage (>1)
    try:
        sh = float(ShieldHealth)
        hu = float(HullHealth)
        if sh > 1.0:
            sh = sh / 100.0
        if hu > 1.0:
            hu = hu / 100.0
    except (TypeError, ValueError):
        sh, hu = 1.0, 1.0

    is_modified = False
    for i in range(len(ListVaisseaux)):
        if ListVaisseaux[i].nom == nom_cible:
            ListVaisseaux[i].PilotRank = PilotRank
            ListVaisseaux[i].ShieldHealth = sh
            ListVaisseaux[i].HullHealth = hu
            ListVaisseaux[i].ShipType = ship_type
            ListVaisseaux[i].Bounty = bounty
            is_modified = True
            # print(f"Vaisseau mis à jour : {ListVaisseaux[i]}")
            break

    if not is_modified:
        vaisseau = Vaisseau(nom_cible, PilotRank, sh, hu, ship_type, bounty)
        ListVaisseaux.append(vaisseau)
        # print(f"Nouveau vaisseau détecté : {vaisseau}")

    # --- enregistrement historique pour ce vaisseau ---
    epoch = parse_timestamp(timestamp) if timestamp else time.time()
    if nom_cible not in enemy_histories:
        enemy_histories[nom_cible] = deque(maxlen=5)
    enemy_histories[nom_cible].append((epoch, sh, hu))


def maj_joueur(hull_health, shield_up, timestamp=None):
    """
    Met à jour l'état joueur et enregistre un échantillon horodaté.
    """
    global joueur, player_history

    # normalize hull
    try:
        h = float(hull_health)
        if h > 1.0:
            h = h / 100.0
    except (TypeError, ValueError):
        h = 1.0

    joueur.hull_health = h
    joueur.shield_up = bool(shield_up)
    joueur.shield_health = 1.0 if joueur.shield_up else 0.0

    # enregistrement historique
    epoch = parse_timestamp(timestamp) if timestamp else time.time()
    player_history.append((epoch, joueur.shield_health, joueur.hull_health))

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

def parse_timestamp(timestamp_iso):
    """
    Convertit un timestamp ISO '2025-08-03T16:39:32Z' en epoch (float seconds).
    """
    try:
        dt = datetime.strptime(timestamp_iso, "%Y-%m-%dT%H:%M:%SZ")
        epoch = dt.timestamp()
        # debug optionnel :
        # print(f"[DEBUG] parse_timestamp: {timestamp_iso} -> {epoch:.3f}")
        return epoch
    except Exception as e:
        # fallback sur l'heure système si parsing échoue
        # print(f"[WARN] parse_timestamp failed: {e} ; fallback to time.time()")
        return time.time()


def calcul_vitesse_degats():
    """
    Calcule :
      - rates.rS_in / rates.rH_in : vitesses de perte du joueur (% fraction / s)
      - pour chaque vaisseau v.rateShield_out / v.rateHull_out : vitesses de perte observée sur l'ennemi (% fraction / s)
    Méthode :
      - utilise les 2 derniers échantillons (timestamp, shield, hull)
      - new_rate = max(0, (prev_value - last_value) / dt)
      - applique EMA (alpha smoothing) avec la valeur précédente
      - clamp entre 0 et max_rate
    """
    global rates, joueur, ListVaisseaux, player_history, enemy_histories

    # paramètres internes (tuneables)
    smoothing_alpha = 0.6   # EMA coefficient (0..1) : 1.0 = pas de lissage, 0.0 = conserver ancienne valeur
    max_rate = 0.5          # cap raisonnable en fraction/s (50% de la barre par seconde)
    min_dt = 0.02           # temps min entre deux samples pour considérer le delta (20 ms)
    eps = DEFAULT_PARAMS.eps

    # --- Joueur : calculer rS_in, rH_in à partir des 2 derniers échantillons ---
    if len(player_history) >= 2:
        prev_epoch, prev_shield, prev_hull = player_history[-2]
        last_epoch, last_shield, last_hull = player_history[-1]
        dt = last_epoch - prev_epoch
        if dt >= min_dt:
            shield_loss_rate = max(0.0, (prev_shield - last_shield) / dt)
            hull_loss_rate = max(0.0, (prev_hull - last_hull) / dt)
            # clamp
            shield_loss_rate = min(shield_loss_rate, max_rate)
            hull_loss_rate = min(hull_loss_rate, max_rate)
            # EMA smoothing
            rates.rS_in = smoothing_alpha * shield_loss_rate + (1.0 - smoothing_alpha) * rates.rS_in
            rates.rH_in = smoothing_alpha * hull_loss_rate + (1.0 - smoothing_alpha) * rates.rH_in
    # else garder les rates précédentes (ou valeurs par défaut)

    # clamp safety
    rates.rS_in = max(0.0, min(rates.rS_in, max_rate))
    rates.rH_in = max(0.0, min(rates.rH_in, max_rate))

    # --- Ennemis : pour chaque vaisseau, calculer la vitesse observée (dégâts subis) ---
    for v in ListVaisseaux:
        hist = enemy_histories.get(v.nom)
        if hist and len(hist) >= 2:
            prev_epoch, prev_shield, prev_hull = hist[-2]
            last_epoch, last_shield, last_hull = hist[-1]
            dt = last_epoch - prev_epoch
            if dt >= min_dt:
                shield_loss_rate = max(0.0, (prev_shield - last_shield) / dt)
                hull_loss_rate = max(0.0, (prev_hull - last_hull) / dt)
                shield_loss_rate = min(shield_loss_rate, max_rate)
                hull_loss_rate = min(hull_loss_rate, max_rate)
                # EMA smoothing on per-vaisseau stored rates
                v.rateShield_out = smoothing_alpha * shield_loss_rate + (1.0 - smoothing_alpha) * v.rateShield_out
                v.rateHull_out = smoothing_alpha * hull_loss_rate + (1.0 - smoothing_alpha) * v.rateHull_out

        # clamp safety
        v.rateShield_out = max(0.0, min(v.rateShield_out, max_rate))
        v.rateHull_out = max(0.0, min(v.rateHull_out, max_rate))

    # debug optional
    print(f"[DEBUG] rates.rS_in={rates.rS_in:.4f}, rates.rH_in={rates.rH_in:.4f}")
    for v in ListVaisseaux:
        print(f"[DEBUG] {v.nom}: rateShield_out={v.rateShield_out:.4f}, rateHull_out={v.rateHull_out:.4f}")


def traitement():
    # 1. mettre à jour vitesses (remplir rates.rH_in, rS_in, et rateShield_out/rateHull_out pour chaque vaisseau)
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
    """
    Calcul lisible et commenté du score de menace (0..100).
    - enemies : liste d'objets Vaisseau (attributs attendus : PilotRank, ShipType, ShieldHealth, HullHealth, rateShield_out, rateHull_out)
    - player  : objet Joueur (attributs attendus : shield_health, hull_health, shield_up)
    - rates   : structure Rates contenant rS_in (perte bouclier joueur %/s) et rH_in (perte coque joueur %/s)
    - params  : instance Params (paramètres réglables)
    """

    eps = params.eps  # sécurité

    # -------------------------
    # 1) Préparer les informations par ennemi (noms explicites)
    # -------------------------
    enemies_info = []
    for enemy in enemies:
        # normalisations pour rang/type
        rank_norm = (getattr(enemy, "PilotRank", 1) - 1) / 8.0   # 0 to 1
        ship_norm = (getattr(enemy, "ShipType", 1) - 1) / 2.0    # 0 to 1

        # poids intrinsèque de la cible (plus élevé = cible plus "importante")
        intrinsic_weight = 1.0 + params.lmbd * (0.6 * rank_norm + 0.4 * ship_norm)

        # état courant de la cible (fract. 0 to 1)
        shield_fraction = float(getattr(enemy, "ShieldHealth", 1.0))
        hull_fraction = float(getattr(enemy, "HullHealth", 1.0))

        # nos mesures (dégâts QUE NOUS infligeons à cette cible, en %/s)
        outgoing_shield_loss_rate = float(getattr(enemy, "rateShield_out", 0.0))
        outgoing_hull_loss_rate = float(getattr(enemy, "rateHull_out", 0.0))

        enemies_info.append({
            "enemy_obj": enemy,
            "rank_norm": rank_norm,
            "ship_norm": ship_norm,
            "intrinsic_weight": intrinsic_weight,
            "shield_fraction": shield_fraction,
            "hull_fraction": hull_fraction,
            "outgoing_shield_loss_rate": outgoing_shield_loss_rate,
            "outgoing_hull_loss_rate": outgoing_hull_loss_rate
        })

    number_of_enemies = len(enemies_info)

    # -------------------------
    # 2) Détecter si le combat est "actif"
    #    - incoming_active : on subit des pertes (bouclier / coque)
    #    - outgoing_active : on inflige des pertes mesurables à au moins une cible
    # -------------------------
    incoming_active = (rates.rS_in > params.combat_threshold_in) or (rates.rH_in > params.combat_threshold_in)
    outgoing_active = any(
        (ei["outgoing_shield_loss_rate"] > params.combat_threshold_out) or
        (ei["outgoing_hull_loss_rate"] > params.combat_threshold_out)
        for ei in enemies_info
    )

    # -------------------------
    # 3) Mode PASSIF (personne ne tire ou pas de données de dps) :
    #    -> menace dépend du rang, type, du nombre d'ennemis et de leur santé effective (eHP).
    # -------------------------
    if (not incoming_active) and (not outgoing_active):
        if number_of_enemies == 0:
            return 0.0

        # normalisations moyennes rank/ship (0..1)
        avg_rank_norm = sum(ei["rank_norm"] for ei in enemies_info) / number_of_enemies
        avg_ship_norm = sum(ei["ship_norm"] for ei in enemies_info) / number_of_enemies
        intrinsic_index = 0.7 * avg_rank_norm + 0.3 * avg_ship_norm   # 0..1 (rang priorisé)

        # eHP pondéré par intrinsic_weight : meilleure représentation de "combien il reste de menace"
        hull_w = params.passive_hull_weight
        shield_w = params.passive_shield_weight

        total_weight = 0.0
        total_weighted_ehp = 0.0
        for ei in enemies_info:
            shield_clamped = max(0.0, min(1.0, ei["shield_fraction"]))
            hull_clamped = max(0.0, min(1.0, ei["hull_fraction"]))
            effective_hp = hull_w * hull_clamped + shield_w * shield_clamped
            w = ei["intrinsic_weight"]
            total_weight += w
            total_weighted_ehp += w * effective_hp

        weighted_ehp = (total_weighted_ehp / total_weight) if total_weight > 0.0 else 0.0

        # score passif brut (avant bonus)
        passive_score = intrinsic_index * params.passive_base * number_of_enemies * weighted_ehp

        # bonus léger si présence de vaisseaux lourds ou rang très élevé
        heavy_bonus = 1.0
        if any(ei["enemy_obj"].ShipType == 3 for ei in enemies_info):
            heavy_bonus += 0.25
        if any(ei["enemy_obj"].PilotRank >= 8 for ei in enemies_info):
            heavy_bonus += 0.15
        passive_score *= heavy_bonus

        # clamp et retour
        passive_score = max(0.0, min(params.passive_cap, passive_score))
        return passive_score

    # -------------------------
    # 4) Mode ACTIF (combat en cours) : calcul Time-To-Die (joueur) vs Time-To-Kill (ennemis)
    # -------------------------
    # Etat du joueur (fractions 0..1)
    player_shield_fraction = getattr(player, "shield_health", 1.0)
    player_hull_fraction = getattr(player, "hull_health", 1.0)
    shield_is_up = bool(getattr(player, "shield_up", False))
    
    if not shield_is_up:
        player_shield_fraction = 0.0

    # vitesses de perte entrantes (ce qu'on subit) — clamp pour éviter div par 0
    incoming_shield_loss_rate = max(eps, float(rates.rS_in))
    incoming_hull_loss_rate = max(eps, float(rates.rH_in))

    # temps estimé avant destruction du joueur (en secondes arbitraires sur la base de %/s)
    time_to_die = (shield_is_up * player_shield_fraction) / incoming_shield_loss_rate + player_hull_fraction / incoming_hull_loss_rate

    # calcul du Time-To-Kill pour chaque ennemi (avec clamp des dps sortants)
    time_to_kill_list = []
    for ei in enemies_info:
        out_shield_rate = max(eps, ei["outgoing_shield_loss_rate"])
        out_hull_rate = max(eps, ei["outgoing_hull_loss_rate"])
        # TTK pondéré par le poids intrinsèque de la cible
        ttk = ei["intrinsic_weight"] * (ei["shield_fraction"] / out_shield_rate + ei["hull_fraction"] / out_hull_rate)
        time_to_kill_list.append(ttk)

    effective_time_to_kill = min(time_to_kill_list) if time_to_kill_list else 0.0

    # effet surnombre (sature grâce à kappa)
    crowd_factor = 1.0 + params.delta * ((number_of_enemies - 1.0) / (1.0 + (number_of_enemies - 1.0) / params.kappa))

    # vulnérabilité du joueur (malus si bouclier off, ou coque faible)
    player_vulnerability = (1.0 + params.alpha * (1 - int(bool(shield_is_up)))) * (1.0 + params.beta * max(0.0, (0.5 - player_hull_fraction) / 0.5))

    # ratio final (TTK / TTD) modulé par contexte
    ratio = (effective_time_to_kill / max(eps, time_to_die)) * crowd_factor * player_vulnerability

    # compressé via sigmoïde centrée en ratio=1 pour obtenir 0..100 lisible
    menace_score = 100.0 * (1.0 / (1.0 + math.exp(-params.g * (ratio - 1.0))))
    # clamp final et retour
    return max(0.0, min(100.0, menace_score))  # Clamp entre 0 et 100

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
                maj_vaiseaux(nom_cible, PilotRank, ShieldHealth, HullHealth, ship_type, bounty, timestamp=time_stamp)
                maj_vaisseau_ennemis = False
            if maj_vaisseau_joueur:
                maj_joueur(player_hull_health, shield_up, timestamp=time_stamp)
                maj_vaisseau_joueur = False
            
            # Calcul du score de menace et mise à jour du HUD
            score = traitement()
            hud.update(f"{score:.1f}")


# ==================================== MAIN ====================================
def main():
    hud = CombatHUD()
    threading.Thread(target=monitor_journal, args=(hud,), daemon=True).start()
    
    hud.update("")
    hud.run()

if __name__ == "__main__":
    main()