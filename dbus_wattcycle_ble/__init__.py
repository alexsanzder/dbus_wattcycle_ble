#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dbus-wattcycle-ble: Wattcycle BLE battery driver for Venus OS.

This package provides a DBus service for Victron Venus OS that connects to
Wattcycle batteries via Bluetooth Low Energy (BLE) and publishes battery data
to the Victron DBus system.
"""

__version__ = '1.0.0'
__author__ = 'Victron Community'

from .config import Config
from .battery_service import BatteryService

__all__ = ['Config', 'BatteryService', '__version__']
