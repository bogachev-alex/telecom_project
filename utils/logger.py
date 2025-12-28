"""
Logging utility for network simulation.
"""
import logging
import sys
from datetime import datetime
import os


class SimulationLogger:
    """Logger that writes to both console and file."""
    
    def __init__(self, log_file="simulation.log"):
        self.log_file = log_file
        self.logger = logging.getLogger('simulation')
        self.logger.setLevel(logging.INFO)
        
        # Clear existing handlers
        self.logger.handlers = []
        
        # File handler
        file_handler = logging.FileHandler(log_file, mode='w', encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        file_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', 
                                       datefmt='%Y-%m-%d %H:%M:%S')
        file_handler.setFormatter(file_format)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_format = logging.Formatter('%(message)s')
        console_handler.setFormatter(console_format)
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def info(self, message):
        """Log info message."""
        self.logger.info(message)
    
    def debug(self, message):
        """Log debug message."""
        self.logger.debug(message)
    
    def warning(self, message):
        """Log warning message."""
        self.logger.warning(message)
    
    def error(self, message):
        """Log error message."""
        self.logger.error(message)
    
    def print(self, message):
        """Print message (alias for info)."""
        self.info(message)


# Global logger instance
_logger = None


def init_logger(log_file="simulation.log"):
    """Initialize global logger."""
    global _logger
    _logger = SimulationLogger(log_file)
    return _logger


def get_logger():
    """Get global logger instance."""
    global _logger
    if _logger is None:
        _logger = SimulationLogger()
    return _logger

