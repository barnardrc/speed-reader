# -*- coding: utf-8 -*-
"""
Created on Thu Jan 15 01:37:24 2026

@author: barna
"""

from PyQt6.QtCore import QThread, pyqtSignal
from utils.eye_tracking.eye_tracker import EyeTracker

class EyeTrackingWorker(QThread):
    # Signal: (Frame, Ratio, EyesOff, Limit)
    # We pass the data back to the Main App via this signal
    update_signal = pyqtSignal(object, object, bool, object)
    
    def __init__(self):
        super().__init__()
        self.running = True
        self.tracker = None

    def run(self):
        # Initialize Tracker INSIDE the thread (Crucial for GStreamer stability)
        try:
            self.tracker = EyeTracker()
        except Exception as e:
            print(f"Worker failed to init camera: {e}")
            return

        while self.running:
            # 1. Get Frame (Blocking call, runs smoothly here)
            frame = self.tracker.get_frame()
            if frame is None: continue

            # 2. Process
            frame, avg_ratio = self.tracker.detect_pupils(frame)
            eyes_off, limit_ratio = self.tracker.check_gaze(avg_ratio)
            
            # 3. Emit Data back to Main Thread
            self.update_signal.emit(frame, avg_ratio, eyes_off, limit_ratio)

        # Cleanup
        self.tracker.release()

    def calibrate(self, current_ratio):
        # We need a thread-safe way to call calibrate
        if self.tracker:
            self.tracker.calibrate(current_ratio)

    def stop(self):
        self.running = False
        self.wait()