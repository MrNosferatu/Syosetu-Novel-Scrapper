#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
import sys
import subprocess
import concurrent.futures
from typing import Dict, List, Optional, Union, Any
from abc import ABC, abstractmethod

# Try to import deep-translator, install if not available
try:
    from deep_translator import GoogleTranslator
    DEEP_TRANSLATOR_AVAILABLE = True
except ImportError:
    DEEP_TRANSLATOR_AVAILABLE = False
    print("Installing deep-translator library...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "deep-translator"])
        print("deep-translator installed successfully!")
        from deep_translator import GoogleTranslator
        DEEP_TRANSLATOR_AVAILABLE = True
    except Exception as e:
        print(f"Failed to install deep-translator: {e}")
        print("Please install manually with: pip install deep-translator")

# Import all translators if available
if DEEP_TRANSLATOR_AVAILABLE:
    try:
        from deep_translator import (
            GoogleTranslator,
            DeepL,
            MyMemoryTranslator,
            LingueeTranslator,
            PonsTranslator,
            LibreTranslator,
            MicrosoftTranslator,
            QcriTranslator,
            PapagoTranslator,
            YandexTranslator,
            ChatGptTranslator
        )
    except ImportError:
        # Some translators might not be available in older versions
        pass


class BaseTranslator(ABC):
    """Base class for translation services."""
    
    @abstractmethod
    def translate_text(self, text: str, target_language: str = "en") -> str:
        """Translate text to target language."""
        pass
    
    @abstractmethod
    def batch_translate(self, texts: List[str], target_language: str = "en") -> List[str]:
        """Translate multiple texts at once."""
        pass


class DeepTranslator(BaseTranslator):
    """Unified translator using deep-translator library."""
    
    def __init__(self, service: str = "google", api_key: Optional[str] = None, target_language: str = "en", 
                 concurrent_requests: int = 3, request_delay: float = 0.1, max_retries: int = 3):
        """Initialize translator with specified service."""
        self.service = service.lower()
        self.api_key = api_key
        self.translator = None
        self.target_language = target_language
        self.concurrent_requests = concurrent_requests
        self.request_delay = request_delay
        self.max_retries = max_retries
        
        if not DEEP_TRANSLATOR_AVAILABLE:
            print("Warning: deep-translator library not available. Translation will not work.")
            return
        
        try:
            if self.service == "google":
                self.translator = GoogleTranslator(source="auto", target=target_language)
            elif self.service == "deepl" and api_key and 'DeepL' in globals():
                self.translator = DeepL(api_key=api_key, target=target_language)
            elif self.service == "mymemory" and 'MyMemoryTranslator' in globals():
                self.translator = MyMemoryTranslator(source="auto", target=target_language)
            elif self.service == "linguee" and 'LingueeTranslator' in globals():
                self.translator = LingueeTranslator(source="auto", target=target_language)
            elif self.service == "pons" and 'PonsTranslator' in globals():
                self.translator = PonsTranslator(source="auto", target=target_language)
            elif self.service == "libre" and 'LibreTranslator' in globals():
                self.translator = LibreTranslator(source="auto", target=target_language)
            elif self.service == "microsoft" and api_key and 'MicrosoftTranslator' in globals():
                self.translator = MicrosoftTranslator(api_key=api_key, target=target_language)
            elif self.service == "qcri" and api_key and 'QcriTranslator' in globals():
                self.translator = QcriTranslator(api_key=api_key, target=target_language)
            elif self.service == "papago" and api_key and 'PapagoTranslator' in globals():
                self.translator = PapagoTranslator(api_key=api_key, target=target_language)
            elif self.service == "yandex" and api_key and 'YandexTranslator' in globals():
                self.translator = YandexTranslator(api_key=api_key, target=target_language)
            elif self.service == "chatgpt" and api_key and 'ChatGptTranslator' in globals():
                self.translator = ChatGptTranslator(api_key=api_key, target=target_language)
            else:
                # Default to Google if service not recognized or not available
                print(f"Using Google Translate as fallback")
                self.translator = GoogleTranslator(source="auto", target=target_language)
        except Exception as e:
            print(f"Error initializing translator: {e}")
            # Fallback to Google
            try:
                self.translator = GoogleTranslator(source="auto", target=target_language)
            except:
                self.translator = None
    
    def translate_text(self, text: str, target_language: str = "en") -> str:
        """Translate text using selected service."""
        if not text or text.isspace() or not self.translator:
            return text
        
        retries = 0
        while retries <= self.max_retries:
            try:
                # Set target language
                if hasattr(self.translator, "target"):
                    self.translator.target = target_language
                
                # Handle text length limitations
                if len(text) > 5000:  # Most services have limits around 5000 chars
                    parts = []
                    for i in range(0, len(text), 4000):  # Split with some overlap
                        part = text[i:i+4000]
                        parts.append(self.translator.translate(part))
                    return "".join(parts)
                else:
                    return self.translator.translate(text)
            except Exception as e:
                retries += 1
                if retries <= self.max_retries:
                    print(f"Translation error: {e}. Retrying in 5 seconds... (Attempt {retries}/{self.max_retries})")
                    time.sleep(5)  # Wait 5 seconds before retrying
                else:
                    print(f"Translation failed after {self.max_retries} attempts: {e}")
                    return text
    
    def batch_translate(self, texts: List[str], target_language: str = "en") -> List[str]:
        """Translate multiple texts concurrently."""
        if not texts or not self.translator:
            return texts
        
        # Use sequential translation if concurrent_requests is 1 or less
        if self.concurrent_requests <= 1:
            results = []
            for text in texts:
                results.append(self.translate_text(text, target_language))
                time.sleep(self.request_delay)
            return results
        
        # Helper function for concurrent translation
        def translate_with_delay(text):
            result = self.translate_text(text, target_language)
            time.sleep(self.request_delay)  # Add delay to avoid rate limiting
            return result
        
        # Use ThreadPoolExecutor for concurrent translation
        results = [None] * len(texts)
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.concurrent_requests) as executor:
            # Submit all translation tasks
            future_to_index = {
                executor.submit(translate_with_delay, text): i 
                for i, text in enumerate(texts)
            }
            
            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    results[index] = future.result()
                except Exception as e:
                    print(f"Translation error for text at index {index}: {e}")
                    # The translate_text method now handles retries internally
                    results[index] = texts[index]  # Use original text if all retries fail
        
        return results


class DummyTranslator(BaseTranslator):
    """Dummy translator that doesn't actually translate."""
    
    def translate_text(self, text: str, target_language: str = "en") -> str:
        """Return the original text without translation."""
        return text
    
    def batch_translate(self, texts: List[str], target_language: str = "en") -> List[str]:
        """Return the original texts without translation."""
        return texts


def get_translator(service: str, api_key: Optional[str] = None, target_language: str = "en", 
               concurrent_requests: int = 3, request_delay: float = 0.1, max_retries: int = 3, **kwargs) -> BaseTranslator:
    """Get the appropriate translator based on service name."""
    if not DEEP_TRANSLATOR_AVAILABLE:
        print("Warning: deep-translator not available. Translation will not work.")
        return DummyTranslator()
    
    if service.lower() == "none":
        return DummyTranslator()
    
    return DeepTranslator(service, api_key, target_language, concurrent_requests, request_delay, max_retries)