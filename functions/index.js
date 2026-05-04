const {onSchedule} = require("firebase-functions/v2/scheduler");
const {initializeApp} = require("firebase-admin/app");
const {getFirestore} = require("firebase-admin/firestore");
const {getMessaging} = require("firebase-admin/messaging");

initializeApp();

// Codziennie o 18:00 wysyła przypomnienie
exports.dailyReminder = onSchedule("0 18 * * *", async () => {
  const db = getFirestore();
  const snap = await db.collection("users").get();
  
  const messages = [];
  snap.forEach(doc => {
    const user = doc.data();
    if(user.fcmToken) {
      const streak = user.streak || 0;
      let title = "Eduvia AI 📚";
      let body = "Nie zapomnij o dzisiejszej nauce!";
      
      if(streak > 0) {
        body = `Masz streak ${streak} dni! Nie przerywaj passy 🔥`;
      }
      
      messages.push({
        token: user.fcmToken,
        notification: {title, body},
        android: {
          notification: {
            icon: "ic_launcher",
            color: "#7c6aff"
          }
        }
      });
    }
  });

  if(messages.length > 0) {
    await getMessaging().sendEach(messages);
    console.log(`Wysłano ${messages.length} powiadomień`);
  }
});
