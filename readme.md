# 🛡️ MAIN LOL - Assistant pour League of Legends (v5.0)

![Version](https://img.shields.io/badge/version-v5.0-blue.svg)
![Python](https://img.shields.io/badge/Python-3.13-green.svg)
![UI](https://img.shields.io/badge/UI-ttkbootstrap-purple.svg)

Un assistant de bureau moderne pour League of Legends qui automatise la phase de sélection (Champ Select), gère vos runes et améliore votre expérience de jeu.

## ✨ Nouveautés de la v5.0

* 🖼️ **Sélecteurs Visuels :** Fini les listes textuelles ! Choisissez vos champions et sorts via une interface visuelle fluide avec recherche intégrée.
* ⚡ **Runes Natives (LCU) :** L'application injecte désormais directement les pages recommandées par Riot (plus rapide et fiable que les sites tiers).
* 🔊 **Smart Audio :** Gestion intelligente du son (plus de spam sonore au lancement ou à l'acceptation).
* 🛑 **Logique Anti-Doublon :** Impossible de sélectionner le même champion sur plusieurs slots (Pick/Ban).

## 🚀 Fonctionnalités Principales

* **Auto-Accept :** Accepte la partie instantanément (avec un unique son de confirmation).
* **Auto-Pick (Priorité) :** Tente de sécuriser vos champions par ordre de priorité (P1 > P2 > P3).
* **Auto-Ban :** Bannit automatiquement votre "Némésis" (avec exclusion automatique des picks).
* **Auto-Spells :** Assigne vos sorts d'invocateur favoris à chaque partie.
* **Auto-Replay :** Clique automatiquement sur "Rejouer" à la fin de la partie (skip des stats).
* **Mode Discret :** L'application se masque automatiquement dans le systray quand le jeu est détecté.
* **Liens Rapides :** Accès direct à OP.GG ou Porofessor avec détection automatique de votre compte actif.

## 🛠️ Installation (Code Source)

1.  **Clonez le dépôt :**
    ```bash
    git clone https://github.com/qurnt1/main_lol.git
    cd MAIN_LOL
    ```

2.  **Installez les dépendances :**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Lancez l'application :**
    ```bash
    python app.py
    ```

## 📦 Compilation (Exécutable Portable)

Un script d'installation intelligent est inclus pour créer une version portable (sans besoin de Python).

1.  Lancez le script de construction :
    ```bash
    python install.py
    ```

2.  Le script va compiler l'application et créer un fichier **`OTP LOL.exe`**.
    * *Note : Le fichier **`OTP LOL.exe`** est portable, vous pouvez le lancer de n'importe ou*

## 💾 Configuration & Sauvegarde

Vos préférences sont sauvegardées automatiquement à chaque fermeture ou modification.

* **Fichier de config :** `%APPDATA%\\MainLoL\\parameters.json`
* **Cache Images :** `%TEMP%\\mainlol_icons` (Pour un chargement ultra-rapide des assets).

## 🎮 Guide d'Utilisation

1.  Lancez l'application.
2.  **Statut :**
    * 🔴 **Rouge :** En attente du client League of Legends.
    * 🟢 **Vert :** Connecté au client (WebSocket Actif).
3.  Cliquez sur l'engrenage ⚙️ pour ouvrir les paramètres :
    * Cliquez sur les boutons de Champions/Sorts pour ouvrir la grille de sélection visuelle.
    * Activez les options (Auto-Accept, Auto-Runes, etc.).
4.  Laissez l'application tourner en fond (réduisez-la dans la barre des tâches).

## ⌨️ Raccourcis Clavier

| Raccourci | Action |
| :--- | :--- |
| `Alt + P` | Ouvre votre profil **Porofessor** dans le navigateur. |
| `Alt + C` | Affiche / Masque la fenêtre principale. |

## ⚙️ Technique

* **Architecture :** Python + Tkinter (ttkbootstrap).
* **Connexion LCU :** Utilise `lcu_driver` pour une communication WebSocket en temps réel (0 latence).
* **DataDragon :** Télécharge et met en cache les images des champions/sorts depuis l'API Riot officielle.
* **AsyncIO :** Gestion asynchrone pour une interface qui ne freeze jamais.

## 🧑‍💻 Auteur

* **Qurnt1** (Développeur)
* Assisté par Gemini.
