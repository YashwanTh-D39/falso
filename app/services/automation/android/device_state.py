"""
FALSO 4.13 Android Device State & Lifecycle Models.

Defines:
- ConnectionState (NOT_CONNECTED, CONNECTED, UNAUTHORIZED, OFFLINE, READY, LOCKED, UNKNOWN)
- AndroidCapabilityState (AVAILABLE, UNAVAILABLE, UNAUTHORIZED, LOCKED, DENIED, FAILED, EXECUTED_UNVERIFIED, VERIFIED)
- AndroidExecutionState (REQUESTED, PLANNED, EXECUTING, EXECUTED, VERIFIED, EXECUTED_UNVERIFIED, FAILED, CANCELLED)
- AndroidDeviceState dataclass tracking live device posture
"""

from __future__ import annotations

from dataclasses import dataclass, field
import enum
import time
from typing import Any


class ConnectionState(enum.Enum):
    NOT_CONNECTED = "NOT_CONNECTED"
    CONNECTED = "CONNECTED"
    UNAUTHORIZED = "UNAUTHORIZED"
    OFFLINE = "OFFLINE"
    READY = "READY"
    LOCKED = "LOCKED"
    UNKNOWN = "UNKNOWN"


class AndroidCapabilityState(enum.Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    UNAUTHORIZED = "UNAUTHORIZED"
    LOCKED = "LOCKED"
    DENIED = "DENIED"
    FAILED = "FAILED"
    EXECUTED_UNVERIFIED = "EXECUTED_UNVERIFIED"
    VERIFIED = "VERIFIED"


class AndroidExecutionState(enum.Enum):
    REQUESTED = "REQUESTED"
    PLANNED = "PLANNED"
    EXECUTING = "EXECUTING"
    EXECUTED = "EXECUTED"
    VERIFIED = "VERIFIED"
    EXECUTED_UNVERIFIED = "EXECUTED_UNVERIFIED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class AndroidDeviceState:
    device_id: str
    manufacturer: str = "Unknown"
    model: str = "Unknown"
    android_version: str = "Unknown"
    api_level: int = 0
    connection_state: ConnectionState = ConnectionState.UNKNOWN
    is_authorized: bool = False
    battery_level: int | None = None
    is_charging: bool | None = None
    screen_state: str = "UNKNOWN"  # ON, OFF, UNKNOWN
    lock_state: str = "UNKNOWN"    # LOCKED, UNLOCKED, UNKNOWN
    storage_free_gb: float | None = None
    foreground_app: str | None = None
    foreground_activity: str | None = None
    installed_packages: list[str] = field(default_factory=list)
    wifi_ssid: str | None = None
    ip_address: str | None = None
    is_vpn_active: bool = False
    developer_options_enabled: bool | None = None
    usb_debugging_enabled: bool = True
    last_seen: float = field(default_factory=time.time)

    def is_usable(self) -> bool:
        return self.connection_state == ConnectionState.READY and self.is_authorized

    def to_dict(self) -> dict[str, Any]:
        return {
            "device_id": self.device_id,
            "manufacturer": self.manufacturer,
            "model": self.model,
            "android_version": self.android_version,
            "api_level": self.api_level,
            "connection_state": self.connection_state.value,
            "is_authorized": self.is_authorized,
            "battery_level": self.battery_level,
            "is_charging": self.is_charging,
            "screen_state": self.screen_state,
            "lock_state": self.lock_state,
            "storage_free_gb": self.storage_free_gb,
            "foreground_app": self.foreground_app,
            "foreground_activity": self.foreground_activity,
            "installed_packages_count": len(self.installed_packages),
            "wifi_ssid": self.wifi_ssid,
            "ip_address": self.ip_address,
            "is_vpn_active": self.is_vpn_active,
            "developer_options_enabled": self.developer_options_enabled,
            "usb_debugging_enabled": self.usb_debugging_enabled,
            "last_seen": self.last_seen,
        }
