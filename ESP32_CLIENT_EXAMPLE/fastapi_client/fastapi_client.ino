#include <WiFi.h>
#include <WebSocketsClient.h>
#include "esp_camera.h"
#include "soc/soc.h"
#include "soc/rtc_cntl_reg.h"
#include <ArduinoJson.h>
#include <ESP32Servo.h>
#include "HX711.h"
#include <mbedtls/base64.h>
#include <math.h>

/*
  ESP32-CAM + HX711 + 2 Servo
  - Khi can thay doi > 10g (dua tren trung vi 10 lan do): chup 1 anh + gui len server
  - Doi server tra output_code 1..5 roi dieu khien servo

  =================== SO DO NOI DAY ===================
  HX711:
    DT (DOUT) -> GPIO13
    SCK       -> GPIO14
    VCC       -> 3.3V
    GND       -> GND

  Servo1 (gat rac xuong bang chuyen):
    Signal    -> GPIO12
    VCC       -> nguon 5V ngoai (khuyen nghi), KHONG cap truc tiep tu 3.3V ESP32-CAM
    GND       -> GND chung voi ESP32-CAM

  Servo2 (xoay huong 0..180 theo 5 loai):
    Signal    -> GPIO2
    VCC       -> nguon 5V ngoai
    GND       -> GND chung voi ESP32-CAM

  Luu y:
  - Bat buoc noi chung mass (GND) giua ESP32-CAM, HX711, va nguon servo.
  - Neu servo gay reset, tang nguon servo/bo tri tu dien loc.
*/

// ================= WIFI/SERVER =================
const char* ssid = "TAN TIEN T2";
const char* password = "86868686";
const char* server = "192.168.1.4";
const int port = 8000;

// ================= WEBSOCKET =================
WebSocketsClient webSocket;
bool wsConnected = false;
bool waitingResponse = false;
unsigned long waitStartMs = 0;
const unsigned long RESPONSE_TIMEOUT_MS = 15000;

// ================= CAMERA (AI-THINKER) =================
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

// ================= HX711 =================
#define HX711_DT_PIN  13
#define HX711_SCK_PIN 14
HX711 scale;
float calibration_factor = 112.0f;
const int MEDIAN_SAMPLES = 10;
const float WEIGHT_CHANGE_THRESHOLD_G = 10.0f;
const unsigned long CAPTURE_DELAY_MS = 2000;
unsigned long lastWeightCheckMs = 0;
const unsigned long WEIGHT_CHECK_INTERVAL_MS = 250;
float baselineWeight = NAN;

// ================= SERVO =================
Servo servo1;
Servo servo2;
#define SERVO1_PIN 12
#define SERVO2_PIN 2
int angleMap[5] = {0, 45, 90, 135, 180}; // ma 1..5 => goc servo2

// ================= HELPERS =================
void sortArray(float* arr, int n) {
  for (int i = 0; i < n - 1; i++) {
    for (int j = 0; j < n - i - 1; j++) {
      if (arr[j] > arr[j + 1]) {
        float t = arr[j];
        arr[j] = arr[j + 1];
        arr[j + 1] = t;
      }
    }
  }
}

float readMedianWeight(int samples) {
  float values[MEDIAN_SAMPLES];
  int valid = 0;

  for (int i = 0; i < samples; i++) {
    if (scale.is_ready()) {
      values[valid++] = scale.get_units(1);
    }
    delay(15);
  }

  if (valid == 0) return NAN;

  sortArray(values, valid);
  if (valid % 2 == 1) return values[valid / 2];
  return (values[valid / 2 - 1] + values[valid / 2]) / 2.0f;
}

String base64Encode(const uint8_t* data, size_t len) {
  size_t outLen = 0;
  size_t outBufLen = ((len + 2) / 3) * 4 + 1;
  char* outBuf = (char*)ps_malloc(outBufLen);
  if (!outBuf) return String();

  int rc = mbedtls_base64_encode(
    (unsigned char*)outBuf,
    outBufLen,
    &outLen,
    (const unsigned char*)data,
    len
  );
  if (rc != 0) {
    free(outBuf);
    return String();
  }

  outBuf[outLen] = '\0';
  String out(outBuf);
  free(outBuf);
  return out;
}

// ================= CAMERA =================
bool initCamera() {
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
  config.frame_size = FRAMESIZE_QVGA; // can bang toc do va do ro cho WS
  config.jpeg_quality = 20;
  config.fb_count = 1;

  return esp_camera_init(&config) == ESP_OK;
}

// ================= NETWORK =================
void connectWiFi() {
  WiFi.begin(ssid, password);
  Serial.print("Connecting WiFi");

  int retry = 0;
  while (WiFi.status() != WL_CONNECTED && retry < 25) {
    delay(400);
    Serial.print(".");
    retry++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi OK");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\nWiFi FAIL -> restart");
    ESP.restart();
  }
}

void handleServoByCode(int code) {
  if (code < 1 || code > 5) return;

  int targetAngle = angleMap[code - 1];
  servo2.write(targetAngle);
  delay(500);

  // Servo1 gat xuong bang chuyen: 0 -> 90 -> 0
  servo1.write(90);
  delay(500);
  servo1.write(0);

  Serial.print("Sorted by code ");
  Serial.print(code);
  Serial.print(", servo2=");
  Serial.println(targetAngle);
}

void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
  if (type == WStype_CONNECTED) {
    wsConnected = true;
    Serial.println("WS Connected");
    return;
  }

  if (type == WStype_DISCONNECTED) {
    wsConnected = false;
    waitingResponse = false;
    waitStartMs = 0;
    Serial.println("WS Disconnected");
    return;
  }

  if (type != WStype_TEXT) return;

  DynamicJsonDocument doc(2048);
  DeserializationError err = deserializeJson(doc, payload, length);
  if (err) {
    Serial.print("JSON parse fail: ");
    Serial.println(err.c_str());
    return;
  }

  const char* msgType = doc["type"] | "";

  // Uu tien format classification_result cua server hien tai
  if (strcmp(msgType, "classification_result") == 0) {
    JsonArray results = doc["data"]["results"].as<JsonArray>();
    if (!results.isNull() && results.size() > 0) {
      int code = results[0]["output_code"] | 0;
      const char* label = results[0]["label"] | "unknown";
      float confidence = results[0]["confidence"] | 0.0f;
      Serial.print("Server output_code=");
      Serial.println(code);
      Serial.print("Label=");
      Serial.print(label);
      Serial.print(", conf=");
      Serial.println(confidence, 3);
      handleServoByCode(code);
    }
    waitingResponse = false;
    waitStartMs = 0;
    return;
  }

  if (strcmp(msgType, "batch_submitted") == 0) {
    int batchId = doc["batch_id"] | -1;
    Serial.print("Batch submitted id=");
    Serial.println(batchId);
    return;
  }

  // Fallback neu server tra truc tiep {"class":1..5}
  if (doc.containsKey("class")) {
    int code = doc["class"] | 0;
    Serial.print("Server class=");
    Serial.println(code);
    handleServoByCode(code);
    waitingResponse = false;
    waitStartMs = 0;
    return;
  }

  if (strcmp(msgType, "error") == 0) {
    Serial.print("Server error: ");
    Serial.println(doc["message"] | "");
    waitingResponse = false;
    waitStartMs = 0;
  }
}

bool sendImageAndWeight(float weightGrams) {
  camera_fb_t * fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("Capture fail");
    return false;
  }

  String b64 = base64Encode(fb->buf, fb->len);
  esp_camera_fb_return(fb);
  if (b64.length() == 0) {
    Serial.println("Base64 encode fail");
    return false;
  }

  String out;
  out.reserve(64 + b64.length());
  out += "{\"type\":\"image\",\"weight_grams\":";
  out += String(weightGrams, 2);
  out += ",\"data\":\"";
  out += b64;
  out += "\"}";

  webSocket.sendTXT(out);
  Serial.print("Sent image + weight=");
  Serial.println(weightGrams);
  return true;
}

void setup() {
  Serial.begin(115200);
  delay(500);
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0);

  if (!initCamera()) {
    Serial.println("Camera init FAIL");
    ESP.restart();
  }

  servo1.attach(SERVO1_PIN);
  servo2.attach(SERVO2_PIN);
  servo1.write(0);
  servo2.write(0);

  scale.begin(HX711_DT_PIN, HX711_SCK_PIN);
  scale.set_scale(calibration_factor);
  scale.tare(10);
  Serial.println("HX711 ready");

  connectWiFi();
  webSocket.begin(server, port, "/ws");
  webSocket.onEvent(webSocketEvent);
  webSocket.setReconnectInterval(3000);
}

void loop() {
  webSocket.loop();

  if (waitingResponse && waitStartMs > 0 && millis() - waitStartMs > RESPONSE_TIMEOUT_MS) {
    Serial.println("Response timeout -> unlock");
    waitingResponse = false;
    waitStartMs = 0;
  }

  if (!wsConnected || waitingResponse) return;
  if (millis() - lastWeightCheckMs < WEIGHT_CHECK_INTERVAL_MS) return;
  lastWeightCheckMs = millis();

  float currentWeight = readMedianWeight(MEDIAN_SAMPLES);
  if (isnan(currentWeight)) return;

  if (isnan(baselineWeight)) {
    baselineWeight = currentWeight;
    Serial.print("Baseline weight=");
    Serial.println(baselineWeight);
    return;
  }

  float delta = fabs(currentWeight - baselineWeight);
  if (delta >= WEIGHT_CHANGE_THRESHOLD_G) {
    Serial.print("Weight changed (>= ");
    Serial.print(WEIGHT_CHANGE_THRESHOLD_G, 1);
    Serial.print("g), capture in ");
    Serial.print(CAPTURE_DELAY_MS / 1000);
    Serial.print("s: baseline=");
    Serial.print(baselineWeight);
    Serial.print(", current=");
    Serial.print(currentWeight);
    Serial.print(", delta=");
    Serial.println(delta);

    delay(CAPTURE_DELAY_MS);
    Serial.println("Capture now after delay");
    if (sendImageAndWeight(currentWeight)) {
      waitingResponse = true;
      waitStartMs = millis();
      baselineWeight = currentWeight;
    }
  }
}
