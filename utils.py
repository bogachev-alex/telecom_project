"""
Utility functions for configuration and common operations.
"""
import yaml


def load_config(file_path: str) -> dict:
    """
    Load YAML configuration file.
    
    Args:
        file_path: Path to the YAML config file
        
    Returns:
        Parsed configuration dictionary
    """
    with open(file_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


