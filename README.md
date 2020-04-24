# piCameraWeb
A Python program to drive the raspberry pi camera with the ability to stream, record video, detect motion and more

I wrote this program initially as a way of both learning more Python and finding out what is really possible on
a Raspberry Pi Zero. I found existing packages like Motion ( / motioneye) and RPi Cam Web Interface rather frustrating 
for various reasons, so I've spent some time making this into a viable application / package in its own right.

This software is still a work in progress and should be regarded as beta at the moment.

The camera driving software exclusively uses the raspberry pi python interface, and uses the splitter port capability to
enable (up to) 4 different camera streams to run in parallel, exploiting the GPU as much as possible to improve performance.
The intention is that the package will run robustly on a Raspberry Pi Zero.

The user interface is entirely through a basic web server, and uses some Javascript in the web browser to provide a responsive
application like interface. It works fine with firefox, chrome and various chrome derivatives (standard android browser for
example).

The package is written to minmise the use of additional packages, so it has its own simple web server built directly on top
of http.server.HTTPServer, and takes a rather unconventional approach to web page building and handling.

Most of the camera driving software is based on the excellent examples from the picamera package documentation

The software includes:

A simple motion detection system based of difference between successive frames

A simple eay to use an external motion detector (such as a PIR module connected via a GPIO port

A video recorder that creates a video when triggered with (optionally) a few seconds of video before and after the trigger

Note that after an extensive update to improve the software, the docs are somewhat out of date temorarily.

## installation instructions
These instructions work on a clean new build of raspbian (any variety - I usually use Raspbian Lite).

Install git:
> sudo apt install git python3-distutils

Clone the utilities repository and this repository from github:
> git clone https://github.com/pootle/pootles_utils.git

> git clone https://github.com/pootle/piCameraWeb.git

Install the utils into the standard python package location
> cd pootles_utils

> sudo python3 setup.py install

Then do the setup for the camera app:
> cd piCameraWeb/setup

> sudo ./setup.sh

Check the camera is OK:
> vcgencmd get_camera

this will return ‘supported=1 ‘detected=1’ if the camera is enabled and a camera is detected.

## test run the software

cd to the piCameraWeb folder, then you can run the web server with:
> python3 webserv.py -c testconfig.py

This will display the useful bit of the url which can use use on any local machine to access the app.

[More documentaton is available here.](https://picamdocs.readthedocs.io/en/latest/)

To start the app automatically on boot use crontab and add the following line: (note crontab will prompt for an editor the first time you do this)

> crontab -e

add this line:

> @reboot              ~/piCameraWeb/webserv.py -c ~/piCameraWeb/testconfig.py -l ~/camlog.log >> ~/shlog.log 2>&1
