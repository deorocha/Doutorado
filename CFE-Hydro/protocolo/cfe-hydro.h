#ifndef CFE_HYDRO_H
#define CFE_HYDRO_H

#include <Arduino.h>
#include <ArduinoJson.h>
// #define MQTT_MAX_PACKET_SIZE 2048
#include <PubSubClient.h>

#ifdef ESP32
  #include <WiFi.h>
#else
  #include <ESP8266WiFi.h>
#endif

class CFEHydro {
public:
    struct SensorConfig {
        const char* type;
        const char* unit;
        const char* description;
        float optimal_min;
        float optimal_max;
        const char* interpolation; // "linear", "logarithmic", "polynomial", "sigmoidal"
        float value;               // leitura atual
    };

    // Construtor para configuração dinâmica (sensores adicionados via addSensor)
    CFEHydro(const char* device_id, int sampling_interval, int transmission_interval)
        : _sampling_interval(sampling_interval), _transmission_interval(transmission_interval),
          _sensors(nullptr), _num_sensors(0), _max_sensors(0), _dynamic(true) {
        _device_id = strdup(device_id);
        _timestamp[0] = '\0';
    }

    // Construtor com array estático de sensores (apenas configuração, valores podem ser atualizados)
    CFEHydro(const char* device_id, int sampling_interval, int transmission_interval,
             SensorConfig* sensors, int num_sensors)
        : _sampling_interval(sampling_interval), _transmission_interval(transmission_interval),
          _sensors(sensors), _num_sensors(num_sensors), _max_sensors(num_sensors), _dynamic(false) {
        _device_id = strdup(device_id);
        _timestamp[0] = '\0';
    }

    // Destrutor libera memória alocada
    ~CFEHydro() {
        free(_device_id);
        if (_dynamic && _sensors != nullptr) {
            // Libera strings internas e o array
            for (int i = 0; i < _num_sensors; i++) {
                free((void*)_sensors[i].type);
                free((void*)_sensors[i].unit);
                free((void*)_sensors[i].description);
                free((void*)_sensors[i].interpolation);
            }
            free(_sensors);
        }
    }

    // Adiciona um novo sensor (apenas modo dinâmico)
    int addSensor(const char* type, const char* unit, const char* description,
                  float optimal_min, float optimal_max, const char* interpolation = "linear") {
        if (!_dynamic) return -1; // não permitido em modo estático

        int new_count = _num_sensors + 1;
        SensorConfig* new_sensors = (SensorConfig*)realloc(_sensors, new_count * sizeof(SensorConfig));
        if (!new_sensors) return -1;

        _sensors = new_sensors;
        _max_sensors = new_count;
        SensorConfig& s = _sensors[_num_sensors];
        s.type = strdup(type);
        s.unit = strdup(unit);
        s.description = strdup(description);
        s.optimal_min = optimal_min;
        s.optimal_max = optimal_max;
        s.interpolation = strdup(interpolation);
        s.value = 0.0f;
        _num_sensors = new_count;
        return _num_sensors - 1;
    }

    // Atualiza o valor de um sensor pelo nome
    bool updateSensor(const char* type, float value) {
        for (int i = 0; i < _num_sensors; i++) {
            if (strcmp(_sensors[i].type, type) == 0) {
                _sensors[i].value = value;
                return true;
            }
        }
        return false;
    }

    // Atualiza o valor pelo índice
    bool updateSensor(int index, float value) {
        if (index >= 0 && index < _num_sensors) {
            _sensors[index].value = value;
            return true;
        }
        return false;
    }

    // Define o timestamp manualmente (se não chamado, será enviado como "unknown")
    void setTimestamp(const char* timestamp) {
        strncpy(_timestamp, timestamp, sizeof(_timestamp) - 1);
        _timestamp[sizeof(_timestamp) - 1] = '\0';
    }

    // Envia os dados via MQTT
    bool send(PubSubClient& mqttClient, const char* topic) {
        // Estima capacidade do JSON (ajuste conforme necessidade)
        size_t capacity = 512 + _num_sensors * 128;
        DynamicJsonDocument doc(capacity);
        buildJson(doc);

        String output;
        serializeJson(doc, output);
        return mqttClient.publish(topic, output.c_str());
    }

private:
    char* _device_id;
    int _sampling_interval;
    int _transmission_interval;
    SensorConfig* _sensors;
    int _num_sensors;
    int _max_sensors;
    bool _dynamic;
    char _timestamp[25]; // buffer para "YYYY-mm-dd HH:MM:SS.999"

    // Constrói o documento JSON
    void buildJson(JsonDocument& doc) {
        doc["device_id"] = _device_id;
        doc["transmission_timestamp"] = (_timestamp[0] != '\0') ? _timestamp : "unknown";
        doc["sampling_interval"] = _sampling_interval;
        doc["transmission_interval"] = _transmission_interval;

        JsonArray readings = doc.createNestedArray("readings");
        for (int i = 0; i < _num_sensors; i++) {
            JsonObject r = readings.createNestedObject();
            r["sensor_type"] = _sensors[i].type;
            r["value"] = _sensors[i].value;
            r["interpolation"] = _sensors[i].interpolation;
            JsonObject meta = r.createNestedObject("metadata");
            meta["unit"] = _sensors[i].unit;
            meta["description"] = _sensors[i].description;
            meta["optimal_min"] = _sensors[i].optimal_min;
            meta["optimal_max"] = _sensors[i].optimal_max;
        }

        JsonObject system = doc.createNestedObject("system");
#ifdef ESP32
        system["free_heap"] = ESP.getFreeHeap();
        system["wifi_rssi"] = WiFi.RSSI();
#else
        system["free_heap"] = 0;
        system["wifi_rssi"] = 0;
#endif
        system["uptime"] = millis() / 1000;
    }
};

#endif