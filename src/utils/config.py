"""
Configuration Management for Biomaterials Hackathon Analyser
Manages API keys, database connections, and application settings
"""

import os
from pathlib import Path
from typing import Dict, Any
import json

class Config:
    """Application configuration manager"""
    
    def __init__(self):
        self.config_dir = Path(__file__).parent.parent.parent / "config"
        self.config_file = self.config_dir / "config.json"
        self.env_file = self.config_dir / ".env"
        
        # Default configuration
        self.defaults = {
            "database": {
                "type": "sqlite",
                "path": "data/biomaterials.db"
            },
            "api_keys": {
                "ncbi_email": "",
                "ncbi_api_key": "",
                "openai_api_key": "",
                "materials_project_api_key": "",
                "uspto_api_key": "",
                "epa_comptox_api_key": "",
                "anthropic_api_key": ""
            },
            "literature_search": {
                "max_results_default": 100,
                "rate_limit_delay": 0.34,
                "cache_results": True,
                "cache_duration_days": 7
            },
            "materials_modeling": {
                "default_temperature": 37.0,
                "default_ph": 7.4,
                "simulation_timeout": 300
            },
            "ui_preferences": {
                "theme": "light",
                "auto_save": True,
                "auto_save_interval": 300
            },
            "export_formats": {
                "default_format": "pdf",
                "include_images": True,
                "include_citations": True
            },
            "tox_servers": {
                "admet_port": 8082,
                "comptox_port": 8083,
                "aop_port": 8084,
                "pbpk_port": 8085,
                "auto_start_admet": True,
                "auto_start_comptox": False,
                "auto_start_aop": True,
                "auto_start_pbpk": False
            },
        }
        
        self._config = self.defaults.copy()
        self.load_config()
    
    def load_config(self):
        """Load configuration from file"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    file_config = json.load(f)
                    self._deep_update(self._config, file_config)
                    
            # Load environment variables
            self._load_env_vars()
            
        except Exception as e:
            print(f"Warning: Could not load config file: {e}")
            print("Using default configuration")
    
    def _load_env_vars(self):
        """Load API keys and sensitive data from environment variables"""
        env_mappings = {
            "NCBI_EMAIL": ["api_keys", "ncbi_email"],
            "NCBI_API_KEY": ["api_keys", "ncbi_api_key"],
            "OPENAI_API_KEY": ["api_keys", "openai_api_key"],
            "MATERIALS_PROJECT_API_KEY": ["api_keys", "materials_project_api_key"],
            "USPTO_API_KEY": ["api_keys", "uspto_api_key"],
            "EPA_COMPTOX_API_KEY": ["api_keys", "epa_comptox_api_key"],
            "ANTHROPIC_API_KEY": ["api_keys", "anthropic_api_key"]
        }
        
        for env_var, config_path in env_mappings.items():
            value = os.getenv(env_var)
            if value:
                self._set_nested(self._config, config_path, value)
    
    def save_config(self):
        """Save current configuration to file"""
        try:
            # Create config directory if it doesn't exist
            self.config_dir.mkdir(exist_ok=True)
            
            # Don't save sensitive API keys to file
            config_to_save = self._config.copy()
            config_to_save["api_keys"] = {k: "" for k in config_to_save["api_keys"]}
            
            with open(self.config_file, 'w') as f:
                json.dump(config_to_save, f, indent=2)
                
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def get(self, *path) -> Any:
        """Get configuration value by path"""
        value = self._config
        for key in path:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None
        return value
    
    def set(self, *path_and_value):
        """Set configuration value by path"""
        if len(path_and_value) < 2:
            raise ValueError("Must provide path and value")
            
        *path, value = path_and_value
        self._set_nested(self._config, path, value)
    
    def _set_nested(self, dictionary: Dict, path: List[str], value: Any):
        """Set value in nested dictionary"""
        for key in path[:-1]:
            if key not in dictionary:
                dictionary[key] = {}
            dictionary = dictionary[key]
        dictionary[path[-1]] = value
    
    def _deep_update(self, base_dict: Dict, update_dict: Dict):
        """Recursively update nested dictionary"""
        for key, value in update_dict.items():
            if (key in base_dict and 
                isinstance(base_dict[key], dict) and 
                isinstance(value, dict)):
                self._deep_update(base_dict[key], value)
            else:
                base_dict[key] = value
    
    # Convenience methods for common configuration access
    @property
    def ncbi_email(self) -> str:
        return self.get("api_keys", "ncbi_email") or ""
    
    @property
    def ncbi_api_key(self) -> str:
        return self.get("api_keys", "ncbi_api_key") or ""
    
    @property
    def database_path(self) -> str:
        return self.get("database", "path") or "data/biomaterials.db"
    
    @property
    def max_search_results(self) -> int:
        return self.get("literature_search", "max_results_default") or 100
    @property
    def anthropic_api_key(self) -> str:
        return self.get("api_keys", "anthropic_api_key") or ""

    @property
    def epa_comptox_api_key(self) -> str:
        return self.get("api_keys", "epa_comptox_api_key") or ""

    @property
    def tox_server_port(self) -> dict:
        return {
            "admet": self.get("tox_servers", "admet_port") or 8082,
            "comptox": self.get("tox_servers", "comptox_port") or 8083,
            "aop": self.get("tox_servers", "aop_port") or 8084,
            "pbpk": self.get("tox_servers", "pbpk_port") or 8085,
        }

    @property
    def tox_auto_start(self) -> dict:
        """Which ToxMCP servers to auto-start at app launch."""
        return {
            "admet": self.get("tox_servers", "auto_start_admet") or True,
            "comptox": bool(self.epa_comptox_api_key),
            "aop": self.get("tox_servers", "auto_start_aop") or True,
            "pbpk": self.get("tox_servers", "auto_start_pbpk") or False,
        }


# Global configuration instance
config = Config()

# Environment setup helper
def create_env_template():
    """Create .env template file with required variables"""
    env_template = """
# Biomaterials Hackathon Analyser Environment Variables
# Copy this file to .env and fill in your API keys

# NCBI E-utilities (required for PubMed access)
NCBI_EMAIL=your-email@example.com
NCBI_API_KEY=your_ncbi_api_key_here

# OpenAI (for AI-powered analysis features)
OPENAI_API_KEY=your_openai_api_key_here

# Materials Project (for materials property data)
MATERIALS_PROJECT_API_KEY=your_materials_project_key_here

# USPTO (for patent analysis)
USPTO_API_KEY=your_uspto_api_key_here
"""
    
    env_file_path = Path(__file__).parent.parent.parent / "config" / ".env.template"
    env_file_path.parent.mkdir(exist_ok=True)
    
    with open(env_file_path, 'w') as f:
        f.write(env_template.strip())
    
    print(f"Created environment template at: {env_file_path}")
    print("Copy this to .env and fill in your API keys")

if __name__ == "__main__":
    # Create environment template
    create_env_template()
    
    # Test configuration
    print("Current configuration:")
    print(f"NCBI Email: {config.ncbi_email}")
    print(f"Database Path: {config.database_path}")
    print(f"Max Search Results: {config.max_search_results}")
