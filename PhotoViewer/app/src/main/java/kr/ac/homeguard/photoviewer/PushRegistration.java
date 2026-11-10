package kr.ac.homeguard.photoviewer;

import android.content.Context;
import android.content.SharedPreferences;
import org.json.JSONObject;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import com.google.firebase.messaging.FirebaseMessaging;

final class PushRegistration {
    private static final ExecutorService NETWORK = Executors.newSingleThreadExecutor();
    static SharedPreferences prefs(Context context) { return context.getSharedPreferences("homeguard", Context.MODE_PRIVATE); }

    static void newSession(Context context) {
        SharedPreferences p = prefs(context);
        if (!p.contains("installation_id")) p.edit().putString("installation_id", UUID.randomUUID().toString()).apply();
        p.edit().putString("push_binding", UUID.randomUUID().toString()).apply();
        register(context);
    }

    static void register(Context context) {
        SharedPreferences p = prefs(context);
        if (!BuildConfig.FCM_CONFIGURED || !p.getBoolean("push_enabled", false) || p.getString("token", "").isEmpty()) return;
        final String binding = p.getString("push_binding", "");
        if (binding.isEmpty()) return;
        FirebaseMessaging.getInstance().getToken().addOnCompleteListener(task -> {
            if (!task.isSuccessful()) { p.edit().putString("push_status", "알림 기기 토큰 발급 실패 · 다시 연결하세요.").apply(); return; }
            final String deviceToken = task.getResult();
            NETWORK.execute(() -> {
                if (!binding.equals(p.getString("push_binding", "")) || !p.getBoolean("push_enabled", false)) return;
                try {
                    JSONObject body = new JSONObject().put("token", deviceToken)
                            .put("installation_id", p.getString("installation_id", "")).put("binding_id", binding);
                    MainActivity.requestJson(p.getString("base", "") + "/api/push/devices/", "POST", body.toString(), p.getString("token", ""));
                    if (binding.equals(p.getString("push_binding", ""))) p.edit().putString("push_status", "알림 기기 연결 완료").apply();
                } catch (Exception error) { p.edit().putString("push_status", "알림 기기 등록 실패 · 다시 연결하세요.").apply(); }
            });
        });
    }

    static void unregister(Context context) {
        SharedPreferences p = prefs(context);
        final String base = p.getString("base", ""), token = p.getString("token", ""), id = p.getString("installation_id", "");
        p.edit().remove("push_binding").putString("push_status", "알림 연결 해제").apply();
        if (base.isEmpty() || token.isEmpty() || id.isEmpty()) return;
        NETWORK.execute(() -> {
            try { MainActivity.request(base + "/api/push/devices/" + id + "/", "DELETE", null, token); }
            catch (Exception ignored) { /* Stale messages are rejected locally by binding ID. */ }
        });
    }
}
