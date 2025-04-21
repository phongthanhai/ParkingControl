# Description
This is a single application for the control subsystem of the thesis: Building a Parking System.
The project involves:
- 2 camera feeds for entry and exit lane using 2 camera threads (QThread) to capture the frames asynchronously 
- Object detection on captured frame of each lane sequentially using processing thread and 2 queues for entry and exit frames 
- GPIO control for barriers of each lanes
- PyQt desktop application for manual control

# Hardware Setup
1. Prepare these hardware components(This will be updated for GPIO control):
- Raspberry Pi 4 model B with at least 4Gbs of RAM, preferably with heatsink and fans for better temperature
- 2 USB Camera of any kind
- A Power supply of 5V-3A to power up the Pi
- USB Mouse and Keyboard
- HDMI-to-microHDMI adapter
- An external monitor
- A microSD card with at least 64Gbs of storage, preferably one that can handle frequent read/write operations and durable
- A microSD to SD adapter
- An SD to USB adapter
- Another pc/laptop device
2. Flash the SD card with Raspberry Pi OS:
- Put the microSD card to SD adapter
- Put the SD adapter to SD to USB adapter and connect the USB port to a laptop/PC
- From the laptop/PC, install Raspberry Pi imager and execute it
- Choose OS: Raspberry Pi OS 64-bit Desktop version and device of Raspbery Pi 4, enable SSH for remote access.
- Wait for the flash to complete
- When it's completed, eject the device and remove the cable safely
- Remove the microSD card from the SD adapter.
3. Connect the hardware components:
- Connect USB keyboard and Mouse via Black USB 2.0 ports.
- Connect 2 USB cameras to the USB 3.0 ports.
- Connect to internet by Ethernet cable if presented via the Ethernet port.
- Connect the external monitor with the HDMI-to-microHDMI cable, with the microHDMI end connects to one of the HDMI ports presented on the Pi.
- Connect the power to the Pi via 5V-3A power supply
- Wait for Pi OS to be booted up. It might take some time for the first boot.
- Go to Pi settings, change the keyboard type to US to prevent mismatch of the keyboard characters
- Check the device name of the USB webcams, default is /dev/video0 and /dev/video2 if the cameras are connected using:
	lsusb
	ls /dev/video*
#Software setup
1. Clone the existing code:

git clone https://github.com/phongthanhai/ParkingControl

2. Navigate and open config.py file

- Change the CAMERA_SOURCE based on the result of USB webcam for entry and exit camera configuration
- Change the MODEL_PATH based on the actual path of the Yolo ONXX model.
- Change the PLATERECOGNIZERAPIKEY by the actual API Key given by Platerecognizer
- Change OCR_RATELIMIT to adjust the rate of Platerecognizer API Call

3. Install python if not installed. Check the version by
python --version
4. Activate the virtual enviroment by:
- Source venv/bin/activate from Pi
- ./venv/Script/activate in windows
4. Run the application by navigate to the project folder in the terminal:
python main.py

#Software debugging tips
If the program did not get executed, because of incompatibility between the packages from Pi and PC
1. Deactivate the virtual environment by:
deactivate
2. Remove venv folder
3. Create a new venv folder using:
python -m venv venv --system-site-packages
4. Install the packages by:
pip install -r requirements.txt
5. On Pi, PyQt5 frequently has error when trying to install from source using pip:
pip install PyQt5
Instead, use apt install:
sudo apt install python3-pyqt5 pyqt5-dev-tools -y
6. Activate the virtual environment that uses pyqt5 as apt package by:
Source /venv/bin/activate
7. Run the application:
python main.py




