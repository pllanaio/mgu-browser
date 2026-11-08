#!/usr/bin/env python3
"""Build authored fixture helpers outside the bundle; reject newer/host ABI leaks."""
import argparse,hashlib,json,pathlib,re,subprocess
p=argparse.ArgumentParser();p.add_argument('--workspace',type=pathlib.Path,required=True);p.add_argument('--include-dir',type=pathlib.Path,required=True);p.add_argument('--output-dir',type=pathlib.Path,required=True);p.add_argument('--cc',default='cc');a=p.parse_args();b=a.workspace.resolve();r=b/'bookworm-root';here=pathlib.Path(__file__).resolve().parent;bundle=here.parents[1]
if b==bundle or bundle in b.parents:p.error('Build workspace must be outside the source-only bundle')
out=a.output_dir.resolve()
if out==bundle or bundle in out.parents:p.error('Build output must be outside the source-only bundle')
out.mkdir(mode=0o700,parents=True,exist_ok=True)
loader=r/'lib/x86_64-linux-gnu/ld-linux-x86-64.so.2';libs=[r/'lib/x86_64-linux-gnu',r/'usr/lib/x86_64-linux-gnu',r/'lib',r/'usr/lib'];lp=':'.join(map(str,libs));rows=[]
if not loader.is_file():p.error('Explicit workspace needs the prepared private runtime')
for name in ['combined_x_control','native_x_probe']:
 source=here/(name+'.c');output=out/name;command=[a.cc,'-O2','-std=c11','-D_POSIX_C_SOURCE=200809L','-Wall','-Wextra','-I'+str(a.include_dir),str(source)]+['-L'+str(d)for d in libs]+['-Wl,--dynamic-linker='+str(loader),'-Wl,-rpath='+lp,'-Wl,-rpath-link='+lp,'-l:libX11.so.6','-l:libXext.so.6','-l:libXtst.so.6','-o',str(output)];subprocess.run(command,check=True)
 versions=subprocess.check_output(['readelf','--dyn-syms','--wide',str(output)],text=True);required=sorted(set(tuple(map(int,x.split('.')))for x in re.findall(r'@GLIBC_([0-9.]+)',versions)))
 if required and required[-1]>(2,36):raise RuntimeError(name+' imports GLIBC above2.36; use a compatible Debian12 build compiler/sysroot')
 check=subprocess.run([str(loader),'--list',str(output)],text=True,capture_output=True);text=check.stdout+check.stderr
 paths=re.findall(r'(?:=>\s*)?(/[^\s()]+)',text);leaks=[x for x in paths if not pathlib.Path(x).is_relative_to(r)]
 if check.returncode or 'not found'in text or leaks:raise RuntimeError('Private loader closure failed: '+text)
 rows.append({'source':source.name,'sourceSha256':hashlib.sha256(source.read_bytes()).hexdigest(),'outputSha256':hashlib.sha256(output.read_bytes()).hexdigest(),'requiredGlibc':['.'.join(map(str,x))for x in required],'privateLoaderClosure':True})
(out/'authored-helper-build.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps({'success':True,'helpers':rows}))
