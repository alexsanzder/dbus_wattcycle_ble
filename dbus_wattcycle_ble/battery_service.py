#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Main battery service for dbus-wattcycle-ble.

This service connects to a Wattcycle battery via Bluetooth Low Energy (BLE),
reads battery data, and publishes it to the Victron DBus system.
"""

import asyncio
import logging
import sys
import os
import dbus
import dbus.mainloop.glib
import dbus.service
from datetime import datetime
from argparse import ArgumentParser
from gi.repository import GLib

try:
    from .wattcycle_ble import WattcycleClient
except ImportError:
    WattcycleClient = None
    logging.error("wattcycle_ble library not installed. Install with: pip install git+https://github.com/qume/wattcycle_ble.git")

from .config import Config
from .vedbus import VeDbusService
from .ve_utils import wrap_dbus_value

logger = logging.getLogger(__name__)

VERSION = '1.0.0'
SERVICE_NAME = 'com.victronenergy.battery.wattcycle_ble'
PRODUCT_ID = 0xA142


class BatteryService:
    """Main battery service that manages BLE connection and DBus publishing."""
    
    def __init__(self, config):
        """Initialize the battery service.
        
        Args:
            config: Config object with service configuration
        """
        self.config = config
        self._dbus = None
        self._running = False
        self._battery_connected = False
        self._product_info = None
        self._last_valid_data = None
        
        # Initialize DBus
        self._init_dbus()
        
        logger.info(f"BatteryService initialized for {config.mac_address}")
    
    def _init_dbus(self):
        """Initialize DBus service and register all paths."""
        # Create DBus service name with device instance
        servicename = f"{SERVICE_NAME}.device0_{self.config.device_instance}"
        
        try:
            self._dbus = VeDbusService(servicename)
            logger.info(f"Registered DBus service: {servicename}")
        except Exception as e:
            logger.error(f"Failed to register DBus service: {e}")
            raise
        
        # Add mandatory paths
        self._dbus.add_mandatory_paths(
            processname="dbus-wattcycle-ble",
            processversion=VERSION,
            connection="BLE",
            deviceinstance=self.config.device_instance,
            productid=PRODUCT_ID,
            productname="Wattcycle BLE Battery",
            firmwareversion="Unknown",
            hardwareversion="1.0",
            connected=0
        )
        
        # Add battery-specific paths
        self._add_battery_paths()
        
        logger.info("All DBus paths registered")
    
    def _add_battery_paths(self):
        """Register battery-specific DBus paths."""
        # DC measurements
        self._dbus.add_path('/Dc/0/Voltage', 0.0, writeable=False)
        self._dbus.add_path('/Dc/0/Current', 0.0, writeable=False)
        self._dbus.add_path('/Dc/0/Power', 0.0, writeable=False)
        self._dbus.add_path('/Dc/0/Temperature', 0.0, writeable=False)
        
        # State of charge
        self._dbus.add_path('/Soc', 0, writeable=False)
        self._dbus.add_path('/Capacity', 0.0, writeable=False)
        
        # Cell voltages
        self._dbus.add_path('/System/MinCellVoltage', 0.0, writeable=False)
        self._dbus.add_path('/System/MaxCellVoltage', 0.0, writeable=False)
        self._dbus.add_path('/System/CellVoltages', [], writeable=False)
        
        # Custom info
        self._dbus.add_path('/CustomName', self.config.battery_name, writeable=False)
        self._dbus.add_path('/Serial', 'Unknown', writeable=False)
        
        # Alarms (0=OK, 1=Warning, 2=Alarm)
        self._dbus.add_path('/Alarms/LowVoltage', 0, writeable=False)
        self._dbus.add_path('/Alarms/HighVoltage', 0, writeable=False)
        self._dbus.add_path('/Alarms/LowTemperature', 0, writeable=False)
        self._dbus.add_path('/Alarms/HighTemperature', 0, writeable=False)
        self._dbus.add_path('/Alarms/LowSoc', 0, writeable=False)
        
        # Battery info
        self._dbus.add_path('/Info/MaxChargeCurrent', 0.0, writeable=False)
        self._dbus.add_path('/Info/MaxDischargeCurrent', 0.0, writeable=False)
        self._dbus.add_path('/Info/ChargeCycles', 0, writeable=False)
        
        # Sync initial values
        self._dbus['/Connected'] = 0
    
    def set_connected_status(self, connected):
        """Update the connected status on DBus."""
        self._battery_connected = connected
        try:
            self._dbus['/Connected'] = 1 if connected else 0
            logger.info(f"Connected status: {connected}")
        except Exception as e:
            logger.error(f"Failed to update connected status: {e}")
    
    def update_dbus_data(self, analog_data, warning_info):
        """Update all DBus paths with new battery data.
        
        Args:
            analog_data: AnalogQuantity object from wattcycle_ble
            warning_info: WarningInfo object from wattcycle_ble
        """
        try:
            # DC measurements
            self._dbus['/Dc/0/Voltage'] = round(analog_data.module_voltage, 2)
            self._dbus['/Dc/0/Current'] = round(analog_data.current, 1)
            
            # Calculate power (P = V × I)
            power = analog_data.module_voltage * analog_data.current
            self._dbus['/Dc/0/Power'] = round(power, 1)
            
            # Temperature (use MOSFET temperature as main temp)
            self._dbus['/Dc/0/Temperature'] = round(analog_data.mos_temperature, 1)
            
            # State of charge and capacity
            self._dbus['/Soc'] = analog_data.soc
            self._dbus['/Capacity'] = round(analog_data.total_capacity, 1)
            
            # Cell voltages
            if analog_data.cell_voltages:
                self._dbus['/System/MinCellVoltage'] = round(min(analog_data.cell_voltages), 3)
                self._dbus['/System/MaxCellVoltage'] = round(max(analog_data.cell_voltages), 3)
                # Convert to mV for Victron format
                cell_mv = [int(v * 1000) for v in analog_data.cell_voltages]
                self._dbus['/System/CellVoltages'] = cell_mv
            
            # Info
            self._dbus['/Info/ChargeCycles'] = analog_data.cycle_number
            
            # Alarms based on warning info
            self._update_alarms(warning_info)
            
            logger.debug(f"Updated DBus: V={analog_data.module_voltage:.2f}V, "
                        f"I={analog_data.current:.1f}A, SOC={analog_data.soc}%")
            
        except Exception as e:
            logger.error(f"Failed to update DBus data: {e}")
    
    def _update_alarms(self, warning_info):
        """Update alarm paths based on warning info.
        
        Args:
            warning_info: WarningInfo object from wattcycle_ble
        """
        try:
            # Map Wattcycle protections to Victron alarms
            protections = warning_info.protections if warning_info else []
            
            # Low voltage alarm
            low_voltage = any('overdischarge' in p.lower() or 'undervoltage' in p.lower() 
                            for p in protections)
            self._dbus['/Alarms/LowVoltage'] = 2 if low_voltage else 0
            
            # High voltage alarm
            high_voltage = any('overcharge' in p.lower() or 'overvoltage' in p.lower() 
                             for p in protections)
            self._dbus['/Alarms/HighVoltage'] = 2 if high_voltage else 0
            
            # Temperature alarms
            low_temp = any('low temperature' in p.lower() for p in protections)
            high_temp = any('high temperature' in p.lower() for p in protections)
            self._dbus['/Alarms/LowTemperature'] = 2 if low_temp else 0
            self._dbus['/Alarms/HighTemperature'] = 2 if high_temp else 0
            
            # Low SOC alarm
            low_soc = any('soc' in p.lower() and ('low' in p.lower() or 'empty' in p.lower()) 
                         for p in protections)
            self._dbus['/Alarms/LowSoc'] = 2 if low_soc else 0
            
        except Exception as e:
            logger.error(f"Failed to update alarms: {e}")
    
    def update_firmware_info(self, product_info):
        """Update firmware and serial info.
        
        Args:
            product_info: ProductInfo object from wattcycle_ble
        """
        if not product_info:
            return
        
        try:
            self._dbus['/FirmwareVersion'] = product_info.firmware_version
            self._dbus['/Serial'] = product_info.serial_number
            logger.info(f"Firmware: {product_info.firmware_version}, "
                       f"Serial: {product_info.serial_number}")
        except Exception as e:
            logger.error(f"Failed to update firmware info: {e}")
    
    async def _connect_and_read(self):
        """Connect to battery and read data once.
        
        Returns:
            tuple: (analog_data, warning_info) or (None, None) on failure
        """
        if WattcycleClient is None:
            logger.error("wattcycle_ble library not available")
            return None, None
        
        try:
            logger.debug(f"Connecting to {self.config.mac_address}")
            
            async with WattcycleClient(self.config.mac_address) as client:
                # Detect frame header
                if not await client.detect_frame_head():
                    logger.error("Failed to detect frame header")
                    return None, None
                
                # Read product info (first time only)
                if self._product_info is None:
                    try:
                        product_info = await client.read_product_info()
                        if product_info:
                            self._product_info = product_info
                            self.update_firmware_info(product_info)
                    except Exception as e:
                        logger.warning(f"Failed to read product info: {e}")
                
                # Read battery data
                analog_data = await client.read_analog_quantity()
                if not analog_data:
                    logger.warning("Failed to read analog quantity")
                    return None, None
                
                # Read warning info
                warning_info = await client.read_warning_info()
                
                logger.debug("Successfully read battery data")
                return analog_data, warning_info
                
        except Exception as e:
            logger.error(f"BLE connection error: {e}")
            return None, None
    
    async def _connection_loop(self):
        """Inner connection loop - manages single connection with periodic polling."""
        logger.info("Starting connection loop")
        
        while self._running:
            try:
                # Connect and read first batch of data
                analog_data, warning_info = await self._connect_and_read()
                
                if analog_data:
                    # Connection successful
                    self.set_connected_status(True)
                    self.update_dbus_data(analog_data, warning_info)
                    
                    # Polling loop
                    while self._running:
                        try:
                            # Wait for poll interval
                            await asyncio.sleep(self.config.poll_interval_seconds)
                            
                            # Read data
                            analog_data, warning_info = await self._connect_and_read()
                            
                            if analog_data:
                                self.update_dbus_data(analog_data, warning_info)
                            else:
                                logger.warning("Failed to read data, will reconnect")
                                break
                                
                        except asyncio.CancelledError:
                            break
                        except Exception as e:
                            logger.error(f"Polling error: {e}")
                            break
                else:
                    logger.warning("Initial connection failed")
                    self.set_connected_status(False)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Connection loop error: {e}")
                self.set_connected_status(False)
            
            # Wait before reconnecting
            if self._running:
                logger.info(f"Reconnecting in {self.config.reconnect_delay} seconds...")
                await asyncio.sleep(self.config.reconnect_delay)
    
    async def run(self):
        """Main service loop."""
        logger.info("Starting BatteryService")
        self._running = True
        
        try:
            await self._connection_loop()
        except asyncio.CancelledError:
            logger.info("Service cancelled")
        except Exception as e:
            logger.error(f"Service error: {e}")
        finally:
            self._running = False
            self.set_connected_status(False)
            logger.info("BatteryService stopped")
    
    def stop(self):
        """Stop the service."""
        logger.info("Stopping BatteryService")
        self._running = False


def main():
    """Main entry point."""
    parser = ArgumentParser(description='dbus-wattcycle-ble: Wattcycle BLE battery service for Venus OS')
    parser.add_argument('-d', '--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('-c', '--config', default='config.yml', help='Configuration file path')
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    logger.info(f"Starting dbus-wattcycle-ble v{VERSION}")
    
    # Load configuration
    try:
        config = Config(args.config)
        logger.info(f"Configuration loaded: {config}")
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        sys.exit(1)
    
    # Initialize DBus with GLib
    try:
        dbus.mainloop.glib.threads_init()
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        logger.info("DBus initialized with GLib")
    except Exception as e:
        logger.error(f"Failed to initialize DBus: {e}")
        sys.exit(1)
    
    # Create battery service
    try:
        service = BatteryService(config)
    except Exception as e:
        logger.error(f"Failed to create battery service: {e}")
        sys.exit(1)
    
    # Setup GLib timer for asyncio polling
    # We run asyncio in a thread and use GLib timer to trigger it
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Create service task
    service_task = loop.create_task(service.run())
    
    # Define timer callback that runs one asyncio step
    def step_asyncio():
        try:
            # Run pending async tasks
            loop.call_soon(loop.stop)
            loop.run_forever()
        except Exception as e:
            logger.error(f"Asyncio step error: {e}")
        return True  # Continue timer
    
    # Start timer - runs every 100ms
    GLib.timeout_add(100, step_asyncio)
    
    # Run GLib main loop
    logger.info("Entering main loop")
    mainloop = GLib.MainLoop()
    
    try:
        mainloop.run()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    finally:
        logger.info("Shutting down...")
        service.stop()
        
        # Cancel asyncio task
        if service_task and not service_task.done():
            service_task.cancel()
            try:
                loop.run_until_complete(service_task)
            except asyncio.CancelledError:
                pass
        
        loop.close()
        logger.info("Shutdown complete")


if __name__ == "__main__":
    main()
