#!/usr/bin/env python3
"""Generate private non-ELF GTK runtime assets; does not modify the core runtime."""
import json,os,pathlib,shutil,subprocess
if any((p/'SOURCE_ONLY').is_file()for p in pathlib.Path(__file__).resolve().parents):raise SystemExit('Historical fixture script: copy it to the explicit external workspace documented in native-gui-proof/README.md before running; outputs do not belong in the source-only bundle.')
BASE=pathlib.Path(__file__).resolve().parent;ROOT=BASE/'bookworm-root';ASSETS=BASE/'bookworm-assets-candidate';env=dict(os.environ);env.update(json.loads((BASE/'bookworm-env.json').read_text()));(ASSETS/'share').mkdir(parents=True,exist_ok=True)
icon=ROOT/'usr/share/icons/Adwaita/16x16/status/image-missing.png';thumbnailer=ROOT/'usr/bin/gdk-pixbuf-thumbnailer'
before=subprocess.run([str(thumbnailer),'-s','32',str(icon),str(BASE/'pixbuf-before.png')],env=env,capture_output=True,text=True)
shutil.copytree(ROOT/'usr/share/mime',ASSETS/'share/mime',dirs_exist_ok=True);env['XDG_DATA_DIRS']=str(ASSETS/'share')+':'+str(ROOT/'usr/share')
subprocess.run([str(ROOT/'usr/bin/update-mime-database'),str(ASSETS/'share/mime')],env=env,check=True)
for name in ['Adwaita','hicolor']:
 dest=ASSETS/'share/icons'/name;shutil.copytree(ROOT/'usr/share/icons'/name,dest,dirs_exist_ok=True)
 subprocess.run([str(ROOT/'usr/bin/gtk-update-icon-cache'),'--force','--ignore-theme-index',str(dest)],env=env,check=True)
after=subprocess.run([str(thumbnailer),'-s','32',str(icon),str(BASE/'pixbuf-after.png')],env=env,capture_output=True,text=True);assert before.returncode==1 and after.returncode==0,(before,after)
overlay={'XDG_DATA_DIRS':env['XDG_DATA_DIRS']};(BASE/'bookworm-assets-env.json').write_text(json.dumps(overlay,indent=2));proof={'before':{'returncode':before.returncode,'stderr':before.stderr},'after':{'returncode':after.returncode,'stderr':after.stderr,'thumbnailBytes':(BASE/'pixbuf-after.png').stat().st_size},'fix':'Compile private MIME database from authenticated package XML and generate private icon caches','runtimeUnchanged':True,'overlayEnvironment':overlay};(BASE/'bookworm-assets-proof.json').write_text(json.dumps(proof,indent=2));print(json.dumps(proof,indent=2))
