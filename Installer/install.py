import os
import subprocess
import sys
import shlex
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
    
    # --- 5. Pré-traitement des arguments (Conversion en chemins absolus) ---
    print("Pré-traitement des chemins relatifs...")
    processed_args = []
    
    arg_iter = iter(args)
    for arg in arg_iter:
        if arg == '--add-data':
            try:
                # 'value' est ".\config;config"
                value = next(arg_iter) 
                parts = value.split(';')
                if len(parts) > 0:
                    src_path = parts[0]
                    dest_path = parts[1] if len(parts) > 1 else os.path.basename(src_path)
                    
                    # Convertit le chemin source en absolu
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
                rel_path = next(arg_iter) # ex: ".\config\imgs\garen.ico"
                abs_path = os.path.abspath(rel_path) # Résoudre !
                
                processed_args.append(arg)
                processed_args.append(abs_path) # Utiliser le chemin absolu
                print(f"  > Chemin --icon résolu : {abs_path}")
            except StopIteration:
                processed_args.append(arg)
        
        elif arg.endswith('.py'):
            # Gérer le fichier .py principal (ex: app.py)
            abs_path = os.path.abspath(arg)
            processed_args.append(abs_path)
            print(f"  > Fichier principal résolu : {abs_path}")
        
        else:
            # L'argument n'est pas un chemin à traiter (ex: --onefile, --name, --hidden-import)
            processed_args.append(arg)
            # Si l'argument attend une valeur (comme --name), on la prend
            if arg in ('--name'):
                try:
                    processed_args.append(next(arg_iter))
                except StopIteration:
                    pass

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
    # print(f"Commande : {' '.join(py_command)}") # Décommentez pour déboguer
    
    try:
        # On exécute la commande
        subprocess.run(py_command, check=True, text=True, encoding='utf-8')
        print("--- PyInstaller a terminé avec succès ---")
    except subprocess.CalledProcessError as e:
        print("--- ERREUR PyInstaller ---")
        print("Le build a échoué.")
        sys.exit(1)
    
    # --- 7. FIN ---
    print("\n--- Script terminé ---")
    print(f"L'exécutable se trouve dans : {dist_path}")

if __name__ == "__main__":
    main()
    if sys.platform == "win32":
        print("\nAppuyez sur Entrée pour quitter...")
        os.system("pause > nul")