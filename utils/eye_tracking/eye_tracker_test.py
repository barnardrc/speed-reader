import cv2
import numpy as np
from eye_tracker import EyeTracker

tracker = EyeTracker()
print("Press 'c' while looking at the BOTTOM STRIP to calibrate.")
print("Press 'q' to quit.")

while True:
    frame = tracker.get_frame()
    if frame is None: continue

    # 1. Get Pupil Ratio (0.0=Top, 1.0=Bottom)
    frame, avg_ratio = tracker.detect_pupils(frame)

    # 2. Check Logic
    eyes_off, limit_ratio = tracker.check_gaze(avg_ratio)

    # --- VISUAL FEEDBACK (New Logic) ---
    
    # Define text colors
    red = (0, 0, 255)
    green = (0, 255, 0)
    white = (255, 255, 255)
    
    # Status Message
    if tracker.baseline_ratio is None:
        msg = "UNCALIBRATED (Look Down & Press 'c')"
        color = white
    elif eyes_off:
        msg = "EYES OFF (LOOKING UP)"
        color = red
    else:
        msg = "Eyes On (Looking Down)"
        color = green

    cv2.putText(frame, msg, (10, 200), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

    # --- DRAW THE RATIO BAR (Visual Debugging) ---
    # Since we can't draw a line on the face, we draw a "Gaze Meter" on the side
    if avg_ratio is not None:
        # Draw Background Bar (Top-Right corner)
        bar_x = 600
        bar_top = 50
        bar_height = 200
        bar_width = 20
        cv2.rectangle(frame, (bar_x, bar_top), (bar_x + bar_width, bar_top + bar_height), (100, 100, 100), -1)
        
        # Draw Current Gaze Position (Map 0.0-1.0 to pixel height)
        # Note: avg_ratio 0 is Top, 1 is Bottom
        current_y = int(bar_top + (avg_ratio * bar_height))
        cv2.circle(frame, (bar_x + 10, current_y), 8, (0, 255, 255), -1) # Yellow Dot = Your Eye
        
        # Draw Threshold Line (if calibrated)
        if limit_ratio is not None:
            limit_y = int(bar_top + (limit_ratio * bar_height))
            cv2.line(frame, (bar_x - 10, limit_y), (bar_x + 30, limit_y), (0, 0, 255), 2) # Red Line = Trigger
            
            # Label
            cv2.putText(frame, "Limit", (bar_x - 50, limit_y + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, white, 1)

    cv2.imshow("Gaze Logic Test", frame)

    # --- CONTROLS ---
    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break
    elif key == ord('c'):
        tracker.calibrate(avg_ratio)

tracker.release()
cv2.destroyAllWindows()