import pathlib,os,subprocess,signal,time,json,secrets,hashlib
if any((p/'SOURCE_ONLY').is_file()for p in pathlib.Path(__file__).resolve().parents):raise SystemExit('Historical fixture script: copy it to the explicit external workspace documented in native-gui-proof/README.md before running; outputs do not belong in the source-only bundle.')
BASE=pathlib.Path(__file__).resolve().parent;ROOT=BASE/'bookworm-root';env=dict(os.environ);env.update(json.loads((BASE/'bookworm-env.json').read_text()));env.update(GTK_CSD='1',GTK_USE_PORTAL='0',XDG_CURRENT_DESKTOP='GNOME',XDG_CONFIG_HOME=str(BASE/'config'),XDG_CACHE_HOME=str(BASE/'cache'))
display=next(':'+str(n)for n in range(219,299)if not pathlib.Path('/tmp/.X11-unix/X'+str(n)).exists());auth=BASE/'bookworm-smoke.Xauthority';auth.touch(mode=0o600);auth.chmod(0o600);env.update(DISPLAY=display,XAUTHORITY=str(auth));children=[];logs=[];results={}
try:
 subprocess.run([str(ROOT/'usr/bin/xauth'),'-f',str(auth),'add',display,'.',secrets.token_hex(16)],check=True,env=env,capture_output=True)
 def launch(args,name,capture=False):
  log=(BASE/(name+'.log')).open('wb');logs.append(log);p=subprocess.Popen(args,env=env,stdout=subprocess.PIPE if capture else log,stderr=log,start_new_session=True);children.append(p);return p
 server=launch(['/usr/bin/strace','-f','-e','trace=execve','-o',str(BASE/'bookworm-xvfb-exec.log'),str(ROOT/'lib/x86_64-linux-gnu/ld-linux-x86-64.so.2'),'--preload',str(BASE/'xkb_private_path.so'),str(ROOT/'usr/bin/Xvfb'),display,'-screen','0','1280x400x24','-nolisten','tcp','-auth',str(auth),'-noreset','-xkbdir',str(ROOT/'usr/share/X11/xkb'),'-fp',str(ROOT/'usr/share/fonts/X11/misc')+',built-ins'],'bookworm-smoke-xvfb')
 for n in range(100):
  if pathlib.Path('/tmp/.X11-unix/X'+display[1:]).exists():break
  if server.poll() is not None:raise RuntimeError('Private Xvfb exited')
  time.sleep(.05)
 results['displayInfo']=subprocess.check_output([str(ROOT/'usr/bin/xdpyinfo'),'-display',display],env=env,text=True)
 bus=launch([str(ROOT/'usr/bin/dbus-daemon'),'--config-file='+str(BASE/'bookworm-dbus.conf'),'--nofork','--print-address=1'],'bookworm-smoke-dbus',True);env['DBUS_SESSION_BUS_ADDRESS']=bus.stdout.readline().decode().strip();assert env['DBUS_SESSION_BUS_ADDRESS'].startswith('unix:')
 wm=launch([str(ROOT/'usr/bin/xfwm4'),'--replace','--compositor=off','--sm-client-disable'],'bookworm-smoke-wm');time.sleep(2);assert wm.poll()is None,'WM exited'
 results['wmRootProperties']=subprocess.check_output([str(ROOT/'usr/bin/xprop'),'-root','_NET_SUPPORTING_WM_CHECK','_NET_SUPPORTED'],env=env,text=True)
 results['processMaps']={}
 for p in pathlib.Path('/proc').iterdir():
  if not p.name.isdigit():continue
  try:
   stat=(p/'stat').read_text();tail=stat[stat.rfind(')')+2:].split()
   if int(tail[2])not in {x.pid for x in children}:continue
   maps=(p/'maps').read_text();libs=sorted(set(line.split()[-1]for line in maps.splitlines()if '.so'in line and line.split()[-1].startswith('/')));results['processMaps'][p.name]={'exe':os.readlink(p/'exe'),'sharedObjects':libs,'hostGraphicsLeaks':[x for x in libs if not x.startswith(str(ROOT))and x!=str(BASE/'xkb_private_path.so')],'cmdline':(p/'cmdline').read_bytes().replace(b'\0',b' ').decode()}
  except (OSError,ValueError):pass
 results['xkbExecTrace']=(BASE/'bookworm-xvfb-exec.log').read_text();results['xkbPrivateCompilerUsed']=str(ROOT/'usr/bin/xkbcomp')in results['xkbExecTrace'];results['hasMitShm']='MIT-SHM'in results['displayInfo'];results['hasXTest']='XTEST'in results['displayInfo'];results['hasDamage']='DAMAGE'in results['displayInfo'];results['hasRandr']='RANDR'in results['displayInfo'];results['has1280x400']='dimensions:    1280x400 pixels'in results['displayInfo'];results['success']=all(results[k]for k in ['xkbPrivateCompilerUsed','hasMitShm','hasXTest','hasDamage','hasRandr','has1280x400'])
 # The host strace process is instrumentation, not part of the runtime graphics stack.
 results['nativeRuntimeHostLeaks']={pid:r['hostGraphicsLeaks']for pid,r in results['processMaps'].items()if r['exe']!= '/usr/bin/strace' and r['hostGraphicsLeaks']}
 assert results['success']and not results['nativeRuntimeHostLeaks']
 (BASE/'bookworm-stack-smoke.json').write_text(json.dumps(results,indent=2));print(json.dumps({k:results[k]for k in ['success','xkbPrivateCompilerUsed','hasMitShm','hasXTest','hasDamage','hasRandr','has1280x400','nativeRuntimeHostLeaks']},indent=2))
finally:
 for p in reversed(children):
  try:os.killpg(p.pid,signal.SIGTERM)
  except ProcessLookupError:pass
 for p in reversed(children):
  try:p.wait(timeout=5)
  except subprocess.TimeoutExpired:
   try:os.killpg(p.pid,signal.SIGKILL)
   except ProcessLookupError:pass
   p.wait()
 for log in logs:log.close()
 auth.unlink(missing_ok=True)
