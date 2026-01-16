# -*- coding: utf-8 -*-
"""
Created on Thu Jan 15 01:37:24 2026

@author: barna
"""

from PyQt6.QtCore import QThread, pyqtSignal
from utils.eye_tracking.eye_tracker import EyeTracker

class EyeTrackingWorker(QThread):
    # Signal 1: Logic (Lightweight, High Priority) - (avg_ratio, eyes_off, limit_ratio)
    logic_signal = pyqtSignal(float, bool, float)
    
    # Signal 2: Frame (Heavy, Low Priority) - (frame)
    frame_signal = pyqtSignal(object)
    
    def __init__(self):
        super().__init__()
        self.running = True
        self.tracker = None
        self.send_video = False # Default to OFF (Performance Mode)
        self.is_calibrating = False

    def set_debug_mode(self, enabled):
        """Toggle video frame emission"""
        self.send_video = enabled
    
    def start_calibration(self):
        """Call this from Main to trigger the 15-frame capture"""
        print("Worker: Starting Calibration Sequence...")
        self.is_calibrating = True

    def run(self):
        try:
            self.tracker = EyeTracker()
        except Exception as e:
            print(f"CRITICAL: Camera init failed: {e}")
            return

        print("EyeTrackingWorker: Started") 

        while self.running:
            try:
                # Get Frame 
                frame = self.tracker.get_frame()
                if frame is None: 
                    continue
                
                
                
                # Process
                frame, avg_ratio = self.tracker.detect_pupils(frame)
                
                if self.is_calibrating and avg_ratio is not None:
                    finished = self.tracker.calibrate_step(avg_ratio)
                    if finished:
                        self.is_calibrating = False
                
                if avg_ratio is None:
                    eyes_off = True
                    limit_ratio = None
                else:
                    eyes_off, limit_ratio = self.tracker.check_gaze(avg_ratio)
                
                
                # --- EMIT SIGNALS ---

                # 1. Logic (Always Emit)
                # Use -1.0 as sentinel for None to ensure consistent float types
                safe_ratio = avg_ratio if avg_ratio is not None else -1.0
                safe_limit = limit_ratio if limit_ratio is not None else -1.0
                
                self.logic_signal.emit(safe_ratio, eyes_off, safe_limit)

                # 2. Frame (Conditionally Emit)
                if self.send_video:
                    self.frame_signal.emit(frame)

            except Exception as e:
                print(f"Error in EyeTracking loop: {e}")
                self.running = False

        self.tracker.release()
        print("EyeTrackingWorker: Stopped")

    def calibrate(self, current_ratio):
        if hasattr(self, 'tracker') and self.tracker is not None:
            self.tracker.calibrate(current_ratio)
        else:
            print("Cannot calibrate: Tracker not initialized.")

    def stop(self):
        self.running = False
        self.wait()