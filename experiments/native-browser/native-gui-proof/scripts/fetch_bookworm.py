#!/usr/bin/env python3
"""Fetch a signed Debian12 GUI runtime into an unprivileged scratch root. No install scripts."""
import concurrent.futures, datetime, email.utils, hashlib, json, lzma, os, pathlib, re, subprocess, urllib.request
if any((p/'SOURCE_ONLY').is_file()for p in pathlib.Path(__file__).resolve().parents):raise SystemExit('Historical fixture script: copy it to the explicit external workspace documented in native-gui-proof/README.md before running; outputs do not belong in the source-only bundle.')

BASE=pathlib.Path(__file__).resolve().parent
OUT=BASE/'bookworm-root'; META=BASE/'bookworm-metadata'; DEBS=BASE/'bookworm-debs'
for p in (OUT,META,DEBS):p.mkdir(mode=0o700,exist_ok=True)
KEY='/usr/share/keyrings/debian-archive-keyring.gpg'
REPOS=[('bookworm','https://deb.debian.org/debian','bookworm'),('bookworm-updates','https://deb.debian.org/debian','bookworm-updates'),('bookworm-security','https://deb.debian.org/debian-security','bookworm-security')]
SEEDS=['xvfb','xfwm4','libgtk-3-0','libxtst6','xauth','xkb-data','x11-xkb-utils','x11-utils','x11-xserver-utils','fonts-dejavu-core','xfonts-base','dbus','dbus-x11','adwaita-icon-theme','shared-mime-info','libglib2.0-bin','libgdk-pixbuf2.0-bin','patchelf']

def fetch(url,p,sha=None,size=None):
 if p.exists() and (not sha or hashlib.sha256(p.read_bytes()).hexdigest()==sha):return
 with urllib.request.urlopen(url,timeout=90) as r:data=r.read()
 if sha and hashlib.sha256(data).hexdigest()!=sha:raise RuntimeError('SHA256 mismatch '+url)
 if size is not None and len(data)!=int(size):raise RuntimeError('Size mismatch '+url)
 tmp=p.with_suffix(p.suffix+'.partial');tmp.write_bytes(data);tmp.replace(p)

def fields(text):
 cur={};last=None
 for line in text.splitlines():
  if not line:
   if cur:yield cur
   cur={};last=None
  elif line[0].isspace():
   if last:cur[last]+='\n'+line[1:]
  else:
   k,_,v=line.partition(':');cur[k]=v.lstrip();last=k
 if cur:yield cur

def cmp(a,op,b):return subprocess.run(['dpkg','--compare-versions',a,op,b]).returncode==0

def verified_repo(repo):
 label,url,suite=repo;d=META/label;d.mkdir(exist_ok=True)
 fetch(url+'/dists/'+suite+'/InRelease',d/'InRelease')
 verified=d/'Release.verified';verified.unlink(missing_ok=True)
 args=['sqv','--keyring',KEY,'--cleartext','--output',str(verified),str(d/'InRelease')]
 r=subprocess.run(args,text=True,capture_output=True);(d/'signature-verification.txt').write_text(r.stdout+r.stderr)
 if r.returncode:raise RuntimeError('Signature verification failed '+label+' '+r.stderr)
 rel=next(fields(verified.read_text()));assert rel['Codename']==suite,(suite,rel.get('Codename'))
 now=datetime.datetime.now(datetime.timezone.utc)
 if 'Valid-Until'in rel and email.utils.parsedate_to_datetime(rel['Valid-Until'])<now:raise RuntimeError('Expired Release '+label)
 hashes={parts[2]:parts[:2] for line in rel['SHA256'].splitlines() if len(parts:=line.split())==3}
 indexes={}
 for kind,remote in [('Packages','main/binary-amd64/Packages.xz'),('Sources','main/source/Sources.xz')]:
  sha,size=hashes[remote];p=d/(kind+'.xz');fetch(url+'/dists/'+suite+'/'+remote,p,sha,size);indexes[kind]=list(fields(lzma.decompress(p.read_bytes()).decode()))
 return {'label':label,'url':url,'suite':suite,'release':{k:rel.get(k) for k in ('Codename','Suite','Date','Valid-Until')},'signatureCommand':args,'inReleaseSha256':hashlib.sha256((d/'InRelease').read_bytes()).hexdigest(),'indexes':indexes}

def main():
 repos=list(concurrent.futures.ThreadPoolExecutor(max_workers=3).map(verified_repo,REPOS));packages={};providers={};sources={}
 for repo in repos:
  for rec in repo['indexes']['Packages']:
   rec['_repo']=repo['label'];rec['_base']=repo['url'];name=rec['Package']
   if name not in packages or cmp(rec['Version'],'gt',packages[name]['Version']):packages[name]=rec
   for part in rec.get('Provides','').split(','):
    virtual=part.strip().split(' ',1)[0]
    if virtual:providers.setdefault(virtual,[]).append(name)
  for rec in repo['indexes']['Sources']:
   rec['_repo']=repo['label'];rec['_base']=repo['url'];sources[(rec['Package'],rec['Version'])]=rec
 selected={};why={};queue=[(x,'seed') for x in SEEDS]
 def satisfy(group):
  for alt in group.split('|'):
   alt=re.sub(r'\[[^]]*\]|<[^>]*>','',alt).strip();m=re.match(r'([a-zA-Z0-9+.-]+)(?::[a-zA-Z0-9-]+)?(?:\s*\((<<|<=|=|>=|>>)\s*([^ )]+)\))?',alt)
   if not m:raise RuntimeError('Cannot parse dependency '+alt)
   name,op,version=m.groups();candidates=[name] if name in packages else providers.get(name,[])
   for candidate in candidates:
    rec=packages[candidate]
    if not op or cmp(rec['Version'],op,version):return candidate
  raise RuntimeError('Unsatisfied dependency '+group)
 while queue:
  name,parent=queue.pop(0)
  if name in selected:continue
  rec=packages[name];selected[name]=rec;why[name]=parent
  for field in ('Pre-Depends','Depends'):
   for group in rec.get(field,'').split(','):
    if group.strip():queue.append((satisfy(group),name))
 manifest={'generatedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'keyring':KEY,'keyringSha256':hashlib.sha256(pathlib.Path(KEY).read_bytes()).hexdigest(),'seeds':SEEDS,'repositories':[{k:v for k,v in r.items() if k!='indexes'} for r in repos],'packages':[],'warning':'Scratch extraction only. No maintainer scripts, alternatives, triggers or system installation. Source archives recorded, not downloaded.'}
 for name,rec in sorted(selected.items()):
  srcname=rec.get('Source',name).split(' ',1)[0];m=re.search(r'\(([^)]+)\)',rec.get('Source',''));srcversion=m.group(1) if m else rec['Version'];source=sources.get((srcname,srcversion));srcfiles=[]
  if source:
   for line in source.get('Checksums-Sha256','').splitlines():
    if not line.strip():continue
    sha,size,file=line.split();srcfiles.append({'url':source['_base']+'/'+source['Directory']+'/'+file,'sha256':sha,'bytes':int(size)})
  manifest['packages'].append({'name':name,'version':rec['Version'],'architecture':rec['Architecture'],'source':srcname,'sourceVersion':srcversion,'repository':rec['_repo'],'url':rec['_base']+'/'+rec['Filename'],'sha256':rec['SHA256'],'bytes':int(rec['Size']),'localFile':str(DEBS/pathlib.Path(rec['Filename']).name),'selectedBecause':why[name],'sourceArchives':srcfiles})
 (BASE/'bookworm-manifest.json').write_text(json.dumps(manifest,indent=2));print('Resolved',len(selected),'packages,',sum(p['bytes']for p in manifest['packages'])/1048576,'MiB compressed',flush=True)
 def get(p):
  fetch(p['url'],pathlib.Path(p['localFile']),p['sha256'],p['bytes']);return p['name']
 with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
  for name in pool.map(get,manifest['packages']):print('Verified',name,flush=True)
 for p in manifest['packages']:
  subprocess.run(['dpkg-deb','--extract',p['localFile'],str(OUT)],check=True)
 for p in OUT.rglob('*'):
  if not p.is_symlink() and p.is_file():p.chmod(p.stat().st_mode&0o777)
 print('Extracted',OUT,flush=True)

if __name__=='__main__':main()
