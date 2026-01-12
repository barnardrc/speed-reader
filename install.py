import os
import sys
import subprocess
import platform
import shutil
import urllib.request
import time
import stat
import webbrowser
import winreg 
import ctypes.util
import json

# --- Configuration ---
REQUIREMENTS_FILE = "requirements.txt"
HARDWARE_MONITOR_MODULE = "utils.dependents" 
MAIN_ENTRY_POINT = "main.py" 

def get_venv_paths(venv_dir):
    """
    Robustly determines executable paths based on OS and directory structure.
    Does not assume a specific layout (Scripts vs bin) without checking.
    """
    if platform.system() == "Windows":
        # Check for standard venv layout
        python_candidates = [
            os.path.join(venv_dir, "Scripts", "python.exe"),
            os.path.join(venv_dir, "python.exe"),  # Conda style
        ]
        pip_candidates = [
            os.path.join(venv_dir, "Scripts", "pip.exe"),
            os.path.join(venv_dir, "Scripts", "pip3.exe"),
            os.path.join(venv_dir, "Library", "bin", "pip.exe"), # Some conda layouts
        ]
    else:
        # Linux/Unix
        python_candidates = [
            os.path.join(venv_dir, "bin", "python"),
            os.path.join(venv_dir, "bin", "python3"),
        ]
        pip_candidates = [
            os.path.join(venv_dir, "bin", "pip"),
            os.path.join(venv_dir, "bin", "pip3"),
        ]

    # Find valid python
    py_path = next((p for p in python_candidates if os.path.exists(p)), None)
    # Find valid pip
    pip_path = next((p for p in pip_candidates if os.path.exists(p)), None)

    return py_path, pip_path

def check_system_dependencies():
    """
    Checks for OS-specific dependencies and essential tools.
    """
    system = platform.system()
    
    # --- 1. Windows: Visual C++ Redistributable ---
    if system == "Windows":
        print("[*] Checking system dependencies...")
        
        is_64bits = sys.maxsize > 2**32
        arch_key = "x64" if is_64bits else "x86"
        key_path = f"SOFTWARE\\Microsoft\\VisualStudio\\14.0\\VC\\Runtimes\\{arch_key}"
        
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_READ)
            installed, _ = winreg.QueryValueEx(key, "Installed")
            winreg.CloseKey(key)
            
            if installed == 1:
                print(f"    - Visual C++ Redistributable ({arch_key}) detected.")
                return True
        except OSError:
            pass 

        print(f"\n[!] MISSING DEPENDENCY: Visual C++ Redistributable ({arch_key})")
        print("    Required for binaries (PyQt, Numpy, etc).")
        
        url = "https://aka.ms/vs/17/release/vc_redist.x64.exe" if is_64bits \
              else "https://aka.ms/vs/17/release/vc_redist.x86.exe"

        if input("    Open download page? (y/n): ").strip().lower() == 'y':
            webbrowser.open(url)
            print("    Install and restart this script.")
            sys.exit(1)
        return False

    # --- 2. Linux: System Libraries & Tools ---
    elif system == "Linux":
        print("[*] Checking Linux system dependencies...")
        
        # Check for 'curl' (Required for Ollama install)
        if not shutil.which("curl"):
            print("[!] CRITICAL: 'curl' is missing.")
            print("    Please install it: sudo apt install curl (or equivalent)")
            sys.exit(1)

        # Check for 'libxcb' (Required for PyQt6)
        if not ctypes.util.find_library("xcb"):
            print("\n[!] CRITICAL: 'libxcb' missing.")
            print("    PyQt6 requires this library to render windows.")
            print("    Run: sudo apt install libxcb-xinerama0 (Debian/Ubuntu)")
            if input("    Continue anyway? (y/n): ").strip().lower() != 'y':
                sys.exit(1)
            return False
            
        print("    - Dependencies (curl, libxcb) detected.")
        return True

    # --- 3. macOS: Essential Tools ---
    elif system == "Darwin":
        # macOS handles PyQt6 libraries automatically, but we still need curl.
        if not shutil.which("curl"):
            print("[!] CRITICAL: 'curl' is missing.")
            print("    This is unusual for macOS. Ensure Command Line Tools are installed.")
            print("    Run: xcode-select --install")
            sys.exit(1)
        return True

    return True

def create_venv_and_install():
    venv_dir = os.path.join(os.getcwd(), "venv")
    
    # 1. Create Environment
    if not os.path.exists(venv_dir):
        print(f"[+] Creating virtual environment in {venv_dir}...")
        
        # Check if running in Conda and Conda is available
        # Note: We use the CURRENT python version to ensure compatibility
        if "conda" in sys.version.lower() and shutil.which("conda"):
            print("    - Conda detected. Creating isolated conda env...")
            current_ver = f"{sys.version_info.major}.{sys.version_info.minor}"
            try:
                subprocess.check_call([
                    "conda", "create", "-p", venv_dir, 
                    f"python={current_ver}", "-y"
                ])
            except subprocess.CalledProcessError:
                print("    - Conda failed. Falling back to standard venv.")
                subprocess.check_call([sys.executable, "-m", "venv", "venv"])
        else:
            subprocess.check_call([sys.executable, "-m", "venv", "venv"])
    else:
        print("[*] Virtual environment exists.")

    # 2. Locate Binaries
    py_path, pip_path = get_venv_paths(venv_dir)
    
    if not py_path or not pip_path:
        print("[!] Error: Created venv but could not find Python/Pip executables.")
        print(f"    Searched in: {venv_dir}")
        sys.exit(1)

    # 3. Install Requirements
    if os.path.exists(REQUIREMENTS_FILE):
        print("[+] Installing dependencies...")
        # Clean environment to prevent leaking global packages into venv
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)
        
        try:
            # Use python -m pip to avoid shebang/path length issues on Windows
            subprocess.check_call(
                [py_path, "-m", "pip", "install", "-r", REQUIREMENTS_FILE],
                env=env
            )
        except subprocess.CalledProcessError:
            print("[!] Failed to install requirements.")
            sys.exit(1)

    return py_path

def download_progress(count, block_size, total_size):
    """
    Callback function to display download progress.
    """
    percent = int(count * block_size * 100 / total_size)
    if percent > 100: percent = 100
    sys.stdout.write(f"\r    - Downloading... {percent}%")
    sys.stdout.flush()

def check_and_install_ollama():
    """Checks for Ollama, installs if missing, and waits for service availability."""
    if shutil.which("ollama"):
        return True

    print("\n[!] Ollama not found.")
    if input("Install Ollama? (y/n): ").strip().lower() != 'y':
        return False

    system = platform.system()
    try:
        if system == "Windows":
            installer = "OllamaSetup.exe"
            print("[+] Downloading Ollama installer...")
            urllib.request.urlretrieve(
                "https://ollama.com/download/OllamaSetup.exe", 
                installer, 
                reporthook=download_progress
            )
            print("\n[+] Running installer (Please complete the setup wizard)...")
            subprocess.run([installer], check=True)
            if os.path.exists(installer): os.remove(installer)

        elif system in ["Linux", "Darwin"]:
            if not shutil.which("curl"):
                print("[!] Error: 'curl' is required.")
                return False
            
            print("[+] Running install script...")
            subprocess.run("curl -fL https://ollama.com/install.sh | sh", shell=True, check=True)
        
        print("\n[*] Waiting for Ollama service to start...")
        for _ in range(10):
            try:
                urllib.request.urlopen("http://localhost:11434", timeout=1)
                print("    - Service is up.")
                return True
            except Exception:
                time.sleep(2)
        
        print("[!] Warning: Ollama installed but service is not responding yet.")
        return True

    except Exception as e:
        print(f"\n[!] Installation failed: {e}")
        return False

def ensure_ollama_service():
    """
    Ensures the Ollama background service is running.
    If it's down, attempts to start it and waits for a heartbeat.
    """
    print("[*] Checking Ollama service status...")
    
    # 1. Try to connect to the API
    url = "http://localhost:11434"
    for _ in range(3): # Quick check (3 attempts)
        try:
            urllib.request.urlopen(url, timeout=0.5)
            return True # Service is up
        except (urllib.error.URLError, ConnectionRefusedError):
            time.sleep(0.5)

    print("    - Service is down. Attempting to start...")

    # 2. Start the service if unreachable
    try:
        if platform.system() == "Windows":
            # Start detached process to avoid blocking the script
            subprocess.Popen(
                ["ollama", "serve"], 
                creationflags=subprocess.CREATE_NO_WINDOW,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        else:
            # Linux/Mac
            subprocess.Popen(
                ["ollama", "serve"], 
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
    except Exception as e:
        print(f"[!] Failed to start Ollama service: {e}")
        return False

    # 3. Wait for startup (up to 20 seconds)
    print("    - Waiting for service to initialize...", end="", flush=True)
    for _ in range(20):
        try:
            urllib.request.urlopen(url, timeout=1)
            print(" Done.")
            return True
        except Exception:
            time.sleep(1)
            print(".", end="", flush=True)
            
    print("\n[!] Service failed to start automatically.")
    print("    Please open a separate terminal and run 'ollama serve'")
    return False

def pull_model(py_path):
    if not os.path.exists(os.path.join("utils", "dependents.py")):
        print("[!] Warning: utils/dependents.py not found. Skipping model detection.")
        return

    if not ensure_ollama_service():
        return

    cmd = [
        py_path, "-c",
        f"import sys, json; sys.path.append('.'); "
        f"from {HARDWARE_MONITOR_MODULE} import HardwareMonitor; "
        f"print(json.dumps(HardwareMonitor().get_recommendation()))"
    ]

    try:
        print("\n[+] Analyzing hardware for AI compatibility...")
        output = subprocess.check_output(cmd, text=True).strip()
        data = json.loads(output)
        
        model_tag = data.get('recommended_model_tag')
        # specific 'reason' key, or fallback to a generic string
        hw_type = data.get('hardware_type', 'Optimized for available CPU/GPU')
        memory = data.get('detected_memory', 'Optimized for your available VRAM/RAM') 
        
        print(f"    - HW:             {hw_type}")
        print(f"    - Memory:         {memory}")
        print(f"    - Recommendation: {model_tag}")

        # Check if already installed
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
        if model_tag in result.stdout:
            print(f"[*] Model '{model_tag}' is already installed.")
            return

        # User Confirmation
        print(f"\n    The model '{model_tag}' is required for this hardware profile.")
        confirm = input(f"    Download and install now? (y/n): ").strip().lower()
        
        if confirm == 'y':
            print("    - Pulling model (This may take a while)...")
            subprocess.run(["ollama", "pull", model_tag], check=True)
            print("    - Install complete.")
        else:
            print("    [!] Warning: No model installed. The application may not function correctly.")
        
    except Exception as e:
        print(f"[!] Model setup error: {e}")
        
def create_shortcuts(py_path):
    print("\n[+] Creating launch scripts...")
    system = platform.system()
    
    if system == "Windows":
        # Dynamic search for PyQt bin to avoid hardcoded paths
        # This handles different PyQt versions or other Qt bindings (PySide)
        venv_root = os.path.dirname(os.path.dirname(py_path))
        qt_search_path = os.path.join(venv_root, "Lib", "site-packages")
        qt_bin = None
        
        # Look for PyQt6 specific bin
        possible_qt = os.path.join(qt_search_path, "PyQt6", "Qt6", "bin")
        if os.path.exists(possible_qt):
            qt_bin = possible_qt

        with open("run.bat", "w") as f:
            f.write("@echo off\n")
            f.write("set QT_PLUGIN_PATH=\n") # Clear conflict vars
            if qt_bin:
                f.write(f'set "PATH={qt_bin};%PATH%"\n')
            f.write(f'"{py_path}" {MAIN_ENTRY_POINT}\n')
            f.write("pause\n")
            
    else:
        with open("run.sh", "w") as f:
            f.write("#!/bin/bash\n")
            f.write(f'"{py_path}" {MAIN_ENTRY_POINT}\n')
        os.chmod("run.sh", os.stat("run.sh").st_mode | stat.S_IEXEC)

def main():
    check_system_dependencies()
    
    # Returns the valid python executable path for future use
    venv_python = create_venv_and_install()
    
    if check_and_install_ollama():
        pull_model(venv_python)
        
    create_shortcuts(venv_python)
    
    print("\n=== Setup Complete ===")

if __name__ == "__main__":
    main()