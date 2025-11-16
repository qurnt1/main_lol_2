# 🛡️ MAIN LOL - Assistant pour League of Legends (v4.4)

![Version](https://img.shields.io/badge/version-v4.4-blue.svg)
![Python](https://img.shields.io/badge/Python-3.9+-green.svg)
![UI](https://img.shields.io/badge/UI-ttkbootstrap-purple.svg)

Un assistant de bureau pour League of Legends qui automatise les actions fastidieuses de la sélection des champions (Champ Select) et fournit des utilitaires rapides.

## ✨ Fonctionnalités Principales

* **Auto-Accept:** Accepte automatiquement les parties dès qu'elles sont trouvées.
* **Auto-Ban:** BANNIT automatiquement et valide le champion de votre choix.
* **Auto-Pick (Priorité):** PICK votre champion par ordre de priorité (P1, P2, P3). Si P1 n'est pas disponible, il tente P2, puis P3.
* **Auto-Spells:** Définit automatiquement vos sorts d'invocateur (Ex: Flash + Heal). Configurable globalement.
* **Auto-Runes:** Sélectionne la page de runes si son nom correspond exactement au champion sélectionné.
* **Liens Rapides:** Ouvre OP.GG ou Porofessor avec votre pseudo (détecté ou manuel).
* **Détection Intelligente:** Utilise l'API LCU (via **WebSocket** si disponible, sinon **HTTP Polling**) pour une réactivité maximale.

## 🚀 Installation (Depuis le code source)

Ce projet est conçu pour être compilé, mais peut aussi être lancé depuis le code source.

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
    python main.py
    ```

## 📦 Compilation (Créer le .exe)

Si vous préférez utiliser l'application comme un programme indépendant sans avoir besoin d'installer Python ou des dépendances sur d'autres machines, vous pouvez la compiler en un fichier `.exe` unique.

Le projet inclut un script qui automatise l'ensemble du processus à l'aide de **PyInstaller**.

1.  **Assurez-vous d'avoir Python** installé sur votre machine (nécessaire uniquement pour l'étape de compilation).

2.  **Naviguez dans le dossier `Installer` :**
    ```bash
    cd chemin/vers/MAIN_LOL_v4/Installer
    ```

3.  **Exécutez le script d'installation :**
    ```python
    python installer.py
    ```

4.  **C'est tout !** Le script va :
    * Vérifier et installer `pyinstaller` si nécessaire.
    * Lire la configuration de build (`PyInstaller.txt`).
    * Compiler le code source.
    * Placer l'exécutable final (ex: `OTP LOL.exe`) **directement à la racine de votre dossier de projet** (`MAIN_LOL_v4`).

Vous pouvez ensuite déplacer ce fichier `.exe` où vous le souhaitez, il est 100% autonome.

## 🎮 Utilisation

1.  Lancez `main.py` (ou l'exécutable `.exe` si vous l'avez compilé).
2.  L'application démarre et attend que le client League of Legends (`LeagueClientUx.exe`) soit lancé.
3.  Une fois le client détecté (point vert 🟢), l'application se réduit dans la barre des tâches (system tray).
4.  Cliquez sur l'icône "Engrenage" (⚙️) dans l'application ou faites un clic droit sur l'icône dans la barre des tâches pour ouvrir les **Paramètres**.
5.  Configurez vos picks, bans, sorts et options.
6.  C'est tout ! L'application gérera la prochaine Champ Select pour vous.

## ⌨️ Raccourcis Clavier

* `Alt + P` : Ouvre votre profil **Porofessor** dans le navigateur.
* `Alt + C` : Affiche / Masque la fenêtre principale de l'application.

## 🛠️ Fonctionnalités Détaillées

### Gestion de la Connexion LCU

L'application utilise un WebSocket pour se connecter au client LoL :

* **WebSocket (`lcu_driver`) :** Si la bibliothèque `lcu_driver` est installée, l'application s'abonne aux événements LCU (League Client Updates) pour une réactivité instantanée. C'est le mode le plus rapide pour l'auto-accept.

### Configuration

* Tous vos paramètres sont sauvegardés dans `config/parameters.json`.
* L'application utilise **DataDragon** (l'API statique de Riot) pour récupérer les ID des champions et les met en cache (`tempfile`) pour un démarrage plus rapide.
* **Détection de Pseudo :** L'application peut détecter automatiquement votre Riot ID (Pseudo#TAG) ou vous pouvez le définir manuellement pour les liens externes.

### Interface

* Construite avec `ttkbootstrap` pour une interface moderne et thématique (le thème "darkly" est utilisé par défaut).
* Fonctionne en arrière-plan grâce à `pystray`, ne vous dérangeant que lorsque c'est nécessaire.
* L'application s'assure qu'une seule instance est lancée à la fois en utilisant un fichier `.lock`.

## 🧑‍💻 Auteur

* **Qurnt1** (Développeur principal)
* Mis à jour et assisté par Gemini.