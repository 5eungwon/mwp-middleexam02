package kr.ac.homeguard.photoviewer;

import android.Manifest;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import com.google.firebase.messaging.FirebaseMessagingService;
import com.google.firebase.messaging.RemoteMessage;
import java.util.Map;

public class DetectionMessagingService extends FirebaseMessagingService {
    private static final String CHANNEL = "homeguard_detection";
    static void createChannel(Context context) {
        NotificationManager manager = context.getSystemService(NotificationManager.class);
        manager.createNotificationChannel(new NotificationChannel(CHANNEL, "새 감지 알림", NotificationManager.IMPORTANCE_HIGH));
    }
    @Override public void onNewToken(String token) { PushRegistration.register(this); }
    @Override public void onMessageReceived(RemoteMessage message) {
        Map<String, String> data = message.getData();
        SharedPreferences p = PushRegistration.prefs(this);
        String binding = p.getString("push_binding", "");
        if (binding.isEmpty() || !binding.equals(data.get("binding_id")) || p.getString("token", "").isEmpty()
                || !p.getBoolean("push_enabled", false)) return;
        if (android.os.Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) return;
        int id;
        try { id = Integer.parseInt(data.get("post_id")); if (id <= 0) return; }
        catch (Exception invalid) { return; }
        Intent intent = new Intent(this, MainActivity.class).putExtra("notification_post_id", id).putExtra("notification_binding", binding)
                .addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        PendingIntent pending = PendingIntent.getActivity(this, id, intent, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        createChannel(this);
        Notification notification = new Notification.Builder(this, CHANNEL).setSmallIcon(R.drawable.ic_guard)
                .setContentTitle(data.getOrDefault("title", "새 감지 기록"))
                .setContentText(data.getOrDefault("body", "새 감지 사진이 등록되었습니다."))
                .setContentIntent(pending).setAutoCancel(true).setCategory(Notification.CATEGORY_ALARM).build();
        getSystemService(NotificationManager.class).notify(id, notification);
    }
}
