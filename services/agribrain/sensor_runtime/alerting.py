import sys

def dispatch_sensor_alert(device_id: str, alert_type: str, message: str) -> None:
    """Dispatch telemetry alerts to the systems diagnostic console (sys.stderr)."""
    sys.stderr.write(
        f"[ALERT] Device: {device_id} | Type: {alert_type} | Message: {message}\n"
    )
