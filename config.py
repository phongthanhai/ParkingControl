import os
import re

# Camera Settings
CAMERA_SOURCES = {
    'entry': 0, 
    'exit': 2
}

# GPIO Settings
GPIO_PINS = {
    'entry': 17,
    'exit': 27
}

# Timing Settings
AUTO_CLOSE_DELAY = 10  # seconds
OCR_TIMEOUT = 30  # seconds

# Validation Settings
VIETNAMESE_PLATE_PATTERN = re.compile(r"^\d{2}[A-Za-z]\d{4,5}$")

# Hardware Settings
CAMERA_RESOLUTION = (640, 480)
CAMERA_FPS = 10

# Model Settings
MODEL_PATH = os.path.expanduser("/home/raspberrypi/Documents/ParkingControl/detect_lp_dynamic_nms_opset18.onnx")
INPUT_SIZE = (320, 320)
CONFIDENCE_THRESHOLD = 0.25

# API Settings
PLATE_RECOGNIZER_API_KEY = "48c3a3ab6f959e54b8019143ce087201fd32833c"
#PLATE_RECOGNIZER_API_KEY = ""
PLATE_RECOGNIZER_URL = "https://api.platerecognizer.com/v1/plate-reader"
OCR_RATE_LIMIT = 5  # seconds between API calls
SERVER_URL = "http://backend-endpoint-here/logs"
API_BASE_URL = "http://192.168.1.18:8000/api/v1"  # Base URL for backend API on Raspberry Pi

# UI Settings
UI_REFRESH_RATE = 100  # ms
