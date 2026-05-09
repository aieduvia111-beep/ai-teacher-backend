(function(){

// ═══ PAGE TRANSITIONS ═══
var style=document.createElement('style');
style.textContent=`
  body{animation:pageIn .3s cubic-bezier(.22,1,.36,1) forwards;}
  @keyframes pageIn{
    from{opacity:0;transform:translateX(18px);}
    to{opacity:1;transform:translateX(0);}
  }
  .page-out{animation:pageOut .22s cubic-bezier(.4,0,1,1) forwards!important;pointer-events:none!important;}
  @keyframes pageOut{
    from{opacity:1;transform:translateX(0);}
    to{opacity:0;transform:translateX(-18px);}
  }

  /* TOAST */
  .edu-toast{position:fixed;bottom:80px;left:50%;transform:translateX(-50%) translateY(20px);background:rgba(20,20,32,.97);border:1px solid rgba(255,255,255,.1);border-radius:100px;padding:12px 22px;color:#eeeef5;font-family:'DM Sans',sans-serif;font-size:.84em;font-weight:500;z-index:99999;opacity:0;transition:all .3s cubic-bezier(.34,1.56,.64,1);white-space:nowrap;backdrop-filter:blur(20px);box-shadow:0 8px 32px rgba(0,0,0,.4);display:flex;align-items:center;gap:8px;pointer-events:none;}
  .edu-toast.show{opacity:1;transform:translateX(-50%) translateY(0);}
  .edu-toast.success{border-color:rgba(34,211,160,.3);box-shadow:0 8px 32px rgba(34,211,160,.15);}
  .edu-toast.error{border-color:rgba(248,113,113,.3);box-shadow:0 8px 32px rgba(248,113,113,.15);}
  .edu-toast.info{border-color:rgba(124,106,255,.3);box-shadow:0 8px 32px rgba(124,106,255,.15);}

  /* OFFLINE SCREEN */
  .edu-offline{position:fixed;inset:0;z-index:99998;background:#06060f;display:none;flex-direction:column;align-items:center;justify-content:center;gap:16px;text-align:center;padding:32px;}
  .edu-offline.show{display:flex;}
  .edu-offline-icon{width:72px;height:72px;border-radius:50%;background:rgba(248,113,113,.1);border:1px solid rgba(248,113,113,.2);display:flex;align-items:center;justify-content:center;margin-bottom:8px;animation:pulse 2s ease-in-out infinite;}
  @keyframes pulse{0%,100%{box-shadow:0 0 0 0 rgba(248,113,113,.2);}50%{box-shadow:0 0 0 12px rgba(248,113,113,0);}}
  .edu-offline-title{font-family:'Syne',sans-serif;font-size:1.4em;font-weight:800;color:#eeeef5;}
  .edu-offline-sub{font-size:.84em;color:#6e6e88;line-height:1.6;max-width:280px;}
  .edu-offline-btn{margin-top:8px;padding:13px 28px;background:linear-gradient(135deg,#7c6aff,#5040c8);border:none;border-radius:100px;color:white;font-family:'Syne',sans-serif;font-size:.88em;font-weight:700;cursor:pointer;transition:all .2s;}
  .edu-offline-btn:active{transform:scale(.96);}

  /* SKELETON */
  .skeleton{background:linear-gradient(90deg,rgba(255,255,255,.04) 25%,rgba(255,255,255,.08) 50%,rgba(255,255,255,.04) 75%);background-size:200% 100%;animation:shimmer 1.5s infinite;}
  @keyframes shimmer{0%{background-position:200% 0;}100%{background-position:-200% 0;}}

  /* RIPPLE na przyciskach */
  button{position:relative;overflow:hidden;}
  .ripple{position:absolute;border-radius:50%;background:rgba(255,255,255,.15);transform:scale(0);animation:rippleAnim .5s linear;pointer-events:none;}
  @keyframes rippleAnim{to{transform:scale(4);opacity:0;}}
`;
document.head.appendChild(style);

// ═══ PAGE TRANSITIONS ═══
document.addEventListener('click',function(e){
  var el=e.target.closest('a[href]');
  if(!el)return;
  var href=el.getAttribute('href');
  if(href&&(href.endsWith('.html')||href.includes('.html?'))){
    e.preventDefault();
    document.body.classList.add('page-out');
    setTimeout(function(){window.location.href=href;},220);
  }
},true);

// ═══ TOAST SYSTEM ═══
var toastEl=null,toastTimer=null;
window.showToast=function(msg,type,duration){
  if(!toastEl){
    toastEl=document.createElement('div');
    toastEl.className='edu-toast';
    document.body.appendChild(toastEl);
  }
  if(toastTimer)clearTimeout(toastTimer);
  toastEl.className='edu-toast '+(type||'info');
  var icon=type==='success'?'✓':type==='error'?'✕':'ℹ';
  toastEl.innerHTML='<span>'+icon+'</span><span>'+msg+'</span>';
  requestAnimationFrame(function(){toastEl.classList.add('show');});
  toastTimer=setTimeout(function(){
    toastEl.classList.remove('show');
  },duration||2800);
};

// ═══ OFFLINE DETECTION ═══
var offlineEl=document.createElement('div');
offlineEl.className='edu-offline';
offlineEl.innerHTML='<div class="edu-offline-icon"><svg viewBox="0 0 24 24" fill="none" stroke="#f87171" stroke-width="1.8" width="32" height="32"><line x1="1" y1="1" x2="23" y2="23"/><path d="M16.72 11.06A10.94 10.94 0 0 1 19 12.55"/><path d="M5 12.55a10.94 10.94 0 0 1 5.17-2.39"/><path d="M10.71 5.05A16 16 0 0 1 22.56 9"/><path d="M1.42 9a15.91 15.91 0 0 1 4.7-2.88"/><path d="M8.53 16.11a6 6 0 0 1 6.95 0"/><line x1="12" y1="20" x2="12.01" y2="20"/></svg></div><div class="edu-offline-title">Brak połączenia</div><div class="edu-offline-sub">Sprawdź połączenie z internetem i spróbuj ponownie.</div><button class="edu-offline-btn" onclick="location.reload()">Spróbuj ponownie</button>';
document.body.appendChild(offlineEl);

window.addEventListener('offline',function(){offlineEl.classList.add('show');});
window.addEventListener('online',function(){offlineEl.classList.remove('show');showToast('Połączono z internetem','success');});
if(!navigator.onLine)offlineEl.classList.add('show');

// ═══ RIPPLE EFFECT ═══
document.addEventListener('click',function(e){
  var btn=e.target.closest('button');
  if(!btn||btn.classList.contains('no-ripple'))return;
  var r=document.createElement('span');
  r.className='ripple';
  var rect=btn.getBoundingClientRect();
  var size=Math.max(rect.width,rect.height);
  r.style.cssText='width:'+size+'px;height:'+size+'px;left:'+(e.clientX-rect.left-size/2)+'px;top:'+(e.clientY-rect.top-size/2)+'px;';
  btn.appendChild(r);
  setTimeout(function(){r.remove();},500);
});

// ═══ HAPTIC ═══
if(window.Capacitor&&window.Capacitor.Plugins&&window.Capacitor.Plugins.Haptics){
  window._haptic=function(t){
    var H=window.Capacitor.Plugins.Haptics;
    if(t==='ok')H.impact({style:'light'});
    else if(t==='err')H.notification({type:'error'});
    else H.impact({style:'medium'});
  };
}else{window._haptic=function(){};}

})();
