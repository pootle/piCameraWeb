# piCameraWeb
A Python program to drive the raspberry pi camera with the ability to stream, record video, detect motion and more

I wrote this program initially as a way of both learning more Python and finding out what is really possible on
a Raspberry Pi Zero. I found existing packages like Motion ( / motioneye) and RPi Cam Web Interface rather frustrating 
for various reasons, so I've spent some time making this into a viable application / package in its own right.

This software is still a work in progress and should be regarded as alpha / experimental at the moment.

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

A video recorder that creates a video when triggered with a few seconds of video before and after the trigger


[More documentaton is available here.](https://picamdocs.readthedocs.io/en/latest/)
