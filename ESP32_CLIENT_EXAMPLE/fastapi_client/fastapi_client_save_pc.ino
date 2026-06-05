#include "esp_camera.h"
#include <WiFi.h>
#include <ArduinoJson.h>
#include "base64.h"
#include "HX711.h"
#include <HTTPClient.h>

// ================= WIFI =================
const char* ssid = "TAN TIEN T2";
const char* password = "86868686";

// ================= SERVER =================
const char* server_host = "http://192.168.1.2:8000";

// ================= HX711 =================
#define DT 13
#define SCK 14

HX711 scale;

float calibration = 123.4;

// ================= CAMERA PINS (AI THINKER) =================
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27

#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

// ================= CẤU HÌNH =================
#define CAPTURE_INTERVAL_MS   5000  // 5 giây

// =====================================================

void initCamera() {
  camera_config_t config;
  
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size = FRAMESIZE_SVGA;  // 800x600
  config.jpeg_quality = 12;
  config.fb_count = 2;
  
  esp_err_t err = esp_camera_init(&config);
  
  if (err != ESP_OK) {
    Serial.printf("Camera init failed: 0x%x\n", err);
    while (true);
  }
  
  Serial.println("Camera OK");
}

// =====================================================

float readWeight() {
  if (!scale.is_ready()) {
    return 0;
  }
  
  long raw = scale.get_value();
  float weight = (raw / calibration) - 35;
  
  if (weight < 0) weight = 0;
  
  return weight;
}

// =====================================================

bool sendImageToServer(camera_fb_t* fb, float weight) {
  HTTPClient http;
  
  String url = String(server_host) + "/api/esp32/save-image";
  
  http.begin(url);
  http.addHeader("Content-Type", "application/json");
  
  // Encode image to base64
  String imageBase64 = base64::encode(fb->buf, fb->len);
  
  // Create JSON payload
  DynamicJsonDocument doc(1024 * 64);
  
  doc["image_data"] = imageBase64;
  doc["weight_grams"] = weight;
  doc["timestamp"] = millis();
  
  String jsonPayload;
  serializeJson(doc, jsonPayload);
  
  Serial.printf("Sending: %d bytes...\n", jsonPayload.length());
  
  int httpResponseCode = http.POST(jsonPayload);
  
  if (httpResponseCode > 0) {
    String response = http.getString();
    Serial.printf("Response: %d | %s\n", httpResponseCode, response.c_str());
    http.end();
    return (httpResponseCode == 200);
  } else {
    Serial.printf("HTTP Error: %s\n", http.errorToString(httpResponseCode).c_str());
    http.end();
    return false;
  }
}

// =====================================================

void captureAndSend() {
  camera_fb_t* fb = esp_camera_fb_get();
  
  if (!fb) {
    Serial.println("Capture failed");
    return;
  }
  
  Serial.printf("Captured: %d bytes\n", fb->len);
  
  float weight = readWeight();
  
  if (sendImageToServer(fb, weight)) {
    Serial.println(">>> SAVED to PC!");
  } else {
    Serial.println(">>> Save failed!");
  }
  
  esp_camera_fb_return(fb);
}

// =====================================================

void setup() {
  Serial.begin(115200);
  Serial.println("\n========== ESP32 -> PC IMAGE SAVE ==========");
  
  // HX711
  scale.begin(DT, SCK);
  delay(500);
  scale.set_scale(calibration);
  scale.tare();
  Serial.println("HX711 Ready");
  
  // WIFI
  WiFi.begin(ssid, password);
  Serial.print("WiFi...");
  
  int timeout = 0;
  while (WiFi.status() != WL_CONNECTED && timeout < 30) {
    delay(500);
    Serial.print(".");
    timeout++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi OK!");
    Serial.println("IP: " + WiFi.localIP().toString());
  } else {
    Serial.println("\nWiFi FAILED!");
  }
  
  // CAMERA
  initCamera();
  
  Serial.println("\n========== READY ==========");
  Serial.println("Capturing every 5 seconds...");
}

// =====================================================

unsigned long lastCapture = 0;

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi lost! Reconnecting...");
    WiFi.reconnect();
    delay(2000);
    return;
  }
  
  if (millis() - lastCapture >= CAPTURE_INTERVAL_MS) {
    lastCapture = millis();
    captureAndSend();
  }
}
