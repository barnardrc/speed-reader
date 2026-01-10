# -*- coding: utf-8 -*-
"""
Created on Sat Jan 10 10:56:09 2026

@author: barna
"""
import psutil
import platform
import subprocess
import shutil
import re

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
            # On Apple Silicon, VRAM is effectively System RAM
            return self.total_ram_gb

        # 2. Check for Nvidia GPU (Windows/Linux)
        if shutil.which("nvidia-smi"):
            try:
                # Query nvidia-smi for memory
                output = subprocess.check_output(
                    ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
                    encoding="utf-8"
                )
                # Sum up memory of all GPUs (for multi-GPU setups)
                total_vram_mb = sum(int(x) for x in output.strip().split('\n') if x.strip().isdigit())
                return round(total_vram_mb / 1024, 1)
            except Exception:
                pass
        
        # 3. Fallback (Intel/AMD Integrated or Drivers missing)
        return 0

    def get_recommendation(self):
        """Returns a recommendation dict based on hardware capabilities."""
        
        # Use VRAM if available (GPU/Mac), otherwise fall back to System RAM (CPU)
        # We subtract a safety buffer (e.g. 2GB for OS)
        available_mem = self.vram_gb if self.vram_gb > 0 else (self.total_ram_gb - 2)
        
        rec = {
            "hardware_type": "CPU (Slow)" if self.vram_gb == 0 else "GPU/Unified (Fast)",
            "detected_memory": f"{self.vram_gb} GB VRAM" if self.vram_gb > 0 else f"{self.total_ram_gb} GB RAM",
            "recommended_model_size": "Tiny (1B-3B)",
            "can_run_7b": False,
            "can_run_13b": False,
            "can_run_70b": False,
            "reasoning": ""
        }

        # Heuristics for 4-bit Quantized Models (Standard for Ollama)
        if available_mem >= 64:
            rec["recommended_model_size"] = "Large (70B+)"
            rec["can_run_7b"] = True
            rec["can_run_13b"] = True
            rec["can_run_70b"] = True
            rec["reasoning"] = "Excellent hardware. You can run almost any local model."
            
        elif available_mem >= 24:
            rec["recommended_model_size"] = "Medium-Large (30B-40B)"
            rec["can_run_7b"] = True
            rec["can_run_13b"] = True
            rec["can_run_70b"] = False
            rec["reasoning"] = "Great for high-quality coding/chat models like Mixtral 8x7B or Llama3 70B (tight fit)."
            
        elif available_mem >= 16:
            rec["recommended_model_size"] = "Medium (13B-14B)"
            rec["can_run_7b"] = True
            rec["can_run_13b"] = True
            rec["reasoning"] = "Perfect for Mistral, Qwen 14B, or Llama3 8B with large context."
            
        elif available_mem >= 8:
            rec["recommended_model_size"] = "Small (7B-8B)"
            rec["can_run_7b"] = True
            rec["reasoning"] = "Standard tier. Runs Llama3 8B, Mistral 7B efficiently."
            
        else:
            rec["reasoning"] = "Low memory. Stick to Phi-3 (3B) or tinyLlama for best performance."

        return rec