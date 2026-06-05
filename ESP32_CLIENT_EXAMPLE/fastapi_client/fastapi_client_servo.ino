/*
 *  ESP8266 (NodeMCU Amica) - Servo Controller
 *  ============================================
 *  Ket noi WiFi -> WebSocket -> Nhan lenh tu Backend
 *
 *  Lenh nhan qua WebSocket:
 *    servo_command + output_code (1-5) -> Servo2 quay goc
 *    servo_command + push:true -> Servo1 day rac
 *
 *  Cai dat:
 *    - Board: NodeMCU 1.0 (ESP-12E Module)
 *    - Flash: 4MB (FS:1MB OTA:~1MB)
 *    - CPU: 80MHz
 *
 *  THAY DOI THU VIEN SERVO:
 *    Neu gap loi "Multiple libraries found for Servo.h",
 *    vao Sketch > Include Library > Manage Libraries,
 *    tim "Servo" by Arduino, go bo cai co duong dan
 *    C:\Users\duyta\AppData\Local\Arduino15\libraries\Servo
 *    Chi giu duy nhat:
 *    C:\Users\duyta\AppData\Local\Arduino15\packages\esp8266\hardware\esp8266\3.1.2\libraries\Servo
 */

#include <ESP8266WiFi.h>
#include <WebSocketsClient.h>
#include <ArduinoJson.h>
#include <Servo.h>

// ===== WIFI =====
const char* ssid = "TAN TIEN T2";
const char* password = "86868686";

// ===== WEBSOCKET =====
const char* ws_host = "192.168.1.2";
const uint16_t ws_port = 8000;
const char* ws_path = "/ws/servo";

WebSocketsClient webSocket;

// ===== SERVO =====
#define SERVO1_PIN  D5   // D5 (GPIO14) - day rac len bang chuyen
#define SERVO2_PIN  D6   // D6 (GPIO12) - cong gate phan loai

Servo servo1;
Servo servo2;

const int SERVO1_REST = 0;
const int SERVO1_PUSH = 90;

const int SERVO2_POS[5] = { 20, 45, 70, 95, 120 };

int servo1_pos = 0;
int servo2_pos = 1;

// ===== LAMP =====
#define LAMP_PIN  D7   // D7 (GPIO13) - den bao hieu

// ===== TIMING =====
unsigned long lastStatusReport = 0;

// ===== SETUP =====
void setup() {
  Serial.begin(115200);
  delay(500);

  pinMode(LAMP_PIN, OUTPUT);
  digitalWrite(LAMP_PIN, LOW);

  // Khoi tao servo
  servo1.attach(SERVO1_PIN);
  servo1.write(SERVO1_REST);
  servo1_pos = SERVO1_REST;

  servo2.attach(SERVO2_PIN);
  servo2.write(Servo2Angle(1));
  servo2_pos = 1;

  // Nhap nhay 3 lan = san sang
  lampBlink(3, 200);

  connectWiFi();
  connectWebSocket();
}

void lampBlink(int times, int ms) {
  for (int i = 0; i < times; i++) {
    digitalWrite(LAMP_PIN, HIGH);
    delay(ms);
    digitalWrite(LAMP_PIN, LOW);
    delay(ms);
  }
}

// ===== WIFI =====
void connectWiFi() {
  Serial.print("Connecting to WiFi: ");
  Serial.println(ssid);
  WiFi.begin(ssid, password);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
    attempts++;
    if (attempts > 30) {
      Serial.println("\n[ERR] WiFi failed! Restarting...");
      ESP.restart();
    }
  }

  Serial.println();
  Serial.print("WiFi OK! IP: ");
  Serial.println(WiFi.localIP());
}

// ===== WEBSOCKET =====
void connectWebSocket() {
  Serial.print("WS connecting to: ");
  Serial.print(ws_host);
  Serial.print(":");
  Serial.print(ws_port);
  Serial.println(ws_path);

  webSocket.begin(ws_host, ws_port, ws_path);
  webSocket.onEvent(webSocketEvent);
  webSocket.setReconnectInterval(5000);
  webSocket.enableHeartbeat(15000, 3000, 2);
}

void webSocketEvent(WStype_t type, uint8_t *payload, size_t length) {
  switch (type) {
    case WStype_DISCONNECTED:
      Serial.println("[WS] Disconnected");
      digitalWrite(LAMP_PIN, LOW);
      break;

    case WStype_CONNECTED:
      Serial.println("[WS] Connected!");
      digitalWrite(LAMP_PIN, HIGH);
      delay(300);
      digitalWrite(LAMP_PIN, LOW);
      sendRegister();
      break;

    case WStype_TEXT: {
      Serial.print("[WS] RX: ");
      Serial.println((char *)payload);
      handleMessage((char *)payload);
      break;
    }

    case WStype_PING:
      // ESP8266 WebSocketsClient tu dong reply pong
      // Khong can lam gi them
      break;

    case WStype_PONG:
      // Pong tu server (hoac auto-reply)
      break;

    default:
      break;
  }
}

void sendRegister() {
  StaticJsonDocument<256> doc;
  doc["type"] = "servo_ready";
  doc["device"] = "ESP8266-SERVO";

  char buffer[256];
  serializeJson(doc, buffer);
  webSocket.sendTXT(buffer);

  Serial.println("[WS] Sent servo_ready");
}

void handleMessage(char *jsonStr) {
  StaticJsonDocument<256> doc;
  DeserializationError err = deserializeJson(doc, jsonStr);
  if (err) {
    Serial.print("[ERR] JSON parse failed: ");
    Serial.println(err.c_str());
    return;
  }

  const char *msgType = doc["type"];

  if (strcmp(msgType, "servo_command") == 0) {
    int outputCode = doc["output_code"] | 0;

    if (outputCode >= 1 && outputCode <= 5) {
      doClassify(outputCode);
    }

    bool push = doc["push"] | false;
    if (push) {
      doPush();
    }

    sendAck(outputCode);
  }
  else if (strcmp(msgType, "ping") == 0) {
    // Tra loi ping
    webSocket.sendTXT("{\"type\":\"pong\"}");
  }
}

void sendAck(int outputCode) {
  StaticJsonDocument<256> doc;
  doc["type"] = "servo_ack";
  doc["output_code"] = outputCode;
  doc["servo1"] = servo1.read();
  doc["servo2"] = servo2.read();
  doc["status"] = "ok";

  char buffer[256];
  serializeJson(doc, buffer);
  webSocket.sendTXT(buffer);

  Serial.print("[WS] Ack code ");
  Serial.println(outputCode);
}

// ===== SERVO ACTIONS =====
int Servo2Angle(int pos) {
  if (pos < 1) pos = 1;
  if (pos > 5) pos = 5;
  return SERVO2_POS[pos - 1];
}

void doClassify(int pos) {
  if (pos < 1) pos = 1;
  if (pos > 5) pos = 5;

  int deg = Servo2Angle(pos);
  servo2.write(deg);
  servo2_pos = pos;

  digitalWrite(LAMP_PIN, HIGH);
  delay(300);
  digitalWrite(LAMP_PIN, LOW);

  Serial.print("[CLASSIFY] pos=");
  Serial.print(pos);
  Serial.print(" -> ");
  Serial.print(deg);
  Serial.println(" deg");
}

void doPush() {
  digitalWrite(LAMP_PIN, HIGH);

  Serial.println("[PUSH] Servo1 push...");
  servo1.write(SERVO1_PUSH);
  delay(500);
  servo1.write(SERVO1_REST);
  delay(300);

  digitalWrite(LAMP_PIN, LOW);
  Serial.println("[PUSH] Done.");
}

void doStatus() {
  Serial.println("--- STATUS ---");
  Serial.print("Servo1: ");
  Serial.println(servo1.read());
  Serial.print("Servo2: ");
  Serial.print(servo2.read());
  Serial.print(" (pos ");
  Serial.print(servo2_pos);
  Serial.println(")");
  Serial.print("Lamp: ");
  Serial.println(digitalRead(LAMP_PIN) ? "ON" : "OFF");
  Serial.print("WiFi RSSI: ");
  Serial.println(WiFi.RSSI());
  Serial.println("----------------");
}

// ===== LOOP =====
void loop() {
  webSocket.loop();

  unsigned long now = millis();

  // Gui status cho server moi 30s
  if (now - lastStatusReport > 30000) {
    lastStatusReport = now;
    if (WiFi.status() == WL_CONNECTED) {
      StaticJsonDocument<128> doc;
      doc["type"] = "servo_status";
      doc["rssi"] = WiFi.RSSI();
      doc["servo1"] = servo1.read();
      doc["servo2_pos"] = servo2_pos;

      char buffer[128];
      serializeJson(doc, buffer);
      webSocket.sendTXT(buffer);
    }
  }

  // Tu dong reconnect WiFi
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[WARN] WiFi lost! Reconnecting...");
    digitalWrite(LAMP_PIN, LOW);
    connectWiFi();
    connectWebSocket();
  }
}
