#!/usr/bin/python3
from gevent import monkey
monkey.patch_all()

from threading import Thread
import time
from datetime import datetime
import logging
from flask import Flask, send_from_directory
from flask.ext.socketio import SocketIO, emit
import pygal
from pygal import XY, Config
import os
import fermenter

logging.basicConfig()

###############################################################################
# PARAMETERS
###############################################################################
STATS_INTERVAL = 2 # (sec): time to wait between updating stats
PLOTS_DIR = "static/plots/"
PLOTS_INTERVAL = 20 # (sec): time to wait between updating plots
plot_config = Config()
plot_config.x_title = "Time (h)"
plot_config.value_formatter = lambda x: "%.2f" %x
plot_config.stroke = True
plot_config.fill = True
plot_config.width = 600
plot_config.height = 400
plot_config.legend_at_bottom =True

###############################################################################
# GLOBALS
###############################################################################
app = Flask(__name__)
socketio = SocketIO(app)
threads = {}

###############################################################################
# EVENTS
###############################################################################
@socketio.on("socket event", namespace="/socket")
def handle_socket_event(message):
    print(message["data"])
@socketio.on("fermenter stop", namespace="/socket")
def handle_stop(message):
    if not events["fermenter idle"].is_set():
        events["fermenter idle"].set()
        fermenter.stop_fermenter(a, records, locks, events["fermenter idle"])
@socketio.on("fermenter start", namespace="/socket")
def handle_start(message):
    if events["fermenter idle"].is_set():
        events["fermenter idle"].clear()
        fermenter.start_fermenter(a, records, locks, events["fermenter idle"])

###############################################################################
# THREADS
###############################################################################
def update_stats(records, locks):
    while True:
        with locks["records"]:
            stats = {
                "start": records["start"],
                "stop": records["stop"],
                "now": datetime.now(),
                "since": ((datetime.now() - records["start"]).total_seconds() /
                          3600),
                "temp": records["temp"][-1],
                "heater": records["heater"][-1],
                "impeller": records["impeller"][-1],
                "optics": {
                    "calibration": {
                        "red": records["optics"]["calibration"]["red"],
                        "green": records["optics"]["calibration"]["green"],
                    },
                    "calibrations": records["optics"]["calibrations"],
                    "ambient": records["optics"]["ambient"][-1],
                    "red": records["optics"]["red"][-1],
                    "green": records["optics"]["green"][-1],
                },
            }
        socketio.emit("stats update", stats, namespace="/socket")
        time.sleep(STATS_INTERVAL)
def trans_to_abs(calib, transmittances):
    """Converts a list of transmittances to a list of absorbances."""
    absorbances = []
    for entry in transmittances:
        if entry and calib:
            absorbances.append((entry[0], fermenter.get_abs(calib, entry[1])))
    return absorbances
def datetime_to_hours(start, series):
    """Converts datetimes into hours."""
    converted = []
    for entry in series:
        if entry:
            converted.append(((entry[0] - start).total_seconds() / 3600,
                              entry[1]))
    return converted
def plot_optics(records, locks):
    optics_plot = XY(plot_config)
    optics_plot.title = "Optical Measurements"
    optics_plot.y_title = "Relative Absorbance"
    with locks["records"]:
        calib_red = records["optics"]["calibration"]["red"]
        red = records["optics"]["red"]
        calib_green = records["optics"]["calibration"]["red"]
        green = records["optics"]["red"]
        red_abs = trans_to_abs(calib_red, red)
        green_abs = trans_to_abs(calib_green, green)
        if red_abs:
            optics_plot.add("Red (OD)", datetime_to_hours(records["start"],
                                                          red_abs))
        if green_abs:
            optics_plot.add("Green", datetime_to_hours(records["start"],
                                                       green_abs))
    return optics_plot
def plot_temp(records, locks):
    temp_plot = XY(plot_config)
    temp_plot.title = "Temperature"
    temp_plot.y_title = "Temperature (deg C)"
    temp_plot.fill = True
    with locks["records"]:
        if records["temp"][-1]:
            temp_plot.add("Temperature", datetime_to_hours(records["start"],
                                                           records["temp"]))
    return temp_plot
def plot_duty_cycles(records, locks):
    temp_plot = XY(plot_config)
    temp_plot.title = "Actuator Duty Cycles"
    temp_plot.y_title = "Duty Cycle (%)"
    with locks["records"]:
        if records["heater"][-1]:
            temp_plot.add("Heater", datetime_to_hours(records["start"],
                                                      records["heater"]))
        if records["impeller"][-1]:
            temp_plot.add("Impeller", datetime_to_hours(records["start"],
                                                        records["impeller"]))
    return temp_plot
def update_plots(records, locks):
    temp_last_update = None
    optics_last_update = None
    duty_cycles_last_update = None
    while True:
        rerender_optics = False
        rerender_temp = False
        rerender_duty_cycles = False
        if records["optics"]["red"][-1]:
            if (not optics_last_update or
                    optics_last_update < records["optics"]["red"][-1][0]):
                optics_last_update = records["optics"]["red"][-1][0]
                rerender_optics = True
        if records["temp"][-1]:
            if (not temp_last_update or
                    temp_last_update < records["temp"][-1][0]):
                temp_last_update = records["temp"][-1][0]
                rerender_temp = True
        if records["heater"][-1]:
            if (not duty_cycles_last_update or
                    duty_cycles_last_update < records["heater"][-1][0]):
                duty_cycles_last_update = records["heater"][-1][0]
                rerender_duty_cycles = True
        if rerender_optics:
            plot_optics(records, locks).render_to_file(PLOTS_DIR +
                                                       "optics.svg")
            socketio.emit("optics plot update", {"time": datetime.now()},
                          namespace="/socket")
        if rerender_temp:
            plot_temp(records, locks).render_to_file(PLOTS_DIR + "temp.svg")
            socketio.emit("temp plot update", {"time": datetime.now()},
                          namespace="/socket")
        if rerender_duty_cycles:
            plot_duty_cycles(records, locks).render_to_file(PLOTS_DIR +
                                                            "duty_cycles.svg")
            socketio.emit("duty cycles plot update", {"time": datetime.now()},
                          namespace="/socket")
        time.sleep(PLOTS_INTERVAL)

###############################################################################
# ROUTES
###############################################################################
@app.route("/")
def index():
    """Deliver the dashboard"""
    global threads
    if "stats" not in threads.keys():
        threads["stats"] = Thread(target=update_stats, name="stats",
                                  args=(records, locks))
        threads["stats"].start()
    if "plot" not in threads.keys():
        threads["plots"] = Thread(target=update_plots, name="plots",
                                  args=(records, locks))
        threads["plots"].start()
    return send_from_directory("static", "dashboard.html")

@app.route("/client.js")
def client():
    """Deliver the client-side scripting"""
    return send_from_directory("static", "client.js")

@app.route("/style.css")
def style():
    """Deliver the client-side styling"""
    return send_from_directory("static", "style.css")

@app.route("/plots/<plot>")
def plots(plot):
    """Deliver the specified plot"""
    return send_from_directory("static/plots/", plot + ".svg")

###############################################################################
# MAIN
###############################################################################
if __name__ == "__main__":
    (a, records, locks, events, threads) = fermenter.run_fermenter()
    socketio.run(app, host='0.0.0.0', port=80)
