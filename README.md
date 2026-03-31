# dbus-wattcycle-ble

Wattcycle BLE battery driver for Victron Venus OS.

This service connects to Wattcycle/XDZN batteries via Bluetooth Low Energy (BLE) and publishes battery data to the Victron DBus system, making the battery appear as a native device in the Venus OS interface.

## Features

- **BLE Connectivity**: Automatic connection and reconnection to Wattcycle batteries
- **Full Battery Monitoring**: Voltage, current, SOC, cell voltages, temperature, and more
- **DBus Integration**: Native Venus OS battery service with standard paths
- **Configurable**: Simple YAML configuration file
- **Robust**: Automatic reconnection on signal loss, error handling, and logging
- **Zero Dependency on PyYAML**: Internal YAML parser works on clean Venus OS installations

## Requirements

- Venus OS device (Cerbo GX, Venus GX, Raspberry Pi running Venus OS, etc.)
- Python 3.11+
- Bluetooth Low Energy support
- Internet connection for initial dependency installation (bleak only)

**Note:** The wattcycle_ble library is now embedded in this package - no additional pip installation required!

## Installation

### Quick Install

1. Copy the project files to your Venus OS device:
   ```bash
   # Via SSH
   scp -r dbus-wattcycle-ble/ root@<your-venus-ip>:/data/
   ```

2. Run the installation script:
   ```bash
   ssh root@<your-venus-ip>
   cd /data/dbus-wattcycle-ble
   ./install.sh
   ```

3. The script will:
    - Check Python version and dependencies
    - Install required Python packages (bleak only - wattcycle_ble is embedded)
    - Install the daemontools service
    - Start the service

### Manual Install

If the automatic script doesn't work, follow these steps:

1. **Install Python dependencies:**
    ```bash
    pip3 install bleak
    # Note: wattcycle_ble is now embedded in the package
    ```

2. **Copy files to /data:**
   ```bash
   mkdir -p /data/dbus-wattcycle-ble
   cp -r dbus_wattcycle_ble config.yml requirements.txt /data/dbus-wattcycle-ble/
   ```

3. **Create service symlink:**
   ```bash
   mkdir -p /service/dbus-wattcycle-ble
   ln -s /data/dbus-wattcycle-ble/service/run /service/dbus-wattcycle-ble/run
   ```

4. **Configure your battery MAC address** (see Configuration section)

5. **Start the service:**
   ```bash
   sv start /service/dbus-wattcycle-ble
   ```

## Finding Your Battery MAC Address

Before configuring the service, you need to find your battery's Bluetooth MAC address:

1. **Use the embedded wattcycle_ble CLI:**
    ```bash
    cd /data/dbus-wattcycle-ble/dbus_wattcycle_ble/wattcycle_ble
    python3 -m cli scan
    ```

2. **Look for devices starting with "XDZN" or "WT":**
    ```
    Found: XDZN_001_EF2F (C0:D6:3C:57:EF:2F)
    ```

3. **Copy the MAC address** (e.g., `C0:D6:3C:57:EF:2F`) to your config file.

**Note:** The wattcycle_ble library is embedded in this package, so no separate installation is required.

## Configuration

Edit `/data/dbus-wattcycle-ble/config.yml`:

```yaml
battery:
  # REQUIRED: Your battery's MAC address
  mac_address: "C0:D6:3C:57:EF:2F"
  
  # Display name in Venus GUI
  name: "House Battery"
  
  # Device instance (use different values for multiple batteries)
  device_instance: 1
  
  # Polling interval in milliseconds (5 seconds = 5000)
  poll_interval: 5000
  
  # Reconnection delay in seconds
  reconnect_delay: 10

logging:
  # Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL
  level: "INFO"
  
  # Optional log file path
  # file: "/var/log/dbus-wattcycle-ble.log"
```

After editing, restart the service:
```bash
sv restart /service/dbus-wattcycle-ble
```

## Verification

### Check Service Status

```bash
svstat /service/dbus-wattcycle-ble
```

Should show:
```
/service/dbus-wattcycle-ble: up (pid XXXXX) X seconds
```

### View Logs

```bash
tail -f /var/log/dbus-wattcycle-ble/main/current
```

Enable debug logging in config.yml for detailed BLE traffic:
```yaml
logging:
  level: "DEBUG"
```

### Check Venus GUI

1. Open your Venus device's display or Remote Console
2. Navigate to **Settings → Devices**
3. Look for "Wattcycle BLE Battery" in the battery list
4. You should see voltage, current, SOC, and other battery data

### Check DBus with dbus-monitor

```bash
dbus-monitor --system "type='signal',interface='com.victronenergy.BusItem'"
```

## DBus Paths

The service publishes the following DBus paths under `com.victronenergy.battery.wattcycle_ble.device0_1`:

### DC Measurements
- `/Dc/0/Voltage` - Pack voltage (V)
- `/Dc/0/Current` - Pack current (A) (positive = charging)
- `/Dc/0/Power` - Power (W) = Voltage × Current
- `/Dc/0/Temperature` - MOSFET temperature (°C)

### State of Charge
- `/Soc` - State of charge (0-100%)
- `/Capacity` - Total capacity (Ah)

### Cell Monitoring
- `/System/MinCellVoltage` - Minimum cell voltage (V)
- `/System/MaxCellVoltage` - Maximum cell voltage (V)
- `/System/CellVoltages` - List of cell voltages (mV)

### Device Info
- `/CustomName` - Battery name from config
- `/Serial` - Battery serial number
- `/FirmwareVersion` - BMS firmware version
- `/Connected` - Connection status (1=connected, 0=disconnected)

### Alarms
- `/Alarms/LowVoltage` - Low voltage alarm (0=OK, 2=Alarm)
- `/Alarms/HighVoltage` - High voltage alarm
- `/Alarms/LowTemperature` - Low temperature alarm
- `/Alarms/HighTemperature` - High temperature alarm
- `/Alarms/LowSoc` - Low SOC alarm

### Additional Info
- `/Info/ChargeCycles` - Number of charge/discharge cycles
- `/Info/MaxChargeCurrent` - Maximum charge current (A) [not yet implemented]
- `/Info/MaxDischargeCurrent` - Maximum discharge current (A) [not yet implemented]

## Troubleshooting

### Service Won't Start

1. **Check logs:**
   ```bash
   tail -50 /var/log/dbus-wattcycle-ble/main/current
   ```

2. **Verify Python version:**
   ```bash
   python3 --version
   # Should be 3.11 or higher
   ```

3. **Check dependencies:**
   ```bash
   pip3 list | grep -E 'bleak|wattcycle'
   ```

4. **Verify Bluetooth:**
   ```bash
   ls /sys/class/bluetooth
   # Should show at least one adapter (e.g., hci0)
   ```

### Can't Find Battery

1. **Verify MAC address format:**
   - Should be in format: `XX:XX:XX:XX:XX:XX`
   - Use uppercase letters

2. **Test BLE connection manually:**
   ```bash
   wattcycle-ble read <MAC-ADDRESS>
   ```

3. **Check Bluetooth status:**
   ```bash
   bluetoothctl power on
   bluetoothctl scan on
   ```

### Connection Drops Frequently

1. **Increase polling interval** in config.yml:
   ```yaml
   battery:
     poll_interval: 10000  # 10 seconds
   ```

2. **Check signal strength:**
   - Move the Venus device closer to the battery
   - Reduce interference from other Bluetooth devices

3. **Enable debug logging** to see connection issues:
   ```yaml
   logging:
     level: "DEBUG"
   ```

### Data Not Updating in Venus GUI

1. **Verify service is running:**
   ```bash
   svstat /service/dbus-wattcycle-ble
   ```

2. **Check Connected status:**
   ```bash
   dbus-send --system --print-reply \
     --dest=com.victronenergy.battery.wattcycle_ble.device0_1 \
     /Connected \
     com.victronenergy.BusItem.GetValue
   ```

3. **Restart Venus GUI** if data appears stuck

## Service Management

### Start/Stop/Restart

```bash
# Start
sv start /service/dbus-wattcycle-ble

# Stop
sv stop /service/dbus-wattcycle-ble

# Restart
sv restart /service/dbus-wattcycle-ble

# Status
svstat /service/dbus-wattcycle-ble
```

### Remove Service

```bash
# Stop service
sv stop /service/dbus-wattcycle-ble

# Remove service symlink
rm /service/dbus-wattcycle-ble

# Optionally remove installation directory
rm -rf /data/dbus-wattcycle-ble
```

## Advanced Configuration

### Multiple Batteries

To monitor multiple batteries, create separate installations:

1. **Create separate directories:**
   ```bash
   cp -r /data/dbus-wattcycle-ble /data/dbus-wattcycle-ble-2
   ```

2. **Configure different MAC addresses and device instances:**
   ```yaml
   # /data/dbus-wattcycle-ble/config.yml
   battery:
     mac_address: "C0:D6:3C:57:EF:2F"
     device_instance: 1
   
   # /data/dbus-wattcycle-ble-2/config.yml
   battery:
     mac_address: "D0:E7:4D:68:F0:3G"
     device_instance: 2
   ```

3. **Create separate service:**
   ```bash
   mkdir -p /service/dbus-wattcycle-ble-2
   ln -s /data/dbus-wattcycle-ble-2/service/run /service/dbus-wattcycle-ble-2/run
   sv start /service/dbus-wattcycle-ble-2
   ```

### Custom Polling Intervals

Adjust the polling interval based on your needs:
- **Fast (1000ms)**: For real-time monitoring (may drain battery faster)
- **Normal (5000ms)**: Default, good balance
- **Slow (10000ms)**: Reduced BLE traffic, less frequent updates

## Development

### Project Structure

```
dbus-wattcycle-ble/
├── dbus_wattcycle_ble/          # Python package
│   ├── __init__.py
│   ├── battery_service.py       # Main service logic
│   ├── config.py                # Configuration handling
│   ├── vedbus.py                # Victron DBus utilities
│   └── ve_utils.py              # Venus OS utilities
├── service/
│   └── run                      # daemontools service script
├── config.yml                   # Configuration template
├── requirements.txt              # Python dependencies
├── install.sh                   # Installation script
└── README.md                    # This file
```

### Dependencies

- **bleak**: BLE library for Python
- **wattcycle-ble**: Wattcycle BLE protocol library

### References

- [dbus-ads1115](https://github.com/alexsanzder/dbus-ads1115) - DBus integration pattern reference
- [wattcycle_ble](https://github.com/qume/wattcycle_ble) - BLE protocol implementation
- [Victron Venus OS DBus API](https://github.com/victronenergy/venus/wiki/dbus-api)

## License

MIT License - See LICENSE file for details

## Support

- **Issues**: Report bugs on GitHub
- **Documentation**: See Victron Community forums
- **Protocol**: See [wattcycle_ble PROTOCOL.md](https://github.com/qume/wattcycle_ble/blob/main/PROTOCOL.md)

## Credits

- **Victron Energy**: Venus OS and DBus API
- **qume**: wattcycle_ble library and protocol reverse-engineering
- **alexsanzder**: dbus-ads1115 reference implementation
