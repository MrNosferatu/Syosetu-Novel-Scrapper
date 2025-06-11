#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import argparse
from typing import Dict, Any, Optional

# Default configuration
DEFAULT_CONFIG = {
    "general": {
        "delay": 1.0,
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    },
    "translation": {
        "enabled": False,
        "service": "google",  # Options: google, deepl, mymemory, linguee, pons, libre, microsoft, qcri, papago, yandex, chatgpt, none
        "api_key": "",
        "target_language": "en",  # Target language code (e.g., en, fr, es)
        "translate_title": True,
        "translate_content": True,
        "concurrent_requests": 3,  # Number of concurrent translation requests
        "request_delay": 0.1,  # Delay between translation requests in seconds
        "max_retries": 3  # Maximum number of retry attempts for failed translations
    }
}

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".syosetu_scraper")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")


def ensure_config_dir():
    """Ensure the configuration directory exists."""
    if not os.path.exists(CONFIG_DIR):
        os.makedirs(CONFIG_DIR)


def load_config() -> Dict[str, Any]:
    """Load configuration from file or create default if not exists."""
    ensure_config_dir()
    
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                # Merge with default config to ensure all keys exist
                merged_config = DEFAULT_CONFIG.copy()
                for section, values in config.items():
                    if section in merged_config:
                        merged_config[section].update(values)
                    else:
                        merged_config[section] = values
                return merged_config
        except Exception as e:
            print(f"Error loading config: {e}. Using default configuration.")
            return DEFAULT_CONFIG
    else:
        # Create default config file
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG


def save_config(config: Dict[str, Any]):
    """Save configuration to file."""
    ensure_config_dir()
    
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        print(f"Error saving config: {e}")


def update_config(section: str, key: str, value: Any) -> Dict[str, Any]:
    """Update a specific configuration value."""
    config = load_config()
    
    if section not in config:
        config[section] = {}
    
    config[section][key] = value
    save_config(config)
    return config


def setup_cli_args():
    """Set up command line arguments for configuration."""
    parser = argparse.ArgumentParser(description="Syosetu Novel Scraper")
    
    # General configuration
    parser.add_argument("--delay", type=float, help="Delay between requests in seconds")
    
    # Translation configuration
    parser.add_argument("--translation", choices=["enable", "disable"], help="Enable or disable translation")
    parser.add_argument("--translator", choices=["google", "deepl", "mymemory", "linguee", "pons", "libre", 
                                               "microsoft", "qcri", "papago", "yandex", "chatgpt", "none"], 
                       help="Translation service to use")
    parser.add_argument("--api-key", help="API key for translation service")
    parser.add_argument("--target-lang", help="Target language code for translation (e.g., en, fr, es)")
    parser.add_argument("--translate-title", choices=["yes", "no"], help="Whether to translate chapter titles")
    parser.add_argument("--translate-content", choices=["yes", "no"], help="Whether to translate chapter content")
    parser.add_argument("--concurrent-requests", type=int, help="Number of concurrent translation requests")
    parser.add_argument("--request-delay", type=float, help="Delay between translation requests in seconds")
    parser.add_argument("--max-retries", type=int, help="Maximum number of retry attempts for failed translations")
    
    # Config management
    parser.add_argument("--show-config", action="store_true", help="Show current configuration")
    parser.add_argument("--reset-config", action="store_true", help="Reset configuration to defaults")
    
    return parser


def process_cli_args(args):
    """Process command line arguments and update configuration."""
    config = load_config()
    changes_made = False
    
    # General configuration
    if args.delay is not None:
        config = update_config("general", "delay", args.delay)
        changes_made = True
    
    # Translation configuration
    if args.translation:
        config = update_config("translation", "enabled", args.translation == "enable")
        changes_made = True
    
    if args.translator:
        config = update_config("translation", "service", args.translator)
        changes_made = True
    
    if args.api_key:
        config = update_config("translation", "api_key", args.api_key)
        changes_made = True
    
    if args.target_lang:
        config = update_config("translation", "target_language", args.target_lang)
        changes_made = True
    
    if args.translate_title:
        config = update_config("translation", "translate_title", args.translate_title == "yes")
        changes_made = True
    
    if args.translate_content:
        config = update_config("translation", "translate_content", args.translate_content == "yes")
        changes_made = True
        
    if args.concurrent_requests is not None:
        config = update_config("translation", "concurrent_requests", args.concurrent_requests)
        changes_made = True
        
    if args.request_delay is not None:
        config = update_config("translation", "request_delay", args.request_delay)
        changes_made = True
        
    if args.max_retries is not None:
        config = update_config("translation", "max_retries", args.max_retries)
        changes_made = True
    

    
    # Config management
    if args.reset_config:
        save_config(DEFAULT_CONFIG)
        print("Configuration reset to defaults.")
        return DEFAULT_CONFIG
    
    if args.show_config or changes_made:
        print("\nCurrent Configuration:")
        print(json.dumps(config, indent=4))
    
    return config