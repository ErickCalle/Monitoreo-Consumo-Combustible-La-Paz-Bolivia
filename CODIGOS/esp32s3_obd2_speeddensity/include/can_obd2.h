#pragma once

// Initializes the TWAI (CAN) peripheral. Returns true on success.
// Must be called once from setup() BEFORE canObd2Task is started.
bool canObd2Init();

// Single lightweight ping: true if the ECU answers at all ("hay contacto"),
// false if the bus stays silent. Used both by the power-on gate in
// setup() and by canObd2Task itself to notice when contact is lost.
bool canObd2CheckContact();

// FreeRTOS task: cyclically requests the OBD2 PIDs needed for the
// speed-density fuel calculation, decodes responses into g_vehicleData
// (protected by g_dataMutex) and drives fuel_calc after each full cycle.
void canObd2Task(void *pvParameters);
