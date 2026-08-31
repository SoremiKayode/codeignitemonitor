import subprocess

from netwatch.monitors.network.carrier import WindowsCarrierDetector, parse_ready_info


def completed(command, **_kwargs):
    output = "" if "interfaces" in command else "Provider Name : MTN Nigeria\n"
    if "interfaces" in command:
        output = "Interface Name : Cellular\nState : Connected\n"
    return subprocess.CompletedProcess(command, 0, output, "")


def test_parse_ready_info_extracts_provider_name() -> None:
    assert parse_ready_info("Provider Name : Airtel NG\n") == "Airtel NG"
    assert parse_ready_info("No provider here") is None


def test_windows_detector_reports_only_windows_reported_carrier() -> None:
    carrier = WindowsCarrierDetector(completed).detect()
    assert carrier.provider_name == "MTN Nigeria"
    assert carrier.interface_name == "Cellular"
    assert carrier.source == "Windows mobile broadband"
