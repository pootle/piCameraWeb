#!/bin/sh

echo "piCameraWeb prep and setup script........"
echo "======================================"
echo "checking system is up to date........."

apt-get -q update

apt-get -q -y upgrade

echo "====================================================="
echo "installing addtional software required by piCameraWeb"
echo "====================================================="

apt-get -q -y install python3-pip gpac python3-pigpio python3-numpy python3-picamera python3-png python3-watchdog python3-psutil

echo "===================================="
echo "applying patches to picamera package"
echo "===================================="

python3 picampatch.py

echo "=============="
echo "setup complete"
