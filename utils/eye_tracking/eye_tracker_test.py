# -*- coding: utf-8 -*-
# eye_tracker_test.py
"""
Created on Wed Jan 14 19:24:20 2026

@author: barna
"""

import cv2
from eye_tracker import EyeTracker

tracker = EyeTracker()
print("Press 'c' while looking at the BOTTOM STRIP to calibrate.")
print("Press 'q' to quit.")

while True:
    frame = tracker.get_frame()
    if frame is None: continue

    # 1. Get Pupil Y
    frame, avg_y = tracker.detect_pupils(frame)

    # 2. Check Logic
    eyes_off, limit_line = tracker.check_gaze(avg_y)

    # --- VISUAL FEEDBACK ---
    
    # Draw the Threshold Line (Blue)
    if limit_line:
        cv2.line(frame, (0, limit_line), (640, limit_line), (255, 255, 0), 2)

    # Status Text
    if tracker.baseline_y is None:
        msg = "UNCALIBRATED (Look Down & Press 'c')"
        color = (255, 255, 255) # White
    elif eyes_off:
        msg = "EYES OFF (LOOKING UP)"
        color = (0, 0, 255) # Red
    else:
        msg = "Eyes On (Looking Down)"
        color = (0, 255, 0) # Green

    cv2.putText(frame, msg, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

    cv2.imshow("Gaze Logic Test", frame)

    # --- CONTROLS ---
    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break
    elif key == ord('c'):
        # Save the current Y as the "Low" position
        tracker.calibrate(avg_y)

tracker.release()
cv2.destroyAllWindows()