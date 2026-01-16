# -*- coding: utf-8 -*-
#eye_tracker.py
"""
Created on Wed Jan 14 19:23:59 2026

@author: barna
"""

import cv2
import os
import numpy as np
from collections import deque

class EyeTracker:
    def __init__(self):

        self.cap = cv2.VideoCapture(
            "libcamerasrc ! video/x-raw, format=NV12, width=640, height=480,framerate=30/1 ! videoconvert ! video/x-raw, format=BGR !  appsink drop=True",
            cv2.CAP_GSTREAMER
        )

        if not self.cap.isOpened():
            raise RuntimeError("Camera failed initialize via GStreamer.")
        
        base_dir = os.path.dirname(os.path.abspath(__file__))
        face_path = os.path.join(base_dir, 'haarcascade_frontalface_default.xml')
        eye_path = os.path.join(base_dir, 'haarcascade_eye.xml')
        print(f"Looking for model at {face_path}")
        
        self.face_cascade = cv2.CascadeClassifier(face_path)
        self.eye_cascade = cv2.CascadeClassifier(eye_path)
        
        if self.face_cascade.empty():
            raise IOError("Failed to load face cascade xml file.")
        if self.eye_cascade.empty():
            raise IOError("Failed to load eye cascade xml file.")
        
        
        
        self.last_pupil_pos = None
        self.alpha = 0.5

        # --- CALIBRATION VARIABLES ---
        self.baseline_y = None
        self.threshold_buffer = 0.0
        self.baseline_ratio = None
        self.eyes_off = False
        
        self.history_size = 12
        self.history = deque(maxlen=self.history_size)
        self.activation_threshold = 0.7

    def get_frame(self):
        if self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                return frame
        return None

    def detect_pupils(self, frame):
        """
        Returns: (frame, vertical_ratio)
        Uses Sub-Pixel 'Moments' for high precision tracking.
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Bilateral Filter
        gray = cv2.bilateralFilter(gray, 10, 25, 25)
        
        ratios = []
        
        faces = self.face_cascade.detectMultiScale(gray, 1.3, 5)

        for (fx, fy, fw, fh) in faces:
            # Draw Face Box
            cv2.rectangle(frame, (fx, fy), (fx+fw, fy+fh), (255, 0, 0), 1)

            # Only look for eyes in the top half
            roi_gray = gray[fy:fy+fh//2, fx:fx+fw]
            
            eyes = self.eye_cascade.detectMultiScale(roi_gray, 1.1, 3)
            
            for (ex, ey, ew, eh) in eyes:
                # Crop top 25% because eyebrows
                eyebrow_cut = int(eh * 0.25)
                eye_roi = roi_gray[ey + eyebrow_cut : ey + eh, ex : ex + ew]
                
                # Morphological Processing
                _, threshold = cv2.threshold(eye_roi, 40, 255, cv2.THRESH_BINARY_INV)
                
                # Opening
                kernel = np.ones((2, 2), np.uint8)
                threshold = cv2.erode(threshold, kernel, iterations=1)
                threshold = cv2.dilate(threshold, kernel, iterations=2)

                contours, _ = cv2.findContours(threshold, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
                contours = sorted(contours, key=lambda x: cv2.contourArea(x), reverse=True)
                
                if len(contours) > 0:
                    cnt = contours[0]
                    
                    # Image Moments (Center of Mass)
                    M = cv2.moments(cnt)
                    
                    if M['m00'] != 0:
                        cx = M['m10'] / M['m00']
                        cy = M['m01'] / M['m00']
                        
                        # Calculate Pupil Center relative to the original eye box
                        pupil_center_y = cy + eyebrow_cut
                        
                        # High Precision Ratio
                        ratio = pupil_center_y / eh
                        ratios.append(ratio)
                        
                        # --- VISUALS ---
                        global_x = int(fx + ex + cx)
                        global_y = int(fy + ey + pupil_center_y)
                        
                        # Eye Box
                        cv2.rectangle(frame, (fx+ex, fy+ey), (fx+ex+ew, fy+ey+eh), (0, 255, 0), 1)
                        # Pupil Dot (Small for precision)
                        cv2.circle(frame, (global_x, global_y), 2, (0, 0, 255), -1)

        avg_ratio = sum(ratios) / len(ratios) if ratios else None
        
        return frame, avg_ratio

    def calibrate(self, current_ratio):
        """Call this when looking DOWN."""
        if current_ratio is not None:
            self.baseline_ratio = current_ratio
            print(f"Calibration Set! Baseline Ratio: {self.baseline_ratio:.2f}")

    def check_gaze(self, current_ratio):
        """
        Returns: (smoothed_state, limit_ratio)
        smoothed_state is True ONLY if the majority of recent frames agree.
        """
        # Safety Check
        if current_ratio is None or self.baseline_ratio is None:
            return False, None

        limit = self.baseline_ratio - self.threshold_buffer

        is_up_raw = (current_ratio < limit)

        self.history.append(1 if is_up_raw else 0)

        # CALCULATE DENSITY
        if len(self.history) < self.history_size:
            return False, limit

        avg_score = sum(self.history) / self.history_size

        # DETERMINE FINAL STATE
        if avg_score > self.activation_threshold:
            self.eyes_off = True  # Looking UP 
        else:
            self.eyes_off = False # Looking DOWN

        return self.eyes_off, limit

    def release(self):
        self.cap.release()