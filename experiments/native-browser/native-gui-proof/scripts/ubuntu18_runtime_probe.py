#!/usr/bin/env python3
"""Run the actual private native graphics runtime on a pinned GLIBC2.27 base."""
import hashlib,json,os,pathlib,re,secrets,shlex,struct,subprocess,time
if any((p/'SOURCE_ONLY').is_file()for p in pathlib.Path(__file__).resolve().parents):raise SystemExit('Historical fixture script: copy it to the explicit external workspace documented in native-gui-proof/README.md before running; outputs do not belong in the source-only bundle.')
B=pathlib.Path(__file__).resolve().parent;R=B/'bookworm-root';STATE=B/'ubuntu18-runtime-state';STATE.mkdir(mode=0o700,exist_ok=True);NAME='mgu-native-private-stack-ubuntu18';IMAGE='ubuntu@sha256:152dc042452c496007f07ca9127571cb9c29697f42acbfad72324b2bb2e43c98'
env={}
for name in ['bookworm-env.json','bookworm-assets-env.json','bookworm-extra-env.json']:env.update(json.loads((B/name).read_text()))
env.update({'DISPLAY':':91','XAUTHORITY':str(STATE/'Xauthority'),'GTK_CSD':'1','GTK_USE_PORTAL':'0','XDG_CURRENT_DESKTOP':'GNOME','XDG_CONFIG_HOME':str(STATE/'config'),'XDG_CACHE_HOME':str(STATE/'cache'),'TMPDIR':str(STATE/'tmp')})
isolation={'GCONV_PATH':str(R/'usr/lib/x86_64-linux-gnu/gconv'),'LOCPATH':str(B/'bookworm-locale/usr/lib/locale'),'LANG':'C.utf8','LC_ALL':'C.utf8'}
env.update(isolation);(B/'bookworm-runtime-isolation-env.json').write_text(json.dumps(isolation,indent=2))
for d in ['config','cache','tmp']:(STATE/d).mkdir(mode=0o700,exist_ok=True)
for pattern in ['maps-*.txt','status-*.txt','native-processes.txt','cleanup.json','bus-address.txt','probe.json','probe-maps.txt','probe.err']:
 for p in STATE.glob(pattern):p.unlink()
(STATE/'nsswitch.conf').write_text('passwd: files\ngroup: files\nshadow: files\ngshadow: files\nhosts: files dns\nnetworks: files\nprotocols: files\nservices: files\nethers: files\nrpc: files\nnetgroup: files\n')
def field(v):return struct.pack('>H',len(v))+v
(STATE/'Xauthority').write_bytes(struct.pack('>H',65535)+field(b'')+field(b'91')+field(b'MIT-MAGIC-COOKIE-1')+field(secrets.token_bytes(16)));(STATE/'Xauthority').chmod(0o600)
(STATE/'environment.sh').write_text('\n'.join('export '+k+'='+shlex.quote(v)for k,v in env.items())+'\n')
(STATE/'session.conf').write_text((B/'bookworm-dbus.conf').read_text().replace('unix:tmpdir='+str(B),'unix:tmpdir='+str(STATE)))
test='''#!/bin/sh
set -eu
BASE=/tmp/mgu-native-window-prototype
ROOT="$BASE/bookworm-root"
STATE="$BASE/ubuntu18-runtime-state"
. "$STATE/environment.sh"
XVFB= BUS= WM=
cleanup() {
 for p in "$WM" "$BUS" "$XVFB"; do
  if [ -n "$p" ]; then /bin/kill -TERM -- -"$p" 2>/dev/null || true; fi
 done
 /bin/sleep .2
 for p in "$WM" "$BUS" "$XVFB"; do
  if [ -n "$p" ]; then /bin/kill -KILL -- -"$p" 2>/dev/null || true; fi
 done
 wait 2>/dev/null || true
 /bin/rm -f "$STATE/Xauthority"
}
trap cleanup EXIT HUP INT TERM
/usr/bin/setsid "$ROOT/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2" --preload "$BASE/xkb_private_path.so" "$ROOT/usr/bin/Xvfb" "$DISPLAY" -screen 0 1280x400x24 -nolisten tcp -auth "$XAUTHORITY" -noreset -xkbdir "$ROOT/usr/share/X11/xkb" -fp "$ROOT/usr/share/fonts/X11/misc,built-ins" > "$STATE/xvfb.log" 2>&1 &
XVFB=$!
ready=0
for n in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
 if "$ROOT/usr/bin/xdpyinfo" > "$STATE/xdpyinfo.txt" 2> "$STATE/xdpyinfo.err"; then ready=1; break; fi
 /bin/sleep .1
done
test "$ready" = 1
if XAUTHORITY="$STATE/nonexistent-auth" "$ROOT/usr/bin/xdpyinfo" > "$STATE/unauthorized.stdout" 2> "$STATE/unauthorized.stderr"; then
 echo 'Unauthenticated X connection unexpectedly succeeded' >&2;exit 1
fi
/usr/bin/setsid "$ROOT/usr/bin/dbus-daemon" --config-file="$STATE/session.conf" --nofork --print-address=1 > "$STATE/bus-address.txt" 2> "$STATE/dbus.log" &
BUS=$!
for n in 1 2 3 4 5 6 7 8 9 10; do if [ -s "$STATE/bus-address.txt" ]; then break; fi; /bin/sleep .1; done
DBUS_SESSION_BUS_ADDRESS=$(/bin/cat "$STATE/bus-address.txt");export DBUS_SESSION_BUS_ADDRESS
"$ROOT/usr/bin/dbus-send" --session --print-reply --dest=org.freedesktop.DBus /org/freedesktop/DBus org.freedesktop.DBus.ListNames > "$STATE/bus-ready.txt"
/usr/bin/setsid "$ROOT/usr/bin/xfwm4" --replace --compositor=off --sm-client-disable > "$STATE/wm.log" 2>&1 &
WM=$!
/bin/sleep .5
/bin/kill -0 "$WM"
"$BASE/native_x_probe" "$STATE" > "$STATE/probe.json" 2> "$STATE/probe.err"
/bin/kill -0 "$WM"
"$ROOT/usr/bin/xprop" -root _NET_SUPPORTING_WM_CHECK _NET_SUPPORTED > "$STATE/wm-properties.txt"
for p in /proc/[0-9]*; do
 exe=$(/bin/readlink "$p/exe" 2>/dev/null || true)
 case "$exe" in
  "$ROOT/"*) pid=${p##*/};/bin/cat "$p/maps" > "$STATE/maps-$pid.txt";/bin/cat "$p/status" > "$STATE/status-$pid.txt";printf '%s %s\\n' "$pid" "$exe" >> "$STATE/native-processes.txt";;
 esac
done
/bin/cat /proc/net/tcp > "$STATE/tcp.txt"
/bin/cat /proc/net/tcp6 > "$STATE/tcp6.txt"
cleanup
trap - EXIT HUP INT TERM
test ! -e /tmp/.X11-unix/X91
test ! -e /tmp/.X91-lock
test ! -e "$STATE/Xauthority"
echo '{"ownedGroupsStopped":true,"xSocketRemoved":true,"xLockRemoved":true,"authorityRemoved":true}' > "$STATE/cleanup.json"
'''
(STATE/'test.sh').write_text(test);(STATE/'test.sh').chmod(0o700)
bootstrap='''set -eu
/usr/bin/getconf GNU_LIBC_VERSION > /tmp/mgu-native-window-prototype/ubuntu18-runtime-state/base-libc.txt
/bin/cat /etc/os-release > /tmp/mgu-native-window-prototype/ubuntu18-runtime-state/base-os.txt
/bin/mkdir -p /tmp/.X11-unix
/bin/chmod 1777 /tmp/.X11-unix
printf 'mgu:x:1000:1000::/tmp:/bin/sh\\n' >> /etc/passwd
printf 'mgu:x:1000:\\n' >> /etc/group
exec /sbin/runuser -u mgu -- /bin/sh /tmp/mgu-native-window-prototype/ubuntu18-runtime-state/test.sh
'''
args=['docker','run','--name',NAME,'--network','none','--ipc','private','--shm-size','64m','--mount','type=bind,src='+str(B)+',dst='+str(B)+',readonly','--mount','type=bind,src='+str(STATE)+',dst='+str(STATE),'--mount','type=bind,src='+str(STATE/'nsswitch.conf')+',dst=/etc/nsswitch.conf,readonly','--mount','type=bind,src='+str(R/'usr/share/xfwm4')+',dst=/usr/share/xfwm4,readonly','--mount','type=bind,src='+str(R/'usr/share/themes')+',dst=/usr/share/themes,readonly',IMAGE,'/bin/sh','-c',bootstrap]
meta={'image':IMAGE,'command':args,'network':'none','ipc':'private','baseMountReadOnly':True,'runstateMountReadWrite':str(STATE),'nativeUid':1000,'hostXSocketMounted':False,'hostIpcShared':False,'extraCapabilities':[],'probeSha256':hashlib.sha256((B/'native_x_probe').read_bytes()).hexdigest()};(B/'ubuntu18-runtime-command.json').write_text(json.dumps(meta,indent=2))
try:
 p=subprocess.run(args,capture_output=True,text=True,timeout=45);(STATE/'docker.stdout').write_text(p.stdout);(STATE/'docker.stderr').write_text(p.stderr);meta['exitCode']=p.returncode
 inspect=subprocess.run(['docker','inspect',NAME],capture_output=True,text=True);(B/'ubuntu18-runtime-container-inspect.json').write_text(inspect.stdout)
 if p.returncode:raise RuntimeError('Container private runtime failed; see state logs: '+p.stderr)
 probe=json.loads((STATE/'probe.json').read_text());leaks={};uids={}
 for maps in STATE.glob('maps-*.txt'):
  paths=sorted(set(line.split()[-1]for line in maps.read_text().splitlines()if '.so'in line and line.split()[-1].startswith('/')));bad=[x for x in paths if not x.startswith(str(R))and not x.startswith(str(B/'bookworm-extra'))and x!=str(B/'xkb_private_path.so')]
  if bad:leaks[maps.name]=bad
  status=(STATE/maps.name.replace('maps-','status-')).read_text();uids[maps.name]=next(line for line in status.splitlines()if line.startswith('Uid:'))
 assetLeaks={}
 for maps in STATE.glob('maps-*.txt'):
  paths=sorted(set(line.split()[-1]for line in maps.read_text().splitlines()if line.split()[-1].startswith('/')));bad=[x for x in paths if not x.startswith(str(B))and not x.startswith('/SYSV')]
  if bad:assetLeaks[maps.name]=bad
 pmaps=(STATE/'probe-maps.txt').read_text();plibs=sorted(set(line.split()[-1]for line in pmaps.splitlines()if '.so'in line and line.split()[-1].startswith('/')));pleaks=[x for x in plibs if not x.startswith(str(R))]
 port=f'{6000+91:04X}';tcp='\n'.join((STATE/x).read_text()for x in ['tcp.txt','tcp6.txt']);tcpListening=any(line.split()[1].split(':')[-1]==port and line.split()[3]=='0A'for line in tcp.splitlines()if len(line.split())>=4 and ':'in line.split()[1])
 result={'success':probe['success']and not leaks and not pleaks and not assetLeaks and not tcpListening,'environment':meta,'baseLibc':(STATE/'base-libc.txt').read_text().strip(),'baseOs':(STATE/'base-os.txt').read_text(),'nativeProbe':probe,'nativeProcesses':(STATE/'native-processes.txt').read_text(),'nativeProcessUids':uids,'nativeSharedLibraryLeaks':leaks,'probeSharedLibraryLeaks':pleaks,'nativeMappedFileLeaks':assetLeaks,'unauthorizedConnectionRejected':bool((STATE/'unauthorized.stderr').read_text()),'xTcpListening':tcpListening,'cleanup':json.loads((STATE/'cleanup.json').read_text())};(B/'ubuntu18-runtime-result.json').write_text(json.dumps(result,indent=2));assert result['success'];print(json.dumps(result,indent=2))
finally:
 subprocess.run(['docker','rm','-f',NAME],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);(STATE/'Xauthority').unlink(missing_ok=True)
