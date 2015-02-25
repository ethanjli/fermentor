#!/usr/bin/python2
from gevent import monkey
monkey.patch_all()

import platform
import subprocess
from threading import Thread
import time
from datetime import timedelta
from flask import Flask, render_template, send_from_directory
from flask.ext.socketio import SocketIO, emit, disconnect

app = Flask(__name__)
app.config["SECRET_KEY"] = b"\xb9\x82y=\x8f\xba\xa2\xc5&*\x13n\xe0L\xe4\x91\xed\xc5\xab\xaa\t\r\xccd"
socketio = SocketIO(app)
thread = {}

def get_uptime():
    with open('/proc/uptime', 'r') as f:
        uptime_seconds = float(f.readline().split()[0])
        return str(timedelta(seconds=round(uptime_seconds)))

def uptime_thread():
    while True:
        time.sleep(0.5)
        socketio.emit("scheduled uptime update", {"data": get_uptime()}, namespace="/socket")

def get_temperature():
    return subprocess.check_output(["/opt/vc/bin/vcgencmd", "measure_temp"]).decode('ascii').split("=")[1][:-3]

def temperature_thread():
    while True:
        time.sleep(5)
        socketio.emit("scheduled temperature update", {"data": get_temperature(), "time": time.ctime()}, namespace="/socket")

@app.route("/")
def index():
    return "<html><body><a href=\"./static_stats\">static stats</a></br><a href=\"live_stats\">live stats</a></body></html>"

@app.route("/static_stats")
def static_stats():
    return render_template("static_stats.html", hostname=platform.node(), platform=platform.platform())

@app.route("/live_stats")
def live_stats():
    global thread
    if "temperature" not in thread.keys():
        thread["temperature"] = Thread(target=temperature_thread)
        thread["temperature"].start()
    if "uptime" not in thread.keys():
        thread["uptime"] = Thread(target=uptime_thread)
        thread["uptime"].start()
    return send_from_directory("static", "live_stats.html")

@socketio.on("socket event", namespace="/socket")
def test_message(message):
    emit("global server announcement", {"data": "A client has connected!"}, broadcast=True);

if __name__ == "__main__":
    socketio.run(app, host='0.0.0.0', port=80)
