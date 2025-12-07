"""
MAIN LOL - Assistant pour League of Legends
------------------------------------------
Auteur: Qurnt1
Version: 6.4 (Debug PICK & RUNES)
"""

# ───────────────────────────────────────────────────────────────────────────
# IMPORTS & CONFIGURATION SYSTEME
# ──────────────────────────────────────────────────────────────────────────

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
import requests
from io import BytesIO

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
URL_DD_IMG_CHAMP = "https://ddragon.leagueoflegends.com/cdn/{version}/img/champion/{filename}"
URL_DD_IMG_SPELL = "https://ddragon.leagueoflegends.com/cdn/{version}/img/spell/{filename}"

EP_SESSION = "/lol-champ-select/v1/session"
EP_SESSION_TIMER = "/lol-champ-select/v1/session/timer"
EP_SESSION_LEGACY = "/lol-champ-select-legacy/v1/session"
EP_GAMEFLOW = "/lol-gameflow/v1/gameflow-phase"
EP_READY_CHECK = "/lol-matchmaking/v1/ready-check"
EP_PICKABLE = "/lol-champ-select/v1/pickable-champion-ids"
EP_CURRENT_SUMMONER = "/lol-summoner/v1/current-summoner"
EP_CHAT_ME = "/lol-chat/v1/me"
EP_LOGIN = "/lol-login/v1/session"
EP_PERKS_PAGES = "/lol-perks/v1/pages"
EP_PERKS_CURRENT = "/lol-perks/v1/currentpage"

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
    "auto_hide_on_connect": True,
    "close_app_on_lol_exit": True,
    "champion_rune_map": {},  # {"ChampionName": PageID}
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
# DATA DRAGON
# ───────────────────────────────────────────────────────────────────────────

class DataDragon:
    URL_VERSIONS = "https://ddragon.leagueoflegends.com/api/versions.json"
    URL_DD_RUNES = "https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/runesReforged.json"
    URL_IMG_RUNE = "https://ddragon.leagueoflegends.com/cdn/img/{path}"
    CACHE_FILE = os.path.join(tempfile.gettempdir(), "mainlol_ddragon_champions.json")

    def __init__(self):
        self.loaded = False
        self.version = None
        self.by_norm_name: Dict[str, int] = {}
        self.by_id: Dict[int, Dict[str, Any]] = {}
        self.name_by_id: Dict[int, str] = {}
        self.all_names: List[str] = []
        self.summoner_data = {} 
        self.summoner_loaded = False
        
        # Runes
        self.runes_data = []
        self.runes_loaded = False
        self.perk_icon_map = {} # ID -> Path

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
            versions = requests.get(self.URL_VERSIONS, timeout=5).json()
            online_version = versions[0]
        except: pass
        
        if self._load_from_cache(target_version=online_version): return

        try:
            if not online_version: 
                versions = requests.get(self.URL_VERSIONS, timeout=5).json()
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
            # Fallback
            basic = {"garen": 86, "teemo": 17, "ashe": 22, "lux": 99}
            for n, cid in basic.items():
                self.by_norm_name[n] = cid
                self.by_id[cid] = {"name": n.title(), "key": str(cid)}
                self.name_by_id[cid] = n.title()
            self.version = "offline"
            self.all_names = sorted(list(self.name_by_id.values()))
            self.loaded = True

    def get_champion_icon(self, name_or_id) -> Optional[Image.Image]:
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
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                img = Image.open(BytesIO(r.content))
                with open(local_path, "wb") as f: f.write(r.content)
                return img
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
    
    def load_summoners(self):
        if self.summoner_loaded: return
        if not self.version: self.load() 
        url = URL_DD_SUMMONERS.format(version=self.version)
        try:
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                data = r.json().get("data", {})
                for key, info in data.items():
                    name = info.get("name")
                    image_full = info.get("image", {}).get("full")
                    if name and image_full:
                        self.summoner_data[name] = image_full
                self.summoner_loaded = True
        except: pass

    def get_summoner_icon(self, spell_name) -> Optional[Image.Image]:
        if spell_name == "(Aucun)" or not spell_name: return None
        self.load_summoners()
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
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                img = Image.open(BytesIO(r.content))
                with open(local_path, "wb") as f: f.write(r.content)
                return img
        except: pass
        return None

    def load_runes(self):
        if self.runes_loaded: return
        if not self.version: self.load()
        try:
            r = requests.get(self.URL_DD_RUNES.format(version=self.version), timeout=5)
            if r.status_code == 200:
                self.runes_data = r.json()
                for tree in self.runes_data:
                    for slot in tree.get('slots', []):
                        for rune in slot.get('runes', []):
                            self.perk_icon_map[rune['id']] = rune['icon']
                    self.perk_icon_map[tree['id']] = tree['icon']
                self.runes_loaded = True
        except: pass

    def get_rune_icon(self, perk_id: int) -> Optional[Image.Image]:
        self.load_runes()
        icon_path = self.perk_icon_map.get(perk_id)
        
        if not icon_path:
             shards = {
                 5001: "perk-images/StatMods/StatModsHealthScalingIcon.png",
                 5002: "perk-images/StatMods/StatModsArmorIcon.png",
                 5003: "perk-images/StatMods/StatModsMagicResIcon.png",
                 5005: "perk-images/StatMods/StatModsAttackSpeedIcon.png",
                 5007: "perk-images/StatMods/StatModsCDRScalingIcon.png",
                 5008: "perk-images/StatMods/StatModsAdaptiveForceIcon.png"
             }
             icon_path = shards.get(perk_id)

        if not icon_path: return None
        
        filename = icon_path.split('/')[-1]
        cache_dir = os.path.join(tempfile.gettempdir(), "mainlol_runes")
        os.makedirs(cache_dir, exist_ok=True)
        local_path = os.path.join(cache_dir, filename)

        if os.path.exists(local_path):
            try: return Image.open(local_path)
            except: pass

        url = self.URL_IMG_RUNE.format(path=icon_path)
        try:
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                with open(local_path, "wb") as f: f.write(r.content)
                return Image.open(BytesIO(r.content))
        except: pass
        return None

# ───────────────────────────────────────────────────────────────────────────
# WINDOW: RUNE CONFIG
# ───────────────────────────────────────────────────────────────────────────

class RuneConfigWindow:
    def __init__(self, parent, champion_name):
        self.parent = parent
        self.app = parent.parent 
        self.champion_name = champion_name
        self.window = ttk.Toplevel(parent.window)
        self.window.title(f"Runes pour {champion_name}")
        self.window.geometry("500x600")
        
        img = Image.open(resource_path("./config/imgs/garen.webp")).resize((16, 16))
        photo = ImageTk.PhotoImage(img)
        self.window.iconphoto(False, photo)
        self.window._icon_img = photo
        
        ttk.Label(self.window, text=f"Choisir une page pour {champion_name}", font=("Segoe UI", 12, "bold")).pack(pady=10)
        
        self.list_frame = ttk.Frame(self.window)
        self.list_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.status_lbl = ttk.Label(self.window, text="Chargement des pages...", bootstyle="info")
        self.status_lbl.pack(pady=5)

        Thread(target=self._fetch_pages_thread, daemon=True).start()

    def _fetch_pages_thread(self):
        if not self.app.ws_active:
            self.window.after(0, lambda: self.status_lbl.configure(text="Erreur: LoL non connecté", bootstyle="danger"))
            return

        async def get_pages():
            res = await self.app.connection.request('get', EP_PERKS_PAGES)
            if res.status == 200: return await res.json()
            return []

        try:
            future = asyncio.run_coroutine_threadsafe(get_pages(), self.app.loop)
            pages = future.result(timeout=5)
            self.window.after(0, lambda: self._populate_list(pages))
        except:
            self.window.after(0, lambda: self.status_lbl.configure(text="Erreur récupération pages", bootstyle="danger"))

    def _populate_list(self, pages):
        self.status_lbl.configure(text="Sélectionnez une page :", bootstyle="secondary")
        
        canvas = tk.Canvas(self.list_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.list_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Lecture dans l'app principale
        current_map_id = self.app.champion_rune_map.get(self.champion_name)
        print(f"[RuneWindow] Ouverture pour {self.champion_name}. ID actuel en mémoire: {current_map_id}")

        # Ajout option "Aucune"
        f_none = ttk.Frame(scrollable_frame)
        f_none.pack(fill="x", pady=2, padx=5)
        ttk.Button(f_none, text=" (Désactiver les runes auto pour ce champion)", bootstyle="secondary-link",
                   command=lambda: self._save_selection(None, "Désactivé")).pack(anchor="w", fill="x")

        for page in pages:
            pid = page['id']
            name = page['name']
            is_selected = (current_map_id == pid)
            all_perks = page.get('selectedPerkIds', [])

            frame_item = ttk.Frame(scrollable_frame, bootstyle="secondary" if not is_selected else "success")
            frame_item.pack(fill="x", pady=4, padx=5)

            btn = ttk.Button(frame_item, text=f" {name}", bootstyle="link", 
                             command=lambda i=pid, n=name: self._save_selection(i, n))
            btn.pack(anchor="w", fill="x", padx=5, pady=(5, 0))
            
            icon_frame = ttk.Frame(frame_item)
            icon_frame.pack(anchor="w", padx=15, pady=(0, 5))
            self._load_all_runes_imgs(icon_frame, all_perks)

    def _load_all_runes_imgs(self, container, perk_ids):
        def task():
            images = []
            for perk_id in perk_ids:
                img = self.app.dd.get_rune_icon(perk_id)
                if img:
                    img = img.resize((24, 24), Image.LANCZOS)
                    images.append(ImageTk.PhotoImage(img))
                else:
                    images.append(None)
            def ui():
                if not container.winfo_exists(): return
                for photo in images:
                    if photo:
                        lbl = ttk.Label(container, image=photo)
                        lbl.image = photo
                        lbl.pack(side="left", padx=1)
            self.window.after(0, ui)
        Thread(target=task, daemon=True).start()

    def _save_selection(self, page_id, page_name):
        print(f"\n[RuneWindow] --- SAUVEGARDE DEMANDEE ---")
        print(f"[RuneWindow] Champion: {self.champion_name}")
        print(f"[RuneWindow] Page Name: {page_name}")
        print(f"[RuneWindow] Page ID (brut): {page_id} (Type: {type(page_id)})")

        if page_id:
            # Force conversion to int
            self.app.champion_rune_map[self.champion_name] = int(page_id)
            print(f"[RuneWindow] -> Assignation: {self.champion_name} = {int(page_id)}")
        else:
            if self.champion_name in self.app.champion_rune_map:
                del self.app.champion_rune_map[self.champion_name]
            print(f"[RuneWindow] -> Suppression de la config pour {self.champion_name}")
        
        print(f"[RuneWindow] Etat de la MAP mémoire APRES modif: {self.app.champion_rune_map}")
        
        self.app.save_parameters()
        self.window.destroy()
        self.app.show_toast(f"Page '{page_name}' associée à {self.champion_name} !")


# ───────────────────────────────────────────────────────────────────────────
# SETTINGS WINDOW
# ───────────────────────────────────────────────────────────────────────────

class SettingsWindow:
    def __init__(self, parent):
        self.parent = parent
        self.window = ttk.Toplevel(parent.root)
        self.window.title("Paramètres - MAIN LOL")
        self.window.geometry("500x800") 
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

        # ROW 0
        ttk.Checkbutton(frame, text="Accepter la partie (Auto-Accept)", variable=self.auto_var,
                        command=lambda: setattr(self.parent, 'auto_accept_enabled', self.auto_var.get()),
                        bootstyle="success-round-toggle").grid(row=0, column=0, columnspan=2, sticky="w", pady=5)

        # ROW 1 (Auto Pick)
        ttk.Checkbutton(frame, text="Sécuriser mon Champion (Auto-Pick)", variable=self.pick_var,
                        command=lambda: (setattr(self.parent, 'auto_pick_enabled', self.pick_var.get()), self.toggle_pick()),
                        bootstyle="info-round-toggle").grid(row=1, column=0, columnspan=2, sticky="w", pady=(15, 5))

        # ROW 2 (Pick 1 + Rune Btn)
        ttk.Label(frame, text="Pick 1 :").grid(row=2, column=0, sticky="e", padx=5, pady=3)
        self.container_pick_1 = ttk.Frame(frame)
        self.container_pick_1.grid(row=2, column=1, sticky="ew", padx=5, pady=3)
        
        self.btn_pick_1 = ttk.Button(self.container_pick_1, text=self.parent.selected_pick_1, bootstyle="secondary-outline")
        self.btn_pick_1.pack(side="left", fill="x", expand=True)
        self.btn_pick_1.configure(command=lambda: self._open_champion_picker("pick", 1))

        self.btn_rune_1 = ttk.Button(self.container_pick_1, text="Runes ⚡", bootstyle="info-outline", width=8,
                                     command=lambda: self._open_rune_direct(self.parent.selected_pick_1))
        self.btn_rune_1.pack(side="right", padx=(5, 0))

        # ROW 3 (Pick 2 + Rune Btn)
        ttk.Label(frame, text="Pick 2 :").grid(row=3, column=0, sticky="e", padx=5, pady=3)
        self.container_pick_2 = ttk.Frame(frame)
        self.container_pick_2.grid(row=3, column=1, sticky="ew", padx=5, pady=3)

        self.btn_pick_2 = ttk.Button(self.container_pick_2, text=self.parent.selected_pick_2, bootstyle="secondary-outline")
        self.btn_pick_2.pack(side="left", fill="x", expand=True)
        self.btn_pick_2.configure(command=lambda: self._open_champion_picker("pick", 2))

        self.btn_rune_2 = ttk.Button(self.container_pick_2, text="Runes ⚡", bootstyle="info-outline", width=8,
                                     command=lambda: self._open_rune_direct(self.parent.selected_pick_2))
        self.btn_rune_2.pack(side="right", padx=(5, 0))

        # ROW 4 (Pick 3 + Rune Btn)
        ttk.Label(frame, text="Pick 3 :").grid(row=4, column=0, sticky="e", padx=5, pady=3)
        self.container_pick_3 = ttk.Frame(frame)
        self.container_pick_3.grid(row=4, column=1, sticky="ew", padx=5, pady=3)

        self.btn_pick_3 = ttk.Button(self.container_pick_3, text=self.parent.selected_pick_3, bootstyle="secondary-outline")
        self.btn_pick_3.pack(side="left", fill="x", expand=True)
        self.btn_pick_3.configure(command=lambda: self._open_champion_picker("pick", 3))

        self.btn_rune_3 = ttk.Button(self.container_pick_3, text="Runes ⚡", bootstyle="info-outline", width=8,
                                     command=lambda: self._open_rune_direct(self.parent.selected_pick_3))
        self.btn_rune_3.pack(side="right", padx=(5, 0))


        # ROW 5 (Auto Ban)
        ttk.Checkbutton(frame, text="Bannir un Champion (Auto-Ban)", variable=self.ban_var,
                        command=lambda: (setattr(self.parent, 'auto_ban_enabled', self.ban_var.get()), self.toggle_ban()),
                        bootstyle="danger-round-toggle").grid(row=5, column=0, columnspan=2, sticky="w", pady=(15, 5))

        # ROW 6 (Ban Button)
        ttk.Label(frame, text="Bannir :").grid(row=6, column=0, sticky="e", padx=5)
        self.btn_ban = ttk.Button(frame, text=self.parent.selected_ban, bootstyle="secondary-outline")
        self.btn_ban.grid(row=6, column=1, sticky="ew", padx=5)
        self.btn_ban.configure(command=lambda: self._open_champion_picker("ban"))

        # ROW 7 (Auto Summoners)
        ttk.Checkbutton(frame, text="Configurer Sorts (Auto-Spells)", variable=self.summ_var,
                        command=lambda: (setattr(self.parent, 'auto_summoners_enabled', self.summ_var.get()), self.toggle_spells()),
                        bootstyle="warning-round-toggle").grid(row=7, column=0, columnspan=2, sticky="w", pady=(15, 5))

        # ROW 8-9 (Spells)
        ttk.Label(frame, text="Sort 1 :").grid(row=8, column=0, sticky="e", padx=5, pady=3)
        self.btn_spell_1 = ttk.Button(frame, text=self.parent.global_spell_1, bootstyle="secondary-outline")
        self.btn_spell_1.grid(row=8, column=1, sticky="ew", padx=5, pady=3)
        self.btn_spell_1.configure(command=lambda: self._open_spell_picker(1))

        ttk.Label(frame, text="Sort 2 :").grid(row=9, column=0, sticky="e", padx=5, pady=3)
        self.btn_spell_2 = ttk.Button(frame, text=self.parent.global_spell_2, bootstyle="secondary-outline")
        self.btn_spell_2.grid(row=9, column=1, sticky="ew", padx=5, pady=3)
        self.btn_spell_2.configure(command=lambda: self._open_spell_picker(2))

        # ROW 11 : Détection Auto
        detect_frame = ttk.Frame(frame)
        detect_frame.grid(row=11, column=0, columnspan=2, sticky="w", pady=(15, 5))
        
        def on_auto_toggle():
            self.toggle_summoner_entry()
            if self.summ_auto_var.get():
                self.parent.force_refresh_summoner()
            self._update_detect_label_text()

        self.switch_auto = ttk.Checkbutton(
            detect_frame, 
            variable=self.summ_auto_var,
            command=on_auto_toggle, 
            bootstyle="round-toggle"
        )
        self.switch_auto.pack(side="left", padx=(0, 10))

        self.lbl_auto_detect = ttk.Label(detect_frame, text="Détection auto du compte")
        self.lbl_auto_detect.pack(side="left")

        # ROW 12 (Pseudo Entry)
        ttk.Label(frame, text="Pseudo :", anchor="w").grid(row=12, column=0, sticky="e", padx=5, pady=5)
        self.summ_entry = ttk.Entry(frame, textvariable=self.summ_entry_var, state="readonly")
        self.summ_entry.grid(row=12, column=1, sticky="ew", padx=5)

        # ROW 13 (Region)
        ttk.Label(frame, text="Région :", anchor="w").grid(row=13, column=0, sticky="e", padx=5, pady=5)
        self.region_var = tk.StringVar(value=self.parent.region)
        self.region_cb = ttk.Combobox(frame, values=REGION_LIST, textvariable=self.region_var, state="readonly")
        self.region_cb.grid(row=13, column=1, sticky="ew", padx=5)
        self.region_cb.bind("<<ComboboxSelected>>", lambda e: setattr(self.parent, 'region', self.region_var.get()))

        # ROW 14 (Sep)
        ttk.Separator(frame).grid(row=14, column=0, columnspan=2, sticky="we", pady=(15, 10))
        
        # ROW 15 (Misc)
        misc_frame = ttk.Frame(frame)
        misc_frame.grid(row=15, column=0, columnspan=2, sticky="w")
        
        ttk.Checkbutton(misc_frame, text="Retour au salon automatique (Skip Honor)", variable=self.play_again_var,
                        command=lambda: setattr(self.parent, 'auto_play_again_enabled', self.play_again_var.get()),
                        bootstyle="info-round-toggle").pack(anchor="w", pady=2)
        
        ttk.Checkbutton(misc_frame, text="Masquer Main LOL quand LoL se lance", variable=self.auto_hide_var,
                        command=lambda: setattr(self.parent, 'auto_hide_on_connect', self.auto_hide_var.get()),
                        bootstyle="secondary-round-toggle").pack(anchor="w", pady=2)
        
        ttk.Checkbutton(misc_frame, text="Fermer Main LOL quand LoL se ferme", variable=self.close_on_exit_var,
                        command=lambda: setattr(self.parent, 'close_app_on_lol_exit', self.close_on_exit_var.get()),
                        bootstyle="danger-round-toggle").pack(anchor="w", pady=2)

        ttk.Button(self.window, text="Fermer", command=self.on_close, bootstyle="primary").pack(pady=(0, 20), side="bottom")

        self.toggle_pick()
        self.toggle_ban()
        self.toggle_spells()
        self.toggle_summoner_entry()
        
        self._update_btn_content(self.btn_ban, self.parent.selected_ban, is_champ=True)
        self._update_btn_content(self.btn_pick_1, self.parent.selected_pick_1, is_champ=True)
        self._update_btn_content(self.btn_pick_2, self.parent.selected_pick_2, is_champ=True)
        self._update_btn_content(self.btn_pick_3, self.parent.selected_pick_3, is_champ=True)
        self._update_btn_content(self.btn_spell_1, self.parent.global_spell_1, is_champ=False)
        self._update_btn_content(self.btn_spell_2, self.parent.global_spell_2, is_champ=False)

    def _open_rune_direct(self, champion_name):
        if not champion_name: 
            self.parent.show_toast("Veuillez sélectionner un champion d'abord.")
            return
        RuneConfigWindow(self, champion_name)

    def _open_champion_picker(self, context="pick", slot_num=1):
        picker = ttk.Toplevel(self.window)
        picker.iconphoto(False, self.window._icon_img)
        title = "Sélectionner Champion"
        if context == "rune": title += " (Pour Runes)"
        elif context == "ban": title += " (Ban)"
        else: title += f" (Pick {slot_num})"
        
        picker.title(title)
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
                    btn = ttk.Button(grid_frame, text=champ_name, bootstyle="link", compound="top",
                                     command=lambda c=champ_name: on_select(c))
                    btn.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
                    self._load_img_into_btn(btn, champ_name, is_champ=True)
                    col += 1
                    if col >= 4:
                        col = 0
                        row += 1

        def on_select(champ_name):
            if context == "rune":
                RuneConfigWindow(self, champ_name)
            elif context == "ban":
                self.parent.selected_ban = champ_name
                self._update_btn_content(self.btn_ban, champ_name, True)
            elif context == "pick":
                if slot_num == 1: 
                    self.parent.selected_pick_1 = champ_name
                    self._update_btn_content(self.btn_pick_1, champ_name, True)
                    self.btn_rune_1.configure(command=lambda: self._open_rune_direct(champ_name))
                elif slot_num == 2:
                    self.parent.selected_pick_2 = champ_name
                    self._update_btn_content(self.btn_pick_2, champ_name, True)
                    self.btn_rune_2.configure(command=lambda: self._open_rune_direct(champ_name))
                elif slot_num == 3:
                    self.parent.selected_pick_3 = champ_name
                    self._update_btn_content(self.btn_pick_3, champ_name, True)
                    self.btn_rune_3.configure(command=lambda: self._open_rune_direct(champ_name))
            picker.destroy()

        search_var.trace("w", lambda *args: populate_grid(search_var.get()))
        search_entry.bind("<Return>", lambda e: grid_frame.winfo_children()[0].invoke() if grid_frame.winfo_children() else None)
        populate_grid()

    def _open_spell_picker(self, spell_slot_num):
        if not self.summ_var.get(): return
        picker = ttk.Toplevel(self.window)
        picker.iconphoto(False, self.window._icon_img)
        picker.title(f"Choisir Sort {spell_slot_num}")
        picker.geometry(f"350x350+{self.window.winfo_x()+50}+{self.window.winfo_y()+100}")
        picker.resizable(False, False)
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
            if col > 3:
                col = 0
                row += 1

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
        self.btn_rune_1.configure(state=st)
        self.btn_rune_2.configure(state=st)
        self.btn_rune_3.configure(state=st)

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
        self.parent.auto_hide_on_connect = self.auto_hide_var.get()
        self.parent.close_app_on_lol_exit = self.close_on_exit_var.get()
        self.parent.save_parameters()
        self.window.destroy()

# ───────────────────────────────────────────────────────────────────────────
# MAIN APP
# ───────────────────────────────────────────────────────────────────────────

class LoLAssistant:
    SUMMONER_SPELL_MAP = SUMMONER_SPELL_MAP
    CURRENT_VERSION = "6.4" 
    GITHUB_REPO_URL = "https://github.com/qurnt1/main_lol_2"
    RAW_README_URL = "https://raw.githubusercontent.com/qurnt1/main_lol_2/refs/heads/main/readme.md"

    def __init__(self):
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
        self.region = DEFAULT_PARAMS["region"]
        self.platform_routing = "euw1"
        self.region_routing = "europe"
        self.auto_play_again_enabled = DEFAULT_PARAMS["auto_play_again_enabled"]
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
        
        self.last_reported_summoner = None 

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

        self.selected_pick_1 = DEFAULT_PARAMS["selected_pick_1"]
        self.selected_pick_2 = DEFAULT_PARAMS["selected_pick_2"]
        self.selected_pick_3 = DEFAULT_PARAMS["selected_pick_3"]
        self.selected_ban = DEFAULT_PARAMS["selected_ban"]
        self.global_spell_1 = DEFAULT_PARAMS["global_spell_1"]
        self.global_spell_2 = DEFAULT_PARAMS["global_spell_2"]
        self.champion_rune_map = DEFAULT_PARAMS.get("champion_rune_map", {})

        self.lol_version = "v0.0.0"
        self.theme_var = tk.StringVar(value=self.theme)
        self.load_config()

        try:
            pygame.mixer.init()
            self.sound_effect = pygame.mixer.Sound(resource_path("config/son.wav"))
        except: self.sound_effect = None

        print(f"[INIT] Map Runes chargée au démarrage: {self.champion_rune_map}")

        self.create_ui()
        self.create_system_tray()
        self.setup_hotkeys()

        self.check_for_updates()

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
        self.auto_hide_on_connect = config.get('auto_hide_on_connect', self.auto_hide_on_connect)
        self.close_app_on_lol_exit = config.get('close_app_on_lol_exit', self.close_app_on_lol_exit)
        self.champion_rune_map = config.get('champion_rune_map', self.champion_rune_map)

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
            "auto_hide_on_connect": self.auto_hide_on_connect,
            "close_app_on_lol_exit": self.close_app_on_lol_exit,
            "champion_rune_map": self.champion_rune_map,
        }
        try:
            os.makedirs(os.path.dirname(PARAMETERS_PATH), exist_ok=True)
            with open(PARAMETERS_PATH, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            print(f"[SAVE] Paramètres sauvegardés sur disque.")
            self.show_toast("Paramètres sauvegardés !")
        except Exception as e:
            print(f"[SAVE ERROR] {e}")
            self.show_toast(f"Erreur sauvegarde")

    def force_refresh_summoner(self):
        if self.ws_active and self.connection:
            logging.info("Refresh forcé des données Summoner demandé via UI.")
            if hasattr(self, 'loop'):
                asyncio.run_coroutine_threadsafe(self._refresh_player_and_region(), self.loop)

    def create_ui(self):
        style = ttk.Style()
        style.configure(".", font=("Segoe UI Emoji", 10))
        style.configure("Status.TLabel", font=("Segoe UI Emoji", 11), background=self.root['bg'])
        
        garen_icon = ImageTk.PhotoImage(Image.open(resource_path("./config/imgs/garen.webp")).resize((32, 32)))
        self.root.iconphoto(False, garen_icon)
        banner_img = ImageTk.PhotoImage(Image.open(resource_path("./config/imgs/garen.webp")).resize((48, 48)))
        
        self.bg_label = tk.Label(self.root, bg="#2b2b2b")
        self.bg_label.place(x=0, y=0, relwidth=1, relheight=1)
        self.bg_label.lower()
        
        self.banner_label = ttk.Label(self.root, image=banner_img)
        self.banner_label.image = banner_img
        self.banner_label.place(relx=0.5, rely=0.08, anchor="n")

        self.connection_indicator = tk.Canvas(self.root, width=12, height=12, bd=0, highlightthickness=0, bg="#2b2b2b")
        self.connection_indicator.place(relx=0.05, rely=0.05, anchor="nw")
        self.update_connection_indicator(False)

        self.status_label = ttk.Label(
            self.root, 
            text="En attente du lancement de League of Legends...", 
            style="Status.TLabel", 
            justify="center", 
            wraplength=380
        )
        self.status_label.place(relx=0.5, rely=0.38, anchor="center")

        gear_path = resource_path("./config/imgs/gear.png")
        if os.path.exists(gear_path):
            gear_img = ImageTk.PhotoImage(Image.open(gear_path).resize((25, 30)))
            cog = ttk.Label(self.root, image=gear_img, cursor="hand2")
            cog.image = gear_img
            cog.place(relx=0.95, rely=0.05, anchor="ne")
            cog.bind("<Button-1>", lambda e: self.open_settings())
        else:
            cog = ttk.Button(self.root, text="⚙", command=self.open_settings, bootstyle="link")
            cog.place(relx=0.95, rely=0.05, anchor="ne")

        opgg_btn = ttk.Button(
            self.root, 
            text="Voir mes stats (OP.GG)", 
            bootstyle="success-outline",
            padding=(20, 10), 
            width=22, 
            command=lambda: webbrowser.open(self.build_opgg_url())
        )
        opgg_btn.place(relx=0.5, rely=0.75, anchor="center")

        self.root.protocol("WM_DELETE_WINDOW", self.root.withdraw)

    def set_background_splash(self, champion_name):
        def _task():
            try:
                cid = self.dd.resolve_champion(champion_name)
                if not cid: return
                real_name = self.dd.by_id[cid].get("id", champion_name)
                url = f"https://ddragon.leagueoflegends.com/cdn/img/champion/splash/{real_name}_0.jpg"
                
                response = requests.get(url, stream=True, timeout=5)
                if response.status_code == 200:
                    from io import BytesIO
                    from PIL import Image, ImageEnhance

                    img_data = BytesIO(response.content)
                    pil_img = Image.open(img_data)

                    window_w, window_h = 380, 180
                    base_width = window_w
                    w_percent = (base_width / float(pil_img.size[0]))
                    h_size = int((float(pil_img.size[1]) * float(w_percent)))
                    
                    if h_size < window_h:
                        base_height = window_h
                        h_percent = (base_height / float(pil_img.size[1]))
                        w_size = int((float(pil_img.size[0]) * float(h_percent)))
                        pil_img = pil_img.resize((w_size, base_height), Image.Resampling.LANCZOS)
                    else:
                        pil_img = pil_img.resize((base_width, h_size), Image.Resampling.LANCZOS)

                    left = (pil_img.width - window_w) / 2
                    top = (pil_img.height - window_h) / 2
                    right = (pil_img.width + window_w) / 2
                    bottom = (pil_img.height + window_h) / 2
                    pil_img = pil_img.crop((left, top, right, bottom))

                    enhancer = ImageEnhance.Brightness(pil_img)
                    pil_img = enhancer.enhance(0.4) 

                    tk_img = ImageTk.PhotoImage(pil_img)
                    
                    def _update_ui():
                        if self.root.winfo_exists():
                            self.bg_label.configure(image=tk_img)
                            self.bg_label.image = tk_img 
                    
                    self.root.after(0, _update_ui)

            except Exception as e:
                print(f"Erreur Splash Art: {e}")

        Thread(target=_task, daemon=True).start()

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
            keyboard.add_hotkey('f10', lambda: asyncio.run_coroutine_threadsafe(self._champ_select_tick(), self.loop))
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

    def update_status(self, message: str, emoji: str = ""):
        now = datetime.now().strftime("%H:%M:%S")
        log_msg = f"[{now}] {emoji} {message}" if emoji else f"[{now}] {message}"
        print(log_msg, flush=True)
        self.root.after(0, lambda: self.status_label.config(text=message))

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
        else:
            resp_me = await self.connection.request('get', "/lol-summoner/v1/current-summoner")
            if resp_me.status == 200:
                me = await resp_me.json()
                self.summoner = me.get("displayName", "Inconnu")
        
        if self.summoner != self.last_reported_summoner:
            self.update_status(f"Connecté : {self._riot_id_display_string()}", "👤")
            self.last_reported_summoner = self.summoner

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
            self.show_toast("Game Start !")
            self.update_status("Game Start détecté", "🎯")
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

    async def _champ_select_tick(self):
        if not self.connection: return
        
        try:
            resp = await self.connection.request('get', "/lol-champ-select/v1/session")
            if resp.status != 200: return
            session = await resp.json()
        except: return

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
                    self.update_status(f"Rôle assigné détecté : {pos}", "ℹ️")

        actions_groups = session.get("actions", [])
        my_actions = []
        for group in actions_groups:
            for action in group:
                if action.get("actorCellId") == local_id and not action.get("completed"):
                    my_actions.append(action)

        # PRE-PICK
        if self.auto_pick_enabled and self.selected_pick_1:
            pick_action = next((a for a in my_actions if a.get("type") == "pick"), None)
            if pick_action:
                target_cid = self.dd.resolve_champion(self.selected_pick_1)
                current_hover = pick_action.get("championId")
                if target_cid and target_cid != 0 and current_hover != target_cid:
                    if time() - self.last_intent_try_ts > 0.5:
                        await self._hover_champion(pick_action["id"], target_cid)
                        self.last_intent_try_ts = time()

        # ACTIONS (BAN & PICK)
        active_action = next((a for a in my_actions if a.get("isInProgress") is True), None)

        if active_action:
            action_type = active_action.get("type")
            
            if action_type == "ban" and self.auto_ban_enabled:
                await self._logic_do_ban(active_action)

            elif action_type == "pick" and self.auto_pick_enabled:
                await self._logic_do_pick(active_action)

    async def _hover_champion(self, action_id, champion_id):
        url = f"/lol-champ-select/v1/session/actions/{action_id}"
        await self.connection.request('patch', url, json={"championId": champion_id})

    async def _logic_do_ban(self, action):
        if not self.selected_ban: return
        if time() - self.last_action_try_ts < 0.1: return
        self.last_action_try_ts = time()

        cid = self.dd.resolve_champion(self.selected_ban)
        if not cid: return

        success = await self._lock_in_champion(action["id"], cid)
        if success:
            self.has_banned = True
            self.update_status(f"Ciao ! {self.selected_ban} a été banni.", "💀")

    async def _logic_do_pick(self, action):
        if time() - self.last_action_try_ts < 0.1: return
        self.last_action_try_ts = time()

        # LOG DEBUG
        print(f"[Pick] --- TENTATIVE DE PICK DETECTEE --- (Action ID: {action['id']})")

        pickable_ids = []
        try:
            r = await self.connection.request('get', EP_PICKABLE)
            if r.status == 200: 
                pickable_ids = await r.json()
        except: pass
        
        pickable_set = set(pickable_ids) if pickable_ids else set()
        is_list_empty = (len(pickable_set) == 0)
        
        # LOG DEBUG
        print(f"[Pick] Champions pickables disponibles (len): {len(pickable_set)}")

        for name in [self.selected_pick_1, self.selected_pick_2, self.selected_pick_3]:
            if not name: continue
            cid = self.dd.resolve_champion(name)
            if not cid: 
                print(f"[Pick] Nom de champion invalide: {name}")
                continue
            
            print(f"[Pick] Analyse du choix: {name} (ID: {cid})...")
            
            should_try = (cid in pickable_set) or is_list_empty

            if should_try:
                print(f"[Pick] -> Tentative de lock-in pour {name}...")
                success = await self._lock_in_champion(action["id"], cid)
                
                # Modif Debug: On considère que si le lock-in a été envoyé, on tente quand même les runes
                # même si le retour est False (car parfois l'API foire mais le pick passe)
                if success:
                    print(f"[Pick] -> SUCCES Lock-in {name}")
                    self.has_picked = True
                    self.update_status(f"{name} sécurisé ! À toi de jouer.", "🔒")
                    self.set_background_splash(name)
                    
                    print(f"[Logic] Champion pické: {name}. Lancement config runes...")
                    asyncio.create_task(self._apply_rune_page(name))

                    if self.auto_summoners_enabled:
                         asyncio.create_task(self._set_spells())
                    return 
                else:
                    print(f"[Pick] -> ECHEC Lock-in pour {name}. Essai suivant...")
            else:
                 print(f"[Pick] {name} (ID {cid}) n'est PAS dans la liste pickable (Banni ou pas possédé ?)")
        
        self.update_status("Aucun champion dispo ou configuré (ou tous bannis) !", "⚠️")

    async def _lock_in_champion(self, action_id, champion_id):
        url_action = f"/lol-champ-select/v1/session/actions/{action_id}"
        await self.connection.request('patch', url_action, json={"championId": champion_id})
        await asyncio.sleep(0.05) 
        
        # Essai de lock standard
        r_complete = await self.connection.request('post', f"{url_action}/complete", json={"championId": champion_id})
        print(f"[Pick] Lock-in Result (1er essai): {r_complete.status}")
        
        if r_complete.status < 400: return True
        
        # Retry bourrin si échec (parfois nécessaire)
        await asyncio.sleep(0.1)
        r_retry = await self.connection.request('post', f"{url_action}/complete")
        print(f"[Pick] Lock-in Result (Retry): {r_retry.status}")
        
        return r_retry.status < 400

    async def _set_spells(self):
        if not self.connection: return
        spell1_name = self.global_spell_1
        spell2_name = self.global_spell_2
        spell1_id = self.SUMMONER_SPELL_MAP.get(spell1_name, 7)
        spell2_id = self.SUMMONER_SPELL_MAP.get(spell2_name, 4)
        payload = {"spell1Id": spell1_id, "spell2Id": spell2_id}
        r = await self.connection.request('patch', "/lol-champ-select/v1/session/my-selection", json=payload)
        if r and r.status < 400: self.update_status(f"Sorts auto-sélectionnés ({spell1_name}, {spell2_name})", "🪄")

    async def _apply_rune_page(self, champion_name):
        print(f"\n[Runes] --- DEBUT APPLICATION RUNES ---")
        print(f"[Runes] Champion demandé : {champion_name}")
        
        # DEBUG: Afficher la map complète en mémoire
        print(f"[Runes] Etat de la MAP mémoire AVANT lecture : {self.champion_rune_map}")
        
        page_id = self.champion_rune_map.get(champion_name)
        if not page_id:
            print(f"[Runes] AUCUNE page configurée pour {champion_name} dans la map.")
            return

        print(f"[Runes] ID cible trouvé dans la config : {page_id} (Type: {type(page_id)})")

        pages_req = await self.connection.request('get', EP_PERKS_PAGES)
        if pages_req.status != 200: 
            print(f"[Runes] ERREUR : Impossible de récupérer les pages du client (Status {pages_req.status})")
            return
        
        pages = await pages_req.json()
        print(f"[Runes] Nombre de pages dans le client : {len(pages)}")
        
        # Vérification si l'ID existe
        target_page = next((p for p in pages if p['id'] == int(page_id)), None)
        
        if target_page:
            print(f"[Runes] Page correspondante trouvée dans le client : '{target_page['name']}' (ID {target_page['id']})")
            res = await self.connection.request('put', EP_PERKS_CURRENT, json=int(page_id))
            
            if res.status < 400:
                self.update_status(f"Page de runes chargée : {target_page['name']}", "📜")
                print(f"[Runes] SUCCES : Page appliquée !")
            else:
                print(f"[Runes] ECHEC : Le client a refusé le changement (Status {res.status})")
        else:
            self.update_status(f"Page de runes (ID {page_id}) introuvable !", "⚠️")
            print(f"[Runes] CRITIQUE : L'ID {page_id} est dans la config mais n'existe plus dans le client LoL.")
            print(f"[Runes] Liste des IDs disponibles : {[p['id'] for p in pages]}")

    async def _handle_post_game(self):
        if not self.auto_play_again_enabled: return
        for i in range(3):
            await asyncio.sleep(2)
            if self.current_phase not in ["EndOfGame", "WaitingForStats"]: break
            r = await self.connection.request('post', "/lol-lobby/v2/play-again")
            if r and r.status < 400:
                self.update_status("Rejouer auto réussi !", "✅")
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
                self.update_status("Client LoL détecté ! Prêt à vous aider.", "⚡")
                logging.info("WebSocket: Connecté au client LCU.")
                await self._refresh_player_and_region()
                if self.auto_hide_on_connect: self.root.after(3000, self.hide_window)

            @connector.close
            async def on_close(connection):
                self.connection = None
                self.ws_active = False
                self.update_connection_indicator(False)
                self.update_status("LoL fermé. En attente...", "💤")
                self.last_reported_summoner = None 
                logging.info("WebSocket: Déconnecté.")
                if self.close_app_on_lol_exit: self.root.after(100, self.quit_app)
                else: self.root.after(100, self.show_window)

            @connector.ws.register(EP_CURRENT_SUMMONER)
            async def _ws_summoner_change(connection, event):
                await self._refresh_player_and_region()

            @connector.ws.register(EP_CHAT_ME)
            async def _ws_chat_me_change(connection, event):
                await self._refresh_player_and_region()

            @connector.ws.register(EP_LOGIN)
            async def _ws_login_session(connection, event):
                data = event.data or {}
                if data.get('status') == "SUCCEEDED":
                    self.update_status("Login détecté...", "🔄")
                    await self._refresh_player_and_region()

            @connector.ws.register(EP_GAMEFLOW)
            async def _ws_phase(connection, event):
                phase = event.data
                if not phase: return
                if phase != self.current_phase:
                    logging.info(f"Phase changée : {self.current_phase} -> {phase}")
                self.current_phase = phase
                
                phase_map = {
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
                friendly_phase = phase_map.get(phase, phase)
                self.update_status(f"Statut : {friendly_phase}", "ℹ️")
                
                if phase == "ChampSelect":
                    self._reset_between_games()
                    await self._champ_select_tick()
                if phase in ("EndOfGame", "WaitingForStats"):
                    await self._handle_post_game()

            @connector.ws.register(EP_READY_CHECK)
            async def _ws_ready(connection, event):
                if self.current_phase not in ["Matchmaking", "ReadyCheck", "None", "Lobby"]: return
                data = event.data or {}
                if self.auto_accept_enabled and data.get('state') == 'InProgress' and data.get('playerResponse') != 'Accepted':
                    await connection.request('post', f'{EP_READY_CHECK}/accept')
                    self.update_status("Partie acceptée !", "✅")

            @connector.ws.register(EP_SESSION)
            async def _ws_cs_session(connection, event):
                if self.cs_tick_lock.locked(): return
                async with self.cs_tick_lock:
                    await self._champ_select_tick()

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

    def check_for_updates(self):
        def _check():
            print("[Update] Vérification des mises à jour...")
            try:
                r = requests.get(self.RAW_README_URL, timeout=5)
                if r.status_code == 200:
                    content = r.text
                    match = re.search(r"v(\d+\.\d+)", content)
                    
                    if match:
                        remote_version = match.group(1)
                        print(f"[Update] Version en ligne trouvée : {remote_version} (Locale : {self.CURRENT_VERSION})")
                        
                        if remote_version != self.CURRENT_VERSION:
                            self.root.after(0, lambda: self._show_update_popup(remote_version))
                    else:
                        print("[Update] Impossible de trouver le numéro de version dans le README.")
                else:
                    print(f"[Update] Echec téléchargement README. Code: {r.status_code}")
            except Exception as e:
                print(f"[Update] Erreur vérification : {e}")

        Thread(target=_check, daemon=True).start()

    def _show_update_popup(self, new_version):
        popup = ttk.Toplevel(self.root)
        popup.title("Mise à jour MAIN LOL")
        popup.geometry("400x250")
        popup.resizable(False, False)
        
        popup.update_idletasks()
        width = popup.winfo_width()
        height = popup.winfo_height()
        x = (popup.winfo_screenwidth() // 2) - (width // 2)
        y = (popup.winfo_screenheight() // 2) - (height // 2)
        popup.geometry(f'{width}x{height}+{x}+{y}')

        try:
            icon_path = resource_path("./config/imgs/garen.webp")
            if os.path.exists(icon_path):
                img = Image.open(icon_path).resize((32, 32))
                photo = ImageTk.PhotoImage(img)
                popup.iconphoto(False, photo)
                popup.iconphoto(True, photo) 
                popup._icon_ref = photo 
        except: pass

        title_lbl = ttk.Label(
            popup, 
            text="Nouvelle version détectée !", 
            font=("Segoe UI Emoji", 14, "bold"),
            bootstyle="inverse-primary"
        )
        title_lbl.pack(fill="x", pady=(0, 15), ipady=10)
        
        info_frame = ttk.Frame(popup, padding=10)
        info_frame.pack(fill="both", expand=True)

        info_text = f"Une mise à jour est disponible sur GitHub.\n\nVersion actuelle : {self.CURRENT_VERSION}\nNouvelle version : {new_version}"
        ttk.Label(info_frame, text=info_text, justify="center", font=("Segoe UI", 11)).pack(pady=5)

        btn_frame = ttk.Frame(popup, padding=(0, 0, 0, 20))
        btn_frame.pack(fill="x")

        def on_download():
            webbrowser.open(self.GITHUB_REPO_URL)
            popup.destroy()

        btn_yes = ttk.Button(btn_frame, text="Télécharger", bootstyle="success", command=on_download, width=15)
        btn_yes.pack(side="left", padx=(40, 10), expand=True)

        btn_no = ttk.Button(btn_frame, text="Plus tard", bootstyle="secondary", command=popup.destroy, width=15)
        btn_no.pack(side="right", padx=(10, 40), expand=True)
        
        popup.attributes('-topmost', True)
        popup.focus_force()

if __name__ == "__main__":
    try:
        app = LoLAssistant()
        app.root.mainloop()
    finally:
        remove_lockfile()