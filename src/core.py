"""
MAIN LOL - Module Core (Logique Métier)
---------------------------------------
Contient DataDragon, WebSocketManager et la logique de jeu.
Ce module est agnostique de l'interface (pas d'import tkinter).
"""

import os
import re
import json
import asyncio
import logging
import unicodedata
from io import BytesIO
from time import time
from functools import lru_cache
from threading import Thread, Event, Lock
from typing import Optional, Dict, Any, List, Callable, Set

import requests
from PIL import Image

try:
    from lcu_driver import Connector
except ImportError:
    Connector = None

from .config import (
    URL_DD_VERSIONS, URL_DD_CHAMPIONS, URL_DD_SUMMONERS,
    URL_DD_IMG_CHAMP, URL_DD_IMG_SPELL, URL_DD_SPLASH,
    DDRAGON_CACHE_FILE, ICONS_CACHE_DIR, SPELLS_CACHE_DIR,
    EP_SESSION, EP_SESSION_TIMER, EP_GAMEFLOW, EP_READY_CHECK,
    EP_CURRENT_SUMMONER, EP_CHAT_ME, EP_LOGIN,
    SUMMONER_SPELL_MAP, PLATFORM_TO_REGION, PHASE_DISPLAY_MAP,
    get_cache_dirs
)


# ───────────────────────────────────────────────────────────────────────────
# DATA DRAGON
# ───────────────────────────────────────────────────────────────────────────

class DataDragon:
    """
    Gestionnaire des données Data Dragon (champions, sorts d'invocateur).
    Gère le cache local et le téléchargement des icônes.
    """
    
    def __init__(self):
        self.loaded: bool = False
        self.version: Optional[str] = None
        self.by_norm_name: Dict[str, int] = {}
        self.by_id: Dict[int, Dict[str, Any]] = {}
        self.name_by_id: Dict[int, str] = {}
        self.all_names: List[str] = []
        self.summoner_data: Dict[str, str] = {}
        self.summoner_loaded: bool = False
        self._image_cache: Dict[str, Image.Image] = {}
        self._cache_lock = Lock()
    
    @staticmethod
    def _normalize(s: str) -> str:
        """Normalise un nom pour la recherche (minuscules, sans accents, sans espaces)."""
        s = s.strip().lower()
        s = unicodedata.normalize('NFD', s)
        s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
        s = re.sub(r"[^a-z0-9]+", "", s)
        return s
    
    def _load_from_cache(self, target_version: Optional[str] = None) -> bool:
        """Charge les données depuis le cache local."""
        try:
            if os.path.exists(DDRAGON_CACHE_FILE):
                with open(DDRAGON_CACHE_FILE, "r", encoding="utf-8") as f:
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
        except Exception as e:
            logging.warning(f"DataDragon: Erreur cache - {e}")
        return False
    
    def _save_cache(self) -> None:
        """Sauvegarde les données dans le cache local."""
        try:
            with open(DDRAGON_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "version": self.version,
                    "by_norm_name": self.by_norm_name,
                    "by_id": self.by_id,
                    "name_by_id": self.name_by_id,
                }, f)
        except Exception as e:
            logging.warning(f"DataDragon: Erreur sauvegarde cache - {e}")
    
    def load(self) -> None:
        """Charge les données des champions depuis Data Dragon."""
        if self.loaded:
            return
        
        get_cache_dirs()  # S'assurer que les dossiers de cache existent
        
        online_version = None
        try:
            versions = requests.get(URL_DD_VERSIONS, timeout=5).json()
            online_version = versions[0]
        except Exception:
            pass
        
        if self._load_from_cache(target_version=online_version):
            return
        
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
            
            # Aliases pour champions avec noms alternatifs
            aliases = {"wukong": "monkeyking", "renata": "renataglasc"}
            for k, v in aliases.items():
                nk, nv = self._normalize(k), self._normalize(v)
                if nv in self.by_norm_name:
                    self.by_norm_name[nk] = self.by_norm_name[nv]
            
            self.version = online_version
            self.all_names = sorted(list(self.name_by_id.values()))
            self.loaded = True
            self._save_cache()
            
        except Exception as e:
            logging.error(f"DataDragon: Erreur chargement - {e}")
            # Fallback minimal
            basic = {"garen": 86, "teemo": 17, "ashe": 22, "lux": 99}
            for n, cid in basic.items():
                self.by_norm_name[n] = cid
                self.by_id[cid] = {"name": n.title(), "key": str(cid)}
                self.name_by_id[cid] = n.title()
            self.version = "offline"
            self.all_names = sorted(list(self.name_by_id.values()))
            self.loaded = True
    
    def resolve_champion(self, name_or_id: Any) -> Optional[int]:
        """Résout un nom ou ID de champion vers son ID numérique."""
        self.load()
        if name_or_id is None:
            return None
        try:
            return int(name_or_id)
        except (ValueError, TypeError):
            pass
        n = self._normalize(str(name_or_id))
        return self.by_norm_name.get(n)
    
    def id_to_name(self, cid: int) -> Optional[str]:
        """Convertit un ID de champion vers son nom."""
        self.load()
        return self.name_by_id.get(cid)
    
    def get_champion_icon(self, name_or_id: Any) -> Optional[Image.Image]:
        """
        Récupère l'icône d'un champion avec cache LRU.
        
        Args:
            name_or_id: Nom ou ID du champion
            
        Returns:
            Image PIL ou None si non trouvée
        """
        cid = self.resolve_champion(name_or_id)
        if not cid:
            return None
        
        # Vérifier le cache mémoire
        cache_key = f"champ_{cid}"
        with self._cache_lock:
            if cache_key in self._image_cache:
                return self._image_cache[cache_key].copy()
        
        champ_data = self.by_id.get(cid)
        if not champ_data:
            return None
        
        image_filename = champ_data.get("image", {}).get("full")
        if not image_filename:
            return None
        
        # Vérifier le cache fichier
        local_path = os.path.join(ICONS_CACHE_DIR, image_filename)
        if os.path.exists(local_path):
            try:
                img = Image.open(local_path)
                with self._cache_lock:
                    self._image_cache[cache_key] = img.copy()
                return img
            except Exception:
                pass
        
        # Télécharger
        url = URL_DD_IMG_CHAMP.format(version=self.version, filename=image_filename)
        try:
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                img = Image.open(BytesIO(r.content))
                with open(local_path, "wb") as f:
                    f.write(r.content)
                with self._cache_lock:
                    self._image_cache[cache_key] = img.copy()
                return img
        except Exception as e:
            logging.warning(f"DataDragon: Erreur téléchargement icône champion - {e}")
        return None
    
    def load_summoners(self) -> None:
        """Charge les données des sorts d'invocateur."""
        if self.summoner_loaded:
            return
        if not self.version:
            self.load()
        
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
        except Exception as e:
            logging.warning(f"DataDragon: Erreur chargement summoners - {e}")
    
    def get_summoner_icon(self, spell_name: str) -> Optional[Image.Image]:
        """
        Récupère l'icône d'un sort d'invocateur avec cache.
        
        Args:
            spell_name: Nom du sort
            
        Returns:
            Image PIL ou None si non trouvée
        """
        if spell_name == "(Aucun)" or not spell_name:
            return None
        
        # Vérifier le cache mémoire
        cache_key = f"spell_{spell_name}"
        with self._cache_lock:
            if cache_key in self._image_cache:
                return self._image_cache[cache_key].copy()
        
        self.load_summoners()
        image_filename = self.summoner_data.get(spell_name)
        if not image_filename:
            return None
        
        # Vérifier le cache fichier
        local_path = os.path.join(SPELLS_CACHE_DIR, image_filename)
        if os.path.exists(local_path):
            try:
                img = Image.open(local_path)
                with self._cache_lock:
                    self._image_cache[cache_key] = img.copy()
                return img
            except Exception:
                pass
        
        # Télécharger
        url = URL_DD_IMG_SPELL.format(version=self.version, filename=image_filename)
        try:
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                img = Image.open(BytesIO(r.content))
                with open(local_path, "wb") as f:
                    f.write(r.content)
                with self._cache_lock:
                    self._image_cache[cache_key] = img.copy()
                return img
        except Exception as e:
            logging.warning(f"DataDragon: Erreur téléchargement icône summoner - {e}")
        return None
    
    def get_splash_art(self, champion_name: str) -> Optional[Image.Image]:
        """
        Récupère le splash art d'un champion.
        
        Args:
            champion_name: Nom du champion
            
        Returns:
            Image PIL ou None si non trouvée
        """
        cid = self.resolve_champion(champion_name)
        if not cid:
            return None
        
        real_name = self.by_id[cid].get("id", champion_name)
        url = URL_DD_SPLASH.format(champion=real_name)
        
        try:
            response = requests.get(url, stream=True, timeout=5)
            if response.status_code == 200:
                return Image.open(BytesIO(response.content))
        except Exception as e:
            logging.warning(f"DataDragon: Erreur splash art - {e}")
        return None


# ───────────────────────────────────────────────────────────────────────────
# WEBSOCKET MANAGER
# ───────────────────────────────────────────────────────────────────────────

class GameState:
    """État du jeu partagé entre le WebSocket et l'UI."""
    
    def __init__(self):
        self.current_phase: str = "None"
        self.summoner: str = ""
        self.summoner_id: Optional[int] = None
        self.puuid: Optional[str] = None
        self.auto_game_name: Optional[str] = None
        self.auto_tag_line: Optional[str] = None
        self.platform_routing: str = "euw1"
        self.region_routing: str = "europe"
        self.assigned_position: str = ""
        
        # Flags d'actions
        self.has_picked: bool = False
        self.has_banned: bool = False
        self.intent_done: bool = False
        self.completed_actions: Set[int] = set()
        
        # Timestamps anti-spam
        self.last_action_try_ts: float = 0.0
        self.last_intent_try_ts: float = 0.0
        self.last_game_start_notify_ts: float = 0.0
        self._last_cs_session_fetch: float = 0.0
        self._last_cs_timer_fetch: float = 0.0
        self.has_played_accept_sound: bool = False
        self.last_reported_summoner: Optional[str] = None
    
    def reset_between_games(self) -> None:
        """Réinitialise l'état entre les parties."""
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


class WebSocketManager:
    """
    Gestionnaire WebSocket pour la communication avec le client LoL.
    Thread-safe: communique avec l'UI via callbacks uniquement.
    """
    
    # Types d'événements pour les callbacks UI
    EVENT_CONNECTED = "connected"
    EVENT_DISCONNECTED = "disconnected"
    EVENT_STATUS = "status"
    EVENT_PHASE_CHANGE = "phase_change"
    EVENT_SUMMONER_UPDATE = "summoner_update"
    EVENT_CHAMPION_PICKED = "champion_picked"
    EVENT_CHAMPION_BANNED = "champion_banned"
    EVENT_SPELLS_SET = "spells_set"
    EVENT_PLAY_AGAIN = "play_again"
    EVENT_TOAST = "toast"
    
    def __init__(
        self, 
        ui_callback: Callable[[str, Any], None],
        dd: DataDragon,
        get_params: Callable[[], Dict[str, Any]]
    ):
        """
        Initialise le WebSocketManager.
        
        Args:
            ui_callback: Fonction appelée pour notifier l'UI (thread-safe via root.after)
            dd: Instance de DataDragon
            get_params: Fonction retournant les paramètres actuels
        """
        self.ui_callback = ui_callback
        self.dd = dd
        self.get_params = get_params
        
        self.state = GameState()
        self.connection = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.ws_active: bool = False
        self._stop_event = Event()
        self._cs_tick_lock = asyncio.Lock()
        
        self.game_start_cooldown: float = 12.0
    
    def _notify_ui(self, event_type: str, data: Any = None) -> None:
        """Notifie l'UI d'un événement de manière thread-safe."""
        self.ui_callback(event_type, data)
    
    def start(self) -> None:
        """Démarre le thread WebSocket."""
        if Connector is None:
            self._notify_ui(self.EVENT_STATUS, ("❌ Erreur: 'lcu_driver' manquant.", ""))
            return
        
        thread = Thread(target=self._ws_loop, daemon=True)
        thread.start()
    
    def stop(self) -> None:
        """Arrête le WebSocket proprement."""
        self._stop_event.set()
    
    @property
    def is_active(self) -> bool:
        """Retourne True si le WebSocket est connecté."""
        return self.ws_active
    
    def get_riot_id(self) -> Optional[str]:
        """Retourne le Riot ID complet (GameName#TagLine)."""
        if self.state.auto_game_name and self.state.auto_tag_line:
            return f"{self.state.auto_game_name}#{self.state.auto_tag_line}"
        return self.state.summoner or None
    
    def get_platform_for_websites(self) -> str:
        """Retourne la région pour les URLs (op.gg, etc.)."""
        params = self.get_params()
        if not params.get("summoner_name_auto_detect", True):
            return params.get("region", "euw").lower()
        return PLATFORM_TO_REGION.get(
            (self.state.platform_routing or "").lower(), 
            "euw"
        )
    
    def force_refresh_summoner(self) -> None:
        """Force un rafraîchissement des données du joueur."""
        if self.ws_active and self.connection and self.loop:
            asyncio.run_coroutine_threadsafe(
                self._refresh_player_and_region(), 
                self.loop
            )
    
    def _ws_loop(self) -> None:
        """Boucle principale du WebSocket (exécutée dans un thread séparé)."""
        if Connector is None:
            return
        
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self.loop = loop
            connector = Connector()
            
            @connector.ready
            async def on_ready(connection):
                self.connection = connection
                self.ws_active = True
                self._notify_ui(self.EVENT_CONNECTED, None)
                self._notify_ui(self.EVENT_STATUS, ("Client LoL détecté ! Prêt à vous aider.", "⚡"))
                logging.info("WebSocket: Connecté au client LCU.")
                await self._refresh_player_and_region()
            
            @connector.close
            async def on_close(connection):
                self.connection = None
                self.ws_active = False
                self._notify_ui(self.EVENT_DISCONNECTED, None)
                self._notify_ui(self.EVENT_STATUS, ("LoL fermé. En attente...", "💤"))
                self.state.last_reported_summoner = None
                logging.info("WebSocket: Déconnecté.")
            
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
                    self._notify_ui(self.EVENT_STATUS, ("Login détecté...", "🔄"))
                    await self._refresh_player_and_region()
            
            @connector.ws.register(EP_GAMEFLOW)
            async def _ws_phase(connection, event):
                phase = event.data
                if not phase:
                    return
                
                if phase != self.state.current_phase:
                    logging.info(f"Phase changée : {self.state.current_phase} -> {phase}")
                self.state.current_phase = phase
                
                friendly_phase = PHASE_DISPLAY_MAP.get(phase, phase)
                self._notify_ui(self.EVENT_PHASE_CHANGE, phase)
                self._notify_ui(self.EVENT_STATUS, (f"Statut : {friendly_phase}", "ℹ️"))
                
                if phase == "ChampSelect":
                    self.state.reset_between_games()
                    await self._champ_select_tick()
                if phase in ("EndOfGame", "WaitingForStats"):
                    await self._handle_post_game()
            
            @connector.ws.register(EP_READY_CHECK)
            async def _ws_ready(connection, event):
                if self.state.current_phase not in ["Matchmaking", "ReadyCheck", "None", "Lobby"]:
                    return
                data = event.data or {}
                params = self.get_params()
                if (params.get("auto_accept_enabled", True) and 
                    data.get('state') == 'InProgress' and 
                    data.get('playerResponse') != 'Accepted'):
                    await connection.request('post', f'{EP_READY_CHECK}/accept')
                    self._notify_ui(self.EVENT_STATUS, ("Partie acceptée !", "✅"))
            
            @connector.ws.register(EP_SESSION)
            async def _ws_cs_session(connection, event):
                if self._cs_tick_lock.locked():
                    return
                async with self._cs_tick_lock:
                    await self._champ_select_tick()
            
            @connector.ws.register(EP_SESSION_TIMER)
            async def _ws_cs_timer(connection, event):
                if time() - self.state._last_cs_timer_fetch > 0.2:
                    await self._champ_select_timer_tick()
                    self.state._last_cs_timer_fetch = time()
            
            loop.run_until_complete(connector.start())
            
        except Exception as e:
            logging.critical(f"[WS] Erreur critique dans la boucle WebSocket : {e}", exc_info=True)
            self.ws_active = False
            self._notify_ui(self.EVENT_DISCONNECTED, None)
    
    async def _refresh_player_and_region(self) -> None:
        """Rafraîchit les données du joueur connecté."""
        if not self.connection:
            return
        
        chat_me = None
        resp_chat = await self.connection.request('get', "/lol-chat/v1/me")
        if resp_chat.status == 200:
            chat_me = await resp_chat.json()
        
        if isinstance(chat_me, dict):
            self.state.auto_game_name = chat_me.get("gameName")
            self.state.auto_tag_line = chat_me.get("gameTag")
            if self.state.auto_game_name and self.state.auto_tag_line:
                self.state.summoner = f"{self.state.auto_game_name}#{self.state.auto_tag_line}"
            else:
                self.state.summoner = chat_me.get("name", "Inconnu")
            self.state.summoner_id = chat_me.get("summonerId")
            self.state.puuid = chat_me.get("puuid")
        else:
            resp_me = await self.connection.request('get', "/lol-summoner/v1/current-summoner")
            if resp_me.status == 200:
                me = await resp_me.json()
                self.state.summoner = me.get("displayName", "Inconnu")
        
        # Anti-spam log
        if self.state.summoner != self.state.last_reported_summoner:
            self._notify_ui(self.EVENT_SUMMONER_UPDATE, self.get_riot_id())
            self._notify_ui(self.EVENT_STATUS, (f"Connecté : {self.get_riot_id()}", "👤"))
            self.state.last_reported_summoner = self.state.summoner
        
        # Région
        reg = None
        resp_reg = await self.connection.request('get', "/riotclient/get_region_locale")
        if resp_reg.status != 200:
            resp_reg = await self.connection.request('get', "/riotclient/region-locale")
        if resp_reg.status == 200:
            reg = await resp_reg.json()
        
        if isinstance(reg, dict):
            platform = (reg.get("platformId") or reg.get("region") or "").lower()
            if platform:
                self.state.platform_routing = platform
                self.state.region_routing = self._platform_to_region_routing(platform)
    
    @staticmethod
    def _platform_to_region_routing(platform: str) -> str:
        """Convertit un platformId en region routing."""
        platform = platform.lower()
        if platform in {"euw1", "eun1", "tr1", "ru"}:
            return "europe"
        if platform in {"na1", "br1", "la1", "la2", "oc1"}:
            return "americas"
        if platform in {"kr", "jp1"}:
            return "asia"
        return "europe"
    
    async def _champ_select_timer_tick(self) -> None:
        """Tick du timer de sélection des champions."""
        if not self.connection:
            return
        
        timer = None
        resp = await self.connection.request('get', "/lol-champ-select/v1/session/timer")
        if resp.status != 200:
            resp = await self.connection.request('get', "/lol-champ-select-legacy/v1/session/timer")
        if resp.status == 200:
            timer = await resp.json()
        
        # Timer info available but not actively used in current version

    async def _champ_select_tick(self) -> None:
        """Tick principal de la sélection des champions."""
        if not self.connection:
            return
        
        try:
            resp = await self.connection.request('get', "/lol-champ-select/v1/session")
            if resp.status != 200:
                return
            session = await resp.json()
        except Exception:
            return
        
        # Ignorer ARAM/modes avec bench
        if session.get("benchEnabled") is True:
            return
        
        local_id = session.get("localPlayerCellId")
        if local_id is None:
            return
        
        params = self.get_params()
        
        # Détection du rôle assigné
        if not self.state.assigned_position:
            my_team = session.get("myTeam", [])
            my_player_obj = next((p for p in my_team if p.get("cellId") == local_id), None)
            if my_player_obj:
                pos = (my_player_obj.get("assignedPosition") or "").upper()
                if pos:
                    self.state.assigned_position = pos
                    self._notify_ui(self.EVENT_STATUS, (f"Rôle assigné détecté : {pos}", "ℹ️"))
        
        # Récupérer mes actions
        actions_groups = session.get("actions", [])
        my_actions = []
        for group in actions_groups:
            for action in group:
                if action.get("actorCellId") == local_id and not action.get("completed"):
                    my_actions.append(action)
        
        # PRE-PICK (hover)
        if params.get("auto_pick_enabled") and params.get("selected_pick_1"):
            pick_action = next((a for a in my_actions if a.get("type") == "pick"), None)
            if pick_action:
                target_cid = self.dd.resolve_champion(params.get("selected_pick_1"))
                current_hover = pick_action.get("championId")
                if target_cid and target_cid != 0 and current_hover != target_cid:
                    if time() - self.state.last_intent_try_ts > 0.5:
                        await self._hover_champion(pick_action["id"], target_cid)
                        self.state.last_intent_try_ts = time()
        
        # ACTIONS (BAN & PICK)
        active_action = next((a for a in my_actions if a.get("isInProgress") is True), None)
        
        if active_action:
            action_type = active_action.get("type")
            
            if action_type == "ban" and params.get("auto_ban_enabled"):
                await self._logic_do_ban(active_action, params)
            
            elif action_type == "pick" and params.get("auto_pick_enabled"):
                await self._logic_do_pick(active_action, params)
    
    async def _hover_champion(self, action_id: int, champion_id: int) -> None:
        """Survole (hover) un champion."""
        url = f"/lol-champ-select/v1/session/actions/{action_id}"
        await self.connection.request('patch', url, json={"championId": champion_id})
    
    async def _logic_do_ban(self, action: Dict[str, Any], params: Dict[str, Any]) -> None:
        """Logique de ban automatique."""
        selected_ban = params.get("selected_ban")
        if not selected_ban:
            return
        if time() - self.state.last_action_try_ts < 0.1:
            return
        self.state.last_action_try_ts = time()
        
        cid = self.dd.resolve_champion(selected_ban)
        if not cid:
            return
        
        success = await self._lock_in_champion(action["id"], cid)
        if success:
            self.state.has_banned = True
            self._notify_ui(self.EVENT_CHAMPION_BANNED, selected_ban)
            self._notify_ui(self.EVENT_STATUS, (f"Ciao ! {selected_ban} a été banni.", "💀"))
    
    async def _logic_do_pick(self, action: Dict[str, Any], params: Dict[str, Any]) -> None:
        """Logique de pick automatique avec fallback."""
        if time() - self.state.last_action_try_ts < 0.1:
            return
        self.state.last_action_try_ts = time()
        
        pickable_ids = []
        try:
            r = await self.connection.request('get', "/lol-champ-select/v1/pickable-champion-ids")
            if r.status == 200:
                pickable_ids = await r.json()
        except Exception:
            pass
        
        pickable_set = set(pickable_ids) if pickable_ids else set()
        is_list_empty = len(pickable_set) == 0
        
        picks = [
            params.get("selected_pick_1"),
            params.get("selected_pick_2"),
            params.get("selected_pick_3")
        ]
        
        for name in picks:
            if not name:
                continue
            cid = self.dd.resolve_champion(name)
            if not cid:
                continue
            
            should_try = (cid in pickable_set) or is_list_empty
            
            if should_try:
                success = await self._lock_in_champion(action["id"], cid)
                if success:
                    self.state.has_picked = True
                    self._notify_ui(self.EVENT_CHAMPION_PICKED, name)
                    self._notify_ui(self.EVENT_STATUS, (f"{name} sécurisé ! À toi de jouer.", "🔒"))
                    
                    if params.get("auto_summoners_enabled"):
                        asyncio.create_task(self._set_spells(params))
                    
                    return
        
        self._notify_ui(self.EVENT_STATUS, ("Aucun champion dispo ou configuré (ou tous bannis) !", "⚠️"))
    
    async def _lock_in_champion(self, action_id: int, champion_id: int) -> bool:
        """Verrouille un champion (double méthode pour robustesse)."""
        url_action = f"/lol-champ-select/v1/session/actions/{action_id}"
        
        # 1. Sélectionner (Hover)
        await self.connection.request('patch', url_action, json={"championId": champion_id})
        
        # 2. Pause technique
        await asyncio.sleep(0.05)
        
        # 3. Méthode 1: completed: True dans PATCH
        await self.connection.request('patch', url_action, json={"championId": champion_id, "completed": True})
        
        # 4. Méthode 2: POST complete
        r = await self.connection.request('post', f"{url_action}/complete")
        
        return r.status < 400
    
    async def _set_spells(self, params: Dict[str, Any]) -> None:
        """Configure les sorts d'invocateur."""
        if not self.connection:
            return
        
        spell1_name = params.get("global_spell_1", "Heal")
        spell2_name = params.get("global_spell_2", "Flash")
        spell1_id = SUMMONER_SPELL_MAP.get(spell1_name, 7)
        spell2_id = SUMMONER_SPELL_MAP.get(spell2_name, 4)
        
        payload = {"spell1Id": spell1_id, "spell2Id": spell2_id}
        r = await self.connection.request('patch', "/lol-champ-select/v1/session/my-selection", json=payload)
        
        if r and r.status < 400:
            self._notify_ui(self.EVENT_SPELLS_SET, (spell1_name, spell2_name))
            self._notify_ui(self.EVENT_STATUS, (f"Sorts auto-sélectionnés ({spell1_name}, {spell2_name})", "🪄"))
    
    async def _handle_post_game(self) -> None:
        """Gère le retour automatique au lobby après une partie."""
        params = self.get_params()
        if not params.get("auto_play_again_enabled"):
            return
        
        for i in range(3):
            await asyncio.sleep(2)
            if self.state.current_phase not in ["EndOfGame", "WaitingForStats"]:
                break
            r = await self.connection.request('post', "/lol-lobby/v2/play-again")
            if r and r.status < 400:
                self._notify_ui(self.EVENT_PLAY_AGAIN, None)
                self._notify_ui(self.EVENT_STATUS, ("Rejouer auto réussi !", "✅"))
                break
