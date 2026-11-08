#!/usr/bin/env python3
"""Generate an original local video/tone fixture outside the source-only bundle."""
import argparse,pathlib,shutil,subprocess
p=argparse.ArgumentParser();p.add_argument('--output',type=pathlib.Path,required=True);p.add_argument('--fps',type=int,choices=[30,60],default=30);p.add_argument('--ffmpeg',default='ffmpeg');a=p.parse_args();out=a.output.resolve();bundle=pathlib.Path(__file__).resolve().parents[2]
if out==bundle or bundle in out.parents:p.error('Generated media must stay outside the source-only bundle')
if out.exists():p.error('Refusing to overwrite existing fixture output')
out.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
subprocess.run([a.ffmpeg,'-hide_banner','-loglevel','error','-f','lavfi','-i','testsrc2=size=960x540:rate='+str(a.fps),'-f','lavfi','-i','sine=frequency=440:sample_rate=48000','-t','16','-c:v','libvpx','-deadline','realtime','-cpu-used','6','-b:v','2400k'if a.fps==60 else'1200k','-c:a','libopus','-b:a','64k','-n',str(out)],check=True)
print('Generated original test pattern/440Hz tone; bytes depend on the supplied FFmpeg version')
