from CoreFoundation import CFRunLoopRun, CFRunLoopStop, CFRunLoopGetCurrent
from CoreAudio import (
    AudioHardwareAddPropertyListener,
    kAudioHardwarePropertyDevices,
)
from AVFoundation import AVCaptureDevice, AVMediaTypeAudio
import subprocess
import objc
import time
import logging
import signal
import sys

# Configure logging with timestamp
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)

_last_devices = None


def get_current_devices():
    """Get the current list of audio input device names using CoreAudio."""
    try:
        devices = AVCaptureDevice.devicesWithMediaType_(AVMediaTypeAudio)
        return set(device.localizedName() for device in devices)
    except Exception as e:
        log.info(f"Error getting devices: {e}")
        return set()


def on_devices_changed():
    global _last_devices

    def trigger_macro():
        subprocess.Popen(
            [
                "osascript",
                "-e",
                'tell application "Keyboard Maestro Engine" to do script "Devices changed"',
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    # Wait for the audio subsystem to settle before querying devices
    time.sleep(0.1)

    # Get current devices
    current_devices = get_current_devices()

    # First run - just store the device list
    if _last_devices is None:
        _last_devices = current_devices
        log.info(f"Initial devices: {sorted(current_devices)}")
        trigger_macro()
        return

    # Check if devices actually changed
    if current_devices == _last_devices:
        # print("Property change but no device list change - ignoring")
        return

    added = current_devices - _last_devices
    removed = _last_devices - current_devices
    if added:
        log.info(f"Added: {sorted(added)}")
    if removed:
        log.info(f"Removed: {sorted(removed)}")
    _last_devices = current_devices

    trigger_macro()


@objc.callbackFor(AudioHardwareAddPropertyListener)
def _callback(_addr, _data):
    on_devices_changed()
    return 0  # noErr


def start():
    # Set up signal handlers for graceful shutdown
    def signal_handler(_sig, _frame):
        log.info("Received signal to stop, shutting down...")
        CFRunLoopStop(CFRunLoopGetCurrent())
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    on_devices_changed()
    AudioHardwareAddPropertyListener(kAudioHardwarePropertyDevices, _callback, None)
    log.info("Audio watcher started. Press Ctrl+C to stop.")
    CFRunLoopRun()


if __name__ == "__main__":
    start()
