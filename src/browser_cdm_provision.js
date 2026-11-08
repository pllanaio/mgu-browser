'use strict';
// Widevine through Chromium's own component updater.
//
// Linux Chromium builds with Widevine support register the "Widevine Content
// Decryption Module" component and download it from Google's component update
// service, exactly as desktop Chrome/Chromium on Linux does. This module starts
// the installed engine once, with a dedicated persistent user-data directory,
// lets the updater fetch the module and stops the engine as soon as a complete,
// valid version is on disk. Sessions then point Chromium's hint file at it
// (browser_drm.js, option cdmCache).
//
// Never downloads, unpacks, copies, patches or executes the CDM in Node. Never
// touches licenses, keys or provider accounts. Node 8 compatible (MGU runtime).
const cp=require('child_process'),fs=require('fs'),path=require('path'),EventEmitter=require('events');
const DRM=require('./browser_drm');

function privateDirectory(directory){
    try{fs.mkdirSync(directory,0o700);}catch(e){if(e.code!=='EEXIST')throw e;}
    const st=fs.lstatSync(directory);
    if(!st.isDirectory()||st.isSymbolicLink()||st.uid!==process.getuid())throw new Error('Unsafe CDM cache directory');
    fs.chmodSync(directory,0o700);
}
// Fixed engine arguments. A regular (non --headless) browser on the headless
// Ozone platform runs the component updater like desktop Chromium; it shows
// nothing and needs no display. Sandbox stays on.
function engineArguments(root){
    return ['--ozone-platform=headless','--disable-gpu','--no-first-run','--no-default-browser-check',
        '--disable-sync','--disable-extensions','--disable-breakpad','--disable-dev-shm-usage','--mute-audio',
        '--password-store=basic','--use-mock-keychain',
        '--component-updater=fast-update','--user-data-dir='+root,'about:blank'];
}

class CdmProvisioner extends EventEmitter{
    constructor(options){
        super();
        if(!options||typeof options.binary!=='string'||typeof options.root!=='string'||!path.isAbsolute(options.root))throw new Error('CDM provisioning requires an engine and an absolute cache directory');
        this.options=options;this.child=null;this.timer=null;this.poll=null;
        this.state={phase:'idle',version:null,error:null,started:0,finished:0};
        this.timeoutMs=options.timeoutMs||5*60*1000;this.pollMs=options.pollMs||2000;
    }
    status(){
        const current=DRM.cache(this.options.root,process.getuid());
        return {phase:this.state.phase,error:this.state.error,installed:current?current.version:null,
            running:!!this.child,startedAt:this.state.started||null,finishedAt:this.state.finished||null};
    }
    // Resolves with the validated module or rejects with a short reason.
    start(){
        if(this.child)return this.pending;
        if(process.platform!=='linux'||process.getuid()===0)return Promise.reject(new Error('CDM provisioning requires an unprivileged Linux user'));
        privateDirectory(this.options.root);
        this.state={phase:'downloading',version:null,error:null,started:Date.now(),finished:0};this.emit('status',this.status());
        this.pending=new Promise((resolve,reject)=>{
            this.settle={resolve,reject};let child;
            try{child=cp.spawn(this.options.binary,engineArguments(this.options.root),{stdio:['ignore','ignore','pipe'],detached:true,env:Object.assign({},process.env,this.options.env||{})});}
            catch(e){return this.finish('engine-start-failed',null);}
            this.child=child;
            child.stderr.on('data',data=>this.emit('diagnostic',data.toString('utf8').slice(0,600)));
            child.on('error',()=>this.finish('engine-start-failed',null));
            child.once('exit',()=>{if(this.child===child){this.child=null;const found=DRM.cache(this.options.root,process.getuid());this.finish(found?null:'engine-exited',found);}});
            this.poll=setInterval(()=>{const found=DRM.cache(this.options.root,process.getuid());if(found)this.finish(null,found);},this.pollMs);
            this.timer=setTimeout(()=>this.finish('download-timeout',null),this.timeoutMs);
        });
        return this.pending;
    }
    finish(error,found){
        if(this.state.phase!=='downloading')return;
        clearInterval(this.poll);clearTimeout(this.timer);this.poll=this.timer=null;
        const child=this.child;this.child=null;
        if(child){
            // Give the updater a moment to finish writing its hint file, then
            // end the whole process group.
            const kill=signal=>{try{process.kill(-child.pid,signal);}catch(e){}};
            kill('SIGTERM');const hard=setTimeout(()=>kill('SIGKILL'),5000);if(hard.unref)hard.unref();
        }
        this.state.phase=error?'failed':'ready';this.state.error=error||null;this.state.version=found?found.version:null;this.state.finished=Date.now();
        this.emit('status',this.status());
        const settle=this.settle;this.settle=null;
        if(settle){if(error)settle.reject(new Error(error));else settle.resolve({version:found.version});}
    }
    stop(){if(this.state.phase==='downloading')this.finish('cancelled',null);}
}
module.exports={CdmProvisioner,engineArguments};
