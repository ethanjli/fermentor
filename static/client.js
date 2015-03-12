// Math
function absorbance(calib, transmittance) {
  return (calib - transmittance) / calib;
}
function duty_cycle_to_percent(duty_cycle) {
  return (duty_cycle * 100).toFixed(0);
}
function convert_timezones(datestr) {
  var date = new Date(datestr);
  return date.toString();
}

// Strings
function time_text(data) {
  if (data) {
    return "Updated: " + (data[0]).toFixed(3) + " hours after start.";
  }
}
function start_text(data) {
  if (data) {
    return "Fermenter started at: " + convert_timezones(data);
  } else {
    return "Fermenter has not yet started.";
  }
}
function stop_text(data, since) {
  if (data) {
    $('form#startbutton').show();
    $('form#stopbutton').hide();
    return "Fermenter stopped at: " + convert_timezones(data);
  } else {
    $('form#startbutton').hide();
    $('form#stopbutton').show();
    return "Fermenter has been running for " + since.toFixed(3) + " hours.";
  }
}
function now_text(data) {
  return "Now: " + convert_timezones(data);
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
    return "Impeller duty cycle: " + duty_cycle_to_percent(data[1]) + " %";
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

google.load('visualization', '1.1', {packages: ['line']});

$(document).ready(function () {

  // Set up socket
  namespace = "/socket";
  var socket = io.connect("http://" + document.domain + ":" + location.port + namespace);
  socket.on("connect", function () {
    socket.emit("socket event", {data: "Successful connection!"});
  });

  // Emit events
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
  $('form#recalibrate').submit(function(event) {
    socket.emit("recalibrate optics", {});
    return false;
  });

  // Receive events
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
    $('#environ_plot_cache').attr("data", "/plots/environ?" + msg.time);
  });
  socket.on("temp plot update", function(msg) {
    $('#temp_plot_cache').attr("data", "/plots/temp?" + msg.time);
    //var header = [['Time (h)', 'Temperature (°C)']];
    var data = new google.visualization.DataTable();
    data.addColumn('number', 'Time (h)');
    data.addColumn('number', 'Temperature (deg C)');
    data.addRows(msg.temp);
    var options = {'title': 'Temperature', 'width': 600, 'height': 320};
    var chart = new google.charts.Line(document.getElementById('temp_plot'));
  });
  socket.on("duty cycles plot update", function(msg) {
    $('#duty_cycles_plot_cache').attr("data", "/plots/duty_cycles?" + msg.time);
  });
});

