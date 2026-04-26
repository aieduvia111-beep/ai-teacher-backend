package com.eduvia.app;

import com.getcapacitor.BridgeActivity;
import ee.forgr.capacitor.social.login.SocialLoginPlugin;

public class MainActivity extends BridgeActivity {
  @Override
  public void onCreate(android.os.Bundle savedInstanceState) {
    registerPlugin(SocialLoginPlugin.class);
    super.onCreate(savedInstanceState);
  }
}
