"""
MAIN LOL - Point d'Entrée (Refactorisé v6.1)
---------------------------------------------
Initialise l'application, gère les threads et la fermeture propre.

Améliorations v6.1:
- Chargement asynchrone de DataDragon (ne bloque plus l'UI)
- Meilleure gestion des erreurs avec logging
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
        """
        Initialise l'application MAIN LOL.
        
        v6.1: DataDragon est maintenant chargé de manière asynchrone
        pour éviter de bloquer l'interface utilisateur au démarrage.
        """
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
        
        # Initialiser DataDragon (NE PAS CHARGER ICI - fait en async)
        logging.info("Initialisation de DataDragon...")
        self.dd = DataDragon()
        # Note: dd.load() sera appelé en arrière-plan
        
        # Créer l'interface AVANT de charger DataDragon
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
        
        # Charger DataDragon en arrière-plan (v6.1)
        self._load_datadragon_async()
        
        # Vérifier les mises à jour en arrière-plan
        self._check_updates_async()
        
        # Démarrer le WebSocket
        self.ws_manager.start()
    
    def _load_datadragon_async(self) -> None:
        """
        Charge DataDragon en arrière-plan pour ne pas bloquer l'UI.
        
        Une fois chargé, affiche un toast de confirmation.
        """
        def load_task():
            try:
                logging.info("Chargement de DataDragon en arrière-plan...")
                self.dd.load()
                
                # Notifier l'UI que le chargement est terminé
                champion_count = len(self.dd.all_names)
                if champion_count > 0:
                    message = f"Champions chargés ({champion_count})"
                    self.ui.root.after(0, lambda: self.ui.show_toast(message, duration=1500))
                    logging.info(f"DataDragon chargé: {champion_count} champions")
                else:
                    logging.warning("DataDragon chargé mais sans champions")
                    
            except Exception as e:
                logging.error(f"Erreur lors du chargement de DataDragon: {e}")
                self.ui.root.after(0, lambda: self.ui.show_toast("Erreur chargement champions", duration=3000))
        
        # Utiliser le ThreadPoolExecutor de l'UI si disponible
        if hasattr(self.ui, 'executor'):
            self.ui.executor.submit(load_task)
        else:
            Thread(target=load_task, daemon=True).start()
    
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
        def check_task():
            try:
                new_version = check_for_updates()
                if new_version:
                    logging.info(f"Nouvelle version disponible: {new_version}")
                    # Planifier l'affichage du popup sur le thread UI
                    self.ui.root.after(0, lambda: self.ui.show_update_popup(new_version))
                else:
                    logging.info("Application à jour.")
            except Exception as e:
                logging.warning(f"Erreur lors de la vérification des mises à jour: {e}")
        
        # Utiliser le ThreadPoolExecutor de l'UI si disponible
        if hasattr(self.ui, 'executor'):
            self.ui.executor.submit(check_task)
        else:
            Thread(target=check_task, daemon=True).start()
    
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
