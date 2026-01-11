# -*- coding: utf-8 -*-
"""
Created on Sat Jan 10 20:42:08 2026
@author: barna
"""
import psutil
import platform
import subprocess
import shutil

class HardwareMonitor:
    def __init__(self):
        self.os_type = platform.system()
        self.total_ram_gb = self._get_system_ram()
        self.vram_gb = self._get_gpu_vram()
        
    def _get_system_ram(self):
        """Returns total system RAM in GB."""
        try:
            mem = psutil.virtual_memory()
            return round(mem.total / (1024 ** 3), 1)
        except Exception:
            return 0

    def _get_gpu_vram(self):
        """
        Attempts to find GPU VRAM. 
        - Windows/Linux: Checks for Nvidia GPUs via nvidia-smi.
        - macOS: Returns System RAM (Unified Memory).
        - Fallback: Returns 0 (Assume CPU only).
        """
        # Apple Silicon Check
        if self.os_type == 'Darwin':
            return self.total_ram_gb

        # Check for Nvidia GPU (Windows/Linux)
        if shutil.which("nvidia-smi"):
            try:
                output = subprocess.check_output(
                    ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
                    encoding="utf-8"
                )
                total_vram_mb = sum(int(x) for x in output.strip().split('\n') if x.strip().isdigit())
                return round(total_vram_mb / 1024, 1)
            except Exception:
                pass
        
        return 0

    def get_recommendation(self):
        """Returns a recommendation dict based on hardware capabilities."""
        
        # Use VRAM if available (GPU/Mac), otherwise fall back to System RAM (CPU)
        # Subtract safety buffer (e.g. 2GB for OS)
        available_mem = self.vram_gb if self.vram_gb > 0 else (self.total_ram_gb - 2)
        
        rec = {
            "hardware_type": "CPU (Slow)" if self.vram_gb == 0 else "GPU/Unified (Fast)",
            "detected_memory": f"{self.vram_gb} GB VRAM" if self.vram_gb > 0 else f"{self.total_ram_gb} GB RAM",
            "recommended_model_tag": "phi3", # Default
            "can_run_70b": False
        }

        # Heuristics for 4-bit Quantized Models
        if available_mem >= 64:
            rec["recommended_model_tag"] = "llama3:70b"
            rec["can_run_70b"] = True
            
        elif available_mem >= 24:
            rec["recommended_model_tag"] = "mixtral"
            
        elif available_mem >= 16:
            rec["recommended_model_tag"] = "qwen2.5:14b"
            
        elif available_mem >= 8:
            rec["recommended_model_tag"] = "llama3"
            
        else:
            rec["recommended_model_tag"] = "phi3"

        return rec