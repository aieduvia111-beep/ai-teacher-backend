/* Oznaczenie PRO przy tytulach funkcji (04.10.2026, user: "jak ktos ma premium musi czuc, ze jest
   premium i traktowany jak krol" - "Notatki PRO", "Quiz PRO" itd.). Maly, plaski znacznik obok tytulu
   strony (.page-h1 oraz naglowek mobilny .m-hdr-title) - bez swiecenia i gradientow. Plan czytamy z
   localStorage ('eduvia_plan', ustawiany przez strony po zalogowaniu - czesto dopiero po chwili, wiec
   sprawdzamy kilka razy). Darmowi uzytkownicy nic nie widza. */
(function () {
  var CSS =
    '.pro-chip{display:inline-block;margin-left:8px;padding:2px 7px;border-radius:6px;' +
    'background:#7c6aff!important;-webkit-background-clip:border-box!important;background-clip:border-box!important;' +
    'color:#fff!important;-webkit-text-fill-color:#fff!important;animation:none!important;' +
    'font-family:Inter,sans-serif;font-size:.36em;font-weight:800;letter-spacing:.08em;line-height:1.5;' +
    'vertical-align:middle;text-transform:uppercase;}' +
    '.m-hdr-title .pro-chip{font-size:.62em;margin-left:6px;}' +
    '.prog-meta .pro-chip{font-size:.7em;margin:0 0 0 8px;order:2;}';

  function isPro() {
    try { return (localStorage.getItem('eduvia_plan') || 'free') !== 'free'; } catch (e) { return false; }
  }

  function apply() {
    var pro = isPro();
    var targets = document.querySelectorAll('.page-h1, .m-hdr-title, .topbar .prog-meta');
    for (var i = 0; i < targets.length; i++) {
      var el = targets[i];
      var chip = el.querySelector('.pro-chip');
      if (pro && !chip) {
        var s = document.createElement('span');
        s.className = 'pro-chip';
        s.textContent = 'PRO';
        el.appendChild(s);
      } else if (!pro && chip) {
        chip.remove();
      }
    }
    return pro;
  }

  var st = document.createElement('style');
  st.textContent = CSS;
  document.head.appendChild(st);

  function start() {
    apply();
    var tries = 0;
    var iv = setInterval(function () {
      apply();
      if (++tries >= 12) clearInterval(iv);
    }, 700);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
