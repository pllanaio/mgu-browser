#!/usr/bin/env python3
"""Build outside the review bundle with an explicitly supplied private X11 sysroot."""
import argparse,pathlib,subprocess
p=argparse.ArgumentParser();p.add_argument('--cc',default='cc');p.add_argument('--include-dir',required=True);p.add_argument('--lib-dir',action='append',required=True);p.add_argument('--loader',required=True);p.add_argument('--output',required=True);a=p.parse_args();here=pathlib.Path(__file__).resolve().parent;out=pathlib.Path(a.output).resolve()
if out==here or here in out.parents:p.error('Build output must be outside the review bundle')
loader=pathlib.Path(a.loader).resolve();libs=[str(pathlib.Path(x).resolve())for x in a.lib_dir];out.parent.mkdir(parents=True,exist_ok=True)
cmd=[a.cc,'-O2','-std=c11','-Wall','-Wextra','-Werror','-I'+str(pathlib.Path(a.include_dir).resolve()),str(here/'src/native_helper.c')]+['-L'+x for x in libs]+['-Wl,--dynamic-linker='+str(loader),'-Wl,-rpath='+':'.join(libs),'-Wl,-rpath-link='+':'.join(libs),'-l:libX11.so.6','-l:libXext.so.6','-l:libXtst.so.6','-o',str(out)]
subprocess.run(cmd,check=True)
print('Built '+str(out))
