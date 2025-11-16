"""
MAIN LOL - Assistant pour League of Legends
------------------------------------------
Ce programme automatise plusieurs actions dans League of Legends :
- Acceptation automatique des parties
- Pré-pick (pré-sélection) du champion dès l'entrée en sélection
- Bannissement automatique (validation incluse)
- Sélection automatique par priorité (Pick 1, 2, 3)
- Sélection automatique des sorts (Spells) (configurable globalement)
- Sélection automatique de la page de runes (si le nom = nom du champion)
- Intégration avec Porofessor et OP.GG (avec override pseudo)
- WebSocket LCU optionnel (fallback polling)
- Timers/backoff dédiés par endpoint
- Anti-spam pour les notifications GameStart

Auteur: Qurnt1 (mis à jour par Gemini)
Version: 4.4 (Fix WebSocket Loop)
"""

# ───────────────────────────────────────────────────────────────────────────
# IMPORTS
# ───────────────────────────────────────────────────────────────────────────

import tkinter as tk
from tkinter import ttk as ttk_widget # Pour éviter conflit avec ttkbootstrap
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
import requests
import urllib3
import tempfile
import re
import unicodedata
from typing import Optional, Dict, Any, List, Tuple

# lcu_driver FACULTATIF: utilisé seulement si présent (WebSocket).
try:
    from lcu_driver import Connector  # noqa: F401
except Exception:
    Connector = None

# ───────────────────────────────────────────────────────────────────────────
# UTILITAIRES GENERAUX
# ───────────────────────────────────────────────────────────────────────────

def resource_path(relative_path: str) -> str:
    """
    Retourne le chemin absolu du fichier, compatible avec PyInstaller.
    Utilisé pour accéder aux ressources dans le dossier config/.
    """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

# Désactive les warnings d'HTTPS auto-signé pour l'API locale du client.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ───────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ───────────────────────────────────────────────────────────────────────────

PARAMETERS_PATH = resource_path("config/parameters.json")

DEFAULT_PARAMS = {
    "auto_accept_enabled": True,
    "auto_pick_enabled": True,
    "auto_ban_enabled": True,
    "auto_summoners_enabled": True, # Renommé (était auto_runes_enabled)
    "selected_pick_1": "Garen",
    "selected_pick_2": "Lux",
    "selected_pick_3": "Ashe",
    "selected_ban": "Teemo",
    "region": "euw",
    "theme": "darkly",
    
    # Override Pseudo
    "summoner_name_auto_detect": True,
    "manual_summoner_name": "VotrePseudo#EUW", 
    
    # NOUVEAU: Sorts Globaux (remplace les sorts par rôle)
    "global_spell_1": "Heal",
    "global_spell_2": "Flash",
}

REGION_LIST = ["euw", "eune", "na", "kr", "jp", "br", "lan", "las", "oce", "tr", "ru"]

# Map des sorts (CORRIGÉE v4.3)
SUMMONER_SPELL_MAP = {
    "Barrier": 21,
    "Cleanse": 1,
    "Exhaust": 3,
    "Flash": 4,
    "Ghost": 6,
    "Heal": 7,
    "Ignite": 14,
    "Smite": 11, 
    "Teleport": 12,
    "(Aucun)": 0  # IMPORTANT: Ré-ajouté pour la logique de doublons
}
SUMMONER_SPELL_LIST = sorted(list(SUMMONER_SPELL_MAP.keys()))


# Instance unique
LOCKFILE_PATH = os.path.join(tempfile.gettempdir(), 'main_lol.lock')

def check_single_instance():
    """Empêche d'ouvrir plusieurs instances de l'application (lock PID simple)."""
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
    """Supprime le lockfile à la fermeture."""
    try:
        if os.path.exists(LOCKFILE_PATH):
            os.remove(LOCKFILE_PATH)
    except Exception:
        pass

check_single_instance()

# ───────────────────────────────────────────────────────────────────────────
# MINI-CLIENT LCU (HTTP via requests)
# ───────────────────────────────────────────────────────────────────────────
class LCUHttpClient:
    """
    Client HTTP minimal pour l'API locale LCU.
    - Lecture du lockfile (port, mot de passe, protocole)
    - Session requests avec Basic Auth ('riot': password), verify=False
    - Méthodes GET/POST/PATCH avec retries + backoff exponentiel
    - Aucune fuite de mot de passe (ne jamais logger)
    """

    def __init__(self):
        self.base_url: Optional[str] = None
        self.session: Optional[requests.Session] = None
        self._password: Optional[str] = None
        self._port: Optional[int] = None
        self._protocol: str = "https"
        self.lockfile_path: Optional[str] = None
        self._last_lockfile_read: float = 0.0
        self._lock = Lock()

    def _find_lockfile_path(self) -> Optional[str]:
        """
        Tente de localiser le lockfile du client LoL.
        Méthode robuste : inspecter le processus LeagueClientUx.exe (Windows)
        et dériver le dossier. Fallbacks classiques fournis.
        """
        candidates = []
        for p in psutil.process_iter(['name', 'exe', 'cmdline']):
            name = (p.info.get('name') or '').lower()
            exe = p.info.get('exe') or ''
            if name in ("leagueclientux.exe", "leagueclient.exe"):
                if exe:
                    folder = os.path.dirname(exe)
                    candidates.append(os.path.join(folder, "lockfile"))
            if "LeagueClient.app" in exe:
                # Support Mac (approximatif)
                folder = os.path.join(exe, "..", "..", "LoL")
                candidates.append(os.path.normpath(os.path.join(folder, "lockfile")))

        default_paths = [
            r"C:\Riot Games\League of Legends\lockfile",
            os.path.expanduser("~/Applications/League of Legends.app/Contents/LoL/lockfile"),
            os.path.expanduser("~/Library/Application Support/League of Legends/lockfile"),
            os.path.expanduser("~/.local/share/League of Legends/lockfile"),
        ]
        candidates.extend(default_paths)

        for path in candidates:
            try:
                if os.path.exists(path):
                    return path
            except Exception:
                pass
        return None

    def _read_lockfile(self) -> bool:
        """
        Lit le lockfile pour configurer la session HTTP.
        Format: processName:PID:port:password:protocol
        """
        with self._lock:
            path = self._find_lockfile_path()
            if not path:
                return False
            try:
                with open(path, 'r') as f:
                    content = f.read().strip()
                parts = content.split(':')
                if len(parts) >= 5:
                    self._port = int(parts[2])
                    self._password = parts[3]
                    self._protocol = parts[4]
                    self.base_url = f"https://127.0.0.1:{self._port}"
                    self.session = requests.Session()
                    self.session.auth = ("riot", self._password)
                    self.session.verify = False
                    self.session.headers.update({
                        "Content-Type": "application/json",
                        "Accept": "application/json"
                    })
                    self.lockfile_path = path
                    self._last_lockfile_read = time()
                    return True
            except Exception:
                return False

    def ensure_ready(self, retry_seconds: float = 20.0) -> bool:
        """
        Tente d'initialiser la session en lisant le lockfile.
        Boucle jusqu'à retry_seconds au maximum. Renvoie True si prêt.
        """
        deadline = time() + retry_seconds
        while time() < deadline:
            if self._read_lockfile():
                return True
            sleep(0.5)
        return False

    def _request(self, method: str, path: str, **kwargs) -> Optional[requests.Response]:
        """
        Effectue une requête HTTP avec backoff. Ne log jamais le password.
        Retourne l'objet Response ou None si échec.
        """
        if not self.session or not self.base_url:
            if not self.ensure_ready(3.0):
                return None

        url = self.base_url + path
        timeout = kwargs.pop("timeout", 5.5)
        max_retries = kwargs.pop("max_retries", 4)
        backoff = kwargs.pop("backoff_start", 0.35)
        json_data = kwargs.pop("json", None)
        data = kwargs.pop("data", None)

        for _ in range(max_retries):
            try:
                resp = self.session.request(
                    method, url, 
                    timeout=timeout, 
                    json=json_data,
                    data=data,
                    **kwargs
                )
                if resp.status_code < 400:
                    return resp
                # Etats transitoires courants (pas notre tour, ressources non prêtes, etc.)
                if resp.status_code in (404, 409, 423) or 500 <= resp.status_code < 600:
                    sleep(backoff)
                    backoff = min(backoff * 2, 2.0)
                    continue
                # Autres codes: on renvoie quand même pour diagnostic
                return resp
            except requests.RequestException:
                sleep(backoff)
                backoff = min(backoff * 2, 2.0)
        return None

    def get_json(self, path: str, **kwargs) -> Optional[Any]:
        resp = self._request("GET", path, **kwargs)
        if not resp: return None
        try:
            return resp.json()
        except Exception:
            return None

    def post(self, path: str, json: Optional[dict] = None, **kwargs) -> Optional[requests.Response]:
        return self._request("POST", path, json=json, **kwargs)

    def patch(self, path: str, json: Optional[dict] = None, **kwargs) -> Optional[requests.Response]:
        return self._request("PATCH", path, json=json, **kwargs)

    def put(self, path: str, json: Optional[dict] = None, data: Optional[Any] = None, **kwargs) -> Optional[requests.Response]:
        return self._request("PUT", path, json=json, data=data, **kwargs)

# ───────────────────────────────────────────────────────────────────────────
# MINI-MODULE DATA DRAGON
# ───────────────────────────────────────────────────────────────────────────

class DataDragon:
    """
    Accès minimal à Data Dragon pour les champions :
    - Télécharge la table des champions une fois et la garde en mémoire.
    - Cache disque optionnel dans le dossier temp (pour démarrages suivants).
    - Fournit un resolve_champion(name_or_id) tolérant (accents/alias).
    """

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
        """Charge la table des champions depuis Data Dragon (ou cache)."""
        if self.loaded: return
        if self._load_from_cache(): return
        try:
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
            # Alias utiles
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
            # Fallback minimal hors-ligne
            basic = {"garen": 86, "teemo": 17, "ashe": 22, "lux": 99, "ezreal": 81}
            for n, cid in basic.items():
                self.by_norm_name[n] = cid
                self.by_id[cid] = {"name": n.title(), "key": str(cid)}
                self.name_by_id[cid] = n.title()
            self.version = "offline"
            self.all_names = sorted(list(self.name_by_id.values()))
            self.loaded = True

    def resolve_champion(self, name_or_id: Any) -> Optional[int]:
        """Convertit un nom ou un ID en championId (int). Tolérant aux accents/espaces."""
        self.load()
        if name_or_id is None: return None
        try:
            return int(name_or_id)
        except Exception:
            pass
        n = self._normalize(str(name_or_id))
        return self.by_norm_name.get(n)

    def id_to_name(self, cid: int) -> Optional[str]:
        self.load()
        return self.name_by_id.get(cid)

# ───────────────────────────────────────────────────────────────────────────
# FENETRE DES PARAMETRES (UI Simplifiée, sans onglets)
# ───────────────────────────────────────────────────────────────────────────

class SettingsWindow:
    """
    Fenêtre de configuration.
    (Simplifiée: sans onglets, sorts globaux)
    """
    def __init__(self, parent):
        self.parent = parent
        self.window = ttk.Toplevel(parent.root)
        self.window.title("Paramètres - MAIN LOL")
        self.window.geometry("550x560") # Ajustement taille
        self.window.resizable(False, False)
        
        img = Image.open(resource_path("./config/imgs/garen.webp")).resize((16, 16))
        photo = ImageTk.PhotoImage(img)
        self.window.iconphoto(False, photo)
        self.window._icon_img = photo
        
        # Variables d'état
        self.auto_var = tk.BooleanVar(value=parent.auto_accept_enabled)
        self.pick_var = tk.BooleanVar(value=parent.auto_pick_enabled)
        self.ban_var = tk.BooleanVar(value=parent.auto_ban_enabled)
        self.summ_var = tk.BooleanVar(value=parent.auto_summoners_enabled) # Renommé
        self.summ_auto_var = tk.BooleanVar(value=parent.summoner_name_auto_detect)
        self.summ_entry_var = tk.StringVar(value=parent.manual_summoner_name)

        # Listes
        try:
            self.parent.dd.load()
            self.all_champions = self.parent.dd.all_names
        except Exception as e:
            print(f"Erreur lors du chargement via DataDragon: {e}")
            self.all_champions = ["Garen", "Teemo", "Ashe"]
        
        self.champions = self.all_champions[:]
        self.spell_list = SUMMONER_SPELL_LIST[:]
        
        self.create_widgets()
        self.window.after(100, self.toggle_summoner_entry)
        self.window.after(1000, self._poll_summoner_label)
        
    def create_widgets(self):
        """Crée tous les widgets dans une seule frame (sans onglets)."""
        
        frame = ttk.Frame(self.window, padding=10)
        frame.pack(pady=10, padx=10, fill="both", expand=True)
        frame.columnconfigure(1, weight=1)

        # Auto-Accept (Row 0)
        ttk.Checkbutton(
            frame,
            text="Accepter automatiquement les parties",
            variable=self.auto_var,
            command=lambda: setattr(self.parent, 'auto_accept_enabled', self.auto_var.get()),
            bootstyle="success-round-toggle"
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=5)

        # Auto-Ban (Row 1)
        ttk.Checkbutton(
            frame, text="Auto-Ban", variable=self.ban_var,
            command=lambda: (
                setattr(self.parent, 'auto_ban_enabled', self.ban_var.get()),
                self.toggle_ban()
            ),
            bootstyle="warning-round-toggle"
        ).grid(row=1, column=0, sticky="w", padx=10, pady=5)
        
        self.ban_cb = ttk.Combobox(frame, values=self.champions, state="normal")
        self.ban_cb.set(getattr(self.parent, 'selected_ban', 'Teemo'))
        self.ban_cb.grid(row=1, column=1, sticky="we", padx=10)
        self.ban_cb.bind("<<ComboboxSelected>>", self._validate_champ_selection) # Modifié
        self.ban_cb.bind("<KeyRelease>", self._on_champ_search)
        self.ban_cb.bind("<FocusOut>", self._validate_champ_selection)
        
        # Auto-Pick (Rows 2-5)
        ttk.Checkbutton(
            frame, text="Auto-Pick (Priorité)", variable=self.pick_var,
            command=lambda: (
                setattr(self.parent, 'auto_pick_enabled', self.pick_var.get()),
                self.toggle_pick()
            ),
            bootstyle="info-round-toggle"
        ).grid(row=2, column=0, columnspan=2, sticky="w", padx=10, pady=(15, 5))

        ttk.Label(frame, text="Pick 1 :").grid(row=3, column=0, sticky="e", padx=(10, 5), pady=2)
        self.pick_cb_1 = ttk.Combobox(frame, values=self.champions, state="normal")
        self.pick_cb_1.set(getattr(self.parent, 'selected_pick_1', 'Garen'))
        self.pick_cb_1.grid(row=3, column=1, sticky="we", padx=10, pady=2)
        self.pick_cb_1.bind("<<ComboboxSelected>>", self._validate_champ_selection) # Modifié
        self.pick_cb_1.bind("<KeyRelease>", self._on_champ_search)
        self.pick_cb_1.bind("<FocusOut>", self._validate_champ_selection)

        ttk.Label(frame, text="Pick 2 :").grid(row=4, column=0, sticky="e", padx=(10, 5), pady=2)
        self.pick_cb_2 = ttk.Combobox(frame, values=self.champions, state="normal")
        self.pick_cb_2.set(getattr(self.parent, 'selected_pick_2', 'Lux'))
        self.pick_cb_2.grid(row=4, column=1, sticky="we", padx=10, pady=2)
        self.pick_cb_2.bind("<<ComboboxSelected>>", self._validate_champ_selection) # Modifié
        self.pick_cb_2.bind("<KeyRelease>", self._on_champ_search)
        self.pick_cb_2.bind("<FocusOut>", self._validate_champ_selection)

        ttk.Label(frame, text="Pick 3 :").grid(row=5, column=0, sticky="e", padx=(10, 5), pady=2)
        self.pick_cb_3 = ttk.Combobox(frame, values=self.champions, state="normal")
        self.pick_cb_3.set(getattr(self.parent, 'selected_pick_3', 'Ashe'))
        self.pick_cb_3.grid(row=5, column=1, sticky="we", padx=10, pady=2)
        self.pick_cb_3.bind("<<ComboboxSelected>>", self._validate_champ_selection) # Modifié
        self.pick_cb_3.bind("<KeyRelease>", self._on_champ_search)
        self.pick_cb_3.bind("<FocusOut>", self._validate_champ_selection)

        # NOUVEAU: Auto Summoners + Sorts Globaux (Rows 6-8)
        ttk.Checkbutton(
            frame, text="Auto Summoners (et Runes si nom = champ)", 
            variable=self.summ_var, # Renommé
            command=lambda: setattr(self.parent, 'auto_summoners_enabled', self.summ_var.get()),
            bootstyle="primary-round-toggle"
        ).grid(row=6, column=0, columnspan=2, sticky="w", padx=10, pady=(15, 5))
        
        ttk.Label(frame, text="Sort 1 :").grid(row=7, column=0, sticky="e", padx=(10, 5), pady=2)
        self.spell_cb_1 = ttk.Combobox(frame, values=self.spell_list, state="readonly", width=15)
        self.spell_cb_1.set(getattr(self.parent, 'global_spell_1'))
        self.spell_cb_1.grid(row=7, column=1, padx=10, pady=5, sticky="we")
        self.spell_cb_1.bind("<<ComboboxSelected>>", self._on_spell_selected) # AJOUT v4.3
        
        ttk.Label(frame, text="Sort 2 :").grid(row=8, column=0, sticky="e", padx=(10, 5), pady=2)
        self.spell_cb_2 = ttk.Combobox(frame, values=self.spell_list, state="readonly", width=15)
        self.spell_cb_2.set(getattr(self.parent, 'global_spell_2'))
        self.spell_cb_2.grid(row=8, column=1, padx=10, pady=5, sticky="we")
        self.spell_cb_2.bind("<<ComboboxSelected>>", self._on_spell_selected) # AJOUT v4.3

        # Région (Row 9)
        ttk.Label(frame, text="Région :", anchor="w").grid(row=9, column=0, sticky="w", padx=10, pady=5)
        self.region_var = tk.StringVar(value=self.parent.region)
        self.region_cb = ttk.Combobox(frame, values=REGION_LIST, textvariable=self.region_var, state="readonly")
        self.region_cb.grid(row=9, column=1, sticky="we", padx=10)
        self.region_cb.bind("<<ComboboxSelected>>", lambda e: setattr(self.parent, 'region', self.region_var.get()))

        # Override Pseudo (Rows 10-11)
        ttk.Checkbutton(
            frame, text="Détection auto du pseudo", variable=self.summ_auto_var,
            command=self.toggle_summoner_entry,
            bootstyle="success-round-toggle"
        ).grid(row=10, column=0, columnspan=2, sticky="w", padx=10, pady=(15, 5))
        
        ttk.Label(frame, text="Pseudo :", anchor="w").grid(row=11, column=0, sticky="w", padx=10, pady=5)
        self.summ_entry = ttk.Entry(frame, textvariable=self.summ_entry_var, state="readonly")
        self.summ_entry.grid(row=11, column=1, sticky="we", padx=10)

        # Bouton Fermer (en dehors de la frame)
        ttk.Button(
            self.window,
            text="Fermer",
            command=self.on_close,
            bootstyle="primary"
        ).pack(pady=(0, 15))
        
        self.toggle_pick()
        self.toggle_ban()
        self._on_spell_selected() # AJOUT v4.3: Appel initial pour filtrer les listes de sorts
            
    def toggle_summoner_entry(self):
        """Active/Désactive le champ de saisie du pseudo."""
        if self.summ_auto_var.get():
            self.summ_entry.configure(state="readonly")
            current_auto = self.parent._get_auto_summoner_name() or "(détection auto...)"
            self.summ_entry_var.set(current_auto)
        else:
            self.summ_entry.configure(state="normal")
            self.summ_entry_var.set(self.parent.manual_summoner_name)
            
    def toggle_pick(self):
        """Active/Désactive les listes de pick."""
        new_state = "normal" if self.pick_var.get() else "disabled"
        self.pick_cb_1.configure(state=new_state)
        self.pick_cb_2.configure(state=new_state)
        self.pick_cb_3.configure(state=new_state)
            
    def toggle_ban(self):
        """Active/Désactive la liste de ban."""
        new_state = "normal" if self.ban_var.get() else "disabled"
        self.ban_cb.configure(state=new_state)
            
    def _poll_summoner_label(self):
        """Met à jour le champ pseudo si en mode auto."""
        if not self.window.winfo_exists():
            return
        if self.summ_auto_var.get():
            current = self.parent._get_auto_summoner_name() or "(détection auto...)"
            if self.summ_entry_var.get() != current:
                self.summ_entry_var.set(current)
        self.window.after(1000, self._poll_summoner_label)

    def _on_champ_search(self, event):
        """Filtre la liste de la combobox ET la déroule automatiquement."""
        widget = event.widget
        current_text = widget.get().lower()

        if not current_text:
            widget['values'] = self.all_champions
            return # Ne pas dérouler si le champ est vide

        filtered_list = [
            champ for champ in self.all_champions 
            if champ.lower().startswith(current_text)
        ]
        
        # Sauvegarde le texte que l'utilisateur a tapé
        original_text = widget.get()
        
        # Met à jour la liste
        widget['values'] = filtered_list
        
        if filtered_list:
            # Ré-affiche le texte (car la mise à jour des values peut l'effacer)
            widget.set(original_text)
        else:
            # Si aucun résultat, vider la liste mais garder le texte
            widget.set(original_text)
            widget['values'] = [] # Vider la liste affichée

        # Force la liste à se dérouler
        try:
            # Commande Tcl pour forcer l'ouverture du menu déroulant
            widget.tk.call('ttk::combobox::PopdownWindow', str(widget))
        except tk.TclError:
            pass # Ignorer l'erreur si la fenêtre est déjà ouverte ou fermée
        
    def _validate_champ_selection(self, event):
        """Valide la sélection lors de la perte de focus ou d'un clic."""
        widget = event.widget
        current_text = widget.get()
        
        # Toujours réinitialiser la liste complète
        widget['values'] = self.all_champions
        
        # Vérifier si ce qui est écrit est un champion valide
        if current_text not in self.all_champions:
            # Si invalide, revenir à la valeur parente
            if widget == self.pick_cb_1: widget.set(self.parent.selected_pick_1)
            elif widget == self.pick_cb_2: widget.set(self.parent.selected_pick_2)
            elif widget == self.pick_cb_3: widget.set(self.parent.selected_pick_3)
            elif widget == self.ban_cb: widget.set(self.parent.selected_ban)
        else:
            # Si valide, sauvegarder la nouvelle valeur
            if widget == self.pick_cb_1: self.parent.selected_pick_1 = current_text
            elif widget == self.pick_cb_2: self.parent.selected_pick_2 = current_text
            elif widget == self.pick_cb_3: self.parent.selected_pick_3 = current_text
            elif widget == self.ban_cb: self.parent.selected_ban = current_text

    # NOUVELLE MÉTHODE pour gérer les doublons de sorts
    def _on_spell_selected(self, event=None):
        """Met à jour les listes de sorts pour éviter les doublons."""
        sel_1 = self.spell_cb_1.get()
        sel_2 = self.spell_cb_2.get()

        # Si les deux sont identiques (et pas "Aucun"), forcer le reset du 2e
        if sel_1 == sel_2 and sel_1 != "(Aucun)":
            sel_2 = "(Aucun)"
            self.spell_cb_2.set("(Aucun)")

        # Filtre pour CB1 : tout sauf sel_2 (sauf si c'est "(Aucun)")
        list_1 = [s for s in self.spell_list if s == sel_1 or (s != sel_2 or s == "(Aucun)")]
        self.spell_cb_1['values'] = list_1

        # Filtre pour CB2 : tout sauf sel_1 (sauf si c'est "(Aucun)")
        list_2 = [s for s in self.spell_list if s == sel_2 or (s != sel_1 or s == "(Aucun)")]
        self.spell_cb_2['values'] = list_2

    def on_close(self):
        """Sauvegarde tous les paramètres avant de fermer."""
        
        # Valider les champs de champion une dernière fois
        self._validate_champ_selection(type('Event', (object,), {'widget': self.pick_cb_1})())
        self._validate_champ_selection(type('Event', (object,), {'widget': self.pick_cb_2})())
        self._validate_champ_selection(type('Event', (object,), {'widget': self.pick_cb_3})())
        self._validate_champ_selection(type('Event', (object,), {'widget': self.ban_cb})())
        
        # Sauvegarde Picks/Ban (maintenant validés)
        self.parent.selected_pick_1 = self.pick_cb_1.get()
        self.parent.selected_pick_2 = self.pick_cb_2.get()
        self.parent.selected_pick_3 = self.pick_cb_3.get()
        self.parent.selected_ban = self.ban_cb.get()
        
        # Sauvegarde Auto Summoners
        self.parent.auto_summoners_enabled = self.summ_var.get()
        self.parent.global_spell_1 = self.spell_cb_1.get()
        self.parent.global_spell_2 = self.spell_cb_2.get()
        
        # Sauvegarde Pseudo
        self.parent.summoner_name_auto_detect = self.summ_auto_var.get()
        if not self.summ_auto_var.get():
            self.parent.manual_summoner_name = self.summ_entry_var.get()
            
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
        self.root.geometry("360x180")
        self.root.resizable(False, False)

        # Variables d'état
        self.running = True
        self.client_seen = False
        self.auto_accept_enabled = DEFAULT_PARAMS["auto_accept_enabled"]
        self.auto_pick_enabled = DEFAULT_PARAMS["auto_pick_enabled"]
        self.auto_ban_enabled = DEFAULT_PARAMS["auto_ban_enabled"]
        self.auto_summoners_enabled = DEFAULT_PARAMS["auto_summoners_enabled"] # Renommé
        self.region = DEFAULT_PARAMS["region"]
        self.platform_routing = "euw1"
        self.region_routing = "europe"
        
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
        self.assigned_position = "" # Rôle toujours détecté, mais plus utilisé pour les sorts

        # Timers
        self.last_game_start_notify_ts = 0.0
        self.game_start_cooldown = 12.0
        self._last_cs_session_fetch = 0.0
        self._last_cs_timer_fetch = 0.0
        self._cs_session_period = 0.7
        self._cs_timer_period = 0.30

        self.dd = DataDragon()
        self.dd.load() 
        self.lcu = LCUHttpClient()
        self._stop_event = Event()
        self.ws_active = False

        # Picks
        self.selected_pick_1 = DEFAULT_PARAMS["selected_pick_1"]
        self.selected_pick_2 = DEFAULT_PARAMS["selected_pick_2"]
        self.selected_pick_3 = DEFAULT_PARAMS["selected_pick_3"]
        self.selected_ban = DEFAULT_PARAMS["selected_ban"]
        
        # NOUVEAU: Sorts Globaux
        self.global_spell_1 = DEFAULT_PARAMS["global_spell_1"]
        self.global_spell_2 = DEFAULT_PARAMS["global_spell_2"]

        self.lol_version = "v0.0.0"
        self.theme_var = tk.StringVar(value=self.theme)
        self.load_config()

        try:
            pygame.mixer.init()
        except Exception:
            pass
        self.create_ui()
        self.create_system_tray()
        self.setup_hotkeys()
        self.lcu_thread = Thread(target=self._lcu_main_loop, daemon=True)
        self.lcu_thread.start()
        if Connector is not None:
            self.ws_thread = Thread(target=self._ws_loop, daemon=True)
            self.ws_thread.start()

    # ── Configuration (Mise à jour pour Sorts Globaux) ───────────

    def load_config(self):
        """Charge la configuration depuis parameters.json."""
        try:
            with open(PARAMETERS_PATH, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except Exception as e:
            print(f"Erreur lors du chargement de la configuration: {e}")
            print("Utilisation des valeurs par défaut")
            config = DEFAULT_PARAMS

        self.auto_accept_enabled = config.get('auto_accept_enabled', self.auto_accept_enabled)
        self.auto_pick_enabled = config.get('auto_pick_enabled', self.auto_pick_enabled)
        self.auto_ban_enabled = config.get('auto_ban_enabled', self.auto_ban_enabled)
        self.auto_summoners_enabled = config.get('auto_summoners_enabled', self.auto_summoners_enabled)
        
        old_pick = config.get('selected_pick', self.selected_pick_1)
        self.selected_pick_1 = config.get('selected_pick_1', old_pick)
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
        
        # NOUVEAU: Sorts Globaux
        self.global_spell_1 = config.get('global_spell_1', self.global_spell_1)
        self.global_spell_2 = config.get('global_spell_2', self.global_spell_2)

    def save_parameters(self):
        """Sauvegarde les paramètres dans parameters.json."""
        config = {
            "auto_accept_enabled": self.auto_accept_enabled,
            "auto_pick_enabled": self.auto_pick_enabled,
            "auto_ban_enabled": self.auto_ban_enabled,
            "auto_summoners_enabled": self.auto_summoners_enabled, # Renommé
            "selected_pick_1": self.selected_pick_1,
            "selected_pick_2": self.selected_pick_2,
            "selected_pick_3": self.selected_pick_3,
            "selected_ban": self.selected_ban,
            "region": self.region,
            "theme": self.theme_var.get(),
            
            "summoner_name_auto_detect": self.summoner_name_auto_detect,
            "manual_summoner_name": self.manual_summoner_name,
            "summoner": self.summoner,
            
            # NOUVEAU: Sorts Globaux
            "global_spell_1": self.global_spell_1,
            "global_spell_2": self.global_spell_2,
        }
        try:
            os.makedirs(os.path.dirname(PARAMETERS_PATH), exist_ok=True)
            with open(PARAMETERS_PATH, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            self.show_toast("Paramètres sauvegardés !")
        except Exception as e:
            print(f"Erreur lors de la sauvegarde: {e}")

    # ── UI (création inchangée) ───────────────────────────
    def create_ui(self):
        """Crée l'interface utilisateur principale (rendu inchangé)."""
        garen_icon = ImageTk.PhotoImage(
            Image.open(resource_path("./config/imgs/garen.webp")).resize((32, 32))
        )
        self.root.iconphoto(False, garen_icon)

        banner_img = ImageTk.PhotoImage(
            Image.open(resource_path("./config/imgs/garen.webp")).resize((48, 48))
        )
        self.banner_label = ttk.Label(self.root, image=banner_img)
        self.banner_label.image = banner_img
        self.banner_label.place(relx=0.5, rely=0.08, anchor="n")

        style = ttk.Style()
        style.configure("Status.TLabel", font=("Segoe UI", 12))

        self.connection_indicator = tk.Canvas(
            self.root,
            width=12, height=12, bd=0, highlightthickness=0, bg=self.root['bg']
        )
        self.connection_indicator.place(relx=0.05, rely=0.05, anchor="nw")
        self.update_connection_indicator(False)

        self.status_label = ttk.Label(
            self.root,
            text="🎮 En attente du client LoL...",
            style="Status.TLabel"
        )
        self.status_label.place(relx=0.5, rely=0.38, anchor="center")

        gear_img = ImageTk.PhotoImage(
            Image.open(resource_path("./config/imgs/gear.png")).resize((25, 30))
        )
        bg_color = self.root['bg']
        cog = tk.Canvas(
            self.root, width=30, height=30, bd=0, highlightthickness=0,
            bg=bg_color, cursor="hand2"
        )
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
        except Exception:
            pass

        def open_opgg():
            url = self.build_opgg_url()
            webbrowser.open(url)

        opgg_btn = ttk.Button(
            self.root,
            text="📊 OP.GG",
            bootstyle="success-outline-toolbutton",
            padding=10,
            command=open_opgg
        )
        opgg_btn.place(relx=0.5, rely=0.75, anchor="center")
        try:
            ToolTip(opgg_btn, text="Voir votre profil OP.GG")
        except Exception:
            pass

        self.root.protocol("WM_DELETE_WINDOW", self.root.withdraw)

    def create_system_tray(self):
        """Crée l'icône dans la barre système (inchangé)."""
        try:
            image = Image.open(resource_path("./config/imgs/garen.webp")).resize((64, 64))
            menu = pystray.Menu(
                pystray.MenuItem("Afficher/Masquer", self.toggle_window),
                pystray.MenuItem("Quitter", self.quit_app)
            )
            self.icon = pystray.Icon("MAIN LOL", image, "MAIN LOL", menu)
            Thread(target=self.icon.run, daemon=True).start()
        except Exception as e:
            print(f"Erreur lors de la création de l'icône système: {e}")

    def setup_hotkeys(self):
        """Configure les raccourcis clavier (inchangé)."""
        try:
            keyboard.add_hotkey('alt+p', self.open_porofessor)
            keyboard.add_hotkey('alt+c', self.toggle_window)
        except Exception as e:
            print(f"Erreur lors de la configuration des raccourcis: {e}")

    # ── Helpers URLs ──────────────────────────────────────────────────────

    def _platform_for_websites(self) -> str:
        """Mappe platform_routing (euw1, na1...) vers code court (euw, na...)."""
        mapping = {"euw1":"euw","eun1":"eune","na1":"na","kr":"kr","jp1":"jp","br1":"br","la1":"lan","la2":"las","oc1":"oce","tr1":"tr","ru":"ru"}
        return mapping.get((self.platform_routing or "").lower(), "euw")

    def _riot_url_name(self) -> str:
        """Construit le segment {Nom-Tag} pour les URLs publiques."""
        disp_name = self._riot_id_display_string() or ""
        if "#" in disp_name:
            left, right = disp_name.split("#", 1)
            if left and right: return f"{left}-{right}"
        return disp_name

    def build_opgg_url(self) -> str:
        platform = self._platform_for_websites()
        name_tag = urllib.parse.quote(self._riot_url_name())
        return f"https://www.op.gg/summoners/{platform}/{name_tag}"

    def build_porofessor_url(self) -> str:
        platform = self._platform_for_websites()
        name_tag = urllib.parse.quote(self._riot_url_name())
        return f"https://porofessor.gg/fr/live/{platform}/{name_tag}"

    def _riot_id_display_string(self) -> Optional[str]:
        """Retourne le pseudo à utiliser (auto ou manuel)"""
        if self.summoner_name_auto_detect:
            return self._get_auto_summoner_name()
        else:
            return self.manual_summoner_name or None
            
    def _get_auto_summoner_name(self) -> Optional[str]:
        """Retourne le pseudo détecté automatiquement."""
        if self.auto_game_name and self.auto_tag_line:
            return f"{self.auto_game_name}#{self.auto_tag_line}"
        return self.summoner or None

    # ── Actions UI ────────────────────────────────────────────────────────

    def open_porofessor(self):
        if self._riot_id_display_string():
            url = self.build_porofessor_url()
            webbrowser.open(url)

    def show_window(self, icon=None):
        if self.root.state() == 'withdrawn':
            self.root.after(0, self.root.deiconify)
            self.root.after(0, self.root.lift)

    def hide_window(self):
        if self.root.state() != 'withdrawn':
            self.root.after(0, self.root.withdraw)

    def toggle_window(self, icon=None):
        if self.root.state() == 'withdrawn': self.show_window()
        else: self.hide_window()

    def open_settings(self):
        SettingsWindow(self)

    def quit_app(self):
        """Arrête l'application proprement."""
        self.save_parameters() # Sauvegarde
        self.running = False
        self._stop_event.set()
        try:
            if hasattr(self, 'icon'): self.icon.stop()
        except Exception: pass
        self.root.quit()
        remove_lockfile() # Supprime le lock

    # ── Helpers UI ────────────────────────────────────────────────────────

    def update_status(self, message: str):
        """Met à jour le message de statut avec horodatage (thread-safe via after)."""
        now = datetime.now().strftime("%H:%M:%S")
        text = f"[{now}] {message}"
        # Affichage UI
        self.root.after(0, lambda: self.status_label.config(text=text))
        # Logs console pour debug
        print(text, flush=True)

    def update_connection_indicator(self, connected: bool):
        """Met à jour l'indicateur de connexion (pulsation si connecté)."""
        def _draw():
            self.connection_indicator.delete("all")
            color = "#00ff00" if connected else "#ff0000"
            # premier cercle statique
            self.connection_indicator.create_oval(2, 2, 10, 10, fill=color, outline="")
            if connected:
                def pulse(step=0):
                    if not self.connection_indicator.winfo_exists(): return
                    r = 4 + int(2 * abs((step % 20) - 10) / 10)
                    self.connection_indicator.delete("all")
                    self.connection_indicator.create_oval(6 - r, 6 - r, 6 + r, 6 + r, fill=color, outline="")
                    if self.running and self.client_seen:
                        self.connection_indicator.after(50, lambda: pulse(step + 1))
                    elif self.connection_indicator.winfo_exists():
                        # Assure que le point redevient rouge si déconnecté
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

    # ── Détection client LoL ────────────────────────────────────

    def _wait_for_client_process(self):
        """
        Attente (polling léger) du process LeagueClientUx.exe.
        """
        while self.running and not self._stop_event.is_set():
            try:
                alive = any(
                    (p.info.get('name') or "") == "LeagueClientUx.exe"
                    for p in psutil.process_iter(['name'])
                )
                if alive and not self.client_seen:
                    self.client_seen = True
                    self.update_status("✅ Client LoL détecté !")
                    self.update_connection_indicator(True)
                    self.root.after(3000, self.hide_window)
                    return True
                if not alive and self.client_seen:
                    self.client_seen = False
                    self.update_status("❌ Client LoL déconnecté")
                    self.update_connection_indicator(False)
                    self.root.after(0, self.quit_app)
                    return False
                sleep(1.0)
            except Exception as e:
                print(f"Erreur lors de la détection du client: {e}")
                sleep(1.0)
        return False

    # ── LCU: Récupération joueur + région ───────────────────

    def _refresh_player_and_region(self):
        """
        Récupère automatiquement:
        - Riot ID: gameName, tagLine (+ fallback displayName)
        - summonerId, puuid
        - platform routing (euw1, na1, kr...) et region routing (europe, americas, asia)
        """
        me = self.lcu.get_json("/lol-summoner/v1/current-summoner", timeout=5.0, max_retries=3)
        if isinstance(me, dict):
            self.auto_game_name = me.get("gameName") or self.auto_game_name
            self.auto_tag_line = me.get("tagLine") or self.auto_tag_line
            display = me.get("displayName") or me.get("name")
            if display: self.summoner = display # Stocke le legacy displayName
            # Fallback si gameName/tagLine absents (vieux comptes ?)
            if (not self.auto_game_name or not self.auto_tag_line) and isinstance(display, str) and "#" in display:
                left, right = display.split("#", 1)
                if left and right:
                    self.auto_game_name = self.auto_game_name or left
                    self.auto_tag_line = self.auto_tag_line or right
            self.summoner_id = me.get("summonerId") or self.summoner_id
            self.puuid = me.get("puuid") or self.puuid
            self.update_status(f"👤 Connecté en tant que {self._riot_id_display_string()}")

        reg = self.lcu.get_json("/riotclient/get_region_locale", timeout=3.0, max_retries=2) \
              or self.lcu.get_json("/riotclient/region-locale", timeout=3.0, max_retries=2)
        if isinstance(reg, dict):
            platform = (reg.get("platformId") or reg.get("region") or "").lower()
            if platform:
                self.platform_routing = platform
                self.region_routing = self._platform_to_region_routing(platform)
                self.update_status(f"🌍 Plateforme détectée : {self.platform_routing}")

    @staticmethod
    def _platform_to_region_routing(platform: str) -> str:
        """Map platformId -> region routing (europe/americas/asia)."""
        platform = platform.lower()
        if platform in {"euw1", "eun1", "tr1", "ru"}: return "europe"
        if platform in {"na1", "br1", "la1", "la2", "oc1"}: return "americas"
        if platform in {"kr", "jp1"}: return "asia"
        return "europe"

    # ── LCU: Boucle principale (polling) ──────────────────────────────────
    def _lcu_main_loop(self):
        if not self._wait_for_client_process(): return
        if not self.lcu.ensure_ready(30.0):
            self.update_status("❌ Impossible de lire le lockfile LCU")
            return
        
        self._refresh_player_and_region()
        
        phase_emojis = {"None":"🏠","Lobby":"🎮","Matchmaking":"🔍","ReadyCheck":"⏳","ChampSelect":"👑","GameStart":"🎯","InProgress":"⚔️","WaitingForStats":"📊","PreEndOfGame":"🏆","EndOfGame":"🎉"}
        last_phase = None
        last_accept_ts = 0.0

        while self.running and not self._stop_event.is_set():
            try:
                # Arrêt si client mort
                if not any((p.info.get('name') or "") == "LeagueClientUx.exe" for p in psutil.process_iter(['name'])):
                    if self.client_seen:
                        self.client_seen = False
                        self.update_status("❌ Client LoL déconnecté")
                        self.update_connection_indicator(False)
                        self.root.after(0, self.quit_app)
                    break
                
                # Si client vient de démarrer
                if not self.client_seen:
                    if not self._wait_for_client_process(): break
                        
                sleep_base = 0.9 if self.ws_active else 0.6

                phase = self.lcu.get_json("/lol-gameflow/v1/gameflow-phase", timeout=3.0, max_retries=2)
                if isinstance(phase, str):
                    self.current_phase = phase
                    if phase != last_phase:
                        emoji = phase_emojis.get(phase, "ℹ️")
                        self.update_status(f"{emoji} Phase : {phase}")
                        print(f"[PHASE] → {phase}", flush=True)
                        if phase == "ChampSelect": self._reset_between_games()
                        if phase in ("GameStart", "InProgress"): self._notify_game_start_once()
                        if phase in ("EndOfGame", "PreEndOfGame", "None"): self._reset_between_games()
                        last_phase = phase
                
                if self.auto_accept_enabled:
                    rc = self.lcu.get_json("/lol-matchmaking/v1/ready-check", timeout=2.0, max_retries=2)
                    if isinstance(rc, dict) and rc.get("state") == "InProgress":
                        if time() - last_accept_ts > 2.0:
                            r = self.lcu.post("/lol-matchmaking/v1/ready-check/accept", timeout=3.0, max_retries=2)
                            code = r.status_code if r else "NO_RESP"
                            self.update_status(f"✅ Partie acceptée automatiquement ! (HTTP {code})")
                            try: pygame.mixer.Sound(resource_path("config/son.wav")).play()
                            except Exception: pass
                            last_accept_ts = time()

                if self.current_phase == "ChampSelect":
                    now = time()
                    if now - self._last_cs_timer_fetch >= self._cs_timer_period:
                        self._champ_select_timer_tick()
                        self._last_cs_timer_fetch = now
                    if now - self._last_cs_session_fetch >= self._cs_session_period:
                        self._champ_select_tick()
                        self._last_cs_session_fetch = now
                
                sleep(sleep_base)
                
            except Exception as e:
                print(f"[LCU LOOP] Erreur: {e}", flush=True)
                sleep(1.0)

    def _notify_game_start_once(self):
        """Anti-spam: joue le son et toast GameStart au maximum toutes les X secondes."""
        now = time()
        if now - self.last_game_start_notify_ts >= self.game_start_cooldown:
            try: pygame.mixer.Sound(resource_path("config/son.wav")).play()
            except Exception: pass
            self.show_toast("🎯 Game Start !")
            self.update_status("🎯 Game Start détecté")
            self.last_game_start_notify_ts = now

    def _reset_between_games(self):
        """Réinitialise tous les flags/états entre les parties."""
        self.completed_actions.clear()
        self.has_picked = False
        self.has_banned = False
        self.intent_done = False
        self.assigned_position = ""
        self.last_action_try_ts = 0.0
        self.last_intent_try_ts = 0.0
        self._last_cs_session_fetch = 0.0
        self._last_cs_timer_fetch = 0.0
        print("[RESET] Flags internes remis à zéro.", flush=True)

    def _champ_select_timer_tick(self):
        """
        Récupère /lol-champ-select/v1/session/timer à fréquence élevée.
        """
        timer = self.lcu.get_json("/lol-champ-select/v1/session/timer", timeout=2.0, max_retries=2, backoff_start=0.15)
        if not isinstance(timer, dict):
            timer = self.lcu.get_json("/lol-champ-select-legacy/v1/session/timer", timeout=2.0, max_retries=2, backoff_start=0.15)

        if isinstance(timer, dict):
            phase = timer.get("phase") or timer.get("timerPhase") or ""
            remain = timer.get("phaseTimeRemaining") or timer.get("timeRemainingInPhase") \
                     or timer.get("adjustedTimeLeftInPhaseMs") or timer.get("totalTimeInPhase") \
                     or timer.get("timeLeftInPhase") or 0
            try:
                remain_sec = int(remain / 1000) if remain and remain > 1000 else int(remain)
            except Exception: remain_sec = 0
            self.update_status(f"👑 ChampSelect • Phase timer: {phase} • reste ~{remain_sec}s")

    # ── Boucle ChampSelect (Pick Prio) ───────
    def _champ_select_tick(self):
        """
        Itération ChampSelect robuste :
        - Pré-pick (Pick 1)
        - Auto-ban
        - Auto-pick (Pick 1, 2, 3) avec vérification de disponibilité
        """

        # --- Récupération session
        session = self.lcu.get_json("/lol-champ-select/v1/session", timeout=4.5, max_retries=3, backoff_start=0.25)
        if not isinstance(session, dict):
            session = self.lcu.get_json("/lol-champ-select-legacy/v1/session", timeout=4.5, max_retries=3, backoff_start=0.25)
            if not isinstance(session, dict):
                print("[CS] Session indisponible.", flush=True)
                return

        local_id = session.get("localPlayerCellId")
        if local_id is None:
            print("[CS] localPlayerCellId manquant.", flush=True)
            return

        # Détecte le rôle si pas déjà fait
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

        # ── AUTOPRÉPICK (Pick 1)
        pick_1_name = self.selected_pick_1
        if self.auto_pick_enabled and not self.intent_done and pick_1_name and my_pick_action:
            if time() - self.last_intent_try_ts > 0.45:
                cid = self.dd.resolve_champion(pick_1_name)
                if isinstance(cid, int):
                    current_cid = my_pick_action.get("championId", 0) or 0
                    if current_cid != cid:
                        url_v1 = f"/lol-champ-select/v1/session/actions/{my_pick_action['id']}"
                        url_legacy = f"/lol-champ-select-legacy/v1/session/actions/{my_pick_action['id']}"
                        r = self.lcu.patch(url_v1, json={"championId": cid}, timeout=3.0, max_retries=3, backoff_start=0.2)
                        if (not r) or r.status_code == 404:
                            r = self.lcu.patch(url_legacy, json={"championId": cid}, timeout=3.0, max_retries=3, backoff_start=0.2)
                        code = r.status_code if r else "NO_RESP"
                        cname = self.dd.id_to_name(cid) or str(cid)
                        if r and r.status_code < 400:
                            self.intent_done = True
                            self.update_status(f"🪄 Pré-pick (intention) sur {cname} (HTTP {code})")
                        else:
                            self.update_status(f"… Tentative de pré-pick refusée (HTTP {code})")
                    else:
                        self.intent_done = True
                else:
                    self.update_status(f"⚠️ Champion inconnu pour pré-pick: {pick_1_name}")
                self.last_intent_try_ts = time()

        if time() - self.last_action_try_ts < 0.28:
            return

        # ── AUTO-BAN
        if self.auto_ban_enabled and not self.has_banned and my_ban_action and self.selected_ban:
            if bool(my_ban_action.get("isInProgress")) is True:
                cid = self.dd.resolve_champion(self.selected_ban)
                if isinstance(cid, int):
                    self._perform_action_patch_then_complete(my_ban_action, cid, "BAN", self.selected_ban)
                else:
                    self.update_status(f"⚠️ Champion inconnu pour ban: {self.selected_ban}")

        # ── AUTO-PICK (Prio 1, 2, 3)
        if self.auto_pick_enabled and not self.has_picked and my_pick_action:
            if bool(my_pick_action.get("isInProgress")) is True:
                # Récupère la liste des champions pickables
                pickable_ids = self.lcu.get_json("/lol-champ-select/v1/pickable-champion-ids")
                if not isinstance(pickable_ids, list):
                    print("[CS] Impossible de récupérer les champions pickables.")
                    pickable_ids = []
                
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
                    self._perform_action_patch_then_complete(
                        my_pick_action, cid_to_pick, "PICK", cname_to_pick
                    )
                else:
                    self.update_status("⚠️ Aucun pick prioritaire n'est disponible.")

        self.last_action_try_ts = time()

    # ── Helpers ChampSelect ───────────────────────────────────────────────

    def _get_my_pending_actions(self, actions_groups: List[List[dict]], local_id: int) -> Tuple[Optional[dict], Optional[dict]]:
        """
        Retourne (prochaine_action_pick, prochaine_action_ban) qui nous appartiennent,
        et qui ne sont pas complétées.
        """
        my_pick, my_ban = None, None
        for group in actions_groups:
            for act in group:
                if act.get("actorCellId") != local_id or act.get("completed"): continue
                if act.get("type") == "ban" and my_ban is None: my_ban = act
                if act.get("type") == "pick" and my_pick is None: my_pick = act
        return my_pick, my_ban

    def _perform_action_patch_then_complete(self, action: dict, champion_id: int, action_kind: str, 
                                            champion_name: Optional[str] = None): # Arg 'position' retiré
        """
        Effectue l'action LCU standard en 2 étapes (PATCH puis POST /complete)
        """
        action_id = action.get("id")
        if not isinstance(action_id, int):
            print(f"[{action_kind}] Action sans id valide.", flush=True)
            return
        if action_id in self.completed_actions: return

        cname = champion_name or self.dd.id_to_name(champion_id) or str(champion_id)
        url_v1 = f"/lol-champ-select/v1/session/actions/{action_id}"
        url_legacy = f"/lol-champ-select-legacy/v1/session/actions/{action_id}"

        # Étape 1: assigner le champion sur l'action
        r1 = self.lcu.patch(url_v1, json={"championId": champion_id}, timeout=3.0, max_retries=5, backoff_start=0.2)
        if (not r1) or r1.status_code == 404:
            r1 = self.lcu.patch(url_legacy, json={"championId": champion_id}, timeout=3.0, max_retries=5, backoff_start=0.2)
        code1 = r1.status_code if r1 else "NO_RESP"
        self.update_status(f"[{action_kind}] Set {cname} → HTTP {code1}")
        if not (r1 and r1.status_code < 400): return

        sleep(0.08)

        # Étape 2: valider via POST /complete
        r2 = self.lcu.post(f"{url_v1}/complete", timeout=3.0, max_retries=4, backoff_start=0.2)
        if (not r2) or r2.status_code == 404:
            r2 = self.lcu.post(f"{url_legacy}/complete", timeout=3.0, max_retries=4, backoff_start=0.2)
        code2 = r2.status_code if r2 else "NO_RESP"
        self.update_status(f"[{action_kind}] Validate (POST /complete) → HTTP {code2}")

        if r2 and r2.status_code < 400:
            self.completed_actions.add(action_id)
            if action_kind == "BAN":
                self.has_banned = True
                self.update_status(f"🚫 {cname} banni automatiquement")
            elif action_kind == "PICK":
                self.has_picked = True
                self.update_status(f"👑 {cname} sélectionné automatiquement")
                if self.auto_summoners_enabled and champion_name:
                    self._set_spells_and_runes(champion_name) # Appel sans 'position'

    # ── Auto Spells & Runes (Mise à jour pour Sorts Globaux) ──────────────

    def _set_spells_and_runes(self, champion_name: str): # Arg 'position' retiré
        def task():
            try:
                self._set_spells() # Appel sans 'position'
                self._set_runes(champion_name)
            except Exception as e:
                print(f"[Runes/Spells] Erreur: {e}")
        Thread(target=task, daemon=True).start()

    def _set_spells(self): # Arg 'position' retiré
        """PATCH les sorts d'invocateur (globaux)."""
        
        # NOUVEAU: Utilise les sorts globaux
        spell1_name = self.global_spell_1
        spell2_name = self.global_spell_2
        
        spell1_id = self.SUMMONER_SPELL_MAP.get(spell1_name, 7) # Fallback Heal
        spell2_id = self.SUMMONER_SPELL_MAP.get(spell2_name, 4) # Fallback Flash
        
        payload = {"spell1Id": spell1_id, "spell2Id": spell2_id}
        r = self.lcu.patch("/lol-champ-select/v1/session/my-selection", json=payload, timeout=3.0)
        
        if r and r.status_code < 400:
            self.update_status(f"🪄 Sorts auto-sélectionnés ({spell1_name}, {spell2_name})")
        else:
            self.update_status(f"⚠️ Échec sélection auto des sorts (HTTP {r.status_code if r else 'NA'})")

    def _set_runes(self, champion_name: str):
        """Active la page de runes si le nom correspond."""
        all_pages = self.lcu.get_json("/lol-perks/v1/pages", timeout=4.0)
        if not isinstance(all_pages, list):
            self.update_status("⚠️ Impossible de lister les pages de runes.")
            return

        target_page = next((p for p in all_pages if p['name'].lower() == champion_name.lower()), None)
        if not target_page:
            self.update_status(f"ℹ️ Aucune page de runes nommée '{champion_name}' trouvée.")
            return
            
        page_id = target_page.get("id")
        if target_page.get("current"):
            self.update_status(f" runes '{champion_name}' déjà active.")
            return
            
        r = self.lcu.put(
            "/lol-perks/v1/currentpage", 
            data=str(page_id), 
            headers={"Content-Type": "application/json"},
            timeout=3.0
        )
        if r and r.status_code < 400:
            self.update_status(f" runes '{champion_name}' (ID {page_id}) activée !")
        else:
            self.update_status(f"⚠️ Échec activation page runes (HTTP {r.status_code if r else 'NA'})")

    # ── WebSocket (CORRIGÉ v4.4) ─────────────────────
    def _ws_loop(self):
        """
        Active un listener WebSocket si `lcu_driver` est installé.
        - Réagit instantanément aux phases, ready-check et champ select.
        - Fallback: si indisponible, on reste sur le polling HTTP.
        """
        if Connector is None: return
        try:
            # --- MODIFICATION v4.4 ---
            # Il faut créer et définir la boucle AVANT d'instancier le Connector
            # car le Connector en a besoin dès son initialisation.
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            # --------------------------

            connector = Connector()

            @connector.ready
            async def on_ready(connection):
                self.ws_active = True
                self.update_status("🔌 WebSocket LCU connecté (mode réactif).")

            @connector.close
            async def on_close(connection):
                self.ws_active = False
                self.update_status("🛑 WebSocket LCU fermé (retour au polling).")

            # Phase de jeu
            @connector.ws.register('/lol-gameflow/v1/gameflow-phase')
            async def _ws_phase(connection, event):
                phase = event.data
                self.current_phase = phase
                emoji = {"None":"🏠","Lobby":"🎮","Matchmaking":"🔍","ReadyCheck":"⏳","ChampSelect":"👑","GameStart":"🎯","InProgress":"⚔️","WaitingForStats":"📊","PreEndOfGame":"🏆","EndOfGame":"🎉"}.get(phase, "ℹ️")
                self.update_status(f"{emoji} Phase : {phase}")
                if phase == "ChampSelect":
                    self._reset_between_games()
                    self._champ_select_tick() # Tick immédiat
                if phase in ("GameStart", "InProgress"): self._notify_game_start_once()
                if phase in ("EndOfGame", "PreEndOfGame", "None"): self._reset_between_games()

            # Ready-check
            @connector.ws.register('/lol-matchmaking/v1/ready-check')
            async def _ws_ready(connection, event):
                data = event.data or {}
                if self.auto_accept_enabled and data.get('state') == 'InProgress':
                    await connection.request('post', '/lol-matchmaking/v1/ready-check/accept')
                    self.update_status("✅ Partie acceptée automatiquement (WS) !")
                    try: pygame.mixer.Sound(resource_path("config/son.wav")).play()
                    except Exception: pass

            # Champ select session -> tick immédiat
            @connector.ws.register('/lol-champ-select/v1/session')
            async def _ws_cs_session(connection, event):
                if time() - self._last_cs_session_fetch > 0.25:
                    self._champ_select_tick()
                    self._last_cs_session_fetch = time()

            # Champ select timer -> tick immédiat
            @connector.ws.register('/lol-champ-select/v1/session/timer')
            async def _ws_cs_timer(connection, event):
                if time() - self._last_cs_timer_fetch > 0.2:
                    self._champ_select_timer_tick()
                    self._last_cs_timer_fetch = time()
            
            # Lancement (loop est déjà créé et défini)
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