"""Tool for Windows system preferences via user-domain Registry (`HKCU`) settings (never admin/HKLM)."""

from __future__ import annotations

from ..safety import guarded_run_argv, succeeded
from ..state import record_change

_TYPE_MAP = {
    "string": "String",
    "dword": "DWord",
    "int": "DWord",
    "bool": "DWord",
}


def set_windows_registry(key_path: str, value_name: str, value: str, value_type: str = "string") -> str:
    """Write one user-domain Windows Registry setting (e.g. Dark mode, Explorer options).
    
    key_path: e.g. "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize"
    value_name: e.g. "AppsUseLightTheme"
    value: e.g. "0" (for Dark Mode) or "1" (for Light Mode)
    value_type: "string", "dword", "int", "bool"
    """
    if not key_path.upper().startswith(("HKCU:\\", "HKLM:\\SOFTWARE\\CLASSES")):
        if key_path.upper().startswith("HKLM"):
            return "REFUSED: only user-domain (HKCU) settings are allowed."

    vt = value_type.lower()
    reg_type = _TYPE_MAP.get(vt, "String")
    
    # Convert boolean string representations to int (0/1) for DWord
    final_val = value
    if vt == "bool" or reg_type == "DWord":
        v_low = str(value).lower()
        if v_low in ("true", "yes", "1"):
            final_val = "1"
        elif v_low in ("false", "no", "0"):
            final_val = "0"

    # Use PowerShell Set-ItemProperty
    ps_command = (
        f"if (!(Test-Path '{key_path}')) {{ New-Item -Path '{key_path}' -Force | Out-Null }}; "
        f"Set-ItemProperty -Path '{key_path}' -Name '{value_name}' -Value '{final_val}' -Type {reg_type}"
    )

    result = guarded_run_argv(
        ["powershell", "-NoProfile", "-Command", ps_command],
        purpose=f"Windows registry {key_path} -> {value_name}",
    )

    if succeeded(result):
        note = record_change(
            "Windows preferences",
            f"`{key_path}` `{value_name}` = {final_val} _({reg_type})_",
            f"set {key_path} {value_name} = {final_val}",
        )
        result += f"\n{note}"
    return result
