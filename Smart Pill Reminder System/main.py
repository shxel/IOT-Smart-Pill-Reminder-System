import uasyncio as asyncio
from machine import Pin, Timer, ADC
import network
import urequests as requests
import dht
import ujson
import utime
import gc
import sys
from umqtt.simple import MQTTClient
from ucollections import OrderedDict
import aiohttp
import os


CONFIG = {
    'WIFI_SSID': 'your_wifi_ssid',         # Replace with actual WiFi SSID
    'WIFI_PASS': 'your_wifi_password',     # Replace with actual WiFi password
    'API_KEYS': {
        'openweather': 'your_openweathermap_api_key',  
        'timezone': 'your_timezoneapi_key'             
    },
    'CITY': 'London',
    'TIMEZONE': 'Europe/London',
    'HARDWARE': {
        'LIGHT_PIN': 2,
        'DHT_PIN': 4,
        'STATUS_LED': 5,
        'POWER_PIN': 34,
        'BUZZER_PIN': 15,      
        'SHUNT_RESISTOR': 0.1, 
        'SUPPLY_VOLTAGE': 3.3  
    },
    'SECURITY_TOKEN': 'your_secret_token',  # Replace with actual security token
    'SENSOR_CALIBRATION': {
        'temp_offset': 0.5,
        'humidity_offset': 2.0
    },
    'MQTT_BROKER': 'mqtt_broker_ip',  # Replace with actual MQTT broker IP
    'MQTT_TOPIC': 'smartpill/status'
}

def load_config():
    """Attempt to load external configuration from config.json."""
    config_path = "config.json"
    try:
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                config_data = ujson.load(f)
            # Merge external config with the default CONFIG
            for key in config_data:
                CONFIG[key] = config_data[key]
            print("External configuration loaded.")
    except Exception as e:
        print("Failed to load external config, using defaults.", e)

class SmartDevice:
    def __init__(self):
        self.status = OrderedDict([
            ('temperature', None),
            ('humidity', None),
            ('weather', None),
            ('internet_speed', None),
            ('light_state', False),
            ('uptime', 0),
            ('memory_free', 0),
            ('power_consumption', 0),
            ('reminders', []),
            ('last_update', None)
        ])
        self.pill_times = []  # Pill reminder times (as "HH:MM" strings)
        self.sensor = dht.DHT22(Pin(CONFIG['HARDWARE']['DHT_PIN']))
        self.light = Pin(CONFIG['HARDWARE']['LIGHT_PIN'], Pin.OUT)
        self.status_led = Pin(CONFIG['HARDWARE']['STATUS_LED'], Pin.OUT)
        self.power_adc = ADC(Pin(CONFIG['HARDWARE']['POWER_PIN']))
        self.power_adc.atten(ADC.ATTN_11DB)
        self.buzzer = Pin(CONFIG['HARDWARE']['BUZZER_PIN'], Pin.OUT)
        self.wifi = network.WLAN(network.STA_IF)
        self.mqtt_client = MQTTClient("esp32", CONFIG['MQTT_BROKER'])
        try:
            self.mqtt_client.connect()
        except Exception as e:
            print("Initial MQTT connection failed:", e)
        self.start_time = utime.time()
        self.sensor_readings = []  # For smoothing sensor data

    async def connect_wifi(self):
        max_retries = 5
        for attempt in range(max_retries):
            try:
                if not self.wifi.isconnected():
                    self.wifi.active(True)
                    self.wifi.connect(CONFIG['WIFI_SSID'], CONFIG['WIFI_PASS'])
                    await asyncio.sleep(5)
                if self.wifi.isconnected():
                    print(f"Connected to {CONFIG['WIFI_SSID']}")
                    return True
            except Exception as e:
                print(f"WiFi connection failed (attempt {attempt+1}): {e}")
                await asyncio.sleep(10)
        print("Failed to connect to WiFi, switching to AP mode")
        # Optionally notify the user via LED or other means
        self.wifi.active(False)
        self.wifi.active(True)
        self.wifi.config(essid='SmartPill_AP', password='smartpill123')
        return False

    async def read_sensor(self, measurement):
        try:
            self.sensor.measure()
            temp = self.sensor.temperature() + CONFIG['SENSOR_CALIBRATION']['temp_offset']
            hum = self.sensor.humidity() + CONFIG['SENSOR_CALIBRATION']['humidity_offset']

            # Validate sensor readings
            if not (-40 <= temp <= 80):
                print("Temperature reading out of range:", temp)
                return None
            if not (0 <= hum <= 100):
                print("Humidity reading out of range:", hum)
                return None

            # Store last 5 readings for smoothing
            self.sensor_readings = (self.sensor_readings + [(temp, hum)])[-5:]
            if measurement == 'temperature':
                return sum(t for t, _ in self.sensor_readings) / len(self.sensor_readings)
            elif measurement == 'humidity':
                return sum(h for _, h in self.sensor_readings) / len(self.sensor_readings)
        except Exception as e:
            print(f"Sensor error: {e}")
            return None

    async def monitor_power(self):
        while True:
            try:
                raw_value = self.power_adc.read()
                voltage = raw_value * CONFIG['HARDWARE']['SUPPLY_VOLTAGE'] / 4095
                current = voltage / CONFIG['HARDWARE']['SHUNT_RESISTOR']
                power = current * CONFIG['HARDWARE']['SUPPLY_VOLTAGE']
                self.status['power_consumption'] = power
            except Exception as e:
                print("Power monitoring error:", e)
            await asyncio.sleep(10)

    async def publish_status(self):
        while True:
            try:
                status = {
                    'temperature': self.status['temperature'],
                    'humidity': self.status['humidity'],
                    'light_state': self.status['light_state'],
                    'power_consumption': self.status['power_consumption']
                }
                # Retry mechanism for publishing
                retries = 0
                delay = 1
                while retries < 5:
                    try:
                        self.mqtt_client.publish(CONFIG['MQTT_TOPIC'], ujson.dumps(status))
                        break
                    except Exception as e:
                        print("Publish error:", e)
                        await asyncio.sleep(delay)
                        delay *= 2
                        retries += 1
            except Exception as e:
                print("Error in publish_status:", e)
            await asyncio.sleep(10)

    async def weather_monitor(self):
        while True:
            try:
                async with aiohttp.ClientSession() as session:
                    url = ("http://api.openweathermap.org/data/2.5/weather?q="
                           f"{CONFIG['CITY']}&appid={CONFIG['API_KEYS']['openweather']}")
                    async with session.get(url) as response:
                        if response.status == 200:
                            weather_data = await response.json()
                            self.status['weather'] = weather_data['weather'][0]['description']
                        else:
                            print("Weather API returned status:", response.status)
            except Exception as e:
                print(f"Weather monitor error: {e}")
            await asyncio.sleep(3600)  # Update weather every hour

    async def pill_reminder(self):
        while True:
            try:
                # Only proceed if pill times are set
                if self.pill_times:
                    current_time = utime.localtime()
                    current_time_str = f"{current_time[3]:02d}:{current_time[4]:02d}"
                    if current_time_str in self.pill_times:
                        print("Time to take your pill!")
                        self.buzzer.on()
                        await asyncio.sleep(5)  # Buzzer on for 5 seconds
                        self.buzzer.off()
                        # Log reminder event if desired
                await asyncio.sleep(60)  # Check every minute
            except Exception as e:
                print("Pill reminder error:", e)
                await asyncio.sleep(60)

    async def system_monitor(self):
        while True:
            self.status['uptime'] = utime.time() - self.start_time
            mem_free = gc.mem_free()
            self.status['memory_free'] = mem_free
            if mem_free < 10000:
                print("Warning: Low memory, consider restarting device!")
            await asyncio.sleep(60)

    async def task_runner(self, measurement, interval):
        """Periodically update sensor measurements."""
        while True:
            value = await self.read_sensor(measurement)
            if value is not None:
                self.status[measurement] = value
            await asyncio.sleep(interval)

async def main():
    load_config()  # Attempt to load external configuration
    device = SmartDevice()
    if not await device.connect_wifi():
        print("Failed to connect to WiFi")
        sys.exit(1)

    # Create tasks for sensor reading, weather monitoring, pill reminders, etc.
    tasks = [
        device.task_runner('temperature', 10800),  # e.g., update every 3 hours
        device.task_runner('humidity', 43200),       # e.g., update every 12 hours
        device.weather_monitor(),
        device.pill_reminder(),
        device.system_monitor(),
        device.publish_status(),
        device.monitor_power()
    ]

    for task in tasks:
        asyncio.create_task(task)

    while True:
        await asyncio.sleep(1)
        gc.collect()

# Run the main async event loop
asyncio.run(main())
