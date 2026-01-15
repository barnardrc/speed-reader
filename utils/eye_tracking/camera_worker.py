# -*- coding: utf-8 -*-
"""
Created on Thu Jan 15 01:37:24 2026

@author: barna
"""

from PyQt6.QtCore import QThread, pyqtSignal
from utils.eye_tracking.eye_tracker import EyeTracker

class EyeTrackingWorker(QThread):
    update_signal = pyqtSignal(object, object, bool, object)
    
    def __init__(self):
        super().__init__()
        self.running = True
        self.tracker = None

    def run(self):
        try:
            self.tracker = EyeTracker()
        except Exception as e:
            print(f"CRITICAL: Camera init failed: {e}")
            return

        print("EyeTrackingWorker: Started") # Debug print

        while self.running:
            try:
                # 1. Get Frame 
                frame = self.tracker.get_frame()
                if frame is None: 
                    continue

                # 2. Process
                frame, avg_ratio = self.tracker.detect_pupils(frame)
                
                # Guard against None if detection fails completely
                if avg_ratio is None:
                    # Send frame but indicate no eyes found
                    self.update_signal.emit(frame, None, True, 0.0)
                    continue

                eyes_off, limit_ratio = self.tracker.check_gaze(avg_ratio)
                
                # 3. Emit Data
                self.update_signal.emit(frame, avg_ratio, eyes_off, limit_ratio)

            except Exception as e:
                print(f"Error in EyeTracking loop: {e}")
                # Optional: self.running = False

        self.tracker.release()
        print("EyeTrackingWorker: Stopped")

    def calibrate(self, current_ratio):
        # Check if tracker is initialized to prevent AttributeError
        if hasattr(self, 'tracker') and self.tracker is not None:
            self.tracker.calibrate(current_ratio)
        else:
            print("Cannot calibrate: Tracker not initialized.")

    def stop(self):
        self.running = False
        self.wait()