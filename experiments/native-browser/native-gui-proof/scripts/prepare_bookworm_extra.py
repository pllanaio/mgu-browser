#!/usr/bin/env python3
import json,os,pathlib,shutil,subprocess
if any((p/'SOURCE_ONLY').is_file()for p in pathlib.Path(__file__).resolve().parents):raise SystemExit('Historical fixture script: copy it to the explicit external workspace documented in native-gui-proof/README.md before running; outputs do not belong in the source-only bundle.')
B=pathlib.Path(__file__).resolve().parent;R=B/'bookworm-root';A=B/'bookworm-extra';env=dict(os.environ);env.update(json.loads((B/'bookworm-env.json').read_text()));env.update(json.loads((B/'bookworm-assets-env.json').read_text()));schemas=B/'bookworm-extra-schemas';schemas.mkdir(exist_ok=True)
for source in [R/'usr/share/glib-2.0/schemas',A/'usr/share/glib-2.0/schemas']:
 if source.exists():
  for p in source.iterdir():
   if p.is_file()and p.suffix in ['.xml','.override']:shutil.copy2(p,schemas/p.name)
subprocess.run([str(R/'usr/bin/glib-compile-schemas'),str(schemas)],check=True)
plugins=sorted(str(p)for d in [R,A]for p in (d/'usr/lib/x86_64-linux-gnu/gdk-pixbuf-2.0/2.10.0/loaders').glob('*.so'));q=R/'usr/lib/x86_64-linux-gnu/gdk-pixbuf-2.0/gdk-pixbuf-query-loaders';p=subprocess.run([str(q)]+plugins,env=env,capture_output=True,check=True);cache=B/'bookworm-extra-loaders.cache';cache.write_bytes(p.stdout);assert b'"svg"'in p.stdout
overlay={'XDG_DATA_DIRS':str(A/'usr/share')+':'+env['XDG_DATA_DIRS'],'GSETTINGS_SCHEMA_DIR':str(schemas),'GDK_PIXBUF_MODULE_FILE':str(cache)};env.update(overlay);(B/'bookworm-extra-env.json').write_text(json.dumps(overlay,indent=2))
icon=R/'usr/share/icons/Adwaita/scalable/actions/go-next-symbolic.svg';out=B/'bookworm-svg-proof.png';p=subprocess.run([str(R/'usr/bin/gdk-pixbuf-thumbnailer'),'-s','32',str(icon),str(out)],env=env,capture_output=True,text=True);proof={'success':p.returncode==0,'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'source':str(icon),'thumbnail':str(out),'thumbnailBytes':out.stat().st_size if out.exists()else 0};(B/'bookworm-extra-proof.json').write_text(json.dumps(proof,indent=2));assert proof['success'],proof
core=(B/'bookworm-dbus.conf').read_text();(B/'bookworm-extra-dbus.conf').write_text(core.replace('<servicedir>','<servicedir>'+str(A/'usr/share/dbus-1/services')+'</servicedir><servicedir>',1))
for f in (A/'usr/share/dbus-1/accessibility-services').glob('*.service'):
 t=f.read_text().replace('Exec=/usr/','Exec='+str(A)+'/usr/');f.write_text(t)
access=(A/'usr/share/defaults/at-spi2/accessibility.conf').read_text().replace('/usr/share/dbus-1/accessibility-services',str(A/'usr/share/dbus-1/accessibility-services')).replace('<listen>unix:dir=/tmp</listen>','<listen>unix:dir='+str(B)+'</listen>');(B/'bookworm-extra-accessibility.conf').write_text(access)
print(json.dumps(proof,indent=2))
