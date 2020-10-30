#!/bin/bash

clang -I KinectLibs/libfreenect/include -I KinectLibs/libfreenect/wrappers/c_sync -L KinectLibs/libfreenect/build/lib -l freenect -l freenect_sync -Wall -o kinect-tilt kinect-tilt.c
