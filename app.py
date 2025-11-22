"""
MAIN LOL - Assistant pour League of Legends
------------------------------------------
Auteur: Qurnt1
Version: 5.0 (Fix UI Images & Crashs)
"""

# ───────────────────────────────────────────────────────────────────────────
# IMPORTS
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

# ───────────────────────────────────────────────────────────────────────────
# UTILITAIRES GENERAUX
# ───────────────────────────────────────────────────────────────────────────

def resource_path(relative_path: str) -> str:
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    
    if relative_path.startswith("./"):
        relative_path = relative_path[2:]
    elif relative_path.startswith(".\\"):
        relative_path = relative_path[2:]
        
    return os.path.join(base_path, relative_path)

def get_appdata_path(filename: str) -> str:
    app_data_dir = os.getenv('APPDATA') 
    app_folder = os.path.join(app_data_dir, "MainLoL")
    if not os.path.exists(app_folder):
        try:
            os.makedirs(app_folder)
        except OSError:
            return filename
    return os.path.join(app_folder, filename)

# ───────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ───────────────────────────────────────────────────────────────────────────

PARAMETERS_PATH = get_appdata_path("parameters.json")

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
    "manual_summoner_name": "VotrePseudo#EUW",
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

LOCKFILE_PATH = os.path.join(tempfile.gettempdir(), 'main_lol.lock')

def check_single_instance():
    if os.path.exists(LOCKFILE_PATH):
        try:
            with open(LOCKFILE_PATH, 'r') as f:
                pid = int(f.read())
            if pid != os.getpid() and psutil.pid_exists(pid):
                print("L'application est déjà en cours d'exécution.")
                sys.exit(0)
        except Exception:
            pass
    with open(LOCKFILE_PATH, 'w') as f:
        f.write(str(os.getpid()))

def remove_lockfile():
    try:
        if os.path.exists(LOCKFILE_PATH):
            os.remove(LOCKFILE_PATH)
    except Exception:
        pass

check_single_instance()

# ───────────────────────────────────────────────────────────────────────────
# DATA DRAGON (Champions + Sorts + Images)
# ───────────────────────────────────────────────────────────────────────────

class DataDragon:
    VERSIONS_URL = "https://ddragon.leagueoflegends.com/api/versions.json"
    CHAMP_LIST_URL_TPL = "https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/champion.json"
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

    @staticmethod
    def _normalize(s: str) -> str:
        s = s.strip().lower()
        s = unicodedata.normalize('NFD', s)
        s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
        s = re.sub(r"[^a-z0-9]+", "", s)
        return s

    def _load_from_cache(self) -> bool:
        try:
            if os.path.exists(self.CACHE_FILE):
                with open(self.CACHE_FILE, "r", encoding="utf-8") as f:
                    payload = json.load(f)
                self.version = payload.get("version")
                self.by_norm_name = {k: int(v) for k, v in payload.get("by_norm_name", {}).items()}
                self.by_id = {int(k): v for k, v in payload.get("by_id", {}).items()}
                self.name_by_id = {int(k): v for k, v in payload.get("name_by_id", {}).items()}
                self.all_names = sorted(list(self.name_by_id.values()))
                self.loaded = True
                return True
        except Exception:
            pass
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
        except Exception:
            pass

    def load(self):
        if self.loaded: return
        if self._load_from_cache(): return

        try:
            import requests
            versions = requests.get(self.VERSIONS_URL, timeout=5).json()
            version = versions[0]
            data = requests.get(self.CHAMP_LIST_URL_TPL.format(version=version), timeout=7).json()
            champs = data.get("data", {})
            for champ_slug, info in champs.items():
                champ_name = info.get("name") or champ_slug
                champ_id = int(info.get("key"))
                self.by_id[champ_id] = info
                self.name_by_id[champ_id] = champ_name
                self.by_norm_name[self._normalize(champ_name)] = champ_id
                self.by_norm_name[self._normalize(info.get("id", champ_slug))] = champ_id

            aliases = {"wukong": "monkeyking"}
            for k, v in aliases.items():
                nk, nv = self._normalize(k), self._normalize(v)
                if nv in self.by_norm_name:
                    self.by_norm_name[nk] = self.by_norm_name[nv]

            self.version = version
            self.all_names = sorted(list(self.name_by_id.values()))
            self.loaded = True
            self._save_cache()
        except Exception:
            # Mode hors ligne (fallback basique)
            basic = {"garen": 86, "teemo": 17, "ashe": 22, "lux": 99, "ezreal": 81}
            for n, cid in basic.items():
                self.by_norm_name[n] = cid
                self.by_id[cid] = {"name": n.title(), "key": str(cid)}
                self.name_by_id[cid] = n.title()
            self.version = "offline"
            self.all_names = sorted(list(self.name_by_id.values()))
            self.loaded = True

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

    def get_champion_icon(self, name_or_id) -> Optional[Image.Image]:
        cid = self.resolve_champion(name_or_id)
        if not cid: return None
        
        champ_data = self.by_id.get(cid)
        if not champ_data: return None
            
        image_filename = champ_data.get("image", {}).get("full")
        if not image_filename: return None

        cache_dir = os.path.join(tempfile.gettempdir(), "mainlol_icons")
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir, exist_ok=True)
            
        local_path = os.path.join(cache_dir, image_filename)

        if os.path.exists(local_path):
            try: return Image.open(local_path)
            except: pass

        url = f"https://ddragon.leagueoflegends.com/cdn/{self.version}/img/champion/{image_filename}"
        try:
            import requests
            from io import BytesIO
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                img_data = BytesIO(r.content)
                img = Image.open(img_data)
                with open(local_path, "wb") as f:
                    f.write(r.content)
                return img
        except Exception as e:
            print(f"Erreur DL image {image_filename}: {e}")
        return None

    def load_summoners(self):
        if self.summoner_loaded: return
        if not self.version: self.load() 

        url = f"https://ddragon.leagueoflegends.com/cdn/{self.version}/data/en_US/summoner.json"
        try:
            import requests
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                data = r.json().get("data", {})
                for key, info in data.items():
                    name = info.get("name")
                    image_full = info.get("image", {}).get("full")
                    if name and image_full:
                        self.summoner_data[name] = image_full
                self.summoner_loaded = True
        except Exception as e:
            print(f"Erreur loading summoners: {e}")

    def get_summoner_icon(self, spell_name) -> Optional[Image.Image]:
        if spell_name == "(Aucun)" or not spell_name: return None
        self.load_summoners()
        image_filename = self.summoner_data.get(spell_name)
        if not image_filename: return None

        cache_dir = os.path.join(tempfile.gettempdir(), "mainlol_spells")
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir, exist_ok=True)
            
        local_path = os.path.join(cache_dir, image_filename)

        if os.path.exists(local_path):
            try: return Image.open(local_path)
            except: pass

        url = f"https://ddragon.leagueoflegends.com/cdn/{self.version}/img/spell/{image_filename}"
        try:
            import requests
            from io import BytesIO
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                img_data = BytesIO(r.content)
                img = Image.open(img_data)
                with open(local_path, "wb") as f:
                    f.write(r.content)
                return img
        except Exception as e:
            print(f"Erreur DL spell {spell_name}: {e}")
        return None

# ───────────────────────────────────────────────────────────────────────────
# FENETRE DES PARAMETRES
# ───────────────────────────────────────────────────────────────────────────

class SettingsWindow:
    def __init__(self, parent):
        self.parent = parent
        self.window = ttk.Toplevel(parent.root)
        self.window.title("Paramètres - MAIN LOL")
        self.window.geometry("500x680") # Légèrement ajusté
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
        self.play_again_var = tk.BooleanVar(value=parent.auto_play_again_enabled)
        self.meta_runes_var = tk.BooleanVar(value=parent.auto_meta_runes_enabled)
        self.auto_hide_var = tk.BooleanVar(value=parent.auto_hide_on_connect)
        self.close_on_exit_var = tk.BooleanVar(value=parent.close_app_on_lol_exit)

        # Listes
        try:
            self.parent.dd.load()
            self.all_champions = self.parent.dd.all_names
        except Exception as e:
            print(f"Erreur DD load: {e}")
            self.all_champions = ["Garen", "Teemo", "Ashe"]

        self.champions = self.all_champions[:]
        self.spell_list = SUMMONER_SPELL_LIST[:]

        self.create_widgets()
        self.window.after(100, self.toggle_summoner_entry)
        self.window.after(1000, self._poll_summoner_label)

    def create_widgets(self):
        frame = ttk.Frame(self.window, padding=15)
        frame.pack(fill="both", expand=True)
        
        # CORRECTION UI : On donne du poids à la colonne 2 (Input) mais pas trop
        # Colonne 0 : Image (fixe)
        # Colonne 1 : Label (fixe, aligné droite)
        # Colonne 2 : Input (prend le reste, aligné gauche)
        frame.columnconfigure(0, weight=0)
        frame.columnconfigure(1, weight=0)
        frame.columnconfigure(2, weight=1) 

        # --- Auto-Accept ---
        ttk.Checkbutton(
            frame, text="Accepter automatiquement les parties", variable=self.auto_var,
            command=lambda: setattr(self.parent, 'auto_accept_enabled', self.auto_var.get()),
            bootstyle="success-round-toggle"
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=5)

        # --- Auto-Ban ---
        self.lbl_img_ban = ttk.Label(frame)
        self.lbl_img_ban.grid(row=1, column=0, padx=(0, 5), pady=5, sticky="e")

        ttk.Checkbutton(
            frame, text="Auto-Ban", variable=self.ban_var,
            command=lambda: (setattr(self.parent, 'auto_ban_enabled', self.ban_var.get()), self.toggle_ban()),
            bootstyle="danger-round-toggle"
        ).grid(row=1, column=1, sticky="w", padx=5, pady=5)

        self.ban_cb = ttk.Combobox(frame, values=self.champions, state="normal")
        self.ban_cb.set(getattr(self.parent, 'selected_ban', 'Teemo'))
        self.ban_cb.grid(row=1, column=2, sticky="ew", padx=(5, 0)) # "ew" pour étirer horizontalement
        self.ban_cb.bind("<<ComboboxSelected>>", self._validate_champ_selection)
        self.ban_cb.bind("<KeyRelease>", self._on_champ_search)
        self.ban_cb.bind("<FocusOut>", self._validate_champ_selection)
        # Bind clic gauche pour ouvrir direct si besoin
        self.ban_cb.bind("<Button-1>", lambda e: self.ban_cb.tk.call('ttk::combobox::PopdownWindow', str(self.ban_cb)))

        # --- Auto-Pick ---
        ttk.Checkbutton(
            frame, text="Auto-Pick (Priorité)", variable=self.pick_var,
            command=lambda: (setattr(self.parent, 'auto_pick_enabled', self.pick_var.get()), self.toggle_pick()),
            bootstyle="info-round-toggle"
        ).grid(row=2, column=0, columnspan=3, sticky="w", pady=(15, 5))

        # Pick 1
        self.lbl_img_p1 = ttk.Label(frame)
        self.lbl_img_p1.grid(row=3, column=0, padx=(0, 5), pady=3, sticky="e")
        ttk.Label(frame, text="Pick 1 :").grid(row=3, column=1, sticky="w", padx=5, pady=3)
        self.pick_cb_1 = ttk.Combobox(frame, values=self.champions, state="normal")
        self.pick_cb_1.set(getattr(self.parent, 'selected_pick_1', 'Garen'))
        self.pick_cb_1.grid(row=3, column=2, sticky="ew", padx=(5, 0))
        self.pick_cb_1.bind("<<ComboboxSelected>>", self._validate_champ_selection)
        self.pick_cb_1.bind("<KeyRelease>", self._on_champ_search)
        self.pick_cb_1.bind("<FocusOut>", self._validate_champ_selection)
        self.pick_cb_1.bind("<Button-1>", lambda e: self.pick_cb_1.tk.call('ttk::combobox::PopdownWindow', str(self.pick_cb_1)))

        # Pick 2
        self.lbl_img_p2 = ttk.Label(frame)
        self.lbl_img_p2.grid(row=4, column=0, padx=(0, 5), pady=3, sticky="e")
        ttk.Label(frame, text="Pick 2 :").grid(row=4, column=1, sticky="w", padx=5, pady=3)
        self.pick_cb_2 = ttk.Combobox(frame, values=self.champions, state="normal")
        self.pick_cb_2.set(getattr(self.parent, 'selected_pick_2', 'Lux'))
        self.pick_cb_2.grid(row=4, column=2, sticky="ew", padx=(5, 0))
        self.pick_cb_2.bind("<<ComboboxSelected>>", self._validate_champ_selection)
        self.pick_cb_2.bind("<KeyRelease>", self._on_champ_search)
        self.pick_cb_2.bind("<FocusOut>", self._validate_champ_selection)
        self.pick_cb_2.bind("<Button-1>", lambda e: self.pick_cb_2.tk.call('ttk::combobox::PopdownWindow', str(self.pick_cb_2)))

        # Pick 3
        self.lbl_img_p3 = ttk.Label(frame)
        self.lbl_img_p3.grid(row=5, column=0, padx=(0, 5), pady=3, sticky="e")
        ttk.Label(frame, text="Pick 3 :").grid(row=5, column=1, sticky="w", padx=5, pady=3)
        self.pick_cb_3 = ttk.Combobox(frame, values=self.champions, state="normal")
        self.pick_cb_3.set(getattr(self.parent, 'selected_pick_3', 'Ashe'))
        self.pick_cb_3.grid(row=5, column=2, sticky="ew", padx=(5, 0))
        self.pick_cb_3.bind("<<ComboboxSelected>>", self._validate_champ_selection)
        self.pick_cb_3.bind("<KeyRelease>", self._on_champ_search)
        self.pick_cb_3.bind("<FocusOut>", self._validate_champ_selection)
        self.pick_cb_3.bind("<Button-1>", lambda e: self.pick_cb_3.tk.call('ttk::combobox::PopdownWindow', str(self.pick_cb_3)))

        # --- Auto Summoners ---
        ttk.Checkbutton(
            frame, text="Auto Summoners", variable=self.summ_var,
            command=lambda: (setattr(self.parent, 'auto_summoners_enabled', self.summ_var.get()), self.toggle_spells()),
            bootstyle="warning-round-toggle"
        ).grid(row=6, column=0, columnspan=3, sticky="w", pady=(15, 5))

        # Sort 1
        ttk.Label(frame, text="Sort 1 :").grid(row=7, column=1, sticky="w", padx=5, pady=3)
        self.btn_spell_1 = ttk.Button(frame, text=self.parent.global_spell_1, bootstyle="secondary-outline")
        self.btn_spell_1.grid(row=7, column=2, sticky="ew", padx=(5, 0), pady=3)
        self.btn_spell_1.configure(command=lambda: self._open_spell_picker(1))

        # Sort 2
        ttk.Label(frame, text="Sort 2 :").grid(row=8, column=1, sticky="w", padx=5, pady=3)
        self.btn_spell_2 = ttk.Button(frame, text=self.parent.global_spell_2, bootstyle="secondary-outline")
        self.btn_spell_2.grid(row=8, column=2, sticky="ew", padx=(5, 0), pady=3)
        self.btn_spell_2.configure(command=lambda: self._open_spell_picker(2))

        # --- Auto Runes ---
        ttk.Checkbutton(
            frame, text="Auto Runes (via LCU)", variable=self.meta_runes_var,
            command=lambda: setattr(self.parent, 'auto_meta_runes_enabled', self.meta_runes_var.get()),
            bootstyle="primary-round-toggle"
        ).grid(row=9, column=0, columnspan=3, sticky="w", pady=(15, 5))

        # --- Pseudo & Region ---
        ttk.Checkbutton(
            frame, text="Détection auto (Pseudo & Région)", variable=self.summ_auto_var,
            command=self.toggle_summoner_entry, bootstyle="secondary-round-toggle"
        ).grid(row=11, column=0, columnspan=3, sticky="w", pady=(15, 5))

        ttk.Label(frame, text="Pseudo :", anchor="w").grid(row=12, column=0, columnspan=2, sticky="w", pady=5)
        self.summ_entry = ttk.Entry(frame, textvariable=self.summ_entry_var, state="readonly")
        self.summ_entry.grid(row=12, column=2, sticky="ew", padx=(5, 0))

        ttk.Label(frame, text="Région :", anchor="w").grid(row=13, column=0, columnspan=2, sticky="w", pady=5)
        self.region_var = tk.StringVar(value=self.parent.region)
        self.region_cb = ttk.Combobox(frame, values=REGION_LIST, textvariable=self.region_var, state="readonly")
        self.region_cb.grid(row=13, column=2, sticky="ew", padx=(5, 0))
        self.region_cb.bind("<<ComboboxSelected>>", lambda e: setattr(self.parent, 'region', self.region_var.get()))

        # --- Divers ---
        ttk.Separator(frame).grid(row=14, column=0, columnspan=3, sticky="we", pady=(15, 10))
        ttk.Checkbutton(
            frame, text="\"Retour au salon\" automatique", variable=self.play_again_var,
            command=lambda: setattr(self.parent, 'auto_play_again_enabled', self.play_again_var.get()),
            bootstyle="info-round-toggle"
        ).grid(row=15, column=0, columnspan=3, sticky="w", pady=2)

        ttk.Checkbutton(
            frame, text="Cacher l'application quand LoL est détecté", variable=self.auto_hide_var,
            command=lambda: setattr(self.parent, 'auto_hide_on_connect', self.auto_hide_var.get()),
            bootstyle="secondary-round-toggle"
        ).grid(row=16, column=0, columnspan=3, sticky="w", pady=2)

        ttk.Checkbutton(
            frame, text="Fermer l'application quand LoL se ferme", variable=self.close_on_exit_var,
            command=lambda: setattr(self.parent, 'close_app_on_lol_exit', self.close_on_exit_var.get()),
            bootstyle="danger-round-toggle"
        ).grid(row=17, column=0, columnspan=3, sticky="w", pady=2)

        ttk.Button(self.window, text="Fermer", command=self.on_close, bootstyle="primary").pack(pady=(0, 15))

        self.toggle_pick()
        self.toggle_ban()
        self.toggle_spells()
        self.toggle_summoner_entry()
        
        # Initialisation des images
        self._update_pick_image(self.pick_cb_1.get(), self.lbl_img_p1)
        self._update_pick_image(self.pick_cb_2.get(), self.lbl_img_p2)
        self._update_pick_image(self.pick_cb_3.get(), self.lbl_img_p3)
        self._update_pick_image(self.ban_cb.get(), self.lbl_img_ban)
        self._update_spell_btn_display(self.btn_spell_1, self.parent.global_spell_1)
        self._update_spell_btn_display(self.btn_spell_2, self.parent.global_spell_2)

    def _on_champ_search(self, event):
        """Gère la recherche ET l'exclusion du perso banni dans les picks."""
        widget = event.widget
        if event.keysym in ['Return', 'Tab', 'Up', 'Down']: return
        
        current_text = widget.get().lower()
        
        # CORRECTION 4 : Exclusion du perso banni dans les listes de Pick
        banned_champ = self.ban_cb.get()
        
        # On filtre : commence par le texte ET n'est pas le perso banni (si on est sur un pick)
        filtered_list = []
        for c in self.all_champions:
            # Si le widget est un Pick, on vérifie qu'il n'est pas banni
            is_banned = (widget != self.ban_cb and c == banned_champ)
            
            if c.lower().startswith(current_text) and not is_banned:
                filtered_list.append(c)

        widget['values'] = filtered_list

        # CORRECTION 3 : Force l'ouverture de la liste déroulante
        try:
            if filtered_list:
                widget.tk.call('ttk::combobox::PopdownWindow', str(widget))
            else:
                # Si vide, on peut fermer ou laisser vide
                pass
        except tk.TclError:
            pass

    # ... (Le reste des méthodes : toggle_summoner_entry, toggle_pick, etc. restent identiques au code précédent)
    # Copie-colle ici les autres méthodes : toggle_*, _validate_champ_selection, _update_pick_image, etc.
    # Elles n'ont pas besoin de changement majeur sauf si tu veux revoir _validate_champ_selection pour la propreté.
    
    def toggle_summoner_entry(self):
        if self.summ_auto_var.get():
            self.summ_entry.configure(state="readonly")
            self.region_cb.configure(state="disabled")
            self.summ_entry_var.set(self.parent._get_auto_summoner_name() or "(détection auto...)")
            auto_region = self.parent._platform_for_websites()
            self.region_var.set(auto_region)
            setattr(self.parent, 'region', auto_region)
        else:
            self.summ_entry.configure(state="normal")
            self.region_cb.configure(state="readonly")
            self.summ_entry_var.set(self.parent.manual_summoner_name)
            self.region_var.set(self.parent.region)

    def toggle_pick(self):
        state = "normal" if self.pick_var.get() else "disabled"
        self.pick_cb_1.configure(state=state)
        self.pick_cb_2.configure(state=state)
        self.pick_cb_3.configure(state=state)

    def toggle_ban(self):
        self.ban_cb.configure(state="normal" if self.ban_var.get() else "disabled")

    def toggle_spells(self):
        state = "normal" if self.summ_var.get() else "disabled"
        self.btn_spell_1.configure(state=state)
        self.btn_spell_2.configure(state=state)

    def _poll_summoner_label(self):
        if not self.window.winfo_exists(): return
        if self.summ_auto_var.get():
            current = self.parent._get_auto_summoner_name() or "(détection auto...)"
            if self.summ_entry_var.get() != current:
                self.summ_entry_var.set(current)
            auto_region = self.parent._platform_for_websites()
            if self.region_var.get() != auto_region:
                self.region_var.set(auto_region)
                setattr(self.parent, 'region', auto_region)
        self.window.after(1000, self._poll_summoner_label)

    def _validate_champ_selection(self, event):
        widget = event.widget
        current_text = widget.get()
        event_type = event.type if hasattr(event, 'type') else ''

        if str(event_type) == 'FocusOut' or event_type == '9':
            # On remet la liste complète (moins le ban si c'est un pick)
            banned = self.ban_cb.get()
            full_list = [c for c in self.all_champions if not (widget != self.ban_cb and c == banned)]
            widget['values'] = full_list

            if current_text not in self.all_champions:
                if widget == self.pick_cb_1: widget.set(self.parent.selected_pick_1)
                elif widget == self.pick_cb_2: widget.set(self.parent.selected_pick_2)
                elif widget == self.pick_cb_3: widget.set(self.parent.selected_pick_3)
                elif widget == self.ban_cb: 
                    widget.set(self.parent.selected_ban)
                    self._update_pick_image(self.parent.selected_ban, self.lbl_img_ban)
                current_text = widget.get()

        if widget in [self.pick_cb_1, self.pick_cb_2, self.pick_cb_3]:
            p1, p2, p3 = self.pick_cb_1.get(), self.pick_cb_2.get(), self.pick_cb_3.get()
            if widget == self.pick_cb_1:
                if current_text == p2 and p2: self.pick_cb_2.set("")
                if current_text == p3 and p3: self.pick_cb_3.set("")
            elif widget == self.pick_cb_2:
                if current_text == p1 and p1: self.pick_cb_1.set("")
                if current_text == p3 and p3: self.pick_cb_3.set("")
            elif widget == self.pick_cb_3:
                if current_text == p1 and p1: self.pick_cb_1.set("")
                if current_text == p2 and p2: self.pick_cb_2.set("")

            self.parent.selected_pick_1 = self.pick_cb_1.get()
            self.parent.selected_pick_2 = self.pick_cb_2.get()
            self.parent.selected_pick_3 = self.pick_cb_3.get()
            
            self._update_pick_image(self.pick_cb_1.get(), self.lbl_img_p1)
            self._update_pick_image(self.pick_cb_2.get(), self.lbl_img_p2)
            self._update_pick_image(self.pick_cb_3.get(), self.lbl_img_p3)
            
        elif widget == self.ban_cb:
            self.parent.selected_ban = current_text
            self._update_pick_image(current_text, self.lbl_img_ban)
            
            # Si on a banni un perso qui était sélectionné en pick, on clear le pick
            if self.pick_cb_1.get() == current_text: self.pick_cb_1.set(""); self._update_pick_image("", self.lbl_img_p1)
            if self.pick_cb_2.get() == current_text: self.pick_cb_2.set(""); self._update_pick_image("", self.lbl_img_p2)
            if self.pick_cb_3.get() == current_text: self.pick_cb_3.set(""); self._update_pick_image("", self.lbl_img_p3)

    def _update_pick_image(self, champ_name, label_widget):
        if not champ_name:
            label_widget.configure(image='')
            label_widget.image = None
            return
        def task():
            img_pil = self.parent.dd.get_champion_icon(champ_name)
            if img_pil:
                img_pil = img_pil.resize((30, 30), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img_pil)
                def ui():
                    if label_widget.winfo_exists():
                        label_widget.configure(image=photo)
                        label_widget.image = photo
                label_widget.after(0, ui)
        Thread(target=task, daemon=True).start()

    def _open_spell_picker(self, spell_slot_num):
        if not self.summ_var.get(): return
        picker = ttk.Toplevel(self.window)
        picker.title(f"Choisir Sort {spell_slot_num}")
        picker.geometry(f"320x300+{self.window.winfo_x() + 50}+{self.window.winfo_y() + 100}")
        picker.resizable(False, False)
        container = ttk.Frame(picker, padding=10)
        container.pack(fill="both", expand=True)

        def on_pick(spell_name):
            other_spell = self.parent.global_spell_2 if spell_slot_num == 1 else self.parent.global_spell_1
            if spell_name == other_spell and spell_name != "(Aucun)":
                if spell_slot_num == 1:
                    self.parent.global_spell_2 = "(Aucun)"
                    self._update_spell_btn_display(self.btn_spell_2, "(Aucun)")
                else:
                    self.parent.global_spell_1 = "(Aucun)"
                    self._update_spell_btn_display(self.btn_spell_1, "(Aucun)")

            if spell_slot_num == 1:
                self.parent.global_spell_1 = spell_name
                self._update_spell_btn_display(self.btn_spell_1, spell_name)
            else:
                self.parent.global_spell_2 = spell_name
                self._update_spell_btn_display(self.btn_spell_2, spell_name)
            picker.destroy()

        row, col = 0, 0
        for spell in self.spell_list:
            f = ttk.Frame(container)
            f.grid(row=row, column=col, padx=5, pady=5)
            btn = ttk.Button(f, bootstyle="link")
            btn.pack()
            self._load_img_into_btn(btn, spell, lambda s=spell: on_pick(s))
            try:
                from ttkbootstrap.tooltip import ToolTip
                ToolTip(btn, text=spell)
            except: pass
            col += 1
            if col > 3: 
                col = 0
                row += 1

    def _update_spell_btn_display(self, btn_widget, spell_name):
        btn_widget.configure(text=spell_name)
        def task():
            img_pil = self.parent.dd.get_summoner_icon(spell_name)
            if img_pil:
                img_pil = img_pil.resize((30, 30), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img_pil)
                def ui():
                    if btn_widget.winfo_exists():
                        btn_widget.configure(image=photo, text=f"  {spell_name}", compound="left") 
                        btn_widget.image = photo
                btn_widget.after(0, ui)
            else:
                def ui_clear():
                    if btn_widget.winfo_exists():
                        btn_widget.configure(image='', text=spell_name)
                btn_widget.after(0, ui_clear)
        Thread(target=task, daemon=True).start()

    def _load_img_into_btn(self, btn_widget, spell_name, callback):
        btn_widget.configure(command=callback)
        def task():
            img_pil = self.parent.dd.get_summoner_icon(spell_name)
            if img_pil:
                img_pil = img_pil.resize((48, 48), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img_pil)
                def ui():
                    if btn_widget.winfo_exists():
                        btn_widget.configure(image=photo)
                        btn_widget.image = photo
                btn_widget.after(0, ui)
            else:
                def ui_txt():
                    if btn_widget.winfo_exists():
                        btn_widget.configure(text=spell_name)
                btn_widget.after(0, ui_txt)
        Thread(target=task, daemon=True).start()

    def on_close(self):
        # Validation forcée
        self._validate_champ_selection(type('Event', (object,), {'widget': self.pick_cb_1, 'type': 'FocusOut'})())
        self._validate_champ_selection(type('Event', (object,), {'widget': self.pick_cb_2, 'type': 'FocusOut'})())
        self._validate_champ_selection(type('Event', (object,), {'widget': self.pick_cb_3, 'type': 'FocusOut'})())
        self._validate_champ_selection(type('Event', (object,), {'widget': self.ban_cb, 'type': 'FocusOut'})())

        self.parent.selected_pick_1 = self.pick_cb_1.get()
        self.parent.selected_pick_2 = self.pick_cb_2.get()
        self.parent.selected_pick_3 = self.pick_cb_3.get()
        self.parent.selected_ban = self.ban_cb.get()

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
# APPLICATION PRINCIPALE
# ───────────────────────────────────────────────────────────────────────────

class LoLAssistant:
    SUMMONER_SPELL_MAP = SUMMONER_SPELL_MAP

    def __init__(self):
        self.theme = DEFAULT_PARAMS["theme"]
        self.root = ttk.Window(themename=self.theme)
        self.root.title("MAIN LOL")
        self.root.geometry("380x180")
        self.root.resizable(False, False)

        # Variables d'état
        self.running = True
        self.auto_accept_enabled = DEFAULT_PARAMS["auto_accept_enabled"]
        self.auto_pick_enabled = DEFAULT_PARAMS["auto_pick_enabled"]
        self.auto_ban_enabled = DEFAULT_PARAMS["auto_ban_enabled"]
        self.auto_summoners_enabled = DEFAULT_PARAMS["auto_summoners_enabled"]
        self.region = DEFAULT_PARAMS["region"]
        self.platform_routing = "euw1"
        self.region_routing = "europe"
        self.auto_play_again_enabled = DEFAULT_PARAMS["auto_play_again_enabled"]
        self.auto_meta_runes_enabled = DEFAULT_PARAMS["auto_meta_runes_enabled"]
        self.auto_hide_on_connect = DEFAULT_PARAMS["auto_hide_on_connect"]
        self.close_app_on_lol_exit = DEFAULT_PARAMS["close_app_on_lol_exit"]
        self.settings_win = None # Variable pour stocker la référence de la fenêtre des paramètres

        # Logique de pseudo
        self.summoner = ""
        self.summoner_id: Optional[int] = None
        self.puuid: Optional[str] = None
        self.auto_game_name: Optional[str] = None
        self.auto_tag_line: Optional[str] = None
        self.manual_summoner_name: str = DEFAULT_PARAMS["manual_summoner_name"]
        self.summoner_name_auto_detect: bool = DEFAULT_PARAMS["summoner_name_auto_detect"]

        # Etats CS
        self.completed_actions: set[int] = set()
        self.has_picked = False
        self.has_banned = False
        self.intent_done = False
        self.last_action_try_ts = 0.0
        self.last_intent_try_ts = 0.0
        self.current_phase = "None"
        self.assigned_position = ""
        self.cs_tick_lock = asyncio.Lock()

        # Timers
        self.last_game_start_notify_ts = 0.0
        self.game_start_cooldown = 12.0
        self._last_cs_session_fetch = 0.0
        self._last_cs_timer_fetch = 0.0
        self._cs_session_period = 0.7
        self._cs_timer_period = 0.30
        self.has_played_accept_sound = False

        # Modules
        self.dd = DataDragon()
        self.dd.load()
        self._stop_event = Event()
        self.ws_active = False
        self.connection: Optional[Connector.connection] = None

        # Picks & Spells
        self.selected_pick_1 = DEFAULT_PARAMS["selected_pick_1"]
        self.selected_pick_2 = DEFAULT_PARAMS["selected_pick_2"]
        self.selected_pick_3 = DEFAULT_PARAMS["selected_pick_3"]
        self.selected_ban = DEFAULT_PARAMS["selected_ban"]
        self.global_spell_1 = DEFAULT_PARAMS["global_spell_1"]
        self.global_spell_2 = DEFAULT_PARAMS["global_spell_2"]

        self.lol_version = "v0.0.0"
        self.theme_var = tk.StringVar(value=self.theme)
        self.load_config()

        try:
            pygame.mixer.init()
            self.sound_effect = pygame.mixer.Sound(resource_path("config/son.wav"))
        except Exception as e:
            print(f"Erreur audio: {e}")
            self.sound_effect = None

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
        if not os.path.exists(PARAMETERS_PATH):
            config = DEFAULT_PARAMS
        else:
            try:
                with open(PARAMETERS_PATH, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except Exception:
                config = DEFAULT_PARAMS

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
        except Exception as e:
            print(f"Erreur lors de la sauvegarde: {e}")

    # ── UI ─────────────────────────────────────────────────────────────────

    def create_ui(self):
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
        try:
            from ttkbootstrap.tooltip import ToolTip
            ToolTip(cog, text="Paramètres")
        except: pass

        opgg_btn = ttk.Button(self.root, text="📊 OP.GG", bootstyle="success-outline", padding=(20, 10), width=15, command=lambda: webbrowser.open(self.build_opgg_url()))
        opgg_btn.place(relx=0.5, rely=0.75, anchor="center")
        try: ToolTip(opgg_btn, text="Voir votre profil OP.GG")
        except: pass

        self.root.protocol("WM_DELETE_WINDOW", self.root.withdraw)

    def create_system_tray(self):
        try:
            image = Image.open(resource_path("./config/imgs/garen.webp")).resize((64, 64))
            menu = pystray.Menu(
                pystray.MenuItem("Afficher/Masquer", self.toggle_window),
                pystray.MenuItem("Quitter", self.quit_app)
            )
            self.icon = pystray.Icon("MAIN LOL", image, "MAIN LOL", menu)
            Thread(target=self.icon.run, daemon=True).start()
        except Exception as e:
            print(f"Erreur tray: {e}")

    def setup_hotkeys(self):
        try:
            keyboard.add_hotkey('alt+p', self.open_porofessor)
            keyboard.add_hotkey('alt+c', self.toggle_window)
        except Exception: pass

    # ── Helpers URLs ──────────────────────────────────────────────────────

    def _platform_for_websites(self) -> str:
        mapping = {
            "euw1": "euw", "eun1": "eune", "na1": "na", "kr": "kr", "jp1": "jp",
            "br1": "br", "la1": "lan", "la2": "las", "oc1": "oce", "tr1": "tr", "ru": "ru"
        }
        if not self.summoner_name_auto_detect:
            return self.region.lower()
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

    # ── Actions UI ────────────────────────────────────────────────────────

    def open_porofessor(self):
        if self._riot_id_display_string(): webbrowser.open(self.build_porofessor_url())

    def show_window(self, icon=None):
        if self.root.state() == 'withdrawn':
            self.root.after(0, self.root.deiconify)
            self.root.after(0, self.root.lift)

    def hide_window(self, icon=None):
        if self.root.state() != 'withdrawn':
            self.root.after(0, self.root.withdraw)

    def toggle_window(self, icon=None):
        if self.root.state() == 'withdrawn': self.show_window()
        else: self.hide_window()

    def open_settings(self):
        # Si la fenêtre existe déjà et est ouverte, on la met au premier plan
        if self.settings_win and self.settings_win.window.winfo_exists():
            self.settings_win.window.lift()
            self.settings_win.window.focus_force()
            return
        
        # Sinon on la crée
        self.settings_win = SettingsWindow(self)

    def quit_app(self):
        self.save_parameters()
        self.running = False
        self._stop_event.set()
        try:
            if hasattr(self, 'icon'): self.icon.stop()
        except Exception: pass
        self.root.quit()
        remove_lockfile()

    # ── Helpers UI ────────────────────────────────────────────────────────

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
        except Exception: pass

    # ── LCU Logic ─────────────────────────────────────────────────────────

    async def _refresh_player_and_region(self):
        if not self.connection: return
        chat_me = None
        resp_chat = await self.connection.request('get', "/lol-chat/v1/me")
        if resp_chat.status == 200:
            chat_me = await resp_chat.json()
            
        if isinstance(chat_me, dict):
            self.auto_game_name = chat_me.get("gameName")
            self.auto_tag_line = chat_me.get("gameTag")
            if self.auto_game_name and self.auto_tag_line:
                self.summoner = f"{self.auto_game_name}#{self.auto_tag_line}"
            else:
                self.summoner = chat_me.get("name", "Inconnu")
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
        if resp_reg.status != 200:
            resp_reg = await self.connection.request('get', "/riotclient/region-locale")
        if resp_reg.status == 200: reg = await resp_reg.json()

        if isinstance(reg, dict):
            platform = (reg.get("platformId") or reg.get("region") or "").lower()
            if platform:
                self.platform_routing = platform
                self.region_routing = self._platform_to_region_routing(platform)
                if self.summoner_name_auto_detect:
                    self.region = self._platform_for_websites()

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
            try: pygame.mixer.Sound(resource_path("config/son.wav")).play()
            except Exception: pass
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
        print("[RESET] Flags internes remis à zéro.", flush=True)

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
            except Exception: remain_sec = 0
            self.update_status(f"👑 ChampSelect • Phase timer: {phase} • reste ~{remain_sec}s")

    async def _champ_select_tick(self):
        if not self.connection: return
        session = None
        resp_sess = await self.connection.request('get', "/lol-champ-select/v1/session")
        if resp_sess.status != 200: resp_sess = await self.connection.request('get', "/lol-champ-select-legacy/v1/session")
        if resp_sess.status == 200: session = await resp_sess.json()
        else: return

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

        # Auto Pick
        pick_1_name = self.selected_pick_1
        if self.auto_pick_enabled and not self.intent_done and pick_1_name and my_pick_action:
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
                    else:
                        self.intent_done = True
                self.last_intent_try_ts = time()

        if time() - self.last_action_try_ts < 0.28: return

        # Auto Ban
        if self.auto_ban_enabled and not self.has_banned and my_ban_action and self.selected_ban:
            if bool(my_ban_action.get("isInProgress")) is True:
                cid = self.dd.resolve_champion(self.selected_ban)
                if isinstance(cid, int):
                    await self._perform_action_patch_then_complete(my_ban_action, cid, "BAN", self.selected_ban)

        # Auto Pick Confirm
        if self.auto_pick_enabled and not self.has_picked and my_pick_action:
            if bool(my_pick_action.get("isInProgress")) is True:
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
                else:
                    self.update_status("⚠️ Aucun pick prioritaire n'est disponible.")

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

        r = await self.connection.request("patch", url_v1, json=payload)
        if r.status == 404: r = await self.connection.request("patch", url_legacy, json=payload)

        if not r or r.status >= 400: return
        self.completed_actions.add(action_id)

        if action_kind == "BAN":
            self.has_banned = True
            self.update_status(f"🚫 {cname} banni automatiquement")
        elif action_kind == "PICK":
            self.has_picked = True
            self.update_status(f"👑 {cname} sélectionné automatiquement")
            if (self.auto_summoners_enabled or self.auto_meta_runes_enabled) and champion_name:
                asyncio.create_task(self._set_spells_and_runes(champion_name))

    async def _set_spells_and_runes(self, champion_name: str):
        try:
            if self.auto_summoners_enabled: await self._set_spells()
            if self.auto_meta_runes_enabled: await self._set_runes(champion_name)
        except Exception as e:
            print(f"[Runes/Spells] Erreur: {e}")

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
                self.update_status(f"✅ Runes appliquées pour {champion_name} !")
        except Exception as e:
            print(f"[Runes] Erreur : {e}")

    async def _handle_post_game(self):
        if not self.auto_play_again_enabled: return
        for i in range(3):
            await asyncio.sleep(2)
            if self.current_phase not in ["EndOfGame", "WaitingForStats"]: break
            r = await self.connection.request('post', "/lol-lobby/v2/play-again")
            if r and r.status < 400:
                self.update_status("✅ Rejouer auto réussi !")
                break

    # ── WebSocket (Désormais obligatoire) ─────────────────────

    def _ws_loop(self):
        """
        Active un listener WebSocket (lcu_driver est requis).
        - Réagit instantanément aux phases, ready-check et champ select.
        """
        if Connector is None: return
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            connector = Connector()

            @connector.ready
            async def on_ready(connection):
                self.connection = connection  # Stocke la connexion
                self.ws_active = True
                self.update_connection_indicator(True)
                self.update_status("🔌 WebSocket LCU connecté (mode réactif).")
                await self._refresh_player_and_region()

                # Masquage automatique de la fenêtre après 3s si activé
                if self.auto_hide_on_connect:
                    self.root.after(3000, self.hide_window)

            @connector.close
            async def on_close(connection):
                self.connection = None
                self.ws_active = False
                self.update_connection_indicator(False)
                self.update_status("🛑 LoL déconnecté.")

                if self.close_app_on_lol_exit:
                    print("Fermeture automatique demandée.")
                    self.root.after(100, self.quit_app)
                else:
                    self.root.after(100, self.show_window)

            @connector.ws.register('/lol-login/v1/session')
            async def _ws_login_session(connection, event):
                data = event.data or {}
                if data.get('status') == "SUCCEEDED":
                    self.update_status("🔄 Changement de compte détecté. Mise à jour...")
                    await self._refresh_player_and_region()

            # Phase de jeu (C'est ici que tout se décide)
            @connector.ws.register('/lol-gameflow/v1/gameflow-phase')
            async def _ws_phase(connection, event):
                phase = event.data
                if not phase: return

                self.current_phase = phase
                emoji = {
                    "None": "🏠", "Lobby": "🎮", "Matchmaking": "🔍", "ReadyCheck": "⏳",
                    "ChampSelect": "👑", "GameStart": "🎯", "InProgress": "⚔️",
                    "WaitingForStats": "📊", "PreEndOfGame": "🏆", "EndOfGame": "🎉"
                }.get(phase, "ℹ️")
                self.update_status(f"{emoji} Phase : {phase}")

                if phase == "ChampSelect":
                    self._reset_between_games()
                    await self._champ_select_tick()

                if phase in ("GameStart", "InProgress"):
                    self._notify_game_start_once()

                if phase in ("EndOfGame", "PreEndOfGame", "None"):
                    self._reset_between_games()

                if phase in ("EndOfGame", "WaitingForStats"):
                    await self._handle_post_game()

            # Ready-check
            @connector.ws.register('/lol-matchmaking/v1/ready-check')
            async def _ws_ready(connection, event):
                if self.current_phase not in ["Matchmaking", "ReadyCheck", "None", "Lobby"]: return
                data = event.data or {}
                
                if self.auto_accept_enabled and data.get('state') == 'InProgress' and data.get('playerResponse') != 'Accepted':
                    await connection.request('post', '/lol-matchmaking/v1/ready-check/accept')
                    self.update_status("✅ Partie acceptée automatiquement (WS) !")
                    if not self.has_played_accept_sound:
                        self.has_played_accept_sound = True
                        try: pygame.mixer.Sound(resource_path("config/son.wav")).play()
                        except Exception: pass

            # Champ select session -> tick immédiat
            @connector.ws.register('/lol-champ-select/v1/session')
            async def _ws_cs_session(connection, event):
                if self.cs_tick_lock.locked(): return
                async with self.cs_tick_lock:
                    await self._champ_select_tick()

            # Champ select timer -> tick immédiat
            @connector.ws.register('/lol-champ-select/v1/session/timer')
            async def _ws_cs_timer(connection, event):
                if time() - self._last_cs_timer_fetch > 0.2:
                    await self._champ_select_timer_tick()
                    self._last_cs_timer_fetch = time()

            loop.run_until_complete(connector.start())

        except Exception as e:
            print(f"[WS] Erreur: {e}", flush=True)
            self.ws_active = False

    def toggle_theme(self):
        new_theme = self.theme_var.get()
        self.root.style.theme_use(new_theme)
        self.theme = new_theme
        self.save_parameters()


# ───────────────────────────────────────────────────────────────────────────
# POINT D'ENTREE
# ───────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        app = LoLAssistant()
        app.root.mainloop()
    finally:
        remove_lockfile()