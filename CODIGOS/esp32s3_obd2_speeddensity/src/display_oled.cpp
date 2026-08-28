#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include "config.h"
#include "types.h"
#include "display_oled.h"

static Adafruit_SSD1306 display(OLED_WIDTH, OLED_HEIGHT, &Wire, OLED_RESET_PIN);
static bool s_ready = false;

bool displayInit() {
  Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL);
  if (!display.begin(SSD1306_SWITCHCAPVCC, OLED_I2C_ADDR)) {
    systemReportError(ErrorCode::OLED_FAIL);
    s_ready = false;
    return false;
  }
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(1);
  display.setCursor(0, 0);
  display.println("ESP32 OBD2");
  display.println("Iniciando...");
  display.display();
  s_ready = true;
  return true;
}

static void drawFrame(const VehicleData &vd, bool serverActive) {
  display.clearDisplay();

  display.setTextSize(1);
  display.setCursor(0, 0);
  display.printf("RPM:%4u %3.0fkm/h\n", (unsigned)vd.rpm, vd.speed_kmh);

  // Consumo instantaneo (arriba) y costo acumulado del viaje en Bs (abajo),
  // ambos en grande -- son los datos que mas se consultan al manejar. El
  // costo sale de los litros ya consumidos (vd.trip_fuel_L), no de la tasa
  // instantanea, para que refleje lo gastado real hasta ahora.
  bool moving = vd.speed_kmh > 2.0f;
  float instantValue = moving ? vd.instant_L100km : vd.instant_Lh;
  double tripCostBs = vd.trip_fuel_L * FUEL_PRICE_BS_PER_L;

  display.setTextSize(2);
  display.setCursor(0, 10);
  if (moving) {
    display.printf("%4.1f/100\n", instantValue);
  } else {
    display.printf("%4.1fL/h\n", instantValue);
  }

  display.setCursor(0, 28);
  display.printf("%5.1fBs\n", tripCostBs);

  display.setTextSize(1);
  display.setCursor(0, 46);
  display.printf("Trip:%5.1fkm %4.2fL\n", vd.trip_distance_km, vd.trip_fuel_L);

  display.setCursor(0, 56);
  display.print(vd.can_status == CanStatus::OK ? "CAN:OK " : "CAN:-- ");
  display.print(serverActive ? WIFI_AP_IP_HINT : "srv:--");

  display.display();
}

void displayTask(void *pvParameters) {
  (void)pvParameters;
  for (;;) {
    // No per-frame idle logic needed anymore: with "sin contacto" the OLED
    // loses power at the MOSFET (power_sleep.cpp), and this task is not
    // even running then -- the whole chip is in deep sleep.
    if (s_ready) {
      VehicleData vd;
      if (xSemaphoreTake(g_dataMutex, pdMS_TO_TICKS(50)) == pdTRUE) {
        vd = g_vehicleData;
        xSemaphoreGive(g_dataMutex);
      }
      drawFrame(vd, g_systemStatus.server_active);
    }
    vTaskDelay(pdMS_TO_TICKS(OLED_REFRESH_PERIOD_MS));
  }
}
