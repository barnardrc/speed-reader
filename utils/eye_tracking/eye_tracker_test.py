import cv2
import numpy as np
from eye_tracker import EyeTracker

# --- GLOBAL VARIABLES FOR MOUSE INTERACTION ---
button_rect = (20, 20, 160, 50)  # (x, y, width, height)
calibration_triggered = False

def mouse_callback(event, x, y, flags, param):
    global calibration_triggered
    if event == cv2.EVENT_LBUTTONDOWN:
        bx, by, bw, bh = button_rect
        # Check if click is inside the button rect
        if bx <= x <= bx + bw and by <= y <= by + bh:
            calibration_triggered = True

# --- INITIALIZATION ---
tracker = EyeTracker()
window_name = "Gaze Logic Test"

cv2.namedWindow(window_name)
cv2.setMouseCallback(window_name, mouse_callback)

print("Click 'CALIBRATE' or press 'c' while looking at the BOTTOM STRIP.")
print("Press 'q' to quit.")

while True:
    frame = tracker.get_frame()
    if frame is None: continue

    # 1. Get Pupil Ratio (0.0=Top, 1.0=Bottom)
    frame, avg_ratio = tracker.detect_pupils(frame)

    # 2. Check Logic
    eyes_off, limit_ratio = tracker.check_gaze(avg_ratio)

    # --- CALIBRATION LOGIC (Button or Key) ---
    if calibration_triggered:
        if avg_ratio is not None:
            tracker.calibrate(avg_ratio)
            print(f"Calibrated at Ratio: {avg_ratio:.2f}")
        else:
            print("Cannot calibrate: No eyes detected.")
        calibration_triggered = False

    # --- VISUAL FEEDBACK ---
    
    # Define text colors
    red = (0, 0, 255)
    green = (0, 255, 0)
    white = (255, 255, 255)
    grey = (100, 100, 100)
    btn_color = (200, 200, 200) # Light Grey
    
    # Status Message
    if tracker.baseline_ratio is None:
        msg = "UNCALIBRATED"
        color = white
    elif eyes_off:
        msg = "EYES OFF (LOOKING UP)"
        color = red
    else:
        msg = "Eyes On (Looking Down)"
        color = green

    cv2.putText(frame, msg, (10, 200), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

    # --- DRAW UI BUTTON ---
    bx, by, bw, bh = button_rect
    # Draw Button Background
    cv2.rectangle(frame, (bx, by), (bx + bw, by + bh), btn_color, -1)
    # Draw Button Border
    cv2.rectangle(frame, (bx, by), (bx + bw, by + bh), (50, 50, 50), 2)
    # Draw Button Text
    cv2.putText(frame, "CALIBRATE", (bx + 15, by + 35), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)

    # --- DRAW THE RATIO BAR ---
    if avg_ratio is not None:
        bar_x = 600
        bar_top = 50
        bar_height = 200
        bar_width = 20
        
        # Background
        cv2.rectangle(frame, (bar_x, bar_top), (bar_x + bar_width, bar_top + bar_height), (100, 100, 100), -1)
        
        # Current Gaze Dot
        safe_ratio = max(0.0, min(1.0, avg_ratio))
        current_y = int(bar_top + (safe_ratio * bar_height))
        cv2.circle(frame, (bar_x + 10, current_y), 8, (0, 255, 255), -1) 
        
        # Limit Line
        if limit_ratio is not None:
            limit_y = int(bar_top + (limit_ratio * bar_height))
            cv2.line(frame, (bar_x - 10, limit_y), (bar_x + 30, limit_y), (0, 0, 255), 2)
            cv2.putText(frame, "Limit", (bar_x - 50, limit_y + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, white, 1)

    cv2.imshow(window_name, frame)

    # --- CONTROLS ---
    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break
    elif key == ord('c'):
        calibration_triggered = True

tracker.release()
cv2.destroyAllWindows()