# 🛡️ MAIN LOL - Assistant pour League of Legends (v4.9)

![Version](https://img.shields.io/badge/version-v4.9-blue.svg)
![Python](https://img.shields.io/badge/Python-3.9+-green.svg)
![UI](https://img.shields.io/badge/UI-ttkbootstrap-purple.svg)

Un assistant de bureau pour League of Legends qui automatise les actions fastidieuses de la sélection des champions (Champ Select) et fournit des utilitaires rapides.

## ✨ Fonctionnalités Principales

* **Auto-Accept :** Accepte automatiquement la partie dès qu'elle est trouvée.
* **Auto-Pick (Priorité) :** Tente de sécuriser vos champions préférés par ordre de priorité (P1, P2, P3).
* **Auto-Ban :** Bannit automatiquement le champion que vous détestez (validation incluse).
* **Auto-Spells :** Assigne automatiquement vos sorts d'invocateur (Ex: Flash sur F).
* **Auto-Runes (Méta) :** Importe automatiquement les meilleures runes pour votre champion et votre rôle via **Runeforge.gg**.
* **Auto-Replay :** Clique automatiquement sur "Rejouer" à la fin de la partie (skip des stats).
* **Mode Discret :** L'application peut se masquer automatiquement dès que le client LoL est détecté.
* **Liens Rapides :** Accès direct à OP.GG ou Porofessor avec détection automatique de votre pseudo/région.

## 🚀 Installation (Depuis le code source)

1.  **Clonez le dépôt :**
    ```bash
    git clone [https://github.com/qurnt1/main_lol.git](https://github.com/qurnt1/main_lol.git)
    cd MAIN_LOL_v4
    ```

2.  **Installez les dépendances :**
    Assurez-vous d'avoir Python 3.9+ installé.
    ```bash
    pip install -r requirements.txt
    ```

3.  **Lancez l'application :**
    ```python
    python app.py
    ```

## 📦 Compilation (Créer l'application portable)

Ce projet inclut un script de construction intelligent utilisant **PyInstaller**.
L'application est compilée en **mode dossier (OneDir)** pour un démarrage instantané et une meilleure stabilité.

1.  **Assurez-vous d'avoir Python** installé sur votre machine.

2.  **Lancez le script de construction :**
    ```bash
    python installer_en_exe.py
    ```

3.  **C'est tout !** Le script va :
    * Installer `pyinstaller` si nécessaire.
    * Compiler le code et inclure les ressources (images, configs par défaut).
    * Créer un dossier nommé **`OTP LOL`** à la racine du projet.

👉 **Pour lancer l'app :** Ouvrez le dossier `OTP LOL` et lancez `OTP LOL.exe`.
Vous pouvez déplacer ce dossier entier où vous voulez (sur une clé USB, un autre disque, etc.).

## 💾 Sauvegarde des Paramètres

Pour garantir que vos réglages ne soient jamais perdus (même si vous mettez à jour l'application), la configuration est sauvegardée dans le dossier utilisateur de Windows :

* **Emplacement :** `%APPDATA%\MainLoL\parameters.json`
    *(Généralement : `C:\Users\VotreNom\AppData\Roaming\MainLoL`)*

Les images et ressources visuelles restent contenues dans le dossier de l'application.

## 🎮 Utilisation

1.  Lancez `OTP LOL.exe`.
2.  L'application attend que le client League of Legends soit ouvert.
3.  **Statut :**
    * 🔴 **Rouge :** En attente de LoL.
    * 🟢 **Vert :** Connecté au WebSocket LCU (Réactivité maximale).
4.  **Configuration :** Cliquez sur l'icône ⚙️ (Engrenage) pour régler vos picks, bans et activer les runes auto.
5.  L'application peut être réduite dans la zone de notification (System Tray) pour ne pas encombrer votre écran.

## ⌨️ Raccourcis Clavier

* `Alt + P` : Ouvre votre profil **Porofessor** dans le navigateur.
* `Alt + C` : Affiche / Masque la fenêtre principale de l'application.

## 🛠️ Fonctionnalités Techniques

* **WebSocket LCU :** Utilise `lcu_driver` pour une communication temps réel avec le client (plus rapide que la détection d'image ou le polling HTTP classique).
* **DataDragon :** Mise en cache locale des données des champions pour réduire les appels API.
* **Architecture Async :** Utilise `asyncio` et `aiohttp` pour gérer les requêtes externes (Runeforge) sans bloquer l'interface.

## 🧑‍💻 Auteur

* **Qurnt1** (Développeur principal)
* Assisté par Gemini.