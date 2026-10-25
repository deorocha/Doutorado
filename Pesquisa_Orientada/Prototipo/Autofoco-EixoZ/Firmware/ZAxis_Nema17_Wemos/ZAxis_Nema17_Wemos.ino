// ZAxis_Nema17_Wemos.ino  —  v2 (não-bloqueante, ready imediato)
//
// Protocolo Serial (115200):
//   Z<mm> | W | ? | $102? | $102=<v> | $0 | PING | $I
// Protocolo HTTP:
//   GET  /move?mm=20   /wait   /pos   /spm   /ping
//   POST /spm (v=<steps_per_mm>)
//
// NOTA: setup() NÃO bloqueia. "ready" é impresso imediatamente.
//       WiFi conecta em background; IP é reportado no loop().

#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include <AccelStepper.h>

// ---- Pinos ----
#define STEP_PIN D5   // GPIO14
#define DIR_PIN  D6   // GPIO12
#define EN_PIN   D7   // GPIO13 (ativo em LOW)
#define LED_PIN  LED_BUILTIN  // GPIO2 (ativo em LOW no Wemos)

// ---- Configuração padrão ----
float steps_per_mm = 400.0f;                 // Nema17 + DRV8825 1/16 + T8
const float MAX_SPEED_MM_S  = 8.0f;          // 8 mm/s = 480 mm/min
const float ACCEL_MM_S2     = 200.0f;        // mm/s²
#define FW_VERSION "2.0"

// ---- WiFi (deixe vazio "" para desabilitar) ----
const char* WIFI_SSID = "AP DO PAI";
const char* WIFI_PASS = "Vitor2005#";

AccelStepper stepper(AccelStepper::DRIVER, STEP_PIN, DIR_PIN);
ESP8266WebServer server(80);

long pos_steps = 0;
bool waiting_idle = false;
bool wifi_reported = false;

void apply_config() {
  stepper.setMaxSpeed(MAX_SPEED_MM_S * steps_per_mm);
  stepper.setAcceleration(ACCEL_MM_S2 * steps_per_mm);
}

void move_mm(float mm) {
  pos_steps = (long)(mm * steps_per_mm);
  stepper.moveTo(pos_steps);
}

// ---------- HTTP ----------
void h_move() {
  if (!server.hasArg("mm")) { server.send(400, "text/plain", "missing mm"); return; }
  move_mm(server.arg("mm").toFloat());
  server.send(200, "text/plain", "ok");
}
void h_wait() {
  unsigned long t0 = millis();
  while (stepper.distanceToGo() != 0 && millis() - t0 < 60000) {
    stepper.run(); delay(1); yield();
  }
  server.send(200, "text/plain", "ok");
}
void h_pos() {
  server.send(200, "text/plain",
              String(stepper.currentPosition() / steps_per_mm, 4));
}
void h_spm_get() { server.send(200, "text/plain", String(steps_per_mm, 4)); }
void h_spm_post() {
  if (!server.hasArg("v")) { server.send(400, "text/plain", "missing v"); return; }
  float v = server.arg("v").toFloat();
  if (v > 0.1f) { steps_per_mm = v; apply_config();
                  server.send(200, "text/plain", "ok"); }
  else server.send(400, "text/plain", "invalid");
}
void h_ping() { server.send(200, "text/plain", "PONG"); }

// ---------- setup (NÃO-BLOQUEANTE) ----------
void setup() {
  // Driver o mais cedo possível
  pinMode(EN_PIN, OUTPUT);
  digitalWrite(EN_PIN, LOW);           // habilita DRV8825

  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, HIGH);         // LED apagado (ativo em LOW)

  Serial.begin(115200);
  Serial.setTimeout(50);               // readStringUntil não trava 1 s
  delay(80);
  Serial.println();
  Serial.println("[Nema17 Z-axis controller]");
  Serial.print("Firmware: ");
  Serial.println(FW_VERSION);
  apply_config();

  // WiFi em background — NÃO espera conexão
  if (strlen(WIFI_SSID) > 0 && strcmp(WIFI_SSID, "SUA_REDE") != 0) {
    WiFi.mode(WIFI_STA);
    WiFi.setAutoReconnect(true);
    WiFi.begin(WIFI_SSID, WIFI_PASS);
    Serial.println("WiFi: conectando em background...");
  } else {
    Serial.println("WiFi: credenciais vazias (pulando)");
  }

  // HTTP (registra mesmo sem WiFi)
  server.on("/move", h_move);
  server.on("/wait", h_wait);
  server.on("/pos",  h_pos);
  server.on("/spm",  HTTP_GET,  h_spm_get);
  server.on("/spm",  HTTP_POST, h_spm_post);
  server.on("/ping", h_ping);
  server.begin();

  // "ready" IMEDIATO — Python pode mandar comandos já
  Serial.println("ready");
}

// ---------- loop ----------
void loop() {
  // Reporta IP quando WiFi conectar (sem travar)
  if (!wifi_reported && WiFi.status() == WL_CONNECTED) {
    Serial.print("IP: ");
    Serial.println(WiFi.localIP());
    wifi_reported = true;
    digitalWrite(LED_PIN, LOW);       // LED aceso = WiFi OK
  }
  if (WiFi.status() != WL_CONNECTED) {
    wifi_reported = false;
    digitalWrite(LED_PIN, HIGH);
  }

  server.handleClient();

  // ---- Serial ----
  if (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    line.trim();
    if (line.startsWith("Z")) {
      move_mm(line.substring(1).toFloat());
      Serial.println("ok");
    } else if (line == "W") {
      waiting_idle = true;
    } else if (line == "?") {
      Serial.print("pos=");
      Serial.println(stepper.currentPosition() / steps_per_mm, 4);
    } else if (line == "$102?") {
      Serial.print("$102=");
      Serial.println(steps_per_mm, 4);
    } else if (line.startsWith("$102=")) {
      float v = line.substring(5).toFloat();
      if (v > 0.1f) { steps_per_mm = v; apply_config();
                      Serial.println("ok"); }
      else Serial.println("error:invalid");
    } else if (line == "$0") {
      stepper.setCurrentPosition(0);
      Serial.println("ok");
    } else if (line == "$I") {
      Serial.print("$I="); Serial.println(FW_VERSION);
    } else if (line == "PING") {
      Serial.println("PONG");
    } else if (line.length()) {
      Serial.println("error:unknown");
    }
  }

  if (stepper.distanceToGo() != 0) {
    stepper.run();
  } else if (waiting_idle) {
    waiting_idle = false;
    Serial.println("ok");
  }
}