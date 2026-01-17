# 🛡️ MAIN LOL - Assistant pour League of Legends

![Version](https://img.shields.io/badge/version-v7.0-blue.svg)
![Python](https://img.shields.io/badge/Python-3.13-green.svg)
![UI](https://img.shields.io/badge/UI-ttkbootstrap-purple.svg)
![Architecture](https://img.shields.io/badge/Architecture-Modulaire-orange.svg)

Un assistant de bureau moderne pour League of Legends qui automatise la phase de sélection des champions et améliore votre expérience de jeu.

---

## 🚀 Fonctionnalités

| Fonctionnalité | Description |
|:---|:---|
| **Auto-Accept** | Accepte la partie instantanément avec confirmation sonore |
| **Auto-Pick** | Sécurise vos champions par priorité (P1 → P2 → P3) |
| **Auto-Ban** | Bannit automatiquement votre "Némésis" |
| **Auto-Spells** | Configure vos sorts d'invocateur automatiquement |
| **Auto-Replay** | Retour au lobby après la partie (skip honor) |
| **Mode Discret** | Se masque dans le systray quand LoL est détecté |
| **Liens Rapides** | Accès direct OP.GG / Porofessor avec détection du compte |

---

## 🛠️ Installation (Source)

```bash
# 1. Cloner le dépôt
git clone https://github.com/qurnt1/main_lol_2.git
cd main_lol_2

# 2. Installer les dépendances
pip install -r requirements.txt

# 3. Lancer l'application
python launcher.py
```

---

## 📦 Compilation (Exécutable Portable)

```bash
python install.py
```

Génère `OTP LOL.exe` - un fichier unique portable (aucune installation requise).

---

## 📁 Architecture v7.0

```
MAIN_LOL/
├── launcher.py          # Point d'entrée principal
├── install.py           # Script de compilation PyInstaller
├── requirements.txt
├── src/                  # Package modulaire
│   ├── __init__.py
│   ├── config.py        # Constantes, chemins, paramètres
│   ├── core.py          # DataDragon, WebSocket (UI-agnostique)
│   ├── ui.py            # Interface graphique (Tkinter)
│   └── utils.py         # Utilitaires (lockfile, updates)
└── config/              # Assets (images, sons)
    ├── imgs/
    └── son.wav
```

### Améliorations techniques v7.0

- ✅ **Architecture modulaire** : Séparation claire (config/core/ui/utils)
- ✅ **Thread-Safety** : Communication UI via `root.after()` 
- ✅ **Mise à jour GitHub** : Via API Releases (plus de parsing README)
- ✅ **Cache LRU** : Images champions/sorts en mémoire
- ✅ **Type Hints** : Typage complet du code

---

## 💾 Fichiers de Configuration

| Fichier | Emplacement |
|:---|:---|
| **Paramètres** | `%APPDATA%\MainLoL\parameters.json` |
| **Logs** | `%APPDATA%\MainLoL\app_debug.log` |
| **Cache Champions** | `%TEMP%\mainlol_ddragon_champions.json` |
| **Cache Icônes** | `%TEMP%\mainlol_icons\` |

> ⚠️ **Note v7.0** : Les logs sont maintenant dans `%APPDATA%\MainLoL\`, plus jamais à la racine du projet.

---

## ⌨️ Raccourcis

| Raccourci | Action |
|:---|:---|
| `Alt + P` | Ouvre Porofessor |
| `Alt + C` | Affiche / Masque la fenêtre |

---

## 🔧 Dépendances

```
ttkbootstrap>=1.10.1
lcu-driver>=3.1.0
Pillow>=10.0.0
pygame>=2.5.0
pystray>=0.19.5
keyboard>=0.13.5
psutil>=5.9.5
requests>=2.31.0
```

---

## 🧑‍💻 Auteur

**Qurnt1** - Assisté par Gemini
