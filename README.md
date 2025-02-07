# Smart Pill Reminder System

The **Smart Pill Reminder System** is an IoT-based solution designed to help users remember to take their medication on time. It consists of two main components:

- **Desktop GUI Application (`gui_app.py`)**
- **Device Firmware (`main.py`)**

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Hardware Requirements](#hardware-requirements)
  - [Device (ESP32-based)](#device-esp32-based)
  - [Desktop Application](#desktop-application)
- [Wiring Diagram](#wiring-diagram)
- [Setup and Installation](#setup-and-installation)
  - [Desktop GUI Application](#desktop-gui-application)
  - [Device Firmware](#device-firmware)
- [Running the System](#running-the-system)
- [Troubleshooting](#troubleshooting)
- [License](#license)
- [Contributing](#contributing)
- [Acknowledgments](#acknowledgments)

---

## Overview

The project consists of two primary modules:

### **1. Desktop GUI Application (`gui_app.py`)**

- **Purpose:**  
  Provides a user-friendly interface to monitor device status, view event history, set pill reminders, and control device functions.
  
- **Key Functionalities:**  
  - Display sensor data (temperature, humidity, light status, power consumption, uptime, etc.)
  - Log events in a local SQLite database.
  - Use a machine learning model (Linear Regression) to predict upcoming temperature values.
  - Control pill reminders, light toggling, device reboot, and firmware updates.
  - Communicate with the device using **MQTT**.

### **2. Device Firmware (`main.py`)**

- **Purpose:**  
  Runs on an ESP32 (or similar) microcontroller to handle sensor readings, network communication, and pill reminders.
  
- **Key Functionalities:**  
  - Connect to WiFi with retry logic and fallback to AP mode if needed.
  - Read data from a **DHT22 sensor** (temperature and humidity).
  - Monitor power consumption using an ADC.
  - Fetch weather updates using the OpenWeather API.
  - Publish device status via **MQTT**.
  - Activate a buzzer for pill reminders at scheduled times.
  - Perform system monitoring (uptime, free memory).

---

## Features

- **MQTT Communication:**  
  Real-time device status updates and commands.
  
- **Sensor Data Acquisition:**  
  Collects and logs data from sensors, storing it in an SQLite database.
  
- **Machine Learning:**  
  Predicts the next temperature value based on historical sensor data using Linear Regression.
  
- **Pill Reminders:**  
  Schedules and triggers pill reminders with visual and audible alerts.
  
- **Robust Error Handling:**  
  Implements retry mechanisms, exponential backoff, and exception handling.
  
- **Configuration Management:**  
  Settings can be adjusted via a `config.json` file or environment variables.

---

## Hardware Requirements

### Device (ESP32-based)

- **ESP32 Microcontroller:**  
  - Must be capable of running MicroPython.
  
- **DHT22 Sensor:**  
  - **VCC:** Connect to 3.3V  
  - **GND:** Connect to Ground  
  - **Data:** Connect to designated GPIO (default: **GPIO4** as per `main.py`)
  
- **Power Monitoring Circuit:**  
  - Uses an ADC pin (default: **GPIO34**) with a shunt resistor (default value: **0.1 ohm**).  
  - Use a voltage divider if necessary.
  
- **Status LED:**  
  - Connect an LED (with an appropriate resistor) to a digital pin (default: **GPIO5**).
  
- **Buzzer (for Pill Reminders):**  
  - Connect the buzzer to a digital output pin (default: **GPIO15**).  
  - A transistor may be required if the buzzer draws more current than the ESP32 pin can supply.
  
- **Optional – External Light Control:**  
  - Use a relay or transistor circuit connected to a digital pin (default: **GPIO2**).

### Desktop Application

- **Computer with Python 3 installed**
- **Required Python Libraries:**  
  - `tkinter` (usually included with Python)  
  - `paho-mqtt`  
  - `pandas`  
  - `scikit-learn`  
  - `sqlite3` (bundled with Python)  
  - `requests`  
  - Additional standard libraries: `json`, `os`, `threading`, etc.

---

## Wiring Diagram

Below is a simple wiring guide for the device:

    +-----------------------+
    |       ESP32           |
    |                       |
    |  3.3V  ----------> VCC (DHT22)
    |  GND   ----------> GND (DHT22)
    |  GPIO4 ----------> Data (DHT22)
    |                       |
    |  GPIO34 --------> ADC Input (Power Monitoring)
    |                       |
    |  GPIO5  --------> LED (Status Indicator)
    |                       |
    |  GPIO15 --------> Buzzer (Pill Reminder)
    |                       |
    |  GPIO2  --------> Relay/Transistor (External Light Control)
    +-----------------------+

**Note:**  
Always verify voltage requirements and use appropriate resistors or level shifters as needed.

---

## Setup and Installation

### Desktop GUI Application (`gui_app.py`)

#### **Dependencies**

Install the required Python libraries:
```bash
pip install paho-mqtt pandas scikit-learn
Configuration
Create a config.json file (optional) in the same directory to override default settings.
Example config.json:
json
{
    "esp_ip": "192.168.1.100",
    "security_token": "your_secret_token",
    "update_interval": 5,
    "mqtt_broker": "mqtt_broker_ip",
    "mqtt_topic": "smartpill/status",
    "db_file": "smartpill.db"
}
Running the Application
To run the desktop application:

bash
python gui_app.py
This command launches the GUI where you can monitor device status, set pill reminders, and view the event history.

Device Firmware (main.py)
Flashing MicroPython
Ensure your ESP32 board has MicroPython installed.
Use tools such as ampy, rshell, or Thonny to upload files.
Configuration
Update the CONFIG dictionary in main.py with:
Your WiFi SSID and password.
MQTT broker details.
API keys for weather monitoring.
Correct hardware pin assignments.
Optionally, external configuration can be loaded if supported by your setup.
Upload and Run
Upload main.py to your ESP32 board.
Reset the board.
Once running, the device will:

Connect to your WiFi network (or switch to AP mode if the connection fails).
Begin collecting sensor data.
Publish status updates via MQTT.
Monitor weather data.
Check for pill reminder times and activate the buzzer as scheduled.
Running the System
Desktop Side:
Run the GUI application (gui_app.py) to visualize the device status and interact with the system.

Device Side:
Once the ESP32 is powered and running main.py, it will handle sensor monitoring, data acquisition, and reminders. Use the serial console for debugging if necessary.

Troubleshooting
MQTT Connection Issues:
Verify the MQTT broker address and ensure that the broker is running.

WiFi Connectivity (Device):
Double-check WiFi credentials in main.py. The device will switch to AP mode if it cannot connect.

Sensor Errors:
Confirm that the DHT22 sensor is properly connected and that wiring matches the pin assignments.

Database Issues (GUI):
Ensure that the application has write permissions in the directory where smartpill.db is created.

Low Memory (Device):
The system monitor in main.py logs warnings if free memory is low. Consider restarting the device if this occurs frequently.

License
This project is licensed under the MIT License.

Contributing
Contributions and suggestions are welcome. Feel free to open an issue or submit a pull request.

Acknowledgments
Thanks to the communities behind Paho-MQTT, Tkinter, Pandas, and Scikit-Learn.
Special thanks to the developers and contributors of MicroPython.
**MOhammad Amin Zakouri**
