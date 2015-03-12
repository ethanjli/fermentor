#!/usr/bin/python2
from gevent import monkey
monkey.patch_all()

from threading import Thread
import time
from datetime import datetime
import logging
from flask import Flask, send_from_directory
from flask.ext.socketio import SocketIO, emit
import pygal
from pygal import XY
import fermenter

logging.basicConfig()

###############################################################################
# PARAMETERS
###############################################################################
STATS_INTERVAL = 2 # (sec): time to wait between updating stats
PLOTS_DIR = "static/plots/"
PLOTS_INTERVAL = 10 # (sec): time to wait between updating plots

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
        absorbances.append((entry[0], fermenter.get_abs(calib, entry[1])))
    return absorbances
def initialize_plots():
    optics = XY(stroke=True)
    optics.title = "Optical Measurements"
    plots = {
        "optics": optics,
    }
    return optics
def update_plots(records, locks, plots):
    while True:
        #rerender = False
        rerender = True
        with (locks["records"]):
            calib_red = records["optics"]["calibration"]["red"]
            red = records["optics"]["red"]
            calib_green = records["optics"]["calibration"]["red"]
            green = records["optics"]["red"]
            #if red and calib_red:
                #plots["optics"].add("OD", trans_to_abs(calib_red, red))
                #rerender = True
            #if green and calib_red:
                #plots["optics"].add("Green", trans_to_abs(calib_green, green))
                #rerender = True
            plots["optics"].add("Placeholder", [(1, 1), (2, 4), (3, 9), (4, 16)])
        if rerender:
            plots["optics"].render_to_file(PLOTS_DIR + "optics.svg")
            socketio.emit("plots update", {"time": datetime.now()},
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
        plots = initialize_plots()
        threads["plots"] = Thread(target=update_plots, name="plots",
                                  args=(records, locks, plots))
        threads["plots"].start()
    return send_from_directory("static", "dashboard.html")

@app.route("/client.js")
def client():
    """Deliver the client-side scripting"""
    return send_from_directory("static", "client.js")

@app.route("/plots/<plot>")
def plots(plot):
    """Deliver the specified plot"""
    return send_from_directory("static/plots/", plot + ".svg")

###############################################################################
# MAIN
###############################################################################
if __name__ == "__main__":
    (records, locks, events, threads) = fermenter.run_fermenter()
    socketio.run(app, host='0.0.0.0', port=80)
