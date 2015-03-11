#!/usr/bin/python2
from gevent import monkey
monkey.patch_all()

from threading import Thread
import time
import logging
from flask import Flask, send_from_directory
from flask.ext.socketio import SocketIO, emit
import fermenter

logging.basicConfig()

###############################################################################
# PARAMETERS
###############################################################################
STATS_INTERVAL = 10 # (sec): time to wait between updating statas

###############################################################################
# GLOBALS
###############################################################################
app = Flask(__name__)
socketio = SocketIO(app)
threads = {}

###############################################################################
# THREADS
###############################################################################
def update_stats(records, locks):
    while True:
        stats = {
            "start": records["start"],
            "stop": records["stop"],
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
    return send_from_directory("static", "dashboard.html")

###############################################################################
# MAIN
###############################################################################
if __name__ == "__main__":
    (records, locks, events, threads) = fermenter.run_fermenter()
    socketio.run(app, host='0.0.0.0', port=80)
