/*
   Autor : André Luiz Rocha
   PID   : cfe-hydro_publisher.ino
   Placa : ESP32 Dev Module
   Função: Enviar dados sensoriados para o broker MQTT
           usando protocolo cfe-hydro.h
   Versão: 1.02
   Date  : 25/02/2026 - 19:35h
   L.U.  : 27/02/2026 - 16:15h
   Referências:
      - WifiManager : https://github.com/tzapu/WiFiManager
      - PubSubClient: https://github.com/knolleary/pubsubclient
      - NTPClient   : https://github.com/arduino-libraries/NTPClient
      - CFE-Hydro   : https://github.com/bps90/cfe-hydro
   Pendências:
      - 
*/

// IMPORTA BIBLIOTECAS ========================================
#include <WiFiManager.h>
#include "cfe-hydro.h"
#include <WiFiUdp.h>
#include <NTPClient.h>
#include <ArduinoSort.h>
#include <LiquidCrystal_I2C.h>

// Configurações de rede e MQTT -------------------------------
const char* mqtt_server = "test.mosquitto.org"; // "BROKER_EXEMPLO.com";
const int mqtt_port = 1883;
const char* mqtt_topic = "cfe-hydro/data";

// DEFINE VARIÁVEIS ===========================================
int lcdColumns = 20;
int lcdRows = 4;
const int intervalo = 60000; // 1 min.
unsigned long ultimoEnvio = millis(); // 0;
String timestamp;
bool wifi_connected = false;

float tp_value = 0.00;
const float tp_coef   = 12.9851;
const float tp_offSet = 0.00;

float ec_value = 0.00;
const float ec_coef   = 0.9756;
const float ec_offSet = 0.00;

float ph_value = 0.00;
const float ph_coef   = 6.3529;
const float ph_offSet = 0.00;

float od_value = 0.00;
const float od_coef   = 1.9355;
const float od_offSet = 0.00;

// INSTANCIA FUNÇÕES ===========================================
void connect_WiFi();
void connect_MQTT();
float readAnalogAverage(int);
void initSensors();
float Get_TP();
float Get_EC();
float Get_PH();
float Get_OD();
void LcdMsg(int, int, String);
void Exibe_Valores_Serial();
void Exibe_Valores_LCD();
String formatTimestamp();

// INSTANCIA OBJETOS ===========================================
LiquidCrystal_I2C lcd(0x27, lcdColumns, lcdRows); 

// DEFINE PINOS ================================================
#define TP_SENSOR_PIN 34
#define EC_SENSOR_PIN 35
#define PH_SENSOR_PIN 32
#define OD_SENSOR_PIN 33
#define STATUS_LED 2

// ADC Configuration
#define ADC_RESOLUTION 4095.0
#define VREF 3.3 // 5.0 // 3.3
#define ADC_SAMPLES 50 // Deve ser > 10 amostras
float myArray[ADC_SAMPLES];

WiFiClient espClient;
PubSubClient mqttClient(espClient);

// NTP
WiFiUDP ntpUDP;
NTPClient timeClient(ntpUDP, "pool.ntp.org", -10800, 60000); // UTC-3 (Brasília): -3 * 3600 = -10800

// CONFIGURAÇÃO DOS SENSORES UTILIZADOS ====================================
CFEHydro::SensorConfig sensores[] = {
   {"temperatura", "°C", "Temperatura", 18.0, 30.0, "linear"},
   {"ph", "pH", "Nível de pH", 5.5, 7.0, "logarithmic"},
   {"ec", "mS/cm", "EC", 0.0, 5.0, "polynomial"},
   {"od", "mg/L", "OD", 0.0, 6.0, "polynomial"}
   // Configurar todos os campos usados aqui.
};
int numSensores = sizeof(sensores) / sizeof(sensores[0]);

// Instância do protocolo
CFEHydro hydro("dispositivo_001", 10, 60, sensores, numSensores);

void setup() {
   Serial.begin(115200);

   lcd.init();
   lcd.backlight();
   lcd.clear();
   LcdMsg(0, 0, "Procolo CFE-Hydro");

   Serial.println("\n=== SISTEMA CFE-HYDRO ===");
   Serial.println("Inicializando...");
   LcdMsg(0, 1, "Inicializando...");

   pinMode(STATUS_LED, OUTPUT);
   digitalWrite(STATUS_LED, LOW);

   initSensors();

   connect_WiFi();

   if (wifi_connected) {
      mqttClient.setServer(mqtt_server, mqtt_port);
      mqttClient.setBufferSize(3072);
   }

   timeClient.begin();

   Serial.println("Setup completo.\n");
   lcd.clear();
   LcdMsg(0, 0, "Setup completo.     ");
   delay(500);
   LcdMsg(0, 1, "Lendo sensores...   ");
} // end setup()

void loop() {
   unsigned long currentMillis = millis();
   if (currentMillis - ultimoEnvio >= intervalo) {
      ultimoEnvio = currentMillis;

      // Leitura dos sensores
      timestamp = formatTimestamp();
      tp_value = Get_TP();
      ph_value = Get_PH();
      ec_value = Get_EC();
      od_value = Get_OD();

      // Exibe valores lidos
      Exibe_Valores_Serial();
      Exibe_Valores_LCD();
      
      // Atualiza os valores no objeto
      hydro.updateSensor("temperatura", tp_value);
      hydro.updateSensor("ph", ph_value);
      hydro.updateSensor("ec", ec_value);
      hydro.updateSensor("od", od_value);
      hydro.setTimestamp(timestamp.c_str());

      // Mantém conexão MQTT
      if (wifi_connected) {
         if (!mqttClient.connected()) {
            connect_MQTT();
         }
         mqttClient.loop();
      }

      // Envia os dados para o Broker
      if (!hydro.send(mqttClient, mqtt_topic)) {
         Serial.println("Falha no envio");
         lcd.clear();
         LcdMsg(0, 0, "Falha no envio.     ");
      } else {
         // Serial.println("Dados enviados com sucesso");
      }
   }
} // end loop()

// Conecta ao WiFi
void connect_WiFi() {
   WiFiManager wm;
   // wm.resetSettings();
   bool res;
   res = wm.autoConnect("CFE-Hydro");
   //lcd.clear();
   LcdMsg(0, 2, "Conectando ao WiFi..");
   if(!res) {
      // wm.resetSettings();
      Serial.println("Falha ao conectar ao WiFi.");
      LcdMsg(0, 3, "Falha conexao WiFi. ");
      ESP.restart();
      wifi_connected = false;
   }
   else {
      Serial.println("Conectado ao Wifi!");
      LcdMsg(0, 3, "Conectado ao Wifi!  ");
      Serial.print(WiFi.SSID());  
      Serial.print("  IP: ");
      Serial.println(WiFi.localIP()); 
      wifi_connected = true;
   }
} // end connect_WiFi()

// Conecta com o Broker MQTT
void connect_MQTT() {
   while (!mqttClient.connected()) {
      Serial.print("Conectando ao MQTT...");
      // LcdMsg(0, 2, "Conectando ao MQTT..");
      String clientId = "CFE-HYDRO-";
      clientId += String(random(0xFFFF), HEX);
      
      if (mqttClient.connect(clientId.c_str())) {
         Serial.println("conectado!");
         // LcdMsg(0, 3, "MQTT Conectado!     ");
         digitalWrite(STATUS_LED, HIGH);
      } else {
         Serial.print("falhou, rc=");
         // LcdMsg(0, 3, "Falha conexao MQTT. ");
         Serial.print(mqttClient.state());
         Serial.println(" tentando novamente em 5 segundos");
         digitalWrite(STATUS_LED, LOW);
         delay(5000);
      }
   }
} // end connect_MQTT()

// Inicializa sensores
void initSensors() {
    Serial.println("Inicializando sensores...");
    lcd.clear();
    LcdMsg(0, 0, "Inicializ. sensores.");
    
    pinMode(TP_SENSOR_PIN, INPUT);
    pinMode(PH_SENSOR_PIN, INPUT);
    pinMode(EC_SENSOR_PIN, INPUT);
    pinMode(OD_SENSOR_PIN, INPUT);
    
    analogReadResolution(12);
    analogSetAttenuation(ADC_11db);
    
    Serial.println("Sensores inicializados.");
    LcdMsg(0, 1, "Sensores OK.");
    delay(1000);
} // end initSensors()

float readAnalogAverage(int pin) {
   memset(myArray, 0, sizeof(myArray));      // Limpa array
   for (int i = 0; i < ADC_SAMPLES; i++) {   // Leitura dos valores
      myArray[i] = analogRead(pin);
      delay(2);
   }
   
   sortArray(myArray, ADC_SAMPLES);          // Ordena array
   float sum = 0.00; // Exclui as 5 menores e 5 maiores leituras
   for (int i = 5; i < (ADC_SAMPLES-5); i++) {
      sum += myArray[i];
   }
   sum = (sum / (ADC_SAMPLES-10));  // Calcula média das leituras válidas
   float volts = (sum * VREF) / ADC_RESOLUTION; // Converte a média p/ tensão (volts)

   return volts;
}

float Get_TP() { // Lê sensor de Temperatura ------------------------------
   float volts = readAnalogAverage(TP_SENSOR_PIN);
   tp_value = (volts * tp_coef) + tp_offSet;
   tp_value = (tp_value < 0) ? 0 : tp_value;
   return tp_value;
} // end Get_Temp()

float Get_EC() { // Lê sensor de EC ---------------------------------------
   float volts = readAnalogAverage(EC_SENSOR_PIN);
   ec_value = (volts * ec_coef) + ec_offSet;
   ec_value = (ec_value < 0) ? 0 : ec_value;
   return ec_value;
} // end Get_EC()

float Get_PH() { // Lê sensor de pH ---------------------------------------
   float volts = readAnalogAverage(PH_SENSOR_PIN);
   ph_value = (volts * ph_coef) + ph_offSet;
   ph_value = (ph_value < 0) ? 0 : ph_value;
   return ph_value;
} // end Get_PH()

float Get_OD() { // Lê sensor de OD ---------------------------------------
   float volts = readAnalogAverage(OD_SENSOR_PIN);
   od_value = (volts * od_coef) + od_offSet;
   od_value = (od_value < 0) ? 0 : od_value;
   return od_value;
} // end Get_OD()

String formatTimestamp() { // Formata timestamp em string usando NTPClient
   timeClient.update();    // Atualizar o cliente NTPClient

   // Obter a data completa do NTPClient
   String formattedDate = timeClient.getFormattedDate();
   // O formato retornado é: "2026-02-06T22:48:00Z"

   // Extrair componentes
   String year = formattedDate.substring(0, 4);
   String month = formattedDate.substring(5, 7);
   String day = formattedDate.substring(8, 10);
   String hour = formattedDate.substring(11, 13);
   String minute = formattedDate.substring(14, 16);
   String second = formattedDate.substring(17, 19);
   unsigned long milliseconds = millis() % 1000;

   // Formata timestamp: "DD/MM/AAAA HH:MM:SS.mmm"
   String formatted = day + "/" + month + "/" + year + " " + 
                      hour + ":" + minute + ":" + second + ".";
        
   // Adicionar milissegundos com 3 dígitos
   if (milliseconds < 10) {
      formatted += "00";
   } else if (milliseconds < 100) {
      formatted += "0";
   }
   formatted += String(milliseconds);

   return formatted;
} // end formatTimestamp()

void LcdMsg(int x, int y, String msg) { // Exibe mensagens no display LCD
   lcd.setCursor(x, y);
   lcd.print(msg);
   delay(500);
} // end LcdMsg()

void Exibe_Valores_Serial() { // Mostra valores no Monitor Serial
   Serial.print("Timestamp: ");
   Serial.print(timestamp);
   Serial.print("  T: ");
   Serial.print(tp_value, 2);
   Serial.print("  pH: ");
   Serial.print(ph_value, 2);
   Serial.print("  EC: ");
   Serial.print(ec_value, 3);
   Serial.print("  OD: ");
   Serial.println(od_value, 2);
} // end Exibe_Valores_Serial()


void Exibe_Valores_LCD() {    // Mostra valores no display LCD
   lcd.clear();
   lcd.setCursor(0, 0);
   lcd.print("T : ");
   lcd.print(tp_value,2);
   lcd.print(" \337C");
   lcd.setCursor(0, 1);
   lcd.print("pH: ");
   lcd.print(ph_value,2);
   lcd.setCursor(0, 2);
   lcd.print("EC: ");
   lcd.print(ec_value,3);
   lcd.print(" mS/cm");
   lcd.setCursor(0, 3);
   lcd.print("OD: ");
   lcd.print(od_value,2);
   lcd.print(" mg/L");
} // end Exibe_Valores_LCD()