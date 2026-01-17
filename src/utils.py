"""
MAIN LOL - Module Utilitaires
-----------------------------
Fonctions utilitaires: lockfile, mise à jour, DPI, etc.
"""

import os
import sys
import logging
import requests
from typing import Optional

import psutil

from .config import LOCKFILE_PATH, GITHUB_RELEASES_API, CURRENT_VERSION


# ───────────────────────────────────────────────────────────────────────────
# HIGH DPI AWARENESS (Windows)
# ───────────────────────────────────────────────────────────────────────────

def enable_high_dpi() -> None:
    """Active la gestion du High DPI sous Windows."""
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass


# ───────────────────────────────────────────────────────────────────────────
# SINGLE INSTANCE (LOCKFILE)
# ───────────────────────────────────────────────────────────────────────────

def check_single_instance() -> bool:
    """
    Vérifie qu'une seule instance de l'application est en cours.
    
    Returns:
        True si cette instance peut continuer, False si une autre existe déjà
    """
    if os.path.exists(LOCKFILE_PATH):
        try:
            with open(LOCKFILE_PATH, 'r') as f:
                pid = int(f.read())
            if pid != os.getpid() and psutil.pid_exists(pid):
                logging.info(f"Instance existante détectée (PID: {pid})")
                return False
        except (ValueError, IOError):
            pass
    
    # Créer/mettre à jour le lockfile
    try:
        with open(LOCKFILE_PATH, 'w') as f:
            f.write(str(os.getpid()))
    except IOError:
        pass
    
    return True


def remove_lockfile() -> None:
    """Supprime le lockfile lors de la fermeture."""
    try:
        if os.path.exists(LOCKFILE_PATH):
            os.remove(LOCKFILE_PATH)
    except IOError:
        pass


# ───────────────────────────────────────────────────────────────────────────
# UPDATE CHECKING (GitHub Releases API)
# ───────────────────────────────────────────────────────────────────────────

def check_for_updates() -> Optional[str]:
    """
    Vérifie les mises à jour via l'API GitHub Releases.
    
    Returns:
        Nouvelle version disponible (str) ou None si à jour
    """
    try:
        logging.info("[Update] Vérification via GitHub Releases API...")
        
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "MainLoL-UpdateChecker"
        }
        
        resp = requests.get(GITHUB_RELEASES_API, headers=headers, timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            tag_name = data.get("tag_name", "")
            
            # Extraire le numéro de version (v6.0 -> 6.0)
            remote_version = tag_name.lstrip("v").strip()
            
            logging.info(f"[Update] Version en ligne: {remote_version}, locale: {CURRENT_VERSION}")
            
            if remote_version and remote_version != CURRENT_VERSION:
                return remote_version
        
        elif resp.status_code == 404:
            logging.warning("[Update] Aucune release trouvée sur le repo")
        else:
            logging.warning(f"[Update] Réponse API: {resp.status_code}")
            
    except requests.RequestException as e:
        logging.warning(f"[Update] Erreur réseau: {e}")
    except Exception as e:
        logging.error(f"[Update] Erreur inattendue: {e}")
    
    return None


def compare_versions(current: str, remote: str) -> bool:
    """
    Compare deux versions sémantiques.
    
    Args:
        current: Version actuelle (ex: "6.0")
        remote: Version distante (ex: "6.1")
        
    Returns:
        True si remote > current
    """
    try:
        current_parts = [int(x) for x in current.split(".")]
        remote_parts = [int(x) for x in remote.split(".")]
        
        # Normaliser la longueur
        max_len = max(len(current_parts), len(remote_parts))
        current_parts.extend([0] * (max_len - len(current_parts)))
        remote_parts.extend([0] * (max_len - len(remote_parts)))
        
        return remote_parts > current_parts
    except (ValueError, AttributeError):
        # En cas d'erreur, comparer comme strings
        return remote != current


# ───────────────────────────────────────────────────────────────────────────
# URL UTILITIES
# ───────────────────────────────────────────────────────────────────────────

def build_opgg_url(region: str, riot_id: str) -> str:
    """
    Construit l'URL OP.GG pour un joueur.
    
    Args:
        region: Région (euw, na, etc.)
        riot_id: Riot ID (GameName#Tag)
        
    Returns:
        URL OP.GG complète
    """
    import urllib.parse
    
    # Convertir GameName#Tag en GameName-Tag pour l'URL
    url_name = riot_id
    if "#" in riot_id:
        left, right = riot_id.split("#", 1)
        if left and right:
            url_name = f"{left}-{right}"
    
    return f"https://www.op.gg/lol/summoners/{region}/{urllib.parse.quote(url_name)}"


def build_porofessor_url(region: str, riot_id: str) -> str:
    """
    Construit l'URL Porofessor pour un joueur.
    
    Args:
        region: Région (euw, na, etc.)
        riot_id: Riot ID (GameName#Tag)
        
    Returns:
        URL Porofessor complète
    """
    import urllib.parse
    
    url_name = riot_id
    if "#" in riot_id:
        left, right = riot_id.split("#", 1)
        if left and right:
            url_name = f"{left}-{right}"
    
    return f"https://porofessor.gg/fr/live/{region}/{urllib.parse.quote(url_name)}"
