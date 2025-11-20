import os
import subprocess
import sys
import shutil
import time

def main():
    print("--- Début du script d'installation (Mode FICHIER UNIQUE / ONEFILE) ---")
    
    # Définition des chemins
    try:
        script_path = os.path.abspath(__file__)
    except NameError:
        script_path = os.path.abspath(sys.argv[0])
        
    root_dir = os.path.dirname(script_path)
    os.chdir(root_dir)

    # Arguments PyInstaller
    raw_args = [
        '--onefile',     # <--- ON REPASSE EN ONEFILE
        '--windowed',    
        '--noconfirm',   
        '--name', 'OTP LOL',
        '--icon', r'.\config\imgs\garen.ico',
        # C'est ici qu'on INCLUT les images DANS l'exe
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
        'app.py'
    ]
    
    # Pré-traitement des arguments (chemins absolus)
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
                    dest_path = parts[1]
                    abs_src_path = os.path.abspath(src_path)
                    processed_args.append(arg)
                    processed_args.append(f"{abs_src_path}{os.pathsep}{dest_path}")
                else:
                    processed_args.extend([arg, value])
            except StopIteration:
                processed_args.append(arg) 
        elif arg == '--icon':
            processed_args.extend([arg, os.path.abspath(next(arg_iter))])
        elif arg == '--name':
            val = next(arg_iter)
            app_name = val
            processed_args.extend([arg, val])
        elif arg.endswith('.py'):
            processed_args.append(os.path.abspath(arg))
            if not app_name:
                app_name = os.path.splitext(os.path.basename(arg))[0]
        else:
            processed_args.append(arg)

    # Lancement PyInstaller
    py_command = [sys.executable, "-m", "PyInstaller"] + processed_args
    
    dist_path = os.path.join(root_dir, 'dist')
    build_path = os.path.join(root_dir, 'build')
    
    py_command.extend(["--clean", f"--distpath={dist_path}", f"--workpath={build_path}", f"--specpath={root_dir}"])

    print("\n--- Compilation en cours... ---")
    try:
        subprocess.run(py_command, check=True, text=True, encoding='utf-8', errors='replace')
    except subprocess.CalledProcessError:
        print("ERREUR COMPILATION"); sys.exit(1)

    # Déplacement du fichier EXE
    exe_name = f"{app_name}.exe"
    source = os.path.join(dist_path, exe_name)
    target = os.path.join(root_dir, exe_name)
    
    print(f"\n--- Déplacement de l'EXE ---")
    if os.path.exists(source):
        if os.path.exists(target):
            os.remove(target) # On supprime l'ancien
        
        shutil.move(source, target)
        print(f"✅ SUCCÈS : {target}")
        
        # Nettoyage
        try:
            shutil.rmtree(build_path)
            shutil.rmtree(dist_path)
            if os.path.exists(os.path.join(root_dir, f"{app_name}.spec")):
                os.remove(os.path.join(root_dir, f"{app_name}.spec"))
            # Nettoyage de l'ancien dossier s'il existe encore
            if os.path.exists(os.path.join(root_dir, app_name)):
                shutil.rmtree(os.path.join(root_dir, app_name))
        except: pass
    else:
        print("Erreur : EXE non trouvé.")

if __name__ == "__main__":
    main()