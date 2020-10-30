#!/bin/bash

DIR="$( cd "$( dirname "$0" )" && pwd )"

sudo apt update
sudo apt install -y cmake freeglut3-dev pkg-config build-essential libxmu-dev libxi-dev libusb-1.0-0-dev python freenect libfreenect-bin libfreenect-demos libfreenect0.5 kinect-audio-setup libopenni-dev libopenni-java libopenni-sensor-primesense-dev libopenni-sensor-primesense0 libopenni0 libopenni2-0 openni-doc openni-utils openni2-doc openni2-utils primesense-nite-nonfree doxygen mono-complete graphviz

cd $DIR
mkdir -p KinectLibs
cd KinectLibs

# Direct downloads
wget https://master.dl.sourceforge.net/project/roboticslab/External/nite/NiTE-Linux-x64-2.2.tar.bz2
tar -xvf NiTE-Linux-x64-2.2.tar.bz2

# OpenNI 2.2 (May not be necessary with git repo also below)
wget https://s3.amazonaws.com/com.occipital.openni/OpenNI-Linux-x64-2.2.0.33.tar.bz2
tar -xvf OpenNI-Linux-x64-2.2.0.33.tar.bz2

# kinect driver
wget https://github.com/downloads/avin2/SensorKinect/SensorKinect093-Bin-Linux-x64-v5.1.2.1.tar.bz2
tar -xvf SensorKinect093-Bin-Linux-x64-v5.1.2.1.tar.bz2
cd Sensor-Bin-Linux-x64-v5.1.2.1
sudo ./install.sh
cd ..

git clone https://github.com/OpenKinect/libfreenect
git clone https://github.com/OpenNI/OpenNI
git clone https://github.com/occipital/OpenNI2
git clone https://github.com/avin2/SensorKinect
git clone https://github.com/arnaud-ramey/NITE-Bin-Dev-Linux-v1.5.2.23

cd libfreenect
mkdir -p build
cd build
cmake .. -DBUILD_OPENNI2_DRIVER=ON
make
sudo make install
sudo ldconfig /usr/local/lib64/
sudo chmod a+rw /dev/bus/usb//
sudo chmod a+rw /dev/bus/usb//

cp -R lib/OpenNI2-FreenectDriver/* ../../NiTE-Linux-x64-2.2/Samples/Bin/OpenNI2/Drivers
cp -R lib/OpenNI2-FreenectDriver/* ../../OpenNI2/Bin/x64-Release/OpenNI2/Drivers
cp -R lib/OpenNI2-FreenectDriver/* ../../OpenNI2/Config/OpenNI2/Drivers
cp -R lib/OpenNI2-FreenectDriver/* ../../OpenNI-Linux-x64-2.2/Redist/OpenNI2/Drivers
cp -R lib/OpenNI2-FreenectDriver/* ../../OpenNI-Linux-x64-2.2/Samples/Bin/OpenNI2/Drivers
cp -R lib/OpenNI2-FreenectDriver/* ../../OpenNI-Linux-x64-2.2/Tools/OpenNI2/Drivers
cd ../..

cd OpenNI
find -name '*.h' -exec sed -i 's/ equivalent(/ is_equivalent(/g' {} +
find -name '*.h' -exec sed -i 's/(equivalent(/(is_equivalent(/g' {} +
find -name '*.h' -exec sed -i 's/!equivalent(/!is_equivalent(/g' {} +
cd Platform/Linux/CreateRedist
chmod +x ./RedistMaker
./RedistMaker
cd ../Redist/OpenNI-Bin-Dev-Linux-x64-v1.5.7.10/
sudo ./install.sh
cd ../../../../..

cd NITE-Bin-Dev-Linux-v1.5.2.23/x64
sudo ./install.sh
cd ../..

wget https://s3.amazonaws.com/com.occipital.openni/OpenNI-Linux-x64-2.2.0.33.tar.bz2
tar -xvf OpenNI-Linux-x64-2.2.0.33.tar.bz2

wget https://github.com/downloads/avin2/SensorKinect/SensorKinect093-Bin-Linux-x64-v5.1.2.1.tar.bz2
tar -xvf SensorKinect093-Bin-Linux-x64-v5.1.2.1.tar.bz2
cd Sensor-Bin-Linux-x64-v5.1.2.1
sudo ./install.sh
cd ..

cd ..
ln -s KinectLibs/NiTE-Linux-x64-2.2/Redist/NiTE2

echo ""
echo "   cd OpenNI/Platform/Linux/Redist/OpenNI-Bin-Dev-Linux-x64-v1.5.7.10/Samples/Bin/x64-Release"
echo "to test out installation with samples."
