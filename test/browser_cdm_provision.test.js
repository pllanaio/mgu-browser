'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('fs'),path=require('path');
const DRM=require('../src/browser_drm'),{CdmProvisioner,engineArguments}=require('../src/browser_cdm_provision');
function root(){
    const parent=path.resolve('.local');try{fs.mkdirSync(parent,0o700);}catch(e){if(e.code!=='EEXIST')throw e;}
    return fs.mkdtempSync(path.join(parent,'cdm-provision-'));
}
// Non-executable ELF header fixture; no proprietary CDM bytes.
function writeVersion(base,version,options){
    options=options||{};const dir=path.join(base,'WidevineCdm',version),lib=path.join(dir,'_platform_specific/linux_x64');
    for(const d of [path.join(base,'WidevineCdm'),dir,path.join(dir,'_platform_specific'),lib]){try{fs.mkdirSync(d,0o755);}catch(e){if(e.code!=='EEXIST')throw e;}}
    fs.writeFileSync(path.join(dir,'manifest.json'),JSON.stringify({version:options.manifestVersion||version,'x-cdm-module-versions':'4','x-cdm-interface-versions':'10','x-cdm-host-versions':'10,11',platforms:[{os:'linux',arch:'x64'}]}),{mode:0o644});
    const elf=Buffer.alloc(64);elf.write('7f454c46',0,'hex');elf[4]=2;elf[5]=1;elf[6]=1;elf.writeUInt16LE(3,16);elf.writeUInt16LE(options.machine||62,18);elf.writeUInt32LE(1,20);elf.writeUInt16LE(64,52);
    fs.writeFileSync(path.join(lib,'libwidevinecdm.so'),elf,{mode:0o644});
    return dir;
}
test('component cache selects the newest complete x86_64 module and ignores broken ones',()=>{
    const r=root();try{
        assert.equal(DRM.cache(r,process.getuid()),null);
        writeVersion(r,'4.10.2830.0');writeVersion(r,'4.10.10000.0',{machine:183});writeVersion(r,'4.10.9000.0',{manifestVersion:'4.10.1.0'});
        fs.mkdirSync(path.join(r,'WidevineCdm','4.10.9999.0'));// incomplete download
        assert.equal(DRM.cache(r,process.getuid()).version,'4.10.2830.0');
        writeVersion(r,'4.10.3112.0');assert.equal(DRM.cache(r,process.getuid()).version,'4.10.3112.0');
        const profile=path.join(r,'profile');fs.mkdirSync(profile,0o700);
        const prepared=DRM.prepare(profile,{cdmCache:r});
        assert.equal(prepared.source,'component');assert.equal(prepared.version,'4.10.3112.0');
        assert.equal(JSON.parse(fs.readFileSync(path.join(profile,'WidevineCdm',DRM.HINT))).Path,path.join(r,'WidevineCdm','4.10.3112.0'));
        // An explicit module wins over the cache.
        fs.mkdirSync(path.join(r,'admin'),0o755);const own=writeVersion(path.join(r,'admin'),'4.10.1.0');
        assert.equal(DRM.prepare(profile,{cdmDirectory:own,cdmCache:r}).source,'development');
    }finally{fs.rmSync(r,{recursive:true,force:true});}
});
test('engine for provisioning keeps the sandbox, runs the updater and gets no page or debugging access',()=>{
    const args=engineArguments('/x/cache');
    assert(args.includes('--component-updater=fast-update'));assert(args.includes('--user-data-dir=/x/cache'));assert(args.includes('--ozone-platform=headless'));
    for(const forbidden of ['--no-sandbox','--disable-component-update','--disable-background-networking','--remote-debugging-port','--headless'])assert(!args.some(a=>a===forbidden||a.indexOf(forbidden+'=')===0),forbidden);
    assert.equal(args[args.length-1],'about:blank');
});
test('provisioning resolves once the engine has written a valid module and stops the engine',async()=>{
    const r=root(),engine=path.join(r,'fake-engine.js'),pidFile=path.join(r,'pid');
    // Fake engine: writes a module after a short delay, then idles like Chromium.
    fs.writeFileSync(engine,'#!'+process.execPath+'\n'+
        'const fs=require("fs"),path=require("path");const dir=process.argv.find(a=>a.indexOf("--user-data-dir=")===0).slice(16);\n'+
        'fs.writeFileSync('+JSON.stringify(pidFile)+',String(process.pid));\n'+
        'setTimeout(()=>{('+writeVersion.toString()+')(dir,"4.10.3112.0");},300);setInterval(()=>{},1000);\n',{mode:0o755});
    try{
        const p=new CdmProvisioner({binary:engine,root:path.join(r,'cache'),pollMs:50,timeoutMs:10000});
        const result=await p.start();assert.equal(result.version,'4.10.3112.0');
        const st=p.status();assert.equal(st.phase,'ready');assert.equal(st.installed,'4.10.3112.0');assert.equal(st.running,false);
        assert.equal(fs.statSync(path.join(r,'cache')).mode&0o777,0o700);
        const pid=Number(fs.readFileSync(pidFile,'utf8'));
        for(let i=0;i<50;i++){try{process.kill(pid,0);}catch(e){break;}await new Promise(x=>setTimeout(x,50));}
        assert.throws(()=>process.kill(pid,0),'engine stopped');
    }finally{fs.rmSync(r,{recursive:true,force:true});}
});
test('provisioning reports a timeout or an engine that exits without a module',async()=>{
    const r=root();try{
        const idle=path.join(r,'idle.js');fs.writeFileSync(idle,'#!'+process.execPath+'\nsetInterval(()=>{},1000);\n',{mode:0o755});
        let p=new CdmProvisioner({binary:idle,root:path.join(r,'a'),pollMs:50,timeoutMs:300});
        await assert.rejects(p.start(),/download-timeout/);assert.equal(p.status().phase,'failed');
        const quit=path.join(r,'quit.js');fs.writeFileSync(quit,'#!'+process.execPath+'\nprocess.exit(3);\n',{mode:0o755});
        p=new CdmProvisioner({binary:quit,root:path.join(r,'b'),pollMs:50,timeoutMs:5000});
        await assert.rejects(p.start(),/engine-exited/);
        p=new CdmProvisioner({binary:idle,root:path.join(r,'c'),pollMs:50,timeoutMs:5000});
        const pending=p.start();p.stop();await assert.rejects(pending,/cancelled/);
    }finally{fs.rmSync(r,{recursive:true,force:true});}
});
