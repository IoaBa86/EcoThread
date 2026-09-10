"""Windows "start with Windows" toggle via the current user's Run registry key."""

import sys
import winreg

RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE_NAME = "EcoThread"


def _launch_command() -> str:
    if getattr(sys, "frozen", False):
        # Running as a PyInstaller-built executable: launch it directly.
        return f'"{sys.executable}"'
    # Running from source: relaunch with the same interpreter and script.
    return f'"{sys.executable}" "{sys.argv[0]}"'


def is_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, RUN_VALUE_NAME)
            return True
    except FileNotFoundError:
        return False


def set_enabled(enabled: bool):
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH) as key:
        if enabled:
            winreg.SetValueEx(key, RUN_VALUE_NAME, 0, winreg.REG_SZ, _launch_command())
        else:
            try:
                winreg.DeleteValue(key, RUN_VALUE_NAME)
            except FileNotFoundError:
                pass
