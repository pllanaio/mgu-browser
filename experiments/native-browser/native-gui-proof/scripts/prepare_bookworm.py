#!/usr/bin/env python3
"""Prepare private runtime paths. Original signed packages remain unchanged in bookworm-debs."""
import hashlib,json,pathlib,subprocess,shutil
if any((p/'SOURCE_ONLY').is_file()for p in pathlib.Path(__file__).resolve().parents):raise SystemExit('Historical fixture script: copy it to the explicit external workspace documented in native-gui-proof/README.md before running; outputs do not belong in the source-only bundle.')
BASE=pathlib.Path(__file__).resolve().parent;ROOT=BASE/'bookworm-root';LOADER=ROOT/'lib/x86_64-linux-gnu/ld-linux-x86-64.so.2';PATCH=BASE/'bookworm-patchelf-tool'
shutil.copy2(ROOT/'usr/bin/patchelf',PATCH)
LP=':'.join(str(ROOT/p)for p in ['lib/x86_64-linux-gnu','usr/lib/x86_64-linux-gnu','lib','usr/lib']);changes=[]
for p in ROOT.rglob('*'):
 if not p.is_file() or p.is_symlink():continue
 try:
  with p.open('rb')as f:magic=f.read(4)
 except OSError:continue
 if magic!=b'\x7fELF' or p==LOADER:continue
 # Only dynamic ELF files have a modifiable RPATH. Kernel modules and non-dynamic objects are ignored.
 r=subprocess.run([str(PATCH),'--print-rpath',str(p)],capture_output=True,text=True)
 if r.returncode:continue
 before=hashlib.sha256(p.read_bytes()).hexdigest()
 interp=subprocess.run([str(PATCH),'--print-interpreter',str(p)],capture_output=True,text=True)
 args=[str(PATCH),'--set-rpath',LP]
 if not interp.returncode:args+=['--set-interpreter',str(LOADER)]
 args+=[str(p)];subprocess.run(args,check=True)
 changes.append({'path':str(p.relative_to(ROOT)),'originalSha256':before,'runtimeSha256':hashlib.sha256(p.read_bytes()).hexdigest(),'interpreter':str(LOADER)if not interp.returncode else None,'runpath':LP})
(BASE/'bookworm-runtime-patches.json').write_text(json.dumps(changes,indent=2));print('Configured dynamic ELF files',len(changes),flush=True)
for p in (ROOT/'usr/share/dbus-1/services').glob('*.service'):
 text=p.read_text();text=text.replace('Exec=/usr/','Exec='+str(ROOT)+'/usr/').replace('Exec=/bin/','Exec='+str(ROOT)+'/bin/');p.write_text(text)
schemas=ROOT/'usr/share/glib-2.0/schemas';subprocess.run([str(ROOT/'usr/bin/glib-compile-schemas'),str(schemas)],check=True)
pix=ROOT/'usr/lib/x86_64-linux-gnu/gdk-pixbuf-2.0/2.10.0';loaders=sorted(str(p)for p in (pix/'loaders').glob('*.so'));r=subprocess.run([str(ROOT/'usr/lib/x86_64-linux-gnu/gdk-pixbuf-2.0/gdk-pixbuf-query-loaders')]+loaders,check=True,capture_output=True);(pix/'loaders.cache').write_bytes(r.stdout)
cache=BASE/'bookworm-font-cache';cache.mkdir(exist_ok=True)
(BASE/'bookworm-fonts.conf').write_text('<?xml version="1.0"?><!DOCTYPE fontconfig SYSTEM "fonts.dtd"><fontconfig><dir>'+str(ROOT/'usr/share/fonts')+'</dir><cachedir>'+str(cache)+'</cachedir><config><rescan><int>0</int></rescan></config></fontconfig>')
(BASE/'bookworm-dbus.conf').write_text('<!DOCTYPE busconfig PUBLIC "-//freedesktop//DTD D-Bus Bus Configuration 1.0//EN" "http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd"><busconfig><type>session</type><listen>unix:tmpdir='+str(BASE)+'</listen><auth>EXTERNAL</auth><servicedir>'+str(ROOT/'usr/share/dbus-1/services')+'</servicedir><policy context="default"><allow send_destination="*" eavesdrop="true"/><allow eavesdrop="true"/><allow own="*"/></policy></busconfig>')
shim=BASE/'xkb_private_path.c';shim.write_text('#define _GNU_SOURCE\n#include <dlfcn.h>\n#include <stdlib.h>\n__attribute__((constructor)) static void configure_private_xkb(void) { char **path = (char **)dlsym(RTLD_DEFAULT, "XkbBinDirectory"); const char *configured = getenv("MGU_XKB_BIN_DIR"); if (path && configured && configured[0] == \'/\') *path = (char *)configured; }\n')
subprocess.run(['gcc','-shared','-fPIC','-O2','-Wl,-z,relro,-z,now','-o',str(BASE/'xkb_private_path.so'),str(shim),'-ldl'],check=True)
env={'PATH':str(ROOT/'usr/bin')+':'+str(ROOT/'bin'),'XDG_DATA_DIRS':str(ROOT/'usr/share'),'GSETTINGS_SCHEMA_DIR':str(schemas),'GDK_PIXBUF_MODULE_FILE':str(pix/'loaders.cache'),'GDK_PIXBUF_MODULEDIR':str(pix/'loaders'),'FONTCONFIG_FILE':str(BASE/'bookworm-fonts.conf'),'FONTCONFIG_PATH':str(ROOT/'etc/fonts'),'XKB_CONFIG_ROOT':str(ROOT/'usr/share/X11/xkb'),'MGU_XKB_BIN_DIR':str(ROOT/'usr/bin'),'GTK_PATH':str(ROOT/'usr/lib/x86_64-linux-gnu/gtk-3.0'),'GTK_EXE_PREFIX':str(ROOT/'usr'),'GTK_DATA_PREFIX':str(ROOT/'usr')}
(BASE/'bookworm-env.json').write_text(json.dumps(env,indent=2));print('Prepared schemas, pixbuf cache, fonts, D-Bus, private XKB shim and environment',flush=True)
