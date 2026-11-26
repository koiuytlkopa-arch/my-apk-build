package app.majhar;

import android.app.Activity;
import android.content.ContentValues;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.provider.MediaStore;
import android.util.Base64;
import android.webkit.*;
import android.widget.Toast;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;
import java.io.OutputStream;

public class MainActivity extends Activity {
    private WebView web;
    private ValueCallback<Uri[]> picker;

    @Override protected void onCreate(Bundle b) {
        super.onCreate(b);
        if (!Python.isStarted()) Python.start(new AndroidPlatform(this));
        Python.getInstance().getModule("android_entry").callAttr("start", getFilesDir().getAbsolutePath());
        web = new WebView(this);
        setContentView(web);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true); s.setDomStorageEnabled(true);
        web.addJavascriptInterface(new Object() {
            @JavascriptInterface public void save(String name, String mime, String b64) {
                try {
                    ContentValues v = new ContentValues();
                    v.put(MediaStore.Downloads.DISPLAY_NAME, name);
                    v.put(MediaStore.Downloads.MIME_TYPE, mime);
                    Uri u = getContentResolver().insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, v);
                    try (OutputStream o = getContentResolver().openOutputStream(u)) { o.write(Base64.decode(b64, Base64.DEFAULT)); }
                    runOnUiThread(() -> Toast.makeText(MainActivity.this, "تم الحفظ في التنزيلات: " + name, Toast.LENGTH_LONG).show());
                } catch (Exception e) {
                    runOnUiThread(() -> Toast.makeText(MainActivity.this, "تعذّر الحفظ", Toast.LENGTH_LONG).show());
                }
            }
        }, "Android");
        web.setWebViewClient(new WebViewClient() {
            @Override public void onReceivedError(WebView v, WebResourceRequest r, WebResourceError e) {
                // الخادم يحتاج ثانية ليبدأ: أعد المحاولة
                v.postDelayed(() -> v.loadUrl("http://127.0.0.1:8765"), 800);
            }
        });
        web.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onShowFileChooser(WebView w, ValueCallback<Uri[]> cb, FileChooserParams p) {
                if (picker != null) picker.onReceiveValue(null);
                picker = cb;
                Intent i = new Intent(Intent.ACTION_GET_CONTENT).addCategory(Intent.CATEGORY_OPENABLE)
                        .setType("image/*").putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);
                startActivityForResult(i, 1);
                return true;
            }
        });
        web.loadUrl("http://127.0.0.1:8765");
    }

    @Override protected void onActivityResult(int req, int res, Intent d) {
        if (req != 1 || picker == null) return;
        Uri[] out = null;
        if (res == RESULT_OK && d != null) {
            if (d.getClipData() != null) {
                out = new Uri[d.getClipData().getItemCount()];
                for (int k = 0; k < out.length; k++) out[k] = d.getClipData().getItemAt(k).getUri();
            } else if (d.getData() != null) out = new Uri[]{d.getData()};
        }
        picker.onReceiveValue(out); picker = null;
    }

    @Override public void onBackPressed() { if (web.canGoBack()) web.goBack(); else super.onBackPressed(); }
}
