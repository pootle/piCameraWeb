#!/bin/sh

echo "piCameraWeb prep and setup script........"
echo "======================================"
echo "checking system is up to date........."

apt-get -q update

apt-get -q -y update

echo "====================================================="
echo "installing addtional software required by piCameraWeb"
echo "====================================================="

apt-get -q -y install python3-pip gpac python3-pigpio python3-numpy

echo "===================================="
echo "installing additional python modules"
echo "===================================="

pip3 install picamera pypng

echo "===================================="
echo "applying patches to picamera package"
echo "===================================="

patch /usr/local/lib/python3.5/dist-packages/picamera/streams.py streams.patch
patch /usr/local/lib/python3.5/dist-packages/picamera/camera.py camera.patch
patch /usr/local/lib/python3.5/dist-packages/picamera/encoders.py encoders.patch

sudo ./wpaping_setup.sh

echo "=============="
echo "setup complete"
