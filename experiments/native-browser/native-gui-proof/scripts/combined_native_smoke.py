#!/usr/bin/env python3
"""Single-container exact-engine/native-GUI/audio smoke. Authored loopback fixture only; no CDP."""
import hashlib,http.server,json,os,pathlib,re,secrets,shlex,shutil,socketserver,struct,subprocess,threading,time
from PIL import Image
B=pathlib.Path(__file__).resolve().parent
if B!=pathlib.Path('/tmp/mgu-native-window-prototype'):raise SystemExit('Historical fixed-prefix proof: copy these authored scripts to /tmp/mgu-native-window-prototype and supply the explicit inputs listed in native-gui-proof/README.md; do not run inside the review bundle.')
R=B/'bookworm-root';S=B/'combined-state'
if S.is_symlink():raise SystemExit('Refusing symlink fixture state')
S.mkdir(mode=0o700,exist_ok=True);NAME='mgu-native-combined-ubuntu18';IMAGE='ubuntu@sha256:152dc042452c496007f07ca9127571cb9c29697f42acbfad72324b2bb2e43c98';ENGINE='/var/opt/mgu-browser-engine/versions/0.1.0/engine';OLD=pathlib.Path('/workspace/mgu-browser/.local/audio-abi-2.27/root');HELPER=pathlib.Path('/workspace/mgu-browser-audio-focus/.local/published-0.15.0-verify/runtime-unpacked/files/audio-bridge');PORT=39092
REPORTS=[];LOCK=threading.Lock()
PAGE='''<!doctype html><meta charset=utf-8><title>MGU coherent native browser</title><style>html,body{margin:0;background:#14243b;color:white;font:16px sans-serif}main{padding:8px}button{font:16px sans-serif;padding:7px;margin-right:9px}video{display:block;width:100%;height:135px;object-fit:contain;background:black}video:fullscreen{width:100vw;height:100vh;object-fit:contain}p{margin:6px}</style><main><button id=play>Play original video and audio</button><button id=full>Native video fullscreen</button><button id=dialog>Native confirm</button><p id=facts>Waiting for native browser</p><video id=v loop src=/clip.webm></video></main><script>
let gl=document.createElement('canvas').getContext('webgl2'),graphics={available:!!gl};if(gl){let ext=gl.getExtension('WEBGL_debug_renderer_info');graphics.renderer=ext?gl.getParameter(ext.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER)}
function send(extra={}){let q=v.getVideoPlaybackQuality(),data=Object.assign({webdriver:navigator.webdriver,ua:navigator.userAgent,graphics,screenX,screenY,outerWidth,outerHeight,innerWidth,innerHeight,fullscreen:document.fullscreenElement?document.fullscreenElement.id:null,video:{time:v.currentTime,paused:v.paused,decoded:q.totalVideoFrames,dropped:q.droppedVideoFrames},buttons:Object.fromEntries(['play','full','dialog'].map(id=>{let r=document.getElementById(id).getBoundingClientRect();return[id,{x:r.x,y:r.y,w:r.width,h:r.height}]}))},extra);facts.textContent='Genuine native Chromium | webdriver: '+navigator.webdriver+' | video frames: '+q.totalVideoFrames;fetch('/report',{method:'POST',body:JSON.stringify(data)})}
play.onclick=()=>v.play().then(()=>send({played:true})).catch(e=>send({playError:e.name}));full.onclick=()=>v.requestFullscreen().then(()=>send()).catch(e=>send({fullscreenError:e.name}));dialog.onclick=()=>send({confirmed:confirm('MGU authored genuine native confirmation — no browser protocol')});document.addEventListener('fullscreenchange',()=>send());setInterval(()=>send(),200);send();</script>'''
class Handler(http.server.BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_GET(self):
  data=(B/'clip.webm').read_bytes()if self.path.startswith('/clip.webm')else PAGE.encode();self.send_response(200);self.send_header('Content-Type','video/webm'if self.path.startswith('/clip.webm')else'text/html; charset=utf-8');self.send_header('Content-Length',str(len(data)));self.end_headers()
  try:self.wfile.write(data)
  except (BrokenPipeError,ConnectionResetError):pass
 def do_POST(self):
  data=json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))))
  with LOCK:REPORTS.append(data)
  self.send_response(204);self.end_headers()
class UnixServer(socketserver.ThreadingUnixStreamServer):daemon_threads=True
def latest():
 with LOCK:return REPORTS[-1]if REPORTS else None
def wait(fn,seconds=12):
 start=time.monotonic()
 while time.monotonic()-start<seconds:
  value=fn()
  if value:return value
  time.sleep(.05)
 raise RuntimeError('Combined native fixture timed out')
def main():
 required=[R/'usr/bin/Xvfb',R/'usr/bin/xfwm4',R/'usr/bin/dbus-daemon',B/'combined_x_control',B/'xkb_private_path.so',B/'published-engine/chromium',B/'clip.webm',OLD/'lib/x86_64-linux-gnu/ld-2.27.so',HELPER]+[B/name for name in ['bookworm-env.json','bookworm-assets-env.json','bookworm-extra-env.json','bookworm-runtime-isolation-env.json','bookworm-fonts.conf','bookworm-dbus.conf']]
 missing=[str(p)for p in required if not p.is_file()]
 if missing:raise SystemExit('Required explicit fixture inputs missing: '+', '.join(missing))
 if hashlib.sha256((B/'published-engine/chromium').read_bytes()).hexdigest()!='9c94b57491fcc1a4b5a013ecb8fa13a637cc9a16aebea5041899c3cb033e5a13':raise SystemExit('Exact Engine0.1 Chromium hash differs')
 if subprocess.run(['docker','inspect',NAME],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0:raise SystemExit('Refusing to reuse an existing named container')
 for p in S.iterdir():
  if p.is_file()or p.is_socket()or p.is_fifo():p.unlink()
 shutil.rmtree(S/'profile',ignore_errors=True)
 for d in ['config','cache','font-cache','tmp']:(S/d).mkdir(mode=0o700,exist_ok=True)
 def field(v):return struct.pack('>H',len(v))+v
 (S/'Xauthority').write_bytes(struct.pack('>H',65535)+field(b'')+field(b'92')+field(b'MIT-MAGIC-COOKIE-1')+field(secrets.token_bytes(16)));(S/'Xauthority').chmod(0o600)
 env={}
 for name in ['bookworm-env.json','bookworm-assets-env.json','bookworm-extra-env.json','bookworm-runtime-isolation-env.json']:env.update(json.loads((B/name).read_text()))
 env.update({'DISPLAY':':92','XAUTHORITY':str(S/'Xauthority'),'GTK_CSD':'1','GTK_USE_PORTAL':'0','XDG_CURRENT_DESKTOP':'GNOME','XDG_CONFIG_HOME':str(S/'config'),'XDG_CACHE_HOME':str(S/'cache'),'TMPDIR':str(S/'tmp'),'MGU_NATIVE_HTTP_PORT':str(PORT),'MGU_NATIVE_HTTP_SOCKET':str(S/'http.sock'),'PULSE_SERVER':'unix:'+str(S/'no-pulse'),'ALSA_CONFIG_PATH':str(S/'client.conf'),'FONTCONFIG_FILE':str(S/'fonts.conf'),'XLOCALEDIR':str(R/'usr/share/X11/locale'),'GTK_IM_MODULE':'simple'})
 (S/'environment.sh').write_text('\n'.join('export '+k+'='+shlex.quote(v)for k,v in env.items())+'\n')
 (S/'fonts.conf').write_text((B/'bookworm-fonts.conf').read_text().replace(str(B/'bookworm-font-cache'),str(S/'font-cache')))
 (S/'session.conf').write_text((B/'bookworm-dbus.conf').read_text().replace('unix:tmpdir='+str(B),'unix:tmpdir='+str(S)))
 (S/'nsswitch.conf').write_text('passwd: files\ngroup: files\nshadow: files\ngshadow: files\nhosts: files dns\nnetworks: files\nprotocols: files\nservices: files\nethers: files\nrpc: files\nnetgroup: files\n')
 (S/'sink.conf').write_text('pcm.null {type null}\npcm.fixture {type file slave.pcm null file "'+str(S/'output.raw')+'" format raw}\n')
 (S/'client.conf').write_text('pcm.null {type null}\npcm.mgu_file {type file slave.pcm null file "'+str(S/'pcm.fifo')+'" format raw}\npcm.mgu_browser {type plug slave {pcm mgu_file rate 48000 channels 2 format S16_LE}}\n')
 script='''#!/bin/sh
set -eu
BASE=/tmp/mgu-native-window-prototype
ROOT="$BASE/bookworm-root"
STATE="$BASE/combined-state"
ENGINE=/var/opt/mgu-browser-engine/versions/0.1.0/engine
. "$STATE/environment.sh"
XVFB= BUS= WM= CHROME= AUDIO= RELAY=
cleanup(){
 for p in "$CHROME" "$AUDIO" "$RELAY" "$WM" "$BUS" "$XVFB";do if [ -n "$p" ];then /bin/kill -TERM -- -"$p" 2>/dev/null||true;fi;done
 /bin/sleep .3
 for p in "$CHROME" "$AUDIO" "$RELAY" "$WM" "$BUS" "$XVFB";do if [ -n "$p" ];then /bin/kill -KILL -- -"$p" 2>/dev/null||true;fi;done
 wait 2>/dev/null||true
 /bin/rm -f "$STATE/Xauthority"
}
trap cleanup EXIT HUP INT TERM
/usr/bin/setsid "$ROOT/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2" --preload "$BASE/xkb_private_path.so" "$ROOT/usr/bin/Xvfb" "$DISPLAY" -screen 0 1280x400x24 -nolisten tcp -auth "$XAUTHORITY" -noreset -xkbdir "$ROOT/usr/share/X11/xkb" -fp "$ROOT/usr/share/fonts/X11/misc,built-ins" >"$STATE/xvfb.log" 2>&1 &
XVFB=$!
for n in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20;do if "$ROOT/usr/bin/xdpyinfo" >"$STATE/display.txt" 2>"$STATE/display.err";then break;fi;/bin/sleep .1;done
/usr/bin/setsid "$ROOT/usr/bin/dbus-daemon" --config-file="$STATE/session.conf" --nofork --print-address=1 >"$STATE/bus-address.txt" 2>"$STATE/dbus.log" &
BUS=$!
for n in 1 2 3 4 5 6 7 8 9 10;do if [ -s "$STATE/bus-address.txt" ];then break;fi;/bin/sleep .1;done
DBUS_SESSION_BUS_ADDRESS=$(/bin/cat "$STATE/bus-address.txt");export DBUS_SESSION_BUS_ADDRESS
"$ROOT/usr/bin/dbus-send" --session --print-reply --dest=org.freedesktop.DBus /org/freedesktop/DBus org.freedesktop.DBus.ListNames >"$STATE/bus-ready.txt"
/usr/bin/setsid "$ROOT/usr/bin/xfwm4" --replace --compositor=off --sm-client-disable >"$STATE/wm.log" 2>&1 &
WM=$!
/usr/bin/setsid /usr/bin/env LANG=C LC_ALL=C LOCPATH= GCONV_PATH= /usr/bin/perl "$BASE/local-http-relay.pl" >"$STATE/relay.log" 2>&1 &
RELAY=$!
/usr/bin/mkfifo "$STATE/helper-control"
exec 9<>"$STATE/helper-control"
/usr/bin/setsid /usr/bin/env LANG=C LC_ALL=C LOCPATH= GCONV_PATH= MGU_EMULATOR_MODE=1 ALSA_CONFIG_PATH="$STATE/sink.conf" /workspace/mgu-browser/.local/audio-abi-2.27/root/lib/x86_64-linux-gnu/ld-2.27.so --library-path /workspace/mgu-browser/.local/audio-abi-2.27/root/lib/x86_64-linux-gnu:/workspace/mgu-browser/.local/audio-abi-2.27/root/usr/lib/x86_64-linux-gnu /workspace/mgu-browser-audio-focus/.local/published-0.15.0-verify/runtime-unpacked/files/audio-bridge --fifo "$STATE/pcm.fifo" --device fixture --fixture <"$STATE/helper-control" >"$STATE/audio.log" 2>&1 &
AUDIO=$!
printf '1\\n' >&9
/usr/bin/setsid /usr/bin/env LD_LIBRARY_PATH="$ROOT/lib/x86_64-linux-gnu:$ROOT/usr/lib/x86_64-linux-gnu:$ROOT/lib:$ROOT/usr/lib" "$ENGINE/chromium" --user-data-dir="$STATE/profile" --window-size=1280,400 --window-position=0,0 --ozone-platform=x11 --use-gl=angle --use-angle=swiftshader-webgl --force-device-scale-factor=1 --no-first-run --no-default-browser-check --disable-background-networking --disable-sync --disable-component-update --password-store=basic --disable-dev-shm-usage --alsa-output-device=mgu_browser http://127.0.0.1:39092/ >"$STATE/chromium.log" 2>&1 &
CHROME=$!
printf '%s\\n' "$XVFB $BUS $WM $RELAY $AUDIO $CHROME" >"$STATE/pids.txt"
echo ready >"$STATE/ready"
while [ ! -e "$STATE/stop" ];do /bin/kill -0 "$CHROME";/bin/kill -0 "$WM";/bin/sleep .1;done
for p in /proc/[0-9]*;do exe=$(/bin/readlink "$p/exe" 2>/dev/null||true);case "$exe" in "$ROOT/"*|"$ENGINE/"*|/workspace/mgu-browser/.local/audio-abi-2.27/root/*) pid=${p##*/};/bin/cat "$p/maps">"$STATE/maps-$pid.txt";/bin/cat "$p/status">"$STATE/status-$pid.txt";/bin/cat "$p/cmdline">"$STATE/cmdline-$pid.txt";printf '%s %s\\n' "$pid" "$exe">>"$STATE/native-processes.txt";;esac;done
"$ROOT/usr/bin/xprop" -root _NET_SUPPORTING_WM_CHECK >"$STATE/wm-properties.txt"
cleanup
trap - EXIT HUP INT TERM
test ! -e /tmp/.X11-unix/X92
test ! -e /tmp/.X92-lock
test ! -e "$STATE/Xauthority"
echo '{"socketRemoved":true,"lockRemoved":true,"authorityRemoved":true}' >"$STATE/cleanup.json"
'''
 (S/'test.sh').write_text(script)
 boot='''set -eu
/usr/bin/getconf GNU_LIBC_VERSION > /tmp/mgu-native-window-prototype/combined-state/base-libc.txt
/bin/mkdir -p /tmp/.X11-unix
/bin/chmod 1777 /tmp/.X11-unix
/bin/cp /var/opt/mgu-browser-engine/versions/0.1.0/engine/chrome-sandbox /tmp/combined-native-sandbox
/bin/chown 0:0 /tmp/combined-native-sandbox
/bin/chmod 4755 /tmp/combined-native-sandbox
/usr/bin/stat -c '%u:%g:%a' /tmp/combined-native-sandbox > /tmp/mgu-native-window-prototype/combined-state/sandbox-mode.txt
/usr/bin/sha256sum /tmp/combined-native-sandbox > /tmp/mgu-native-window-prototype/combined-state/sandbox-hash.txt
export CHROME_DEVEL_SANDBOX=/tmp/combined-native-sandbox
printf 'mgu:x:1000:1000::/tmp:/bin/sh\\n' >> /etc/passwd
printf 'mgu:x:1000:\\n' >> /etc/group
exec /sbin/runuser -u mgu -- /bin/sh /tmp/mgu-native-window-prototype/combined-state/test.sh
'''
 args=['docker','run','--name',NAME,'--network','none','--ipc','private','--shm-size','128m','--cap-add','SYS_ADMIN','--security-opt','apparmor=unconfined']
 for source,target,ro in [(B,B,True),(S,S,False),(B/'published-engine',ENGINE,True),(R/'usr/share/xfwm4','/usr/share/xfwm4',True),(R/'usr/share/themes','/usr/share/themes',True),(S/'nsswitch.conf','/etc/nsswitch.conf',True),(OLD,OLD,True),(HELPER,HELPER,True)]:args+=['--mount','type=bind,src='+str(source)+',dst='+str(target)+(',readonly'if ro else'')]
 args+=[IMAGE,'/bin/sh','-c',boot]
 (B/'combined-command.json').write_text(json.dumps({'command':args,'image':IMAGE,'network':'none','ipc':'private','headless':False,'cdp':False,'engineChromiumSha256':hashlib.sha256((B/'published-engine/chromium').read_bytes()).hexdigest(),'helperSha256':hashlib.sha256(HELPER.read_bytes()).hexdigest()},indent=2))
 sock=S/'http.sock';web=UnixServer(str(sock),Handler);threading.Thread(target=web.serve_forever,daemon=True).start();log=(S/'docker.log').open('wb');container=subprocess.Popen(args,stdout=log,stderr=subprocess.STDOUT)
 def native(*argv):
  cmd=['docker','exec','--user','1000:1000','--env','DISPLAY=:92','--env','XAUTHORITY='+str(S/'Xauthority'),NAME,str(B/'combined_x_control')]+list(map(str,argv));p=subprocess.run(cmd,capture_output=True,text=True,timeout=15)
  if p.returncode:raise RuntimeError('Native XTest/capture failed '+p.stderr)
  return json.loads(p.stdout)if p.stdout.startswith('{')else None
 def click(name):
  r=latest();p=r['buttons'][name];x=r['screenX']+(r['outerWidth']-r['innerWidth'])/2+p['x']+p['w']/2;y=r['screenY']+r['outerHeight']-r['innerHeight']+p['y']+p['h']/2;native('click',int(x),int(y))
 def shot(name):
  native('capture',str(S/(name+'.ppm')));Image.open(S/(name+'.ppm')).save(S/(name+'.png'))
 result={}
 try:
  wait(lambda:(S/'ready').exists());r=wait(latest,18);assert r['webdriver']is False
  def settled():
   with LOCK:recent=REPORTS[-4:]
   fields=['screenX','screenY','outerWidth','outerHeight','innerWidth','innerHeight'];return len(recent)==4 and all(all(v[k]==recent[-1][k]for k in fields)for v in recent)
  wait(settled);shot('native-initial')
  for attempt in range(3):
   click('play')
   try:wait(lambda:not latest()['video']['paused']and latest()['video']['decoded']>15,2);break
   except RuntimeError:
    if attempt==2:raise
  shot('native-video')
  before=latest();pcm0=(S/'output.raw').stat().st_size;bench=native('bench','6',str(S/'native-video-bench.ppm'));Image.open(S/'native-video-bench.ppm').save(S/'native-video-bench.png');after=latest();pcm1=(S/'output.raw').stat().st_size
  assert bench['frames']>=170 and bench['changedFrames']>=120 and after['video']['decoded']-before['video']['decoded']>=120
  result.update(initialFacts=r,inlineBefore=before,inlineAfter=after,inlineCapture=bench,audioMeasuredByteStart=pcm0,audioMeasuredByteEnd=pcm1)
  click('full');wait(lambda:latest()['fullscreen']=='v');time.sleep(1.2);shot('native-fullscreen-transition')
  if latest()['innerHeight']<395:
   native('click',latest()['outerWidth']-30,27);result['nativeFullscreenNoticeDismissAttempt']=True;time.sleep(.4)
  before=latest();full=native('bench','4',str(S/'native-video-fullscreen.ppm'));Image.open(S/'native-video-fullscreen.ppm').save(S/'native-video-fullscreen.png');after=latest();assert full['changedFrames']>=70 and after['video']['decoded']>before['video']['decoded']+60;result.update(fullscreenBefore=before,fullscreenAfter=after,fullscreenCapture=full)
  native('key','Escape');wait(lambda:latest()['fullscreen']is None);click('dialog');time.sleep(.3);shot('native-confirm');native('key','Return');wait(lambda:any(v.get('confirmed')is True for v in REPORTS));result['nativeConfirmAccepted']=True
  native('key','l','Control_L');native('text','chrome://sandbox');native('key','Return');time.sleep(.6);shot('native-sandbox')
  import numpy as np
  samples=np.fromfile(S/'output.raw',dtype='<i2');window=samples[pcm0//2:pcm1//2];mono=window.reshape(-1,2).mean(axis=1);nonzero=int(np.count_nonzero(window));spectrum=np.abs(np.fft.rfft(mono*np.hanning(len(mono))));frequency=float(np.fft.rfftfreq(len(mono),1/48000)[np.argmax(spectrum)]);assert nonzero>48000 and abs(frequency-440)<3
  result['audio']={'nonzeroSamples':nonzero,'peakHz':frequency,'measuredPcmBytes':pcm1-pcm0,'sampleRate':48000,'channels':2,'sampleBits':16,'helperLog':(S/'audio.log').read_text(),'physicalSpeakersTested':False}
  (S/'stop').touch();container.wait(timeout=12);assert container.returncode==0,(S/'docker.log').read_text();libs={};uids={};renderers=[];badflags=[]
  for maps in S.glob('maps-*.txt'):
   paths=sorted(set(line.split()[-1]for line in maps.read_text().splitlines()if '.so'in line and line.split()[-1].startswith('/')));bad=[p for p in paths if not p.startswith(str(B))and not p.startswith(ENGINE)and not p.startswith(str(OLD))]
   if bad:libs[maps.name]=bad
   pid=maps.stem.split('-')[1];status=(S/('status-'+pid+'.txt')).read_text();cmd=(S/('cmdline-'+pid+'.txt')).read_bytes().replace(b'\0',b' ').decode();uids[pid]=next(line for line in status.splitlines()if line.startswith('Uid:'))
   if '--type=renderer'in cmd:renderers.append({'pid':pid,'NoNewPrivs':re.search(r'^NoNewPrivs:\s*(\d+)',status,re.M).group(1),'Seccomp':re.search(r'^Seccomp:\s*(\d+)',status,re.M).group(1)})
   if any(flag in cmd for flag in ['--no-sandbox','--headless','--remote-debugging','--enable-automation']):badflags.append(cmd)
  result.update(baseLibc=(S/'base-libc.txt').read_text().strip(),nativeLibraryLeaks=libs,nativeUids=uids,rendererSandboxStatuses=renderers,badFlags=badflags,sandboxMode=(S/'sandbox-mode.txt').read_text().strip(),sandboxHash=(S/'sandbox-hash.txt').read_text().split()[0],cleanup=json.loads((S/'cleanup.json').read_text()),nativeProcesses=(S/'native-processes.txt').read_text(),commandArtifact=str(B/'combined-command.json'))
  result['success']=not libs and not badflags and bool(renderers)and all(r['NoNewPrivs']=='1'and r['Seccomp']=='2'for r in renderers)and result['sandboxMode']=='0:0:4755'and result['sandboxHash']==hashlib.sha256((B/'published-engine/chrome-sandbox').read_bytes()).hexdigest();assert result['success'];(B/'combined-result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
 finally:
  (S/'stop').touch();subprocess.run(['docker','rm','-f',NAME],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  try:container.wait(timeout=5)
  except subprocess.TimeoutExpired:container.kill();container.wait()
  log.close();web.shutdown();web.server_close();sock.unlink(missing_ok=True);(S/'Xauthority').unlink(missing_ok=True);(B/'combined-reports.json').write_text(json.dumps(REPORTS,indent=2))
if __name__=='__main__':main()
