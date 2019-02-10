#!/bin/sh

echo "piCameraWeb prep and setup script........"
echo "checking system is up to date........."

apt-get -q update

apt-get -q -y update

echo "installing addtional software required by piCameraWeb"

apt-get -q -y install python3-pip gpac python3-pigpio python3-numpy

echo "installing additional python modules"

pip3 install picamera pypng

echo "applying patches to picamera package"

patch /usr/local/lib/python3.5/dist-packages/picamera/streams.py streams.patch
patch /usr/local/lib/python3.5/dist-packages/picamera/camera.py camera.patch
patch /usr/local/lib/python3.5/dist-packages/picamera/encoders.py encoders.patch

