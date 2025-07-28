import os
import cv2
import numpy as np
import pytesseract
from nudenet import NudeDetector
from PIL import Image

detector = NudeDetector()  # downloads the model the first time

def detect_nsfw(frame):
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    # we pass the numpy RGB array directly to NudeDetector
    result = detector.detect(rgb)
    nsfw_labels = {"EXPOSED_ANUS", "EXPOSED_BREAST_F", "EXPOSED_GENITALIA_F", "EXPOSED_GENITALIA_M", "EXPOSED_BUTTOCKS_F", "EXPOSED_BUTTOCKS_M"}
    nsfw_score = 0.0
    for det in result:
        if 'label' in det and det['label'] in nsfw_labels:
            nsfw_score = max(nsfw_score, det.get('score', 0.0))
    return nsfw_score

def detect_forbidden_text(frame, blacklist=None):
    if blacklist is None:
        blacklist = ['no signal', 'error', 'forbidden']
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    text = pytesseract.image_to_string(gray).lower()
    found = [mot for mot in blacklist if mot in text]
    return found

def detect_unauthorized_logo(frame, logos_dir='assets/logos_autorises/'):
    """returns True if no authorized logo is detected in the frame."""
    if not os.path.exists(logos_dir):
        return False  # no logos to compare
    found_logo = False
    frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    for logo_name in os.listdir(logos_dir):
        logo_path = os.path.join(logos_dir, logo_name)
        if not os.path.isfile(logo_path):
            continue
        logo = cv2.imread(logo_path, cv2.IMREAD_GRAYSCALE)
        if logo is None or logo.shape[0] > frame_gray.shape[0] or logo.shape[1] > frame_gray.shape[1]:
            continue
        res = cv2.matchTemplate(frame_gray, logo, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
        if max_val > 0.8:
            found_logo = True
            break
    return not found_logo 