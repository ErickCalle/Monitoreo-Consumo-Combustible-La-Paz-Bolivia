# ESP32-S3 (N16R8) — Consumo de gasolina por Speed-Density vía OBD2

Firmware PlatformIO/Arduino en C++ para ESP32-S3, FreeRTOS repartido en los
2 núcleos. Lee PIDs OBD2 por CAN (TWAI + SN65HVD230), calcula consumo por el
método **speed-density**, muestra todo en un OLED I2C, guarda un CSV en
microSD por SPI y sirve un dashboard web local (WiFi SoftAP) con datos en
vivo, gráficas e historial descargable.

## 1. Mapa de conexiones

Ver también la explicación dada en el chat. Resumen:

| Bus | Señal | GPIO ESP32-S3 |
|---|---|---|
| TWAI (CAN) | TX -> SN65HVD230 CTX | GPIO4 |
| TWAI (CAN) | RX <- SN65HVD230 CRX | GPIO5 |
| I2C | SDA -> OLED | GPIO8 |
| I2C | SCL -> OLED | GPIO9 |
| SPI (SD) | SCK | GPIO12 |
| SPI (SD) | MISO | GPIO13 |
| SPI (SD) | MOSI | GPIO11 |
| SPI (SD) | CS | GPIO10 |
| LED | CAN activo | GPIO15 |
| LED | Actividad SD | GPIO16 |
| LED | Servidor activo | GPIO17 |
| LED | Error | GPIO18 |
| Power-gate | MOSFET rail LEDs+OLED | GPIO6 |
| Power-gate | MOSFET rail microSD | GPIO7 |

**No usar GPIO 26-37** (flash/PSRAM octal internos del N16R8), ni 0/3/19/20/43-46
(strapping / USB nativo / consola UART0).

SN65HVD230: CANH/CANL al pin 6 y 14 del conector OBD2 (J1962). Alimentar a
3.3V. Dejar el jumper de terminación 120Ω abierto salvo que tengas problemas
de señal.

### Alimentación y "sin contacto" (deep sleep)

Rail 1 (ESP32-S3 + SN65HVD230) va cableada directo al pin 16 del OBD2
(12V constante) y nunca se corta -- el SN65 tiene que seguir vivo para que
el próximo ciclo de despertar pueda volver a preguntarle al bus. Rail 2
(LEDs+OLED, microSD) pasa por los dos MOSFET de arriba, controlados por el
propio ESP32-S3:

- **MOSFET recomendado: canal P, de alto lado** (corta el 3.3V que entra al
  periférico, no su GND) -- con un N-MOSFET de bajo lado el GND del OLED/SD
  puede quedar ligeramente flotante mientras conduce, y eso genera
  problemas de integridad de señal en buses referenciados a GND como I2C y
  SPI.
- Sin una línea de 12V conmutada del vehículo, la única forma de saber si
  "hay contacto" es preguntándole al bus CAN (la ECU responde en cuanto la
  llave pasa de apagado a accesorios/contacto, y dentro de segundos deja de
  responder cuando vuelve a apagarse). Sin respuesta durante
  `CONTACT_LOST_DEBOUNCE_CYCLES` ciclos seguidos -> el ESP32-S3 cierra el
  archivo de la SD, corta ambos MOSFET, y entra en **deep sleep** real
  (~10-25µA), despertando solo por temporizador
  (`DEEP_SLEEP_WAKE_INTERVAL_US`) para volver a preguntar.
- Al arrancar (o al despertar del deep sleep), `setup()` hace lo mismo antes
  de encender nada de la rail 2: si no hay contacto, vuelve a dormir sin
  siquiera montar la SD ni levantar el WiFi.

## 2. Compilar y flashear

Requiere [PlatformIO](https://platformio.org/) (CLI o extensión de VS Code).

Hay **un entorno de compilación por vehículo** (`platformio.ini`), no un
único firmware genérico: cada uno define un build flag
(`-DVEHICLE_VANETTE` / `-DVEHICLE_CHANGAN`) que selecciona en tiempo de
compilación la cilindrada real y la tabla VE correspondientes (ver el
bloque `#if VEHICLE_*` en `include/config.h` y `src/fuel_calc.cpp`). Si no
se indica ningún entorno, `pio run` compila `vanette` por defecto
(`default_envs` en `platformio.ini`).

```
pio run -e vanette -t upload    # Nissan Vanette
pio run -e changan -t upload    # Changan Honor
pio device monitor -b 115200
```

Si `board_build.partitions = partitions.csv` da error de tamaño, revisa que
tu `platform = espressif32` esté razonablemente actualizado (>= 6.x soporta
bien N16R8/octal PSRAM).

## 3. Calibración (importante)

El método speed-density **no mide** el aire, lo estima. Los dos parámetros
de calibración están condicionados por vehículo, no se editan a mano:

- `ENGINE_DISPLACEMENT_L` (`include/config.h`): cilindrada real de cada
  motor (Vanette 1,626\,L, Changan 1,298\,L, Tabla 4.4 de la tesis).
- Tabla `kVeTable` (`src/fuel_calc.cpp`): eficiencia volumétrica (%) por
  RPM. La del Vanette está calibrada con datos reales contra su PID 0x10
  (MAF) — ver `CODIGOS/calibrate_ve_table.py` y
  `CODIGOS/ve_curve_calibrator.py`. La del Changan sigue siendo la tabla
  genérica de literatura, porque ese vehículo no soporta el PID 0x10 y
  no admite el mismo método de calibración directa (ver "Caso sin MAF"
  en el Capítulo 3 de la tesis y `CODIGOS/ve_curve_calibrator_indirect.py`
  para la alternativa vía STFT/LTFT).
- `FUEL_AFR_STOICH` / `FUEL_DENSITY_G_PER_L`: casi no cambian para
  gasolina, pero están expuestos por si usas otro combustible; no están
  condicionados por vehículo.

## 4. PIDs OBD2 usados (Modo 01, un solo frame CAN, sin ISO-TP multiframe
porque ninguno de estos PIDs lo necesita)

| PID | Dato | Uso |
|---|---|---|
| 0x0C | RPM | speed-density |
| 0x0B | MAP (kPa) | speed-density |
| 0x0F | IAT (°C) | speed-density |
| 0x0D | Velocidad (km/h) | L/100km, distancia de viaje |
| 0x05 | Refrigerante (°C) | mostrado en pantalla/CSV |
| 0x04 | Carga calculada (%) | mostrado en pantalla/CSV |
| 0x06 / 0x07 | Fuel trim corto/largo (%) | corrige el AFR estimado |
| 0x33 | Presión barométrica (kPa) | solo validación, ver abajo |

Al arrancar se consulta `0x00` (PIDs soportados 01-20) para omitir los PIDs
que la ECU no implemente; si esa consulta falla se asume que todos están
soportados y cada PID individual maneja su propio timeout. El PID 0x33 cae
fuera de ese rango (0x21-0x40), así que su soporte se resuelve aparte con
un sondeo directo de una sola vez al arrancar (`queryBaroSupport()`).

### Presión barométrica (PID 0x33): por qué es solo un dato de validación

El cálculo speed-density ya usa la presión real y absoluta del colector
(MAP, PID 0x0B) en cada ciclo, así que la densidad del aire -- y por lo
tanto el consumo -- ya queda corregida por altitud sin necesitar ningún
factor adicional: a mariposa cerrada el MAP nunca puede superar la presión
atmosférica real, sea cual sea esta. Multiplicar además por un factor
`P_baro / P0` sería corregir la altitud dos veces sobre el mismo número.

Por eso `baro_kpa` (PID 0x33, o el modelo ISA evaluado en `SITE_ALTITUDE_M`
como respaldo si el vehículo no soporta el PID) se registra en el CSV y se
muestra en el panel web únicamente como dato de **validación**: con el
contacto puesto y el motor apagado, el MAP debería leer aproximadamente lo
mismo que `baro_kpa`, porque en ese estado no hay vacío de admisión. Ese
contraste (MAP en KOEO vs. `baro_kpa`) es la prueba real y barata de hacer
para confirmar que el sensor MAP está bien calibrado a la altitud de
operación -- no un paso que el firmware necesite ejecutar automáticamente.

## 5. Dashboard web

- SoftAP siempre activo: SSID `ESP32_OBD2` / password `obd2trip123`
  (cámbialos en `config.h`). IP típica: `192.168.4.1`.
- Opcionalmente se une también como cliente a tu WiFi si llenas
  `WIFI_STA_SSID`/`WIFI_STA_PASS` (solo para tener hora NTP real en el CSV).
- El HTML/JS del dashboard está embebido en el firmware (sin CDN externo)
  a propósito: el SoftAP no tiene internet, así que cualquier librería de
  gráficas externa no cargaría. El gráfico es un mini-renderer canvas propio.
- Endpoints: `/api/live`, `/ws` (WebSocket, push cada 500ms), `/api/files`,
  `/api/download?file=...`, `/api/chartdata?file=...&maxpoints=N`,
  `POST /api/reset`.

## 6. Notas de diseño / concurrencia

- `canObd2Task` arma cada ciclo de PIDs en una copia local ("scratch") y
  solo toca `g_vehicleData` (bajo `g_dataMutex`) en el paso final de
  fusión + `fuelCalcUpdate()`. Esto es intencional: evita que un ciclo de
  ~0.2-1.4s de polling CAN pise un cambio concurrente (p.ej. el botón
  "Reiniciar viaje" de la web) con una foto vieja de los datos.
- `/api/download` y `/api/chartdata` leen el archivo completo a RAM
  (`readFileToBuffer`, con preferencia por PSRAM) mientras sostienen
  `g_sdMutex`, y lo liberan **antes** de servir la respuesta o parsear el
  CSV — así una descarga lenta por WiFi no bloquea las escrituras del
  logger cada segundo. Los archivos de más de 4MB (`MAX_SD_READ_BYTES`)
  se rechazan en vez de arriesgar un fallo de asignación de memoria.
- La descarga usa `request->onDisconnect(...)` como red de seguridad para
  liberar el buffer si el cliente corta la conexión a medio camino
  (revisa que tu versión de ESPAsyncWebServer exponga ese método; el
  fork ESP32Async pineado en `platformio.ini` lo tiene).
- El LED de error solo muestra el **último** fallo (1=CAN, 2=SD, 3=OLED,
  4=WiFi); el detalle completo queda en el log Serial.
- La recuperación de bus-off (`handleBusRecoveryIfNeeded`) es no
  bloqueante: sondea el estado real del controlador TWAI en cada vuelta
  del bucle en vez de esperar un tiempo fijo, y reintenta `twai_start()`
  hasta que realmente tenga éxito.
- La tabla de VE es un punto de partida genérico, no un valor de fábrica
  del vehículo: sin calibrarla el consumo tendrá un error sistemático.
