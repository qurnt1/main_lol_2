"""
MAIN LOL - Point d'Entrée
-------------------------
Initialise l'application, gère les threads et la fermeture propre.
"""

import sys
import logging
from threading import Thread
from typing import Dict, Any

# Imports locaux depuis le package src
from src.config import (
    load_parameters, save_parameters, DEFAULT_PARAMS, 
    get_cache_dirs, CURRENT_VERSION
)
from src.utils import enable_high_dpi, check_single_instance, remove_lockfile, check_for_updates
from src.core import DataDragon, WebSocketManager
from src.ui import LoLAssistantUI



class MainLoLApplication:
    """Classe principale gérant le cycle de vie de l'application."""
    
    def __init__(self):
        """Initialise l'application MAIN LOL."""
        # Activer High DPI
        enable_high_dpi()
        
        # Vérifier instance unique
        if not check_single_instance():
            logging.info("Une autre instance est déjà en cours. Fermeture.")
            sys.exit(0)
        
        # Charger les paramètres
        self._params: Dict[str, Any] = load_parameters()
        
        # Créer les dossiers de cache
        get_cache_dirs()
        
        # Initialiser DataDragon
        logging.info("Chargement de DataDragon...")
        self.dd = DataDragon()
        self.dd.load()
        
        # Créer l'interface
        logging.info("Création de l'interface...")
        self.ui = LoLAssistantUI(
            dd=self.dd,
            params=self._params,
            save_callback=self._save_params,
            update_param_callback=self._update_param,
            get_params_callback=self._get_params,
            quit_callback=self.quit_app
        )
        
        # Créer le gestionnaire WebSocket
        logging.info("Initialisation du WebSocket...")
        self.ws_manager = WebSocketManager(
            ui_callback=self.ui.on_core_event,
            dd=self.dd,
            get_params=self._get_params
        )
        
        # Connecter le WS à l'UI
        self.ui.set_ws_manager(self.ws_manager)
        
        # Vérifier les mises à jour en arrière-plan
        self._check_updates_async()
        
        # Démarrer le WebSocket
        self.ws_manager.start()
    
    def _get_params(self) -> Dict[str, Any]:
        """Retourne les paramètres actuels."""
        return self._params.copy()
    
    def _update_param(self, key: str, value: Any) -> None:
        """Met à jour un paramètre."""
        self._params[key] = value
    
    def _save_params(self) -> None:
        """Sauvegarde les paramètres."""
        if save_parameters(self._params):
            logging.info("Paramètres sauvegardés avec succès.")
        else:
            logging.error("Échec de la sauvegarde des paramètres.")
    
    def _check_updates_async(self) -> None:
        """Vérifie les mises à jour en arrière-plan."""
        def _check():
            new_version = check_for_updates()
            if new_version:
                logging.info(f"Nouvelle version disponible: {new_version}")
                # Planifier l'affichage du popup sur le thread UI
                self.ui.root.after(0, lambda: self.ui.show_update_popup(new_version))
            else:
                logging.info("Application à jour.")
        
        Thread(target=_check, daemon=True).start()
    
    def run(self) -> None:
        """Lance la boucle principale de l'application."""
        logging.info(f"MAIN LOL v{CURRENT_VERSION} démarré.")
        try:
            self.ui.run()
        finally:
            self.cleanup()
    
    def quit_app(self) -> None:
        """Ferme l'application proprement."""
        logging.info("Fermeture de l'application...")
        self._save_params()
        self.ws_manager.stop()
        self.ui.stop()
        self.cleanup()
    
    def cleanup(self) -> None:
        """Nettoyage final avant fermeture."""
        remove_lockfile()
        logging.info("Nettoyage terminé.")


def main() -> None:
    """Point d'entrée principal."""
    try:
        app = MainLoLApplication()
        app.run()
    except KeyboardInterrupt:
        logging.info("Interruption clavier détectée.")
    except Exception as e:
        logging.critical(f"Erreur fatale: {e}", exc_info=True)
    finally:
        remove_lockfile()


if __name__ == "__main__":
    main()
