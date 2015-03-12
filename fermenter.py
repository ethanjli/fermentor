#!/usr/bin/env python2
"""
Drives an Arduino to control a fermenter.
"""

import time
from datetime import datetime
from array import array
import numpy as np
from Arduino import Arduino
import threading
from threading import Thread
import signal
import sys

###############################################################################
# PARAMETERS
###############################################################################
# Pins
SENSOR_PINS = {
    "phototransistor": 0,
    "thermometer": 5,
}
ACTUATOR_PINS = {
    "impeller motor": 10,
    "heater fan": 3,
    "heater": 5,
    "red led": 9,
    "green led": 7,
}

# Light sensing
LOW_PASS_FILTER_TAU = 0.016 # (s): the RC constant of the low pass filter
STEADY_STATE_TAUS = 30 # number of taus to wait to reach steady state
FILTER_STEADY_STATE_TIME = LOW_PASS_FILTER_TAU * STEADY_STATE_TAUS
LIGHT_MEASUREMENT_INTERVAL = 10 # (sec): time to wait between measurements

# Light noise filtering
LIGHT_SAMPLES_PER_ACQUISITION = 10
LIGHT_SAMPLE_INTERVAL = 0.1 # (sec): time to wait between each sampling
LIGHT_OUTLIER_THRESHOLD = 50 # maximum allowed deviation from median
LIGHT_ACQUISITIONS_PER_MEASUREMENT = 5 # robustness to ambient light variation

# Temperature noise filtering
TEMP_SAMPLES_PER_ACQUISITION = 10
TEMP_SAMPLE_INTERVAL = 0.5 # (sec): time to wait between each sampling
TEMP_OUTLIER_THRESHOLD = 20 # (deg C): maximum allowed deviation from median

# Temperature control
HEAT_LOSS = 9.3 # (Watts): rate of heat loss at 37 deg C
MAX_HEATING = 14.9 # (Watts): rate at which TEC supply heat
SETPOINT = 37.5 # (deg C): target temperature to maintain
HEATER_SETPOINT_DUTY = HEAT_LOSS / MAX_HEATING # stable duty cycle at setpoint
GAIN = HEATER_SETPOINT_DUTY - 1 # proportional gain
TEMP_MEASUREMENT_INTERVAL = 10 # (sec): time to wait between measurements

# Impeller
IMPELLER_DEFAULT_DUTY = 0.2 # default duty cycle of the impeller

# Idling
IDLE_CHECK_INTERVAL = 5 # (sec): time to wait between wakeup checks

# Constants
SERIAL_RATE = "115200" # (baud) rate of USB communication
PWM_MAX = 255
ARDUINO_PORT = "/dev/ttyACM0"
ANALOG_PIN_OFFSET = 15 # the formal pin number corresponding to pin A0

###############################################################################
# STATELESS FUNCTIONS
###############################################################################
def duty_cycle_to_pin_val(duty_cycle):
    """Return the pin value corresponding to a given duty cycle"""
    return round(duty_cycle * PWM_MAX)
def pin_val_to_temp(pin_value):
    """Return the deg C temperature represented by the input pin value."""
    return 0.174 * pin_value + 0.764
def temp_to_heating_control_effort(temp):
    """Return the duty cycle needed to reach the setpoint temperature."""
    raw_duty = HEATER_SETPOINT_DUTY + GAIN * (temp - SETPOINT)
    return max(0, min(1, raw_duty))
def discard_temp_outliers(samples):
    """Filter outliers out from a set of temperature samples.
    Assumes that the set of temperature samples is acquired when fluid and
    sensor are at quasi-steady state, and thus wild fluctuations in temperature
    are physically nonsensical.

    Arguments:
        data: a Numpy array of temperature measurements, in deg C.
        threshold: the maximum difference in temperature from the median for a
            given sample to be considered a valid sample.
    """
    distances = np.abs(samples - np.median(samples))
    return samples[distances <= TEMP_OUTLIER_THRESHOLD]
def discard_light_outliers(samples):
    """Filter outliers out from a set of light samples.
    Assumes that the set of light samples is acquired when fluid and
    phototransistor are at quasi-steady state, and thus wild fluctuations in
    light correspond to ambient noise < 10 Hz.

    Arguments:
        data: a Numpy array of temperature measurements, in deg C.
        threshold: the maximum difference in light from the median for a
            given sample to be considered a valid sample.
    """
    distances = np.abs(samples - np.median(samples))
    return samples[distances <= LIGHT_OUTLIER_THRESHOLD]
def get_abs(transmittance, full_transmittance):
    """Normalizes a transmittance against a calibration value."""
    return float(full_transmittance - transmittance) / full_transmittance

###############################################################################
# ARDUINO SUBROUTINES
###############################################################################
def connect():
    """Initializes a connection to the Arduino"""
    a = Arduino(SERIAL_RATE, port=ARDUINO_PORT)
    print("Connected.")
    return a
def set_pin_modes(a):
    """Initializes pin modes for all pins"""
    for pin in SENSOR_PINS.values():
        a.pinMode(pin + ANALOG_PIN_OFFSET, "INPUT")
    for pin in ACTUATOR_PINS.values():
        a.pinMode(pin, "OUTPUT")
def turn_off_actuators(a, arduino_lock):
    """Turns off all actuators"""
    with arduino_lock:
        for pin in ACTUATOR_PINS.values():
            a.digitalWrite(pin, "LOW")
def turn_off_leds(a, arduino_lock):
    """Turns off all LEDs"""
    with arduino_lock:
        a.digitalWrite(ACTUATOR_PINS["red led"], "LOW")
        a.digitalWrite(ACTUATOR_PINS["green led"], "LOW")
def initialize_default_actuators(a, arduino_lock):
    """Turns on open-loop actuators to default states"""
    with arduino_lock:
        a.digitalWrite(ACTUATOR_PINS["heater fan"], "HIGH")
        a.analogWrite(ACTUATOR_PINS["impeller motor"],
                duty_cycle_to_pin_val(IMPELLER_DEFAULT_DUTY))
def set_impeller(a, arduino_lock, duty):
    """Sets the impeller motor duty cycle"""
    with arduino_lock:
        a.analogWrite(ACTUATOR_PINS["impeller motor"],
                      duty_cycle_to_pin_val(duty))

###############################################################################
# DATA ACQUISITION & PROCESSING
###############################################################################
def acquire_pin(a, pin, nsamples, sample_interval, arduino_lock):
    """Acquires a pin value as sampled over a time interval.
    Returns as a Numpy array.

    Arguments:
        pin: the pin from which to read
        nsamples: the number of samples to acquire
        sample_interval: the time to wait between samples
    """
    samples = array('i')
    for i in range(nsamples):
        if i != 0:
            time.sleep(sample_interval)
        with arduino_lock:
            samples.append(a.analogRead(pin))
    return np.array(samples)
def acquire_temp(a, arduino_lock):
    """Returns the temperature as sampled over a short time interval.
    Discards outliers and returns the mean of the remaining samples.
    Temperature is returned as a pin value.
    """
    samples = acquire_pin(a, SENSOR_PINS["thermometer"],
            TEMP_SAMPLES_PER_ACQUISITION, TEMP_SAMPLE_INTERVAL, arduino_lock)
    return np.mean(discard_temp_outliers(samples))
def acquire_light(a, color, arduino_lock):
    """Returns the light intensity as sampled over a short time interval.
    Light intensity is returned as an absolute pin value.
    Turns off the green LED and turns on the LED and waits for filter response
    before sampling.
    Discards outliers and returns the mean of the remaining samples.

    Arguments:
        color: should be either "red", "green", or "ambient"
    """
    turn_off_leds(a, arduino_lock)
    with arduino_lock:
        if color == "red":
            a.digitalWrite(ACTUATOR_PINS["red led"], "HIGH")
        elif color == "green":
            a.digitalWrite(ACTUATOR_PINS["green led"], "HIGH")
    time.sleep(FILTER_STEADY_STATE_TIME)
    samples = acquire_pin(a, SENSOR_PINS["phototransistor"],
            LIGHT_SAMPLES_PER_ACQUISITION, LIGHT_SAMPLE_INTERVAL, arduino_lock)
    turn_off_leds(a, arduino_lock)
    return np.mean(discard_light_outliers(samples))
def measure_temp(a, arduino_lock):
    """Returns the temperature as measured over a short time.
    Temperature is returned in deg C.
    """
    return pin_val_to_temp(acquire_temp(a, arduino_lock))
def measure_transmittances(a, arduino_lock):
    """Returns normalized light intensities as acquired over an extended time.
    Light intensity is normalized to the ambient light.
    Acquisition of different colors is time multiplexed.
    Returns as a tuple of ambient light, red transmittance, and green
    transmittance.
    """
    acquisitions = {
        "red": array('i'),
        "ambient": array('i'),
        "green": array('i'),
    }
    for _ in range(LIGHT_ACQUISITIONS_PER_MEASUREMENT):
        for color in acquisitions.keys():
            light = acquire_light(a, color, arduino_lock)
            if not np.isnan(light):
                acquisitions[color].append(int(light))
    ambient = np.mean(discard_light_outliers(np.array(acquisitions["ambient"])))
    red = np.mean(discard_light_outliers(np.array(acquisitions["red"])))
    green = np.mean(discard_light_outliers(np.array(acquisitions["green"])))
    return (ambient, ambient - red, ambient - green)

###############################################################################
# DATA LOGGING
###############################################################################
def record_heat_control(a, arduino_lock):
    """Returns a heat control record.
    Also adjusts the heating control effort and records that.
    """
    temp = measure_temp(a, arduino_lock)
    heater_duty_cycle = temp_to_heating_control_effort(temp)
    end_time = datetime.now()
    if np.isnan(temp):
        return None
    else:
        return (end_time, temp, heater_duty_cycle)
def record_transmittances(a, arduino_lock):
    """Returns a transmittances record."""
    (ambient, red, green) = measure_transmittances(a, arduino_lock)
    end_time = datetime.now()
    if np.isnan(ambient) or np.isnan(red) or np.isnan(green):
        return None
    else:
        return (end_time, ambient, red, green)
def construct_records():
    """Returns an empty records dictionary."""
    records = {
        "start": datetime.now(),
        "stop": None,
        "temp": [None],
        "heater": [None],
        "impeller": [None],
        "optics": {
            "calibration": {
                "red": None,
                "green": None,
            },
            "calibrations": [None],
            "ambient": [None],
            "red": [None],
            "green": [None],
        },
    }
    return records
def reinitialize_records(records):
    """Clears everything in records.
    Sets the start time of to be the current time.
    """
    records["start"] = datetime.now()
    records["stop"] = None
    records["temp"][:] = [None]
    records["heater"][:] = [None]
    records["impeller"][:] = [None]
    records["optics"]["calibration"]["red"] = None
    records["optics"]["calibration"]["green"] = None
    records["optics"]["calibrations"][:] = [None]
    records["optics"]["ambient"][:] = [None]
    records["optics"]["red"][:] = [None]

###############################################################################
# THREADS
###############################################################################
def construct_locks():
    """Returns an initial locks dictionary."""
    locks = {
        "arduino": threading.Lock(),
        "records": threading.Lock(),
        "impeller motor": threading.Lock(),
        "heater": threading.Lock(),
        "leds": threading.Lock(),
    }
    return locks
def construct_events():
    """Returns an initial events dictionary with events in initial states."""
    events = {
        "fermenter idle": threading.Event(),
        "calibrate": threading.Event(),
    }
    events["fermenter idle"].set()
    events["calibrate"].set()
    return events
def start_fermenter(a, records, locks, idle_event):
    """Starts fermenter operation."""
    print("Starting...")
    idle_event.clear()
    with locks["records"]:
        reinitialize_records(records)
        with locks["impeller motor"]:
            records["impeller"].append((datetime.now(), IMPELLER_DEFAULT_DUTY))
            initialize_default_actuators(a, locks["arduino"])
    print("Started.")
def stop_fermenter(a, records, locks, idle_event):
    """Stops fermenter operation."""
    print("Preparing to stop...")
    idle_event.set()
    with locks["leds"]:
        turn_off_leds(a, locks["arduino"])
    with locks["records"]:
        records["impeller"].append((datetime.now(),
                                    records["impeller"][-1][1]))
        records["heater"].append((datetime.now(), records["heater"][-1][1]))
        with locks["impeller motor"] and locks["heater"]:
            turn_off_actuators(a, locks["arduino"])
            records["impeller"].append((datetime.now(), 0))
            records["heater"].append((datetime.now(), 0))
        records["stop"] = datetime.now()
    print("Stopped.")
def monitor_temp(a, records, locks, idle_event):
    """Continuously monitor and record fluid temperature and heater state.
    Also adjust heater based on temperature control information.
    """
    while True:
        if not idle_event.is_set():
            record = record_heat_control(a, locks["arduino"])
            if record:
                print(record)
                with locks["arduino"] and locks["heater"]:
                    a.analogWrite(ACTUATOR_PINS["heater"],
                                  duty_cycle_to_pin_val(record[2]))
                with locks["records"]:
                    records["temp"].append((record[0], record[1]))
                    records["heater"].append((record[0], record[2]))
                idle_event.wait(TEMP_MEASUREMENT_INTERVAL)
        else:
            time.sleep(IDLE_CHECK_INTERVAL)
def monitor_optics(a, records, locks, calibrate_event, idle_event):
    """Continuously monitor and record fluid optical properties"""
    while True:
        if not idle_event.is_set():
            with locks["leds"]:
                record = record_transmittances(a, locks["arduino"])
            if record:
                with locks["records"]:
                    if calibrate_event.is_set():
                        records["optics"]["calibrations"].append((record[0],
                                                                  record[2],
                                                                  record[3]))
                        records["optics"]["calibration"]["red"] = record[2]
                        records["optics"]["calibration"]["green"] = record[3]
                        calibrate_event.clear()
                    records["optics"]["ambient"].append((record[0], record[1]))
                    records["optics"]["red"].append((record[0], record[2]))
                    records["optics"]["green"].append((record[0], record[3]))
                idle_event.wait(LIGHT_MEASUREMENT_INTERVAL)
        else:
            time.sleep(IDLE_CHECK_INTERVAL)

###############################################################################
# MAIN
###############################################################################
def interrupt_handler(signal_num, _):
    sys.exit(signal_num)
def run_fermenter():
    a = connect()
    set_pin_modes(a)
    signal.signal(signal.SIGINT, interrupt_handler)
    records = construct_records()
    locks = construct_locks()
    events = construct_events()
    temp_monitor = Thread(target=monitor_temp, name="temp",
                          args=(a, records, locks, events["fermenter idle"]))
    optics_monitor = Thread(target=monitor_optics, name="optics",
                            args=(a, records, locks, events["calibrate"],
                                  events["fermenter idle"]))
    threads = {
        "temp": temp_monitor,
        "optics": optics_monitor,
    }
    threads["temp"].daemon = True
    threads["optics"].daemon = True
    turn_off_leds(a, locks["arduino"])
    turn_off_actuators(a, locks["arduino"])
    start_fermenter(a, records, locks, events["fermenter idle"])
    threads["temp"].start()
    #threads["optics"].start()
    return (a, records, locks, events, threads)

if __name__ == "__main__":
    (a, records, locks, events, threads) = run_fermenter()
    for thread in threads.values():
        signal.pause()
