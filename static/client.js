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
    return "Vessel temperature: " + data[1] + " °C (as of " + data[0] + ")";
  } else {
    return "Vessel temperature will be updated soon!";
  }
}
function heater_text(data) {
  if (data) {
    return "Heater duty cycle: " + (data[1] * 100) + " % (as of " + data[0] + ")";
  } else {
    return "Heater duty cycle will be updated soon!";
  }
}

$(document).ready(function () {
  namespace = "/socket";
  var socket = io.connect("http://" + document.domain + ":" + location.port + namespace);
  socket.on("connect", function () {
    socket.emit("socket event", {data: "Successful connection!"});
  });
  socket.on("stats update", function (msg) {
    $("#start").text("start time: " + msg.start);
    $('#stop').text(stop_text(msg.stop));
    $('#temp').text(temp_text(msg.temp));
    $('#heater').text(heater_text(msg.heater));
    $('#impeller').text('impeller duty cycle: ' + msg.impeller);
    $('#calibred').text('red transmittance calibration: ' + msg.optics.calibration.red);
    $('#calibgreen').text('green transmittance calibration: ' + msg.optics.calibration.green);
    $('#ambient').text('ambient light: ' + msg.optics.ambient);
    $('#red').text('red transmittance: ' + msg.optics.red);
    $('#green').text('green transmittance: ' + msg.optics.green);
  });
});
