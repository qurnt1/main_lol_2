import os
import sys
import subprocess
import shlex
import time

# --- VÉRIFICATION ET REDÉMARRAGE POUR WINSHELL ---
# On tente d'importer winshell dès le début.
try:
    import winshell
except ImportError:
    # S'il n'est pas là, on l'installe
    print("Module 'winshell' non trouvé. Tentative d'installation...")
    try:
        # On exécute pip pour l'installer
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "winshell"],
            check=True, capture_output=True, text=True, encoding='utf-8'
        )
        print("'winshell' a été installé avec succès.")
        print("Redémarrage automatique du script pour charger le module...")
        
        # C'EST LA MAGIE : On relance ce script (install.py)
        # et on quitte l'instance actuelle.
        os.execv(sys.executable, [sys.executable] + sys.argv)
        
    except subprocess.CalledProcessError as e:
        print(f"ERREUR: Impossible d'installer 'winshell'.")
        print(e.stderr)
        if sys.platform == "win32":
            os.system("pause")
        sys.exit(1)

# Si le script arrive ici, cela signifie que 'winshell' est
# importé et disponible pour le reste de l'exécution.

# -------------------------------------------------

def check_and_install(package_name):
    """
    Vérifie si un package est installé, sinon l'installe via pip.
    (Simplifié, car winshell est déjà géré)
    """
    if package_name == "winshell":
        print("winshell est déjà chargé.")
        return

    print(f"Vérification de {package_name}...")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "show", package_name],
            capture_output=True, text=True, check=True, encoding='utf-8'
        )
        print(f"{package_name} est déjà installé.")
    except subprocess.CalledProcessError:
        print(f"{package_name} non trouvé. Installation en cours...")
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", package_name],
                check=True, capture_output=True, text=True, encoding='utf-8'
            )
            print(f"{package_name} a été installé avec succès.")
        except subprocess.CalledProcessError as e:
            print(f"ERREUR: Impossible d'installer {package_name}.")
            print(e.stderr)
            sys.exit(1)

def create_shortcut(app_name, exe_path, icon_path):
    """
    Crée un raccourci sur le bureau Windows.
    """
    # L'import local n'est plus nécessaire car il est fait en haut.
    # try:
    #     import winshell
    # except ImportError:
    #     print("ERREUR: Le module 'winshell' n'a pas pu être importé...")
    #     return

    desktop = winshell.desktop()
    shortcut_path = os.path.join(desktop, f"{app_name}.lnk")
    
    print(f"Création du raccourci sur le bureau : {shortcut_path}")
    
    try:
        with winshell.shortcut(shortcut_path) as shortcut:
            shortcut.path = exe_path
            shortcut.working_directory = os.path.dirname(exe_path)
            shortcut.description = f"Raccourci pour {app_name}"
            
            if icon_path and os.path.exists(icon_path):
                print(f"Assignation de l'icône : {icon_path}")
                shortcut.icon_location = (icon_path, 0)
            elif icon_path:
                print(f"AVERTISSEMENT: Chemin d'icône non trouvé : {icon_path}")
                
        print("Raccourci créé avec succès.")
            
    except Exception as e:
        print(f"ERREUR lors de la création du raccourci : {e}")


def main():
    print("--- Début du script d'installation ---")
    
    # --- 1. Installation des dépendances ---
    # 'winshell' est géré au démarrage. Il ne reste que 'pyinstaller'.
    check_and_install("pyinstaller")

    # --- 2. Définition des chemins ---
    script_path = os.path.abspath(__file__)
    installer_dir = os.path.dirname(script_path)
    root_dir = os.path.dirname(installer_dir)
    pyinstaller_txt_path = os.path.join(installer_dir, "PyInstaller.txt")

    print(f"Dossier racine du projet : {root_dir}")
    print(f"Dossier d'installation : {installer_dir}")

    # --- 3. Changement du répertoire de travail ---
    os.chdir(root_dir)
    print(f"Répertoire de travail actuel : {os.getcwd()}")

    # --- 4. Lecture et analyse de PyInstaller.txt ---
    if not os.path.exists(pyinstaller_txt_path):
        print(f"ERREUR: Fichier {pyinstaller_txt_path} non trouvé !")
        sys.exit(1)

    print("Lecture de PyInstaller.txt...")
    with open(pyinstaller_txt_path, 'r', encoding='utf-8') as f:
        content = f.read()

    cleaned_content = content.replace("pyinstaller", "").replace("`\n", " ").replace("`", " ")
    args = shlex.split(cleaned_content)
    
    # --- 5. Pré-traitement des arguments pour PyInstaller ---
    print("Pré-traitement des chemins relatifs...")
    processed_args = []
    
    app_name = "MonApplication" # Nom par défaut
    icon_abs_path = None      # Chemin ABSOLU de l'icône

    arg_iter = iter(args)
    for arg in arg_iter:
        if arg == '--add-data':
            try:
                value = next(arg_iter) 
                parts = value.split(';')
                if len(parts) > 0:
                    src_path = parts[0]
                    dest_path = parts[1] if len(parts) > 1 else os.path.basename(src_path)
                    abs_src_path = os.path.abspath(src_path)
                    
                    processed_args.append(arg)
                    processed_args.append(f"{abs_src_path};{dest_path}")
                    print(f"  > Chemin --add-data résolu : {abs_src_path}")
                else:
                    processed_args.append(arg)
                    processed_args.append(value)
            except StopIteration:
                processed_args.append(arg) 

        elif arg == '--icon':
            try:
                rel_path = next(arg_iter)
                icon_abs_path = os.path.abspath(rel_path)
                
                processed_args.append(arg)
                processed_args.append(icon_abs_path)
                print(f"  > Chemin --icon résolu : {icon_abs_path}")
            except StopIteration:
                processed_args.append(arg)
        
        elif arg == '--name':
            try:
                app_name = next(arg_iter)
                processed_args.append(arg)
                processed_args.append(app_name)
            except StopIteration:
                processed_args.append(arg)
        
        elif arg.endswith('.py'):
            abs_path = os.path.abspath(arg)
            processed_args.append(abs_path)
            print(f"  > Fichier principal résolu : {abs_path}")
        
        else:
            processed_args.append(arg)

    print(f"Nom de l'application détecté : {app_name}")
    print(f"Chemin de l'icône détecté : {icon_abs_path}")


    # --- 6. Construction et exécution de la commande PyInstaller ---
    py_command = [sys.executable, "-m", "PyInstaller"]
    py_command.extend(processed_args) 
    
    dist_path = os.path.join(installer_dir, 'dist')
    build_path = os.path.join(installer_dir, 'build')
    
    py_command.extend([
        f"--distpath={dist_path}",
        f"--workpath={build_path}",
        f"--specpath={installer_dir}"
    ])

    print("\n--- Lancement de PyInstaller ---")
    
    try:
        subprocess.run(py_command, check=True, text=True, encoding='utf-8')
        print("--- PyInstaller a terminé avec succès ---")
    except subprocess.CalledProcessError as e:
        print("--- ERREUR PyInstaller ---")
        print("Le build a échoué.")
        sys.exit(1)
    
    # --- 7. Création du raccourci ---
    print("\n--- Création du raccourci ---")
    
    exe_path = os.path.join(dist_path, f"{app_name}.exe")

    if not os.path.exists(exe_path):
        print(f"ERREUR: L'exécutable n'a pas été trouvé à : {exe_path}")
    else:
        print(f"Exécutable trouvé : {exe_path}")
        create_shortcut(app_name, exe_path, icon_abs_path)

    print("\n--- Script terminé ---")
    print(f"L'exécutable se trouve dans : {dist_path}")

if __name__ == "__main__":
    main()
    if sys.platform == "win32":
        print("\nAppuyez sur Entrée pour quitter...")
        os.system("pause > nul")