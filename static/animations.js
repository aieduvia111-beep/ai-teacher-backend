(function(){
var s=document.createElement('style');
s.textContent='.ripple-wave{position:absolute;border-radius:50%;background:rgba(255,255,255,.25);transform:scale(0);animation:rA .6s linear;pointer-events:none;}@keyframes rA{to{transform:scale(4);opacity:0;}}.card,.tool-card,.feat-card,.stat-card,.quick-card,.review-card{transition:transform .2s cubic-bezier(.34,1.56,.64,1),box-shadow .2s ease!important;}.card:active,.tool-card:active,.feat-card:active,.stat-card:active,.quick-card:active,.review-card:active{transform:translateY(-3px) scale(1.01)!important;box-shadow:0 12px 32px rgba(124,106,255,.15)!important;}@keyframes xpFloat{0%{opacity:1;transform:translateY(0);}100%{opacity:0;transform:translateY(-30px);}}.xp-float-pop{position:fixed;font-family:"Syne",sans-serif;font-weight:800;font-size:.9em;color:#22d3a0;pointer-events:none;z-index:9999;animation:xpFloat .9s ease forwards;}';
document.head.appendChild(s);
document.addEventListener('click',function(e){
  var btn=e.target.closest('button');
  if(!btn)return;
  var r=document.createElement('span');
  r.classList.add('ripple-wave');
  var rect=btn.getBoundingClientRect();
  var size=Math.max(rect.width,rect.height);
  r.style.cssText='width:'+size+'px;height:'+size+'px;left:'+(e.clientX-rect.left-size/2)+'px;top:'+(e.clientY-rect.top-size/2)+'px;';
  btn.style.position='relative';
  btn.style.overflow='hidden';
  btn.appendChild(r);
  setTimeout(function(){r.remove();},600);
});
window._showXPPop=function(xp,x,y){
  var el=document.createElement('div');
  el.className='xp-float-pop';
  el.textContent='+'+xp+' XP';
  el.style.left=(x||window.innerWidth/2)+'px';
  el.style.top=(y||window.innerHeight/2)+'px';
  document.body.appendChild(el);
  setTimeout(function(){el.remove();},900);
};
})();
