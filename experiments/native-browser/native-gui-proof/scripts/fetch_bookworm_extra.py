#!/usr/bin/env python3
"""Optional SVG-loader/accessibility add-on; never mutates an active core runtime."""
import concurrent.futures,hashlib,json,pathlib,re,subprocess
if any((p/'SOURCE_ONLY').is_file()for p in pathlib.Path(__file__).resolve().parents):raise SystemExit('Historical fixture script: copy it to the explicit external workspace documented in native-gui-proof/README.md before running; outputs do not belong in the source-only bundle.')
import fetch_bookworm as f
B=f.BASE;R=B/'bookworm-root';A=B/'bookworm-extra';A.mkdir(mode=0o700,exist_ok=True);libpaths=':'.join(str(p)for p in [A/'lib/x86_64-linux-gnu',A/'usr/lib/x86_64-linux-gnu',R/'lib/x86_64-linux-gnu',R/'usr/lib/x86_64-linux-gnu',R/'lib',R/'usr/lib']);loader=R/'lib/x86_64-linux-gnu/ld-linux-x86-64.so.2';patch=B/'bookworm-patchelf-tool'
repos=list(concurrent.futures.ThreadPoolExecutor(max_workers=3).map(f.verified_repo,f.REPOS));packages={};sources={};providers={}
for repo in repos:
 for p in repo['indexes']['Packages']:
  p['_repo']=repo['label'];p['_base']=repo['url'];n=p['Package']
  if n not in packages or f.cmp(p['Version'],'gt',packages[n]['Version']):packages[n]=p
  for v in p.get('Provides','').split(','):
   if v.strip():providers.setdefault(v.strip().split(' ',1)[0],[]).append(n)
 for s in repo['indexes']['Sources']:s['_base']=repo['url'];sources[(s['Package'],s['Version'])]=s
existing={p['name']:p for p in json.loads((B/'bookworm-manifest.json').read_text())['packages']};selected={};queue=['librsvg2-common','at-spi2-core']
while queue:
 n=queue.pop(0)
 if n in existing or n in selected:continue
 p=packages[n];selected[n]=p
 for kind in ['Pre-Depends','Depends']:
  for group in p.get(kind,'').split(','):
   if not group.strip():continue
   chosen=None
   for alt in group.split('|'):
    alt=re.sub(r'\[[^]]*\]|<[^>]*>','',alt).strip();m=re.match(r'([\w+.-]+)(?::[\w-]+)?(?:\s*\((<<|<=|=|>=|>>)\s*([^ )]+)\))?',alt);name,op,version=m.groups()
    for cn in ([name]if name in packages else providers.get(name,[])):
     rec=packages[cn]
     if not op or f.cmp(rec['Version'],op,version):chosen=cn;break
    if chosen:break
   if not chosen:raise RuntimeError('Unsatisfied '+group)
   queue.append(chosen)
manifest={'seeds':['librsvg2-common','at-spi2-core'],'packages':[],'coreManifest':'bookworm-manifest.json','warning':'Separate optional scratch add-on. No maintainer scripts. Original signed packages retained.'}
for n,p in sorted(selected.items()):
 local=f.DEBS/pathlib.Path(p['Filename']).name;f.fetch(p['_base']+'/'+p['Filename'],local,p['SHA256'],p['Size']);subprocess.run(['dpkg-deb','--extract',str(local),str(A)],check=True);sn=p.get('Source',n).split(' ',1)[0];sv=re.search(r'\(([^)]+)\)',p.get('Source',''));sv=sv.group(1)if sv else p['Version'];source=sources[(sn,sv)];sa=[]
 for line in source['Checksums-Sha256'].splitlines():
  if not line.strip():continue
  sha,size,name=line.split();sa.append({'url':source['_base']+'/'+source['Directory']+'/'+name,'sha256':sha,'bytes':int(size)})
 manifest['packages'].append({'name':n,'version':p['Version'],'url':p['_base']+'/'+p['Filename'],'sha256':p['SHA256'],'bytes':int(p['Size']),'source':sn,'sourceVersion':sv,'sourceArchives':sa});print('Verified extra',n,p['Version'],flush=True)
patches=[]
for p in A.rglob('*'):
 if p.is_symlink()or not p.is_file():continue
 p.chmod(p.stat().st_mode&0o777)
 with p.open('rb')as h:magic=h.read(4)
 if magic!=b'\x7fELF':continue
 r=subprocess.run([str(patch),'--print-rpath',str(p)],capture_output=True,text=True)
 if r.returncode:continue
 original=hashlib.sha256(p.read_bytes()).hexdigest();i=subprocess.run([str(patch),'--print-interpreter',str(p)],capture_output=True,text=True);cmd=[str(patch),'--set-rpath',libpaths]
 if not i.returncode:cmd+=['--set-interpreter',str(loader)]
 subprocess.run(cmd+[str(p)],check=True);patches.append({'path':str(p.relative_to(A)),'originalSha256':original,'runtimeSha256':hashlib.sha256(p.read_bytes()).hexdigest()})
for p in (A/'usr/share/dbus-1/services').glob('*.service'):
 s=p.read_text().replace('Exec=/usr/','Exec='+str(A)+'/usr/').replace('Exec=/bin/','Exec='+str(A)+'/bin/');p.write_text(s)
(B/'bookworm-extra-manifest.json').write_text(json.dumps(manifest,indent=2));(B/'bookworm-extra-patches.json').write_text(json.dumps(patches,indent=2));print('Prepared optional extra',A,flush=True)
