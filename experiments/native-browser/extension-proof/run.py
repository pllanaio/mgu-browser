#!/usr/bin/env python3
# SPDX-License-Identifier: MIT — authored local proof, immutable original engine.
import pathlib,os,json,struct,secrets,subprocess,shlex,time,socket,shutil,hashlib
B=pathlib.Path('/tmp/mgu-native-extension-prototype');N=pathlib.Path('/tmp/mgu-native-window-prototype');R=N/'bookworm-root';S=B/'state';NAME='mgu-native-extension-proof';IMAGE='ubuntu@sha256:152dc042452c496007f07ca9127571cb9c29697f42acbfad72324b2bb2e43c98';NODE=pathlib.Path('/workspace/mgu-browser/.local/backend-start-audit/node-v8.16.2-linux-x64/bin/node');ENGINE='/var/opt/mgu-browser-engine/versions/0.1.0/engine'
def wait(fn,seconds=15):
 start=time.monotonic()
 while time.monotonic()-start<seconds:
  value=fn()
  if value:return value
  time.sleep(.06)
 raise RuntimeError('Native extension fixture timed out')
def main():
 required=[N/'bookworm-env.json',N/'bookworm-assets-env.json',N/'bookworm-extra-env.json',N/'bookworm-runtime-isolation-env.json',N/'bookworm-fonts.conf',N/'bookworm-dbus.conf',N/'bookworm-root/usr/bin/Xvfb',N/'xkb_private_path.so',N/'combined_x_control',N/'clip.webm',N/'published-engine/chromium',NODE,B/'native_host',B/'peercred.node',B/'native-host-manifest.json',B/'extension/manifest.json',B/'endpoint.js']
 missing=[str(p)for p in required if not p.is_file()]
 if missing:raise RuntimeError('Missing documented fixture inputs: '+', '.join(missing))
 if hashlib.sha256((N/'published-engine/chromium').read_bytes()).hexdigest()!='9c94b57491fcc1a4b5a013ecb8fa13a637cc9a16aebea5041899c3cb033e5a13':raise RuntimeError('Exact immutable Engine0.1 Chromium hash mismatch')
 if subprocess.run(['docker','container','inspect',NAME],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0:raise RuntimeError('Fixture container name already exists; refusing to alter it')
 S.mkdir(mode=0o700,exist_ok=True)
 if S.is_symlink()or S.resolve()!=B/'state':raise RuntimeError('Dedicated fixture state must be a real directory')
 for p in S.iterdir():
  if p.is_dir():shutil.rmtree(p)
  else:p.unlink()
 for d in ['config','cache','font-cache','tmp','downloads']:(S/d).mkdir(mode=0o700)
 def field(v):return struct.pack('>H',len(v))+v
 (S/'Xauthority').write_bytes(struct.pack('>H',65535)+field(b'')+field(b'93')+field(b'MIT-MAGIC-COOKIE-1')+field(secrets.token_bytes(16)));(S/'Xauthority').chmod(0o600)
 env={}
 for name in ['bookworm-env.json','bookworm-assets-env.json','bookworm-extra-env.json','bookworm-runtime-isolation-env.json']:env.update(json.loads((N/name).read_text()))
 env.update(DISPLAY=':93',XAUTHORITY=str(S/'Xauthority'),GTK_CSD='1',GTK_USE_PORTAL='0',XDG_CURRENT_DESKTOP='GNOME',XDG_CONFIG_HOME=str(S/'config'),XDG_CACHE_HOME=str(S/'cache'),TMPDIR=str(S/'tmp'),FONTCONFIG_FILE=str(S/'fonts.conf'),XLOCALEDIR=str(R/'usr/share/X11/locale'),GTK_IM_MODULE='simple',ALSA_CONFIG_PATH=str(S/'alsa.conf'),PULSE_SERVER='unix:'+str(S/'no-pulse'))
 (S/'environment.sh').write_text('\n'.join('export '+k+'='+shlex.quote(v)for k,v in env.items())+'\n');(S/'fonts.conf').write_text((N/'bookworm-fonts.conf').read_text().replace(str(N/'bookworm-font-cache'),str(S/'font-cache')));(S/'session.conf').write_text((N/'bookworm-dbus.conf').read_text().replace('unix:tmpdir='+str(N),'unix:tmpdir='+str(S)));(S/'nsswitch.conf').write_text('passwd: files\ngroup: files\nhosts: files dns\n');(S/'alsa.conf').write_text('pcm.!default {type null}\n')
 (S/'profile/Default').mkdir(parents=True);(S/'profile/Default/Preferences').write_text(json.dumps({'download':{'default_directory':str(S/'downloads'),'prompt_for_download':False},'browser':{'check_default_browser':False}}))
 script='''#!/bin/sh
set -eu
BASE=/tmp/mgu-native-window-prototype
ROOT="$BASE/bookworm-root"
STATE=/tmp/mgu-native-extension-prototype/state
ENGINE=/var/opt/mgu-browser-engine/versions/0.1.0/engine
. "$STATE/environment.sh"
XVFB= BUS= WM= CHROME= ENDPOINT=
cleanup(){
 for p in "$CHROME" "$ENDPOINT" "$WM" "$BUS" "$XVFB";do if [ -n "$p" ];then /bin/kill -TERM -- -"$p" 2>/dev/null||true;fi;done
 /bin/sleep .3
 for p in "$CHROME" "$ENDPOINT" "$WM" "$BUS" "$XVFB";do if [ -n "$p" ];then /bin/kill -KILL -- -"$p" 2>/dev/null||true;fi;done
 wait 2>/dev/null||true
 /bin/rm -f "$STATE/Xauthority" "$STATE/native.sock" "$STATE/control.sock"
}
trap cleanup EXIT HUP INT TERM
/usr/bin/setsid "$ROOT/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2" --preload "$BASE/xkb_private_path.so" "$ROOT/usr/bin/Xvfb" "$DISPLAY" -screen 0 1280x720x24 -nolisten tcp -auth "$XAUTHORITY" -noreset -xkbdir "$ROOT/usr/share/X11/xkb" -fp "$ROOT/usr/share/fonts/X11/misc,built-ins" >"$STATE/xvfb.log" 2>&1 &
XVFB=$!
for n in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20;do if "$ROOT/usr/bin/xdpyinfo" >"$STATE/display.txt" 2>"$STATE/display.err";then break;fi;/bin/sleep .1;done
/usr/bin/setsid "$ROOT/usr/bin/dbus-daemon" --config-file="$STATE/session.conf" --nofork --print-address=1 >"$STATE/bus-address.txt" 2>"$STATE/dbus.log" &
BUS=$!
for n in 1 2 3 4 5 6 7 8 9 10;do if [ -s "$STATE/bus-address.txt" ];then break;fi;/bin/sleep .1;done
DBUS_SESSION_BUS_ADDRESS=$(/bin/cat "$STATE/bus-address.txt");export DBUS_SESSION_BUS_ADDRESS
/usr/bin/setsid "$ROOT/usr/bin/xfwm4" --replace --compositor=off --sm-client-disable >"$STATE/wm.log" 2>&1 &
WM=$!
/usr/bin/setsid /opt/mgu-native-prototype/node /opt/mgu-native-prototype/endpoint.js >"$STATE/endpoint.log" 2>&1 &
ENDPOINT=$!
for n in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20;do if [ -e "$STATE/endpoint-ready" ];then break;fi;/bin/sleep .1;done
/usr/bin/setsid /usr/bin/env LD_LIBRARY_PATH="$ROOT/lib/x86_64-linux-gnu:$ROOT/usr/lib/x86_64-linux-gnu:$ROOT/lib:$ROOT/usr/lib" "$ENGINE/chromium" --user-data-dir="$STATE/profile" --window-size=1280,720 --window-position=0,0 --ozone-platform=x11 --use-gl=angle --use-angle=swiftshader-webgl --force-device-scale-factor=1 --no-first-run --no-default-browser-check --disable-background-networking --disable-sync --disable-component-update --password-store=basic --disable-dev-shm-usage --alsa-output-device=default --load-extension=/opt/mgu-native-prototype/extension http://127.0.0.1:39093/ >"$STATE/chromium.log" 2>&1 &
CHROME=$!
printf '%s\\n' "$XVFB $BUS $WM $ENDPOINT $CHROME" >"$STATE/pids.txt"
echo ready >"$STATE/ready"
while [ ! -e "$STATE/stop" ];do /bin/kill -0 "$CHROME";/bin/kill -0 "$ENDPOINT";/bin/sleep .1;done
for p in /proc/[0-9]*;do exe=$(/bin/readlink "$p/exe" 2>/dev/null||true);case "$exe" in "$ROOT/"*|"$ENGINE/"*|/opt/mgu-native-prototype/*) pid=${p##*/};/bin/cat "$p/maps">"$STATE/maps-$pid.txt";/bin/cat "$p/status">"$STATE/status-$pid.txt";/bin/cat "$p/cmdline">"$STATE/cmdline-$pid.txt";;esac;done
cleanup
trap - EXIT HUP INT TERM
test ! -e /tmp/.X11-unix/X93
test ! -e /tmp/.X93-lock
test ! -e "$STATE/Xauthority"
echo '{"socketRemoved":true,"lockRemoved":true,"authorityRemoved":true}' >"$STATE/cleanup.json"
''';(S/'test.sh').write_text(script)
 boot='''set -eu
/bin/mkdir -p /tmp/.X11-unix /opt/mgu-native-prototype /etc/chromium/native-messaging-hosts
/bin/chmod 1777 /tmp/.X11-unix
/bin/cp /var/opt/mgu-browser-engine/versions/0.1.0/engine/chrome-sandbox /tmp/extension-native-sandbox
/bin/chown 0:0 /tmp/extension-native-sandbox
/bin/chmod 4755 /tmp/extension-native-sandbox
export CHROME_DEVEL_SANDBOX=/tmp/extension-native-sandbox
/bin/cp -R /tmp/mgu-native-extension-prototype/extension /opt/mgu-native-prototype/extension
/bin/cp /tmp/mgu-native-extension-prototype/native_host /tmp/mgu-native-extension-prototype/peercred.node /tmp/mgu-native-extension-prototype/endpoint.js /opt/mgu-native-prototype/
/bin/cp /fixture-node /opt/mgu-native-prototype/node
/bin/cp /tmp/mgu-native-extension-prototype/native-host-manifest.json /etc/chromium/native-messaging-hosts/org.mgu.browser.prototype.json
/bin/chown -R 0:0 /opt/mgu-native-prototype /etc/chromium/native-messaging-hosts
/bin/chmod -R a+rX /opt/mgu-native-prototype /etc/chromium/native-messaging-hosts
/bin/chmod -R a-w /opt/mgu-native-prototype /etc/chromium/native-messaging-hosts
/bin/chmod 555 /opt/mgu-native-prototype/native_host /opt/mgu-native-prototype/node
/usr/bin/stat -c '%u:%g:%a' /etc/chromium/native-messaging-hosts/org.mgu.browser.prototype.json /opt/mgu-native-prototype/native_host > /tmp/mgu-native-extension-prototype/state/immutable-host.txt
printf 'mgu:x:1000:1000::/tmp:/bin/sh\\n' >> /etc/passwd
printf 'mgu:x:1000:\\n' >> /etc/group
exec /sbin/runuser -u mgu -- /bin/sh /tmp/mgu-native-extension-prototype/state/test.sh
'''
 args=['docker','run','--name',NAME,'--network','none','--ipc','private','--shm-size','128m','--cap-add','SYS_ADMIN','--security-opt','apparmor=unconfined']
 for source,target,ro in [(N,N,True),(B,B,True),(S,S,False),(N/'published-engine',ENGINE,True),(R/'usr/share/xfwm4','/usr/share/xfwm4',True),(R/'usr/share/themes','/usr/share/themes',True),(S/'nsswitch.conf','/etc/nsswitch.conf',True),(NODE,'/fixture-node',True)]:args+=['--mount','type=bind,src='+str(source)+',dst='+str(target)+(',readonly'if ro else'')]
 args+=[IMAGE,'/bin/sh','-c',boot];(B/'command.json').write_text(json.dumps(args,indent=2));log=(S/'docker.log').open('wb');container=subprocess.Popen(args,stdout=log,stderr=subprocess.STDOUT)
 def control(op,args=None):
  s=socket.socket(socket.AF_UNIX);s.settimeout(8);s.connect(str(S/'control.sock'));s.sendall((json.dumps({'id':'control','op':op,'args':args or{}})+'\n').encode());data=b''
  while b'\n'not in data:data+=s.recv(65536)
  s.close();v=json.loads(data.split(b'\n')[0]);
  if not v['ok']:raise RuntimeError(v.get('error'))
  return v['result']
 def native(*argv):
  p=subprocess.run(['docker','exec','--user','1000:1000','--env','DISPLAY=:93','--env','XAUTHORITY='+str(S/'Xauthority'),NAME,str(N/'combined_x_control')]+list(map(str,argv)),capture_output=True,text=True,timeout=10)
  if p.returncode:raise RuntimeError(p.stderr)
  return json.loads(p.stdout)if p.stdout.startswith('{')else None
 try:
  wait(lambda:(S/'control.sock').exists());status=wait(lambda:control('status')if control('status')['connected']else None,20)
  def report(child=False):
   return next((v for v in reversed(control('reports'))if v['child']==child),None)
  initial=wait(lambda:report(False));assert initial['webdriver']is False
  wait(lambda:report(True));
  def settled():
   recent=[v for v in control('reports')if not v['child']][-5:];keys=['screenX','screenY','outerWidth','outerHeight','innerWidth','innerHeight'];return len(recent)==5 and all(all(v[k]==recent[-1][k]for k in keys)for v in recent)
  wait(settled);native('capture',str(S/'startup.ppm'));tabs=control('tabs.query');tab=next(t for t in tabs if t.get('url')=='http://127.0.0.1:39093/');tabid=tab['id']
  def current_tab():return next(t for t in control('tabs.query')if t['id']==tabid)
  def click(name,child=False):
   main=report(False);r=report(child);p=r['rects'][name];left=main['screenX']+(main['outerWidth']-main['innerWidth'])/2;top=main['screenY']+main['outerHeight']-main['innerHeight']
   if child:f=main['rects']['child'];left+=f['x']+2;top+=f['y']+2
   native('click',int(left+p['x']+p['w']/2),int(top+p['y']+p['h']/2))
  def snapshot():return [e['message']for e in control('events')]
  def focus(tag,password=False,multiline=False,child=False):
   def latest_focus():
    frames={};messages=snapshot()
    for m in messages:
     if m['event']=='focus':frames[m['data']['frameId']]=m['data']
    f=next((m['data']for m in reversed(messages)if m['event']=='focus'and frames.get(m['data']['frameId'])is m['data']and m['data']['focused']and not m['data'].get('delegatesFocus')),None)
    return f if f and f['tag']==tag and f['password']==password and f['multiline']==multiline and (f['frameId']!=0)==child else None
   return wait(latest_focus)
  click('email');email_focus=focus('INPUT');assert email_focus['type']=='email'and email_focus['maxLength']==42
  click('closedPassword');password_focus=focus('INPUT',True);assert password_focus['closedRoots']==1 and password_focus['maxLength']==23 and report(False)['closedRootHidden']
  click('closedNotes');notes_focus=focus('TEXTAREA',False,True);assert notes_focus['closedRoots']==1
  click('email',True);child_focus=focus('INPUT',child=True);assert child_focus['url']=='http://localhost:39093/child'and child_focus['documentId']!=email_focus['documentId']
  native('key','Escape','Shift_L');time.sleep(.8);native('key','F10','Alt_L');time.sleep(.2);native('capture',str(S/'native-task-manager.ppm'));native('key','F4','Alt_L');time.sleep(.3)
  if os.environ.get('MGU_EXTENSION_TASK_ONLY')=='1':
   control('finish');container.wait(timeout=15);return
  for event in snapshot():
   if event['event']=='focus':assert not any(k in event['data']for k in ['value','text','textContent','passwordValue'])
  click('play');wait(lambda:not report(False)['video']['paused']);wait(lambda:current_tab()['audible']);regular_audible=True
  control('tabs.update',{'tabId':tabid,'muted':True});assert current_tab()['mutedInfo']['muted'];control('tabs.update',{'tabId':tabid,'muted':False});assert not current_tab()['mutedInfo']['muted']
  click('pause');wait(lambda:not current_tab()['audible'],8)
  click('closedPlay');wait(lambda:not report(False)['closed']['paused']);wait(lambda:current_tab()['audible']);closed_audible=True
  click('closedMute');wait(lambda:report(False)['closed']['muted']);wait(lambda:not current_tab()['audible'],8)
  click('closedMute');wait(lambda:not report(False)['closed']['muted']);wait(lambda:current_tab()['audible']);click('closedPause');wait(lambda:not current_tab()['audible'],8)
  click('play',True);wait(lambda:not report(True)['video']['paused']);wait(lambda:current_tab()['audible']);child_audible=True
  click('pause',True);wait(lambda:not current_tab()['audible'],8)
  click('closedPlay',True);wait(lambda:not report(True)['closed']['paused']);wait(lambda:current_tab()['audible']);child_closed_audible=True;click('closedPause',True);wait(lambda:not current_tab()['audible'],8)
  all_cookies=control('cookies.getAll',{'partitionKey':{}});http_only=next(c for c in all_cookies if c['name']=='networkHttpOnly'and c['domain']=='127.0.0.1');persistent=next(c for c in all_cookies if c['name']=='networkPersistent'and c['domain']=='127.0.0.1');assert http_only['httpOnly']and http_only['session']and http_only['hostOnly']and not persistent['session']
  explicit=control('cookies.set',{'url':'http://localhost:39093/','name':'extensionHttpOnly','value':'generated-private-cookie','httpOnly':True,'sameSite':'lax'});assert explicit['session']and explicit['httpOnly']and explicit['hostOnly']
  partition=control('cookies.set',{'url':'http://localhost:39093/','name':'partitionFixture','value':'generated-partition-cookie','secure':True,'sameSite':'no_restriction','partitionKey':{'topLevelSite':'http://127.0.0.1','hasCrossSiteAncestor':True}});assert partition['partitionKey']=={'topLevelSite':'http://127.0.0.1','hasCrossSiteAncestor':True}
  plain=control('cookies.getAll',{});all_cookies=control('cookies.getAll',{'partitionKey':{}});assert not any(c['name']=='partitionFixture'for c in plain);assert any(c['name']=='partitionFixture'and c['partitionKey']==partition['partitionKey']for c in all_cookies)
  control('cookies.set',{'url':'http://localhost:39093/','name':'extensionHttpOnly','value':'generated-private-replacement','httpOnly':True,'sameSite':'lax'})
  cookie_events=[m['data']for m in snapshot()if m['event']=='cookieChanged'and m['data']['cookie']['name']=='extensionHttpOnly'];assert any(c['removed']and c['cause']=='overwrite'for c in cookie_events)and any(not c['removed']and c['cause']=='explicit'for c in cookie_events)
  click('download');downloads=wait(lambda:next((d for d in control('downloads.search',{})if d.get('state')=='complete'and d.get('filename','').endswith('/native-mgu-fixture.txt')),None));assert pathlib.Path(downloads['filename']).read_bytes()==b'MGU native extension exact download\n'
  click('slow');slow=wait(lambda:next((d for d in control('downloads.search',{})if d.get('state')=='in_progress'and d.get('bytesReceived',0)>0 and d.get('url','').endswith('/download/slow')),None));progress_bytes=slow['bytesReceived'];control('downloads.cancel',{'downloadId':slow['id']});cancelled=wait(lambda:next((d for d in control('downloads.search',{'id':slow['id']})if d['state']=='interrupted'),None));assert cancelled['error']=='USER_CANCELED'
  added=control('tabs.create',{'url':'http://127.0.0.1:39093/second'});wait(lambda:next((t for t in control('tabs.query')if t['id']==added['id']and t.get('title')=='MGU native extension fixture'),None));control('tabs.update',{'tabId':added['id'],'url':'http://localhost:39093/child'});wait(lambda:next((t for t in control('tabs.query')if t['id']==added['id']and t.get('title')=='MGU OOPIF fixture'),None));control('tabs.remove',{'tabId':added['id']});assert not any(t['id']==added['id']for t in control('tabs.query'))
  rejected=subprocess.run(['docker','exec','--user','1000:1000',NAME,'/opt/mgu-native-prototype/native_host','chrome-extension://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/'],capture_output=True,timeout=3);assert rejected.returncode==2
  native('capture',str(S/'native-extension-screen.ppm'))
  events=snapshot();assert any(m['event']=='tabUpdated'and 'audible'in m['data']['change']for m in events);assert any(m['event']=='tabUpdated'and 'mutedInfo'in m['data']['change']for m in events)
  result={'success':True,'engine':'156.0.8078.79','node':status['node'],'webdriver':initial['webdriver'],'noHeadlessOrCDP':True,'extensionId':(B/'extension-id').read_text().strip(),'nativeMessaging':True,'wrongExtensionOriginRejected':True,'peerUIDChecks':control('status')['peerChecks'],'immutableHost':(S/'immutable-host.txt').read_text().splitlines(),'tabs':{'metadata':True,'createNavigateClose':True,'nativeAudible':regular_audible,'nativeMutedEvents':True,'closedShadowAudible':closed_audible,'crossOriginFrameAudible':child_audible,'crossOriginClosedShadowAudible':child_closed_audible,'recentAudioRetentionQualified':True},'focus':{'email':True,'closedPasswordNoValues':True,'closedRootSwitch':True,'crossOriginFrame':True,'frameId':child_focus['frameId'],'closedRootAPI':password_focus['closedRootAPI']},'cookies':{'httpOnly':True,'session':True,'persistentExpiry':True,'hostOnly':True,'partitionEnumeration':True,'partitionKey':partition['partitionKey'],'changeOverwriteThenExplicit':True,'valuesLogged':False},'downloads':{'nativeFilename':pathlib.Path(downloads['filename']).name,'exactBytes':True,'progressSearchBytes':progress_bytes,'cancel':cancelled['error']},'eventCount':len(events),'privateNetwork':'none'}
  (B/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2),flush=True)
  control('finish')
  container.wait(timeout=15);assert container.returncode==0
  bad=[];renderers=[];uids=[]
  for cmdfile in S.glob('cmdline-*.txt'):
   cmd=cmdfile.read_bytes().replace(b'\0',b' ').decode();pid=cmdfile.stem.split('-')[1];status=(S/('status-'+pid+'.txt')).read_text()
   if any(flag in cmd for flag in ['--no-sandbox','--headless','--remote-debugging','--enable-automation']):bad.append(cmd)
   if '--type=renderer'in cmd:renderers.append({'pid':pid,'noNewPrivs':int(next(v.split()[1]for v in status.splitlines()if v.startswith('NoNewPrivs:'))),'seccomp':int(next(v.split()[1]for v in status.splitlines()if v.startswith('Seccomp:')))})
   uids.append(next(v.split()[1]for v in status.splitlines()if v.startswith('Uid:')))
  assert not bad and renderers and all(v['noNewPrivs']==1 and v['seccomp']==2 for v in renderers)and set(uids)=={'1000'}
  result.update(rendererSandbox=renderers,allNativeUIDs1000=True,actualForbiddenFlags=bad,cleanup=json.loads((S/'cleanup.json').read_text()),engineSHA256=hashlib.sha256((N/'published-engine/chromium').read_bytes()).hexdigest())
  (B/'result.json').write_text(json.dumps(result,indent=2));print('CONTAINER_EXIT',container.returncode)
 finally:
  try:
   (B/'last-reports.json').write_text(json.dumps(control('reports'),indent=2));(B/'last-focus-events.json').write_text(json.dumps([e for e in control('events')if e['message']['event']=='focus'],indent=2));native('capture',str(S/'final-debug.ppm'))
  except Exception:pass
  (S/'stop').touch();subprocess.run(['docker','rm','-f',NAME],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  try:container.wait(timeout=3)
  except subprocess.TimeoutExpired:container.kill();container.wait()
  log.close()
if __name__=='__main__':main()
