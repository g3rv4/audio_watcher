from CoreFoundation import CFRunLoopRun, CFRunLoopStop, CFRunLoopGetCurrent
from CoreAudio import (
    AudioObjectAddPropertyListener,
    AudioObjectRemovePropertyListener,
    AudioObjectGetPropertyData,
    AudioObjectPropertyAddress,
    kAudioHardwarePropertyDefaultInputDevice,
    kAudioDevicePropertyDeviceIsRunningSomewhere,
    kAudioObjectPropertyScopeGlobal,
    kAudioObjectPropertyElementMain,
    kAudioObjectSystemObject,
    kAudioHardwareNoError,
)
from AVFoundation import AVCaptureDevice, AVMediaTypeAudio
import struct
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

_current_device_id = None
_mic_is_running = None


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


def get_default_input_device_id():
    """Get the AudioObjectID of the current default input device."""
    addr = AudioObjectPropertyAddress(
        mSelector=kAudioHardwarePropertyDefaultInputDevice,
        mScope=kAudioObjectPropertyScopeGlobal,
        mElement=kAudioObjectPropertyElementMain,
    )
    status, size, data = AudioObjectGetPropertyData(
        kAudioObjectSystemObject, addr, 0, [], 4, None
    )
    if status != kAudioHardwareNoError:
        log.error(f"Failed to get default input device ID, status: {status}")
        return None
    return struct.unpack("<I", data)[0]


def get_device_is_running(device_id):
    """Query whether the given audio device is currently being used."""
    addr = AudioObjectPropertyAddress(
        mSelector=kAudioDevicePropertyDeviceIsRunningSomewhere,
        mScope=kAudioObjectPropertyScopeGlobal,
        mElement=kAudioObjectPropertyElementMain,
    )
    status, size, data = AudioObjectGetPropertyData(
        device_id, addr, 0, [], 4, None
    )
    if status != kAudioHardwareNoError:
        log.error(f"Failed to get IsRunningSomewhere for device {device_id}, status: {status}")
        return None
    return struct.unpack("<I", data)[0] != 0


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


def _register_running_listener(device_id):
    addr = AudioObjectPropertyAddress(
        mSelector=kAudioDevicePropertyDeviceIsRunningSomewhere,
        mScope=kAudioObjectPropertyScopeGlobal,
        mElement=kAudioObjectPropertyElementMain,
    )
    status = AudioObjectAddPropertyListener(
        device_id, addr, _on_property_changed, None
    )
    if status != kAudioHardwareNoError:
        log.error(f"Failed to add IsRunning listener on device {device_id}, status: {status}")
    else:
        log.info(f"Registered IsRunning listener on device {device_id}")


def _unregister_running_listener(device_id):
    addr = AudioObjectPropertyAddress(
        mSelector=kAudioDevicePropertyDeviceIsRunningSomewhere,
        mScope=kAudioObjectPropertyScopeGlobal,
        mElement=kAudioObjectPropertyElementMain,
    )
    status = AudioObjectRemovePropertyListener(
        device_id, addr, _on_property_changed, None
    )
    if status != kAudioHardwareNoError:
        log.warning(f"Failed to remove IsRunning listener from device {device_id}, status: {status}")


@objc.callbackFor(AudioObjectAddPropertyListener)
def _on_property_changed(objectID, numAddresses, addresses, clientData):
    if objectID == kAudioObjectSystemObject:
        _handle_device_change()
    else:
        _handle_running_change(objectID)
    return 0  # noErr


def _handle_device_change():
    global _current_device_id, _mic_is_running

    time.sleep(0.1)  # Let audio subsystem settle

    new_device_id = get_default_input_device_id()
    input_name = get_input_device_name()
    log.info(f"Default input device changed: {input_name} (ID: {new_device_id})")

    if _current_device_id is not None and _current_device_id != new_device_id:
        _unregister_running_listener(_current_device_id)

    if new_device_id is not None and new_device_id != _current_device_id:
        _register_running_listener(new_device_id)

    _current_device_id = new_device_id

    if new_device_id is not None:
        is_running = get_device_is_running(new_device_id)
        _mic_is_running = is_running
        log.info(f"Microphone is {'IN USE' if is_running else 'not in use'}")

    trigger_macro()


def _handle_running_change(device_id):
    global _mic_is_running

    is_running = get_device_is_running(device_id)
    if is_running is None:
        return

    if is_running != _mic_is_running:
        _mic_is_running = is_running
        input_name = get_input_device_name()
        if is_running:
            log.info(f"Microphone started: {input_name} (device {device_id})")
        else:
            log.info(f"Microphone stopped: {input_name} (device {device_id})")
        trigger_macro()


def start():
    global _current_device_id, _mic_is_running

    def signal_handler(_sig, _frame):
        log.info("Received signal to stop, shutting down...")
        if _current_device_id is not None:
            _unregister_running_listener(_current_device_id)
        CFRunLoopStop(CFRunLoopGetCurrent())
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Get initial device and state
    _current_device_id = get_default_input_device_id()
    input_name = get_input_device_name()
    log.info(f"Initial input device: {input_name} (ID: {_current_device_id})")

    if _current_device_id is not None:
        _mic_is_running = get_device_is_running(_current_device_id)
        log.info(f"Microphone is {'IN USE' if _mic_is_running else 'not in use'}")
        _register_running_listener(_current_device_id)

    # Listen for default input device changes
    device_change_addr = AudioObjectPropertyAddress(
        mSelector=kAudioHardwarePropertyDefaultInputDevice,
        mScope=kAudioObjectPropertyScopeGlobal,
        mElement=kAudioObjectPropertyElementMain,
    )
    AudioObjectAddPropertyListener(
        kAudioObjectSystemObject, device_change_addr, _on_property_changed, None
    )

    trigger_macro()

    log.info("Monitoring input device changes and microphone usage. Press Ctrl+C to stop.")
    CFRunLoopRun()


if __name__ == "__main__":
    start()
