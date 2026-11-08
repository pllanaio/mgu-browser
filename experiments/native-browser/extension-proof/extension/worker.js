'use strict';
// SPDX-License-Identifier: MIT — original MGU prototype, no page-world bridge.
const HOST='org.mgu.browser.prototype';let port,sequence=0;
const tabView=t=>({id:t.id,windowId:t.windowId,url:t.url,title:t.title,status:t.status,active:t.active,audible:!!t.audible,mutedInfo:t.mutedInfo,incognito:t.incognito});
function send(event,data){if(port)try{port.postMessage({v:1,seq:++sequence,kind:'event',event,data});}catch(e){}}
const own=(o,k)=>Object.prototype.hasOwnProperty.call(o,k);
async function command(message){
 if(!message||message.v!==1||message.kind!=='command'||typeof message.id!=='string'||message.id.length>96||!message.args||typeof message.args!=='object')return;
 let result;const a=message.args;
 try{
  switch(message.op){
   case 'tabs.query':result=(await chrome.tabs.query({})).map(tabView);break;
   case 'tabs.create':if(typeof a.url!=='string'||!/^https?:\/\//.test(a.url))throw Error('Explicit HTTP(S) URL required');result=tabView(await chrome.tabs.create({url:a.url,active:a.active!==false}));break;
   case 'tabs.update':if(!Number.isInteger(a.tabId))throw Error('Tab ID required');{const patch={};if(own(a,'url')){if(typeof a.url!=='string'||!/^https?:\/\//.test(a.url))throw Error('Explicit HTTP(S) URL required');patch.url=a.url;}if(own(a,'active'))patch.active=!!a.active;if(own(a,'muted'))patch.muted=!!a.muted;result=tabView(await chrome.tabs.update(a.tabId,patch));}break;
   case 'tabs.remove':if(!Number.isInteger(a.tabId))throw Error('Tab ID required');await chrome.tabs.remove(a.tabId);result=true;break;
   case 'cookies.getAll':result=await chrome.cookies.getAll(a);break;
   case 'cookies.set':result=await chrome.cookies.set(a);break;
   case 'cookies.remove':result=await chrome.cookies.remove(a);break;
   case 'downloads.search':result=await chrome.downloads.search(a);break;
   case 'downloads.cancel':if(!Number.isInteger(a.downloadId))throw Error('Download ID required');await chrome.downloads.cancel(a.downloadId);result=true;break;
   default:throw Error('Unknown command');
  }
  port.postMessage({v:1,id:message.id,kind:'response',ok:true,result});
 }catch(e){port.postMessage({v:1,id:message.id,kind:'response',ok:false,error:String(e&&e.message||e).slice(0,256)});}
}
function connect(){if(port)return;try{port=chrome.runtime.connectNative(HOST);port.onMessage.addListener(command);port.onDisconnect.addListener(()=>{const reason=chrome.runtime.lastError&&chrome.runtime.lastError.message;port=null;setTimeout(connect,1000);});send('hello',{extensionId:chrome.runtime.id,manifestVersion:3,version:chrome.runtime.getManifest().version,focusClosedRoot:!!(chrome.dom&&chrome.dom.openOrClosedShadowRoot)});chrome.tabs.query({}).then(t=>send('tabs',t.map(tabView)));}catch(e){port=null;setTimeout(connect,1000);}}
chrome.tabs.onCreated.addListener(t=>send('tabCreated',tabView(t)));
chrome.tabs.onUpdated.addListener((tabId,change,tab)=>send('tabUpdated',{tabId,change,tab:tabView(tab)}));
chrome.tabs.onActivated.addListener(data=>send('tabActivated',data));
chrome.tabs.onRemoved.addListener((tabId,info)=>send('tabRemoved',{tabId,info}));
chrome.cookies.onChanged.addListener(data=>send('cookieChanged',data));
chrome.downloads.onCreated.addListener(data=>send('downloadCreated',data));
chrome.downloads.onChanged.addListener(data=>send('downloadChanged',data));
chrome.runtime.onMessage.addListener((message,sender)=>{
 if(sender.id!==chrome.runtime.id||!sender.tab||!message||message.kind!=='focus')return;
 const m=message.data||{},data={tabId:sender.tab.id,frameId:sender.frameId,documentId:sender.documentId,url:sender.url,focused:!!m.focused,delegatesFocus:!!m.delegatesFocus,tag:String(m.tag||'').slice(0,32),type:String(m.type||'').slice(0,32),editable:!!m.editable,password:!!m.password,multiline:!!m.multiline,readOnly:!!m.readOnly,disabled:!!m.disabled,maxLength:Number.isInteger(m.maxLength)?m.maxLength:null,closedRoots:Number.isInteger(m.closedRoots)?m.closedRoots:0,closedRootAPI:!!m.closedRootAPI};
 send('focus',data);
});
connect();
