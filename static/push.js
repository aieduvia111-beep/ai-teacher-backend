const VAPID_KEY = 'BK5oMBm3JjcatbW05Yqi9S9FDXEjDwZnRxU4Hbm2qmF7JSLtaKCXvHZ3_-d1LsSDzXaRynr_OkTnWOMNWZNSWLw';

function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - base64String.length % 4) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const rawData = window.atob(base64);
  return new Uint8Array([...rawData].map(c => c.charCodeAt(0)));
}

async function initPush() {
  if (!('serviceWorker' in navigator) || !('PushManager' in window)) return;
  try {
    const reg = await navigator.serviceWorker.register('/sw.js');
    if (Notification.permission === 'granted') { await subscribePush(reg); return; }
    if (Notification.permission === 'default') { showPushPrompt(reg); }
  } catch(e) {}
}

function showPushPrompt(reg) {
  const prompt = document.createElement('div');
  prompt.style.cssText = 'position:fixed;bottom:80px;left:16px;right:16px;background:linear-gradient(135deg,#0f0f18,#161622);border:1px solid rgba(124,106,255,.3);border-radius:20px;padding:20px;z-index:9999;box-shadow:0 20px 60px rgba(0,0,0,.5);';
  prompt.innerHTML = '<div style="display:flex;align-items:center;gap:12px;margin-bottom:14px;"><div style="width:44px;height:44px;border-radius:12px;background:rgba(124,106,255,.15);border:1px solid rgba(124,106,255,.3);display:flex;align-items:center;justify-content:center;font-size:1.3em;flex-shrink:0;">🔔</div><div><div style="font-family:Syne,sans-serif;font-weight:800;font-size:.95em;color:white;margin-bottom:3px;">Włącz przypomnienia</div><div style="font-size:.78em;color:#8888a0;line-height:1.4;">Otrzymuj codzienne powiadomienia o nauce!</div></div></div><div style="display:flex;gap:10px;"><button id="pushYes" style="flex:1;padding:12px;background:linear-gradient(135deg,#7c6aff,#5040c8);border:none;border-radius:12px;color:white;font-family:Syne,sans-serif;font-size:.85em;font-weight:700;cursor:pointer;">🔔 Włącz</button><button id="pushNo" style="flex:1;padding:12px;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.1);border-radius:12px;color:#8888a0;font-family:Syne,sans-serif;font-size:.85em;cursor:pointer;">Nie teraz</button></div>';
  document.body.appendChild(prompt);
  document.getElementById('pushYes').onclick = async () => {
    prompt.remove();
    const permission = await Notification.requestPermission();
    if (permission === 'granted') await subscribePush(reg);
  };
  document.getElementById('pushNo').onclick = () => prompt.remove();
}

async function subscribePush(reg) {
  try {
    const sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(VAPID_KEY)
    });
    await fetch('https://ai-teacher-backend-1.onrender.com/api/push/subscribe', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ subscription: sub, uid: localStorage.getItem('eduvia_uid') })
    }).catch(() => {});
  } catch(e) {}
}

window.addEventListener('load', initPush);
