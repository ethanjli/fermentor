#!/usr/bin/env python2
"""
Drives an Arduino to control a fermenter.
"""

import time
import datetime
from array import array
import numpy as np
import nanpy

###############################################################################
# PARAMETERS
###############################################################################
# Pins
SENSOR_PINS = {
        "button": 13,
        "phototransistor": 0,
        "thermometer": 4,
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
LIGHT_MEASUREMENT_INTERVAL = 20 # (sec): time to wait between measurements

# Light noise filtering
LIGHT_SAMPLES_PER_ACQUISITION = 10
LIGHT_SAMPLE_INTERVAL = 0.1 # (sec): time to wait between each sampling
LIGHT_OUTLIER_THRESHOLD = 50 # maximum allowed deviation from median
LIGHT_ACQUISITIONS_PER_MEASUREMENT = 10 # robustness to ambient light variation

# Temperature noise filtering
TEMP_SAMPLES_PER_ACQUISITION = 10
TEMP_SAMPLE_INTERVAL = 0.1 # (sec): time to wait between each sampling
TEMP_OUTLIER_THRESHOLD = 0.5 # (deg C): maximum allowed deviation from median

# Temperature control
HEAT_LOSS = 9.3 # (Watts): rate of heat loss at 37 deg C
MAX_HEATING = 14.9 # (Watts): rate at which TEC supply heat
SETPOINT = 37.5 # (deg C): target temperature to maintain
HEATER_SETPOINT_DUTY = HEAT_LOSS / MAX_HEATING # stable duty cycle at setpoint
GAIN = HEATER_SETPOINT_DUTY - 1 # proportional gain
TEMP_MEASUREMENT_INTERVAL = 5 # (sec): time to wait between measurements

# Button pressing
BUTTON_CHECK_INTERVAL = 0.5 # (sec): time to wait between checks of button

# Constants
SERIAL_RATE = "9600" # (baud) rate of USB communication
PWM_MAX = 255

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
    return max(0, min(1, raw_duty))
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
def transmittance_to_absorbance(transmittance, full_transmittance):
    """Normalizes a transmittance against a calibration value."""
    return float(full_transmittance - transmittance) / full_transmittance

###############################################################################
# ARDUINO SUBROUTINES
###############################################################################
def connect():
    """Initializes a connection to the Arduino"""
    return nanpy.ArduinoApi()
def set_pin_modes(a):
    """Initializes pin modes for all pins"""
    for pin in SENSOR_PINS.values():
        a.pinMode(pin, a.INPUT)
    for pin in ACTUATOR_PINS.values():
        a.pinMode(pin, a.OUTPUT)
def turn_off_actuators(a):
    """Turns off all actuators"""
    for pin in ACTUATOR_PINS.values():
        a.digitalWrite(pin, a.LOW)
def turn_off_leds(a):
    """Turns off all LEDs"""
    a.digitalWrite(ACTUATOR_PINS["red led"], a.LOW)
    a.digitalWrite(ACTUATOR_PINS["green led"], a.LOW)

###############################################################################
# DATA ACQUISITION & PROCESSING
###############################################################################
def acquire_pin(a, pin, nsamples, sample_interval):
    """Acquires a pin value as sampled over a time interval.
    Returns as a Numpy array.

    Arguments:
        pin: the pin from which to read
        nsamples: the number of samples to acquire
        sample_interval: the time to wait between samples
    """
    samples = array('I')
    for i in range(nsamples):
        if i != 0:
            time.sleep(sample_interval)
        samples.append(a.analogRead(pin))
    return np.array(samples)
def acquire_temp(a):
    """Returns the temperature as sampled over a short time interval.
    Discards outliers and returns the mean of the remaining samples.
    Temperature is returned as a pin value.
    """
    samples = acquire_pin(a, SENSOR_PINS["thermometer"],
            TEMP_SAMPLES_PER_ACQUISITION, TEMP_SAMPLE_INTERVAL)
    return np.mean(discard_temp_outliers(samples))
def acquire_light(a, color):
    """Returns the light intensity as sampled over a short time interval.
    Light intensity is returned as an absolute pin value.
    Turns off the green LED and turns on the LED and waits for filter response
    before sampling.
    Discards outliers and returns the mean of the remaining samples.

    Arguments:
        color: should be either "red", "green", or "ambient"
    """
    turn_off_leds(a)
    if color == "red":
        a.digitalWrite(ACTUATOR_PINS["red led"], a.HIGH)
    elif color == "green":
        a.digitalWrite(ACTUATOR_PINS["green led"], a.HIGH)
    time.sleep(FILTER_STEADY_STATE_TIME)
    samples = acquire_pin(a, SENSOR_PINS["phototransistor"],
            LIGHT_SAMPLES_PER_ACQUISITION, LIGHT_SAMPLE_INTERVAL)
    turn_off_leds(a)
    return np.mean(discard_light_outliers(samples))
def measure_temp(a):
    """Returns the temperature as measured over a short time.
    Temperature is returned in deg C.
    """
    return pin_val_to_temp(acquire_temp(a))
def measure_transmittances(a):
    """Returns normalized light intensities as acquired over an extended time.
    Light intensity is normalized to the ambient light.
    Acquisition of different colors is time multiplexed.
    Returns as a tuple of ambient light, red transmittance, and green
    transmittance.
    """
    acquisitions = {
            "red": array('I'),
            "ambient": array('I'),
            "green": array'I'),
    }
    for i in range(LIGHT_ACQUISITIONS_PER_MEASUREMENT):
        for color in acquisitions.keys():
            acquisitions[color].append(acquire_light(a, color))
    ambient = np.mean(discard_light_outliers(acquisitions["ambient"]))
    red = np.mean(discard_light_outliers(acquisitions["red"]))
    green = np.mean(discard_light_outliers(acquisitions["green"]))
    return (ambient, ambient - red, ambient - green)

###############################################################################
# DATA LOGGING
###############################################################################
def record_heat_control(a):
    """Returns a heat control record."""
    temp = measure_temp(a)
    heater_duty_cycle = temp_to_heating_control_effort(temp)
    a.analogWrite(ACTUATOR_PINS["heater"],
            duty_cycle_to_pin_val(heater_duty_cycle))
    end_time = datetime.now()
    return (end_time, temp, heater_duty_cycle)
def record_transmittances(a):
    """Returns a transmittances record."""
    (ambient, red, green) = measure_transmittances(a)
    end_time = datetime.now()
    return (end_time, ambient, red, green)

###############################################################################
# THREADS
###############################################################################
def monitor_temp(a, records, idle_event):
    """Continuously monitor and record fluid temperature and heater state"""
    while not idle_event.is_set():
        record = record_heat_control(a)
        records["temperature"].append((record[0], record[1]))
        records["heater"].append((record[0], record[2]))
        idle_event.wait(TEMP_MEASUREMENT_INTERVAL)
def monitor_optics(a, records, idle_event):
    """Continuously monitor and record fluid optical properties"""
    while not idle_event.is_set():
        record = record_transmittances(a)
        records["ambient"].append((record[0], record[1]))
        records["red"].append((record[0], record[2]))
        records["green"].append((record[0], record[3]))
        idle_event.wait(LIGHT_MEASUREMENT_INTERVAL)
def monitor_button(a, records, idle_event):
    """Continuously monitor power button state"""
    while true:
        if a.digitalRead(SENSOR_PINS["button"]):
            idle_event.set()
        else:
            idle_event.clear()
        wait(BUTTON_CHECK_INTERVAL)
