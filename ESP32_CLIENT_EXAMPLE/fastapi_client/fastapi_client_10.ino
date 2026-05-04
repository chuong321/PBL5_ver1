/*
 * ESP32-CAM FastAPI WebSocket Client (10s interval)
 * Sends one image every 10 seconds to /ws
 */

#include <WiFi.h>
#include <WebSocketsClient.h>
#include "esp_camera.h"
#include "soc/soc.h"
#include "soc/rtc_cntl_reg.h"
#include <ArduinoJson.h>

// ==================== WiFi ====================
const char* ssid = "Chuong12345";
const char* password = "chuong12345678";
const char* server = "172.20.10.3";  // Your PC IP
const int port = 8000;

// ==================== Hardware Pins ====================

// Camera (AI-THINKER ESP32-CAM)
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

// 5 Output Relays
const int RELAY_PINS[5] = {16, 17, 4, 2, 15};

// Weight Sensor (ADC)
const int WEIGHT_SENSOR_PIN = 36;

// ==================== Global Variables ====================
WebSocketsClient webSocket;
camera_config_t config;
bool connected = false;
unsigned long lastCaptureTime = 0;
const unsigned long captureInterval = 10000;  // 10s between captures

void setup() {
  Serial.begin(115200);
  delay(500);

  // Disable brownout detector
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0);

  // Initialize camera
  if (!initCamera()) {
    Serial.println("Camera init failed");
    return;
  }

  // Initialize relay pins
  for (int i = 0; i < 5; i++) {
    pinMode(RELAY_PINS[i], OUTPUT);
    digitalWrite(RELAY_PINS[i], LOW);
  }

  // Initialize weight sensor
  pinMode(WEIGHT_SENSOR_PIN, INPUT);

  // Connect WiFi
  connectToWiFi();

  // Setup WebSocket
  webSocket.begin(server, port, "/ws");
  webSocket.onEvent(webSocketEvent);
  webSocket.setReconnectInterval(5000);
}

void loop() {
  webSocket.loop();

  if (connected && (millis() - lastCaptureTime >= captureInterval)) {
    captureAndSendImage();
    lastCaptureTime = millis();
  }

  delay(10);
}

// ==================== CAMERA ====================

bool initCamera() {
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d7 = Y7_GPIO_NUM;
  config.pin_d6 = Y6_GPIO_NUM;
  config.pin_d5 = Y5_GPIO_NUM;
  config.pin_d4 = Y4_GPIO_NUM;
  config.pin_d3 = Y3_GPIO_NUM;
  config.pin_d2 = Y2_GPIO_NUM;
  config.pin_d1 = Y9_GPIO_NUM;
  config.pin_d0 = Y8_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;

  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size = FRAMESIZE_VGA;  // 640x480
  config.jpeg_quality = 12;
  config.fb_count = 1;

  if (esp_camera_init(&config) != ESP_OK) {
    return false;
  }
  return true;
}

// ==================== WiFi ====================

void connectToWiFi() {
  WiFi.begin(ssid, password);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    attempts++;
  }
}

// ==================== WEBSOCKET ====================

void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
  if (type == WStype_CONNECTED) {
    connected = true;
    webSocket.sendTXT("{\"type\":\"ping\"}");
  } else if (type == WStype_DISCONNECTED) {
    connected = false;
  } else if (type == WStype_TEXT) {
    String msg = String((char*)(payload));

    DynamicJsonDocument doc(4096);
    if (deserializeJson(doc, msg) == DeserializationError::Ok) {
      String type = doc["type"];
      if (type == "classification_result") {
        handleClassificationResult(doc);
      }
    }
  }
}

void handleClassificationResult(DynamicJsonDocument& doc) {
  JsonArray results = doc["data"]["results"];

  for (JsonObject res : results) {
    int code = res["output_code"];
    activateRelay(code);
  }
}

// ==================== RELAY CONTROL ====================

void activateRelay(int code) {
  if (code >= 1 && code <= 5) {
    int relayIndex = code - 1;

    digitalWrite(RELAY_PINS[relayIndex], HIGH);
    delay(2000);

    for (int i = 0; i < 5; i++) {
      digitalWrite(RELAY_PINS[i], LOW);
    }
  }
}

// ==================== WEIGHT SENSOR ====================

float readWeight() {
  int raw = analogRead(WEIGHT_SENSOR_PIN);
  return (raw / 4095.0) * 1000.0;
}

// ==================== BASE64 ENCODING ====================

static const char base64_chars[] =
  "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

String base64Encode(uint8_t* data, size_t len) {
  String encoded;
  int i = 0;
  uint8_t char_array_3[3];
  uint8_t char_array_4[4];

  while (i < len) {
    char_array_3[i % 3] = *(data++);
    i++;

    if (i % 3 == 0) {
      char_array_4[0] = (char_array_3[0] & 0xfc) >> 2;
      char_array_4[1] = ((char_array_3[0] & 0x03) << 4) + ((char_array_3[1] & 0xf0) >> 4);
      char_array_4[2] = ((char_array_3[1] & 0x0f) << 2) + ((char_array_3[2] & 0xc0) >> 6);
      char_array_4[3] = char_array_3[2] & 0x3f;

      for (i = 0; i < 4; i++) {
        encoded += base64_chars[char_array_4[i]];
      }
    }
  }

  if (i % 3 != 0) {
    for (int j = i % 3; j < 3; j++) char_array_3[j] = '\0';

    char_array_4[0] = (char_array_3[0] & 0xfc) >> 2;
    char_array_4[1] = ((char_array_3[0] & 0x03) << 4) + ((char_array_3[1] & 0xf0) >> 4);
    char_array_4[2] = ((char_array_3[1] & 0x0f) << 2) + ((char_array_3[2] & 0xc0) >> 6);

    for (int j = 0; j <= (i % 3); j++) {
      encoded += base64_chars[char_array_4[j]];
    }

    while (i++ % 3) encoded += '=';
  }

  return encoded;
}

// ==================== CAPTURE & SEND ====================

void captureAndSendImage() {
  camera_fb_t * fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("Capture failed");
    return;
  }

  String img_b64 = base64Encode(fb->buf, fb->len);
  float weight = readWeight();

  DynamicJsonDocument payload(img_b64.length() + 256);
  payload["type"] = "image";
  payload["data"] = img_b64;
  payload["weight_grams"] = weight;

  String json;
  serializeJson(payload, json);

  webSocket.sendTXT(json);
  esp_camera_fb_return(fb);
}
