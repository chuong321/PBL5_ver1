#include "esp_camera.h"
#include <WiFi.h>
#include <WebSocketsClient.h>
#include <ArduinoJson.h>
#include "base64.h"
#include "HX711.h"

// ================= WIFI =================
const char* ssid = "TAN TIEN T2";
const char* password = "86868686";

// ================= WEBSOCKET =================
const char* ws_host = "192.168.1.4";
const uint16_t ws_port = 8000;
const char* ws_path = "/ws";

WebSocketsClient webSocket;

// ================= HX711 =================
#define DT 14
#define SCK 13

HX711 scale;

long offset = 110060;
float calibration = 81;

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

  config.frame_size = FRAMESIZE_VGA;

  config.jpeg_quality = 20;

  config.fb_count = 1;

  esp_err_t err = esp_camera_init(&config);

  if (err != ESP_OK) {

    Serial.printf("Camera init failed: 0x%x\n", err);

    while (true);
  }

  Serial.println("Camera OK");
}

// =====================================================

void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {

  switch(type) {

    case WStype_DISCONNECTED:
      Serial.println("WebSocket Disconnected");
      break;

    case WStype_CONNECTED:
      Serial.println("WebSocket Connected");
      break;

    case WStype_TEXT:
      Serial.printf("Server: %s\n", payload);
      break;

    default:
      break;
  }
}

// =====================================================

float readWeight() {

  if (!scale.is_ready()) {

    Serial.println("HX711 not found");

    return 0;
  }

  long raw = scale.read_average(10);

  float weight = (raw - offset) / calibration -35;

  if (weight < 0)
    weight = 0;

  Serial.print("RAW: ");
  Serial.print(raw);

  Serial.print(" | Weight: ");
  Serial.print(weight, 1);
  Serial.println(" g");

  return weight;
}

// =====================================================

void sendImage() {

  camera_fb_t * fb = esp_camera_fb_get();

  if (!fb) {

    Serial.println("Camera capture failed");

    return;
  }

  // ========= ĐỌC CÂN THẬT =========

  float weight = readWeight();

  // ========= BASE64 =========

  String imageBase64 = base64::encode(fb->buf, fb->len);

  // ========= JSON =========

  DynamicJsonDocument doc(1024);

  doc["type"] = "image";

  doc["data"] = imageBase64;

  doc["weight_grams"] = weight;

  String jsonString;

  serializeJson(doc, jsonString);

  // ========= SEND =========

  webSocket.sendTXT(jsonString);

  Serial.print("Image sent | Weight: ");
  Serial.print(weight, 1);
  Serial.println(" g");

  esp_camera_fb_return(fb);
}

// =====================================================

void setup() {

  Serial.begin(115200);

  // ========= HX711 =========

  scale.begin(DT, SCK);

  delay(1000);

  Serial.println("HX711 Ready");

  // ========= WIFI =========

  WiFi.begin(ssid, password);

  Serial.print("Connecting WiFi");

  while (WiFi.status() != WL_CONNECTED) {

    delay(500);

    Serial.print(".");
  }

  Serial.println();

  Serial.println("WiFi connected");

  Serial.println(WiFi.localIP());

  // ========= CAMERA =========

  initCamera();

  // ========= WEBSOCKET =========

  webSocket.begin(ws_host, ws_port, ws_path);

  webSocket.onEvent(webSocketEvent);

  webSocket.setReconnectInterval(5000);
}

// =====================================================

unsigned long lastSend = 0;

// =====================================================

void loop() {

  webSocket.loop();

  // gửi ảnh mỗi 3 giây

  if (millis() - lastSend > 3000) {

    lastSend = millis();

    if (webSocket.isConnected()) {

      sendImage();
    }
  }
}