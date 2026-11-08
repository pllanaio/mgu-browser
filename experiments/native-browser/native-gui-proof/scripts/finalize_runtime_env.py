#!/usr/bin/env python3
"""Write explicit private runtime-data paths after the core/assets/add-on steps."""
import argparse,json,pathlib
p=argparse.ArgumentParser();p.add_argument('--workspace',required=True);a=p.parse_args();b=pathlib.Path(a.workspace).resolve();r=b/'bookworm-root';locale=b/'bookworm-locale/usr/lib/locale'
if not (locale/'C.utf8/LC_CTYPE').is_file():p.error('Manifest-pinned Debian12 C.utf8 locale data is required')
f=b/'bookworm-env.json';env=json.loads(f.read_text());env.update(XDG_CONFIG_DIRS=str(r/'etc/xdg'),GDK_BACKEND='x11',GTK_MODULES='',GIO_MODULE_DIR=str(r/'usr/lib/x86_64-linux-gnu/gio/modules'),GSETTINGS_BACKEND='memory',LIBGL_DRIVERS_PATH=str(r/'usr/lib/x86_64-linux-gnu/dri'),XCURSOR_PATH=str(r/'usr/share/icons'));f.write_text(json.dumps(env,indent=2)+'\n')
isolation={'GCONV_PATH':str(r/'usr/lib/x86_64-linux-gnu/gconv'),'LOCPATH':str(locale),'LANG':'C.utf8','LC_ALL':'C.utf8'};(b/'bookworm-runtime-isolation-env.json').write_text(json.dumps(isolation,indent=2)+'\n')
print('Configured private XDG/GIO/GL/gconv/locale data paths')
