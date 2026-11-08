#!/usr/bin/env python3
"""Explicit-input, disposable old-base runtime gate. Never installs/fetches packages."""
import argparse,json,pathlib,secrets,shlex,struct,subprocess
p=argparse.ArgumentParser();p.add_argument('--runtime-root',required=True);p.add_argument('--helper',required=True);p.add_argument('--node',required=True);p.add_argument('--include-dir',required=True);p.add_argument('--workdir',required=True);p.add_argument('--cc',default='cc');p.add_argument('--docker-image',default='ubuntu@sha256:152dc042452c496007f07ca9127571cb9c29697f42acbfad72324b2bb2e43c98');a=p.parse_args();source=pathlib.Path(__file__).resolve().parent.parent;root=pathlib.Path(a.runtime_root).resolve();helper=pathlib.Path(a.helper).resolve();node=pathlib.Path(a.node).resolve();work=pathlib.Path(a.workdir).resolve()
if source==work or source in work.parents:p.error('Scratch workdir must be outside review source')
work.mkdir(parents=True,mode=0o700,exist_ok=True);fixture=work/'x-fixture';libs=[str(root/'lib/x86_64-linux-gnu'),str(root/'usr/lib/x86_64-linux-gnu')];loader=root/'lib/x86_64-linux-gnu/ld-linux-x86-64.so.2'
subprocess.run([a.cc,'-O2','-std=c11','-Wall','-Wextra','-Werror','-I'+str(pathlib.Path(a.include_dir).resolve()),str(source/'test/x_fixture.c')]+['-L'+x for x in libs]+['-Wl,--dynamic-linker='+str(loader),'-Wl,-rpath='+':'.join(libs),'-Wl,-rpath-link='+':'.join(libs),'-l:libX11.so.6','-o',str(fixture)],check=True)
def field(v):return struct.pack('>H',len(v))+v
(work/'Xauthority').write_bytes(struct.pack('>H',65535)+field(b'')+field(b'93')+field(b'MIT-MAGIC-COOKIE-1')+field(secrets.token_bytes(16)));(work/'Xauthority').chmod(0o600)
(work/'nsswitch.conf').write_text('passwd: files\ngroup: files\nhosts: files dns\n')
env={'DISPLAY':':93','XAUTHORITY':str(work/'Xauthority'),'XLOCALEDIR':str(root/'usr/share/X11/locale'),'GCONV_PATH':str(root/'usr/lib/x86_64-linux-gnu/gconv'),'LANG':'C','LC_ALL':'C','PATH':'/usr/bin:/bin'}
(work/'environment.sh').write_text('\n'.join('export '+k+'='+shlex.quote(v)for k,v in env.items())+'\n')
script='''set -eu
. WORK/environment.sh
XVFB=
cleanup(){ if [ -n "$XVFB" ];then /bin/kill -TERM -- -"$XVFB" 2>/dev/null||true;wait "$XVFB" 2>/dev/null||true;fi;/bin/rm -f WORK/Xauthority; }
trap cleanup EXIT HUP INT TERM
/usr/bin/setsid ROOT/usr/bin/Xvfb :93 -screen 0 1280x400x24 -nolisten tcp -auth WORK/Xauthority -noreset -xkbdir ROOT/usr/share/X11/xkb -fp ROOT/usr/share/fonts/X11/misc,built-ins >WORK/xvfb.log 2>&1 &
XVFB=$!
for n in 1 2 3 4 5 6 7 8 9 10;do if ROOT/usr/bin/xdpyinfo >WORK/display.txt 2>WORK/display.err;then break;fi;/bin/sleep .1;done
NODE SOURCE/test/native_runtime.test.js HELPER WORK/x-fixture WORK
cleanup
trap - EXIT HUP INT TERM
test ! -e /tmp/.X11-unix/X93
test ! -e /tmp/.X93-lock
'''
for key,value in [('ROOT',str(root)),('WORK',str(work)),('SOURCE',str(source)),('HELPER',str(helper)),('NODE',str(node))]:script=script.replace(key,shlex.quote(value))
(work/'test.sh').write_text(script)
boot='set -eu\n/bin/mkdir -p /tmp/.X11-unix\n/bin/chmod 1777 /tmp/.X11-unix\nprintf \'mgu:x:1000:1000::/tmp:/bin/sh\\n\' >> /etc/passwd\nprintf \'mgu:x:1000:\\n\' >> /etc/group\nexec /sbin/runuser -u mgu -- /bin/sh '+shlex.quote(str(work/'test.sh'))
name='mgu-native-helper-test';args=['docker','run','--name',name,'--network','none','--ipc','private','--shm-size','64m']
for src,dst,ro in [(root,root,True),(source,source,True),(helper,helper,True),(node,node,True),(work,work,False),(root/'usr/bin/xkbcomp','/usr/bin/xkbcomp',True),(work/'nsswitch.conf','/etc/nsswitch.conf',True)]:args+=['--mount','type=bind,src='+str(src)+',dst='+str(dst)+(',readonly'if ro else'')]
args+=[a.docker_image,'/bin/sh','-c',boot]
try:
 r=subprocess.run(args,capture_output=True,text=True,timeout=45);(work/'container.stdout').write_text(r.stdout);(work/'container.stderr').write_text(r.stderr)
 if r.returncode:raise RuntimeError('Native runtime test failed: '+r.stderr+'\n'+r.stdout)
 result=json.loads((work/'native-runtime-result.json').read_text());result['environment']={'base':'Ubuntu18/glibc2.27','privateHelperRuntime':'Supplied X11/GLIBC2.36 sysroot','node8ProcessUsesBaseLibc':True,'containerImage':a.docker_image,'privateIPC':True,'network':'none','extraCapabilities':[]};(work/'native-runtime-result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
finally:
 subprocess.run(['docker','rm','-f',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);(work/'Xauthority').unlink(missing_ok=True)
