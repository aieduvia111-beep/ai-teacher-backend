importScripts('https://www.gstatic.com/firebasejs/10.7.1/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/10.7.1/firebase-messaging-compat.js');

firebase.initializeApp({
  apiKey: "AIzaSyBq9RSMSRWnVEkvMvIqtU4ZNemZhmJUiOU",
  authDomain: "eduvia-c69bc.firebaseapp.com",
  projectId: "eduvia-c69bc",
  storageBucket: "eduvia-c69bc.firebasestorage.app",
  messagingSenderId: "613529563678",
  appId: "1:613529563678:web:5028a3edfbd68969d4340f"
});

const messaging = firebase.messaging();

messaging.onBackgroundMessage(payload => {
  const {title, body, icon} = payload.notification || {};
  self.registration.showNotification(title || 'Eduvia AI', {
    body: body || 'Masz nową wiadomość!',
    icon: icon || '/static/icon-192.png',
    badge: '/static/icon-192.png',
    vibrate: [200, 100, 200],
    data: payload.data
  });
});

self.addEventListener('notificationclick', e => {
  e.notification.close();
  e.waitUntil(clients.openWindow('https://ai-teacher-backend-inky.vercel.app/dashboard_FINAL.html'));
});
