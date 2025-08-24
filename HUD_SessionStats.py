"""
Session statistics HUD for Elite Dangerous

This module creates a translucent overlay using Tkinter to display :
- Total buy/sell
- Number of kills
- Total distance travelled
- Number of jumps
- Total bounty earned
- Number of new codex entry
- Total Exploration data sold
- Session duration

Features:
- Monitors the Elite Dangerous journal in real-time.
- Detects all the events listed above.
- Displays results in a transparent HUD always on top-right of the screen.

This script is intended to be launched directly or from a launcher but can be launched independently.
"""

import os
import sys
import time
import json
import ctypes
import tkinter as tk
from string import ascii_uppercase
from pathlib import Path
from datetime import datetime
import threading

import Language # Language file
lang = "english"

largeur, hauteur = 1920, 1080

def ctypeTaille():
    global largeur, hauteur
    
    user32 = ctypes.windll.user32
    user32.SetProcessDPIAware()  # éviter les problèmes de mise à l'échelle
    largeur = user32.GetSystemMetrics(0)
    hauteur = user32.GetSystemMetrics(1)

    print(f"Résolution de l'écran principal : {largeur} x {hauteur}")

ctypeTaille()

# ====================== HUD DE STATS ======================

class SessionHUD:
    """
    A transparent and click-through Tkinter window that displays :
    - Total buy/sell
    - Number of kills
    - Total distance travelled
    - Number of jumps
    - Total bounty earned
    - Number of new codex entry
    - Total Exploration data sold
    - Session duration

    Methods:
        update(system, body_list): Updates the HUD content.
        run(): Starts the Tkinter main loop.
    """
    
    TRANSPARENT_COLOR = "#000000"  # couleur unique utilisée comme "colorkey"
    
    def __init__(self):
        """
        Initializes the HUD window with transparent background and non-interactive settings.
        """
        
        self.root = tk.Tk()
        self.root.title("HUD Session")
        self.root.geometry(f"{round(largeur * 0.1)}x{round(hauteur * 0.18)}+{round(largeur * 0.88)}+10") # "200x150+1710+10"
        self.root.configure(bg=self.TRANSPARENT_COLOR)
        self.root.wm_attributes("-topmost", True)
        # Important : ne PAS définir -alpha si vous voulez utiliser -transparentcolor
        self.root.overrideredirect(True)
        self.root.wm_attributes("-topmost", True)

        # utiliser une couleur spécifique et unique comme couleur transparente
        self.root.configure(bg=self.TRANSPARENT_COLOR)
        self.root.wm_attributes("-transparentcolor", self.TRANSPARENT_COLOR)

        self.text = tk.Text(
            self.root,
            fg="lime",
            bg=self.TRANSPARENT_COLOR,
            font=("Consolas", 12, "bold"),
            wrap="word",
            state="disabled",
            borderwidth=0,
            highlightthickness=0
        )
        self.text.pack(fill="both", expand=True)

        self.make_click_through()
        
        self.session_start = datetime.utcnow()
        self.stats = {
            "buy": 0,
            "sell": 0,
            "kills": 0,
            "distance": 0.0,
            "jumps": 0,
            "bounty": 0,
            "codex": 0,
            "ExplorationData": 0,
        }

    def _hex_to_colorref(self, hex_color: str) -> int:
        h = hex_color.lstrip("#")
        r = int(h[0:2], 16)
        g = int(h[2:4], 16)
        b = int(h[4:6], 16)
        # COLORREF = 0x00BBGGRR (Windows uses low bytes for R,G,B ordering in this packing)
        return r | (g << 8) | (b << 16)

    def make_click_through(self):
        hwnd = self.root.winfo_id()
        GWL_EXSTYLE = -20
        WS_EX_LAYERED = 0x00080000
        WS_EX_TRANSPARENT = 0x00000020

        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED | WS_EX_TRANSPARENT)

        # Optionnel — forcer la clé couleur côté WinAPI (LWA_COLORKEY = 0x1)
        colorref = self._hex_to_colorref(self.TRANSPARENT_COLOR)
        LWA_COLORKEY = 0x1
        # crKey, bAlpha (ignored for LWA_COLORKEY), dwFlags
        ctypes.windll.user32.SetLayeredWindowAttributes(hwnd, colorref, 0, LWA_COLORKEY)

    def update(self):
        """
        Updates the displayed info :
        - Total buy/sell
        - Number of kills
        - Total distance travelled
        - Number of jumps
        - Total bounty earned
        - Number of new codex entry
        - Total Exploration data sold
        - Session duration

        Args:
            system (str): The current star system name.
            body_list (List[str]): A list of interesting celestial body types or notes.
        """
        
        duration = datetime.utcnow() - self.session_start
        text_content = (
            f"{Language.languages[lang]["HUD_SessionStats"]["Kills"]} : {self.stats['kills']}\n"
            f"{Language.languages[lang]["HUD_SessionStats"]["Distance"]} : {self.stats['distance']:.2f} AL\n"
            f"{Language.languages[lang]["HUD_SessionStats"]["Jumps"]} : {self.stats['jumps']} \n"
            f"{Language.languages[lang]["HUD_SessionStats"]["Bounty"]} : {self.stats['bounty']} cr\n"
            f"{Language.languages[lang]["HUD_SessionStats"]["Sell"]} : {self.stats['sell']} cr\n"
            f"{Language.languages[lang]["HUD_SessionStats"]["Buy"]} : {self.stats['buy']} cr\n"
            f"{Language.languages[lang]["HUD_SessionStats"]["Codex"]} : {self.stats['codex']}\n"
            f"{Language.languages[lang]["HUD_SessionStats"]["Exploration"]} : {self.stats['ExplorationData']}\n"

            f"{Language.languages[lang]["HUD_SessionStats"]["Session"]} : {str(duration).split('.')[0]}\n"
        )

        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", text_content)
        self.text.config(state="disabled")

    def apply_command_on_ui(self, cmd):
        global lang
        
        if cmd == "english":
            lang = "english"
        elif cmd == "french":
            lang = "french"

    def run(self):
        """
        Runs the Tkinter main loop to display the HUD.
        """
        
        self.root.mainloop()

# ====================== JOURNAL ======================

def find_latest_journal():
    """
    Searches for the latest Elite Dangerous journal file in all available hard-drives.

    Returns:
        Path: Path to the most recently modified journal file.

    Raises:
        FileNotFoundError: If no journal files are found.
    """
    
    candidate_dirs = []
    for drive_letter in ascii_uppercase:
        root = Path(f"{drive_letter}:\\")
        test_path = root / "Users"
        if test_path.exists():
            for user_dir in test_path.iterdir():
                journal_dir = user_dir / "Saved Games" / "Frontier Developments" / "Elite Dangerous"
                if journal_dir.exists():
                    candidate_dirs.append(journal_dir)

    journal_files = []
    for d in candidate_dirs:
        journal_files += list(d.glob("Journal.*.log"))

    if not journal_files:
        raise FileNotFoundError("No Elite Dangerous log files found.")

    latest_file = max(journal_files, key=os.path.getmtime)
    return latest_file

def monitor_session(hud: SessionHUD):
    """
    Monitors the latest Elite Dangerous journal for the events related to the displayed info,
    updates the HUD when a new system is entered.

    Args:
        hud (SystemHUD): The HUD instance to update with system and body data.
    """
    
    journal_path = find_latest_journal()
    print(f"[INFO] Reading journal : {journal_path}")

    with open(journal_path, 'r', encoding='utf-8') as f:
        f.seek(0, os.SEEK_END)

        while True:
            line = f.readline()
            if not line:
                time.sleep(0.1)
                continue

            try:
                data = json.loads(line)
                event = data.get("event")

                if event == "Bounty":
                    hud.stats["bounty"] += data.get("TotalReward")
                    hud.stats["kills"] += 1
                
                elif event == "PVPKill":
                    hud.stats["kills"] += 1

                elif event == "FSDJump":
                    hud.stats["distance"] += data.get("JumpDist", 0.0)
                    hud.stats["jumps"] += 1

                elif event == "MarketBuy":
                    hud.stats["buy"] += data.get("TotalCost")

                elif event == "MarketSell":
                    hud.stats["sell"] += data.get("TotalSale")
                
                elif event == "BuyTradeData" or event == "BuyExplorationData":
                    hud.stats["buy"] += data.get("Cost")
                
                elif event == "CodexEntry":
                    hud.stats["codex"] += 1
                
                elif event == "MultiSellExplorationData":
                    hud.stats["ExplorationData"] += data.get("TotalEarnings")

                hud.update()

            except json.JSONDecodeError:
                continue

# ====================== LANCEMENT ======================
def listen_commands(hud: SessionHUD):
    for line in sys.stdin:
        cmd = line.strip()
        if not cmd:
            continue
        hud.root.after(0, hud.apply_command_on_ui, cmd)

def update_loop(hud: SessionHUD):
    """
    Update the HUD every second to keep the session duration running.

    Args:
        hud (SessionHUD): The HUD instance
    """
    while True:
        hud.update()
        time.sleep(1)  # met à jour toutes les secondes

def main():
    """
    Entry point for the script.

    - Reads language info from command-line arguments (if any).
    - Initializes the HUD.
    - Starts the journal monitoring in a background thread.
    - Launches the HUD main loop.
    """
    
    global lang
    
    # Lecture d'un argument eventuel passé par le launcher
    if len(sys.argv) > 1:
        lang = sys.argv[1]
    
    hud = SessionHUD()

    threading.Thread(target=monitor_session, args=(hud,), daemon=True).start()
    threading.Thread(target=update_loop, args=(hud,), daemon=True).start()
    threading.Thread(target=listen_commands, args=(hud,), daemon=True).start()

    hud.run()

if __name__ == "__main__":
    main()
