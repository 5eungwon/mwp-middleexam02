package kr.ac.homeguard.photoviewer;

import android.app.Application;
import com.google.firebase.FirebaseApp;
import com.google.firebase.FirebaseOptions;

public class HomeGuardApplication extends Application {
    @Override public void onCreate() {
        super.onCreate();
        if (BuildConfig.FCM_CONFIGURED && FirebaseApp.getApps(this).isEmpty()) {
            FirebaseOptions options = new FirebaseOptions.Builder()
                    .setProjectId(BuildConfig.FCM_PROJECT).setGcmSenderId(BuildConfig.FCM_SENDER)
                    .setApplicationId(BuildConfig.FCM_APP).setApiKey(BuildConfig.FCM_API_KEY).build();
            FirebaseApp.initializeApp(this, options);
        }
        DetectionMessagingService.createChannel(this);
    }
}
