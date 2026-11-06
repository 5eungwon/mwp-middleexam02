package kr.ac.homeguard.photoviewer;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.SharedPreferences;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.text.InputType;
import android.util.LruCache;
import android.view.Gravity;
import android.view.View;
import android.view.WindowInsets;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URI;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Native photo client. Networking always runs outside the main thread. */
public class MainActivity extends Activity {
    private static final int BG = Color.rgb(244, 246, 248);
    private static final int INK = Color.rgb(20, 33, 61);
    private static final int MUTED = Color.rgb(104, 116, 135);
    private static final int GREEN = Color.rgb(37, 135, 95);
    private static final int WHITE = Color.WHITE;
    private final ExecutorService workers = Executors.newFixedThreadPool(4);
    private final LruCache<String, Bitmap> images = new LruCache<String, Bitmap>(12 * 1024 * 1024) {
        @Override protected int sizeOf(String key, Bitmap value) { return value.getByteCount(); }
    };
    private SharedPreferences prefs;
    private String base, token, username, search = "";
    private boolean unreadOnly;
    private int currentDetail = -1, generation;
    private LinearLayout root, content;
    private TextView status;
    private EditText searchInput;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        prefs = getSharedPreferences("homeguard", MODE_PRIVATE);
        base = prefs.getString("base", "http://10.0.2.2:8000");
        token = prefs.getString("token", "");
        username = prefs.getString("username", "");
        if (android.os.Build.VERSION.SDK_INT >= 33) {
            getOnBackInvokedDispatcher().registerOnBackInvokedCallback(
                    android.window.OnBackInvokedDispatcher.PRIORITY_DEFAULT,
                    () -> { if (currentDetail > 0) showFeed(); else finish(); });
        }
        if (state != null) {
            search = state.getString("search", "");
            unreadOnly = state.getBoolean("unread");
            currentDetail = state.getInt("detail", -1);
        }
        if (token.isEmpty()) showLogin();
        else if (currentDetail > 0) showDetail(currentDetail);
        else showFeed();
    }

    @Override public void onSaveInstanceState(Bundle state) {
        state.putString("search", searchInput == null ? search : searchInput.getText().toString());
        state.putBoolean("unread", unreadOnly);
        state.putInt("detail", currentDetail);
        super.onSaveInstanceState(state);
    }

    @Override protected void onDestroy() {
        generation++;
        workers.shutdownNow();
        super.onDestroy();
    }

    // API 33+ uses the native OnBackInvokedCallback registered in onCreate.
    // This fallback is needed only on API 27–32.
    @android.annotation.SuppressLint("GestureBackNavigation")
    @Override public void onBackPressed() {
        if (currentDetail > 0) showFeed();
        else super.onBackPressed();
    }

    private int dp(float n) { return Math.round(n * getResources().getDisplayMetrics().density); }
    private GradientDrawable shape(int color, int radius) {
        GradientDrawable result = new GradientDrawable();
        result.setColor(color);
        result.setCornerRadius(dp(radius));
        return result;
    }
    private LinearLayout column() {
        LinearLayout view = new LinearLayout(this);
        view.setOrientation(LinearLayout.VERTICAL);
        return view;
    }
    private LinearLayout row() {
        LinearLayout view = new LinearLayout(this);
        view.setOrientation(LinearLayout.HORIZONTAL);
        view.setGravity(Gravity.CENTER_VERTICAL);
        return view;
    }
    private TextView text(String value, int size, int color, boolean bold) {
        TextView view = new TextView(this);
        view.setText(value);
        view.setTextSize(size);
        view.setTextColor(color);
        view.setIncludeFontPadding(false);
        if (bold) view.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        return view;
    }
    private void gap(LinearLayout parent, int height) {
        View view = new View(this);
        parent.addView(view, new LinearLayout.LayoutParams(1, dp(height)));
    }
    private Button button(String label, boolean primary) {
        Button button = new Button(this);
        button.setText(label);
        button.setTextSize(14);
        button.setAllCaps(false);
        button.setTextColor(primary ? WHITE : INK);
        button.setBackground(shape(primary ? INK : Color.rgb(229, 234, 239), 12));
        button.setMinHeight(dp(48));
        button.setMinimumHeight(dp(48));
        button.setPadding(dp(14), dp(8), dp(14), dp(8));
        return button;
    }
    private EditText input(String hint, int type) {
        EditText field = new EditText(this);
        field.setHint(hint);
        field.setContentDescription(hint);
        field.setTextSize(15);
        field.setTextColor(INK);
        field.setSingleLine(true);
        field.setInputType(type);
        field.setPadding(dp(16), dp(14), dp(16), dp(14));
        GradientDrawable background = shape(WHITE, 12);
        background.setStroke(dp(1), Color.rgb(218, 224, 232));
        field.setBackground(background);
        field.setLayoutParams(new LinearLayout.LayoutParams(-1, dp(52)));
        return field;
    }

    private void shell(String subtitle) {
        generation++;
        searchInput = null;
        root = column();
        root.setBackgroundColor(BG);
        root.setOnApplyWindowInsetsListener((view, insets) -> {
            int top, bottom;
            if (android.os.Build.VERSION.SDK_INT >= 30) {
                android.graphics.Insets bars = insets.getInsets(WindowInsets.Type.systemBars());
                top = bars.top; bottom = bars.bottom;
            } else { top = insets.getSystemWindowInsetTop(); bottom = insets.getSystemWindowInsetBottom(); }
            view.setPadding(0, top, 0, bottom);
            return insets;
        });
        setContentView(root);
        root.requestApplyInsets();
        LinearLayout header = row();
        header.setPadding(dp(22), dp(20), dp(18), dp(18));
        TextView emblem = text("⌂", 28, WHITE, true);
        emblem.setGravity(Gravity.CENTER);
        emblem.setBackground(shape(INK, 14));
        header.addView(emblem, new LinearLayout.LayoutParams(dp(46), dp(46)));
        LinearLayout title = column();
        title.setPadding(dp(12), 0, 0, 0);
        title.addView(text("우리집 지킴이", 21, INK, true));
        gap(title, 5);
        title.addView(text(subtitle, 11, MUTED, false));
        header.addView(title, new LinearLayout.LayoutParams(0, -2, 1));
        if (!token.isEmpty()) {
            Button logout = button("로그아웃", false);
            logout.setTextSize(11);
            logout.setPadding(dp(8), dp(6), dp(8), dp(6));
            logout.setOnClickListener(v -> new AlertDialog.Builder(this).setMessage("로그아웃할까요?")
                    .setNegativeButton("취소", null).setPositiveButton("로그아웃", (d, w) -> logout()).show());
            header.addView(logout, new LinearLayout.LayoutParams(dp(76), dp(42)));
        }
        root.addView(header);
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        content = column();
        content.setPadding(dp(22), dp(6), dp(22), dp(24));
        scroll.addView(content);
        root.addView(scroll, new LinearLayout.LayoutParams(-1, 0, 1));
    }

    private void showLogin() {
        currentDetail = -1;
        shell("HOME GUARD · PHOTO VIEWER");
        gap(content, 28);
        TextView eyebrow = text("내 공간을 더 안심하게", 13, GREEN, true);
        content.addView(eyebrow);
        gap(content, 14);
        content.addView(text("어디에서나,\n우리집을 확인하세요.", 29, INK, true));
        gap(content, 15);
        content.addView(text("카메라가 포착한 순간을 사진으로 확인하고\n새로운 감지 기록을 빠르게 살펴보세요.", 14, MUTED, false));
        gap(content, 32);
        content.addView(text("서버에 연결", 18, INK, true));
        gap(content, 15);
        content.addView(text("서버 주소", 12, MUTED, true));
        gap(content, 7);
        EditText server = input("서버 주소", InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        server.setText(base);
        content.addView(server);
        gap(content, 15);
        EditText user = input("아이디", InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS);
        user.setText(username);
        content.addView(user);
        gap(content, 11);
        EditText password = input("비밀번호", InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        password.setImportantForAutofill(View.IMPORTANT_FOR_AUTOFILL_YES);
        content.addView(password);
        gap(content, 18);
        Button login = button("로그인", true);
        content.addView(login, new LinearLayout.LayoutParams(-1, dp(54)));
        gap(content, 12);
        status = text("PythonAnywhere 서버는 https:// 주소를 입력하세요.\n에뮬레이터의 로컬 서버: http://10.0.2.2:8000", 11, MUTED, false);
        content.addView(status);
        final int viewGeneration = generation;
        login.setOnClickListener(v -> {
            final String host = server.getText().toString().trim().replaceAll("/+$", "");
            final String name = user.getText().toString().trim();
            final String secret = password.getText().toString();
            try {
                URI uri = URI.create(host);
                if (!("https".equals(uri.getScheme()) || "http".equals(uri.getScheme())) || uri.getHost() == null
                        || uri.getUserInfo() != null || uri.getQuery() != null || uri.getFragment() != null
                        || !(uri.getPath() == null || uri.getPath().isEmpty())) throw new IllegalArgumentException();
            } catch (Exception e) { status.setText(R.string.invalid_server); return; }
            if (name.isEmpty() || secret.isEmpty()) { status.setText("아이디와 비밀번호를 입력하세요."); return; }
            login.setEnabled(false);
            status.setText("서버에 연결하고 있습니다…");
            workers.execute(() -> {
                try {
                    String form = "username=" + encode(name) + "&password=" + encode(secret);
                    JSONObject response = new JSONObject(request(host + "/api-token-auth/", "POST", form, ""));
                    String newToken = response.getString("token");
                    runOnUiThread(() -> {
                        if (generation != viewGeneration || isFinishing()) return;
                        base = host; token = newToken; username = response.optString("username", name);
                        prefs.edit().putString("base", base).putString("token", token).putString("username", username).apply();
                        password.setText(""); showFeed();
                    });
                } catch (Exception e) {
                    runOnUiThread(() -> { if (generation == viewGeneration) { login.setEnabled(true); status.setText(message(e)); } });
                }
            });
        });
    }

    private void showFeed() {
        currentDetail = -1;
        shell(username + "님의 감지 기록");
        LinearLayout heading = row();
        heading.addView(text("감지 기록", 27, INK, true), new LinearLayout.LayoutParams(0, -2, 1));
        TextView live = text("PHOTO VIEWER", 10, MUTED, true);
        heading.addView(live);
        content.addView(heading);
        gap(content, 10);
        content.addView(text("카메라가 발견한 새로운 순간들", 13, MUTED, false));
        gap(content, 22);
        LinearLayout filters = row();
        searchInput = input("객체 또는 내용 검색", InputType.TYPE_CLASS_TEXT);
        searchInput.setText(search);
        filters.addView(searchInput, new LinearLayout.LayoutParams(0, dp(50), 1));
        Button find = button("검색", true);
        LinearLayout.LayoutParams findParams = new LinearLayout.LayoutParams(dp(68), dp(50));
        findParams.setMarginStart(dp(8));
        filters.addView(find, findParams);
        content.addView(filters);
        gap(content, 12);
        LinearLayout actions = row();
        Button all = button("전체", !unreadOnly);
        Button unread = button("미확인", unreadOnly);
        Button refresh = button("새로고침", false);
        actions.addView(all, new LinearLayout.LayoutParams(0, dp(44), 1));
        LinearLayout.LayoutParams actionParams = new LinearLayout.LayoutParams(0, dp(44), 1);
        actionParams.setMarginStart(dp(8));
        actions.addView(unread, actionParams);
        LinearLayout.LayoutParams refreshParams = new LinearLayout.LayoutParams(0, dp(44), 1);
        refreshParams.setMarginStart(dp(8));
        actions.addView(refresh, refreshParams);
        content.addView(actions);
        gap(content, 18);
        status = text("감지 기록을 불러오고 있습니다…", 12, MUTED, false);
        content.addView(status);
        gap(content, 14);
        LinearLayout list = column();
        content.addView(list);
        find.setOnClickListener(v -> { search = searchInput.getText().toString().trim(); loadPosts(list); });
        searchInput.setOnEditorActionListener((v, actionId, event) -> {
            if (actionId == android.view.inputmethod.EditorInfo.IME_ACTION_DONE || actionId == android.view.inputmethod.EditorInfo.IME_ACTION_SEARCH) {
                search = searchInput.getText().toString().trim(); loadPosts(list); return true;
            }
            return false;
        });
        all.setOnClickListener(v -> { search = searchInput.getText().toString().trim(); unreadOnly = false; showFeed(); });
        unread.setOnClickListener(v -> { search = searchInput.getText().toString().trim(); unreadOnly = true; showFeed(); });
        refresh.setOnClickListener(v -> loadPosts(list));
        loadPosts(list);
    }

    private void loadPosts(LinearLayout list) {
        final int requestGeneration = ++generation;
        status.setText("감지 기록을 불러오고 있습니다…");
        list.removeAllViews();
        final String path = base + "/api_root/Post/?search=" + encode(search) + (unreadOnly ? "&unread=1" : "");
        workers.execute(() -> {
            try {
                JSONArray posts = new JSONArray(request(path, "GET", null, token));
                runOnUiThread(() -> {
                    if (generation != requestGeneration || isFinishing()) return;
                    status.setText(getString(R.string.record_count, posts.length(), unreadOnly ? "미확인" : "최신순"));
                    if (posts.length() == 0) {
                        LinearLayout empty = card();
                        empty.addView(text("아직 감지 기록이 없습니다", 18, INK, true));
                        gap(empty, 10);
                        empty.addView(text("검색 조건을 바꾸거나 카메라에서\n새 객체가 감지된 후 새로고침하세요.", 13, MUTED, false));
                        list.addView(empty);
                    }
                    for (int i = 0; i < posts.length(); i++) addPostCard(list, posts.optJSONObject(i), requestGeneration);
                });
            } catch (Exception e) { showFailure(e, requestGeneration); }
        });
    }

    private LinearLayout card() {
        LinearLayout card = column();
        card.setPadding(dp(18), dp(18), dp(18), dp(18));
        card.setBackground(shape(WHITE, 20));
        card.setElevation(dp(1));
        return card;
    }

    private void addPostCard(LinearLayout list, JSONObject post, int requestGeneration) {
        if (post == null) return;
        LinearLayout card = card();
        boolean acknowledged = post.optBoolean("acknowledged");
        LinearLayout meta = row();
        TextView chip = text(acknowledged ? "확인 완료" : "새로운 감지", 11, acknowledged ? MUTED : GREEN, true);
        chip.setPadding(dp(10), dp(6), dp(10), dp(6));
        chip.setBackground(shape(acknowledged ? BG : Color.rgb(229, 245, 236), 8));
        meta.addView(chip, new LinearLayout.LayoutParams(0, -2, 1));
        TextView date = text(date(post.optString("created_date")), 10, MUTED, false);
        date.setPadding(dp(10), 0, 0, 0);
        meta.addView(date);
        card.addView(meta);
        gap(card, 14);
        ImageView image = new ImageView(this);
        image.setBackground(shape(BG, 12));
        image.setScaleType(ImageView.ScaleType.CENTER_CROP);
        image.setContentDescription("감지 사진: " + post.optString("title"));
        card.addView(image, new LinearLayout.LayoutParams(-1, dp(180)));
        loadImage(post.optString("image"), image, requestGeneration);
        gap(card, 15);
        card.addView(text(post.optString("title", "감지 기록"), 20, INK, true));
        gap(card, 8);
        TextView preview = text(post.optString("text"), 13, MUTED, false);
        preview.setMaxLines(2);
        card.addView(preview);
        gap(card, 15);
        card.addView(text("사진 자세히 보기  →", 12, GREEN, true));
        card.setClickable(true);
        card.setFocusable(true);
        card.setContentDescription(post.optString("title") + ", " + (acknowledged ? "확인 완료" : "미확인") + ", 상세 보기");
        card.setOnClickListener(v -> { search = searchInput.getText().toString().trim(); showDetail(post.optInt("id")); });
        list.addView(card, new LinearLayout.LayoutParams(-1, -2));
        gap(list, 16);
    }

    private void showDetail(int id) {
        currentDetail = id;
        shell("감지 사진 상세");
        Button back = button("← 감지 기록", false);
        content.addView(back, new LinearLayout.LayoutParams(dp(132), dp(44)));
        back.setOnClickListener(v -> showFeed());
        gap(content, 22);
        status = text("사진 정보를 불러오고 있습니다…", 13, MUTED, false);
        content.addView(status);
        final int requestGeneration = generation;
        workers.execute(() -> {
            try {
                JSONObject post = new JSONObject(request(base + "/api_root/Post/" + id + "/", "GET", null, token));
                runOnUiThread(() -> {
                    if (generation != requestGeneration || isFinishing()) return;
                    status.setText(date(post.optString("created_date")));
                    gap(content, 14);
                    content.addView(text(post.optString("title", "감지 기록"), 29, INK, true));
                    gap(content, 18);
                    ImageView image = new ImageView(this);
                    image.setScaleType(ImageView.ScaleType.FIT_CENTER);
                    image.setAdjustViewBounds(true);
                    image.setMinimumHeight(dp(240));
                    image.setBackground(shape(WHITE, 18));
                    image.setContentDescription("감지 사진: " + post.optString("title"));
                    content.addView(image, new LinearLayout.LayoutParams(-1, -2));
                    loadImage(post.optString("image"), image, requestGeneration);
                    gap(content, 20);
                    LinearLayout description = card();
                    description.addView(text("감지 내용", 13, GREEN, true));
                    gap(description, 12);
                    description.addView(text(post.optString("text"), 16, INK, false));
                    gap(description, 16);
                    description.addView(text("등록: " + post.optString("author", username), 12, MUTED, false));
                    content.addView(description);
                    gap(content, 20);
                    Button acknowledge = button(post.optBoolean("acknowledged") ? "✓ 확인 완료" : "이 기록 확인 완료로 표시", !post.optBoolean("acknowledged"));
                    acknowledge.setEnabled(!post.optBoolean("acknowledged"));
                    content.addView(acknowledge, new LinearLayout.LayoutParams(-1, dp(54)));
                    acknowledge.setOnClickListener(v -> {
                        acknowledge.setEnabled(false);
                        workers.execute(() -> {
                            try {
                                request(base + "/api_root/Post/" + id + "/acknowledge/", "POST", "", token);
                                runOnUiThread(() -> {
                                    if (generation == requestGeneration) {
                                        acknowledge.setText("✓ 확인 완료");
                                        Toast.makeText(this, "확인 상태가 저장되었습니다.", Toast.LENGTH_SHORT).show();
                                    }
                                });
                            } catch (Exception e) {
                                runOnUiThread(() -> { if (generation == requestGeneration) acknowledge.setEnabled(true); });
                                showFailure(e, requestGeneration);
                            }
                        });
                    });
                });
            } catch (Exception e) { showFailure(e, requestGeneration); }
        });
    }

    private void loadImage(String source, ImageView view, int requestGeneration) {
        if (source.isEmpty()) return;
        String absolute = source.startsWith("/") ? base + source : source;
        Bitmap cached = images.get(absolute);
        if (cached != null) { view.setImageBitmap(cached); return; }
        workers.execute(() -> {
            HttpURLConnection connection = null;
            try {
                URL url = new URL(absolute);
                connection = (HttpURLConnection) url.openConnection();
                connection.setConnectTimeout(8000); connection.setReadTimeout(15000);
                connection.setInstanceFollowRedirects(false);
                URI host = URI.create(base);
                if (url.getHost().equals(host.getHost()) && url.getPort() == host.getPort() && url.getProtocol().equals(host.getScheme()))
                    connection.setRequestProperty("Authorization", "JWT " + token);
                if (connection.getResponseCode() != 200) throw new Exception("이미지 응답 오류");
                byte[] bytes;
                try (InputStream stream = connection.getInputStream()) { bytes = read(stream, 12 * 1024 * 1024); }
                BitmapFactory.Options options = new BitmapFactory.Options();
                options.inJustDecodeBounds = true;
                BitmapFactory.decodeByteArray(bytes, 0, bytes.length, options);
                options.inSampleSize = 1;
                while (options.outWidth / options.inSampleSize > 1600 || options.outHeight / options.inSampleSize > 1600) options.inSampleSize *= 2;
                options.inJustDecodeBounds = false;
                Bitmap bitmap = BitmapFactory.decodeByteArray(bytes, 0, bytes.length, options);
                if (bitmap == null) throw new Exception("이미지 형식 오류");
                images.put(absolute, bitmap);
                runOnUiThread(() -> { if (generation == requestGeneration && !isFinishing()) view.setImageBitmap(bitmap); });
            } catch (Exception e) {
                runOnUiThread(() -> { if (generation == requestGeneration) view.setContentDescription("사진을 불러오지 못했습니다. 새로고침해 주세요."); });
            } finally { if (connection != null) connection.disconnect(); }
        });
    }

    private void logout() {
        token = "";
        prefs.edit().remove("token").apply();
        images.evictAll();
        search = ""; unreadOnly = false;
        showLogin();
    }
    private void showFailure(Exception error, int requestGeneration) {
        runOnUiThread(() -> {
            if (generation != requestGeneration || isFinishing()) return;
            if (error instanceof ApiException && ((ApiException) error).code == 401) {
                logout(); status.setText("로그인 유효 기간이 지났습니다. 다시 로그인하세요.");
            } else status.setText(message(error));
        });
    }
    private String message(Exception e) {
        if (e instanceof ApiException) {
            int code = ((ApiException) e).code;
            if (code == 401 || code == 400) return "로그인 정보를 확인하세요. (HTTP " + code + ")";
            if (code == 403) return "이 기록에 접근할 권한이 없습니다.";
            if (code == 404) return "기록 또는 API 주소를 찾을 수 없습니다.";
            return "서버 요청에 실패했습니다. (HTTP " + code + ")";
        }
        return "서버에 연결하지 못했습니다. 서버 주소와 네트워크를 확인한 뒤 다시 시도하세요.";
    }
    private static String encode(String text) {
        try { return URLEncoder.encode(text, "UTF-8"); } catch (Exception ignored) { return ""; }
    }
    private static String date(String raw) {
        try { return OffsetDateTime.parse(raw).atZoneSameInstant(ZoneId.of("Asia/Seoul")).format(DateTimeFormatter.ofPattern("MM.dd HH:mm")); }
        catch (Exception ignored) { return raw.length() > 16 ? raw.substring(0, 16).replace('T', ' ') : raw; }
    }
    private static byte[] read(InputStream stream, int limit) throws Exception {
        ByteArrayOutputStream output = new ByteArrayOutputStream();
        byte[] buffer = new byte[8192];
        int count;
        while ((count = stream.read(buffer)) != -1) {
            if (output.size() + count > limit) throw new Exception("응답 크기 제한 초과");
            output.write(buffer, 0, count);
        }
        return output.toByteArray();
    }
    private static String request(String url, String method, String data, String auth) throws Exception {
        HttpURLConnection connection = (HttpURLConnection) new URL(url).openConnection();
        try {
            connection.setRequestMethod(method);
            connection.setConnectTimeout(8000); connection.setReadTimeout(15000);
            connection.setInstanceFollowRedirects(false);
            connection.setRequestProperty("Accept", "application/json");
            if (!auth.isEmpty()) connection.setRequestProperty("Authorization", "JWT " + auth);
            if (data != null) {
                connection.setDoOutput(true);
                connection.setRequestProperty("Content-Type", "application/x-www-form-urlencoded; charset=UTF-8");
                try (java.io.OutputStream stream = connection.getOutputStream()) { stream.write(data.getBytes(StandardCharsets.UTF_8)); }
            }
            int code = connection.getResponseCode();
            if (code < 200 || code >= 300) throw new ApiException(code);
            try (InputStream stream = connection.getInputStream()) { return new String(read(stream, 2 * 1024 * 1024), StandardCharsets.UTF_8); }
        } finally { connection.disconnect(); }
    }
    private static class ApiException extends Exception {
        final int code;
        ApiException(int code) { super("HTTP " + code); this.code = code; }
    }
}
