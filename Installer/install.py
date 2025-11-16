import os
import subprocess
import sys
import shlex
import time
import shutil # Ajout de l'import pour déplacer le fichier

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
    script_path = os.path.abspath(__file__)
    installer_dir = os.path.dirname(script_path)
    root_dir = os.path.dirname(installer_dir)
    pyinstaller_txt_path = os.path.join(installer_dir, "PyInstaller.txt")

    print(f"Dossier racine du projet : {root_dir}")
    print(f"Dossier d'installation : {installer_dir}")

    # --- 3. Changement du répertoire de travail ---
    # On se place à la racine du projet pour que les chemins relatifs soient corrects
    os.chdir(root_dir)
    print(f"Répertoire de travail actuel : {os.getcwd()}")

    # --- 4. Lecture et analyse de PyInstaller.txt ---
    if not os.path.exists(pyinstaller_txt_path):
        print(f"ERREUR: Fichier {pyinstaller_txt_path} non trouvé !")
        sys.exit(1)

    print("Lecture de PyInstaller.txt...")
    with open(pyinstaller_txt_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Nettoyage de la commande
    cleaned_content = content.replace("pyinstaller", "").replace("`\n", " ").replace("`", " ")
    args = shlex.split(cleaned_content)
    
    # --- 5. Pré-traitement des arguments (Conversion en chemins absolus et capture du nom) ---
    print("Pré-traitement des chemins relatifs...")
    processed_args = []
    app_name = None # Variable pour stocker le nom de l'application (--name)
    
    arg_iter = iter(args)
    for arg in arg_iter:
        if arg == '--add-data':
            try:
                # 'value' est ".\config;config"
                value = next(arg_iter) 
                parts = value.split(';')
                
                # S'assurer que 'value' contient au moins la source (parts[0])
                if len(parts) > 0:
                    src_path = parts[0]
                    dest_path = parts[1] if len(parts) > 1 else os.path.basename(src_path)
                    
                    # Convertit le chemin source en absolu
                    abs_src_path = os.path.abspath(src_path)
                    
                    processed_args.append(arg)
                    processed_args.append(f"{abs_src_path};{dest_path}")
                    print(f"  > Chemin --add-data résolu : {abs_src_path}")
                else:
                    processed_args.append(arg)
                    processed_args.append(value)
            except StopIteration:
                processed_args.append(arg) 

        elif arg == '--icon':
            try:
                rel_path = next(arg_iter) # ex: ".\config\imgs\garen.ico"
                abs_path = os.path.abspath(rel_path) # Résoudre !
                
                processed_args.append(arg)
                processed_args.append(abs_path) # Utiliser le chemin absolu
                print(f"  > Chemin --icon résolu : {abs_path}")
            except StopIteration:
                processed_args.append(arg)
        
        elif arg == '--name':
            try:
                name_value = next(arg_iter)
                app_name = name_value       # Capture le nom de l'application pour le déplacement
                processed_args.append(arg)
                processed_args.append(name_value)
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
    
    # Définition des chemins de sortie DANS le dossier 'Installer'
    dist_path = os.path.join(installer_dir, 'dist')
    build_path = os.path.join(installer_dir, 'build')
    
    # Ajout des arguments pour forcer les dossiers de sortie
    py_command.extend([
        f"--distpath={dist_path}",
        f"--workpath={build_path}",
        f"--specpath={installer_dir}" # On met aussi le .spec dans 'Installer'
    ])

    print("\n--- Lancement de PyInstaller ---")
    
    try:
        # On exécute la commande
        subprocess.run(py_command, check=True, text=True, encoding='utf-8')
        print("--- PyInstaller a terminé avec succès ---")
    except subprocess.CalledProcessError as e:
        print("--- ERREUR PyInstaller ---")
        print("Le build a échoué.")
        sys.exit(1)
    
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
        os.system("pause > nul")