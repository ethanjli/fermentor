// Math
function absorbance(calib, transmittance) {
  return (calib - transmittance) / calib;
}
function duty_cycle_to_percent(duty_cycle) {
  return ~~(duty_cycle * 100)
}

// Strings
function time_text(data) {
  if (data) {
    return "Updated " + data[0] + ".";
  }
}
function start_text(data) {
  if (data) {
    return "Fermenter started at: " + data;
  } else {
    return "Fermenter has not yet started.";
  }
}
function stop_text(data, since) {
  if (data) {
    $('form#startbutton').show();
    $('form#stopbutton').hide();
    return "Fermenter stopped at: " + data;
  } else {
    $('form#startbutton').hide();
    $('form#stopbutton').show();
    return "Fermenter has been running for " + since.toFixed(2) + " hours.";
  }
}
function now_text(data) {
  return "Last update: " + data;
}
function temp_text(data) {
  if (data) {
    return "Vessel temperature: " + data[1].toFixed(2) + " °C";
  } else {
    return "Vessel temperature will be updated soon!";
  }
}
function heater_text(data) {
  if (data) {
    return "Heater duty cycle: " + duty_cycle_to_percent(data[1]) + " %";
  } else {
    return "Heater duty cycle will be updated soon!";
  }
}
function impeller_text(data) {
  if (data) {
    return "Impeller duty cycle: " + duty_cycle_to_percent([1]) + " %";
  } else {
    return "Impeller duty cycle will be updated soon!";
  }
}
function ambient_text(data) {
  if (data) {
    return "Ambient light: " + ~~(data[1]);
  } else {
    return "Ambient light will be updated soon!";
  }
}
function red_text(red_calib, data) {
  if (data) {
    return "OD: " + absorbance(red_calib, data[1]).toFixed(2);
  } else {
    return "OD will be updated soon!";
  }
}
function green_text(green_calib, data) {
  if (data) {
    return "Green absorbance: " + absorbance(green_calib, data[1]).toFixed(2);
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
    $("#stop").text(stop_text(msg.stop, msg.since));
    $("#now").text(now_text(msg.now));
    $('#impeller').text(impeller_text(msg.impeller));
    $('#temp_update_time').text(time_text(msg.temp));
    $('#temp').text(temp_text(msg.temp));
    $('#heater').text(heater_text(msg.heater));
    $('#optics_update_time').text(time_text(msg.optics.ambient));
    $('#ambient').text(ambient_text(msg.optics.ambient));
    $('#red').text(red_text(msg.optics.calibration.red, msg.optics.red));
    $('#green').text(green_text(msg.optics.calibration.green, msg.optics.green));
  });
  socket.on("optics plot update", function(msg) {
    $('#optics_plot_cache').attr("data", "/plots/optics?" + msg.time);
  });
  socket.on("temp plot update", function(msg) {
    $('#temp_plot_cache').attr("data", "/plots/temp?" + msg.time);
  });
  socket.on("duty cycles plot update", function(msg) {
    $('#duty_cycles_plot_cache').attr("data", "/plots/duty_cycles?" + msg.time);
  });
  document.getElementById('optics_plot_cache').addEventListener("load", function () {
    $('#optics_plot').attr("data", $('#optics_plot_cache').attr("data"));
  });
  document.getElementById('temp_plot_cache').addEventListener("load", function () {
    $('#temp_plot').attr("data", $('#temp_plot_cache').attr("data"));
  });
  document.getElementById('duty_cycles_plot_cache').addEventListener("load", function () {
    $('#duty_cycles_plot').attr("data", $('#duty_cycles_plot_cache').attr("data"));
  });
  $('form#startbutton').submit(function(event) {
    socket.emit("fermenter start", {});
    return false;
  });
  $('form#stopbutton').submit(function(event) {
    socket.emit("fermenter stop", {});
    return false;
  });
  $('form#impellermenu').change(function(event) {
    socket.emit("impeller set", {data: $('#impellerduty').val()});
    return false;
  });
});
