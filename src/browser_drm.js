'use strict';
// Optional, administrator-provisioned CDM. Never download, copy or execute a CDM
// in Node. Chromium validates its own CDM ABI and loads it inside its sandbox.
const fs=require('fs'),path=require('path');
const HINT='latest-component-updated-widevine-cdm';
function owned(stat,uid){return (stat.uid===0||stat.uid===uid)&&!(stat.mode&0o022)&&!stat.isSymbolicLink();}
function directories(directory,uid){
    if(typeof directory!=='string'||directory.length>4096||directory.indexOf('\0')>=0||!path.isAbsolute(directory)||path.normalize(directory)!==directory)throw Error('CDM directory rejected');
    let current='/';
    for(const part of directory.split('/').filter(Boolean)){current=path.join(current,part);const st=fs.lstatSync(current);if(!st.isDirectory()||!owned(st,uid))throw Error('CDM directory permissions rejected');}
}
function readOwned(file,uid,max,head){
    const fd=fs.openSync(file,fs.constants.O_RDONLY|fs.constants.O_NOFOLLOW);
    try{const st=fs.fstatSync(fd);if(!st.isFile()||st.nlink!==1||!owned(st,uid)||st.size>max||st.size<(head||0))throw Error('CDM file rejected');
        if(head){const bytes=Buffer.alloc(head);if(fs.readSync(fd,bytes,0,head,0)!==head)throw Error('CDM header rejected');return bytes;}
        return fs.readFileSync(fd,'utf8');
    }finally{fs.closeSync(fd);}
}
function validate(directory,uid){
    directories(directory,uid);
    const manifest=JSON.parse(readOwned(path.join(directory,'manifest.json'),uid,65536));
    if(!manifest||!/^\d{1,6}\.\d{1,6}\.\d{1,6}\.\d{1,6}$/.test(manifest.version||'')||(manifest.os&&manifest.os!=='linux')||(manifest.arch&&manifest.arch!=='x64'))throw Error('CDM manifest rejected');
    for(const key of ['x-cdm-module-versions','x-cdm-interface-versions','x-cdm-host-versions'])if(typeof manifest[key]!=='string'||!/^\d+(,\d+)*$/.test(manifest[key]))throw Error('CDM ABI declaration rejected');
    const platform=path.join(directory,'_platform_specific/linux_x64');directories(platform,uid);
    const elf=readOwned(path.join(platform,'libwidevinecdm.so'),uid,128*1024*1024,64);
    if(elf.slice(0,4).toString('hex')!=='7f454c46'||elf[4]!==2||elf[5]!==1||elf[6]!==1||elf.readUInt16LE(16)!==3||elf.readUInt16LE(18)!==62||elf.readUInt32LE(20)!==1||elf.readUInt16LE(52)!==64)throw Error('Linux x86_64 CDM required');
    return {directory,version:manifest.version};
}
function configuration(file,uid){
    uid=uid===undefined?0:uid;directories(path.dirname(file),uid);
    let data;try{data=readOwned(file,uid,8192);}catch(e){if(e.code==='ENOENT')return null;throw e;}
    const value=JSON.parse(data);
    if(!value||typeof value.directory!=='string'||Object.keys(value).some(k=>k!=='directory'))throw Error('CDM configuration rejected');
    return validate(value.directory,uid);
}
// Chromium's own component updater stores a downloaded CDM as
// <root>/WidevineCdm/<version>/{manifest.json,_platform_specific/linux_x64/...}.
// The cache belongs to the backend user. Pick the newest version that passes
// the same checks as an administrator-provided module.
function versionKey(v){return v.split('.').map(n=>('000000'+n).slice(-6)).join('.');}
function cache(root,uid){
    if(typeof root!=='string'||!path.isAbsolute(root))return null;
    const base=path.join(root,'WidevineCdm');let names;
    try{directories(base,uid);names=fs.readdirSync(base);}catch(e){return null;}
    names=names.filter(n=>/^\d{1,6}\.\d{1,6}\.\d{1,6}\.\d{1,6}$/.test(n)).sort((a,b)=>versionKey(b)<versionKey(a)?-1:1);
    for(const name of names){try{const selected=validate(path.join(base,name),uid);if(selected.version===name)return selected;}catch(e){}}
    return null;
}
function prepare(profile,options){
    options=options||{};let selected=null,reason='no-cdm',source=null;
    try{
        if(options.cdmConfig){selected=configuration(options.cdmConfig);source='administrator';}
        else if(options.cdmDirectory){selected=validate(options.cdmDirectory,process.getuid());source='development';}
        if(selected)reason='configured';
    }catch(e){reason='configuration-rejected';selected=null;}
    // Fallback: a module Chromium itself downloaded from Google's component
    // update service (see browser_cdm_provision.js). An explicit administrator
    // module always takes precedence.
    if(!selected&&options.cdmCache){selected=cache(options.cdmCache,process.getuid());if(selected){reason='configured';source='component';}}
    // A restored profile must not select a different native library. Even with
    // no configured CDM, overwrite Chromium's hint with the empty selection.
    const directory=path.join(profile,'WidevineCdm');
    try{fs.mkdirSync(directory,0o700);}catch(e){if(e.code!=='EEXIST')throw e;}
    const st=fs.lstatSync(directory);if(!st.isDirectory()||st.isSymbolicLink()||st.uid!==process.getuid())throw Error('Unsafe CDM profile directory');
    fs.chmodSync(directory,0o700);
    const file=path.join(directory,HINT);try{fs.unlinkSync(file);}catch(e){if(e.code!=='ENOENT')throw e;}
    fs.writeFileSync(file,JSON.stringify({Path:selected?selected.directory:''})+'\n',{mode:0o600,flag:'wx'});
    return {configured:!!selected,configuration:reason,source:selected?source:null,version:selected?selected.version:null,recognized:false,protectedPlaybackVerified:false};
}
function status(prepared,probe){
    const result=Object.assign({configured:false,configuration:'no-cdm',version:null,recognized:false,protectedPlaybackVerified:false},prepared||{});
    if(probe){result.recognized=probe.state==='recognized';result.state=probe.state;result.error=probe.error||null;
        if(probe.robustness&&typeof probe.robustness==='object')result.robustness={swSecureCrypto:probe.robustness.swSecureCrypto===true,swSecureDecode:probe.robustness.swSecureDecode===true,hwSecureAll:probe.robustness.hwSecureAll===true};
        if(typeof probe.cbcs==='boolean')result.cbcs=probe.cbcs;
        if(['usable','output-restricted','output-downscaled','internal-error','unknown'].includes(probe.hdcp))result.hdcp=probe.hdcp;
        // L3 (software) is what desktop Linux Chrome has: providers cap it,
        // typically at 720p, but it is the level Netflix/Disney+/Prime accept on Linux.
        if(result.robustness)result.securityLevel=result.robustness.hwSecureAll?'L1':result.robustness.swSecureCrypto?'L3':null;
    }
    else result.state='not-tested';
    return result;
}
// Fixed JavaScript, no license server calls or provider/account requests.
const probeScript=`(async()=>{
    const video=document.createElement("video"),audio=document.createElement("audio");
    const result={secure:isSecureContext,h264:!!video.canPlayType('video/mp4; codecs="avc1.42E01E"'),vp9:!!video.canPlayType('video/webm; codecs="vp9"'),aac:!!audio.canPlayType('audio/mp4; codecs="mp4a.40.2"'),opus:!!audio.canPlayType('audio/webm; codecs="opus"'),widevine:false,drm:{state:"unavailable",error:null}};
    if(!isSecureContext){result.drm.state="insecure-context";return JSON.stringify(result);}
    if(!navigator.requestMediaKeySystemAccess){result.drm.state="eme-unavailable";return JSON.stringify(result);}
    let timer;
    try{
        await Promise.race([(async()=>{
            const access=await navigator.requestMediaKeySystemAccess("com.widevine.alpha",[
                {initDataTypes:["cenc"],videoCapabilities:[{contentType:'video/mp4; codecs="avc1.42E01E"'}]},
                {initDataTypes:["cenc"],videoCapabilities:[{contentType:'video/webm; codecs="vp9"'}]}
            ]);
            const keys=await access.createMediaKeys();
            result.widevine=true;result.drm.state="recognized";
            // What streaming players ask for. Software CDMs (L3) offer the SW_*
            // levels only; HW_SECURE_ALL (L1) needs a certified hardware path.
            const level=async(robustness,scheme)=>{const capability={contentType:'video/mp4; codecs="avc1.42E01E"',robustness};if(scheme)capability.encryptionScheme=scheme;
                try{await navigator.requestMediaKeySystemAccess("com.widevine.alpha",[{initDataTypes:["cenc"],videoCapabilities:[capability]}]);return true;}catch(e){return false;}};
            result.drm.robustness={swSecureCrypto:await level("SW_SECURE_CRYPTO"),swSecureDecode:await level("SW_SECURE_DECODE"),hwSecureAll:await level("HW_SECURE_ALL")};
            result.drm.cbcs=await level("SW_SECURE_CRYPTO","cbcs");
            if(keys&&typeof keys.getStatusForPolicy==="function"){
                try{const hdcp=await keys.getStatusForPolicy({minHdcpVersion:"1.0"});result.drm.hdcp=["usable","output-restricted","output-downscaled","internal-error"].includes(hdcp)?hdcp:"unknown";}
                catch(e){result.drm.hdcp="unknown";}
            }
        })(),new Promise((_,reject)=>{timer=setTimeout(()=>{const e=new Error();e.name="TimeoutError";reject(e);},4000);})]);
    }catch(e){if(!result.widevine){result.drm.error=["NotSupportedError","SecurityError","InvalidStateError","QuotaExceededError","TimeoutError","OperationError"].includes(e.name)?e.name:"UnknownError";result.drm.state=e.name==="TimeoutError"?"timed-out":"unavailable";}}
    finally{clearTimeout(timer);}
    return JSON.stringify(result);
})()`;
module.exports={validate,configuration,cache,prepare,status,probeScript,HINT};
