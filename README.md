# fermenter
fermenter is the codebase for a Raspberry Pi to operate a simple Arduino-driven fermenter and provide a real-time web interface for high-level control of fermenter behavior. This was done by Ethan Li and Jessica Lam for the project extension for BIOE 123 ("Optics and Devices Lab") at Stanford University. This project implements proportional temperature control of a fermenter, along with OD and green absorption sensing to monitor growth of a custom E coli strain that produces purple protein.

## Dependencies
The following must be installed to run the web interface:
- [python 2](https://www.python.org/): required by Flask-SocketIO
- [numpy](http://www.numpy.org/): for basic data processing
- [Flask](http://flask.pocoo.org/)
- [Flask-SocketIO](https://github.com/miguelgrinberg/Flask-SocketIO) for real-time communication between a web browser and the server
- [Python-Arduino-Command-API](https://github.com/thearn/Python-Arduino-Command-API) for Arduino interfacing.

The project also uses [jQuery](http://jquery.com) for live page updating and [Google Charts](https://developers.google.com/chart/) for data plotting.

## Issues
Because this project was implemented only over a span of four days, and all of its substantive components were implemented over the course of 48 hours, this project is not good for production use:
- The plot update messages sent over WebSockets are wasteful in terms of data and processor time.
- UI design was not a high priority, given the time constraints.
- The data structures used are not the most suitable ones possible. They are not always initialized/reinitialized properly.
- The project did not undergo exhaustive testing or thorough quality checking.
- Certain routines are underdecomposed.
- Interface and naming are messy.
- Potential race conditions between multiple browser clients are not considered.
- Documentation is lacking in many areas.
- Notably, when the web interface is run on a Raspberry Pi B+ on a 2 A power suppply while powering an Arduino, it tends to brownout. In cases when CPU load is high, the code interfacing to the Arduino tends to read egregiously incorrect temperature values.

## Getting Started
When all dependencies are installed, run `fermenter.py` for basic (non-interactive) control of the fermenter. To expose the web interface, instead run `app.py` with the necessary permissions. For example, to serve the web interface on port 80, you may need to run it through `sudo`.
