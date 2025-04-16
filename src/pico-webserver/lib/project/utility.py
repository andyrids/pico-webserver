"""Utility module containing MicroPython helper functions.

Author: Andrew Ridyard.

License: GNU General Public License v3 or later.

Copyright (C): 2024.

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
    debug_message: Print debug messages if verbose flag is True.
    debug_network_status: Print specific WLAN status debug message.
    dynamic_get_secret: Read secret from /env/secrets.py.
    dynamic_set_secret: Write secret to /env/secrets.py.
"""

import network
import os
import sys

from io import IOBase, TextIOBase
from typing import Optional, Union

def debug_message(message: str, verbose: bool) -> None:
    """Print verbose debug message if verbose flag is True
    
    Args:
        message (str): Message to print.
        verbose (bool): Message print flag.
    """
    # "{:^30}".format("CENTRED STRING")
    if not verbose:
        return
    print("\n".join([i.strip() for i in message.split("\n")]))


def debug_network_status(
        WLAN: network.WLAN,
        mode: int,
        verbose: bool
    ) -> None:
    """Print verbose WLAN status debug message if verbose flag is True.

    Args:
        WLAN (network.WLAN): WLAN instance.
        mode (str): WLAN instance mode.
        verbose (bool): Message print flag.
    """
    WLAN_MODE_STR = ("STA", "AP")[mode]
    status = WLAN.status()
    active = WLAN.active()
    connected = WLAN.isconnected()

    message = f"""
    WLAN INFO
    ---------
    MODE: {WLAN_MODE_STR}
    STATUS: {status}
    ACTIVE: {active}
    CONNECTED: {connected}
    """

    debug_message(message, verbose)


def create_secrets() -> str:
    """Create an env/secrets file if missing.
    
    Returns:
        env/secrets filename.
    """

    SECRETS_PY = "secrets.py"
    SECRETS_MPY = "secrets.mpy"

    env_directory = os.listdir("env")
    if SECRETS_PY not in env_directory and SECRETS_MPY not in env_directory:
        with open(f"env/{SECRETS_PY}", "w") as secrets:
            secret_lines = ("WLAN_SSID = None", "WLAN_PASSWORD = None")
            secrets.write("\n".join(secret_lines))

    return SECRETS_PY if SECRETS_PY in os.listdir("env") else SECRETS_MPY


def dynamic_get_secret(name: str) -> Union[str, None]:
    """Dynamically import 'env.secrets' and 
    return the secret specified by name.

    Dynamic import allows for changes to secrets.py 
    and updated values being returned on subsequent 
    function calls.

    Args:
        name (str): Name of secret enumeration.

    Returns:
        str | None: Specified secret value or None if empty string.
    """
    exec("import env.secrets", {})
    # use getattr rather than sys.modules["env.secrets"].AP_PASSWORD etc.
    secret = getattr(sys.modules["env.secrets"], name, None)
    del sys.modules["env.secrets"]

    return None if isinstance(secret, str) and secret == "" else secret


def dynamic_set_secret(name: str, value: Optional[str] = None) -> bool:
    """Dynamically set secret variable value in the secrets file.

    Args:
        name (str): Secret name.

        value (Optional[str]): Secret value.

    Returns:
        bool: True if new secret value is not None, else False.
    """
    value = None if isinstance(value, str) and not value else value
    secret = f"{name}={value!r}\n" if value else f"{name}={value}\n"

    secrets_path = f"env/{create_secrets()}"
    with open(secrets_path, "r") as secrets:
        name_found = False
        secret_lines: list[str] = secrets.readlines()
        for i, secret_line in enumerate(secret_lines):
            if name in secret_line:
                secret_lines[i] = secret
                name_found = True
                break
    if not name_found:
        secret_lines.append(secret)

    with open(secrets_path, "w") as secrets:
        secrets.write("".join(secret_lines))

    return value is not None
