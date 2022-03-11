#!/bin/bash

#gst-launch-1.0 libcamerasrc ! video/x-raw,width=1280,height=720,framerate=10/1,format=NV12 ! videoconvert ! queue ! \
#v4l2h264enc ! 'video/x-h264, profile=high, level=(string)4' ! queue ! \
#h264parse ! flvmux name=flvmux ! queue ! rtmpsink location=rtmp://live-fra.twitch.tv/app/${TWITCH_KEY}

gst-launch-1.0 souphttpsrc location=http://localhost:5000/playlist.m3u8 ! hlsdemux ! decodebin ! videoconvert ! \
videoscale ! video/x-raw,width=1280,height=720,framerate=10/1 ! queue ! \
v4l2h264enc ! 'video/x-h264, profile=high, level=(string)4' ! queue ! \
h264parse ! flvmux name=flvmux ! queue ! rtmpsink location=rtmp://live-fra.twitch.tv/app/${TWITCH_KEY}
