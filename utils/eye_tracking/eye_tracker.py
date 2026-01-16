"""
Created on Wed Jan 14 19:23:59 2026
# -*- coding: utf-8 -*-
# eye_tracker.py
@author: barna
"""

import cv2
import os
import numpy as np
from collections import deque

class EyeTracker:
    def __init__(self):
        self.cap = cv2.VideoCapture(
            "libcamerasrc ! video/x-raw, format=NV12, width=640, height=480, framerate=30/1 ! videoconvert ! video/x-raw, format=BGR ! appsink",
            cv2.CAP_GSTREAMER
        )

        if not self.cap.isOpened():
            raise RuntimeError("Camera failed initialize via GStreamer.")
        
        base_dir = os.path.dirname(os.path.abspath(__file__))
        face_path = os.path.join(base_dir, 'haarcascade_frontalface_default.xml')
        # Using eyeglasses model is generally more stable for everyone
        eye_path = os.path.join(base_dir, 'haarcascade_eye.xml')
        
        self.face_cascade = cv2.CascadeClassifier(face_path)
        self.eye_cascade = cv2.CascadeClassifier(eye_path)
        
        if self.face_cascade.empty() or self.eye_cascade.empty():
            raise IOError("Failed to load cascade xml files.")
        
        # --- SMOOTHING VARIABLES ---
        self.alpha_box = 0.4  # Lower = Smoother Box, Higher = Faster Tracking
        self.prev_face = None # (x, y, w, h)
        self.prev_eyes = []   # List of (x, y, w, h)

        # Logic Variables
        self.baseline_ratio = None
        self.threshold_buffer = 0.04 # Increased slightly for stability
        self.eyes_off = False
        
        self.history_size = 12
        self.history = deque(maxlen=self.history_size)
        self.activation_threshold = 0.6

    def get_frame(self):
        if self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret: return frame
        return None

    def smooth_rect(self, current, prev):
        """Applies Exponential Moving Average to rectangle coordinates."""
        if prev is None: return current
        
        (cx, cy, cw, ch) = current
        (px, py, pw, ph) = prev
        
        # Smooth each component
        nx = int(self.alpha_box * cx + (1 - self.alpha_box) * px)
        ny = int(self.alpha_box * cy + (1 - self.alpha_box) * py)
        nw = int(self.alpha_box * cw + (1 - self.alpha_box) * pw)
        nh = int(self.alpha_box * ch + (1 - self.alpha_box) * ph)
        
        return (nx, ny, nw, nh)

    def detect_pupils(self, frame):
        """
        Returns: (frame, vertical_ratio)
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.bilateralFilter(gray, 10, 25, 25)
        
        ratios = []
        current_eyes_rects = [] # Store for next frame smoothing

        # 1. FACE DETECTION (Smoothed)
        faces = self.face_cascade.detectMultiScale(gray, 1.1, 4)
        
        if len(faces) > 0:
            # We assume the largest face is the user
            faces = sorted(faces, key=lambda b: b[2] * b[3], reverse=True)
            raw_face = faces[0]
            
            # Smooth the Face Box
            smooth_face = self.smooth_rect(raw_face, self.prev_face)
            self.prev_face = smooth_face
            
            (fx, fy, fw, fh) = smooth_face
            cv2.rectangle(frame, (fx, fy), (fx+fw, fy+fh), (255, 0, 0), 1)

            # Define Eye Search Region (Top half of face)
            roi_gray = gray[fy:fy+fh//2, fx:fx+fw]
            
            # 2. EYE DETECTION
            eyes = self.eye_cascade.detectMultiScale(
                roi_gray, 
                scaleFactor=1.1, 
                minNeighbors=3, 
                minSize=(20, 20)
            )
            
            # Sort eyes by X position to roughly match left/right consistency
            eyes = sorted(eyes, key=lambda x: x[0])
            
            for i, raw_eye in enumerate(eyes):
                # Try to match with previous eye frame history
                # If we have a history for this index, smooth it
                prev_eye = self.prev_eyes[i] if i < len(self.prev_eyes) else None
                
                (ex, ey, ew, eh) = self.smooth_rect(raw_eye, prev_eye)
                current_eyes_rects.append((ex, ey, ew, eh))
                
                # --- PUPIL LOGIC (Using Smoothed Box) ---
                eyebrow_cut = int(eh * 0.25)
                eye_roi = roi_gray[ey + eyebrow_cut : ey + eh, ex : ex + ew]
                
                _, threshold = cv2.threshold(eye_roi, 40, 255, cv2.THRESH_BINARY_INV)
                kernel = np.ones((2, 2), np.uint8)
                threshold = cv2.erode(threshold, kernel, iterations=1)
                threshold = cv2.dilate(threshold, kernel, iterations=2)

                contours, _ = cv2.findContours(threshold, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
                contours = sorted(contours, key=lambda x: cv2.contourArea(x), reverse=True)
                
                if len(contours) > 0:
                    cnt = contours[0]
                    M = cv2.moments(cnt)
                    if M['m00'] != 0:
                        cx = M['m10'] / M['m00']
                        cy = M['m01'] / M['m00']
                        
                        pupil_center_y = cy + eyebrow_cut
                        ratio = pupil_center_y / eh
                        ratios.append(ratio)
                        
                        # Visuals
                        global_x = int(fx + ex + cx)
                        global_y = int(fy + ey + pupil_center_y)
                        cv2.rectangle(frame, (fx+ex, fy+ey), (fx+ex+ew, fy+ey+eh), (0, 255, 0), 1)
                        cv2.circle(frame, (global_x, global_y), 2, (0, 0, 255), -1)

            # Update history for next frame
            self.prev_eyes = current_eyes_rects

        avg_ratio = sum(ratios) / len(ratios) if ratios else None
        return frame, avg_ratio

    def calibrate(self, current_ratio):
        if current_ratio is not None:
            self.baseline_ratio = current_ratio
            print(f"Calibration Set! Baseline Ratio: {self.baseline_ratio:.2f}")

    def check_gaze(self, current_ratio):
        if current_ratio is None or self.baseline_ratio is None:
            return False, None

        limit = self.baseline_ratio - self.threshold_buffer
        is_up_raw = (current_ratio < limit)

        self.history.append(1 if is_up_raw else 0)

        if len(self.history) < self.history_size:
            return False, limit

        avg_score = sum(self.history) / self.history_size

        if avg_score > self.activation_threshold:
            self.eyes_off = True  
        else:
            self.eyes_off = False 

        return self.eyes_off, limit

    def release(self):
        self.cap.release()