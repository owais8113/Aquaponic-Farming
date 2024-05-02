import machine
import time
import network
import socket
import ssd1306
import onewire
import ds18x20
import utime

# Wi-Fi credentials
ssid = "________"
password = "_________"

# Sensor pins
TRIGGER_PIN = 14
ECHO_PIN = 15
TEMP_SENSOR_PIN = 7
WATER_LEVEL_PIN = 16
TURBIDITY_PIN = 26  # Pin connected to the turbidity sensor
OLED_SCL_PIN = 5
OLED_SDA_PIN = 4
BUZZER_PIN = 0  # Pin connected to the buzzer

# Relay pins
PUMP_PIN = 12
HEATER_PIN = 13

# Initialize ultrasonic sensor
trigger = machine.Pin(TRIGGER_PIN, machine.Pin.OUT)
echo = machine.Pin(ECHO_PIN, machine.Pin.IN)

# Initialize OLED display
i2c = machine.I2C(0, scl=machine.Pin(OLED_SCL_PIN), sda=machine.Pin(OLED_SDA_PIN))
oled = ssd1306.SSD1306_I2C(128, 64, i2c)

# Initialize DS18 temperature sensor
ow = onewire.OneWire(machine.Pin(TEMP_SENSOR_PIN))
ds = ds18x20.DS18X20(ow)
roms = ds.scan()

# Initialize water level sensor
water_level = machine.Pin(WATER_LEVEL_PIN, machine.Pin.IN)

# Initialize turbidity sensor
adc = machine.ADC(machine.Pin(TURBIDITY_PIN))

# Initialize buzzer
buzzer = machine.Pin(BUZZER_PIN, machine.Pin.OUT)

# Initialize relays
pump_relay = machine.Pin(PUMP_PIN, machine.Pin.OUT)
heater_relay = machine.Pin(HEATER_PIN, machine.Pin.OUT)

# Set initial state of relays
pump_relay.off()
heater_relay.off()

# Connect to WLAN
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(ssid, password)

# Wait for Wi-Fi connection
connection_timeout = 10
while connection_timeout > 0:
    if wlan.status() == network.STAT_GOT_IP:
        break
    connection_timeout -= 1
    print("Waiting for Wi-Fi connection...")
    time.sleep(1)

# Check if connection is successful
if wlan.status() != network.STAT_GOT_IP:
    raise RuntimeError("Failed to establish a network connection")
else:
    print("Connection successful!")
    network_info = wlan.ifconfig()
    print("IP address:", network_info[0])

def webpage(distance, temperature, water_presence, turbidity, pump_state, heater_state):
    html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Aquaponic Farming using IoT</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                /* CSS animations */
                @keyframes fadeIn {{
                    from {{ opacity: 0; }}
                    to {{ opacity: 1; }}
                }}

                @keyframes slideIn {{
                    from {{ transform: translateY(-50px); }}
                    to {{ transform: translateY(0); }}
                }}

                @keyframes pulse {{
                    0% {{ transform: scale(1); }}
                    50% {{ transform: scale(1.1); }}
                    100% {{ transform: scale(1); }}
                }}
            
                /* Styling */
                body {{
                    font-family: Arial, sans-serif;
                    margin: 0;
                    padding: 0;
                    background-color: #f2f2f2;
                    text-align-last: center;
                }}

                h1, h2 {{
                    text-align: center;
                    animation: fadeIn 1s ease-in-out;
                }}

                .sensor-box {{
                    width: 80%;
                    margin: 20px auto;
                    padding: 10px;
                    background-color: #ffffff;
                    border-radius: 10px;
                    box-shadow: 0px 0px 10px 0px rgba(0,0,0,0.1);
                    animation: slideIn 1s ease-in-out;
                }}

                .sensor-title {{
                    font-size: 20px;
                    font-weight: bold;
                }}

                .sensor-value {{
                    font-size: 18px;
                    margin-top: 5px;
                }}

                .small-value {{
                    font-size: 14px;
                }}

                input[type="submit"] {{
                    background-color: #4CAF50;
                    border: none;
                    color: white;
                    padding: 15px 32px;
                    text-align: center;
                    text-decoration: none;
                    display: inline-block;
                    font-size: 16px;
                    margin: 4px 2px;
                    cursor: pointer;
                    border-radius: 12px;
                    transition-duration: 0.4s;
                    box-shadow: 0px 8px 16px 0px rgba(0,0,0,0.2);
                    animation: pulse 2s infinite;
                }}

                input[type="submit"]:hover {{
                    background-color: #45a049;
                    animation: none; /* Disable animation on hover */
                }}
            </style>
        </head>
        <body>
            <h1>Aquaponic Farming using IoT</h1>
            
            <!-- Distance Box -->
            <div class="sensor-box">
                <div class="sensor-title">Distance</div>
                <div class="sensor-value">{distance} cm</div>
            </div>

            <!-- Temperature Box -->
            <div class="sensor-box">
                <div class="sensor-title">Temperature</div>
                <div class="sensor-value">{temperature} °C</div>
            </div>

            <!-- Water Presence Box -->
            <div class="sensor-box">
                <div class="sensor-title">Water Presence</div>
                <div class="sensor-value">{water_presence}</div>
            </div>

            <!-- Turbidity Box -->
            <div class="sensor-box">
                <div class="sensor-title">Turbidity</div>
                <div class="sensor-value small-value">{turbidity}</div>
            </div>

            <h2>Control</h2>
            <form action="/pump_toggle" method="post">
                <input type="submit" value="Toggle Pump ({pump_state})" />
            </form>
            <form action="/heater_toggle" method="post">
                <input type="submit" value="Toggle Heater ({heater_state})" />
            </form>
        </body>
        </html>
        """
    return html

# Initialize socket and start listening
addr = socket.getaddrinfo("0.0.0.0", 80)[0][-1]
s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(addr)
s.listen(1)

print("Listening on", addr)

# Function to measure distance using ultrasonic sensor
def measure_distance():
    trigger.low()
    utime.sleep_us(2)
    trigger.high()
    utime.sleep_us(10)
    trigger.low()
    
    while echo.value() == 0:
        pulse_start = utime.ticks_us()
    while echo.value() == 1:
        pulse_end = utime.ticks_us()
        
    pulse_duration = pulse_end - pulse_start
    distance = pulse_duration * 0.0343 / 2  # Speed of sound = 343 m/s
    return distance

# Function to parse the request path
def parse_request_path(request):
    try:
        path_start = request.find(b' ') + 1
        path_end = request.find(b' ', path_start)
        path = request[path_start:path_end].decode()
        return path
    except Exception as e:
        print("Error parsing request path:", e)
        return None

# Function to read temperature from DS18B20 sensor
def read_temperature():
    ow = onewire.OneWire(machine.Pin(TEMP_SENSOR_PIN))
    ds = ds18x20.DS18X20(ow)
    roms = ds.scan()
    if len(roms) > 0:
        ds.convert_temp()
        utime.sleep_ms(750)
        temperature = ds.read_temp(roms[0])
        return temperature
    else:
        print("No DS18B20 sensor found!")
        return None

# Main loop to listen for connections
while True:
    conn, addr = s.accept()
    print("Got a connection from", addr)

    # Receive and parse the request
    request = conn.recv(1024)
    print("Request content:", request)

    try:
        # Extract request path
        request_path = parse_request_path(request)
        
        if request_path == "/":
            # Read sensor data and relay states
            distance = 17 - measure_distance()
            temperature = read_temperature()
            water_presence = water_level.value()
            turbidity = adc.read_u16() * (100 / 65535)  # Convert ADC value to voltage, assuming 5V reference
            pump_state = "ON" if pump_relay.value() else "OFF"
            heater_state = "ON" if heater_relay.value() else "OFF"

            Activate buzzer if water is not present
            if not water_presence:
                buzzer.on()
            else:
                buzzer.off()

            # Print values on OLED display
            oled.fill(0)
            oled.text("Water Level:", 0, 0)
            oled.text(str(distance) + " cm", 0, 16)
            oled.text("Temperature:", 0, 32)
            oled.text(str(temperature) + " C", 0, 48)
            oled.text("Turbidity:", 0, 64)
            oled.text(str(turbidity), 0, 80)
            oled.show()

            # Generate HTML response
            response = webpage(distance, temperature, water_presence, turbidity, pump_state, heater_state)

            # Send HTTP response
            conn.send("HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: {}\r\n\r\n{}".format(len(response), response))
        elif request_path == "/pump_toggle":
            # Toggle pump relay
            pump_relay.value(not pump_relay.value())
            conn.send("HTTP/1.1 303 See Other\r\nLocation: /\r\n\r\n")
        elif request_path == "/heater_toggle":
            # Toggle heater relay
            heater_relay.value(not heater_relay.value())
            conn.send("HTTP/1.1 303 See Other\r\nLocation: /\r\n\r\n")
        else:
            # Return a 404 Not Found response for invalid requests
            conn.send("HTTP/1.1 404 Not Found\r\nContent-Type: text/plain\r\nContent-Length: 9\r\n\r\nNot Found")
    except Exception as e:
        print("Error:", e)
    finally:
        # Close the connection
        conn.close()

