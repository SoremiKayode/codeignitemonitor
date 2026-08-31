"""Mobile-carrier detection through Windows' public mobile broadband command."""

from __future__ import annotations

import re
import subprocess
from collections.abc import Callable

from netwatch.core.models import CarrierInfo


def parse_ready_info(output: str) -> str | None:
    """Extract a provider name from `netsh mbn show readyinfo` output."""
    match = re.search(r"^\s*(?:Provider\s+Name|Provider)\s*:\s*(.+?)\s*$", output, re.MULTILINE | re.IGNORECASE)
    return match.group(1).strip() if match else None


class WindowsCarrierDetector:
    """Reports a cellular provider only when Windows exposes it; never guesses from IPs."""

    def __init__(self, run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run) -> None:
        self._run = run

    def detect(self) -> CarrierInfo:
        try:
            interfaces = self._run(["netsh", "mbn", "show", "interfaces"], capture_output=True, text=True, timeout=3, check=False)
        except (OSError, subprocess.SubprocessError):
            return CarrierInfo(None, None, "Windows mobile broadband is unavailable")
        # MBN output is localized. Interface Name is stable enough to use as the command argument.
        name_match = re.search(r"^\s*Interface Name\s*:\s*(.+?)\s*$", interfaces.stdout, re.MULTILINE | re.IGNORECASE)
        if not name_match:
            return CarrierInfo(None, None, "No Windows mobile broadband interface")
        interface = name_match.group(1).strip()
        try:
            ready = self._run(["netsh", "mbn", "show", "readyinfo", f"interface={interface}"], capture_output=True, text=True, timeout=3, check=False)
        except (OSError, subprocess.SubprocessError):
            return CarrierInfo(None, interface, "Mobile interface found; provider unavailable")
        provider = parse_ready_info(ready.stdout)
        return CarrierInfo(provider, interface, "Windows mobile broadband")
