# utils/ai_backend.py
import socket
import requests

class AIBackendManager:
    def __init__(self, settings_dict):
        self.settings = settings_dict
        
        # Load settings or defaults
        self.backend_type = self.settings.get("ai_backend_type", "ollama")
        self.ollama_url = self.settings.get("ollama_url", "http://localhost:11434")
        self.selected_model = self.settings.get("ai_model", "llama3")
        
        self.available_models = []
        self.is_connected = False
        
        # General Config
        self.timeout = self.settings.get("ai_timeout", 30)
        self.max_context_length = 1000 
        self.comprehension_overlap = 200
        self.entity_overlap = 20
        

    def check_status(self):
        """
        Checks connectivity and updates available models.
        Returns: (bool, str) -> (Success, Message)
        """
        if self.backend_type == "ollama":
            return self._check_ollama()
        
        # Placeholder for Cloud implementation
        return False, "Unknown Backend"

    def _check_ollama(self):
        # 1. Quick Port Check
        host = self.ollama_url.replace("http://", "").replace("https://", "").split(":")[0]
        port = 11434
        try:
            with socket.create_connection((host, port), timeout=1):
                pass
        except (socket.timeout, ConnectionRefusedError, OSError):
            self.is_connected = False
            return False, f"Ollama unreachable at {host}:{port}"

        # 2. Fetch Models (API Check)
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=2)
            if response.status_code == 200:
                data = response.json()
                self.available_models = [m['name'] for m in data.get('models', [])]
                self.is_connected = True
                
                # Validate selected model
                if self.selected_model not in self.available_models and self.available_models:
                    # Fallback if previous model is missing
                    self.selected_model = self.available_models[0]
                
                return True, "Ollama Connected"
        except Exception as e:
            pass
        
        self.is_connected = False
        return False, "Port open, but API failed"

    def get_available_models(self):
        return self.available_models

    def set_model(self, model_name):
        self.selected_model = model_name
        self.settings["ai_model"] = model_name