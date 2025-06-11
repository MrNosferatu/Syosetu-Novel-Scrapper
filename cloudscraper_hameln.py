#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import time
import logging
import subprocess
import importlib

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger('hameln_scraper')

# Try to import cloudscraper, install if not available
try:
    import cloudscraper
except ImportError:
    logger.info("Installing cloudscraper...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "cloudscraper"])
        import cloudscraper
        logger.info("cloudscraper installed successfully")
    except Exception as e:
        logger.error(f"Failed to install cloudscraper: {e}")
        logger.error("Please install manually with: pip install cloudscraper")
        sys.exit(1)

def get_hameln_chapter(novel_id, chapter_num):
    """Get Hameln chapter content using cloudscraper."""
    # Create a cloudscraper session to bypass JavaScript checks
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'firefox',
            'platform': 'windows',
            'mobile': False
        }
    )
    
    # Set cookie
    scraper.cookies.set('over18', 'off', domain='syosetu.org')
    
    # First visit the main site
    logger.info("Visiting main site...")
    main_response = scraper.get("https://syosetu.org/")
    main_response.raise_for_status()
    
    # Visit novel page
    novel_url = f"https://syosetu.org/novel/{novel_id}/"
    logger.info(f"Visiting novel page: {novel_url}")
    scraper.headers.update({'Referer': 'https://syosetu.org/'})
    novel_response = scraper.get(novel_url)
    novel_response.raise_for_status()
    
    # Wait a bit
    time.sleep(1)
    
    # Visit chapter page
    chapter_url = f"https://syosetu.org/novel/{novel_id}/{chapter_num}.html"
    logger.info(f"Visiting chapter page: {chapter_url}")
    scraper.headers.update({'Referer': novel_url})
    chapter_response = scraper.get(chapter_url)
    chapter_response.raise_for_status()
    
    # Print response info
    logger.info(f"Status: {chapter_response.status_code}")
    logger.info(f"Content length: {len(chapter_response.content)} bytes")
    logger.info(f"Content preview: {chapter_response.text[:200]}...")
    
    return chapter_response.text

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python cloudscraper_hameln.py NOVEL_ID CHAPTER_NUM")
        sys.exit(1)
    
    novel_id = sys.argv[1]
    chapter_num = sys.argv[2]
    
    try:
        content = get_hameln_chapter(novel_id, chapter_num)
        print("Successfully retrieved chapter content")
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)