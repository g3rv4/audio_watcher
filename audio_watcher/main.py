from CoreFoundation import CFRunLoopRun, CFRunLoopStop, CFRunLoopGetCurrent
from CoreAudio import (
    AudioHardwareAddPropertyListener,
    kAudioHardwarePropertyDefaultInputDevice,
)
from AVFoundation import AVCaptureDevice, AVMediaTypeAudio
import subprocess
import objc
import time
import logging
import signal
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)

_last_devices = None


def get_input_device_name():
    """Get the name of the current default input device."""
    try:
        default_device = AVCaptureDevice.defaultDeviceWithMediaType_(AVMediaTypeAudio)
        if default_device:
            return default_device.localizedName()
        return None
    except Exception as e:
        log.info(f"Error getting input device: {e}")
        return None


def on_devices_changed():
    global _last_devices

    def trigger_macro():
        subprocess.Popen(
            [
                "osascript",
                "-e",
                'tell application "Keyboard Maestro Engine" to do script "Update Icon"',
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    # Wait for the audio subsystem to settle before querying devices
    time.sleep(0.1)

    input_device = get_input_device_name()
    log.info(f"Current input device: {input_device}")

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
    AudioHardwareAddPropertyListener(
        kAudioHardwarePropertyDefaultInputDevice, _callback, None
    )
    log.info("Monitoring default input device changes. Press Ctrl+C to stop.")
    CFRunLoopRun()


if __name__ == "__main__":
    start()
