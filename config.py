import os

# Camera Settings
CAMERA_SOURCES = {
    'entry': 0,  # /dev/video0
    'exit': 2    # /dev/video2
}
CAMERA_RESOLUTION = (640, 480)
CAMERA_FPS = 10

# Model Settings
MODEL_PATH = os.path.expanduser("/home/raspberrypi/Documents/ALPR/detect_lp_dynamic_nms_opset18.onnx")
INPUT_SIZE = (320, 320)
CONFIDENCE_THRESHOLD = 0.25

# API Settings
PLATE_RECOGNIZER_API_KEY = "api_token_here"
PLATE_RECOGNIZER_URL = "https://api.platerecognizer.com/v1/plate-reader"
OCR_RATE_LIMIT = 5  # seconds between API calls

# UI Settings
UI_REFRESH_RATE = 100  # ms
