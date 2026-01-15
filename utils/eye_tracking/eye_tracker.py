# -*- coding: utf-8 -*-
#eye_tracker.py
"""
Created on Wed Jan 14 19:23:59 2026

@author: barna
"""

import cv2
import os
import numpy as np

class EyeTracker:
    def __init__(self):
        # --- PATH SETUP ---
        base_dir = os.path.dirname(os.path.abspath(__file__))
        face_path = os.path.join(base_dir, 'haarcascade_frontalface_default.xml')
        eye_path = os.path.join(base_dir, 'haarcascade_eye.xml')

        # --- CAMERA SETUP ---
        # Using the Pipeline that worked for you (NV12 -> BGR)
        self.pipeline = (
            "libcamerasrc ! "
            "video/x-raw, width=640, height=480, framerate=30/1 ! "
            "videoconvert ! "
            "video/x-raw, format=BGR ! "
            "appsink drop=1"
        )
        self.cap = cv2.VideoCapture(self.pipeline, cv2.CAP_GSTREAMER)
        
        if not self.cap.isOpened():
            raise RuntimeError("Camera failed to initialize.")

        # --- MODEL SETUP ---
        self.face_cascade = cv2.CascadeClassifier(face_path)
        self.eye_cascade = cv2.CascadeClassifier(eye_path)

        # --- CALIBRATION VARIABLES ---
        self.baseline_y = None  # Stores the Y position when looking at the bottom strip
        self.threshold_buffer = 15  # Pixels of "wiggle room" before triggering
        self.eyes_off = False       # The Flag you requested

    def get_frame(self):
        if self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                return frame
        return None

    def detect_pupils(self, frame):
        """
        Returns: (frame, y_average)
        y_average is the average Y-coordinate of all detected pupils.
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        pupil_y_coords = []
        
        faces = self.face_cascade.detectMultiScale(gray, 1.3, 5)

        for (fx, fy, fw, fh) in faces:
            roi_gray = gray[fy:fy+fh, fx:fx+fw]
            
            # Detect Eyes within the face
            eyes = self.eye_cascade.detectMultiScale(roi_gray, 1.1, 5)
            
            for (ex, ey, ew, eh) in eyes:
                eye_roi = roi_gray[ey:ey+eh, ex:ex+ew]
                
                # BLOB DETECTION (Inverted Threshold)
                # Adjust '40' if pupils are lost
                _, threshold = cv2.threshold(eye_roi, 40, 255, cv2.THRESH_BINARY_INV)
                contours, _ = cv2.findContours(threshold, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
                contours = sorted(contours, key=lambda x: cv2.contourArea(x), reverse=True)
                
                if len(contours) > 0:
                    cnt = contours[0]
                    (cx, cy, cw, ch) = cv2.boundingRect(cnt)
                    
                    # Calculate Global Y coordinate
                    # Face Y + Eye Y + Blob Y + Blob Center Offset
                    pupil_y = fy + ey + cy + ch // 2
                    pupil_x = fx + ex + cx + cw // 2
                    
                    pupil_y_coords.append(pupil_y)
                    
                    # VISUAL DEBUGGING
                    # Green Box = Eye, Red Dot = Pupil
                    cv2.rectangle(frame, (fx+ex, fy+ey), (fx+ex+ew, fy+ey+eh), (0, 255, 0), 1)
                    cv2.circle(frame, (pupil_x, pupil_y), 4, (0, 0, 255), -1)

        # Calculate average Y of both eyes for stability
        avg_y = int(sum(pupil_y_coords) / len(pupil_y_coords)) if pupil_y_coords else None
        
        return frame, avg_y

    def calibrate(self, current_y):
        """Call this when user is looking at the bottom strip."""
        if current_y is not None:
            self.baseline_y = current_y
            print(f"Calibration Set! Baseline Y: {self.baseline_y}")

    def check_gaze(self, current_y):
        """
        Determines if eyes have moved UP past the threshold.
        """
        if current_y is None or self.baseline_y is None:
            return False

        # LOGIC:
        # If current Y is LESS than (Baseline - Buffer), we are looking UP.
        limit = self.baseline_y - self.threshold_buffer
        
        if current_y < limit:
            self.eyes_off = True
        else:
            self.eyes_off = False
            
        return self.eyes_off, limit

    def release(self):
        self.cap.release()