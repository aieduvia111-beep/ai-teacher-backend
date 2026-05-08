package com.eduvia.app;

import android.Manifest;
import android.content.Intent;
import android.os.Bundle;
import android.speech.RecognitionListener;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;
import android.speech.tts.TextToSpeech;
import android.speech.tts.UtteranceProgressListener;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.getcapacitor.annotation.Permission;
import com.getcapacitor.annotation.PermissionCallback;
import com.getcapacitor.PermissionState;
import java.util.ArrayList;
import java.util.Locale;

@CapacitorPlugin(
    name = "EduviaSpeech",
    permissions = {
        @Permission(strings = {Manifest.permission.RECORD_AUDIO}, alias = "microphone")
    }
)
public class EduviaSpeechPlugin extends Plugin {

    private SpeechRecognizer speechRecognizer;
    private TextToSpeech tts;
    private PluginCall activeCall;
    private boolean ttsReady = false;

    @Override
    public void load() {
        tts = new TextToSpeech(getContext(), status -> {
            if (status == TextToSpeech.SUCCESS) {
                int result = tts.setLanguage(new Locale("pl", "PL"));
                if (result == TextToSpeech.LANG_MISSING_DATA || result == TextToSpeech.LANG_NOT_SUPPORTED) {
                    tts.setLanguage(Locale.getDefault());
                }
                tts.setSpeechRate(0.95f);
                ttsReady = true;
            }
        });
    }

    @PluginMethod
    public void startListening(PluginCall call) {
        if (getPermissionState("microphone") != PermissionState.GRANTED) {
            requestPermissionForAlias("microphone", call, "micCallback");
            return;
        }
        doStartListening(call);
    }

    @PermissionCallback
    private void micCallback(PluginCall call) {
        if (getPermissionState("microphone") == PermissionState.GRANTED) {
            doStartListening(call);
        } else {
            call.reject("Brak uprawnien do mikrofonu");
        }
    }

    private void doStartListening(PluginCall call) {
        activeCall = call;
        getActivity().runOnUiThread(() -> {
            try {
                if (speechRecognizer != null) speechRecognizer.destroy();
                speechRecognizer = SpeechRecognizer.createSpeechRecognizer(getContext());
                speechRecognizer.setRecognitionListener(new RecognitionListener() {
                    @Override public void onReadyForSpeech(Bundle p) {
                        JSObject e = new JSObject(); e.put("status","ready");
                        notifyListeners("speechStatus", e);
                    }
                    @Override public void onResults(Bundle results) {
                        ArrayList<String> m = results.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
                        if (m != null && !m.isEmpty()) {
                            JSObject ret = new JSObject(); ret.put("text", m.get(0));
                            if (activeCall != null) { activeCall.resolve(ret); activeCall = null; }
                        } else {
                            if (activeCall != null) { activeCall.reject("Nie rozpoznano"); activeCall = null; }
                        }
                    }
                    @Override public void onError(int error) {
                        if (activeCall != null) { activeCall.reject("Blad: " + error); activeCall = null; }
                    }
                    @Override public void onBeginningOfSpeech() {}
                    @Override public void onRmsChanged(float r) {}
                    @Override public void onBufferReceived(byte[] b) {}
                    @Override public void onEndOfSpeech() {}
                    @Override public void onPartialResults(Bundle p) {}
                    @Override public void onEvent(int t, Bundle p) {}
                });

                Intent intent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
                intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
                intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "pl-PL");
                intent.putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1);
                speechRecognizer.startListening(intent);
            } catch (Exception e) {
                call.reject("Blad: " + e.getMessage());
            }
        });
    }

    @PluginMethod
    public void stopListening(PluginCall call) {
        getActivity().runOnUiThread(() -> { if (speechRecognizer != null) speechRecognizer.stopListening(); });
        call.resolve();
    }

    @PluginMethod
    public void speak(PluginCall call) {
        String text = call.getString("text", "");
        float rate = call.getFloat("rate", 1.0f);
        if (!ttsReady || tts == null) { call.reject("TTS nie gotowy"); return; }
        tts.setSpeechRate(rate);
        tts.setOnUtteranceProgressListener(new UtteranceProgressListener() {
            @Override public void onStart(String u) {}
            @Override public void onDone(String u) { call.resolve(); }
            @Override public void onError(String u) { call.reject("Blad TTS"); }
        });
        tts.speak(text, TextToSpeech.QUEUE_FLUSH, null, "EDUVIA_TTS");
    }

    @PluginMethod
    public void stopSpeaking(PluginCall call) {
        if (tts != null) tts.stop();
        call.resolve();
    }

    @Override
    protected void handleOnDestroy() {
        if (speechRecognizer != null) speechRecognizer.destroy();
        if (tts != null) { tts.stop(); tts.shutdown(); }
    }
}
