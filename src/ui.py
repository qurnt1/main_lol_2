"""
MAIN LOL - Module Interface Graphique (Refactorisé v6.1)
---------------------------------------------------------
Contient LoLAssistantUI (fenêtre principale) et SettingsWindow.
Toutes les mises à jour UI utilisent root.after() pour la thread-safety.

Améliorations v6.1:
- ThreadPoolExecutor pour le chargement des icônes
- Méthodes create_widgets() décomposées en sous-méthodes
- Logging des erreurs au lieu de pass silencieux
- Imports explicites (plus de wildcard)
"""

import os
import logging
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Optional, Dict, Any, Callable

import tkinter as tk
from tkinter import ttk as ttk_widget
import ttkbootstrap as ttk
from ttkbootstrap.scrolled import ScrolledFrame
from PIL import Image, ImageTk, ImageEnhance
import pystray
import keyboard
import pygame

from .config import (
    resource_path, CURRENT_VERSION, GITHUB_REPO_URL,
    REGION_LIST, SUMMONER_SPELL_LIST, DEFAULT_PARAMS
)
from .utils import build_opgg_url, build_porofessor_url


# ───────────────────────────────────────────────────────────────────────────
# CONSTANTES (remplace l'import wildcard de ttkbootstrap.constants)
# ───────────────────────────────────────────────────────────────────────────

# Bootstyles les plus utilisés
BOOTSTYLE_SUCCESS = "success"
BOOTSTYLE_PRIMARY = "primary"
BOOTSTYLE_SECONDARY = "secondary"
BOOTSTYLE_DANGER = "danger"
BOOTSTYLE_INFO = "info"
BOOTSTYLE_WARNING = "warning"


# ───────────────────────────────────────────────────────────────────────────
# SETTINGS WINDOW
# ───────────────────────────────────────────────────────────────────────────

class SettingsWindow:
    """Fenêtre de paramètres de l'application."""
    
    def __init__(self, parent: "LoLAssistantUI"):
        """
        Initialise la fenêtre de paramètres.
        
        Args:
            parent: Instance de LoLAssistantUI
        """
        self.parent = parent
        self.window = ttk.Toplevel(parent.root)
        self.window.title("Paramètres - MAIN LOL")
        self.window.geometry("500x750")
        self.window.resizable(False, False)
        self.window.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # Icône
        self._setup_window_icon()
        
        # Variables liées aux paramètres
        self._init_variables()
        
        # Liste des champions
        self.all_champions = parent.dd.all_names if parent.dd.all_names else ["Garen", "Teemo", "Ashe"]
        self.spell_list = SUMMONER_SPELL_LIST[:]
        
        # Frame principal
        self.main_frame: Optional[ttk.Frame] = None
        
        self.create_widgets()
        self.window.after(100, self.toggle_summoner_entry)
        self.window.after(1000, self._poll_summoner_label)
    
    def _setup_window_icon(self) -> None:
        """Configure l'icône de la fenêtre."""
        try:
            img = Image.open(resource_path("./config/imgs/garen.webp")).resize((16, 16))
            photo = ImageTk.PhotoImage(img)
            self.window.iconphoto(False, photo)
            self.window._icon_img = photo
        except Exception as e:
            logging.debug(f"Impossible de charger l'icône de la fenêtre Settings: {e}")
            self.window._icon_img = None
    
    def _init_variables(self) -> None:
        """Initialise toutes les variables Tkinter liées aux paramètres."""
        params = self.parent.get_params()
        
        # Variables de toggle
        self.auto_accept_var = tk.BooleanVar(value=params.get("auto_accept_enabled", True))
        self.auto_pick_var = tk.BooleanVar(value=params.get("auto_pick_enabled", True))
        self.auto_ban_var = tk.BooleanVar(value=params.get("auto_ban_enabled", True))
        self.auto_summoners_var = tk.BooleanVar(value=params.get("auto_summoners_enabled", True))
        self.summoner_auto_detect_var = tk.BooleanVar(value=params.get("summoner_name_auto_detect", True))
        self.summoner_entry_var = tk.StringVar(value=params.get("manual_summoner_name", ""))
        self.saved_manual_name = params.get("manual_summoner_name", "")
        self.play_again_var = tk.BooleanVar(value=params.get("auto_play_again_enabled", False))
        self.auto_hide_var = tk.BooleanVar(value=params.get("auto_hide_on_connect", True))
        self.close_on_exit_var = tk.BooleanVar(value=params.get("close_app_on_lol_exit", True))
        
        # Aliases pour compatibilité (variables renommées)
        self.auto_var = self.auto_accept_var
        self.pick_var = self.auto_pick_var
        self.ban_var = self.auto_ban_var
        self.summ_var = self.auto_summoners_var
        self.summ_auto_var = self.summoner_auto_detect_var
        self.summ_entry_var = self.summoner_entry_var
    
    def create_widgets(self) -> None:
        """Crée tous les widgets de la fenêtre (méthode principale)."""
        self.main_frame = ttk.Frame(self.window, padding=15)
        self.main_frame.pack(fill="both", expand=True)
        self.main_frame.columnconfigure(0, weight=0)
        self.main_frame.columnconfigure(1, weight=1)
        
        current_row = 0
        
        # Sections modulaires
        current_row = self._create_auto_accept_section(current_row)
        current_row = self._create_pick_section(current_row)
        current_row = self._create_ban_section(current_row)
        current_row = self._create_spells_section(current_row)
        current_row = self._create_summoner_detection_section(current_row)
        current_row = self._create_misc_section(current_row)
        
        # Bouton Fermer
        ttk.Button(
            self.window, text="Fermer", command=self.on_close, bootstyle="primary"
        ).pack(pady=(0, 20), side="bottom")
        
        # Initialiser les états
        self.toggle_pick()
        self.toggle_ban()
        self.toggle_spells()
        self.toggle_summoner_entry()
        
        # Charger les icônes dans les boutons
        self._load_initial_icons()
    
    def _create_auto_accept_section(self, start_row: int) -> int:
        """Crée la section Auto-Accept."""
        ttk.Checkbutton(
            self.main_frame, text="Accepter la partie automatiquement", 
            variable=self.auto_accept_var,
            command=lambda: self.parent.update_param("auto_accept_enabled", self.auto_accept_var.get()),
            bootstyle="success-round-toggle"
        ).grid(row=start_row, column=0, columnspan=2, sticky="w", pady=5)
        
        return start_row + 1
    
    def _create_pick_section(self, start_row: int) -> int:
        """Crée la section Auto-Pick avec les 3 slots de champions."""
        params = self.parent.get_params()
        
        # Toggle Auto Pick
        ttk.Checkbutton(
            self.main_frame, text="Sécuriser mon Champion", 
            variable=self.auto_pick_var,
            command=lambda: (self.parent.update_param("auto_pick_enabled", self.auto_pick_var.get()), self.toggle_pick()),
            bootstyle="info-round-toggle"
        ).grid(row=start_row, column=0, columnspan=2, sticky="w", pady=(15, 5))
        
        # Pick buttons (3 slots)
        ttk.Label(self.main_frame, text="Pick 1 :").grid(row=start_row + 1, column=0, sticky="e", padx=5, pady=3)
        self.btn_pick_1 = ttk.Button(self.main_frame, text=params.get("selected_pick_1", "Garen"), bootstyle="secondary-outline")
        self.btn_pick_1.grid(row=start_row + 1, column=1, sticky="ew", padx=5, pady=3)
        self.btn_pick_1.configure(command=lambda: self._open_champion_picker("pick", 1))
        
        ttk.Label(self.main_frame, text="Pick 2 :").grid(row=start_row + 2, column=0, sticky="e", padx=5, pady=3)
        self.btn_pick_2 = ttk.Button(self.main_frame, text=params.get("selected_pick_2", "Lux"), bootstyle="secondary-outline")
        self.btn_pick_2.grid(row=start_row + 2, column=1, sticky="ew", padx=5, pady=3)
        self.btn_pick_2.configure(command=lambda: self._open_champion_picker("pick", 2))
        
        ttk.Label(self.main_frame, text="Pick 3 :").grid(row=start_row + 3, column=0, sticky="e", padx=5, pady=3)
        self.btn_pick_3 = ttk.Button(self.main_frame, text=params.get("selected_pick_3", "Ashe"), bootstyle="secondary-outline")
        self.btn_pick_3.grid(row=start_row + 3, column=1, sticky="ew", padx=5, pady=3)
        self.btn_pick_3.configure(command=lambda: self._open_champion_picker("pick", 3))
        
        return start_row + 4
    
    def _create_ban_section(self, start_row: int) -> int:
        """Crée la section Auto-Ban."""
        params = self.parent.get_params()
        
        # Toggle Auto Ban
        ttk.Checkbutton(
            self.main_frame, text="Bannir un Champion", 
            variable=self.auto_ban_var,
            command=lambda: (self.parent.update_param("auto_ban_enabled", self.auto_ban_var.get()), self.toggle_ban()),
            bootstyle="danger-round-toggle"
        ).grid(row=start_row, column=0, columnspan=2, sticky="w", pady=(15, 5))
        
        # Ban button
        ttk.Label(self.main_frame, text="Bannir :").grid(row=start_row + 1, column=0, sticky="e", padx=5)
        self.btn_ban = ttk.Button(self.main_frame, text=params.get("selected_ban", "Teemo"), bootstyle="secondary-outline")
        self.btn_ban.grid(row=start_row + 1, column=1, sticky="ew", padx=5)
        self.btn_ban.configure(command=lambda: self._open_champion_picker("ban"))
        
        return start_row + 2
    
    def _create_spells_section(self, start_row: int) -> int:
        """Crée la section Auto-Spells."""
        params = self.parent.get_params()
        
        # Toggle Auto Spells
        ttk.Checkbutton(
            self.main_frame, text="Configurer Sorts", 
            variable=self.auto_summoners_var,
            command=lambda: (self.parent.update_param("auto_summoners_enabled", self.auto_summoners_var.get()), self.toggle_spells()),
            bootstyle="warning-round-toggle"
        ).grid(row=start_row, column=0, columnspan=2, sticky="w", pady=(15, 5))
        
        # Spell buttons
        ttk.Label(self.main_frame, text="Sort 1 :").grid(row=start_row + 1, column=0, sticky="e", padx=5, pady=3)
        self.btn_spell_1 = ttk.Button(self.main_frame, text=params.get("global_spell_1", "Heal"), bootstyle="secondary-outline")
        self.btn_spell_1.grid(row=start_row + 1, column=1, sticky="ew", padx=5, pady=3)
        self.btn_spell_1.configure(command=lambda: self._open_spell_picker(1))
        
        ttk.Label(self.main_frame, text="Sort 2 :").grid(row=start_row + 2, column=0, sticky="e", padx=5, pady=3)
        self.btn_spell_2 = ttk.Button(self.main_frame, text=params.get("global_spell_2", "Flash"), bootstyle="secondary-outline")
        self.btn_spell_2.grid(row=start_row + 2, column=1, sticky="ew", padx=5, pady=3)
        self.btn_spell_2.configure(command=lambda: self._open_spell_picker(2))
        
        return start_row + 3
    
    def _create_summoner_detection_section(self, start_row: int) -> int:
        """Crée la section de détection du pseudo/région."""
        params = self.parent.get_params()
        
        # Toggle Auto Detect
        detect_frame = ttk.Frame(self.main_frame)
        detect_frame.grid(row=start_row, column=0, columnspan=2, sticky="w", pady=(15, 5))
        
        def on_auto_toggle():
            self.toggle_summoner_entry()
            if self.summoner_auto_detect_var.get():
                self.parent.force_refresh_summoner()
            self._update_detect_label_text()
        
        self.switch_auto = ttk.Checkbutton(
            detect_frame, variable=self.summoner_auto_detect_var,
            command=on_auto_toggle, bootstyle="round-toggle"
        )
        self.switch_auto.pack(side="left", padx=(0, 10))
        
        self.lbl_auto_detect = ttk.Label(detect_frame, text="Détection auto du compte")
        self.lbl_auto_detect.pack(side="left")
        
        # Summoner Entry
        ttk.Label(self.main_frame, text="Pseudo :", anchor="w").grid(row=start_row + 1, column=0, sticky="e", padx=5, pady=5)
        self.summ_entry = ttk.Entry(self.main_frame, textvariable=self.summoner_entry_var, state="readonly")
        self.summ_entry.grid(row=start_row + 1, column=1, sticky="ew", padx=5)
        
        # Region
        ttk.Label(self.main_frame, text="Région :", anchor="w").grid(row=start_row + 2, column=0, sticky="e", padx=5, pady=5)
        self.region_var = tk.StringVar(value=params.get("region", "euw"))
        self.region_cb = ttk.Combobox(self.main_frame, values=REGION_LIST, textvariable=self.region_var, state="readonly")
        self.region_cb.grid(row=start_row + 2, column=1, sticky="ew", padx=5)
        self.region_cb.bind("<<ComboboxSelected>>", lambda e: self.parent.update_param("region", self.region_var.get()))
        
        return start_row + 3
    
    def _create_misc_section(self, start_row: int) -> int:
        """Crée la section des options diverses."""
        # Separator
        ttk.Separator(self.main_frame).grid(row=start_row, column=0, columnspan=2, sticky="we", pady=(15, 10))
        
        # Misc Options Frame
        misc_frame = ttk.Frame(self.main_frame)
        misc_frame.grid(row=start_row + 1, column=0, columnspan=2, sticky="w")
        
        ttk.Checkbutton(
            misc_frame, text="Retour au salon automatique a la fin de la partie", 
            variable=self.play_again_var,
            command=lambda: self.parent.update_param("auto_play_again_enabled", self.play_again_var.get()),
            bootstyle="info-round-toggle"
        ).pack(anchor="w", pady=2)
        
        ttk.Checkbutton(
            misc_frame, text="Masquer Main LOL au lancement de LoL (3 secondes)", 
            variable=self.auto_hide_var,
            command=lambda: self.parent.update_param("auto_hide_on_connect", self.auto_hide_var.get()),
            bootstyle="secondary-round-toggle"
        ).pack(anchor="w", pady=2)
        
        ttk.Checkbutton(
            misc_frame, text="Fermer Main LOL à la fermeture de LoL", 
            variable=self.close_on_exit_var,
            command=lambda: self.parent.update_param("close_app_on_lol_exit", self.close_on_exit_var.get()),
            bootstyle="danger-round-toggle"
        ).pack(anchor="w", pady=2)
        
        return start_row + 2
    
    def _load_initial_icons(self) -> None:
        """Charge les icônes initiales dans tous les boutons."""
        params = self.parent.get_params()
        
        self._update_btn_content(self.btn_ban, params.get("selected_ban", ""), is_champ=True)
        self._update_btn_content(self.btn_pick_1, params.get("selected_pick_1", ""), is_champ=True)
        self._update_btn_content(self.btn_pick_2, params.get("selected_pick_2", ""), is_champ=True)
        self._update_btn_content(self.btn_pick_3, params.get("selected_pick_3", ""), is_champ=True)
        self._update_btn_content(self.btn_spell_1, params.get("global_spell_1", ""), is_champ=False)
        self._update_btn_content(self.btn_spell_2, params.get("global_spell_2", ""), is_champ=False)
    
    def _open_champion_picker(self, context: str = "pick", slot_num: int = 1) -> None:
        """Ouvre le sélecteur de champion."""
        picker = ttk.Toplevel(self.window)
        if self.window._icon_img:
            picker.iconphoto(False, self.window._icon_img)
        picker.title(f"Sélectionner Champion ({context.title()})")
        picker.geometry(f"480x600+{self.window.winfo_x()+20}+{self.window.winfo_y()+20}")
        
        # Search bar
        search_frame = ttk.Frame(picker, padding=10)
        search_frame.pack(fill="x")
        ttk.Label(search_frame, text="Rechercher :").pack(side="left")
        search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=search_var)
        search_entry.pack(side="left", fill="x", expand=True, padx=5)
        search_entry.focus_set()
        
        # Scrollable grid
        scroll_container = ScrolledFrame(picker, autohide=False)
        scroll_container.pack(fill="both", expand=True, padx=5, pady=5)
        grid_frame = scroll_container
        
        # Exclude already selected champions
        params = self.parent.get_params()
        excluded = set()
        if context == "pick":
            pick_1 = params.get("selected_pick_1")
            pick_2 = params.get("selected_pick_2")
            pick_3 = params.get("selected_pick_3")
            banned = params.get("selected_ban")
            if banned:
                excluded.add(banned)
            if slot_num == 1:
                excluded.update({pick_2, pick_3})
            elif slot_num == 2:
                excluded.update({pick_1, pick_3})
            elif slot_num == 3:
                excluded.update({pick_1, pick_2})
        
        valid_champs = [c for c in self.all_champions if c not in excluded]
        
        def populate_grid(filter_text: str = "") -> None:
            for widget in grid_frame.winfo_children():
                widget.destroy()
            filter_text = filter_text.lower()
            row, col = 0, 0
            for champ_name in valid_champs:
                if filter_text in champ_name.lower():
                    btn = ttk.Button(
                        grid_frame, text=champ_name, bootstyle="link", compound="top",
                        command=lambda c=champ_name: on_select(c)
                    )
                    btn.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
                    self._load_img_into_btn(btn, champ_name, is_champ=True)
                    col += 1
                    if col >= 4:
                        col = 0
                        row += 1
        
        def on_select(champ_name: str) -> None:
            if context == "ban":
                self.parent.update_param("selected_ban", champ_name)
                self._update_btn_content(self.btn_ban, champ_name, True)
            elif context == "pick":
                if slot_num == 1:
                    self.parent.update_param("selected_pick_1", champ_name)
                    self._update_btn_content(self.btn_pick_1, champ_name, True)
                elif slot_num == 2:
                    self.parent.update_param("selected_pick_2", champ_name)
                    self._update_btn_content(self.btn_pick_2, champ_name, True)
                elif slot_num == 3:
                    self.parent.update_param("selected_pick_3", champ_name)
                    self._update_btn_content(self.btn_pick_3, champ_name, True)
            picker.destroy()
        
        search_var.trace("w", lambda *args: populate_grid(search_var.get()))
        search_entry.bind("<Return>", lambda e: grid_frame.winfo_children()[0].invoke() if grid_frame.winfo_children() else None)
        populate_grid()
    
    def _open_spell_picker(self, spell_slot_num: int) -> None:
        """Ouvre le sélecteur de sort."""
        if not self.auto_summoners_var.get():
            return
        
        picker = ttk.Toplevel(self.window)
        if self.window._icon_img:
            picker.iconphoto(False, self.window._icon_img)
        picker.title(f"Choisir Sort {spell_slot_num}")
        picker.geometry(f"350x350+{self.window.winfo_x()+50}+{self.window.winfo_y()+100}")
        picker.resizable(False, False)
        container = ttk.Frame(picker, padding=10)
        container.pack(fill="both", expand=True)
        
        def on_pick(spell_name: str) -> None:
            params = self.parent.get_params()
            other = params.get("global_spell_2") if spell_slot_num == 1 else params.get("global_spell_1")
            if spell_name == other and spell_name != "(Aucun)":
                if spell_slot_num == 1:
                    self.parent.update_param("global_spell_2", "(Aucun)")
                    self._update_btn_content(self.btn_spell_2, "(Aucun)", False)
                else:
                    self.parent.update_param("global_spell_1", "(Aucun)")
                    self._update_btn_content(self.btn_spell_1, "(Aucun)", False)
            
            if spell_slot_num == 1:
                self.parent.update_param("global_spell_1", spell_name)
                self._update_btn_content(self.btn_spell_1, spell_name, False)
            else:
                self.parent.update_param("global_spell_2", spell_name)
                self._update_btn_content(self.btn_spell_2, spell_name, False)
            picker.destroy()
        
        row, col = 0, 0
        for spell in self.spell_list:
            spell_frame = ttk.Frame(container)
            spell_frame.grid(row=row, column=col, padx=5, pady=5)
            btn = ttk.Button(spell_frame, bootstyle="link", command=lambda s=spell: on_pick(s))
            btn.pack()
            self._load_img_into_btn(btn, spell, False)
            col += 1
            if col > 3:
                col = 0
                row += 1
    
    def _update_btn_content(self, btn_widget: ttk.Button, name: str, is_champ: bool = True) -> None:
        """Met à jour le contenu d'un bouton avec icône (thread-safe via ThreadPoolExecutor)."""
        if not name:
            name = "..."
        
        def task():
            try:
                if is_champ:
                    img = self.parent.dd.get_champion_icon(name)
                else:
                    img = self.parent.dd.get_summoner_icon(name)
                
                if img:
                    img = img.resize((30, 30), Image.LANCZOS)
                    photo = ImageTk.PhotoImage(img)
                    
                    def update_ui():
                        if btn_widget.winfo_exists():
                            btn_widget.configure(image=photo, text=f"  {name}", compound="left")
                            btn_widget.image = photo
                    
                    btn_widget.after(0, update_ui)
                else:
                    def update_ui_no_img():
                        if btn_widget.winfo_exists():
                            btn_widget.configure(image='', text=f"  {name}", compound="left")
                    btn_widget.after(0, update_ui_no_img)
            except Exception as e:
                logging.debug(f"Erreur chargement icône pour {name}: {e}")
        
        self.parent.executor.submit(task)
    
    def _load_img_into_btn(self, btn_widget: ttk.Button, name: str, is_champ: bool = True) -> None:
        """Charge une image dans un bouton (thread-safe via ThreadPoolExecutor)."""
        def task():
            try:
                if is_champ:
                    img = self.parent.dd.get_champion_icon(name)
                else:
                    img = self.parent.dd.get_summoner_icon(name)
                
                if img:
                    size = (40, 40) if is_champ else (48, 48)
                    img = img.resize(size, Image.LANCZOS)
                    photo = ImageTk.PhotoImage(img)
                    
                    def update_ui():
                        if btn_widget.winfo_exists():
                            btn_widget.configure(image=photo)
                            btn_widget.image = photo
                    
                    btn_widget.after(0, update_ui)
            except Exception as e:
                logging.debug(f"Erreur chargement image pour {name}: {e}")
        
        self.parent.executor.submit(task)
    
    def toggle_summoner_entry(self) -> None:
        """Bascule l'état de l'entrée pseudo selon la détection auto."""
        if self.summoner_auto_detect_var.get():
            current_entry = self.summoner_entry_var.get()
            current_auto = self.parent.get_auto_summoner_name()
            if current_entry != current_auto and current_entry != "(détection auto...)":
                self.saved_manual_name = current_entry
            
            self.summ_entry.configure(state="readonly")
            self.region_cb.configure(state="disabled")
            
            self.parent.force_refresh_summoner()
            auto_name = self.parent.get_auto_summoner_name()
            self.summoner_entry_var.set(auto_name if auto_name else "(détection auto...)")
            
            auto_reg = self.parent.get_platform_for_websites()
            self.region_var.set(auto_reg)
            self.parent.update_param("region", auto_reg)
        else:
            self.summ_entry.configure(state="normal")
            self.region_cb.configure(state="readonly")
            self.summoner_entry_var.set(self.saved_manual_name)
            self.region_var.set(self.parent.get_params().get("region", "euw"))
        
        self._update_detect_label_text()
    
    def toggle_pick(self) -> None:
        """Active/désactive les boutons de pick."""
        state = "normal" if self.auto_pick_var.get() else "disabled"
        self.btn_pick_1.configure(state=state)
        self.btn_pick_2.configure(state=state)
        self.btn_pick_3.configure(state=state)
    
    def toggle_ban(self) -> None:
        """Active/désactive le bouton de ban."""
        self.btn_ban.configure(state="normal" if self.auto_ban_var.get() else "disabled")
    
    def toggle_spells(self) -> None:
        """Active/désactive les boutons de sorts."""
        state = "normal" if self.auto_summoners_var.get() else "disabled"
        self.btn_spell_1.configure(state=state)
        self.btn_spell_2.configure(state=state)
    
    def _update_detect_label_text(self) -> None:
        """Met à jour le label de détection auto."""
        detected = self.parent.get_auto_summoner_name()
        
        if self.parent.is_ws_active() and detected:
            self.lbl_auto_detect.configure(text=f"Détection auto du compte (compte détecté : {detected})")
        else:
            self.lbl_auto_detect.configure(text="Détection auto du compte")
    
    def _poll_summoner_label(self) -> None:
        """Polling périodique pour mettre à jour le label summoner."""
        if not self.window.winfo_exists():
            return
        
        self._update_detect_label_text()
        
        if self.summoner_auto_detect_var.get():
            curr = self.parent.get_auto_summoner_name() or "(détection auto...)"
            if self.summoner_entry_var.get() != curr:
                self.summoner_entry_var.set(curr)
            areg = self.parent.get_platform_for_websites()
            if self.region_var.get() != areg:
                self.region_var.set(areg)
                self.parent.update_param("region", areg)
        
        if not self.summoner_auto_detect_var.get():
            self.saved_manual_name = self.summoner_entry_var.get()
        
        self.window.after(1000, self._poll_summoner_label)
    
    def on_close(self) -> None:
        """Ferme la fenêtre et sauvegarde les paramètres."""
        self.parent.update_param("auto_summoners_enabled", self.auto_summoners_var.get())
        self.parent.update_param("summoner_name_auto_detect", self.summoner_auto_detect_var.get())
        
        if not self.summoner_auto_detect_var.get():
            self.parent.update_param("manual_summoner_name", self.summoner_entry_var.get())
            self.parent.update_param("region", self.region_var.get())
        
        self.parent.update_param("auto_play_again_enabled", self.play_again_var.get())
        self.parent.update_param("auto_hide_on_connect", self.auto_hide_var.get())
        self.parent.update_param("close_app_on_lol_exit", self.close_on_exit_var.get())
        self.parent.save_and_notify()
        self.window.destroy()


# ───────────────────────────────────────────────────────────────────────────
# MAIN UI
# ───────────────────────────────────────────────────────────────────────────

class LoLAssistantUI:
    """Interface graphique principale de MAIN LOL."""
    
    # ThreadPoolExecutor partagé pour le chargement des icônes
    MAX_WORKERS = 4
    
    def __init__(
        self, 
        dd,  # DataDragon instance
        params: Dict[str, Any],
        save_callback: Callable[[], None],
        update_param_callback: Callable[[str, Any], None],
        get_params_callback: Callable[[], Dict[str, Any]],
        quit_callback: Callable[[], None]
    ):
        """
        Initialise l'interface principale.
        
        Args:
            dd: Instance de DataDragon
            params: Dictionnaire des paramètres
            save_callback: Fonction pour sauvegarder les paramètres
            update_param_callback: Fonction pour mettre à jour un paramètre
            get_params_callback: Fonction pour récupérer les paramètres
            quit_callback: Fonction pour quitter l'application
        """
        self.dd = dd
        self._params = params
        self._save_callback = save_callback
        self._update_param_callback = update_param_callback
        self._get_params_callback = get_params_callback
        self._quit_callback = quit_callback
        
        self.running = True
        self.settings_win: Optional[SettingsWindow] = None
        self.ws_manager = None  # Sera défini par main.py
        
        # ThreadPoolExecutor pour le chargement des icônes
        self.executor = ThreadPoolExecutor(max_workers=self.MAX_WORKERS)
        
        # Initialiser le son
        self._init_sound()
        
        # Créer la fenêtre
        self.theme = params.get("theme", "darkly")
        self.root = ttk.Window(themename=self.theme)
        self.root.title("MAIN LOL")
        self.root.geometry("380x180")
        self.root.resizable(False, False)
        
        self.theme_var = tk.StringVar(value=self.theme)
        
        # Références aux widgets (initialisées dans create_ui)
        self.bg_label: Optional[tk.Label] = None
        self.banner_label: Optional[ttk.Label] = None
        self.connection_indicator: Optional[tk.Canvas] = None
        self.status_label: Optional[ttk.Label] = None
        
        self.create_ui()
        self.create_system_tray()
        self.setup_hotkeys()
    
    def _init_sound(self) -> None:
        """Initialise le système de son."""
        try:
            pygame.mixer.init()
            self.sound_effect = pygame.mixer.Sound(resource_path("config/son.wav"))
        except Exception as e:
            logging.debug(f"Impossible d'initialiser le son: {e}")
            self.sound_effect = None
    
    def set_ws_manager(self, ws_manager) -> None:
        """Définit le gestionnaire WebSocket."""
        self.ws_manager = ws_manager
    
    def get_params(self) -> Dict[str, Any]:
        """Retourne les paramètres actuels."""
        return self._get_params_callback()
    
    def update_param(self, key: str, value: Any) -> None:
        """Met à jour un paramètre."""
        self._update_param_callback(key, value)
    
    def save_and_notify(self) -> None:
        """Sauvegarde les paramètres et affiche une notification."""
        self._save_callback()
        self.show_toast("Paramètres sauvegardés !")
    
    def is_ws_active(self) -> bool:
        """Retourne True si le WebSocket est connecté."""
        return self.ws_manager.is_active if self.ws_manager else False
    
    def get_auto_summoner_name(self) -> Optional[str]:
        """Retourne le nom du summoner détecté automatiquement."""
        return self.ws_manager.get_riot_id() if self.ws_manager else None
    
    def get_platform_for_websites(self) -> str:
        """Retourne la région pour les URLs."""
        if self.ws_manager:
            return self.ws_manager.get_platform_for_websites()
        return self.get_params().get("region", "euw")
    
    def force_refresh_summoner(self) -> None:
        """Force un rafraîchissement du summoner."""
        if self.ws_manager:
            self.ws_manager.force_refresh_summoner()
    
    def create_ui(self) -> None:
        """Crée tous les widgets de l'interface (méthode principale)."""
        self._configure_styles()
        self._create_background()
        self._create_banner()
        self._create_connection_indicator()
        self._create_status_label()
        self._create_settings_gear()
        self._create_opgg_button()
        
        # Window protocol
        self.root.protocol("WM_DELETE_WINDOW", self.root.withdraw)
    
    def _configure_styles(self) -> None:
        """Configure les styles de l'interface."""
        style = ttk.Style()
        style.configure(".", font=("Segoe UI Emoji", 10))
        style.configure("Status.TLabel", font=("Segoe UI Emoji", 11), background=self.root['bg'])
    
    def _create_background(self) -> None:
        """Crée le label de fond."""
        self.bg_label = tk.Label(self.root, bg="#2b2b2b")
        self.bg_label.place(x=0, y=0, relwidth=1, relheight=1)
        self.bg_label.lower()
    
    def _create_banner(self) -> None:
        """Crée la bannière avec l'icône."""
        try:
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
        except Exception as e:
            logging.debug(f"Impossible de charger les images de bannière: {e}")
    
    def _create_connection_indicator(self) -> None:
        """Crée l'indicateur de connexion."""
        self.connection_indicator = tk.Canvas(
            self.root, width=12, height=12, bd=0, highlightthickness=0, bg="#2b2b2b"
        )
        self.connection_indicator.place(relx=0.05, rely=0.05, anchor="nw")
        self.update_connection_indicator(False)
    
    def _create_status_label(self) -> None:
        """Crée le label de statut."""
        self.status_label = ttk.Label(
            self.root, text="En attente du lancement de League of Legends...",
            style="Status.TLabel", justify="center", wraplength=380
        )
        self.status_label.place(relx=0.5, rely=0.38, anchor="center")
    
    def _create_settings_gear(self) -> None:
        """Crée le bouton de paramètres (engrenage)."""
        gear_path = resource_path("./config/imgs/gear.png")
        if os.path.exists(gear_path):
            try:
                gear_img = ImageTk.PhotoImage(Image.open(gear_path).resize((25, 30)))
                cog = ttk.Label(self.root, image=gear_img, cursor="hand2")
                cog.image = gear_img
                cog.place(relx=0.95, rely=0.05, anchor="ne")
                cog.bind("<Button-1>", lambda e: self.open_settings())
            except Exception as e:
                logging.debug(f"Impossible de charger l'icône engrenage: {e}")
                self._create_fallback_gear()
        else:
            self._create_fallback_gear()
    
    def _create_fallback_gear(self) -> None:
        """Crée un bouton engrenage de secours (texte)."""
        cog = ttk.Button(self.root, text="⚙", command=self.open_settings, bootstyle="link")
        cog.place(relx=0.95, rely=0.05, anchor="ne")
    
    def _create_opgg_button(self) -> None:
        """Crée le bouton OP.GG."""
        opgg_btn = ttk.Button(
            self.root, text="Voir mes stats (OP.GG)",
            bootstyle="success-outline", padding=(20, 10), width=22,
            command=lambda: webbrowser.open(self.build_opgg_url())
        )
        opgg_btn.place(relx=0.5, rely=0.75, anchor="center")
    
    def build_opgg_url(self) -> str:
        """Construit l'URL OP.GG."""
        riot_id = self._get_riot_id_display()
        if not riot_id:
            riot_id = self.get_params().get("manual_summoner_name", "")
        return build_opgg_url(self.get_platform_for_websites(), riot_id)
    
    def build_porofessor_url(self) -> str:
        """Construit l'URL Porofessor."""
        riot_id = self._get_riot_id_display()
        if not riot_id:
            riot_id = self.get_params().get("manual_summoner_name", "")
        return build_porofessor_url(self.get_platform_for_websites(), riot_id)
    
    def _get_riot_id_display(self) -> Optional[str]:
        """Retourne le Riot ID à afficher selon le mode de détection."""
        params = self.get_params()
        if params.get("summoner_name_auto_detect", True):
            return self.get_auto_summoner_name()
        return params.get("manual_summoner_name")
    
    def set_background_splash(self, champion_name: str) -> None:
        """Met le splash art d'un champion en arrière-plan."""
        def task():
            try:
                img = self.dd.get_splash_art(champion_name)
                if not img:
                    return
                
                # Resize and crop
                window_w, window_h = 380, 180
                base_width = window_w
                w_percent = base_width / float(img.size[0])
                h_size = int(float(img.size[1]) * w_percent)
                
                if h_size < window_h:
                    base_height = window_h
                    h_percent = base_height / float(img.size[1])
                    w_size = int(float(img.size[0]) * h_percent)
                    img = img.resize((w_size, base_height), Image.Resampling.LANCZOS)
                else:
                    img = img.resize((base_width, h_size), Image.Resampling.LANCZOS)
                
                # Center crop
                left = (img.width - window_w) / 2
                top = (img.height - window_h) / 2
                right = (img.width + window_w) / 2
                bottom = (img.height + window_h) / 2
                img = img.crop((left, top, right, bottom))
                
                # Darken
                enhancer = ImageEnhance.Brightness(img)
                img = enhancer.enhance(0.4)
                
                tk_img = ImageTk.PhotoImage(img)
                
                def update_ui():
                    if self.root.winfo_exists() and self.bg_label:
                        self.bg_label.configure(image=tk_img)
                        self.bg_label.image = tk_img
                
                self.root.after(0, update_ui)
                
            except Exception as e:
                logging.warning(f"Erreur Splash Art pour {champion_name}: {e}")
        
        self.executor.submit(task)
    
    def create_system_tray(self) -> None:
        """Crée l'icône du system tray."""
        try:
            image = Image.open(resource_path("./config/imgs/garen.webp")).resize((64, 64))
            menu = pystray.Menu(
                pystray.MenuItem("Afficher/Masquer", self.toggle_window),
                pystray.MenuItem("Quitter", self._quit_callback)
            )
            self.icon = pystray.Icon("MAIN LOL", image, "MAIN LOL", menu)
            
            def run_tray():
                try:
                    self.icon.run()
                except Exception as e:
                    logging.debug(f"Erreur system tray: {e}")
            
            self.executor.submit(run_tray)
        except Exception as e:
            logging.warning(f"Impossible de créer le system tray: {e}")
    
    def setup_hotkeys(self) -> None:
        """Configure les raccourcis clavier."""
        try:
            keyboard.add_hotkey('alt+p', self.open_porofessor)
            keyboard.add_hotkey('alt+c', self.toggle_window)
        except Exception as e:
            logging.debug(f"Impossible de configurer les hotkeys: {e}")
    
    def open_porofessor(self) -> None:
        """Ouvre Porofessor dans le navigateur."""
        riot_id = self._get_riot_id_display()
        if riot_id:
            webbrowser.open(self.build_porofessor_url())
    
    def show_window(self) -> None:
        """Affiche la fenêtre."""
        if self.root.state() == 'withdrawn':
            self.root.after(0, self.root.deiconify)
            self.root.after(0, self.root.lift)
    
    def hide_window(self) -> None:
        """Masque la fenêtre."""
        if self.root.state() != 'withdrawn':
            self.root.after(0, self.root.withdraw)
    
    def toggle_window(self, icon=None) -> None:
        """Bascule la visibilité de la fenêtre."""
        if self.root.state() == 'withdrawn':
            self.show_window()
        else:
            self.hide_window()
    
    def open_settings(self) -> None:
        """Ouvre la fenêtre de paramètres."""
        if self.settings_win and self.settings_win.window.winfo_exists():
            self.settings_win.window.lift()
            self.settings_win.window.focus_force()
            return
        self.settings_win = SettingsWindow(self)
    
    def update_status(self, message: str, emoji: str = "") -> None:
        """Met à jour le label de statut (thread-safe)."""
        now = datetime.now().strftime("%H:%M:%S")
        log_msg = f"[{now}] {emoji} {message}" if emoji else f"[{now}] {message}"
        print(log_msg, flush=True)
        
        self.root.after(0, lambda: self.status_label.config(text=message))
    
    def update_connection_indicator(self, connected: bool) -> None:
        """Met à jour l'indicateur de connexion (thread-safe)."""
        def draw():
            if not self.connection_indicator or not self.connection_indicator.winfo_exists():
                return
            
            self.connection_indicator.delete("all")
            color = "#00ff00" if connected else "#ff0000"
            self.connection_indicator.create_oval(2, 2, 10, 10, fill=color, outline="")
            
            if connected:
                def pulse(step=0):
                    if not self.connection_indicator.winfo_exists():
                        return
                    radius = 4 + int(2 * abs((step % 20) - 10) / 10)
                    self.connection_indicator.delete("all")
                    self.connection_indicator.create_oval(6 - radius, 6 - radius, 6 + radius, 6 + radius, fill=color, outline="")
                    if self.running and self.is_ws_active():
                        self.connection_indicator.after(50, lambda: pulse(step + 1))
                    elif self.connection_indicator.winfo_exists():
                        self.connection_indicator.delete("all")
                        self.connection_indicator.create_oval(2, 2, 10, 10, fill="#ff0000", outline="")
                pulse()
        
        self.root.after(0, draw)
    
    def show_toast(self, message: str, duration: int = 2000) -> None:
        """Affiche une notification toast."""
        try:
            toast = ttk.Label(
                self.root, text=message, bootstyle="success",
                font=("Segoe UI", 10, "bold")
            )
            toast.place(relx=0.5, rely=0.98, anchor="s")
            self.root.after(duration, toast.destroy)
        except Exception as e:
            logging.debug(f"Erreur affichage toast: {e}")
    
    def show_update_popup(self, new_version: str) -> None:
        """Affiche la popup de mise à jour."""
        popup = ttk.Toplevel(self.root)
        popup.title("Mise à jour MAIN LOL")
        popup.geometry("400x250")
        popup.resizable(False, False)
        
        # Center popup
        popup.update_idletasks()
        width = popup.winfo_width()
        height = popup.winfo_height()
        x = (popup.winfo_screenwidth() // 2) - (width // 2)
        y = (popup.winfo_screenheight() // 2) - (height // 2)
        popup.geometry(f'{width}x{height}+{x}+{y}')
        
        # Icon
        try:
            icon_path = resource_path("./config/imgs/garen.webp")
            if os.path.exists(icon_path):
                img = Image.open(icon_path).resize((32, 32))
                photo = ImageTk.PhotoImage(img)
                popup.iconphoto(False, photo)
                popup._icon_ref = photo
        except Exception as e:
            logging.debug(f"Erreur icône popup update: {e}")
        
        # Title
        title_lbl = ttk.Label(
            popup, text="Nouvelle version détectée !",
            font=("Segoe UI Emoji", 14, "bold"),
            bootstyle="inverse-primary"
        )
        title_lbl.pack(fill="x", pady=(0, 15), ipady=10)
        
        # Info
        info_frame = ttk.Frame(popup, padding=10)
        info_frame.pack(fill="both", expand=True)
        
        info_text = f"Une mise à jour est disponible sur GitHub.\n\nVersion actuelle : {CURRENT_VERSION}\nNouvelle version : {new_version}"
        ttk.Label(info_frame, text=info_text, justify="center", font=("Segoe UI", 11)).pack(pady=5)
        
        # Buttons
        btn_frame = ttk.Frame(popup, padding=(0, 0, 0, 20))
        btn_frame.pack(fill="x")
        
        def on_download():
            webbrowser.open(GITHUB_REPO_URL)
            popup.destroy()
        
        btn_yes = ttk.Button(
            btn_frame, text="Télécharger", bootstyle="success",
            command=on_download, width=15
        )
        btn_yes.pack(side="left", padx=(40, 10), expand=True)
        
        btn_no = ttk.Button(
            btn_frame, text="Plus tard", bootstyle="secondary",
            command=popup.destroy, width=15
        )
        btn_no.pack(side="right", padx=(10, 40), expand=True)
        
        popup.attributes('-topmost', True)
        popup.focus_force()
    
    def on_core_event(self, event_type: str, data: Any) -> None:
        """
        Gestionnaire d'événements du core (thread-safe).
        Planifie les mises à jour UI sur le thread principal.
        """
        self.root.after(0, lambda: self._handle_core_event(event_type, data))
    
    def _handle_core_event(self, event_type: str, data: Any) -> None:
        """Traite un événement du core sur le thread principal."""
        from .core import WebSocketManager  # Import relatif correct
        
        if event_type == WebSocketManager.EVENT_CONNECTED:
            self.update_connection_indicator(True)
            params = self.get_params()
            if params.get("auto_hide_on_connect", True):
                self.root.after(3000, self.hide_window)
        
        elif event_type == WebSocketManager.EVENT_DISCONNECTED:
            self.update_connection_indicator(False)
            params = self.get_params()
            if params.get("close_app_on_lol_exit", True):
                self.root.after(100, self._quit_callback)
            else:
                self.root.after(100, self.show_window)
        
        elif event_type == WebSocketManager.EVENT_STATUS:
            message, emoji = data
            self.update_status(message, emoji)
        
        elif event_type == WebSocketManager.EVENT_CHAMPION_PICKED:
            self.set_background_splash(data)
        
        elif event_type == WebSocketManager.EVENT_TOAST:
            self.show_toast(data)
    
    def run(self) -> None:
        """Lance la boucle principale Tkinter."""
        self.root.mainloop()
    
    def stop(self) -> None:
        """Arrête l'interface."""
        self.running = False
        
        # Arrêter le ThreadPoolExecutor
        try:
            self.executor.shutdown(wait=False)
        except Exception as e:
            logging.debug(f"Erreur arrêt executor: {e}")
        
        # Arrêter le system tray
        try:
            if hasattr(self, 'icon'):
                self.icon.stop()
        except Exception as e:
            logging.debug(f"Erreur arrêt tray icon: {e}")
        
        self.root.quit()
