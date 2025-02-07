import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import requests
import threading
import time
from datetime import datetime
import paho.mqtt.client as mqtt
import sqlite3
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error
import json
import os
import atexit
import re

class EnhancedSmartPillApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Smart Pill Reminder Pro")
        
        # Event to signal threads to stop on exit
        self.stop_threads = threading.Event()

        # Load configuration from file or environment variables
        self.config = self.load_config()
        self.validate_config()

        # Setup UI Components
        self.create_status_panel()
        self.create_controls_panel()
        self.create_history_panel()
        self.create_menu()

        # Initialize MQTT
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_message = self.on_mqtt_message
        self.mqtt_client.on_disconnect = self.on_mqtt_disconnect
        self.connect_mqtt()

        # Initialize Database
        self.db_conn = sqlite3.connect(self.config['db_file'])
        self.create_db_tables()
        # Ensure database connection is closed on exit
        atexit.register(self.close_db)

        # Initialize ML Model
        self.model = None
        self.train_model()

        # Initialize pill times list
        self.pill_times = []

        # Start background threads
        self.start_update_thread()
        self.start_reminder_check()

        # Bind closing event to clean up threads
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def load_config(self):
        """Load configuration from a JSON file or environment variables."""
        config_path = "config.json"
        if os.path.exists(config_path):
            with open(config_path) as config_file:
                return json.load(config_file)
        else:
            return {
                'esp_ip': os.getenv('ESP_IP', "192.168.1.100"),
                'security_token': os.getenv('SECURITY_TOKEN', "your_secret_token"),
                'update_interval': int(os.getenv('UPDATE_INTERVAL', 5)),
                'mqtt_broker': os.getenv('MQTT_BROKER', "mqtt_broker_ip"),
                'mqtt_topic': os.getenv('MQTT_TOPIC', "smartpill/status"),
                'db_file': os.getenv('DB_FILE', "smartpill.db")
            }

    def validate_config(self):
        """Simple validation for configuration values."""
        broker = self.config.get('mqtt_broker', '')
        # Basic regex for IPv4 or hostname (very simple check)
        if not re.match(r"^(\d{1,3}\.){3}\d{1,3}$", broker) and not re.match(r"^[\w\.-]+$", broker):
            messagebox.showerror("Configuration Error", "Invalid MQTT broker address in configuration.")
            self.root.destroy()

    def connect_mqtt(self):
        """Connect to the MQTT broker with exponential backoff retry mechanism."""
        max_retries = 5
        delay = 1
        for attempt in range(max_retries):
            try:
                self.mqtt_client.connect(self.config['mqtt_broker'])
                self.mqtt_client.subscribe(self.config['mqtt_topic'])
                self.mqtt_client.loop_start()
                self.log_event("Connected to MQTT broker")
                return
            except Exception as e:
                self.log_event(f"MQTT Connection Error (attempt {attempt+1}): {e}")
                time.sleep(delay)
                delay *= 2
        messagebox.showerror("MQTT Error", "Unable to connect to MQTT broker after multiple attempts.")

    def on_mqtt_disconnect(self, client, userdata, rc):
        """Handle MQTT disconnection and attempt to reconnect with retry logic."""
        self.log_event("MQTT Disconnected, attempting to reconnect...")
        max_retries = 5
        delay = 1
        for attempt in range(max_retries):
            try:
                time.sleep(delay)
                self.mqtt_client.reconnect()
                self.log_event("Reconnected to MQTT broker")
                return
            except Exception as e:
                self.log_event(f"Reconnection attempt {attempt+1} failed: {e}")
                delay *= 2
        self.log_event("Failed to reconnect to MQTT broker after multiple attempts.")

    def create_status_panel(self):
        status_frame = ttk.LabelFrame(self.root, text="Device Status")
        status_frame.grid(row=0, column=0, padx=10, pady=10, sticky='nsew')

        self.status_labels = {
            'temperature': ttk.Label(status_frame, text="Temperature: --°C"),
            'humidity': ttk.Label(status_frame, text="Humidity: --%"),
            'weather': ttk.Label(status_frame, text="Weather: --"),
            'speed': ttk.Label(status_frame, text="Internet Speed: --ms"),
            'light': ttk.Label(status_frame, text="Light: OFF"),
            'uptime': ttk.Label(status_frame, text="Uptime: --"),
            'memory': ttk.Label(status_frame, text="Free Memory: --"),
            'power': ttk.Label(status_frame, text="Power Consumption: --W"),
            'prediction': ttk.Label(status_frame, text="Next Temp Prediction: --°C")
        }

        for idx, label in enumerate(self.status_labels.values()):
            label.grid(row=idx, column=0, sticky='w', padx=5, pady=2)

    def create_controls_panel(self):
        controls_frame = ttk.LabelFrame(self.root, text="Device Controls")
        controls_frame.grid(row=0, column=1, padx=10, pady=10, sticky='nsew')

        # Pill Reminder Controls
        ttk.Label(controls_frame, text="Pill Times (HH:MM, comma separated):").grid(row=0, column=0, sticky='w', padx=5)
        self.pill_entry = ttk.Entry(controls_frame, width=25)
        self.pill_entry.grid(row=1, column=0, pady=5, padx=5)
        ttk.Button(controls_frame, text="Set Reminders", command=self.set_pill_times).grid(row=2, column=0, padx=5, pady=5)

        # Light Control
        self.light_state = False
        self.light_button = ttk.Button(controls_frame, text="Toggle Light", command=self.toggle_light)
        self.light_button.grid(row=3, column=0, pady=10, padx=5)

        # System Controls
        ttk.Button(controls_frame, text="Reboot Device", command=self.reboot_device).grid(row=4, column=0, padx=5, pady=5)
        ttk.Button(controls_frame, text="Update Firmware", command=self.ota_update).grid(row=5, column=0, padx=5, pady=5)

    def create_history_panel(self):
        history_frame = ttk.LabelFrame(self.root, text="Event History")
        history_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=10, sticky='nsew')

        self.history_log = scrolledtext.ScrolledText(history_frame, width=60, height=10)
        self.history_log.pack(fill='both', expand=True)

    def create_menu(self):
        menu_bar = tk.Menu(self.root)
        config_menu = tk.Menu(menu_bar, tearoff=0)
        config_menu.add_command(label="Settings", command=self.show_settings)
        config_menu.add_command(label="View History", command=self.view_history)
        menu_bar.add_cascade(label="Configuration", menu=config_menu)
        self.root.config(menu=menu_bar)

    def create_db_tables(self):
        cursor = self.db_conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS sensor_data
                          (timestamp TEXT, temperature REAL, humidity REAL, power REAL)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS events
                          (timestamp TEXT, event TEXT)''')
        self.db_conn.commit()

    def close_db(self):
        try:
            if self.db_conn:
                self.db_conn.close()
                print("Database connection closed.")
        except Exception as e:
            print(f"Error closing database: {e}")

    def log_event(self, message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.history_log.insert(tk.END, f"[{timestamp}] {message}\n")
        self.history_log.see(tk.END)
        try:
            cursor = self.db_conn.cursor()
            cursor.execute("INSERT INTO events VALUES (?, ?)", (timestamp, message))
            self.db_conn.commit()
        except Exception as e:
            print(f"Error logging event to DB: {e}")

    def on_mqtt_message(self, client, userdata, message):
        try:
            status = json.loads(message.payload.decode('utf-8'))
            self.root.after(0, self.update_status_labels, status)
        except Exception as e:
            self.log_event(f"Error processing MQTT message: {e}")

    def update_status_labels(self, status):
        try:
            self.status_labels['temperature'].config(text=f"Temperature: {status.get('temperature', '--')}°C")
            self.status_labels['humidity'].config(text=f"Humidity: {status.get('humidity', '--')}%")
            self.status_labels['light'].config(text=f"Light: {'ON' if status.get('light_state') else 'OFF'}")
            self.status_labels['power'].config(text=f"Power Consumption: {status.get('power_consumption', '--')}W")
            # Update prediction label with the latest prediction
            prediction = self.predict_temperature()
            if prediction:
                self.status_labels['prediction'].config(text=f"Next Temp Prediction: {prediction:.2f}°C")
        except Exception as e:
            self.log_event(f"Error updating status labels: {e}")

    def show_settings(self):
        messagebox.showinfo("Settings", "Settings dialog not implemented yet.")

    def view_history(self):
        try:
            cursor = self.db_conn.cursor()
            cursor.execute("SELECT * FROM events ORDER BY timestamp DESC")
            events = cursor.fetchall()
            history_window = tk.Toplevel(self.root)
            history_window.title("Event History")
            history_text = scrolledtext.ScrolledText(history_window, width=80, height=20)
            history_text.pack()
            for event in events:
                history_text.insert(tk.END, f"{event[0]} - {event[1]}\n")
        except Exception as e:
            self.log_event(f"Error viewing history: {e}")

    def train_model(self):
        try:
            cursor = self.db_conn.cursor()
            cursor.execute("SELECT timestamp, temperature, humidity FROM sensor_data")
            data = cursor.fetchall()

            if not data or len(data) < 10:  # Require at least 10 records for training
                print("Insufficient data available for training.")
                self.log_event("Insufficient data for model training; skipping.")
                return

            df = pd.DataFrame(data, columns=['timestamp', 'temperature', 'humidity'])
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df['hour'] = df['timestamp'].dt.hour
            df['day'] = df['timestamp'].dt.day

            X = df[['hour', 'day', 'humidity']]
            y = df['temperature']

            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

            self.model = LinearRegression()
            self.model.fit(X_train, y_train)

            y_pred = self.model.predict(X_test)
            mse = mean_squared_error(y_test, y_pred)
            print(f"Model trained with MSE: {mse}")
            self.log_event(f"Model trained with MSE: {mse}")
        except Exception as e:
            self.log_event(f"Error during model training: {e}")

    def predict_temperature(self):
        if not self.model:
            return None  # No prediction available

        try:
            cursor = self.db_conn.cursor()
            cursor.execute("SELECT timestamp, humidity FROM sensor_data ORDER BY timestamp DESC LIMIT 1")
            latest_data = cursor.fetchone()

            if not latest_data:
                return None

            timestamp, humidity = latest_data
            dt = pd.to_datetime(timestamp)
            hour = dt.hour
            day = dt.day
            input_data = [[hour, day, humidity]]
            prediction = self.model.predict(input_data)
            return prediction[0]
        except Exception as e:
            self.log_event(f"Error during temperature prediction: {e}")
            return None

    def set_pill_times(self):
        """Parse and set pill times from user input (HH:MM format)."""
        try:
            input_text = self.pill_entry.get()
            times = [time_str.strip() for time_str in input_text.split(',') if time_str.strip()]
            valid_times = []
            for t in times:
                if re.match(r"^(?:[01]\d|2[0-3]):[0-5]\d$", t):
                    valid_times.append(t)
                else:
                    messagebox.showerror("Input Error", f"Invalid time format: {t}")
                    return
            self.pill_times = valid_times
            self.log_event(f"Pill times set to: {', '.join(self.pill_times)}")
        except Exception as e:
            self.log_event(f"Error setting pill times: {e}")

    def toggle_light(self):
        """Toggle light state (this is a stub – actual device control code would go here)."""
        try:
            self.light_state = not self.light_state
            state_str = "ON" if self.light_state else "OFF"
            self.status_labels['light'].config(text=f"Light: {state_str}")
            self.log_event(f"Light toggled to {state_str}")
        except Exception as e:
            self.log_event(f"Error toggling light: {e}")

    def reboot_device(self):
        """Reboot the device (this is a stub; actual reboot code would depend on the environment)."""
        try:
            self.log_event("Device reboot initiated.")
            messagebox.showinfo("Reboot", "Device will reboot now.")
            # Insert actual reboot code here if applicable.
        except Exception as e:
            self.log_event(f"Error during reboot: {e}")

    def ota_update(self):
        """Start OTA firmware update (this is a stub – implement your update logic here)."""
        try:
            self.log_event("OTA update initiated.")
            messagebox.showinfo("OTA Update", "Firmware update started.")
            # Insert OTA update logic here.
        except Exception as e:
            self.log_event(f"Error during OTA update: {e}")

    def start_update_thread(self):
        """Start a background thread for periodic updates (stub example)."""
        self.update_thread = threading.Thread(target=self.update_loop, daemon=True)
        self.update_thread.start()

    def update_loop(self):
        while not self.stop_threads.is_set():
            try:
                # For example, update the uptime label every 'update_interval' seconds
                uptime = datetime.now().strftime("%H:%M:%S")
                self.status_labels['uptime'].config(text=f"Uptime: {uptime}")
                time.sleep(self.config.get('update_interval', 5))
            except Exception as e:
                self.log_event(f"Update thread error: {e}")

    def start_reminder_check(self):
        """Start a background thread for checking pill reminders."""
        self.reminder_thread = threading.Thread(target=self.reminder_loop, daemon=True)
        self.reminder_thread.start()

    def reminder_loop(self):
        while not self.stop_threads.is_set():
            try:
                # Check if pill times are set
                if self.pill_times:
                    current_time = datetime.now().strftime("%H:%M")
                    if current_time in self.pill_times:
                        self.log_event("Time to take your pill!")
                        # Here you might add additional UI cues (e.g. flashing window)
                time.sleep(60)  # Check every minute
            except Exception as e:
                self.log_event(f"Reminder thread error: {e}")

    def on_close(self):
        """Cleanup before closing the application."""
        self.stop_threads.set()  # Signal threads to stop
        try:
            self.mqtt_client.loop_stop()
        except Exception:
            pass
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = EnhancedSmartPillApp(root)
    root.mainloop()
