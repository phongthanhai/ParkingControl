import os
import re

CAMERA_SOURCES = {
    'entry': 0, 
    'exit': 2
}

GPIO_PINS = {
    'entry': 17,
    'exit': 27
}

AUTO_CLOSE_DELAY = 10
OCR_TIMEOUT = 30

VIETNAMESE_PLATE_PATTERN = re.compile(r"^\d{2}[A-Za-z]\d{4,5}$")

CAMERA_RESOLUTION = (640, 480)
CAMERA_FPS = 10

MODEL_PATH = os.path.expanduser("/home/raspberrypi/Documents/ParkingControl/detect_lp_dynamic_nms_opset18.onnx")
INPUT_SIZE = (320, 320)
CONFIDENCE_THRESHOLD = 0.25

PLATE_RECOGNIZER_API_KEY = "48c3a3ab6f959e54b8019143ce087201fd32833c"
PLATE_RECOGNIZER_URL = "https://api.platerecognizer.com/v1/plate-reader"
OCR_RATE_LIMIT = 5
API_BASE_URL = "http://192.168.1.8:8000/api/v1"

UI_REFRESH_RATE = 100

LOT_ID = 1
