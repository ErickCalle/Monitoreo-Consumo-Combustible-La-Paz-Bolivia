#!/usr/bin/env python3
"""
Benchmark ELM327 -- SOLO para llenar la columna "ELM327 (sesion separada)"
de la Tabla 4.6 del Capitulo 4.

Habla directo con el ELM327 por comandos AT (sin pasar por Car Scanner),
solicitando el PID 0x0C (RPM, igual que el benchmark del ESP32 en
can_bench_tool/) durante 5 minutos, con el motor del vehiculo en ralenti.

Requisitos:
    pip install pyserial

Antes de correr:
    1. Emparejar el ELM327 por Bluetooth en Windows (Configuracion >
       Dispositivos > Bluetooth y otros dispositivos > Agregar dispositivo).
    2. Anotar el puerto COM saliente asignado: Panel de control >
       Dispositivos e impresoras > click derecho en el ELM327 >
       Propiedades > pestana "Servicios" o "Hardware", o en el
       Administrador de dispositivos, bajo "Puertos (COM y LPT)".
    3. Cambiar PORT abajo por ese puerto (ej. "COM5").
"""
import time
import serial

PORT = "COM3"            # <-- cambiar al puerto COM real del ELM327
BAUDRATE = 38400          # tipico por Bluetooth SPP; si no conecta, probar 9600 o 115200
TEST_DURATION_S = 5 * 60
REQUEST_PERIOD_S = 0.1
RESPONSE_TIMEOUT_S = 0.15


def send_at(ser, cmd, wait=0.3):
    ser.reset_input_buffer()
    ser.write((cmd + "\r").encode())
    time.sleep(wait)
    return ser.read(ser.in_waiting or 1).decode(errors="ignore")


def main():
    ser = serial.Serial(PORT, BAUDRATE, timeout=RESPONSE_TIMEOUT_S)

    print("Inicializando ELM327...")
    print(send_at(ser, "ATZ", 1.0))    # reset
    print(send_at(ser, "ATE0"))        # eco apagado, respuestas mas limpias
    print(send_at(ser, "ATSP6"))       # forzar protocolo ISO 15765-4 CAN, 11 bit / 500 kbps
    print(send_at(ser, "0100"))        # primer PID de descubrimiento, "despierta" el bus

    requests_sent = 0
    responses_ok = 0
    error_frames = 0
    latencies = []

    print(f"\nIniciando benchmark de {TEST_DURATION_S // 60} minutos (PID 0x0C, RPM)...")
    start = time.time()
    last_print = start

    while time.time() - start < TEST_DURATION_S:
        t0 = time.time()
        ser.reset_input_buffer()
        ser.write(b"010C\r")
        requests_sent += 1

        resp = ser.read(64).decode(errors="ignore")
        elapsed = time.time() - t0
        resp_clean = resp.replace("\r", " ").replace(">", " ").upper()

        if "NO DATA" in resp_clean or "ERROR" in resp_clean or "BUS" in resp_clean:
            error_frames += 1
        elif "41 0C" in resp_clean:
            responses_ok += 1
            latencies.append(elapsed)
        # cualquier otra cosa (respuesta vacia, timeout de pyserial) se
        # cuenta como solicitud sin respuesta, ni exito ni error de bus

        if time.time() - last_print > 30:
            last_print = time.time()
            print(f"...{int(time.time() - start)} s | "
                  f"solicitudes={requests_sent} respuestas={responses_ok} "
                  f"errores={error_frames}")

        sleep_left = REQUEST_PERIOD_S - elapsed
        if sleep_left > 0:
            time.sleep(sleep_left)

    avg_latency_ms = (sum(latencies) / len(latencies) * 1000) if latencies else 0.0

    print("\n================================================")
    print("RESULTADO -- Tabla 4.6, columna ELM327 (sesion separada)")
    print("================================================")
    print(f"Solicitudes enviadas:        {requests_sent}")
    print(f"Tramas recibidas en 5 min:    {responses_ok}")
    print(f"Tramas con error/NO DATA:      {error_frames}")
    print(f"Latencia promedio (ms):      {avg_latency_ms:.1f}")
    print("================================================")

    ser.close()


if __name__ == "__main__":
    main()
