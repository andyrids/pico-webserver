"""Connection module contains functions and exceptions related to Pico
network and MQTT client connections.

Author: Andrew Ridyard.

License: GNU General Public License v3 or later.

Copyright (C): 2025.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.

Functions:
    access_point_reset: Reset network interface to AP.
    activate_interface: Activate WLAN interface.
    connect_interface: Connect WLAN interface to a network.
    connection_issue: WLAN connection issue flag function.
    deactivate_interface: Deactivate WLAN interface.
    get_network_interface: Get a network interface, in STA or AP mode.

Exceptions:
    CertificateNotFound
    WLANConnectionError
"""

import binascii
import machine
import network
from time import sleep
from .utility import debug_message, dynamic_get_secret, dynamic_set_secret


class CertificateNotFound(Exception):
    """SSL context certificate not found."""
    pass


class WLANConnectionError(Exception):
    """WLAN connection failed."""
    pass


def activate_interface(WLAN: network.WLAN, verbose: bool) -> None:
    """Activate WLAN interface and wait 5 seconds for initialisation.
    
    NOTE: The active method does not behave as expected on the Pico W 
    for STA mode - it will always return False (hence the timeout).

    Args:
        WLAN (network.WLAN): WLAN instance
        debug (bool): Enable verbose debug messages

    Returns:
        None
    """
    debug_message("ACTIVATE NETWORK INTERFACE", verbose)
    # activate network interface
    WLAN.active(True)
    try: # 5 second timeout
        await_timeout = iter(range(5))
        while next(await_timeout) >= 0:
            if WLAN.status() == network.STAT_GOT_IP or WLAN.active():
                debug_message("NETWORK INTERFACE ACTIVE - AP MODE", verbose)
                break
            sleep(1)
    except StopIteration:
        debug_message("NETWORK INTERFACE TIMEOUT - STA MODE", verbose)


def deactivate_interface(WLAN: network.WLAN, verbose: bool) -> None:
    """Deactivate WLAN interface.

    NOTE: The `active` method does not behave as expected on the Pico W
    for STA mode - it will always return False (hence the timeout).

    Args:
        WLAN (network.WLAN): WLAN instance.
        verbose (bool): Enable verbose debug messages.
    """
    debug_message("DEACTIVATE NETWORK INTERFACE", verbose)
    WLAN.active(False)

    try: # 10 second timeout
        await_timeout = iter(range(5))
        while next(await_timeout) >= 0:
            if not WLAN.active():
                debug_message("NETWORK INTERFACE INACTIVE - AP MODE", verbose)
                break
            sleep(1)
    except StopIteration:
        debug_message("DEACTIVATE NETWORK INTERFACE TIMEOUT - STA MODE", verbose)


def connect_interface(WLAN: network.WLAN, verbose: bool) -> None:
        """Connect the WLAN interface using the WLAN_SSID & WLAN_PASSWORD
        credentials. Connection will raise a TypeError if WLAN is in AP mode 
        and the original WAN AP interface will be returned.

        Args:
            WLAN (network.WLAN): Activated WLAN interface.
            debug (bool): Enable verbose debug messages.

        Returns:
            network.WLAN: Connected STA WLAN | AP WLAN interface.

        Raises:
            StopIteration: On WLAN STA interface connection timeout (15s).
            WLANConnectionError: On failed connection to WiFi access point.
        """
        try:
            WLAN_SSID = dynamic_get_secret("WLAN_SSID")
            WLAN_PASSWORD = dynamic_get_secret("WLAN_PASSWORD")
    
            if WLAN_SSID is None:
                debug_message("NETWORK SSID SECRET NOT SET", verbose)
                raise WLANConnectionError

            available_networks = {name.decode() for name,*_ in set(WLAN.scan()) if name}
            if WLAN_SSID not in available_networks:
                debug_message(f"NETWORK SSID '{WLAN_SSID}' NOT AVAILABLE: {available_networks}", verbose)
                raise WLANConnectionError

            debug_message(f"CONNECTING TO SSID '{WLAN_SSID}'", verbose)

            # connect WLAN interface
            WLAN.connect(WLAN_SSID, WLAN_PASSWORD)
        # if WLAN is not in STA mode
        except (OSError, TypeError) as e:
            debug_message(f"TypeError: {e}", verbose)
            debug_message(f"WLAN CONNECT ERROR - SSID {WLAN_SSID}", verbose)
            raise WLANConnectionError from e
        try: # 30 second timeout
            debug_message("WAITING FOR WLAN CONNECTION", verbose)
            await_timeout = iter(range(30))
            while next(await_timeout)>= 0:
                debug_message(f"WLAN STATUS: {WLAN.status()}", verbose)
                if (WLAN.status() == network.STAT_GOT_IP) or WLAN.isconnected():
                    break
                sleep(1)
        except StopIteration:
            debug_message(f"FAILED TO CONNECT - SSID: {WLAN_SSID} | STATUS: {WLAN.status()}", verbose)
            raise


def access_point_reset(
        WLAN: network.WLAN, verbose: bool
    ) -> tuple[network.WLAN, int]:
    """Creates a WLAN instance in AP mode, configures SSID & password and
    activates the instance.

    Args:
        AP_SSID (str): AP SSID
        AP_PASSWORD (str): AP password
        debug (bool): Enable verbose debug messages

    Returns:
        network.WLAN
    """
    WLAN.disconnect()
    deactivate_interface(WLAN, verbose)
    WLAN.deinit()

    WLAN = network.WLAN(network.AP_IF)
    AP_SSID = dynamic_get_secret("AP_SSID")
    AP_PASSWORD = dynamic_get_secret("AP_PASSWORD")
    WLAN.config(ssid=AP_SSID, password=AP_PASSWORD)
    activate_interface(WLAN, verbose)
    return WLAN, network.AP_IF


def get_network_interface(verbose: bool = False) -> tuple[network.WLAN, int]:
    """Get a network interface instance, which is initialised in STA or AP 
    mode, depending on env/secrets file credentials and connection status.

    STA Mode
    --------
    1. WLAN_SSID & WLAN_PASSWORD variables set in env/secrets
    2. WLAN connection with WLAN_SSID & WLAN_PASSWORD

    AP Mode
    --------
    1. WLAN_SSID & WLAN_PASSWORD variables not set | WLAN connection fails
    2. AP SSID is PICO-W-[UNIQUE ID] e.g. 'PICO-W-E66161234567890B'
    3. AP PASSWORD is [UNIQUE ID] e.g. 'E66161234567890B'
    4. Check device IP on connection to SSID via PC/mobile

    Interface enumerations:
        network.STA_IF | WLAN.IF_STA (0) - Client
        network.AP_IF | WLAN.IF_AP (1) - Access point

    Status enumerations:
        network.STAT_WRONG_PASSWORD (-3)
        network.STAT_NO_AP_FOUND (-2)
        network.STAT_CONNECT_FAIL (-1)
        network.STAT_IDLE (0)
        network.STAT_CONNECTING (1)
        network.STAT_GOT_IP (3)

    Args:
        verbose (bool): Enable verbose debug messages

    Returns:
        tuple[network.WLAN, network.STA_IF | network.AP_IF]
    """
    debug_message("INITIALISE NETWORK WLAN INSTANCE", verbose)

    WLAN_SSID = dynamic_get_secret("WLAN_SSID")
    WLAN_PASSWORD = dynamic_get_secret("WLAN_PASSWORD")

    AP_SSID = dynamic_get_secret("AP_SSID")
    AP_PASSWORD = dynamic_get_secret("AP_PASSWORD")

    # initial declaration of AP SSID & PASSWORD based on unique ID
    if (AP_SSID is None) or (AP_PASSWORD is None):
        debug_message("SETTING AP_SSID & AP_PASSWORD", verbose)
        # Pico W unique ID - e.g. E66161234567890B, (8 bytes in length)
        PICO_ID = binascii.hexlify(machine.unique_id()).decode().upper()
        # SSID: PICO-W-E66161234567890B, KEY: E66161234567890B
        AP_SSID = f"PICO-W-{PICO_ID}"
        AP_PASSWORD = PICO_ID

        # write both values to the env/secrets file
        dynamic_set_secret("AP_SSID", AP_SSID)
        dynamic_set_secret("AP_PASSWORD", AP_PASSWORD)
    
    # select WLAN instance mode based on credential values
    if WLAN_SSID is None or len(WLAN_SSID) < 1:
        # reset WLAN secrets
        dynamic_set_secret("WLAN_SSID", None)
        dynamic_set_secret("WLAN_PASSWORD", None)
        debug_message("SETTING WLAN MODE TO AP", verbose)
        WLAN_MODE = network.AP_IF
    else:
        WLAN_MODE = network.STA_IF
        debug_message("SETTING WLAN MODE TO STA", verbose)
    
    # create WLAN instance
    WLAN = network.WLAN(WLAN_MODE)
    # config WLAN AP with SSID & KEY values 
    WLAN.config(ssid=AP_SSID, password=AP_PASSWORD, pm=0xa11140)

    activate_interface(WLAN, verbose)

    # attempt WLAN interface connection 
    try:
        # successful STA mode connection
        connect_interface(WLAN, verbose)
        debug_message(f"WLAN CONNECTION SUCCESSFUL: {WLAN_SSID}", verbose)
        return WLAN, WLAN_MODE
    except WLANConnectionError:
        WLAN, WLAN_MODE = access_point_reset(WLAN, verbose)
        return WLAN, WLAN_MODE
    except StopIteration:
        # WLAN connection timed out
        debug_message(f"WLAN CONNECTION TO SSID {WLAN_SSID} TIMEOUT", verbose)
        debug_message("SWITCHING TO AP MODE", verbose)
        WLAN, WLAN_MODE = access_point_reset(WLAN, verbose)
        return WLAN, WLAN_MODE


def connection_issue(WLAN: network.WLAN, WLAN_MODE: int) -> bool:
    """Test for connection issue.

    Args:
        WLAN (network.WLAN): _description_
        verbose (bool): Enable verbose debug messages

    Returns:
        bool: True if WLAN is in AP mode or if WLAN is in STA mode and not
            connected to a WiFi access point, else False.
    """
    return (
        (WLAN_MODE == WLAN.IF_AP) or 
        (WLAN_MODE == WLAN.IF_STA and not WLAN.isconnected())
    )
