# HUD for Elite Dangerous

## 🧾 Description

This project is a custom Heads-Up Display (HUD) for Elite Dangerous that provides real-time information for exploration and exobiology, session statistics (coming soon), and tactical decision support (planned). It reads the game’s journal logs to extract key data such as your current system, credits earned, kills, targets scanned, and more. The HUD is designed to be fast and lightweight, with a clean interface built using Python’s tkinter, and leverages modules like pygame and requests for enhanced functionality.

## 🚀 Features
- Displays interesting planets and stars to scan in your current system (Universal Cartographics)
- Highlights planets with potential exobiology and displays the possible hight-value species
- Simple UI with `tkinter`
- Lightweight and efficient
- Coming soon: real-time session statistics (credits earned, kills, distance traveled, etc.)
- Planned: risk analysis

## ⚙️ Installation

### Prerequisites

- Python 3.13
- Required modules:
  - `pygame`
  - `requests`
- Other modules are from the Python standard library

### Install dependencies

```bash
pip install -r requirements.txt
```

## Run the project

`python HUD_Launcher.py` in a terminal or run `HUD_Launcher.py` directly.
You can also run individual HUD modules directly, but this is not recommended due to potential overlay issues.

## 📄 License

This project is licensed under the [MIT License](./LICENSE).

