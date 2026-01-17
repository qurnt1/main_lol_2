"""
MAIN LOL - Module de Configuration
----------------------------------
Contient toutes les constantes, endpoints, et la gestion des paramètres.
"""

import os
import sys
import json
import tempfile
import logging
from typing import Dict, Any, Optional

# ───────────────────────────────────────────────────────────────────────────
# LOGGING CONFIGURATION (configured after get_appdata_path is defined below)
# ───────────────────────────────────────────────────────────────────────────

# Note: logging.basicConfig is called at the end of this file to ensure
# the log file is ALWAYS in AppData, never in the project root.


# ───────────────────────────────────────────────────────────────────────────
# APPLICATION METADATA
# ───────────────────────────────────────────────────────────────────────────

CURRENT_VERSION: str = "6.1"
GITHUB_REPO_URL: str = "https://github.com/qurnt1/main_lol_2"
GITHUB_RELEASES_API: str = "https://api.github.com/repos/qurnt1/main_lol_2/releases/latest"

# ───────────────────────────────────────────────────────────────────────────
# DATA DRAGON URLS
# ───────────────────────────────────────────────────────────────────────────

URL_DD_VERSIONS: str = "https://ddragon.leagueoflegends.com/api/versions.json"
URL_DD_CHAMPIONS: str = "https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/champion.json"
URL_DD_SUMMONERS: str = "https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/summoner.json"
URL_DD_IMG_CHAMP: str = "https://ddragon.leagueoflegends.com/cdn/{version}/img/champion/{filename}"
URL_DD_IMG_SPELL: str = "https://ddragon.leagueoflegends.com/cdn/{version}/img/spell/{filename}"
URL_DD_SPLASH: str = "https://ddragon.leagueoflegends.com/cdn/img/champion/splash/{champion}_0.jpg"

# ───────────────────────────────────────────────────────────────────────────
# LCU API ENDPOINTS
# ───────────────────────────────────────────────────────────────────────────

EP_SESSION: str = "/lol-champ-select/v1/session"
EP_SESSION_TIMER: str = "/lol-champ-select/v1/session/timer"
EP_SESSION_LEGACY: str = "/lol-champ-select-legacy/v1/session"
EP_GAMEFLOW: str = "/lol-gameflow/v1/gameflow-phase"
EP_READY_CHECK: str = "/lol-matchmaking/v1/ready-check"
EP_PICKABLE: str = "/lol-champ-select/v1/pickable-champion-ids"
EP_CURRENT_SUMMONER: str = "/lol-summoner/v1/current-summoner"
EP_CHAT_ME: str = "/lol-chat/v1/me"
EP_LOGIN: str = "/lol-login/v1/session"

# ───────────────────────────────────────────────────────────────────────────
# GAME DATA MAPPINGS
# ───────────────────────────────────────────────────────────────────────────

REGION_LIST: list = ["euw", "eune", "na", "kr", "jp", "br", "lan", "las", "oce", "tr", "ru"]

SUMMONER_SPELL_MAP: Dict[str, int] = {
    "Barrier": 21, "Cleanse": 1, "Exhaust": 3, "Flash": 4, "Ghost": 6,
    "Heal": 7, "Ignite": 14, "Smite": 11, "Teleport": 12, "(Aucun)": 0
}

SUMMONER_SPELL_LIST: list = sorted(list(SUMMONER_SPELL_MAP.keys()))

PLATFORM_TO_REGION: Dict[str, str] = {
    "euw1": "euw", "eun1": "eune", "na1": "na", "kr": "kr", 
    "jp1": "jp", "br1": "br", "la1": "lan", "la2": "las", 
    "oc1": "oce", "tr1": "tr", "ru": "ru"
}

PHASE_DISPLAY_MAP: Dict[str, str] = {
    "Lobby": "Au Salon (Lobby)",
    "Matchmaking": "Recherche de partie...",
    "ReadyCheck": "Partie trouvée !",
    "ChampSelect": "Sélection des champions",
    "InProgress": "Partie en cours",
    "EndOfGame": "Fin de partie",
    "WaitingForStats": "En attente des stats",
    "PreEndOfGame": "Nexus détruit",
    "None": "Inactif"
}

# ───────────────────────────────────────────────────────────────────────────
# DEFAULT PARAMETERS
# ───────────────────────────────────────────────────────────────────────────

DEFAULT_PARAMS: Dict[str, Any] = {
    "auto_accept_enabled": True,
    "auto_pick_enabled": True,
    "auto_ban_enabled": True,
    "auto_summoners_enabled": True,
    "selected_pick_1": "Garen",
    "selected_pick_2": "Lux",
    "selected_pick_3": "Ashe",
    "selected_ban": "Teemo",
    "region": "euw",
    "theme": "darkly",
    "summoner_name_auto_detect": True,
    "manual_summoner_name": "VotrePseudo#VotreTag",
    "global_spell_1": "Heal",
    "global_spell_2": "Flash",
    "auto_play_again_enabled": False,
    "auto_hide_on_connect": True,
    "close_app_on_lol_exit": True,
}

# ───────────────────────────────────────────────────────────────────────────
# PATH UTILITIES
# ───────────────────────────────────────────────────────────────────────────

def resource_path(relative_path: str) -> str:
    """
    Retourne le chemin absolu vers une ressource, compatible avec PyInstaller.
    
    Args:
        relative_path: Chemin relatif vers la ressource (depuis la racine du projet)
        
    Returns:
        Chemin absolu vers la ressource
    """
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        # Le fichier config.py est dans src/, donc on remonte d'un niveau
        current_dir = os.path.dirname(os.path.abspath(__file__))
        base_path = os.path.dirname(current_dir)  # Remonte de src/ vers la racine
    
    # Nettoyer le préfixe "./" ou ".\\"
    if relative_path.startswith("./"):
        relative_path = relative_path[2:]
    elif relative_path.startswith(".\\"):
        relative_path = relative_path[2:]
    
    return os.path.join(base_path, relative_path)



def get_appdata_path(filename: str) -> str:
    """
    Retourne le chemin vers un fichier dans le dossier AppData de l'application.
    
    Args:
        filename: Nom du fichier
        
    Returns:
        Chemin complet vers le fichier dans AppData/MainLoL/
    """
    app_data_dir = os.getenv('APPDATA')
    if not app_data_dir:
        return filename
    
    app_folder = os.path.join(app_data_dir, "MainLoL")
    if not os.path.exists(app_folder):
        try:
            os.makedirs(app_folder)
        except OSError:
            return filename
    
    return os.path.join(app_folder, filename)


# ───────────────────────────────────────────────────────────────────────────
# FILE PATHS
# ───────────────────────────────────────────────────────────────────────────

PARAMETERS_PATH: str = get_appdata_path("parameters.json")
LOCKFILE_PATH: str = os.path.join(tempfile.gettempdir(), 'main_lol.lock')
DDRAGON_CACHE_FILE: str = os.path.join(tempfile.gettempdir(), "mainlol_ddragon_champions.json")
ICONS_CACHE_DIR: str = os.path.join(tempfile.gettempdir(), "mainlol_icons")
SPELLS_CACHE_DIR: str = os.path.join(tempfile.gettempdir(), "mainlol_spells")

# ───────────────────────────────────────────────────────────────────────────
# PARAMETERS MANAGEMENT
# ───────────────────────────────────────────────────────────────────────────

def load_parameters() -> Dict[str, Any]:
    """
    Charge les paramètres depuis le fichier JSON.
    
    Returns:
        Dictionnaire des paramètres (valeurs par défaut si fichier inexistant)
    """
    if not os.path.exists(PARAMETERS_PATH):
        return DEFAULT_PARAMS.copy()
    
    try:
        with open(PARAMETERS_PATH, 'r', encoding='utf-8') as f:
            config = json.load(f)
        # Fusionner avec les valeurs par défaut pour les clés manquantes
        merged = DEFAULT_PARAMS.copy()
        merged.update(config)
        return merged
    except (json.JSONDecodeError, IOError) as e:
        logging.warning(f"Erreur chargement paramètres: {e}")
        return DEFAULT_PARAMS.copy()


def save_parameters(params: Dict[str, Any]) -> bool:
    """
    Sauvegarde les paramètres dans le fichier JSON.
    
    Args:
        params: Dictionnaire des paramètres à sauvegarder
        
    Returns:
        True si succès, False sinon
    """
    try:
        os.makedirs(os.path.dirname(PARAMETERS_PATH), exist_ok=True)
        with open(PARAMETERS_PATH, 'w', encoding='utf-8') as f:
            json.dump(params, f, indent=4, ensure_ascii=False)
        return True
    except (IOError, OSError) as e:
        logging.error(f"Erreur sauvegarde paramètres: {e}")
        return False


def get_cache_dirs() -> None:
    """Crée les dossiers de cache s'ils n'existent pas."""
    for cache_dir in [ICONS_CACHE_DIR, SPELLS_CACHE_DIR]:
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir, exist_ok=True)


# ───────────────────────────────────────────────────────────────────────────
# LOGGING CONFIGURATION (STRICT: AppData ONLY)
# ───────────────────────────────────────────────────────────────────────────

def _setup_logging() -> str:
    """
    Configure le logging vers AppData/MainLoL/app_debug.log.
    
    Returns:
        Chemin absolu du fichier de log
    """
    # STRICT: Le log doit TOUJOURS être dans AppData, JAMAIS à la racine du projet
    app_data_dir = os.getenv('APPDATA')
    if not app_data_dir:
        # Fallback Windows: utiliser le dossier utilisateur
        app_data_dir = os.path.expanduser("~")
    
    log_folder = os.path.join(app_data_dir, "MainLoL")
    
    # Créer le dossier s'il n'existe pas
    if not os.path.exists(log_folder):
        try:
            os.makedirs(log_folder, exist_ok=True)
        except OSError:
            # En dernier recours seulement, utiliser temp
            log_folder = tempfile.gettempdir()
    
    log_path = os.path.join(log_folder, "app_debug.log")
    
    # Configuration du logging
    logging.basicConfig(
        filename=log_path,
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        encoding='utf-8'
    )
    
    return log_path


# Initialiser le logging au chargement du module
LOG_FILE_PATH: str = _setup_logging()
