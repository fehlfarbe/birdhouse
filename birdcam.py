#!/usr/bin/env python3
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock, Thread, Event
from typing import Tuple, Optional
import logging
from bmp280 import BMP280
import numpy as np
import cv2

try:
    from smbus2 import SMBus
except ImportError:
    from smbus import SMBus


logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)


@dataclass
class SensorValues:
    timestamp: float = 0.
    temperature: float = 0.
    humidity: float = 0.
    pressure: float = 0.
    cpuTemperature: float = 0.


class Birdcam:

    def __init__(self, cam: int = 0, resolution: Tuple[int, int] = (1280, 720), fps: int = 30,
                 capture_dir: str = ("."), capture_time: int = 60):
        # camera
        self._width: int = resolution[0]
        self._height: int = resolution[1]
        self._fps: int = fps
        self._fps_stream: int = 10
        self._cam: cv2.VideoCapture = cv2.VideoCapture(
            f"libcamerasrc ! video/x-raw,width=(int){self._width},height=(int){self._height},framerate=(fraction){self._fps}/1 ! videoconvert ! appsink",
        cv2.CAP_GSTREAMER)
        self._output: Optional[cv2.VideoWriter] = cv2.VideoWriter(
            f"appsrc ! video/x-raw,width=(int){self._width},height=(int){self._height},framerate=(fraction){self._fps_stream}/1,format=BGR "
            f"! queue ! videoconvert ! v4l2h264enc ! video/x-h264,profile=main,level=(string)4 ! queue ! "
            f"h264parse ! mpegtsmux ! hlssink playlist-root=http://192.168.100.203:5000 location=/dev/shm/segment_%05d.ts playlist-location=/dev/shm/playlist.m3u8 target-duration=5 max-files=5",
            cv2.CAP_GSTREAMER, 0, self._fps_stream, (self._width, self._height), True)
        self._frame: Optional[np.array] = None

        # capture
        self._captureTime: int = capture_time
        self._captureDir: str = capture_dir

        # BMP280
        self._sensorValues: SensorValues = SensorValues()
        bus: SMBus = SMBus(1)
        self._bmp280: BMP280 = BMP280(i2c_dev=bus)

        # threads
        self._threadVideoCapture: Thread = Thread(target=self._runVideoCapture)
        self._threadVideoCapture.daemon = True
        self._threadImageCapture: Thread = Thread(target=self._runImageCapture)
        self._threadImageCapture.daemon = True
        self._threadSensorUpdate: Thread = Thread(target=self._runUpdateSensors)
        self._threadSensorUpdate.daemon = True
        self._lockCapture: Lock = Lock()
        self._stoppedCapture: Event = Event()

    def start(self):
        self._threadVideoCapture.start()
        self._threadImageCapture.start()
        self._threadSensorUpdate.start()

    def stop(self):
        if self._threadVideoCapture.is_alive():
            self._stoppedCapture.set()
            self._threadVideoCapture.join()
        if self._threadImageCapture.is_alive():
            self._stoppedCapture.set()
            self._threadImageCapture.join()
        if self._threadSensorUpdate.is_alive():
            self._stoppedCapture.set()
            self._threadSensorUpdate.join()

    def _runVideoCapture(self):
        tLastStreamedImage = time.time()
        while self._isRunning():
            ret, frame = self._cam.read()

            if ret:
                # add text
                self._addText(frame)

                # update frame
                with self._lockCapture:
                    self._frame = frame

                # write to output stream
                current = time.time()
                if self._output is not None and self._output.isOpened() \
                        and (current-tLastStreamedImage) > 1./self._fps_stream:
                    self._output.write(frame)
                    tLastStreamedImage = time.time()

        self._cam.release()
        self._output.release()

    def _runImageCapture(self):
        while self._isRunning():
            now = datetime.now()
            nowDate = now.strftime("%Y-%m-%d")
            nowDatetime = now.strftime('%Y-%m-%d %H:%M:%S')

            captureDir = os.path.join(self._captureDir, nowDate)

            if not os.path.exists(captureDir):
                try:
                    os.mkdir(captureDir)
                except Exception as e:
                    logging.error(f"Cannot create capture dir {captureDir}: {e}")
                    time.sleep(self._captureTime)
                    continue

            filename = os.path.join(captureDir, f"{nowDatetime}.jpg")
            logging.info(f"Saving image to {filename}")
            with self._lockCapture:
                frame = self._frame
                if frame is not None:
                    cv2.imwrite(filename, frame, (int(cv2.IMWRITE_JPEG_QUALITY), 80))

            time.sleep(self._captureTime)

    def _runUpdateSensors(self):
        while self._isRunning():
            # update sensor values
            temperature = self._bmp280.get_temperature()
            pressure = self._bmp280.get_pressure()
            cpu = self._getCPUTemperature()
            self._sensorValues = SensorValues(datetime.now().timestamp(), temperature, 0, pressure, cpu)

            time.sleep(0.1)

    def _isRunning(self) -> bool:
        return not self._stoppedCapture.is_set() and self._cam.isOpened()

    def _addText(self, frame: np.array) -> np.array:
        font = cv2.FONT_HERSHEY_COMPLEX_SMALL
        height, width, channels = frame.shape
        # draw black border for text
        cv2.rectangle(frame, (0, height), (width, height - 40), (0, 0, 0), -1)
        # inserting text on video
        text = f"{datetime.fromtimestamp(self._sensorValues.timestamp).strftime('%Y-%m-%d %H:%M:%S')} " \
               f"T={self._sensorValues.temperature:.2f}C, P={self._sensorValues.pressure:.2f}hPa " \
               f"CPU={self._sensorValues.cpuTemperature}C"
        cv2.putText(frame,
                    text,
                    (10, height - 15),
                    font, 1,
                    (255, 255, 255),
                    1,
                    cv2.LINE_8)

        return frame

    def _getCPUTemperature(self) -> float:
        tempStr = os.popen("vcgencmd measure_temp").readline()
        try:
            return float(re.search("[0-9]+\.[0-9]+", tempStr).group())
        except ValueError:
            return 0.

    def generator(self, resolution=None, fps=1) -> bytes:
        while self._isRunning():
            t0 = time.time()
            flag = False
            with self._lockCapture:
                frame = self._frame
                if frame is None:
                    time.sleep(0.1)
                    continue
                if resolution is not None:
                    frame = cv2.resize(frame, resolution)
                frame = self._addText(frame)
                (flag, encodedImage) = cv2.imencode(".jpg", frame)
            if flag:
                yield b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + bytearray(encodedImage) + b'\r\n'
                # wait for fps
                sleep = 1./fps - (time.time()-t0)
                if sleep > 0:
                    logging.debug(f"sleeping for {sleep:.2f} seconds")
                    time.sleep(sleep)


if __name__ == '__main__':
    # resolution = (640, 480)
    resolution = (1280, 960)
    cam = Birdcam(resolution=resolution, capture_dir="/home/pi/birdhouse/capture")
    cam.start()
    Event().wait()
