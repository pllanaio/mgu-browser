'use strict';
// SPDX-License-Identifier: MIT. Deliberately never reads value/textContent/PIN/PW.
let scheduled=false,last='';const observedRoots=new WeakSet();
function report(){scheduled=false;let element=document.activeElement,depth=0;const api=!!(chrome.dom&&chrome.dom.openOrClosedShadowRoot);
 for(let i=0;element&&i<16;i++){let root;try{root=api?chrome.dom.openOrClosedShadowRoot(element):element.shadowRoot;}catch(e){}if(root&&!observedRoots.has(root)){observedRoots.add(root);root.addEventListener('focusin',schedule,true);root.addEventListener('focusout',schedule,true);}if(!root||!root.activeElement)break;element=root.activeElement;if(root.mode==='closed')depth++;}
 const tag=element&&element.tagName||'',type=String(element&&element.type||'').toLowerCase(),textLike=tag==='TEXTAREA'||tag==='INPUT'&&!['button','submit','reset','checkbox','radio','file','image','range','color','hidden'].includes(type),data={focused:document.hasFocus(),tag,type,delegatesFocus:tag==='IFRAME'||tag==='FRAME',editable:!!(element&&(textLike||element.isContentEditable)),password:type==='password',multiline:tag==='TEXTAREA'||!!(element&&element.isContentEditable),readOnly:!!(element&&element.readOnly),disabled:!!(element&&element.disabled),maxLength:element&&Number.isInteger(element.maxLength)?element.maxLength:null,closedRoots:depth,closedRootAPI:api};
 const next=JSON.stringify(data);if(next===last)return;last=next;chrome.runtime.sendMessage({kind:'focus',data}).catch(()=>{});
}
function schedule(){if(!scheduled){scheduled=true;queueMicrotask(report);}}
document.addEventListener('focusin',schedule,true);document.addEventListener('focusout',schedule,true);window.addEventListener('focus',schedule,true);window.addEventListener('blur',schedule,true);document.addEventListener('DOMContentLoaded',schedule,{once:true});schedule();
