#!/usr/bin/env python3
"""Prepare already-extracted, manifest-pinned optional libraries. No downloads."""
import argparse,hashlib,json,pathlib,subprocess
p=argparse.ArgumentParser();p.add_argument('--workspace',required=True);a=p.parse_args();b=pathlib.Path(a.workspace).resolve();r=b/'bookworm-root';extra=b/'bookworm-extra';loader=r/'lib/x86_64-linux-gnu/ld-linux-x86-64.so.2';patch=b/'bookworm-patchelf-tool'
if not extra.is_dir()or not patch.is_file():p.error('Explicit workspace needs prepared core and extracted optional inputs')
libpaths=':'.join(str(x)for x in [extra/'lib/x86_64-linux-gnu',extra/'usr/lib/x86_64-linux-gnu',r/'lib/x86_64-linux-gnu',r/'usr/lib/x86_64-linux-gnu',r/'lib',r/'usr/lib']);changes=[]
for f in extra.rglob('*'):
 if not f.is_file()or f.is_symlink():continue
 f.chmod(f.stat().st_mode&0o777)
 with f.open('rb')as h:magic=h.read(4)
 if magic!=b'\x7fELF':continue
 if subprocess.run([str(patch),'--print-rpath',str(f)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode:continue
 original=hashlib.sha256(f.read_bytes()).hexdigest();interp=subprocess.run([str(patch),'--print-interpreter',str(f)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);cmd=[str(patch),'--set-rpath',libpaths]
 if not interp.returncode:cmd+=['--set-interpreter',str(loader)]
 subprocess.run(cmd+[str(f)],check=True);changes.append({'path':str(f.relative_to(extra)),'originalSha256':original,'runtimeSha256':hashlib.sha256(f.read_bytes()).hexdigest()})
for f in (extra/'usr/share/dbus-1/services').glob('*.service'):
 text=f.read_text().replace('Exec=/usr/','Exec='+str(extra)+'/usr/').replace('Exec=/bin/','Exec='+str(extra)+'/bin/');f.write_text(text)
(b/'bookworm-extra-patches.json').write_text(json.dumps(changes,indent=2)+'\n')
print('Prepared '+str(len(changes))+' optional ELF files; no package resolution/download occurred')
