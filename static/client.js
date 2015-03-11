// Math
function absorbance(calib, transmittance) {
  return (calib - transmittance) / calib;
}
function duty_cycle_to_percent(duty_cycle) {
  return ~~(duty_cycle * 100)
}

// Strings
function start_text(data) {
  if (data) {
    return "Fermenter started at: " + data;
  } else {
    return "Fermenter has not yet started.";"
  }
}
function stop_text(data) {
  if (data) {
    return "Fermenter stopped at: " + data;
  } else {
    return "Fermenter is still running.";
  }
}
function temp_text(data) {
  if (data) {
    return "Vessel temperature: " + data[1] + "(as of " + data[0] + ")";
  } else {
    return "Vessel temperature will be updated soon!";
  }
}
function temp_text(data) {
  if (data) {
    return "Vessel temperature: " + data[1].toFixed(2) + " °C (as of " + data[0] + ")";
  } else {
    return "Vessel temperature will be updated soon!";
  }
}
function heater_text(data) {
  if (data) {
    return "Heater duty cycle: " + duty_cycle_to_percent(data[1]) + " % (as of " + data[0] + ")";
  } else {
    return "Heater duty cycle will be updated soon!";
  }
}
function impeller_text(data) {
  if (data) {
    return "Impeller duty cycle: " + duty_cycle_to_percent([1]) + " % (as of " + data[0] + ")";
  } else {
    return "Impeller duty cycle will be updated soon!";
  }
}
function ambient_text(data) {
  if (data) {
    return "Ambient light: " + ~~(data[1]) + "  (as of " + data[0] + ")";
  } else {
    return "Ambient light will be updated soon!";
  }
}
function red_text(red_calib, data) {
  if (data) {
    return "OD: " + absorbance(red_calib, data[1]).toFixed(2) + "  (as of " + data[0] + ")";
  } else {
    return "OD will be updated soon!";
  }
}
function green_text(green_calib, data) {
  if (data) {
    return "Green absorbance: " + absorbance(green_calib, data[1]).toFixed(2) + "  (as of " + data[0] + ")";
  } else {
    return "Green absorbance will be updated soon!";
  }
}

$(document).ready(function () {
  namespace = "/socket";
  var socket = io.connect("http://" + document.domain + ":" + location.port + namespace);
  socket.on("connect", function () {
    socket.emit("socket event", {data: "Successful connection!"});
  });
  socket.on("stats update", function (msg) {
    $("#start").text(start_text(msg.start));
    $('#stop').text(stop_text(msg.stop));
    $('#temp').text(temp_text(msg.temp));
    $('#heater').text(heater_text(msg.heater));
    $('#impeller').text(impeller_text(msg.impeller));
    $('#ambient').text(ambient_text(msg.optics.ambient));
    $('#red').text(red_text(msg.optics.calibration.red, msg.optics.red));
    $('#green').text(green_text(msg.optics.calibration.green, msg.optics.green));
  });
});
