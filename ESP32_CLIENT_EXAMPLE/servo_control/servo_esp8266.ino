#include <ESP8266WiFi.h>
#include <WebSocketsClient.h>
#include <Servo.h>

// ================= SERVO =================
#define SERVO1_PIN  D1  // GPIO5 - Servo gạt
#define SERVO2_PIN  D2  // GPIO4 - Servo quay góc 1-5

Servo servo1;
Servo servo2;

// ================= VỊ TRÍ SERVO =================
// Servo 1 gạt
#define SERVO1_POS_REST   0    // Vị trí nghỉ
#define SERVO1_POS_PUSH  180  // Vị trí gạt

// Servo 2 quay: 5 góc tương ứng 1-5
#define SERVO2_POS_1   0
#define SERVO2_POS_2  45
#define SERVO2_POS_3  90
#define SERVO2_POS_4 135
#define SERVO2_POS_5 180

// ================= TRẠNG THÁI =================
int currentAngle = SERVO2_POS_1;

// ================= WIFI =================
const char* ssid = "TAN TIEN T2";
const char* password = "86868686";

// ================= SERVER =================
const char* server_host = "192.168.1.2";  // IP máy chạy server
const int server_port = 8000;
const char* ws_path = "/ws/servo";

// ================= WEBSOCKET =================
WebSocketsClient webSocket;

// =====================================================

void webSocketEvent(WStype_t type, uint8_t* payload, size_t length) {
  switch (type) {
    case WStype_DISCONNECTED:
      Serial.println("[WS] Disconnected!");
      break;
      
    case WStype_CONNECTED:
      Serial.println("[WS] Connected!");
      webSocket.sendTXT("{\"type\":\"servo_ready\"}");
      break;
      
    case WStype_TEXT: {
      Serial.print("[WS] RX: ");
      Serial.println((char*)payload);
      
      // Parse JSON
      // {"type":"servo_command","output_code":3}
      String data = String((char*)payload);
      
      if (data.indexOf("servo_command") != -1) {
        int code = 0;
        if (data.indexOf("output_code") != -1) {
          int idx = data.indexOf("output_code");
          int valStart = data.indexOf(":", idx) + 1;
          String valStr = "";
          for (int i = valStart; i < (int)length && isDigit(data.charAt(i)); i++) {
            valStr += data.charAt(i);
          }
          if (valStr.length() > 0) {
            code = valStr.toInt();
          }
        }
        
        if (code >= 1 && code <= 5) {
          Serial.print("[SERVO] Command: ");
          Serial.println(code);
          
          if (code == 1) {
            trash1();
          } else if (code == 2) {
            trash2();
          } else if (code == 3) {
            trash3();
          } else if (code == 4) {
            trash4();
          } else if (code == 5) {
            trash5();
          }
          
          char buffer[64];
          snprintf(buffer, sizeof(buffer), "{\"type\":\"servo_ack\",\"code\":%d}", code);
          webSocket.sendTXT(buffer);
        }
      }
      break;
    }
    
    case WStype_PONG:
      Serial.println("[WS] Pong received");
      break;
      
    case WStype_PING:
      Serial.println("[WS] Ping received");
      break;
      
    default:
      break;
  }
}

// =====================================================

void pushServo1() {
  servo1.write(SERVO1_POS_PUSH);
  Serial.println("SERVO1: PUSH");
}

void restServo1() {
  servo1.write(SERVO1_POS_REST);
  Serial.println("SERVO1: REST");
}

void rotateServo2(int angle) {
  servo2.write(angle);
  currentAngle = angle;
  Serial.print("SERVO2: ");
  Serial.println(angle);
}

void trash1() {
  pushServo1();
  delay(300);
  rotateServo2(SERVO2_POS_1);
  delay(500);
  restServo1();
}

void trash2() {
  pushServo1();
  delay(300);
  rotateServo2(SERVO2_POS_2);
  delay(500);
  restServo1();
}

void trash3() {
  pushServo1();
  delay(300);
  rotateServo2(SERVO2_POS_3);
  delay(500);
  restServo1();
}

void trash4() {
  pushServo1();
  delay(300);
  rotateServo2(SERVO2_POS_4);
  delay(500);
  restServo1();
}

void trash5() {
  pushServo1();
  delay(300);
  rotateServo2(SERVO2_POS_5);
  delay(500);
  restServo1();
}

// =====================================================

void setup() {
  Serial.begin(115200);
  Serial.println("\n========== ESP8266 SERVO + WS ==========");
  
  // SERVO
  servo1.attach(SERVO1_PIN);
  servo2.attach(SERVO2_PIN);
  restServo1();
  rotateServo2(SERVO2_POS_1);
  Serial.println("Servo OK");
  
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
  
  // WEBSOCKET
  webSocket.begin(server_host, server_port, ws_path);
  webSocket.onEvent(webSocketEvent);
  webSocket.setReconnectInterval(5000);
  webSocket.enableHeartbeat(15000, 3000, 2);
  
  Serial.println("WebSocket connecting...");
  Serial.println("\n========== READY ==========");
  Serial.println("Waiting for servo commands from server...");
}

// =====================================================

void loop() {
  webSocket.loop();
  
  // Debug: nhan 1-5 tu Serial
  if (Serial.available() > 0) {
    char c = Serial.read();
    if (c >= '1' && c <= '5') {
      int code = c - '0';
      Serial.print("Serial command: ");
      Serial.println(code);
      
      if (code == 1) trash1();
      else if (code == 2) trash2();
      else if (code == 3) trash3();
      else if (code == 4) trash4();
      else if (code == 5) trash5();
    }
  }
}
