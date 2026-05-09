package com.eduvia.app;

import com.getcapacitor.BridgeActivity;
import com.codetrixstudio.capacitor.GoogleAuth.GoogleAuth;
import android.webkit.WebView;
import android.webkit.PermissionRequest;
import android.webkit.WebSettings;
import com.getcapacitor.Bridge;

public class MainActivity extends BridgeActivity {
  @Override
  public void onCreate(android.os.Bundle savedInstanceState) {
    registerPlugin(GoogleAuth.class);
    super.onCreate(savedInstanceState);
  }

  @Override
  public void onStart() {
    super.onStart();
    Bridge bridge = getBridge();
    if (bridge != null) {
      WebView webView = bridge.getWebView();
      WebSettings settings = webView.getSettings();
      settings.setMediaPlaybackRequiresUserGesture(false);
      settings.setDomStorageEnabled(true);
      settings.setJavaScriptEnabled(true);
      settings.setAllowFileAccess(true);
      settings.setAllowContentAccess(true);
      settings.setSupportZoom(false);
      webView.setWebChromeClient(new android.webkit.WebChromeClient() {
        @Override
        public void onPermissionRequest(PermissionRequest request) {
          request.grant(request.getResources());
        }
      });
    }
  }
}
