"""
Launcher for Elite Dangerous HUDs (Heads-Up Displays).

This script provides a graphical interface using Pygame to launch and manage multiple HUD modules
used in Elite Dangerous, including system stats, exobiology tools, and session statistics. It also
offers a language selection menu.

Modules launched:
- HUD_System.py
- HUD_ExoBio.py
- HUD_SessionStats.py

Language support is loaded from the external Language.py module.
"""

import subprocess
import os
import pygame
pygame.init()

import Language # Language file

fenetre = pygame.display.set_mode((500, 350), pygame.DOUBLEBUF, pygame.HWSURFACE)
pygame.display.set_caption("Elite HUD launcher")

sys_process = None
joystick_process = None
exobio_process = None
stats_process = None

lang = "english" # default language

def lancer_systeme():
    """
    Launches the system HUD module as a subprocess.
    """
    
    global sys_process
    sys_process = subprocess.Popen(["python", "HUD_System.py", lang], stdin=subprocess.PIPE, text=True, encoding="utf-8", bufsize=1)
    send_cmd_to_hud("HUD_Sys", "HUD_ExoBio")

def arreter_systeme():
    """
    Terminates the system HUD subprocess if running.
    """
    
    global sys_process
    if sys_process and sys_process.poll() is None:
        sys_process.terminate() # ou .kill() si inefficace
        sys_process = None
    send_cmd_to_hud("HUD_Sys_Stop", "HUD_ExoBio")


def lancer_exobio(HUD_Systeme_running):
    """
    Launches the ExoBiology HUD module as a subprocess.

    Args:
        HUD_Systeme_running (bool): Whether the system HUD is running, to adjust window position.
    """
    
    global exobio_process
    
    decalerFenetreExobio = "False"
    if HUD_Systeme_running:
        decalerFenetreExobio = "True"
    else:
        decalerFenetreExobio = "False"
    
    exobio_process = subprocess.Popen(["python", "HUD_ExoBio.py", lang, decalerFenetreExobio], stdin=subprocess.PIPE, text=True, encoding="utf-8", bufsize=1)

def arreter_exobio():
    """
    Terminates the ExoBiology HUD subprocess if running.
    """
    
    global exobio_process
    if exobio_process and exobio_process.poll() is None:
        exobio_process.terminate() # ou .kill() si inefficace
        exobio_process = None


def lancer_stats():
    """
    Launches the session statistics HUD module as a subprocess.
    """
    
    global stats_process
    stats_process = subprocess.Popen(["python", "HUD_SessionStats.py", lang], stdin=subprocess.PIPE, text=True, encoding="utf-8", bufsize=1)

def arreter_stats():
    """
    Terminates the session statistics HUD subprocess if running.
    """
    
    global stats_process
    if stats_process and stats_process.poll() is None:
        stats_process.terminate() # ou .kill() si inefficace
        stats_process = None


def send_cmd_to_hud(value, targetHUD):
    if targetHUD == "HUD_Sys" and sys_process and sys_process.poll() is None:
        sys_process.stdin.write(value + "\n")
        sys_process.stdin.flush()

    elif targetHUD == "HUD_ExoBio" and exobio_process and exobio_process.poll() is None:
        exobio_process.stdin.write(value + "\n")
        exobio_process.stdin.flush()

    elif targetHUD == "HUD_SessionStats" and stats_process and stats_process.poll() is None:
        stats_process.stdin.write(value + "\n")
        stats_process.stdin.flush()


def Choose_lang(fenetre):
    """
    Displays a Pygame interface to allow the user to select a language.

    Args:
        fenetre (pygame.Surface): The Pygame window surface.

    Returns:
        str: The chosen language code ("french" or "english").
    """
    
    police = pygame.font.Font(None, 30)
    
    chosen_Lang = ""
    
    #                                 x  y  width height
    French_button_rect = pygame.Rect(50, 50, 150, 50)
    English_button_rect = pygame.Rect(300, 50, 150, 50)
    
    French_button_color = (255, 255, 255)
    English_button_color = (255, 255, 255)
    
    text_French = police.render("Français", True, (0, 0, 0))
    text_English = police.render("English", True, (0, 0, 0))
    
    text_French_rect = text_French.get_rect(center=(French_button_rect.centerx, French_button_rect.centery))
    text_English_rect = text_English.get_rect(center=(English_button_rect.centerx, English_button_rect.centery))
    
    run = True
    while run:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                run = False

            elif event.type == pygame.MOUSEMOTION:
                # Position de la souris
                x, y = pygame.mouse.get_pos()
            
                # Vérification de la position de la souris pour mettre à jour la couleur des boutons
                if French_button_rect[0] <= x <= (French_button_rect[0] + French_button_rect[2]) and French_button_rect[1] <= y <= (French_button_rect[1] + French_button_rect[3]):
                    French_button_color = (255, 255, 0)
                else:
                    French_button_color = (255, 255, 255)
                
                if English_button_rect[0] <= x <= (English_button_rect[0] + English_button_rect[2]) and English_button_rect[1] <= y <= (English_button_rect[1] + English_button_rect[3]):
                    English_button_color = (255, 255, 0)
                else:
                    English_button_color = (255, 255, 255)
            
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                # Gestion du clic sur les boutons                
                if French_button_rect[0] <= x <= (French_button_rect[0] + French_button_rect[2]) and French_button_rect[1] <= y <= (French_button_rect[1] + French_button_rect[3]):
                    print("Button Français clicked")
                    chosen_Lang = "french"
                    run = False
                
                if English_button_rect[0] <= x <= (English_button_rect[0] + English_button_rect[2]) and English_button_rect[1] <= y <= (English_button_rect[1] + English_button_rect[3]):
                    print("Button English clicked")
                    chosen_Lang = "english"
                    run = False
    
        fenetre.fill((0, 0, 0))
        
        pygame.draw.rect(fenetre, French_button_color, French_button_rect)
        pygame.draw.rect(fenetre, English_button_color, English_button_rect)
        
        fenetre.blit(text_French, text_French_rect)
        fenetre.blit(text_English, text_English_rect)
        
        pygame.display.flip()

        send_cmd_to_hud(f"{chosen_Lang}", "HUD_System")
        send_cmd_to_hud(f"{chosen_Lang}", "HUD_ExoBio")
        send_cmd_to_hud(f"{chosen_Lang}", "HUD_SessionStats")

    return chosen_Lang

def Choose_Interesting():
    os.startfile("interestingTypes.json")

def run():
    """
    Main loop of the launcher interface.

    Displays clickable buttons to launch or stop each HUD component.
    Handles real-time interaction and language switching.
    """
    
    global lang
    
    HUD_Systeme_running = False
    HUD_Stats_running = False
    HUD_Combat_running = False
    HUD_ExoBio_running = False
    
    police1 = pygame.font.Font(None, 30)

    # Variables pour les couleurs de survol
    GREEN = (0, 150, 100)
    RED = (180, 0, 0)
    BLUE = (0, 100, 255)
    WHITE = (255, 255, 255)
    BLACK = (0, 0, 0)
    YELLOW = (255, 255, 0)
    
    button_Lang_x = 150
    button_Lang_y = 50
    button_Lang_width = 200
    button_Lang_height = 50
    button_Lang_color = WHITE
    button_Lang_text = Language.languages[lang]["Launcher"]["Lang"] # In Language.py, target language, HUD name, target word
    
    button_InterestingTypes_x = 200
    button_InterestingTypes_y = 150
    button_InterestingTypes_width = 50
    button_InterestingTypes_height = 50

    button1_x = 50
    button1_y = 150
    button1_width = 150
    button1_height = 50
    button1_color = GREEN
    button1_text = Language.languages[lang]["Launcher"]["Systems"]

    button2_x = 300
    button2_y = 150
    button2_width = 150
    button2_height = 50
    button2_color = GREEN
    button2_text = Language.languages[lang]["Launcher"]["ExoBio"]

    button3_x = 50
    button3_y = 250
    button3_width = 150
    button3_height = 50
    button3_color = GREEN
    button3_text = Language.languages[lang]["Launcher"]["Combat"]
    
    button4_x = 300
    button4_y = 250
    button4_width = 150
    button4_height = 50
    button4_color = GREEN
    button4_text = Language.languages[lang]["Launcher"]["Stats"]

    button_Lang_rect = pygame.Rect(button_Lang_x, button_Lang_y, button_Lang_width, button_Lang_height)
    #button_InterestingTypes_rect = pygame.Rect(button_InterestingTypes_x, button_InterestingTypes_y, button_InterestingTypes_width, button_InterestingTypes_height)
    button1_rect = pygame.Rect(button1_x, button1_y, button1_width, button1_height)
    button2_rect = pygame.Rect(button2_x, button2_y, button2_width, button2_height)
    button3_rect = pygame.Rect(button3_x, button3_y, button3_width, button3_height)
    button4_rect = pygame.Rect(button4_x, button4_y, button4_width, button4_height)

    texte_Lang = police1.render(button_Lang_text, True, BLACK)
    texte_1 = police1.render(button1_text, True, WHITE)
    texte_2 = police1.render(button2_text, True, WHITE)
    texte_3 = police1.render(button3_text, True, WHITE)
    texte_4 = police1.render(button4_text, True, WHITE)

    texte_Lang_rect = texte_Lang.get_rect(center=(button_Lang_rect.centerx, button_Lang_rect.centery))
    texte_1_rect = texte_1.get_rect(center=(button1_rect.centerx, button1_rect.centery))
    texte_2_rect = texte_2.get_rect(center=(button2_rect.centerx, button2_rect.centery))
    texte_3_rect = texte_3.get_rect(center=(button3_rect.centerx, button3_rect.centery))
    texte_4_rect = texte_4.get_rect(center=(button4_rect.centerx, button4_rect.centery))
    
    ImageInterestingTypes = pygame.image.load("HUD_System_Setting_Icon.png")
    ImageInterestingTypes = pygame.transform.scale(ImageInterestingTypes, (45, 45))
    #ImageInterestingTypes_rect = ImageInterestingTypes.get_rect(topleft=(button_InterestingTypes_x + 5, button_InterestingTypes_y + 5))
    InterestingTypesCOLOR = WHITE
    
    run = True
    while run:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                run = False
                arreter_systeme()
                arreter_exobio()
                arreter_stats()

            elif event.type == pygame.MOUSEMOTION:
                # Position de la souris
                x, y = pygame.mouse.get_pos()
            
                # Vérification de la position de la souris pour mettre à jour la couleur des boutons
                if button_Lang_x <= x <= (button_Lang_x + button_Lang_width) and button_Lang_y <= y <= (button_Lang_y + button_Lang_height):
                    button_Lang_color = YELLOW
                else:
                    button_Lang_color = WHITE
                
                if button_InterestingTypes_x <= x <= (button_InterestingTypes_x + button_InterestingTypes_width) and button_InterestingTypes_y <= y <= (button_InterestingTypes_y + button_InterestingTypes_height):
                    InterestingTypesCOLOR = YELLOW
                else:
                    InterestingTypesCOLOR = WHITE
                    
                if button1_x <= x <= (button1_x + button1_width) and button1_y <= y <= (button1_y + button1_height):
                    button1_color = BLUE
                elif HUD_Systeme_running:
                    button1_color = RED
                else:
                    button1_color = GREEN

                if button2_x <= x <= (button2_x + button2_width) and button2_y <= y <= (button2_y + button2_height):
                    button2_color = BLUE
                elif HUD_ExoBio_running:
                    button2_color = RED
                else:
                    button2_color = GREEN

                if button3_x <= x <= (button3_x + button3_width) and button3_y <= y <= (button3_y + button3_height):
                    button3_color = BLUE
                elif HUD_Combat_running:
                    button3_color = RED
                else:
                    button3_color = GREEN
                    
                if button4_x <= x <= (button4_x + button4_width) and button4_y <= y <= (button4_y + button4_height):
                    button4_color = BLUE
                elif HUD_Stats_running:
                    button4_color = RED
                else:
                    button4_color = GREEN
            
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                # Gestion du clic sur les boutons                
                if button_Lang_x <= x <= (button_Lang_x + button_Lang_width) and button_Lang_y <= y <= (button_Lang_y + button_Lang_height):
                    print("Button Lang clicked")
                    lang = Choose_lang(fenetre)
                    
                    # Update the text of the butons
                    button_Lang_text = Language.languages[lang]["Launcher"]["Lang"]
                    button1_text = Language.languages[lang]["Launcher"]["Systems"]
                    button2_text = Language.languages[lang]["Launcher"]["ExoBio"]
                    button3_text = Language.languages[lang]["Launcher"]["Combat"]
                    button4_text = Language.languages[lang]["Launcher"]["Stats"]
                    
                    texte_Lang = police1.render(button_Lang_text, True, BLACK)
                    texte_1 = police1.render(button1_text, True, WHITE)
                    texte_2 = police1.render(button2_text, True, WHITE)
                    texte_3 = police1.render(button3_text, True, WHITE)
                    texte_4 = police1.render(button4_text, True, WHITE)

                    texte_Lang_rect = texte_Lang.get_rect(center=(button_Lang_rect.centerx, button_Lang_rect.centery))
                    texte_1_rect = texte_1.get_rect(center=(button1_rect.centerx, button1_rect.centery))
                    texte_2_rect = texte_2.get_rect(center=(button2_rect.centerx, button2_rect.centery))
                    texte_3_rect = texte_3.get_rect(center=(button3_rect.centerx, button3_rect.centery))
                    texte_4_rect = texte_4.get_rect(center=(button4_rect.centerx, button4_rect.centery))
                    
                
                if button_InterestingTypes_x <= x <= (button_InterestingTypes_x + button_InterestingTypes_width) and button_InterestingTypes_y <= y <= (button_InterestingTypes_y + button_InterestingTypes_height) and not HUD_Systeme_running:
                    print("Button InterestingTypes clicked")
                    Choose_Interesting()
                    
                
                if button1_x <= x <= (button1_x + button1_width) and button1_y <= y <= (button1_y + button1_height) and not HUD_Systeme_running:
                    print("Button 1 clicked")
                    # Executer un le fichier HUD_Systemev5.py dans un thread séparé
                    lancer_systeme()
                    HUD_Systeme_running = True
                    
                elif button1_x <= x <= (button1_x + button1_width) and button1_y <= y <= (button1_y + button1_height) and HUD_Systeme_running:
                    print("Button 1 already running, stopping it")
                    arreter_systeme()
                    HUD_Systeme_running = False
                    
                
                if button2_x <= x <= (button2_x + button2_width) and button2_y <= y <= (button2_y + button2_height) and not HUD_ExoBio_running:
                    print("Button 2 clicked")
                    # Executer un le fichier HUD_Joystickv8.py dans un thread séparé
                    lancer_exobio(HUD_Systeme_running)
                    HUD_ExoBio_running = True
                    
                elif button2_x <= x <= (button2_x + button2_width) and button2_y <= y <= (button2_y + button2_height) and HUD_ExoBio_running:
                    print("Button 2 already running, stopping it")
                    arreter_exobio()
                    HUD_ExoBio_running = False
                    
                
                if button3_x <= x <= (button3_x + button3_width) and button3_y <= y <= (button3_y + button3_height) and not HUD_Combat_running:
                    print("Button 3 clicked")
                    HUD_Combat_running = True
                    
                elif button3_x <= x <= (button3_x + button3_width) and button3_y <= y <= (button3_y + button3_height) and HUD_Combat_running:
                    print("Button 3 already running, stopping it")
                    HUD_Combat_running = False
                    
                
                if button4_x <= x <= (button4_x + button4_width) and button4_y <= y <= (button4_y + button4_height) and not HUD_Stats_running:
                    print("Button 4 clicked")
                    lancer_stats()
                    HUD_Stats_running = True
                    
                elif button4_x <= x <= (button4_x + button4_width) and button4_y <= y <= (button4_y + button4_height) and HUD_Stats_running:
                    print("Button 4 already running, stopping it")
                    arreter_stats()
                    HUD_Stats_running = False
                    
        
        fenetre.fill((0, 0, 0)) # Fond noir

        # Dessiner les boutons
        pygame.draw.rect(fenetre, button_Lang_color, button_Lang_rect)
        pygame.draw.rect(fenetre, button1_color, button1_rect)
        pygame.draw.rect(fenetre, button2_color, button2_rect)
        pygame.draw.rect(fenetre, button3_color, button3_rect)
        pygame.draw.rect(fenetre, button4_color, button4_rect)
        
        pygame.draw.rect(fenetre, InterestingTypesCOLOR, (button_InterestingTypes_x, button_InterestingTypes_y, 50, 50))
        fenetre.blit(ImageInterestingTypes, (button_InterestingTypes_x + 2, button_InterestingTypes_y + 2))
        
        fenetre.blit(texte_Lang, texte_Lang_rect)
        fenetre.blit(texte_1, texte_1_rect)
        fenetre.blit(texte_2, texte_2_rect)
        fenetre.blit(texte_3, texte_3_rect)
        fenetre.blit(texte_4, texte_4_rect)

        pygame.display.flip()

run()
pygame.quit()