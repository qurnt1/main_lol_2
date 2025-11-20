import os
import subprocess
import sys
import shutil
import time

def check_and_install(package_name):
    """
    Vérifie si un package est installé, sinon l'installe via pip.
    """
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

def main():
    print("--- Début du script d'installation (Mode DOSSIER / ONEDIR) ---")
    
    # --- 1. Installation de PyInstaller ---
    check_and_install("pyinstaller")

    # --- 2. Définition des chemins ---
    try:
        script_path = os.path.abspath(__file__)
    except NameError:
        script_path = os.path.abspath(sys.argv[0])
        
    root_dir = os.path.dirname(script_path)
    print(f"Dossier racine du projet : {root_dir}")

    # --- 3. Changement du répertoire de travail ---
    os.chdir(root_dir)

    # --- 4. Définition des arguments PyInstaller ---
    # MODIFICATION IMPORTANTE : Passage en --onedir
    raw_args = [
        '--onedir',      # <--- Créera un dossier au lieu d'un seul fichier
        '--windowed',    # Pas de console noire
        '--noconfirm',   # Ne pas demander confirmation pour écraser
        '--name', 'OTP LOL',
        '--icon', r'.\config\imgs\garen.ico',
        '--add-data', r'.\config;config', # Copie le dossier config DANS le dossier de l'exe
        '--collect-all', 'ttkbootstrap',
        '--hidden-import=keyboard',
        '--hidden-import=pygame.mixer',
        '--hidden-import=pygame.sndarray',
        '--hidden-import=psutil',
        '--hidden-import=urllib3',
        '--hidden-import=pystray',
        '--hidden-import=PIL.Image',
        '--hidden-import=PIL.ImageTk',
        'app.py'
    ]
    
    # --- 5. Pré-traitement des arguments (Conversion en chemins absolus) ---
    print("Pré-traitement des chemins relatifs...")
    processed_args = []
    app_name = None 
    
    arg_iter = iter(raw_args)
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
                    processed_args.append(f"{abs_src_path}{os.pathsep}{dest_path}")
                    print(f"  > Chemin --add-data résolu : {abs_src_path} -> {dest_path}")
                else:
                    processed_args.extend([arg, value])
            except StopIteration:
                processed_args.append(arg) 

        elif arg == '--icon':
            try:
                rel_path = next(arg_iter)
                abs_path = os.path.abspath(rel_path)
                processed_args.extend([arg, abs_path])
            except StopIteration:
                processed_args.append(arg)
        
        elif arg == '--name':
            try:
                name_value = next(arg_iter)
                app_name = name_value
                processed_args.extend([arg, name_value])
            except StopIteration:
                processed_args.append(arg)
        
        elif arg.endswith('.py'):
            abs_path = os.path.abspath(arg)
            processed_args.append(abs_path)
            if not app_name:
                app_name = os.path.splitext(os.path.basename(abs_path))[0]
        
        else:
            processed_args.append(arg)

    if not app_name:
        print("ERREUR: Impossible de déterminer le nom de l'application.")
        sys.exit(1)

    # --- 6. Exécution de PyInstaller ---
    py_command = [sys.executable, "-m", "PyInstaller"]
    py_command.extend(processed_args) 
    
    dist_path = os.path.join(root_dir, 'dist')
    build_path = os.path.join(root_dir, 'build')
    
    py_command.extend([
        "--clean",
        f"--distpath={dist_path}",
        f"--workpath={build_path}",
        f"--specpath={root_dir}"
    ])

    print("\n--- Lancement de PyInstaller (Mode Dossier) ---")
    
    try:
        result = subprocess.run(
            py_command,
            check=True,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        print("\n--- PyInstaller a terminé avec succès ---")

    except subprocess.CalledProcessError as e:
        print(f"\n--- ERREUR PyInstaller (Code {e.returncode}) ---")
        sys.exit(1)
    except Exception as e:
        print(f"\n--- ERREUR Inattendue : {e}")
        sys.exit(1)

    # --- 7. Déplacement du DOSSIER FINAL vers la racine ---
    
    # En mode --onedir, PyInstaller crée un DOSSIER portant le nom de l'app
    source_folder = os.path.join(dist_path, app_name)
    target_folder = os.path.join(root_dir, app_name)
    
    print(f"\n--- Gestion du dossier de sortie ---")
    print(f"Source : {source_folder}")
    print(f"Cible  : {target_folder}")

    if os.path.exists(source_folder):
        try:
            # Si le dossier cible existe déjà, on le supprime pour le remplacer proprement
            if os.path.exists(target_folder):
                print(f"Le dossier cible '{app_name}' existe déjà. Suppression...")
                shutil.rmtree(target_folder)
                time.sleep(1) # Petite pause pour laisser Windows libérer les fichiers

            # Déplacement du dossier complet
            shutil.move(source_folder, target_folder)
            print(f"SUCCÈS : Le dossier de l'application est prêt ici : {target_folder}")
            print(f"L'exécutable se trouve à l'intérieur : {os.path.join(target_folder, app_name + '.exe')}")
            
            # Nettoyage
            print(f"Nettoyage des dossiers temporaires...")
            try:
                shutil.rmtree(build_path)
                shutil.rmtree(dist_path)
                spec_file = os.path.join(root_dir, f"{app_name}.spec")
                if os.path.exists(spec_file):
                    os.remove(spec_file)
            except Exception as e:
                print(f"Note : Nettoyage partiel ({e})")
                
        except Exception as e:
            print(f"ERREUR lors du déplacement du dossier : {e}")
            print(f"Votre application est toujours dans : {source_folder}")
    else:
        print(f"ERREUR CRITIQUE : Le dossier généré {source_folder} est introuvable.")

    print("\n--- Terminé ---")

if __name__ == "__main__":
    main()
    if sys.platform == "win32":
        print("\nAppuyez sur Entrée pour quitter...")
        try:
            input()
        except EOFError:
            pass