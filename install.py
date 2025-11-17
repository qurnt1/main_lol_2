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
        # Tente de vérifier l'installation avec 'pip show'
        subprocess.run(
            [sys.executable, "-m", "pip", "show", package_name],
            capture_output=True, text=True, check=True, encoding='utf-8'
        )
        print(f"{package_name} est déjà installé.")
    except subprocess.CalledProcessError:
        # Le package n'est pas trouvé, on l'installe
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
            sys.exit(1) # Quitte si PyInstaller ne peut pas être installé

def main():
    print("--- Début du script d'installation ---")
    
    # --- 1. Installation de PyInstaller ---
    check_and_install("pyinstaller")

    # --- 2. Définition des chemins ---
    # Chemin de ce script (install.py)
    # Gère le cas où le script est lancé depuis un IDE (où __file__ n'existe pas)
    try:
        script_path = os.path.abspath(__file__)
    except NameError:
        # Si __file__ n'est pas défini (ex: REPL, certains IDE)
        script_path = os.path.abspath(sys.argv[0])
        
    # Le dossier racine du projet EST le dossier où se trouve ce script
    root_dir = os.path.dirname(script_path)

    print(f"Dossier racine du projet : {root_dir}")

    # --- 3. Changement du répertoire de travail ---
    # On se place à la racine du projet
    os.chdir(root_dir)
    print(f"Répertoire de travail actuel : {os.getcwd()}")

    # --- 4. Définition des arguments PyInstaller ---
    # Tous les arguments sont codés en dur ici.
    # Les chemins relatifs (.\) seront résolus à partir de la racine du projet (root_dir)
    raw_args = [
        '--onefile',
        '--windowed',
        '--name', 'OTP LOL',
        '--icon', r'.\config\imgs\garen.ico',
        '--add-data', r'.\config;config',
        '--collect-all', 'ttkbootstrap',
        '--hidden-import=keyboard',
        '--hidden-import=pygame.mixer',
        '--hidden-import=pygame.sndarray',
        '--hidden-import=psutil',
        '--hidden-import=urllib3',
        '--hidden-import=pystray',
        '--hidden-import=PIL.Image',
        '--hidden-import=PIL.ImageTk',
        'app.py' # Le script principal
    ]
    
    # --- 5. Pré-traitement des arguments (Conversion en chemins absolus) ---
    print("Pré-traitement des chemins relatifs...")
    processed_args = []
    app_name = None # Variable pour stocker le nom de l'application (--name)
    
    arg_iter = iter(raw_args)
    for arg in arg_iter:
        if arg == '--add-data':
            try:
                # 'value' est ".\config;config"
                value = next(arg_iter) 
                parts = value.split(';')
                
                if len(parts) > 0:
                    src_path = parts[0]
                    dest_path = parts[1] if len(parts) > 1 else os.path.basename(src_path)
                    
                    # Convertit le chemin source en absolu (CWD est root_dir)
                    abs_src_path = os.path.abspath(src_path)
                    
                    processed_args.append(arg)
                    # Utilisation de os.pathsep pour la compatibilité (même si PyInstaller préfère ';')
                    processed_args.append(f"{abs_src_path}{os.pathsep}{dest_path}")
                    print(f"  > Chemin --add-data résolu : {abs_src_path}")
                else:
                    processed_args.extend([arg, value])
            except StopIteration:
                processed_args.append(arg) 

        elif arg == '--icon':
            try:
                rel_path = next(arg_iter) # ex: ".\config\imgs\garen.ico"
                abs_path = os.path.abspath(rel_path) # Résoudre depuis root_dir
                
                processed_args.extend([arg, abs_path]) # Utiliser le chemin absolu
                print(f"  > Chemin --icon résolu : {abs_path}")
            except StopIteration:
                processed_args.append(arg)
        
        elif arg == '--name':
            try:
                name_value = next(arg_iter)
                app_name = name_value
                processed_args.extend([arg, name_value])
                print(f"  > Nom de l'application défini : {app_name}")
            except StopIteration:
                processed_args.append(arg)
        
        elif arg.endswith('.py'):
            # Gérer le fichier .py principal (ex: app.py)
            abs_path = os.path.abspath(arg)
            processed_args.append(abs_path)
            # Si --name n'est pas utilisé, le nom de l'EXE sera basé sur ce script
            if not app_name:
                app_name = os.path.splitext(os.path.basename(abs_path))[0]
            print(f"  > Fichier principal résolu : {abs_path}")
        
        else:
            # L'argument n'est pas un chemin à traiter (ex: --onefile, --hidden-import)
            processed_args.append(arg)


    if not app_name:
        print("ERREUR: Impossible de déterminer le nom de l'application (--name non trouvé).")
        sys.exit(1)

    # --- 6. Construction et exécution de la commande PyInstaller ---
    py_command = [sys.executable, "-m", "PyInstaller"]
    py_command.extend(processed_args) 
    
    # Définition des chemins de sortie DANS le dossier racine
    dist_path = os.path.join(root_dir, 'dist')
    build_path = os.path.join(root_dir, 'build')
    
    # Ajout des arguments pour forcer les dossiers de sortie
    py_command.extend([
        "--clean", # <-- FORCE LE NETTOYAGE AVANT LE BUILD
        f"--distpath={dist_path}",
        f"--workpath={build_path}",
        f"--specpath={root_dir}" # On met aussi le .spec à la racine
    ])

    print("\n--- Commande PyInstaller finale (pour débogage) ---")
    # A décommenter si besoin de voir la commande exacte
    # print(" ".join(f'"{c}"' if " " in c else c for c in py_command))
    
    print("\n--- Lancement de PyInstaller (cela peut prendre un moment) ---")
    print("La sortie de PyInstaller s'affichera ci-dessous en temps réel :\n")
    
    # ######################################################################
    # # DÉBUT DE LA MODIFICATION
    # ######################################################################
    
    # Au lieu de Popen et du spinner (qui causaient un deadlock),
    # nous utilisons subprocess.run().
    # C'est un appel bloquant (le script attend la fin) et,
    # en *omettant* 'capture_output=True', il envoie
    # le stdout et le stderr de PyInstaller directement à la console.
    # C'est la meilleure "barre de progression" que vous puissiez avoir.
    
    try:
        # check=True : Lèvera une exception si PyInstaller échoue (code de retour != 0)
        # text=True, encoding, errors : Assure une gestion correcte des textes
        result = subprocess.run(
            py_command,
            check=True,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        
        # Si on arrive ici, c'est que le code de retour était 0 (succès)
        print("\n--- PyInstaller a terminé avec succès ---")

    except subprocess.CalledProcessError as e:
        # PyInstaller a échoué.
        print("\n--- ERREUR PyInstaller ---")
        print("Le build a échoué.")
        # Pas besoin d'afficher e.stderr, car il a déjà été
        # affiché en direct dans la console par subprocess.run()
        print(f"Code de retour de PyInstaller : {e.returncode}")
        sys.exit(1)

    except Exception as e:
        # Une autre erreur, ex: PyInstaller non trouvé (bien que vérifié avant)
        print(f"\n--- ERREUR Inattendue lors du lancement de PyInstaller ---")
        print(str(e))
        sys.exit(1)

    # ######################################################################
    # # FIN DE LA MODIFICATION
    # ######################################################################
    
    # --- 7. Déplacement de l'exécutable à la racine du projet ---
    
    # Construction du nom de fichier final (inclut l'extension .exe sous Windows)
    exe_filename = f"{app_name}.exe" if sys.platform == "win32" else app_name
    
    source_path = os.path.join(dist_path, exe_filename)
    target_path = os.path.join(root_dir, exe_filename)
    
    print(f"\n--- Déplacement de l'exécutable vers la racine du projet ---")
    
    if os.path.exists(source_path):
        try:
            # Déplacement de l'EXE
            shutil.move(source_path, target_path)
            print(f"SUCCÈS : L'exécutable a été déplacé vers : {target_path}")
            
            # Optionnel : Nettoyer les dossiers temporaires
            print(f"Nettoyage des dossiers temporaires (build, dist)...")
            try:
                shutil.rmtree(build_path)
                shutil.rmtree(dist_path)
                # On pourrait aussi supprimer le .spec
                spec_file = os.path.join(root_dir, f"{app_name}.spec")
                if os.path.exists(spec_file):
                    os.remove(spec_file)
                print("Nettoyage terminé.")
            except Exception as e:
                print(f"ATTENTION : N'a pas pu nettoyer les dossiers temporaires : {e}")
                
        except Exception as e:
            print(f"ERREUR lors du déplacement de l'exécutable : {e}")
            print(f"Le fichier est toujours disponible dans : {source_path}")
    else:
        print(f"ATTENTION : Fichier exécutable non trouvé à l'emplacement prévu : {source_path}")
        print("Vérifiez la sortie de PyInstaller ou l'argument --name.")

    # --- 8. FIN ---
    print("\n--- Script terminé ---")

if __name__ == "__main__":
    main()
    # Pause pour Windows afin de voir les messages dans la console
    if sys.platform == "win32":
        print("\nAppuyez sur Entrée pour quitter...")
        try:
            input()
        except EOFError:
            pass