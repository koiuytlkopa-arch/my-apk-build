package app.bkor;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.webkit.*;
import java.io.*;
import android.webkit.MimeTypeMap;

public class MainActivity extends Activity {
    private WebView web;
    private ValueCallback<Uri[]> picker;
    private int retries = 0;

    private static final String ENTRY = "index.html";
    private WebResourceResponse asset(String p) throws IOException {
        InputStream in = getAssets().open("www" + p);
        String ext = MimeTypeMap.getFileExtensionFromUrl(p);
        String mime = MimeTypeMap.getSingleton().getMimeTypeFromExtension(ext);
        if ("mjs".equals(ext)) mime = "text/javascript";
        if ("wasm".equals(ext)) mime = "application/wasm";
        if (mime == null) mime = "application/octet-stream";
        return new WebResourceResponse(mime, "UTF-8", in);
    }

    @Override protected void onCreate(Bundle b) {
        super.onCreate(b);
        web = new WebView(this);
        setContentView(web);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        web.setWebViewClient(new WebViewClient() {
            @Override public WebResourceResponse shouldInterceptRequest(WebView v, WebResourceRequest r) {
                Uri u = r.getUrl();
                if (!"app.local".equals(u.getHost())) return null;
                String p = u.getPath();
                if (p == null || p.equals("/")) p = "/" + ENTRY;
                try { return asset(p); } catch (IOException e) {
                    try { if (!p.contains(".")) return asset("/" + ENTRY); } catch (IOException e2) { }
                    return new WebResourceResponse("text/plain", "UTF-8", 404, "Not Found", null, new ByteArrayInputStream(new byte[0]));
                }
            }
        });
        web.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onShowFileChooser(WebView w, ValueCallback<Uri[]> cb, FileChooserParams p) {
                if (picker != null) picker.onReceiveValue(null);
                picker = cb;
                Intent i = new Intent(Intent.ACTION_GET_CONTENT).addCategory(Intent.CATEGORY_OPENABLE)
                        .setType("*/*").putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);
                startActivityForResult(i, 1);
                return true;
            }
        });
        web.setDownloadListener((url, ua, cd, mime, len) -> {
            try { startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url))); } catch (Exception e) { }
        });
        web.loadUrl("https://app.local/" + ENTRY);
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
        picker.onReceiveValue(out);
        picker = null;
    }

    @Override public void onBackPressed() { if (web.canGoBack()) web.goBack(); else super.onBackPressed(); }
}
