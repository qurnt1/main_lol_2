"""
MAIN LOL - Assistant pour League of Legends
------------------------------------------
Auteur: Qurnt1
Version: 5.3 (Pages de Runes U.GG)
"""

# ───────────────────────────────────────────────────────────────────────────
# IMPORTS & CONFIGURATION SYSTEME
# ───────────────────────────────────────────────────────────────────────────

import tkinter as tk
from tkinter import ttk as ttk_widget
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from PIL import Image, ImageTk
import pystray
import keyboard
import json
import os
import sys
import psutil
from time import sleep, time
import pygame
import webbrowser
from threading import Thread, Event, Lock
import urllib.parse
from datetime import datetime
import tempfile
import re
import unicodedata
from typing import Optional, Dict, Any, List, Tuple
from lcu_driver import Connector
import asyncio
import logging
import requests # Requis pour U.GG

# --- 1. CONFIGURATION DU LOGGING ---
logging.basicConfig(
    filename='app_debug.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    encoding='utf-8'
)

# --- 2. GESTION DU HIGH DPI ---
try:
    from ctypes import windll
    windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

# ───────────────────────────────────────────────────────────────────────────
# CONSTANTES
# ───────────────────────────────────────────────────────────────────────────

URL_DD_VERSIONS = "https://ddragon.leagueoflegends.com/api/versions.json"
URL_DD_CHAMPIONS = "https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/champion.json"
URL_DD_SUMMONERS = "https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/summoner.json"
URL_DD_RUNES = "https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/runesReforged.json"
URL_DD_IMG_CHAMP = "https://ddragon.leagueoflegends.com/cdn/{version}/img/champion/{filename}"
URL_DD_IMG_SPELL = "https://ddragon.leagueoflegends.com/cdn/{version}/img/spell/{filename}"
URL_DD_IMG_PERK = "https://ddragon.leagueoflegends.com/cdn/img/{filename}" # Runes images

# U.GG API (Interne)
URL_UGG_OVERVIEW = "https://stats2.u.gg/lol/1.5/overview/{patch}/ranked_solo_5x5/{champ_id}/1.5.0.json"

EP_SESSION = "/lol-champ-select/v1/session"
EP_SESSION_TIMER = "/lol-champ-select/v1/session/timer"
EP_SESSION_LEGACY = "/lol-champ-select-legacy/v1/session"
EP_GAMEFLOW = "/lol-gameflow/v1/gameflow-phase"
EP_READY_CHECK = "/lol-matchmaking/v1/ready-check"
EP_PICKABLE = "/lol-champ-select/v1/pickable-champion-ids"
EP_CURRENT_SUMMONER = "/lol-summoner/v1/current-summoner"
EP_CHAT_ME = "/lol-chat/v1/me"
EP_LOGIN = "/lol-login/v1/session"

# ───────────────────────────────────────────────────────────────────────────
# UTILITAIRES
# ───────────────────────────────────────────────────────────────────────────

def resource_path(relative_path: str) -> str:
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    if relative_path.startswith("./"): relative_path = relative_path[2:]
    elif relative_path.startswith(".\\"): relative_path = relative_path[2:]
    return os.path.join(base_path, relative_path)

def get_appdata_path(filename: str) -> str:
    app_data_dir = os.getenv('APPDATA') 
    app_folder = os.path.join(app_data_dir, "MainLoL")
    if not os.path.exists(app_folder):
        try: os.makedirs(app_folder)
        except OSError: return filename
    return os.path.join(app_folder, filename)

PARAMETERS_PATH = get_appdata_path("parameters.json")
RUNES_CONFIG_PATH = get_appdata_path("runes_config.json")
LOCKFILE_PATH = os.path.join(tempfile.gettempdir(), 'main_lol.lock')

DEFAULT_PARAMS = {
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
    "auto_meta_runes_enabled": True,
    "auto_hide_on_connect": True,
    "close_app_on_lol_exit": True,
}

REGION_LIST = ["euw", "eune", "na", "kr", "jp", "br", "lan", "las", "oce", "tr", "ru"]
SUMMONER_SPELL_MAP = {
    "Barrier": 21, "Cleanse": 1, "Exhaust": 3, "Flash": 4, "Ghost": 6,
    "Heal": 7, "Ignite": 14, "Smite": 11, "Teleport": 12, "(Aucun)": 0
}
SUMMONER_SPELL_LIST = sorted(list(SUMMONER_SPELL_MAP.keys()))

def check_single_instance():
    if os.path.exists(LOCKFILE_PATH):
        try:
            with open(LOCKFILE_PATH, 'r') as f:
                pid = int(f.read())
            if pid != os.getpid() and psutil.pid_exists(pid):
                sys.exit(0)
        except: pass
    try:
        with open(LOCKFILE_PATH, 'w') as f: f.write(str(os.getpid()))
    except: pass

def remove_lockfile():
    try:
        if os.path.exists(LOCKFILE_PATH): os.remove(LOCKFILE_PATH)
    except: pass

check_single_instance()

# ───────────────────────────────────────────────────────────────────────────
# DATA DRAGON (Champions + Runes)
# ───────────────────────────────────────────────────────────────────────────

class DataDragon:
    CACHE_FILE = os.path.join(tempfile.gettempdir(), "mainlol_ddragon_champions.json")
    RUNES_CACHE_FILE = os.path.join(tempfile.gettempdir(), "mainlol_ddragon_runes.json")

    def __init__(self):
        self.loaded = False
        self.version = None
        self.by_norm_name: Dict[str, int] = {}
        self.by_id: Dict[int, Dict[str, Any]] = {}
        self.name_by_id: Dict[int, str] = {}
        self.all_names: List[str] = []

        # Summoners
        self.summoner_data = {}
        self.summoner_loaded = False

        # Runes (arbres + mapping)
        self.runes_loaded = False
        self.runes_data: List[Dict[str, Any]] = []      # structure brute runesReforged.json
        self.perk_images: Dict[int, str] = {}           # rune_id / tree_id -> chemin icon relatif
        self.rune_tree_map: Dict[int, int] = {}         # rune_id -> tree_id (8000, 8100, 8200, …)
        self.rune_slot_map: Dict[int, int] = {}         # rune_id -> index de slot dans l’arbre (0 = keystone)


    @staticmethod
    def _normalize(s: str) -> str:
        s = s.strip().lower()
        s = unicodedata.normalize('NFD', s)
        s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
        s = re.sub(r"[^a-z0-9]+", "", s)
        return s

    def _load_from_cache(self, target_version=None) -> bool:
        try:
            if os.path.exists(self.CACHE_FILE):
                with open(self.CACHE_FILE, "r", encoding="utf-8") as f:
                    payload = json.load(f)
                cached_version = payload.get("version")
                if target_version and cached_version != target_version:
                    return False
                self.version = cached_version
                self.by_norm_name = {k: int(v) for k, v in payload.get("by_norm_name", {}).items()}
                self.by_id = {int(k): v for k, v in payload.get("by_id", {}).items()}
                self.name_by_id = {int(k): v for k, v in payload.get("name_by_id", {}).items()}
                self.all_names = sorted(list(self.name_by_id.values()))
                self.loaded = True
                return True
        except: pass
        return False

    def _save_cache(self):
        try:
            with open(self.CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "version": self.version,
                    "by_norm_name": self.by_norm_name,
                    "by_id": self.by_id,
                    "name_by_id": self.name_by_id,
                }, f)
        except: pass

    def load(self):
        if self.loaded: return
        import requests
        online_version = None
        try:
            versions = requests.get(URL_DD_VERSIONS, timeout=5).json()
            online_version = versions[0]
        except: pass
        
        if self._load_from_cache(target_version=online_version): return

        try:
            if not online_version: 
                versions = requests.get(URL_DD_VERSIONS, timeout=5).json()
                online_version = versions[0]

            url_champs = URL_DD_CHAMPIONS.format(version=online_version)
            data = requests.get(url_champs, timeout=10).json()
            champs = data.get("data", {})
            self.by_id = {}
            self.name_by_id = {}
            self.by_norm_name = {}

            for champ_slug, info in champs.items():
                champ_name = info.get("name") or champ_slug
                champ_id = int(info.get("key"))
                self.by_id[champ_id] = info
                self.name_by_id[champ_id] = champ_name
                self.by_norm_name[self._normalize(champ_name)] = champ_id
                self.by_norm_name[self._normalize(info.get("id", champ_slug))] = champ_id

            aliases = {"wukong": "monkeyking", "renata": "renataglasc"}
            for k, v in aliases.items():
                nk, nv = self._normalize(k), self._normalize(v)
                if nv in self.by_norm_name:
                    self.by_norm_name[nk] = self.by_norm_name[nv]

            self.version = online_version
            self.all_names = sorted(list(self.name_by_id.values()))
            self.loaded = True
            self._save_cache()
        except:
            basic = {"garen": 86, "teemo": 17, "ashe": 22, "lux": 99}
            for n, cid in basic.items():
                self.by_norm_name[n] = cid
                self.by_id[cid] = {"name": n.title(), "key": str(cid)}
                self.name_by_id[cid] = n.title()
            self.version = "offline"
            self.all_names = sorted(list(self.name_by_id.values()))
            self.loaded = True

    def load_runes(self):
        """Charge les données des runes (arbres + images)."""
        if self.runes_loaded: return
        if not self.version: self.load()
        
        # Essai cache runes
        try:
            if os.path.exists(self.RUNES_CACHE_FILE):
                with open(self.RUNES_CACHE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data.get("version") == self.version:
                        self.runes_data = data.get("data")
                        self._map_rune_images()
                        self.runes_loaded = True
                        return
        except: pass

        # Téléchargement
        try:
            url = URL_DD_RUNES.format(version=self.version)
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                self.runes_data = r.json()
                self._map_rune_images()
                self.runes_loaded = True
                # Save cache
                with open(self.RUNES_CACHE_FILE, "w", encoding="utf-8") as f:
                    json.dump({"version": self.version, "data": self.runes_data}, f)
        except Exception as e:
            logging.error(f"[DataDragon] Erreur loading runes: {e}")

    def _map_rune_images(self):
        """
        Construit :
          - self.perk_images : id (arbre ou rune) -> chemin d'icône
          - self.rune_tree_map : id rune -> id arbre (8000, 8100, ...)
          - self.rune_slot_map : id rune -> index de slot (0 = keystone)
        """
        self.perk_images = {}
        self.rune_tree_map = {}
        self.rune_slot_map = {}

        for tree in self.runes_data or []:
            tree_id = tree.get("id")
            if tree_id is None:
                continue

            # icône de l’arbre
            icon_tree = tree.get("icon")
            if icon_tree:
                self.perk_images[tree_id] = icon_tree

            # slots : 0 = keystones, 1–3 = autres lignes
            for slot_index, slot in enumerate(tree.get("slots", [])):
                for rune in slot.get("runes", []):
                    rid = rune.get("id")
                    icon = rune.get("icon")
                    if rid is None or not icon:
                        continue
                    self.perk_images[rid] = icon
                    self.rune_tree_map[rid] = tree_id
                    self.rune_slot_map[rid] = slot_index

    def get_rune_image(self, rune_id) -> Optional[Image.Image]:
        self.load_runes()
        icon_path = self.perk_images.get(rune_id)
        # Fallback pour les Shards (5008, 5005, etc)
        if not icon_path:
            # Mapping basic shards
            shards = {
                5008: "perk-images/StatMods/StatModsAdaptiveForceIcon.png",
                5005: "perk-images/StatMods/StatModsAttackSpeedIcon.png",
                5007: "perk-images/StatMods/StatModsCDRScalingIcon.png",
                5002: "perk-images/StatMods/StatModsArmorIcon.png",
                5003: "perk-images/StatMods/StatModsMagicResIcon.png",
                5001: "perk-images/StatMods/StatModsHealthScalingIcon.png"
            }
            icon_path = shards.get(rune_id)

        if not icon_path: return None

        cache_dir = os.path.join(tempfile.gettempdir(), "mainlol_runes")
        if not os.path.exists(cache_dir): os.makedirs(cache_dir, exist_ok=True)
        
        filename = os.path.basename(icon_path)
        local_path = os.path.join(cache_dir, filename)

        if os.path.exists(local_path):
            try: return Image.open(local_path)
            except: pass

        url = URL_DD_IMG_PERK.format(filename=icon_path)
        try:
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                from io import BytesIO
                img = Image.open(BytesIO(r.content))
                with open(local_path, "wb") as f: f.write(r.content)
                return img
        except: pass
        return None

    # ... (Reste des méthodes Champions/Spells inchangées) ...
    def get_champion_icon(self, name_or_id):
        # (Copier le code précédent)
        cid = self.resolve_champion(name_or_id)
        if not cid: return None
        champ_data = self.by_id.get(cid)
        if not champ_data: return None
        image_filename = champ_data.get("image", {}).get("full")
        if not image_filename: return None
        cache_dir = os.path.join(tempfile.gettempdir(), "mainlol_icons")
        if not os.path.exists(cache_dir): os.makedirs(cache_dir, exist_ok=True)
        local_path = os.path.join(cache_dir, image_filename)
        if os.path.exists(local_path):
            try: return Image.open(local_path)
            except: pass
        url = URL_DD_IMG_CHAMP.format(version=self.version, filename=image_filename)
        try:
            from io import BytesIO
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                with open(local_path, "wb") as f: f.write(r.content)
                return Image.open(BytesIO(r.content))
        except: pass
        return None

    def resolve_champion(self, name_or_id: Any) -> Optional[int]:
        self.load()
        if name_or_id is None: return None
        try: return int(name_or_id)
        except: pass
        n = self._normalize(str(name_or_id))
        return self.by_norm_name.get(n)

    def id_to_name(self, cid: int) -> Optional[str]:
        self.load()
        return self.name_by_id.get(cid)
    
    def get_summoner_icon(self, spell_name):
        # (Copier le code précédent)
        if spell_name == "(Aucun)" or not spell_name: return None
        if not self.summoner_loaded: self.load_summoners()
        image_filename = self.summoner_data.get(spell_name)
        if not image_filename: return None
        cache_dir = os.path.join(tempfile.gettempdir(), "mainlol_spells")
        if not os.path.exists(cache_dir): os.makedirs(cache_dir, exist_ok=True)
        local_path = os.path.join(cache_dir, image_filename)
        if os.path.exists(local_path):
            try: return Image.open(local_path)
            except: pass
        url = URL_DD_IMG_SPELL.format(version=self.version, filename=image_filename)
        try:
            from io import BytesIO
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                with open(local_path, "wb") as f: f.write(r.content)
                return Image.open(BytesIO(r.content))
        except: pass
        return None

    def load_summoners(self):
        if self.summoner_loaded: return
        if not self.version: self.load()
        try:
            r = requests.get(URL_DD_SUMMONERS.format(version=self.version), timeout=5)
            if r.status_code == 200:
                data = r.json().get("data", {})
                for key, info in data.items():
                    name = info.get("name")
                    if name: self.summoner_data[name] = info.get("image", {}).get("full")
                self.summoner_loaded = True
        except: pass

# ───────────────────────────────────────────────────────────────────────────
# CLIENT U.GG (API Meta - ROBUSTE)
# ───────────────────────────────────────────────────────────────────────────

class UGGClient:
    """
    Client U.GG robuste qui :
      - envoie un User-Agent "navigateur"
      - parcourt le JSON pour détecter les builds
      - reconstruit les pages runes avec DataDragon pour garantir des combos valides
    """

    def __init__(self, dd: DataDragon):
        """
        dd : instance DataDragon déjà initialisée.
        On s’en sert pour la version (patch) et pour savoir dans quel arbre se trouve chaque rune.
        """
        self.dd = dd
        # version de LoL (ex: "15.24.1") -> "15_24" pour l’URL U.GG
        self.dd_version = dd.version or "15.24.1"
        parts = self.dd_version.split(".")
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            self.patch_str = f"{parts[0]}_{parts[1]}"
        else:
            self.patch_str = "15_24"

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0 Safari/537.36"
            ),
            "Accept": "application/json,text/plain,*/*",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "en-US,en;q=0.9",
            "Origin": "https://u.gg",
            "Referer": "https://u.gg/",
            "Connection": "keep-alive",
        })

    # ---------- helpers internes ----------

    def _find_roles_dict(self, obj):
        """
        Cherche récursivement un dict qui ressemble à :
        { "1": [...], "4": [...], ... } où les valeurs sont des listes
        contenant les builds (ce qu'on voit dans ton preview).
        """
        if isinstance(obj, dict):
            numeric_keys = [k for k in obj.keys() if isinstance(k, str) and k.isdigit()]
            if numeric_keys:
                # on regarde si au moins une de ces clés pointe vers une liste de builds
                for k in numeric_keys:
                    v = obj[k]
                    if isinstance(v, list) and v and isinstance(v[0], (list, dict)):
                        return obj
            # sinon on descend récursivement
            for v in obj.values():
                found = self._find_roles_dict(v)
                if found is not None:
                    return found

        elif isinstance(obj, list):
            for item in obj:
                found = self._find_roles_dict(item)
                if found is not None:
                    return found

        return None

    def _find_rune_headers(self, obj):
        """
        Cherche récursivement des listes de la forme :
        [?, ?, primaryTreeId, subTreeId, [perks...], ...]
        avec primaryTreeId / subTreeId entre 8000 et 9000 (arbres de runes).
        Retourne une liste de ces "headers".
        """
        headers = []

        def _recurse(x):
            if isinstance(x, list):
                # pattern candidat : [?, ?, primary, sub, [perks], ...]
                if (
                    len(x) >= 5
                    and isinstance(x[2], (int, str))
                    and isinstance(x[3], (int, str))
                    and isinstance(x[4], list)
                ):
                    try:
                        primary = int(x[2])
                        sub = int(x[3])
                    except ValueError:
                        primary = sub = None

                    if (
                        primary is not None
                        and sub is not None
                        and 8000 <= primary <= 9000
                        and 8000 <= sub <= 9000
                    ):
                        headers.append(x)

                for y in x:
                    _recurse(y)

            elif isinstance(x, dict):
                for y in x.values():
                    _recurse(y)

        _recurse(obj)
        return headers

    # ---------- méthode publique ----------
    def get_runes(self, champ_id: int, role: str = "TOP") -> List[Dict]:
        """
        Récupère jusqu'à 3 pages de runes U.GG pour un champion donné et un rôle donné.

        Retour :
        [
          {
            "name": "Méta : Plus joué (U.GG)" ou "Méta : Variante 1 (U.GG)",
            "primaryStyleId": ...,
            "subStyleId": ...,
            "selectedPerkIds": [keystone, 3 primaires, 2 secondaires, 3 shards],
            "icon_id": keystone,
          },
          ...
        ]
        """
        role_map = {
            "JUNGLE": "1",
            "SUPPORT": "2",
            "ADC": "3",
            "BOTTOM": "3",
            "TOP": "4",
            "MID": "5",
            "MIDDLE": "5",
        }
        role_id = role_map.get(role.upper(), "4")  # TOP par défaut

        url = URL_UGG_OVERVIEW.format(patch=self.patch_str, champ_id=champ_id)
        pages: List[Dict[str, Any]] = []

        print(f"[DEBUG UGG] get_runes() start - champ_id={champ_id}, role={role}, role_id={role_id}, patch={self.patch_str}")
        print(f"[DEBUG UGG] URL appelée: {url}")

        try:
            r = self.session.get(url, timeout=5)
        except Exception as e:
            logging.error(f"[U.GG] Erreur réseau pour {url} : {e}")
            return []

        print(f"[DEBUG UGG] HTTP status={r.status_code}, len_body={len(r.content) if r.content else 0}")
        if r.status_code != 200:
            logging.error(f"[U.GG] HTTP {r.status_code} pour {url}")
            logging.error(f"[U.GG] Réponse (début) : {r.text[:200].replace(chr(10), ' ')}")
            return []

        # Dump brut pour debug
        try:
            raw_path = os.path.join(tempfile.gettempdir(), f"ugg_raw_{champ_id}.json")
            with open(raw_path, "wb") as f:
                f.write(r.content)
            print(f"[DEBUG UGG] JSON brut écrit dans: {raw_path}")
        except Exception as e:
            print(f"[DEBUG UGG] Impossible d'écrire le JSON brut: {e}")

        try:
            data = r.json()
        except Exception as e:
            logging.error(f"[U.GG] JSON invalide pour {url} : {e}")
            print(f"[DEBUG UGG] JSON invalide: {e}")
            return []

        if isinstance(data, dict):
            print(f"[DEBUG UGG] data est un dict, premières clés: {list(data.keys())[:10]}")

        # 1) On cherche un dict de rôles {"1": [...], "4": [...], ...}
        roles_dict = self._find_roles_dict(data)
        search_scope = data
        if roles_dict:
            print(f"[DEBUG UGG] roles_dict trouvé, clés={list(roles_dict.keys())}")
            if role_id in roles_dict:
                print(f"[DEBUG UGG] Utilisation de la branche role_id={role_id}")
                search_scope = roles_dict[role_id]
            else:
                numeric_keys = sorted([k for k in roles_dict.keys() if k.isdigit()])
                if numeric_keys:
                    print(f"[DEBUG UGG] role_id={role_id} introuvable, fallback sur rôle={numeric_keys[0]}")
                    search_scope = roles_dict[numeric_keys[0]]
                else:
                    search_scope = roles_dict

        # 2) Détection des "headers" runes dans ce scope
        headers = self._find_rune_headers(search_scope)
        print(f"[DEBUG UGG] _find_rune_headers -> nb_headers={len(headers)}")
        if headers:
            print(f"[DEBUG UGG] Premier header (aperçu): {headers[0][:5]}")

        if not headers:
            logging.error(f"[U.GG] Aucune page de runes détectée pour champ_id={champ_id}, role={role}")
            return []

        default_shards = [5008, 5008, 5002]  # Force adaptative, Force adaptative, Armure

        # 3) Construction des pages à partir des headers
        for idx, h in enumerate(headers[:3]):
            try:
                primary = int(h[2])
                sub = int(h[3])
                perks_raw = h[4]

                # Normalisation de perks_raw en liste plate d'int
                flat_perks: List[int] = []

                def _flatten(x):
                    if isinstance(x, list):
                        for v in x:
                            _flatten(v)
                    elif isinstance(x, dict):
                        for v in x.values():
                            _flatten(v)
                    else:
                        try:
                            flat_perks.append(int(x))
                        except Exception:
                            pass

                _flatten(perks_raw)

                if not flat_perks:
                    continue

                # Séparation runes normales vs shards (stat mods)
                shards = [p for p in flat_perks if 5000 <= p < 6000]
                non_shards = [p for p in flat_perks if p not in shards]

                # Grouper par arbre via DataDragon
                primaries_raw: List[int] = []
                secondaries_raw: List[int] = []
                for pid in non_shards:
                    tree_id = self.dd.rune_tree_map.get(pid)
                    if tree_id == primary:
                        primaries_raw.append(pid)
                    elif tree_id == sub:
                        secondaries_raw.append(pid)

                # Fallback si le mapping échoue (structure U.GG inattendue)
                if not primaries_raw or not secondaries_raw:
                    logging.warning(f"[U.GG] Mapping runes->arbres incomplet, fallback simple pour champ_id={champ_id}")
                    primaries_raw = non_shards[:4]
                    secondaries_raw = non_shards[4:6]

                # Keystone = première rune primaire de slot 0 si possible
                keystone_candidates = [pid for pid in primaries_raw if self.dd.rune_slot_map.get(pid) == 0]
                if keystone_candidates:
                    keystone = keystone_candidates[0]
                elif primaries_raw:
                    keystone = primaries_raw[0]
                else:
                    continue  # pas de keystone possible

                # Ordonner les primaires : keystone + 3 autres
                primaries_ordered = [keystone] + [pid for pid in primaries_raw if pid != keystone]
                primaries_ordered = primaries_ordered[:4]

                # Ordonner les secondaires : 2 runes distinctes max
                seen = set()
                secondaries_ordered: List[int] = []
                for pid in secondaries_raw:
                    if pid in seen:
                        continue
                    seen.add(pid)
                    secondaries_ordered.append(pid)
                    if len(secondaries_ordered) >= 2:
                        break

                # Runes d’arbres (4 primaires + 2 secondaires)
                tree_perks = primaries_ordered + secondaries_ordered

                # Shards : garder les 3 premiers valides, sinon compléter par défaut
                valid_shards = [5001, 5002, 5003, 5005, 5007, 5008]
                shards_clean = [pid for pid in shards if pid in valid_shards][:3]
                while len(shards_clean) < 3:
                    shards_clean.append(default_shards[len(shards_clean)])
                shards_clean = shards_clean[:3]

                full_perks = tree_perks + shards_clean

                name = "Méta : Plus joué (U.GG)" if idx == 0 else f"Méta : Variante {idx} (U.GG)"
                page_obj = {
                    "name": name,
                    "primaryStyleId": primary,
                    "subStyleId": sub,
                    "selectedPerkIds": full_perks,
                    "icon_id": keystone,
                }
                pages.append(page_obj)
                print(f"[DEBUG UGG] Page construite idx={idx}: {page_obj}")
            except Exception as e:
                logging.error(f"[U.GG] Erreur build page idx={idx} : {e}", exc_info=True)

        print(f"[DEBUG UGG] get_runes() retourne {len(pages)} page(s) pour champ_id={champ_id}, role={role}")
        return pages

# ───────────────────────────────────────────────────────────────────────────
# FENETRE SELECTEUR RUNES (U.GG avec choix de rôle + preview détaillé)
# ───────────────────────────────────────────────────────────────────────────

class RuneSelectorWindow:
    def __init__(self, parent, champ_name, slot_num):
        self.parent = parent          # SettingsWindow
        self.champ_name = champ_name
        self.slot_num = slot_num
        self.window = ttk.Toplevel(parent.window)
        self.window.title(f"Runes U.GG : {champ_name}")
        self.window.geometry("520x480")
        self.window.resizable(False, False)

        # Icône de la fenêtre (icon.png)
        try:
            icon_img = Image.open(resource_path("./config/imgs/garen.ico")).resize((16, 16))
            icon_photo = ImageTk.PhotoImage(icon_img)
            self.window.iconphoto(False, icon_photo)
            # Evite que le garbage collector détruise l'image
            self.window._icon_img = icon_photo
        except Exception as e:
            print(f"[DEBUG RUNES] Impossible de charger l'icône de la fenêtre : {e}")

        # ID champion via DataDragon
        self.champ_id = self.parent.parent.dd.resolve_champion(champ_name)

        # Rôle courant (TOP par défaut)
        self.current_role = "TOP"
        self.role_var = tk.StringVar(value=self.current_role)

        # Références UI pour pouvoir les détruire proprement
        self.loading_lbl = None
        self.header_label = None
        self.pages_container = None

        # Si on a déjà une config pour ce champion, on récupère le rôle stocké
        try:
            if os.path.exists(RUNES_CONFIG_PATH):
                with open(RUNES_CONFIG_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                conf = data.get(self.champ_name)
                if isinstance(conf, dict):
                    stored_role = conf.get("role")
                    if stored_role in ("TOP", "JUNGLE", "MID", "ADC", "SUPPORT"):
                        self.current_role = stored_role
                        self.role_var.set(self.current_role)
        except Exception as e:
            print(f"[DEBUG RUNES] Erreur lecture rôle stocké pour {self.champ_name}: {e}")

        # ── Bandeau haut : Titre + sélection du rôle ──────────────────────
        top_frame = ttk.Frame(self.window, padding=10)
        top_frame.pack(fill="x")

        ttk.Label(
            top_frame,
            text=f"Pages U.GG pour {self.champ_name}",
            font=("Segoe UI", 12, "bold")
        ).pack(anchor="w")

        roles_frame = ttk.Frame(top_frame)
        roles_frame.pack(anchor="w", pady=(5, 0))

        for role_label in ["TOP", "JUNGLE", "MID", "ADC", "SUPPORT"]:
            rb = ttk.Radiobutton(
                roles_frame,
                text=role_label,
                value=role_label,
                variable=self.role_var,
                command=self._on_role_change,
                bootstyle="secondary-toolbutton"
            )
            rb.pack(side="left", padx=3)

        # Label de chargement (remplacé ensuite par les pages)
        self.loading_lbl = ttk.Label(
            self.window,
            text="Récupération des données U.GG...",
            font=("Segoe UI", 11)
        )
        self.loading_lbl.pack(expand=True, pady=10)

        print(f"[DEBUG RUNES] RuneSelectorWindow.__init__ -> champ_name={self.champ_name}, slot={self.slot_num}, champ_id={self.champ_id}, role={self.current_role}")

        # Thread pour ne pas geler l'UI
        Thread(
            target=self.fetch_and_display,
            args=(self.current_role,),
            daemon=True
        ).start()

    # ── Callback quand l’utilisateur change de rôle ───────────────────────
    def _on_role_change(self):
        new_role = self.role_var.get()
        self.current_role = new_role
        print(f"[DEBUG RUNES] _on_role_change -> nouveau rôle={new_role}")

        # Nettoyage complet du contenu dynamique (header + pages + loading)
        if self.header_label and self.header_label.winfo_exists():
            self.header_label.destroy()
            self.header_label = None

        if self.pages_container and self.pages_container.winfo_exists():
            self.pages_container.destroy()
            self.pages_container = None

        if self.loading_lbl and self.loading_lbl.winfo_exists():
            self.loading_lbl.destroy()

        # Nouveau label de chargement
        self.loading_lbl = ttk.Label(
            self.window,
            text="Récupération des données U.GG...",
            font=("Segoe UI", 11)
        )
        self.loading_lbl.pack(expand=True, pady=10)

        # On relance un fetch pour ce rôle
        Thread(
            target=self.fetch_and_display,
            args=(new_role,),
            daemon=True
        ).start()

    # ── Récupération des pages U.GG pour un rôle donné ────────────────────
    def fetch_and_display(self, role: str = "TOP"):
        print(f"[DEBUG RUNES] fetch_and_display() appelé pour {self.champ_name} (champ_id={self.champ_id}, role={role})")
        pages = []

        if self.champ_id:
            # IMPORTANT : on passe l'INSTANCE DataDragon, pas sa version
            ugg = UGGClient(self.parent.parent.dd)
            pages = ugg.get_runes(self.champ_id, role=role)

        # Retour au thread UI
        self.window.after(0, lambda: self.show_results(pages, role))


    # ── Affichage des résultats dans la fenêtre ───────────────────────────
    def show_results(self, pages, role: str):
        # On enlève le label de chargement s'il existe
        if self.loading_lbl and self.loading_lbl.winfo_exists():
            self.loading_lbl.destroy()
            self.loading_lbl = None

        print(f"[DEBUG RUNES] show_results() pour {self.champ_name} - role={role} - nb_pages={len(pages)}")

        # Nettoyage header + conteneur si existant
        if self.header_label and self.header_label.winfo_exists():
            self.header_label.destroy()
        if self.pages_container and self.pages_container.winfo_exists():
            self.pages_container.destroy()

        # Header unique
        self.header_label = ttk.Label(
            self.window,
            text=f"Pages recommandées pour {self.champ_name} ({role})",
            font=("Segoe UI", 12, "bold")
        )
        self.header_label.pack(pady=(5, 5))

        if not pages:
            print(f"[DEBUG RUNES] Aucune page à afficher pour {self.champ_name} ({role})")
            ttk.Label(
                self.window,
                text="Aucune donnée trouvée ou erreur de connexion.\nVérifiez le rôle ou réessayez plus tard.",
                bootstyle="danger"
            ).pack(pady=20)
            return

        # Conteneur pour toutes les options (1 à 3)
        self.pages_container = ttk.Frame(self.window, padding=10)
        self.pages_container.pack(fill="both", expand=True)

        for idx, page in enumerate(pages):
            print(f"[DEBUG RUNES] Page idx={idx} (aperçu) pour {self.champ_name}: {page}")

            frame = ttk.Labelframe(
                self.pages_container,
                text=page['name'],
                padding=10,
                bootstyle="info"
            )
            frame.pack(fill="x", pady=5)

            # Colonne gauche : Keystone
            left_col = ttk.Frame(frame)
            left_col.pack(side="left", padx=8)

            perks = page.get("selectedPerkIds", []) or []
            # On s'attend à : [keystone, 3 primaires, 2 secondaires, 3 shards]
            if len(perks) < 9:
                perks = perks + [None] * (9 - len(perks))

            keystone_id = page.get("icon_id") or (perks[0] if perks else None)

            lbl_keystone = ttk.Label(left_col)
            lbl_keystone.pack()
            if keystone_id:
                self._load_rune_img(lbl_keystone, keystone_id, size=(48, 48))

            ttk.Label(left_col, text=str(keystone_id or ""), font=("Segoe UI", 8)).pack(pady=(2, 0))

            # Colonne centrale : détails des runes principales / secondaires / shards
            center_col = ttk.Frame(frame)
            center_col.pack(side="left", fill="both", expand=True, padx=8)

            ttk.Label(center_col, text="Détail des runes :", font=("Segoe UI", 9, "bold")).pack(anchor="w")

            # Découpage : primaires / secondaires / shards
            prim_others = [pid for pid in perks[1:4] if pid]
            sec_runes = [pid for pid in perks[4:6] if pid]
            shards = [pid for pid in perks[6:9] if pid]

            # Ligne des runes primaires
            self._create_rune_row(center_col, prim_others, label_text="Primaires")

            # Ligne des runes secondaires
            self._create_rune_row(center_col, sec_runes, label_text="Secondaires")

            # Ligne des shards (affichés comme icônes aussi)
            if shards:
                self._create_rune_row(center_col, shards, label_text="Shards")

            # Colonne droite : bouton choisir
            right_col = ttk.Frame(frame)
            right_col.pack(side="right", padx=8)

            btn = ttk.Button(
                right_col,
                text="Choisir",
                bootstyle="success",
                command=lambda p=page: self.save_preset(p)
            )
            btn.pack(pady=15)

    # ── Helper : créer une rangée d’icônes de runes ───────────────────────
    def _create_rune_row(self, parent_frame, rune_ids, label_text=None):
        row = ttk.Frame(parent_frame)
        row.pack(anchor="w", pady=2)

        if label_text:
            ttk.Label(
                row,
                text=f"{label_text} :",
                font=("Segoe UI", 9, "bold")
            ).pack(side="left", padx=(0, 4))

        icons_frame = ttk.Frame(row)
        icons_frame.pack(side="left")

        for rid in rune_ids:
            if not rid:
                continue
            lbl = ttk.Label(icons_frame)
            lbl.pack(side="left", padx=2)
            # Petites icônes pour les runes secondaires/principales
            self._load_rune_img(lbl, rid, size=(28, 28))

    # ── Chargement d'une image de rune (dimension paramétrable) ───────────
    def _load_rune_img(self, lbl, rune_id, size=(48, 48)):
        print(f"[DEBUG RUNES] _load_rune_img -> rune_id={rune_id}, size={size}")

        def task():
            try:
                img = self.parent.parent.dd.get_rune_image(rune_id)
                print(f"[DEBUG RUNES] get_rune_image({rune_id}) -> {'OK' if img else 'None'}")
                if not img:
                    return
                img = img.resize(size, Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)

                def ui():
                    if lbl.winfo_exists():
                        lbl.configure(image=photo)
                        lbl.image = photo

                lbl.after(0, ui)
            except Exception as e:
                print(f"[DEBUG RUNES] Erreur dans _load_rune_img pour rune_id={rune_id}: {e}")

        Thread(target=task, daemon=True).start()

    # ── Sauvegarde de la page choisie en local (avec le rôle) ─────────────
    def save_preset(self, page_data):
        role = getattr(self, "current_role", "TOP")
        new_conf = {
            "name": f"Auto {self.champ_name}",
            "primaryStyleId": page_data["primaryStyleId"],
            "subStyleId": page_data["subStyleId"],
            "selectedPerkIds": page_data["selectedPerkIds"],
            "role": role
        }

        full_data = {}
        if os.path.exists(RUNES_CONFIG_PATH):
            try:
                with open(RUNES_CONFIG_PATH, "r", encoding="utf-8") as f:
                    full_data = json.load(f)
            except Exception as e:
                print(f"[DEBUG RUNES] Erreur lecture ancienne config runes: {e}")

        full_data[self.champ_name] = new_conf

        try:
            with open(RUNES_CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(full_data, f, indent=2, ensure_ascii=False)
            print(f"[DEBUG RUNES] save_preset() -> sauvegardé {self.champ_name} role={role}")
            self.parent.parent.show_toast(f"Runes U.GG pour {self.champ_name} ({role}) sauvegardées !")
            self.window.destroy()
        except Exception as e:
            print(f"[DEBUG RUNES] Erreur save_preset pour {self.champ_name}: {e}")

# ───────────────────────────────────────────────────────────────────────────
# SETTINGS WINDOW (MODIFIE)
# ───────────────────────────────────────────────────────────────────────────

class SettingsWindow:
    def __init__(self, parent):
        self.parent = parent
        self.window = ttk.Toplevel(parent.root)
        self.window.title("Paramètres - MAIN LOL")
        self.window.geometry("550x750") # Un peu plus large pour le bouton rune
        self.window.resizable(False, False)
        self.window.protocol("WM_DELETE_WINDOW", self.on_close)

        img = Image.open(resource_path("./config/imgs/garen.webp")).resize((16, 16))
        photo = ImageTk.PhotoImage(img)
        self.window.iconphoto(False, photo)
        self.window._icon_img = photo

        # Variables
        self.auto_var = tk.BooleanVar(value=parent.auto_accept_enabled)
        self.pick_var = tk.BooleanVar(value=parent.auto_pick_enabled)
        self.ban_var = tk.BooleanVar(value=parent.auto_ban_enabled)
        self.summ_var = tk.BooleanVar(value=parent.auto_summoners_enabled)
        self.summ_auto_var = tk.BooleanVar(value=parent.summoner_name_auto_detect)
        self.summ_entry_var = tk.StringVar(value=parent.manual_summoner_name)
        self.saved_manual_name = parent.manual_summoner_name
        self.play_again_var = tk.BooleanVar(value=parent.auto_play_again_enabled)
        self.meta_runes_var = tk.BooleanVar(value=parent.auto_meta_runes_enabled)
        self.auto_hide_var = tk.BooleanVar(value=parent.auto_hide_on_connect)
        self.close_on_exit_var = tk.BooleanVar(value=parent.close_app_on_lol_exit)

        try:
            self.parent.dd.load()
            self.all_champions = self.parent.dd.all_names
        except:
            self.all_champions = ["Garen", "Teemo", "Ashe"]

        self.spell_list = SUMMONER_SPELL_LIST[:]
        self.create_widgets()
        self.window.after(100, self.toggle_summoner_entry)
        self.window.after(1000, self._poll_summoner_label)

    def create_widgets(self):
        frame = ttk.Frame(self.window, padding=15)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=0) 
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=0)

        # ROW 0 : Auto Accept
        ttk.Checkbutton(frame, text="Accepter automatiquement les parties", variable=self.auto_var,
                        command=lambda: setattr(self.parent, 'auto_accept_enabled', self.auto_var.get()),
                        bootstyle="success-round-toggle").grid(row=0, column=0, columnspan=3, sticky="w", pady=5)

        # ROW 1 : Auto Pick
        ttk.Checkbutton(frame, text="Auto-Pick (Priorité)", variable=self.pick_var,
                        command=lambda: (setattr(self.parent, 'auto_pick_enabled', self.pick_var.get()), self.toggle_pick()),
                        bootstyle="info-round-toggle").grid(row=1, column=0, columnspan=3, sticky="w", pady=(15, 5))

        # ROW 2 : Auto Runes (DÉPLACÉ ICI COMME DEMANDÉ)
        # Note : Cela active l'application automatique. La configuration se fait via les boutons "Runes" à côté des champions.
        ttk.Checkbutton(frame, text="Auto Runes (Application auto)", variable=self.meta_runes_var,
                        command=lambda: setattr(self.parent, 'auto_meta_runes_enabled', self.meta_runes_var.get()),
                        bootstyle="primary-round-toggle").grid(row=2, column=0, columnspan=3, sticky="w", pady=(0, 15))

        # ROW 3-5 : Les Picks
        def create_pick_row(row, label_text, btn_attr, slot):
            ttk.Label(frame, text=label_text).grid(row=row, column=0, sticky="e", padx=5, pady=3)
            btn = ttk.Button(frame, text=getattr(self.parent, btn_attr), bootstyle="secondary-outline")
            btn.grid(row=row, column=1, sticky="ew", padx=5, pady=3)
            btn.configure(command=lambda: self._open_champion_picker("pick", slot))
            setattr(self, f"btn_pick_{slot}", btn)
            
            # Bouton Rune spécifique au champion
            # C'est ce bouton qui ouvrira la fenêtre U.GG
            btn_rune = ttk.Button(frame, text="Runes", bootstyle="link-secondary", width=6)
            btn_rune.grid(row=row, column=2, padx=5)
            btn_rune.configure(command=lambda: self._open_rune_page(getattr(self.parent, btn_attr), slot))

        create_pick_row(3, "Pick 1 :", "selected_pick_1", 1)
        create_pick_row(4, "Pick 2 :", "selected_pick_2", 2)
        create_pick_row(5, "Pick 3 :", "selected_pick_3", 3)

        # ROW 6 : Auto Ban
        ttk.Checkbutton(frame, text="Auto-Ban", variable=self.ban_var,
                        command=lambda: (setattr(self.parent, 'auto_ban_enabled', self.ban_var.get()), self.toggle_ban()),
                        bootstyle="danger-round-toggle").grid(row=6, column=0, columnspan=3, sticky="w", pady=(15, 5))

        # ROW 7 : Ban Button
        ttk.Label(frame, text="Bannir :").grid(row=7, column=0, sticky="e", padx=5)
        self.btn_ban = ttk.Button(frame, text=self.parent.selected_ban, bootstyle="secondary-outline")
        self.btn_ban.grid(row=7, column=1, columnspan=2, sticky="ew", padx=5)
        self.btn_ban.configure(command=lambda: self._open_champion_picker("ban"))

        # ROW 8 : Auto Summoners
        ttk.Checkbutton(frame, text="Auto Summoners", variable=self.summ_var,
                        command=lambda: (setattr(self.parent, 'auto_summoners_enabled', self.summ_var.get()), self.toggle_spells()),
                        bootstyle="warning-round-toggle").grid(row=8, column=0, columnspan=3, sticky="w", pady=(15, 5))

        # ROW 9-10 : Spells
        ttk.Label(frame, text="Sort 1 :").grid(row=9, column=0, sticky="e", padx=5, pady=3)
        self.btn_spell_1 = ttk.Button(frame, text=self.parent.global_spell_1, bootstyle="secondary-outline")
        self.btn_spell_1.grid(row=9, column=1, columnspan=2, sticky="ew", padx=5, pady=3)
        self.btn_spell_1.configure(command=lambda: self._open_spell_picker(1))

        ttk.Label(frame, text="Sort 2 :").grid(row=10, column=0, sticky="e", padx=5, pady=3)
        self.btn_spell_2 = ttk.Button(frame, text=self.parent.global_spell_2, bootstyle="secondary-outline")
        self.btn_spell_2.grid(row=10, column=1, columnspan=2, sticky="ew", padx=5, pady=3)
        self.btn_spell_2.configure(command=lambda: self._open_spell_picker(2))

        # ROW 11 : Detect (Reste identique)
        detect_frame = ttk.Frame(frame)
        detect_frame.grid(row=11, column=0, columnspan=3, sticky="w", pady=(15, 5))
        def on_auto_toggle():
            self.toggle_summoner_entry()
            if self.summ_auto_var.get(): self.parent.force_refresh_summoner()
            self._update_detect_label_text()
        self.switch_auto = ttk.Checkbutton(detect_frame, variable=self.summ_auto_var, command=on_auto_toggle, bootstyle="round-toggle")
        self.switch_auto.pack(side="left", padx=(0, 10))
        self.lbl_auto_detect = ttk.Label(detect_frame, text="Détection auto du compte")
        self.lbl_auto_detect.pack(side="left")

        # ROW 12-15 (Misc) - Reste identique, juste décalé visuellement par logique, mais le code grid reste le même
        ttk.Label(frame, text="Pseudo :").grid(row=12, column=0, sticky="e", padx=5, pady=5)
        self.summ_entry = ttk.Entry(frame, textvariable=self.summ_entry_var, state="readonly")
        self.summ_entry.grid(row=12, column=1, columnspan=2, sticky="ew", padx=5)

        ttk.Label(frame, text="Région :").grid(row=13, column=0, sticky="e", padx=5, pady=5)
        self.region_var = tk.StringVar(value=self.parent.region)
        self.region_cb = ttk.Combobox(frame, values=REGION_LIST, textvariable=self.region_var, state="readonly")
        self.region_cb.grid(row=13, column=1, columnspan=2, sticky="ew", padx=5)
        self.region_cb.bind("<<ComboboxSelected>>", lambda e: setattr(self.parent, 'region', self.region_var.get()))

        ttk.Separator(frame).grid(row=14, column=0, columnspan=3, sticky="we", pady=(15, 10))
        
        misc_frame = ttk.Frame(frame)
        misc_frame.grid(row=15, column=0, columnspan=3, sticky="w")
        ttk.Checkbutton(misc_frame, text="\"Retour au salon\" automatique", variable=self.play_again_var, command=lambda: setattr(self.parent, 'auto_play_again_enabled', self.play_again_var.get()), bootstyle="info-round-toggle").pack(anchor="w", pady=2)
        ttk.Checkbutton(misc_frame, text="Cacher l'application quand LoL est détecté", variable=self.auto_hide_var, command=lambda: setattr(self.parent, 'auto_hide_on_connect', self.auto_hide_var.get()), bootstyle="secondary-round-toggle").pack(anchor="w", pady=2)
        ttk.Checkbutton(misc_frame, text="Fermer l'application quand LoL se ferme", variable=self.close_on_exit_var, command=lambda: setattr(self.parent, 'close_app_on_lol_exit', self.close_on_exit_var.get()), bootstyle="danger-round-toggle").pack(anchor="w", pady=2)

        ttk.Button(self.window, text="Fermer", command=self.on_close, bootstyle="primary").pack(pady=(0, 20), side="bottom")

        self.toggle_pick()
        self.toggle_ban()
        self.toggle_spells()
        self.toggle_summoner_entry()
        self._update_all_btns()

    def _open_rune_page(self, champ_name, slot):
        if not champ_name or champ_name == "...":
            print(f"[DEBUG RUNES] _open_rune_page appelé mais champ_name vide (slot={slot})")
            logging.info(f"[DEBUG RUNES] _open_rune_page: champ_name vide (slot={slot})")
            return

        print(f"[DEBUG RUNES] _open_rune_page -> champ={champ_name}, slot={slot}")
        logging.info(f"[DEBUG RUNES] Ouverture RuneSelectorWindow pour champ={champ_name}, slot={slot}")

        # On charge les runes avant d'ouvrir
        self.parent.dd.load_runes()
        RuneSelectorWindow(self, champ_name, slot)


    def _update_all_btns(self):
        self._update_btn_content(self.btn_ban, self.parent.selected_ban, True)
        self._update_btn_content(self.btn_pick_1, self.parent.selected_pick_1, True)
        self._update_btn_content(self.btn_pick_2, self.parent.selected_pick_2, True)
        self._update_btn_content(self.btn_pick_3, self.parent.selected_pick_3, True)
        self._update_btn_content(self.btn_spell_1, self.parent.global_spell_1, False)
        self._update_btn_content(self.btn_spell_2, self.parent.global_spell_2, False)

    # ... (Methodes _open_champion_picker, _open_spell_picker, _update_btn_content, etc. identiques)
    # COPIE COLLE TES METHODES PRECEDENTES ICI
    def _open_champion_picker(self, context="pick", slot_num=1):
        picker = ttk.Toplevel(self.window)
        picker.title(f"Sélectionner Champion")
        picker.geometry(f"480x600+{self.window.winfo_x()+20}+{self.window.winfo_y()+20}")
        search_frame = ttk.Frame(picker, padding=10)
        search_frame.pack(fill="x")
        ttk.Label(search_frame, text="Rechercher :").pack(side="left")
        search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=search_var)
        search_entry.pack(side="left", fill="x", expand=True, padx=5)
        search_entry.focus_set()
        from ttkbootstrap.scrolled import ScrolledFrame
        scroll_container = ScrolledFrame(picker, autohide=False)
        scroll_container.pack(fill="both", expand=True, padx=5, pady=5)
        grid_frame = scroll_container
        excluded = set()
        if context == "pick":
            p1, p2, p3 = self.parent.selected_pick_1, self.parent.selected_pick_2, self.parent.selected_pick_3
            banned = self.parent.selected_ban
            if banned: excluded.add(banned)
            if slot_num == 1: excluded.update({p2, p3})
            elif slot_num == 2: excluded.update({p1, p3})
            elif slot_num == 3: excluded.update({p1, p2})
        valid_champs = [c for c in self.all_champions if c not in excluded]
        def populate_grid(filter_text=""):
            for widget in grid_frame.winfo_children(): widget.destroy()
            filter_text = filter_text.lower()
            row, col = 0, 0
            for champ_name in valid_champs:
                if filter_text in champ_name.lower():
                    btn = ttk.Button(grid_frame, text=champ_name, bootstyle="link", compound="top", command=lambda c=champ_name: on_select(c))
                    btn.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
                    self._load_img_into_btn(btn, champ_name, is_champ=True)
                    col += 1
                    if col >= 4: col, row = 0, row + 1
        def on_select(champ_name):
            if context == "ban":
                self.parent.selected_ban = champ_name
                self._update_btn_content(self.btn_ban, champ_name, True)
            elif context == "pick":
                if slot_num == 1: 
                    self.parent.selected_pick_1 = champ_name
                    self._update_btn_content(self.btn_pick_1, champ_name, True)
                elif slot_num == 2:
                    self.parent.selected_pick_2 = champ_name
                    self._update_btn_content(self.btn_pick_2, champ_name, True)
                elif slot_num == 3:
                    self.parent.selected_pick_3 = champ_name
                    self._update_btn_content(self.btn_pick_3, champ_name, True)
            picker.destroy()
        search_var.trace("w", lambda *args: populate_grid(search_var.get()))
        populate_grid()

    def _open_spell_picker(self, spell_slot_num):
        if not self.summ_var.get(): return
        picker = ttk.Toplevel(self.window)
        picker.title(f"Choisir Sort")
        picker.geometry(f"350x350+{self.window.winfo_x()+50}+{self.window.winfo_y()+100}")
        container = ttk.Frame(picker, padding=10)
        container.pack(fill="both", expand=True)
        def on_pick(spell_name):
            other = self.parent.global_spell_2 if spell_slot_num == 1 else self.parent.global_spell_1
            if spell_name == other and spell_name != "(Aucun)":
                if spell_slot_num == 1:
                    self.parent.global_spell_2 = "(Aucun)"
                    self._update_btn_content(self.btn_spell_2, "(Aucun)", False)
                else:
                    self.parent.global_spell_1 = "(Aucun)"
                    self._update_btn_content(self.btn_spell_1, "(Aucun)", False)
            if spell_slot_num == 1:
                self.parent.global_spell_1 = spell_name
                self._update_btn_content(self.btn_spell_1, spell_name, False)
            else:
                self.parent.global_spell_2 = spell_name
                self._update_btn_content(self.btn_spell_2, spell_name, False)
            picker.destroy()
        row, col = 0, 0
        for spell in self.spell_list:
            f = ttk.Frame(container)
            f.grid(row=row, column=col, padx=5, pady=5)
            btn = ttk.Button(f, bootstyle="link", command=lambda s=spell: on_pick(s))
            btn.pack()
            self._load_img_into_btn(btn, spell, False)
            col += 1
            if col > 3: col, row = 0, row + 1

    def _update_btn_content(self, btn_widget, name, is_champ=True):
        if not name: name = "..."
        def task():
            if is_champ: img = self.parent.dd.get_champion_icon(name)
            else: img = self.parent.dd.get_summoner_icon(name)
            if img:
                img = img.resize((30, 30), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                def ui():
                    if btn_widget.winfo_exists():
                        btn_widget.configure(image=photo, text=f"  {name}", compound="left")
                        btn_widget.image = photo
                btn_widget.after(0, ui)
            else:
                def ui_c():
                    if btn_widget.winfo_exists():
                        btn_widget.configure(image='', text=f"  {name}", compound="left")
                btn_widget.after(0, ui_c)
        Thread(target=task, daemon=True).start()

    def _load_img_into_btn(self, btn_widget, name, is_champ=True):
        def task():
            if is_champ: img = self.parent.dd.get_champion_icon(name)
            else: img = self.parent.dd.get_summoner_icon(name)
            if img:
                size = (40, 40) if is_champ else (48, 48)
                img = img.resize(size, Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                def ui():
                    if btn_widget.winfo_exists():
                        btn_widget.configure(image=photo)
                        btn_widget.image = photo
                btn_widget.after(0, ui)
        Thread(target=task, daemon=True).start()

    def toggle_summoner_entry(self):
        if self.summ_auto_var.get():
            current_entry = self.summ_entry_var.get()
            current_auto = self.parent._get_auto_summoner_name()
            if current_entry != current_auto and current_entry != "(détection auto...)":
                self.saved_manual_name = current_entry
            self.summ_entry.configure(state="readonly")
            self.region_cb.configure(state="disabled")
            self.parent.force_refresh_summoner()
            auto_name = self.parent._get_auto_summoner_name()
            self.summ_entry_var.set(auto_name if auto_name else "(détection auto...)")
            auto_reg = self.parent._platform_for_websites()
            self.region_var.set(auto_reg)
            setattr(self.parent, 'region', auto_reg)
        else:
            self.summ_entry.configure(state="normal")
            self.region_cb.configure(state="readonly")
            self.summ_entry_var.set(self.saved_manual_name)
            self.region_var.set(self.parent.region)
        self._update_detect_label_text()

    def toggle_pick(self):
        st = "normal" if self.pick_var.get() else "disabled"
        self.btn_pick_1.configure(state=st)
        self.btn_pick_2.configure(state=st)
        self.btn_pick_3.configure(state=st)

    def toggle_ban(self):
        self.btn_ban.configure(state="normal" if self.ban_var.get() else "disabled")

    def toggle_spells(self):
        st = "normal" if self.summ_var.get() else "disabled"
        self.btn_spell_1.configure(state=st)
        self.btn_spell_2.configure(state=st)

    def _update_detect_label_text(self):
        detected = self.parent._get_auto_summoner_name()
        if self.parent.ws_active and detected:
            self.lbl_auto_detect.configure(text=f"Détection auto du compte (compte détecté : {detected})")
        else:
            self.lbl_auto_detect.configure(text="Détection auto du compte")

    def _poll_summoner_label(self):
        if not self.window.winfo_exists(): return
        self._update_detect_label_text()
        if self.summ_auto_var.get():
            curr = self.parent._get_auto_summoner_name() or "(détection auto...)"
            if self.summ_entry_var.get() != curr: self.summ_entry_var.set(curr)
            areg = self.parent._platform_for_websites()
            if self.region_var.get() != areg:
                self.region_var.set(areg)
                setattr(self.parent, 'region', areg)
        if not self.summ_auto_var.get():
            self.saved_manual_name = self.summ_entry_var.get()
        self.window.after(1000, self._poll_summoner_label)

    def on_close(self):
        self.parent.auto_summoners_enabled = self.summ_var.get()
        self.parent.summoner_name_auto_detect = self.summ_auto_var.get()
        if not self.summ_auto_var.get():
            self.parent.manual_summoner_name = self.summ_entry_var.get()
            self.parent.region = self.region_var.get()
        self.parent.auto_play_again_enabled = self.play_again_var.get()
        self.parent.auto_meta_runes_enabled = self.meta_runes_var.get()
        self.parent.auto_hide_on_connect = self.auto_hide_var.get()
        self.parent.close_app_on_lol_exit = self.close_on_exit_var.get()
        self.parent.save_parameters()
        self.window.destroy()

# ───────────────────────────────────────────────────────────────────────────
# MAIN APP
# ───────────────────────────────────────────────────────────────────────────

class LoLAssistant:
    SUMMONER_SPELL_MAP = SUMMONER_SPELL_MAP

    def __init__(self):
        # ... (Init identique au précédent)
        self.theme = DEFAULT_PARAMS["theme"]
        self.root = ttk.Window(themename=self.theme)
        self.root.title("MAIN LOL")
        self.root.geometry("380x180")
        self.root.resizable(False, False)
        self.running = True
        self.auto_accept_enabled = DEFAULT_PARAMS["auto_accept_enabled"]
        self.auto_pick_enabled = DEFAULT_PARAMS["auto_pick_enabled"]
        self.auto_ban_enabled = DEFAULT_PARAMS["auto_ban_enabled"]
        self.auto_summoners_enabled = DEFAULT_PARAMS["auto_summoners_enabled"]
        self.selected_pick_1 = DEFAULT_PARAMS["selected_pick_1"]
        self.selected_pick_2 = DEFAULT_PARAMS["selected_pick_2"]
        self.selected_pick_3 = DEFAULT_PARAMS["selected_pick_3"]
        self.selected_ban = DEFAULT_PARAMS["selected_ban"]
        self.region = DEFAULT_PARAMS["region"]
        self.platform_routing = "euw1"
        self.region_routing = "europe"
        self.auto_play_again_enabled = DEFAULT_PARAMS["auto_play_again_enabled"]
        self.auto_meta_runes_enabled = DEFAULT_PARAMS["auto_meta_runes_enabled"]
        self.auto_hide_on_connect = DEFAULT_PARAMS["auto_hide_on_connect"]
        self.close_app_on_lol_exit = DEFAULT_PARAMS["close_app_on_lol_exit"]
        self.settings_win = None
        self.summoner = ""
        self.summoner_id = None
        self.puuid = None
        self.auto_game_name = None
        self.auto_tag_line = None
        self.manual_summoner_name = DEFAULT_PARAMS["manual_summoner_name"]
        self.summoner_name_auto_detect = DEFAULT_PARAMS["summoner_name_auto_detect"]
        self.global_spell_1 = DEFAULT_PARAMS["global_spell_1"]
        self.global_spell_2 = DEFAULT_PARAMS["global_spell_2"]
        self.completed_actions = set()
        self.has_picked = False
        self.has_banned = False
        self.intent_done = False
        self.last_action_try_ts = 0.0
        self.last_intent_try_ts = 0.0
        self.current_phase = "None"
        self.assigned_position = ""
        self.cs_tick_lock = asyncio.Lock()
        self.last_game_start_notify_ts = 0.0
        self.game_start_cooldown = 12.0
        self._last_cs_session_fetch = 0.0
        self._last_cs_timer_fetch = 0.0
        self.has_played_accept_sound = False
        self.dd = DataDragon()
        self.dd.load()
        self._stop_event = Event()
        self.ws_active = False
        self.connection = None
        self.lol_version = "v0.0.0"
        self.theme_var = tk.StringVar(value=self.theme)
        self.load_config()
        try:
            pygame.mixer.init()
            self.sound_effect = pygame.mixer.Sound(resource_path("config/son.wav"))
        except: self.sound_effect = None
        self.create_ui()
        self.create_system_tray()
        self.setup_hotkeys()
        if Connector is not None:
            self.ws_thread = Thread(target=self._ws_loop, daemon=True)
            self.ws_thread.start()
        else:
            self.root.after(100, lambda: self.update_status("❌ Erreur: 'lcu_driver' manquant."))
            self.root.after(100, lambda: self.update_connection_indicator(False))

    def load_config(self):
        if not os.path.exists(PARAMETERS_PATH): config = DEFAULT_PARAMS
        else:
            try:
                with open(PARAMETERS_PATH, 'r', encoding='utf-8') as f: config = json.load(f)
            except: config = DEFAULT_PARAMS
        self.auto_accept_enabled = config.get('auto_accept_enabled', self.auto_accept_enabled)
        self.auto_pick_enabled = config.get('auto_pick_enabled', self.auto_pick_enabled)
        self.auto_ban_enabled = config.get('auto_ban_enabled', self.auto_ban_enabled)
        self.auto_summoners_enabled = config.get('auto_summoners_enabled', self.auto_summoners_enabled)
        self.selected_pick_1 = config.get('selected_pick_1', self.selected_pick_1)
        self.selected_pick_2 = config.get('selected_pick_2', self.selected_pick_2)
        self.selected_pick_3 = config.get('selected_pick_3', self.selected_pick_3)
        self.selected_ban = config.get('selected_ban', self.selected_ban)
        self.region = config.get('region', self.region)
        self.theme = config.get('theme', self.theme)
        self.theme_var.set(self.theme)
        self.root.style.theme_use(self.theme)
        self.summoner_name_auto_detect = config.get('summoner_name_auto_detect', self.summoner_name_auto_detect)
        self.manual_summoner_name = config.get('manual_summoner_name', self.manual_summoner_name)
        self.summoner = config.get('summoner', '')
        self.global_spell_1 = config.get('global_spell_1', self.global_spell_1)
        self.global_spell_2 = config.get('global_spell_2', self.global_spell_2)
        self.auto_play_again_enabled = config.get('auto_play_again_enabled', self.auto_play_again_enabled)
        self.auto_meta_runes_enabled = config.get('auto_meta_runes_enabled', self.auto_meta_runes_enabled)
        self.auto_hide_on_connect = config.get('auto_hide_on_connect', self.auto_hide_on_connect)
        self.close_app_on_lol_exit = config.get('close_app_on_lol_exit', self.close_app_on_lol_exit)

    def save_parameters(self):
        config = {
            "auto_accept_enabled": self.auto_accept_enabled,
            "auto_pick_enabled": self.auto_pick_enabled,
            "auto_ban_enabled": self.auto_ban_enabled,
            "auto_summoners_enabled": self.auto_summoners_enabled,
            "selected_pick_1": self.selected_pick_1,
            "selected_pick_2": self.selected_pick_2,
            "selected_pick_3": self.selected_pick_3,
            "selected_ban": self.selected_ban,
            "region": self.region,
            "theme": self.theme_var.get(),
            "summoner_name_auto_detect": self.summoner_name_auto_detect,
            "manual_summoner_name": self.manual_summoner_name,
            "summoner": self.summoner,
            "global_spell_1": self.global_spell_1,
            "global_spell_2": self.global_spell_2,
            "auto_play_again_enabled": self.auto_play_again_enabled,
            "auto_meta_runes_enabled": self.auto_meta_runes_enabled,
            "auto_hide_on_connect": self.auto_hide_on_connect,
            "close_app_on_lol_exit": self.close_app_on_lol_exit,
        }
        try:
            os.makedirs(os.path.dirname(PARAMETERS_PATH), exist_ok=True)
            with open(PARAMETERS_PATH, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            self.show_toast("Paramètres sauvegardés !")
        except: self.show_toast(f"Erreur sauvegarde")

    def force_refresh_summoner(self):
        if self.ws_active and self.connection:
            if hasattr(self, 'loop'):
                asyncio.run_coroutine_threadsafe(self._refresh_player_and_region(), self.loop)

    def create_ui(self):
        # (Identique à avant)
        garen_icon = ImageTk.PhotoImage(Image.open(resource_path("./config/imgs/garen.webp")).resize((32, 32)))
        self.root.iconphoto(False, garen_icon)
        banner_img = ImageTk.PhotoImage(Image.open(resource_path("./config/imgs/garen.webp")).resize((48, 48)))
        self.banner_label = ttk.Label(self.root, image=banner_img)
        self.banner_label.image = banner_img
        self.banner_label.place(relx=0.5, rely=0.08, anchor="n")
        style = ttk.Style()
        style.configure("Status.TLabel", font=("Segoe UI", 12))
        self.connection_indicator = tk.Canvas(self.root, width=12, height=12, bd=0, highlightthickness=0, bg=self.root['bg'])
        self.connection_indicator.place(relx=0.05, rely=0.05, anchor="nw")
        self.update_connection_indicator(False)
        self.status_label = ttk.Label(self.root, text="🔌 En attente du WebSocket LCU...", style="Status.TLabel", justify="center", wraplength=380)
        self.status_label.place(relx=0.5, rely=0.38, anchor="center")
        gear_img = ImageTk.PhotoImage(Image.open(resource_path("./config/imgs/gear.png")).resize((25, 30)))
        bg_color = self.root['bg']
        cog = tk.Canvas(self.root, width=30, height=30, bd=0, highlightthickness=0, bg=bg_color, cursor="hand2")
        cog.create_image(0, 0, anchor="nw", image=gear_img)
        cog.image = gear_img
        cog.place(relx=0.95, rely=0.05, anchor="ne")
        def on_enter(e): cog.configure(bg="#2c2c2c")
        def on_leave(e): cog.configure(bg=bg_color)
        cog.bind("<Enter>", on_enter)
        cog.bind("<Leave>", on_leave)
        cog.bind("<Button-1>", lambda e: self.open_settings())
        opgg_btn = ttk.Button(self.root, text="📊 OP.GG", bootstyle="success-outline", padding=(20, 10), width=15, command=lambda: webbrowser.open(self.build_opgg_url()))
        opgg_btn.place(relx=0.5, rely=0.75, anchor="center")
        self.root.protocol("WM_DELETE_WINDOW", self.root.withdraw)

    def create_system_tray(self):
        try:
            image = Image.open(resource_path("./config/imgs/garen.webp")).resize((64, 64))
            menu = pystray.Menu(pystray.MenuItem("Afficher/Masquer", self.toggle_window), pystray.MenuItem("Quitter", self.quit_app))
            self.icon = pystray.Icon("MAIN LOL", image, "MAIN LOL", menu)
            Thread(target=self.icon.run, daemon=True).start()
        except: pass

    def setup_hotkeys(self):
        try:
            keyboard.add_hotkey('alt+p', self.open_porofessor)
            keyboard.add_hotkey('alt+c', self.toggle_window)
        except: pass

    def _platform_for_websites(self) -> str:
        mapping = {"euw1": "euw", "eun1": "eune", "na1": "na", "kr": "kr", "jp1": "jp", "br1": "br", "la1": "lan", "la2": "las", "oc1": "oce", "tr1": "tr", "ru": "ru"}
        if not self.summoner_name_auto_detect: return self.region.lower()
        return mapping.get((self.platform_routing or "").lower(), "euw")

    def _riot_url_name(self) -> str:
        disp_name = self._riot_id_display_string() or ""
        if "#" in disp_name:
            left, right = disp_name.split("#", 1)
            if left and right: return f"{left}-{right}"
        return disp_name

    def build_opgg_url(self) -> str:
        return f"https://www.op.gg/lol/summoners/{self._platform_for_websites()}/{urllib.parse.quote(self._riot_url_name())}"

    def build_porofessor_url(self) -> str:
        return f"https://porofessor.gg/fr/live/{self._platform_for_websites()}/{urllib.parse.quote(self._riot_url_name())}"

    def _riot_id_display_string(self) -> Optional[str]:
        if self.summoner_name_auto_detect: return self._get_auto_summoner_name()
        return self.manual_summoner_name or None

    def _get_auto_summoner_name(self) -> Optional[str]:
        if self.auto_game_name and self.auto_tag_line: return f"{self.auto_game_name}#{self.auto_tag_line}"
        return self.summoner or None

    def open_porofessor(self):
        if self._riot_id_display_string(): webbrowser.open(self.build_porofessor_url())

    def show_window(self, icon=None):
        if self.root.state() == 'withdrawn':
            self.root.after(0, self.root.deiconify)
            self.root.after(0, self.root.lift)

    def hide_window(self, icon=None):
        if self.root.state() != 'withdrawn': self.root.after(0, self.root.withdraw)

    def toggle_window(self, icon=None):
        if self.root.state() == 'withdrawn': self.show_window()
        else: self.hide_window()

    def open_settings(self):
        if self.settings_win and self.settings_win.window.winfo_exists():
            self.settings_win.window.lift()
            self.settings_win.window.focus_force()
            return
        self.settings_win = SettingsWindow(self)

    def quit_app(self):
        self.save_parameters()
        self.running = False
        self._stop_event.set()
        try:
            if hasattr(self, 'icon'): self.icon.stop()
        except: pass
        self.root.quit()
        remove_lockfile()

    def update_status(self, message: str):
        now = datetime.now().strftime("%H:%M:%S")
        text = f"[{now}] {message}"
        self.root.after(0, lambda: self.status_label.config(text=text))
        print(text, flush=True)

    def update_connection_indicator(self, connected: bool):
        def _draw():
            self.connection_indicator.delete("all")
            color = "#00ff00" if connected else "#ff0000"
            self.connection_indicator.create_oval(2, 2, 10, 10, fill=color, outline="")
            if connected:
                def pulse(step=0):
                    if not self.connection_indicator.winfo_exists(): return
                    r = 4 + int(2 * abs((step % 20) - 10) / 10)
                    self.connection_indicator.delete("all")
                    self.connection_indicator.create_oval(6 - r, 6 - r, 6 + r, 6 + r, fill=color, outline="")
                    if self.running and self.ws_active:
                        self.connection_indicator.after(50, lambda: pulse(step + 1))
                    elif self.connection_indicator.winfo_exists():
                        self.connection_indicator.delete("all")
                        self.connection_indicator.create_oval(2, 2, 10, 10, fill="#ff0000", outline="")
                pulse()
        self.root.after(0, _draw)

    def show_toast(self, message, duration=2000):
        try:
            toast = ttk.Label(self.root, text=message, bootstyle="success", font=("Segoe UI", 10, "bold"))
            toast.place(relx=0.5, rely=0.98, anchor="s")
            self.root.after(duration, toast.destroy)
        except: pass

    async def _refresh_player_and_region(self):
        if not self.connection: return
        chat_me = None
        resp_chat = await self.connection.request('get', "/lol-chat/v1/me")
        if resp_chat.status == 200: chat_me = await resp_chat.json()
        if isinstance(chat_me, dict):
            self.auto_game_name = chat_me.get("gameName")
            self.auto_tag_line = chat_me.get("gameTag")
            if self.auto_game_name and self.auto_tag_line: self.summoner = f"{self.auto_game_name}#{self.auto_tag_line}"
            else: self.summoner = chat_me.get("name", "Inconnu")
            self.summoner_id = chat_me.get("summonerId")
            self.puuid = chat_me.get("puuid")
            self.update_status(f"👤 Connecté : {self._riot_id_display_string()}")
        else:
            resp_me = await self.connection.request('get', "/lol-summoner/v1/current-summoner")
            if resp_me.status == 200:
                me = await resp_me.json()
                self.summoner = me.get("displayName", "Inconnu")
                self.update_status(f"👤 Connecté (Legacy) : {self.summoner}")
        reg = None
        resp_reg = await self.connection.request('get', "/riotclient/get_region_locale")
        if resp_reg.status != 200: resp_reg = await self.connection.request('get', "/riotclient/region-locale")
        if resp_reg.status == 200: reg = await resp_reg.json()
        if isinstance(reg, dict):
            platform = (reg.get("platformId") or reg.get("region") or "").lower()
            if platform:
                self.platform_routing = platform
                self.region_routing = self._platform_to_region_routing(platform)
                if self.summoner_name_auto_detect: self.region = self._platform_for_websites()

    @staticmethod
    def _platform_to_region_routing(platform: str) -> str:
        platform = platform.lower()
        if platform in {"euw1", "eun1", "tr1", "ru"}: return "europe"
        if platform in {"na1", "br1", "la1", "la2", "oc1"}: return "americas"
        if platform in {"kr", "jp1"}: return "asia"
        return "europe"

    def _notify_game_start_once(self):
        now = time()
        if now - self.last_game_start_notify_ts >= self.game_start_cooldown:
            self.show_toast("🎯 Game Start !")
            self.update_status("🎯 Game Start détecté")
            self.last_game_start_notify_ts = now

    def _reset_between_games(self):
        self.completed_actions.clear()
        self.has_picked = False
        self.has_banned = False
        self.intent_done = False
        self.assigned_position = ""
        self.last_action_try_ts = 0.0
        self.last_intent_try_ts = 0.0
        self._last_cs_session_fetch = 0.0
        self._last_cs_timer_fetch = 0.0
        self.has_played_accept_sound = False

    async def _champ_select_timer_tick(self):
        if not self.connection: return
        timer = None
        resp = await self.connection.request('get', "/lol-champ-select/v1/session/timer")
        if resp.status != 200: resp = await self.connection.request('get', "/lol-champ-select-legacy/v1/session/timer")
        if resp.status == 200: timer = await resp.json()
        if isinstance(timer, dict):
            phase = timer.get("phase") or timer.get("timerPhase") or ""
            remain = timer.get("phaseTimeRemaining") or timer.get("timeRemainingInPhase") or timer.get("adjustedTimeLeftInPhaseMs") or timer.get("totalTimeInPhase") or timer.get("timeLeftInPhase") or 0
            try: remain_sec = int(remain / 1000) if remain and remain > 1000 else int(remain)
            except: remain_sec = 0
            self.update_status(f"👑 ChampSelect • Phase timer: {phase} • reste ~{remain_sec}s")

    async def _champ_select_tick(self):
        if not self.connection: return
        session = None
        resp_sess = await self.connection.request('get', "/lol-champ-select/v1/session")
        if resp_sess.status != 200: resp_sess = await self.connection.request('get', "/lol-champ-select-legacy/v1/session")
        if resp_sess.status == 200: session = await resp_sess.json()
        else: return
        
        # ARAM check
        if session.get("benchEnabled") is True: return

        local_id = session.get("localPlayerCellId")
        if local_id is None: return

        if not self.assigned_position:
            my_team = session.get("myTeam", [])
            my_player_obj = next((p for p in my_team if p.get("cellId") == local_id), None)
            if my_player_obj:
                pos = (my_player_obj.get("assignedPosition") or "").upper()
                if pos:
                    self.assigned_position = pos
                    self.update_status(f"ℹ️ Rôle assigné détecté : {pos}")

        actions_groups = session.get("actions", []) or []
        my_pick_action, my_ban_action = self._get_my_pending_actions(actions_groups, local_id)

        # PRE-PICK
        pick_1_name = self.selected_pick_1
        if self.auto_pick_enabled and not self.intent_done and pick_1_name and my_pick_action:
            if not my_pick_action.get("completed"):
                if time() - self.last_intent_try_ts > 0.45:
                    cid = self.dd.resolve_champion(pick_1_name)
                    if isinstance(cid, int):
                        current_cid = my_pick_action.get("championId", 0) or 0
                        if current_cid != cid:
                            url_v1 = f"/lol-champ-select/v1/session/actions/{my_pick_action['id']}"
                            url_legacy = f"/lol-champ-select-legacy/v1/session/actions/{my_pick_action['id']}"
                            r = await self.connection.request('patch', url_v1, json={"championId": cid})
                            if r.status == 404: r = await self.connection.request('patch', url_legacy, json={"championId": cid})
                            cname = self.dd.id_to_name(cid) or str(cid)
                            if r and r.status < 400:
                                self.intent_done = True
                                self.update_status(f"🪄 Pré-pick (intention) sur {cname}")
                        else: self.intent_done = True
                    self.last_intent_try_ts = time()

        if time() - self.last_action_try_ts < 0.28: return

        # BAN
        if self.auto_ban_enabled and not self.has_banned and my_ban_action and self.selected_ban:
            if my_ban_action.get("isInProgress") is True:
                cid = self.dd.resolve_champion(self.selected_ban)
                if isinstance(cid, int): await self._perform_action_patch_then_complete(my_ban_action, cid, "BAN", self.selected_ban)

        # PICK
        if self.auto_pick_enabled and not self.has_picked and my_pick_action:
            if my_pick_action.get("isInProgress") is True:
                pickable_ids = []
                resp_picks = await self.connection.request('get', "/lol-champ-select/v1/pickable-champion-ids")
                if resp_picks.status == 200: pickable_ids = await resp_picks.json()
                pickable_set = set(pickable_ids)
                cid_to_pick, cname_to_pick = None, None
                pick_list = [self.selected_pick_1, self.selected_pick_2, self.selected_pick_3]
                for champ_name in pick_list:
                    if not champ_name: continue
                    cid = self.dd.resolve_champion(champ_name)
                    if cid and cid in pickable_set:
                        cid_to_pick, cname_to_pick = cid, champ_name
                        self.update_status(f"👑 Pick Prio '{cname_to_pick}' (dispo) trouvé !")
                        break
                if cid_to_pick and cname_to_pick:
                    await self._perform_action_patch_then_complete(my_pick_action, cid_to_pick, "PICK", cname_to_pick)
                else: self.update_status("⚠️ Aucun pick prioritaire n'est disponible.")
        self.last_action_try_ts = time()

    def _get_my_pending_actions(self, actions_groups: List[List[dict]], local_id: int) -> Tuple[Optional[dict], Optional[dict]]:
        my_pick, my_ban = None, None
        for group in actions_groups:
            for act in group:
                if act.get("actorCellId") != local_id or act.get("completed"): continue
                if act.get("type") == "ban" and my_ban is None: my_ban = act
                if act.get("type") == "pick" and my_pick is None: my_pick = act
        return my_pick, my_ban

    async def _perform_action_patch_then_complete(self, action: dict, champion_id: int, action_kind: str, champion_name: Optional[str] = None):
        if not self.connection: return
        action_id = action.get("id")
        if not isinstance(action_id, int): return
        if action_id in self.completed_actions: return
        cname = champion_name or self.dd.id_to_name(champion_id) or str(champion_id)
        url_v1 = f"/lol-champ-select/v1/session/actions/{action_id}"
        url_legacy = f"/lol-champ-select-legacy/v1/session/actions/{action_id}"
        payload = {"championId": champion_id, "completed": True}
        logging.info(f"Tentative de {action_kind} sur {cname} (Action ID: {action_id})...")
        r = await self.connection.request("patch", url_v1, json=payload)
        if r.status == 404: r = await self.connection.request("patch", url_legacy, json=payload)
        if not r or r.status >= 400:
            logging.error(f"Échec {action_kind} sur {cname}. Code: {r.status if r else 'None'}")
            return
        self.completed_actions.add(action_id)
        if action_kind == "BAN":
            self.has_banned = True
            self.update_status(f"🚫 {cname} banni automatiquement")
            logging.info(f"Succès BAN {cname}")
        elif action_kind == "PICK":
            self.has_picked = True
            self.update_status(f"👑 {cname} sélectionné automatiquement")
            logging.info(f"Succès PICK {cname}")
            if (self.auto_summoners_enabled or self.auto_meta_runes_enabled) and champion_name:
                asyncio.create_task(self._set_spells_and_runes(champion_name))

    async def _set_spells_and_runes(self, champion_name: str):
        try:
            if self.auto_summoners_enabled: await self._set_spells()
            if self.auto_meta_runes_enabled: await self._set_runes(champion_name)
        except Exception as e: print(f"[Runes/Spells] Erreur: {e}")

    async def _set_spells(self):
        if not self.connection: return
        spell1_name = self.global_spell_1
        spell2_name = self.global_spell_2
        spell1_id = self.SUMMONER_SPELL_MAP.get(spell1_name, 7)
        spell2_id = self.SUMMONER_SPELL_MAP.get(spell2_name, 4)
        payload = {"spell1Id": spell1_id, "spell2Id": spell2_id}
        r = await self.connection.request('patch', "/lol-champ-select/v1/session/my-selection", json=payload)
        if r and r.status < 400: self.update_status(f"🪄 Sorts auto-sélectionnés ({spell1_name}, {spell2_name})")

    async def _set_runes(self, champion_name: str):
        # 1. Vérifier si on a une config CUSTOM locale
        custom_runes = {}
        if os.path.exists(RUNES_CONFIG_PATH):
            try:
                with open(RUNES_CONFIG_PATH, "r") as f: data = json.load(f)
                custom_runes = data.get(champion_name)
            except: pass

        if custom_runes:
            # APPLICATION RUNES CUSTOM
            self.update_status(f"🔮 Runes : Application de votre page custom pour {champion_name}...")
            await self._apply_runes_payload(custom_runes)
        else:
            # APPLICATION RUNES RIOT (Fallback)
            if not self.connection: return
            champ_id = self.dd.resolve_champion(champion_name)
            if not champ_id: return
            position = (self.assigned_position or "").upper()
            if position == "ADC": position = "BOTTOM"
            if position == "SUPPORT": position = "UTILITY"
            if not position: return
            self.update_status(f"🔮 Runes : Recherche page Riot pour {champion_name} ({position})...")
            try:
                r = await self.connection.request('get', f"/lol-perks/v1/recommended-pages/champion/{champ_id}/position/{position}")
                if r.status != 200: return
                rec_pages = await r.json()
                if not rec_pages: return
                target_page = rec_pages[0]
                payload = {
                    "name": f"Auto {champion_name} ({position})",
                    "primaryStyleId": target_page.get("primaryPerkStyleId"),
                    "subStyleId": target_page.get("subPerkStyleId"),
                    "selectedPerkIds": target_page.get("selectedPerkIds"),
                    "current": True
                }
                await self._apply_runes_payload(payload)
            except Exception as e:
                print(f"[Runes] Erreur application runes : {e}")

    async def _apply_runes_payload(self, payload):
        # Logique commune pour appliquer une page (custom ou riot)
        try:
            pages_resp = await self.connection.request('get', "/lol-perks/v1/pages")
            all_pages = await pages_resp.json()
            existing_page_id = None
            for p in all_pages:
                if p.get("name", "").startswith("Auto ") and p.get("isEditable"):
                    existing_page_id = p.get("id")
                    break
            final_id = None
            if existing_page_id:
                await self.connection.request('put', f"/lol-perks/v1/pages/{existing_page_id}", json=payload)
                final_id = existing_page_id
            else:
                create_resp = await self.connection.request('post', "/lol-perks/v1/pages", json=payload)
                if create_resp.status >= 400:
                    first_editable = next((p for p in all_pages if p.get("isEditable")), None)
                    if first_editable:
                        await self.connection.request('delete', f"/lol-perks/v1/pages/{first_editable['id']}")
                        create_resp = await self.connection.request('post', "/lol-perks/v1/pages", json=payload)
                new_page = await create_resp.json()
                final_id = new_page.get("id")
            if final_id:
                await self.connection.request('put', "/lol-perks/v1/currentpage", data=str(final_id))
                self.update_status(f"✅ Runes appliquées !")
        except Exception as e:
            logging.error(f"Erreur application payload runes: {e}")

    async def _handle_post_game(self):
        if not self.auto_play_again_enabled: return
        for i in range(3):
            await asyncio.sleep(2)
            if self.current_phase not in ["EndOfGame", "WaitingForStats"]: break
            r = await self.connection.request('post', "/lol-lobby/v2/play-again")
            if r and r.status < 400:
                self.update_status("✅ Rejouer auto réussi !")
                break

    def _ws_loop(self):
        if Connector is None: return
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self.loop = loop 
            connector = Connector()
            @connector.ready
            async def on_ready(connection):
                self.connection = connection
                self.ws_active = True
                self.update_connection_indicator(True)
                self.update_status("🔌 WebSocket LCU connecté.")
                logging.info("WebSocket: Connecté au client LCU.")
                await self._refresh_player_and_region()
                if self.auto_hide_on_connect: self.root.after(3000, self.hide_window)
            @connector.close
            async def on_close(connection):
                self.connection = None
                self.ws_active = False
                self.update_connection_indicator(False)
                self.update_status("🛑 LoL déconnecté.")
                logging.info("WebSocket: Déconnecté.")
                if self.close_app_on_lol_exit: self.root.after(100, self.quit_app)
                else: self.root.after(100, self.show_window)
            @connector.ws.register(EP_CURRENT_SUMMONER)
            async def _ws_summoner_change(connection, event): await self._refresh_player_and_region()
            @connector.ws.register(EP_CHAT_ME)
            async def _ws_chat_me_change(connection, event): await self._refresh_player_and_region()
            @connector.ws.register(EP_LOGIN)
            async def _ws_login_session(connection, event):
                data = event.data or {}
                if data.get('status') == "SUCCEEDED":
                    self.update_status("🔄 Login détecté...")
                    await self._refresh_player_and_region()
            @connector.ws.register(EP_GAMEFLOW)
            async def _ws_phase(connection, event):
                phase = event.data
                if not phase: return
                if phase != self.current_phase: logging.info(f"Phase changée : {self.current_phase} -> {phase}")
                self.current_phase = phase
                self.update_status(f"ℹ️ Phase : {phase}")
                if phase == "ChampSelect":
                    self._reset_between_games()
                    await self._champ_select_tick()
                if phase in ("EndOfGame", "WaitingForStats"): await self._handle_post_game()
            @connector.ws.register(EP_READY_CHECK)
            async def _ws_ready(connection, event):
                if self.current_phase not in ["Matchmaking", "ReadyCheck", "None", "Lobby"]: return
                data = event.data or {}
                if self.auto_accept_enabled and data.get('state') == 'InProgress' and data.get('playerResponse') != 'Accepted':
                    await connection.request('post', f'{EP_READY_CHECK}/accept')
                    self.update_status("✅ Partie acceptée !")
            @connector.ws.register(EP_SESSION)
            async def _ws_cs_session(connection, event):
                if self.cs_tick_lock.locked(): return
                async with self.cs_tick_lock: await self._champ_select_tick()
            @connector.ws.register(EP_SESSION_TIMER)
            async def _ws_cs_timer(connection, event):
                if time() - self._last_cs_timer_fetch > 0.2:
                    await self._champ_select_timer_tick()
                    self._last_cs_timer_fetch = time()
            loop.run_until_complete(connector.start())
        except Exception as e:
            logging.critical(f"[WS] Erreur critique dans la boucle WebSocket : {e}", exc_info=True)
            self.ws_active = False

    def toggle_theme(self):
        new_theme = self.theme_var.get()
        self.root.style.theme_use(new_theme)
        self.theme = new_theme
        self.save_parameters()

if __name__ == "__main__":
    try:
        app = LoLAssistant()
        app.root.mainloop()
    finally:
        remove_lockfile()