import os
import subprocess
import sys
import shutil

def main():
    print("=" * 60)
    print("   MAIN LOL - Script de Compilation (v7.0)")
    print("   Architecture Modulaire (src/)")
    print("=" * 60)
    
    # Définition des chemins
    try:
        script_path = os.path.abspath(__file__)
    except NameError:
        script_path = os.path.abspath(sys.argv[0])
        
    root_dir = os.path.dirname(script_path)
    os.chdir(root_dir)

    # ─────────────────────────────────────────────────────────────────────
    # CONFIGURATION PYINSTALLER
    # ─────────────────────────────────────────────────────────────────────
    
    raw_args = [
        '--onefile',      # Fichier unique portable
        '--windowed',     # Pas de console
        '--noconfirm',    # Écraser sans confirmation
        '--name', 'OTP LOL',
        '--icon', r'.\config\imgs\garen.ico',
        
        # ─── INCLUSION DES ASSETS ───
        '--add-data', r'.\config;config',
        
        # ─── INCLUSION DU PACKAGE SRC ───
        # PyInstaller détecte automatiquement les imports, mais on force
        # l'inclusion du dossier src pour être sûr
        '--add-data', r'.\src;src',
        
        # ─── DÉPENDANCES UI ───
        '--collect-all', 'ttkbootstrap',
        
        # ─── HIDDEN IMPORTS (Modules non détectés automatiquement) ───
        # Modules du package src (pour être sûr qu'ils sont inclus)
        '--hidden-import=src',
        '--hidden-import=src.config',
        '--hidden-import=src.core',
        '--hidden-import=src.ui',
        '--hidden-import=src.utils',
        
        # Dépendances tierces
        '--hidden-import=keyboard',
        '--hidden-import=pygame',
        '--hidden-import=pygame.mixer',
        '--hidden-import=pygame.sndarray',
        '--hidden-import=psutil',
        '--hidden-import=urllib3',
        '--hidden-import=pystray',
        '--hidden-import=PIL.Image',
        '--hidden-import=PIL.ImageTk',
        '--hidden-import=PIL.ImageEnhance',
        '--hidden-import=lcu_driver',
        '--hidden-import=requests',
        
        # ─── POINT D'ENTRÉE ───
        'launcher.py'
    ]
    
    # ─────────────────────────────────────────────────────────────────────
    # PRÉ-TRAITEMENT DES ARGUMENTS (chemins absolus)
    # ─────────────────────────────────────────────────────────────────────
    
    processed_args = []
    app_name = None 
    arg_iter = iter(raw_args)
    
    for arg in arg_iter:
        if arg == '--add-data':
            try:
                value = next(arg_iter) 
                parts = value.split(';')
                if len(parts) >= 2:
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
            icon_path = next(arg_iter)
            abs_icon = os.path.abspath(icon_path)
            if os.path.exists(abs_icon):
                processed_args.extend([arg, abs_icon])
            else:
                print(f"⚠️  Icône non trouvée: {abs_icon}")
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

    # ─────────────────────────────────────────────────────────────────────
    # LANCEMENT DE PYINSTALLER
    # ─────────────────────────────────────────────────────────────────────
    
    dist_path = os.path.join(root_dir, 'dist')
    build_path = os.path.join(root_dir, 'build')
    
    py_command = [sys.executable, "-m", "PyInstaller"] + processed_args
    py_command.extend([
        "--clean", 
        f"--distpath={dist_path}", 
        f"--workpath={build_path}", 
        f"--specpath={root_dir}"
    ])

    print("\n📦 Compilation en cours...")
    print("   (Cela peut prendre quelques minutes)\n")
    
    try:
        subprocess.run(py_command, check=True, text=True, encoding='utf-8', errors='replace')
    except subprocess.CalledProcessError as e:
        print(f"\n❌ ERREUR COMPILATION: {e}")
        sys.exit(1)

    # ─────────────────────────────────────────────────────────────────────
    # DÉPLACEMENT ET NETTOYAGE
    # ─────────────────────────────────────────────────────────────────────
    
    exe_name = f"{app_name}.exe"
    source = os.path.join(dist_path, exe_name)
    target = os.path.join(root_dir, exe_name)
    
    print(f"\n📁 Déplacement de l'exécutable...")
    
    if os.path.exists(source):
        if os.path.exists(target):
            os.remove(target)
        
        shutil.move(source, target)
        print(f"\n✅ SUCCÈS : {target}")
        print(f"   Taille : {os.path.getsize(target) / (1024*1024):.1f} Mo")
        
        # Nettoyage
        print("\n🧹 Nettoyage des fichiers temporaires...")
        try:
            if os.path.exists(build_path):
                shutil.rmtree(build_path)
            if os.path.exists(dist_path):
                shutil.rmtree(dist_path)
            spec_file = os.path.join(root_dir, f"{app_name}.spec")
            if os.path.exists(spec_file):
                os.remove(spec_file)
            # Nettoyage de l'ancien dossier onedir s'il existe
            old_dir = os.path.join(root_dir, app_name)
            if os.path.exists(old_dir):
                shutil.rmtree(old_dir)
            print("   ✓ Nettoyage terminé")
        except Exception as e:
            print(f"   ⚠️ Erreur nettoyage: {e}")
    else:
        print(f"\n❌ Erreur : EXE non trouvé à {source}")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("   COMPILATION TERMINÉE")
    print("=" * 60)


if __name__ == "__main__":
    main()