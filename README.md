# Birdhouse

Simple Python webserver and OpenCV script for birdhouse liveview and temperature/pressure measurement 
with Raspberry Pi.

## install

- Activate I2C and camera in raspi-config (GStreamer pipeline uses new libcamera interface)

- Install numpy and GStreamer:  
  `sudo apt install python3-numpy gstreamer1.0-plugins{good,bad,ugly,base}`
- Install precompiled OpenCV from https://github.com/prepkg/opencv-raspberrypi  
  `wget https://github.com/prepkg/opencv-raspberrypi/releases/download/4.5.5/opencv.deb && sudo apt install -y ./opencv.deb`
- Clone this project and install requirements.txt:  
  `pip3 install -r requirements.txt`