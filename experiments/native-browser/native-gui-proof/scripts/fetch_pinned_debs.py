#!/usr/bin/env python3
"""Verify/fetch exact manifest-pinned public .debs into an explicit external cache.

No host installation/maintainer scripts. Optional extraction goes to a NEW scratch
workspace outside this source-only bundle. This does not build a release package.
"""
import argparse,concurrent.futures,hashlib,json,os,pathlib,stat,subprocess,urllib.parse,urllib.request
HERE=pathlib.Path(__file__).resolve().parent;BUNDLE=HERE.parents[1]
def sha(path):
 h=hashlib.sha256()
 with path.open('rb')as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def external(value):
 raw=pathlib.Path(value)
 if raw.is_symlink():raise ValueError('Output must not be a symbolic link')
 p=raw.resolve()
 if p==BUNDLE or BUNDLE in p.parents:raise ValueError('Output must stay outside the source-only bundle')
 return p
def records(inputs,include_devel=False):
 result=[]
 manifests=[('bookworm-manifest.json','bookworm-root'),('bookworm-extra-manifest.json','bookworm-extra'),('bookworm-locale-manifest.json','bookworm-locale')]
 if include_devel:manifests.append(('bookworm-devel-manifest.json','bookworm-devel'))
 for name,target in manifests:
  data=json.loads((inputs/name).read_text());packages=data.get('packages')if isinstance(data,dict)else None
  if packages is None:packages=[{'name':r['Package'],'url':r['_url'],'sha256':r['SHA256'],'bytes':int(r['Size'])}for r in (data if isinstance(data,list)else[data])]
  for p in packages:
   url=p['url'];u=urllib.parse.urlparse(url)
   if u.scheme!='https'or u.hostname!='deb.debian.org'or'..'in u.path.split('/'):raise ValueError('Unexpected public package URL')
   if len(p['sha256'])!=64 or any(c not in '0123456789abcdef'for c in p['sha256']):raise ValueError('Invalid manifest hash')
   n=int(p['bytes'])
   if not 0<n<128*1024*1024:raise ValueError('Package size outside fixture bound')
   result.append({'name':p['name'],'url':url,'sha256':p['sha256'],'bytes':n,'target':target})
 return result
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--cache',required=True);p.add_argument('--allow-download',action='store_true');p.add_argument('--include-devel',action='store_true');p.add_argument('--inputs',type=pathlib.Path,default=BUNDLE/'inputs');p.add_argument('--extract-workspace');a=p.parse_args();cache=external(a.cache);cache.mkdir(mode=0o700,parents=True,exist_ok=True);items=records(a.inputs,a.include_devel)
 def get(row):
  dest=cache/pathlib.Path(urllib.parse.urlparse(row['url']).path).name
  if dest.exists()or dest.is_symlink():
   s=dest.lstat()
   if not stat.S_ISREG(s.st_mode)or s.st_nlink!=1 or s.st_size!=row['bytes']or sha(dest)!=row['sha256']:raise ValueError('Cached package differs: '+dest.name)
  else:
   if not a.allow_download:raise ValueError('Missing pinned package: '+dest.name+' (use --allow-download explicitly)')
   temp=dest.with_name(dest.name+'.partial-'+str(os.getpid()))
   try:
    with urllib.request.urlopen(row['url'],timeout=45)as r,temp.open('xb')as f:
     total=0
     while True:
      b=r.read(min(1024*1024,row['bytes']+1-total))
      if not b:break
      total+=len(b)
      if total>row['bytes']:raise ValueError('Package exceeds pinned size')
      f.write(b)
    if temp.stat().st_size!=row['bytes']or sha(temp)!=row['sha256']:raise ValueError('Downloaded package differs: '+dest.name)
    temp.replace(dest)
   finally:
    if temp.exists():temp.unlink()
  return row,dest
 unique={}
 for row in items:
  name=pathlib.Path(urllib.parse.urlparse(row['url']).path).name
  if name in unique and unique[name]['sha256']!=row['sha256']:raise ValueError('Conflicting pinned package filename')
  unique[name]=row
 with concurrent.futures.ThreadPoolExecutor(max_workers=4)as pool:files=dict((str(path.name),path)for row,path in pool.map(get,unique.values()))
 verified=[(row,files[pathlib.Path(urllib.parse.urlparse(row['url']).path).name])for row in items]
 if a.extract_workspace:
  root=external(a.extract_workspace)
  if root.exists()and any(root.iterdir()):raise ValueError('Extraction workspace must be new or empty')
  root.mkdir(mode=0o700,parents=True,exist_ok=True)
  if root.stat().st_uid!=os.getuid()or os.getuid()==0:raise ValueError('Unprivileged owner-owned workspace required')
  for row,file in verified:
   target=root/row['target'];target.mkdir(mode=0o700,exist_ok=True);subprocess.run(['dpkg-deb','--extract',str(file),str(target)],check=True)
  for f in root.rglob('*'):
   if f.is_file()and not f.is_symlink():f.chmod(f.stat().st_mode&0o777)
 print(json.dumps({'success':True,'verifiedPackages':len(verified),'pinnedBytes':sum(x['bytes']for x in items),'downloadAllowed':a.allow_download,'extracted':bool(a.extract_workspace),'maintainerScriptsRun':False}))
if __name__=='__main__':main()
