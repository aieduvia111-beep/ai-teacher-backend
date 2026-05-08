package com.eduvia.app;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.provider.MediaStore;
import android.util.Base64;
import androidx.activity.result.ActivityResult;
import androidx.core.content.FileProvider;
import com.getcapacitor.*;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.getcapacitor.annotation.Permission;
import com.getcapacitor.annotation.PermissionCallback;
import java.io.File;
import java.io.InputStream;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

@CapacitorPlugin(
    name = "EduviaFile",
    permissions = {
        @Permission(strings = {Manifest.permission.CAMERA}, alias = "camera"),
        @Permission(strings = {Manifest.permission.READ_MEDIA_IMAGES}, alias = "photos"),
        @Permission(strings = {Manifest.permission.READ_EXTERNAL_STORAGE}, alias = "storage")
    }
)
public class EduviaFilePlugin extends Plugin {

    private Uri photoUri;

    @PluginMethod
    public void takePhoto(PluginCall call) {
        if (getPermissionState("camera") != PermissionState.GRANTED) {
            requestPermissionForAlias("camera", call, "cameraCallback");
            return;
        }
        launchCamera(call);
    }

    @PermissionCallback
    private void cameraCallback(PluginCall call) {
        if (getPermissionState("camera") == PermissionState.GRANTED) {
            launchCamera(call);
        } else {
            call.reject("Brak uprawnień do aparatu");
        }
    }

    private void launchCamera(PluginCall call) {
        try {
            String timestamp = new SimpleDateFormat("yyyyMMdd_HHmmss", Locale.getDefault()).format(new Date());
            File photoFile = new File(getContext().getCacheDir(), "EDUVIA_" + timestamp + ".jpg");
            photoUri = FileProvider.getUriForFile(
                getContext(),
                getContext().getPackageName() + ".fileprovider",
                photoFile
            );
            Intent intent = new Intent(MediaStore.ACTION_IMAGE_CAPTURE);
            intent.putExtra(MediaStore.EXTRA_OUTPUT, photoUri);
            startActivityForResult(call, intent, "cameraResult");
        } catch (Exception e) {
            call.reject("Blad aparatu: " + e.getMessage());
        }
    }

    @ActivityCallback
    private void cameraResult(PluginCall call, ActivityResult result) {
        if (result.getResultCode() == Activity.RESULT_OK && photoUri != null) {
            String base64 = uriToBase64(photoUri);
            if (base64 != null) {
                JSObject ret = new JSObject();
                ret.put("base64", base64);
                call.resolve(ret);
            } else {
                call.reject("Blad odczytu zdjecia");
            }
        } else {
            call.reject("Anulowano");
        }
    }

    @PluginMethod
    public void pickFromGallery(PluginCall call) {
        Intent intent = new Intent(Intent.ACTION_PICK, MediaStore.Images.Media.EXTERNAL_CONTENT_URI);
        intent.setType("image/*");
        intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);
        startActivityForResult(call, intent, "galleryResult");
    }

    @ActivityCallback
    private void galleryResult(PluginCall call, ActivityResult result) {
        if (result.getResultCode() == Activity.RESULT_OK && result.getData() != null) {
            JSArray images = new JSArray();
            Intent data = result.getData();
            if (data.getClipData() != null) {
                int count = Math.min(data.getClipData().getItemCount(), 15);
                for (int i = 0; i < count; i++) {
                    Uri uri = data.getClipData().getItemAt(i).getUri();
                    String base64 = uriToBase64(uri);
                    if (base64 != null) images.put(base64);
                }
            } else if (data.getData() != null) {
                String base64 = uriToBase64(data.getData());
                if (base64 != null) images.put(base64);
            }
            JSObject ret = new JSObject();
            ret.put("images", images);
            call.resolve(ret);
        } else {
            call.reject("Anulowano");
        }
    }

    private String uriToBase64(Uri uri) {
        try {
            InputStream inputStream = getContext().getContentResolver().openInputStream(uri);
            if (inputStream == null) return null;
            byte[] bytes = inputStream.readAllBytes();
            inputStream.close();
            return Base64.encodeToString(bytes, Base64.NO_WRAP);
        } catch (Exception e) {
            return null;
        }
    }
}
