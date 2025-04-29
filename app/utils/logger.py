import os
import sys
import datetime
import inspect
import traceback
from enum import Enum
from typing import Optional, TextIO

class LogLevel(Enum):
    INFO = 1
    WARNING = 2
    ERROR = 3
    DEBUG = 4

class Logger:
    """
    Custom logger implementation with support for different log levels and output destinations.
    """
    
    def __init__(self, name: str, log_file: Optional[str] = None, level: LogLevel = LogLevel.INFO, console_output: bool = True):
        """
        Initialize a new Logger instance.
        
        Args:
            name: Name of the logger (usually the module name)
            log_file: Optional path to a log file
            level: Minimum log level to record
            console_output: Whether to output logs to console
        """
        self.name = name
        self.level = level
        self.console_output = console_output
        self.log_file = log_file
        self.file_handle = None
        
        if log_file:
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            try:
                self.file_handle = open(log_file, 'a', encoding='utf-8')
            except Exception as e:
                print(f"Failed to open log file {log_file}: {str(e)}")
    
    def __del__(self):
        """Close file handle when logger is destroyed"""
        if self.file_handle:
            try:
                self.file_handle.close()
            except:
                pass
    
    def _log(self, level: LogLevel, message: str, *args, **kwargs):
        """Internal logging method"""
        if level.value < self.level.value:
            return
        
        # Format the message with args and kwargs if provided
        if args or kwargs:
            try:
                message = message.format(*args, **kwargs)
            except Exception as e:
                message = f"{message} (Format Error: {str(e)})"
        
        # Get caller information
        frame = inspect.currentframe().f_back.f_back
        filename = os.path.basename(frame.f_code.co_filename)
        lineno = frame.f_lineno
        
        # Create the log entry
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        level_name = level.name
        log_message = f"[{timestamp}] [{level_name}] [{self.name}:{filename}:{lineno}] {message}"
        
        # Output to console if enabled
        if self.console_output:
            # Use different colors for different log levels
            if level == LogLevel.INFO:
                print(log_message)
            elif level == LogLevel.WARNING:
                print(f"\033[93m{log_message}\033[0m")  # Yellow
            elif level == LogLevel.ERROR:
                print(f"\033[91m{log_message}\033[0m")  # Red
            elif level == LogLevel.DEBUG:
                print(f"\033[90m{log_message}\033[0m")  # Gray
        
        # Write to log file if available
        if self.file_handle:
            try:
                self.file_handle.write(log_message + "\n")
                self.file_handle.flush()
            except Exception as e:
                print(f"Failed to write to log file: {str(e)}")
    
    def info(self, message: str, *args, **kwargs):
        """Log an INFO level message"""
        self._log(LogLevel.INFO, message, *args, **kwargs)
    
    def warning(self, message: str, *args, **kwargs):
        """Log a WARNING level message"""
        self._log(LogLevel.WARNING, message, *args, **kwargs)
    
    def error(self, message: str, *args, **kwargs):
        """Log an ERROR level message"""
        self._log(LogLevel.ERROR, message, *args, **kwargs)
        
    def debug(self, message: str, *args, **kwargs):
        """Log a DEBUG level message"""
        self._log(LogLevel.DEBUG, message, *args, **kwargs)
    
    def exception(self, message: str, *args, exc_info=True, **kwargs):
        """Log an exception with traceback"""
        exc_text = traceback.format_exc() if exc_info else ""
        self._log(LogLevel.ERROR, f"{message}\n{exc_text}", *args, **kwargs)


# Create a module-level function to get or create loggers
_loggers = {}

def get_logger(name: str = None, log_file: Optional[str] = None, level: LogLevel = LogLevel.INFO):
    """
    Get or create a logger instance
    
    Args:
        name: The name of the logger (defaults to the module name if not provided)
        log_file: Optional path to log file
        level: Minimum log level to record
        
    Returns:
        Logger: A logger instance
    """
    if name is None:
        # Get the caller's module name if name not provided
        frame = inspect.currentframe().f_back
        name = os.path.splitext(os.path.basename(frame.f_code.co_filename))[0]
    
    # Return existing logger if it exists
    if name in _loggers:
        return _loggers[name]
    
    # Create new logger
    logger = Logger(name, log_file, level)
    _loggers[name] = logger
    return logger


# Create a default logger
default_logger = get_logger('root')