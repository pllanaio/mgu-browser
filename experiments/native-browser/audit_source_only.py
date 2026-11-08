#!/usr/bin/env python3
"""Check this review tree's explicit source/evidence boundary; never print contents."""
import argparse,hashlib,json,pathlib,re,tempfile
MAX_FILE=2*1024*1024
ALLOWED={'.py','.c','.js','.json','.md','.pl','.png','.txt'}
NAMES={'LICENSE','SOURCE_ONLY','.gitignore','extension-id'}
PRIVATE=re.compile(br'-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----')
BANNED_NAME=re.compile(r'(^|/)(Xauthority|\.Xauthority|Cookies(?:-[^/]*)?|Login Data(?:-[^/]*)?|Local State|Preferences|.*\.(?:pem|der|deb|tgz|node|so(?:\.[^/]*)?|a|o|raw|ppm|pyc)|.*\.tar(?:\.[^/]*)?)$')
def cookie_values(value):
 if isinstance(value,dict):
  if all(k in value for k in ['name','domain','value'])and isinstance(value['value'],str):return True
  return any(cookie_values(v)for v in value.values())
 if isinstance(value,list):return any(map(cookie_values,value))
 return False
def inspect(root):
 errors=[];files=[]
 for f in sorted(root.rglob('*')):
  rel=f.relative_to(root).as_posix()
  if '.git'in f.relative_to(root).parts:continue
  if f.is_symlink():errors.append({'path':rel,'reason':'symlink'});continue
  if not f.is_file():continue
  if BANNED_NAME.search(rel):errors.append({'path':rel,'reason':'runtime/private/output filename'});continue
  if f.name not in NAMES and f.suffix not in ALLOWED:errors.append({'path':rel,'reason':'file type outside allowlist'});continue
  if f.stat().st_size>MAX_FILE:errors.append({'path':rel,'reason':'file exceeds review-size bound'});continue
  data=f.read_bytes()
  if data.startswith((b'\x7fELF',b'!<arch>\n',b'\x1f\x8b',b'\xfd7zXZ\x00',b'PK\x03\x04')):errors.append({'path':rel,'reason':'binary/archive payload'});continue
  if PRIVATE.search(data):errors.append({'path':rel,'reason':'private-key PEM header'});continue
  if f.suffix=='.png':
   if '/evidence/'not in '/'+rel or not data.startswith(b'\x89PNG\r\n\x1a\n'):errors.append({'path':rel,'reason':'non-evidence or invalid PNG'});continue
  else:
   try:data.decode('utf8')
   except UnicodeDecodeError:errors.append({'path':rel,'reason':'non-text source'});continue
  if f.suffix=='.json':
   try:value=json.loads(data)
   except ValueError:errors.append({'path':rel,'reason':'invalid JSON'});continue
   if '/evidence/'in '/'+rel and cookie_values(value):errors.append({'path':rel,'reason':'raw cookie values in evidence'});continue
  if rel not in ['source-manifest.json','audit-result.json']:files.append({'path':rel,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
 return errors,files
def selftest():
 with tempfile.TemporaryDirectory(prefix='native-source-audit-')as temp:
  root=pathlib.Path(temp);(root/'ok.c').write_text('int main(void){return 0;}\n');assert not inspect(root)[0]
  (root/'bad.js').write_bytes(b'\x7fELFfake');assert inspect(root)[0][0]['reason']=='binary/archive payload';(root/'bad.js').unlink()
  (root/'secret.txt').write_text('-----BEGIN '+'PRIVATE KEY-----\nfixture-not-a-key\n');assert inspect(root)[0][0]['reason']=='private-key PEM header';(root/'secret.txt').unlink()
  (root/'Xauthority').write_bytes(b'fixture');assert inspect(root)[0][0]['reason']=='runtime/private/output filename';(root/'Xauthority').unlink()
  (root/'evidence').mkdir();(root/'evidence/cookie-test.json').write_text(json.dumps({'name':'fixture','domain':'localhost','value':'generated'}));assert inspect(root)[0][0]['reason']=='raw cookie values in evidence'
def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=pathlib.Path,default=pathlib.Path(__file__).resolve().parent);p.add_argument('--write-manifest',action='store_true');p.add_argument('--self-test',action='store_true');a=p.parse_args()
 if a.self_test:selftest()
 root=a.root.resolve();errors,files=inspect(root);result={'success':not errors,'files':len(files),'bytes':sum(x['bytes']for x in files),'sourceOnly':not errors,'checks':['allowed text/source and evidence-PNG types','no symlinks','no ELF/native addon/archive payload','no runtime/profile/private-key filenames','no private-key PEM headers','no raw cookie records in JSON evidence'],'errors':errors,'scope':'Allowlist/marker audit plus manual evidence review; not a complete encoded-secret or legal review'}
 if a.write_manifest and not errors:
  (root/'source-manifest.json').write_text(json.dumps({'format':1,'excludes':['source-manifest.json','audit-result.json'],'files':files},indent=2)+'\n');(root/'audit-result.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result,indent=2))
 if errors:raise SystemExit(1)
if __name__=='__main__':main()
