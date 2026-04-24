(function(){
var s1=document.createElement('style');
s1.textContent='.ripple-wave{position:absolute;border-radius:50%;background:rgba(255,255,255,.25);transform:scale(0);animation:rA .6s linear;pointer-events:none;}@keyframes rA{to{transform:scale(4);opacity:0;}}';
document.head.appendChild(s1);
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
})();
