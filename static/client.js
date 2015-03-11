
$(document).ready(function () {
  namespace = "/socket";
  var socket = io.connect("http://" + document.domain + ":" + location.port + namespace);
  socket.on("connect", function () {
    socket.emit("socket event", {data: "Successful connection!"});
  });
  socket.on("stats update", function (msg) {
    $("#start").text("start time: " + msg.start);
    $('#stop').text('stop time: ' + msg.stop);
    $('#temp').text('temperature: ' + msg.temp + 'deg C');
    $('#heater').text('heater duty cycle: ' + msg.heater);
    $('#impeller').text('impeller duty cycle: ' + msg.impeller);
    $('#calibred').text('red transmittance calibration: ' + msg.optics.calibration.red);
    $('#calibgreen').text('green transmittance calibration: ' + msg.optics.calibration.green);
    $('#ambient').text('ambient light: ' + msg.optics.ambient);
    $('#red').text('red transmittance: ' + msg.optics.red);
    $('#green').text('green transmittance: ' + msg.optics.green);
  });
});
