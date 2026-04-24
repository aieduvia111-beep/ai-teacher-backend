(function(){
  var style=document.createElement('style');
  style.textContent='body{animation:pageIn .25s ease forwards;}@keyframes pageIn{from{opacity:0;transform:translateY(12px);}to{opacity:1;transform:translateY(0);}}.page-out{animation:pageOut .2s ease forwards!important;pointer-events:none;}@keyframes pageOut{from{opacity:1;transform:translateY(0);}to{opacity:0;transform:translateY(-8px);}}';
  document.head.appendChild(style);
  document.addEventListener('click',function(e){
    var el=e.target.closest('a[href]');
    if(!el)return;
    var href=el.getAttribute('href');
    if(href&&(href.endsWith('.html')||href.includes('.html?'))){
      e.preventDefault();
      document.body.classList.add('page-out');
      setTimeout(function(){window.location.href=href;},200);
    }
  },true);
})();
