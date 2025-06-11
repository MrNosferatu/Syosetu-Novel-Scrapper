#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
from bs4 import BeautifulSoup
import re
import json
import time
import logging
import argparse
import sys
import os
import subprocess
import importlib
from typing import Dict, List, Optional, Union, Any
from site_parsers import get_parser
from config import load_config, setup_cli_args, process_cli_args

# Try to import rich, install if not available
try:
    from rich.progress import Progress, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn
    from rich.console import Console
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("Installing rich library...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "rich"])
        print("rich installed successfully!")
        from rich.progress import Progress, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn
        from rich.console import Console
        RICH_AVAILABLE = True
    except Exception as e:
        print(f"Failed to install rich: {e}")
        print("Please install manually with: pip install rich")
        RICH_AVAILABLE = False

# Configure logging - only show errors by default
logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger('syosetu_scraper')

# Try to import cloudscraper for Hameln site
try:
    import cloudscraper
    CLOUDSCRAPER_AVAILABLE = True
except ImportError:
    CLOUDSCRAPER_AVAILABLE = False


class SyosetuScraper:
    """A flexible scraper for various Syosetu web novel sites."""
    
    # Base URLs for different Syosetu sites
    SITES = {
        'ncode': 'https://ncode.syosetu.com',
        'novel18': 'https://novel18.syosetu.com',
        'mnlt': 'https://mnlt.syosetu.com',
        'yomou': 'https://yomou.syosetu.com',
        'hameln': 'https://syosetu.org'
    }
    
    # URL patterns for different sites
    URL_PATTERNS = {
        'ncode': {
            'novel': '{base_url}/{novel_id}/',
            'chapter': '{base_url}/{novel_id}/{chapter}'
        },
        'novel18': {
            'novel': '{base_url}/{novel_id}/',
            'chapter': '{base_url}/{novel_id}/{chapter}'
        },
        'mnlt': {
            'novel': '{base_url}/{novel_id}/',
            'chapter': '{base_url}/{novel_id}/{chapter}'
        },
        'yomou': {
            'novel': '{base_url}/{novel_id}/',
            'chapter': '{base_url}/{novel_id}/{chapter}'
        },
        'hameln': {
            'novel': '{base_url}/novel/{novel_id}/',
            'chapter': '{base_url}/novel/{novel_id}/{chapter}.html'
        }
    }
    
    def __init__(self, site_type='ncode', config=None):
        """Initialize the scraper.
        
        Args:
            site_type (str): Type of Syosetu site ('ncode', 'novel18', 'mnlt', 'yomou')
            config (Dict[str, Any], optional): Configuration dictionary
        """
        if site_type not in self.SITES:
            raise ValueError(f"Unknown site type: {site_type}. Available types: {', '.join(self.SITES.keys())}")
        
        # Load configuration or use default
        self.config = config or load_config()
        self.general_config = self.config.get("general", {})
        self.translation_config = self.config.get("translation", {})
            
        self.base_url = self.SITES[site_type]
        self.site_type = site_type
        self.parser = get_parser(site_type, self.translation_config)
        self.delay = self.general_config.get("delay", 1.0)
        
        # Set up session based on site type
        if site_type == 'hameln' and CLOUDSCRAPER_AVAILABLE:
            # Use cloudscraper for Hameln to bypass JavaScript checks
            self.session = cloudscraper.create_scraper(
                browser={
                    'browser': 'firefox',
                    'platform': 'windows',
                    'mobile': False
                }
            )
            # Set cookie
            self.session.cookies.set('over18', 'off', domain='syosetu.org')
        else:
            # Use regular requests for other sites
            self.session = requests.Session()
            self.session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Firefox/139.0',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.7,ja;q=0.3'
            })
            
            # Set cookies for age-restricted sites
            if site_type == 'hameln':
                self.session.cookies.set('over18', 'off', domain='syosetu.org')
                logger.warning("cloudscraper not available. Hameln chapters may not be accessible.")
                logger.warning("Install cloudscraper with: pip install cloudscraper")
    
    def _make_request(self, url: str) -> BeautifulSoup:
        """Make a request and return BeautifulSoup object.
        
        Args:
            url (str): URL to request
            
        Returns:
            BeautifulSoup: Parsed HTML
        """
        logger.debug(f"Requesting: {url}")
        try:
            # For Hameln site, set proper referer
            if self.site_type == 'hameln' and '.html' in url:
                novel_base = url.rsplit('/', 1)[0] + '/'
                self.session.headers.update({'Referer': novel_base})
            
            # Make the request
            response = self.session.get(url)
            response.raise_for_status()
            time.sleep(self.delay)  # Be nice to the server
            return BeautifulSoup(response.content, 'lxml')
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            
            # If Hameln chapter fails and cloudscraper is not available, suggest installation
            if self.site_type == 'hameln' and '.html' in url and not CLOUDSCRAPER_AVAILABLE:
                logger.error("Hameln chapters require cloudscraper to bypass JavaScript checks")
                logger.error("Install cloudscraper with: pip install cloudscraper")
            
            raise
    
    def get_novel_info(self, novel_id: str) -> Dict:
        url_pattern = self.URL_PATTERNS.get(self.site_type, {}).get('novel', '{base_url}/{novel_id}/')
        url = url_pattern.format(base_url=self.base_url, novel_id=novel_id)
        
        soup = self._make_request(url)
        return self.parser.parse_novel_info(soup, url)
    
    def get_chapter_list(self, novel_id: str) -> List[Dict]:
        url_pattern = self.URL_PATTERNS.get(self.site_type, {}).get('novel', '{base_url}/{novel_id}/')
        url = url_pattern.format(base_url=self.base_url, novel_id=novel_id)
        
        soup = self._make_request(url)
        chapters = self.parser.parse_chapter_list(soup, novel_id, self.base_url)
        
        # Format chapter URLs according to site-specific patterns
        chapter_url_pattern = self.URL_PATTERNS.get(self.site_type, {}).get('chapter')
        if chapter_url_pattern:
            for chapter in chapters:
                if 'url' not in chapter or not chapter['url']:
                    chapter_num = chapter.get('chapter_num', str(chapter['index']))
                    chapter['url'] = chapter_url_pattern.format(
                        base_url=self.base_url,
                        novel_id=novel_id,
                        chapter=chapter_num
                    )
        
        return chapters

    def get_chapter_content(self, chapter_url: str, chapter_title: str = None) -> Dict:
        soup = self._make_request(chapter_url)
        return self.parser.parse_chapter_content(soup, chapter_url, chapter_title)


def download_chapters(scraper, novel_id, novel_info, chapters, chapter_input):
    """Download chapters based on user input."""
    from exporter import download_novel
    
    # Parse chapter input
    chapter_range = None
    if chapter_input == "0":
        # Download all chapters
        print(f"Downloading all {len(chapters)} chapters...")
    elif "-" in chapter_input:
        # Download range of chapters
        try:
            start, end = map(int, chapter_input.split("-"))
            if 1 <= start <= len(chapters) and 1 <= end <= len(chapters):
                chapter_range = [start, end]
                print(f"Downloading chapters {start} to {end}...")
            else:
                print(f"Invalid chapter range. Valid range: 1-{len(chapters)}")
                return
        except ValueError:
            print("Invalid chapter range format. Use 'start-end' (e.g., '1-5')")
            return
    else:
        # Download single chapter
        try:
            chapter_num = int(chapter_input)
            if 1 <= chapter_num <= len(chapters):
                chapter_range = [chapter_num, chapter_num]
                print(f"Downloading chapter {chapter_num}...")
            else:
                print(f"Invalid chapter number. Valid range: 1-{len(chapters)}")
                return
        except ValueError:
            print("Invalid chapter number. Please enter a number.")
            return
    
    # Ask if novel info should be included
    include_info = input("Include novel information (title, author, description)? (y/n): ").lower().strip() == 'y'
    
    # Check for Japanese content and suggest EPUB
    has_japanese = False
    if novel_info['title'] and any(ord(c) > 127 for c in novel_info['title']):
        has_japanese = True
    
    # Ask for format with recommendation
    if has_japanese:
        print("\nNote: This novel contains Japanese characters.")
        print("EPUB format is recommended for proper character display.")


    format_type = input("Download as PDF or EPUB? (pdf/epub): ").lower().strip()
    if format_type not in ['pdf', 'epub']:
        print("Invalid format. Using EPUB as default.")
        format_type = 'epub'

    # Download chapters with content
    chapters_to_download = []
    
    # Determine which chapters to download
    if chapter_range:
        start, end = chapter_range
        chapters_to_process = [(i, chapters[i]) for i in range(start-1, end) if i < len(chapters)]
    else:
        chapters_to_process = list(enumerate(chapters))
    
    # Use Rich progress bar if available
    if RICH_AVAILABLE:
        # Create a single console instance for the entire function
        console = Console()
        
        # Track time for ETA calculation
        start_time = time.time()
        completed_chapters = 0
        avg_time_per_chapter = 0
        chapter_times = []  # Store individual chapter times for analysis
        
        with Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TextColumn("[cyan]{task.fields[eta]}"),
            console=console
        ) as progress:
            download_task = progress.add_task(
                "[green]Downloading chapters", 
                total=len(chapters_to_process),
                eta="Calculating...",
                start_time=time.time()  # Store start time in task fields
            )
            
            for i, chapter in chapters_to_process:
                chapter_start_time = time.time()
                
                # Truncate long titles for display
                display_title = chapter['title'][:30] + "..." if len(chapter['title']) > 30 else chapter['title']
                progress.update(
                    download_task, 
                    description=f"[green]Chapter {i+1}/{len(chapters_to_process)}: {display_title}"
                )
                
                # Download chapter content
                chapter_content = scraper.get_chapter_content(chapter['url'], chapter['title'])
                
                # Create a new chapter object to avoid modifying the original
                chapter_copy = chapter.copy()
                chapter_copy['content'] = chapter_content['content']
                chapter_copy['title'] = chapter_content['title']
                chapters_to_download.append(chapter_copy)
                
                # Calculate time taken for this chapter
                chapter_time = time.time() - chapter_start_time
                completed_chapters += 1
                chapter_times.append(chapter_time)
                
                # Update running average with more weight to recent chapters
                if completed_chapters == 1:
                    avg_time_per_chapter = chapter_time
                else:
                    # Use weighted average (70% previous average, 30% new data)
                    avg_time_per_chapter = (avg_time_per_chapter * 0.7) + (chapter_time * 0.3)
                    
                    # If we have enough data, use median of last 5 chapters for more stability
                    if len(chapter_times) >= 5:
                        recent_times = sorted(chapter_times[-5:])
                        median_time = recent_times[len(recent_times) // 2]
                        # Blend median with weighted average for better stability
                        avg_time_per_chapter = (avg_time_per_chapter * 0.6) + (median_time * 0.4)
                
                # Calculate ETA based on refined average
                chapters_remaining = len(chapters_to_process) - completed_chapters
                eta_seconds = avg_time_per_chapter * chapters_remaining
                
                # Calculate elapsed time
                elapsed = time.time() - start_time
                elapsed_hours, elapsed_remainder = divmod(elapsed, 3600)
                elapsed_minutes, elapsed_seconds = divmod(elapsed_remainder, 60)
                
                # Format ETA in HH:MM:SS format for better readability
                hours, remainder = divmod(eta_seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                
                # Format strings based on duration
                if hours > 0:
                    eta_str = f"ETA: {int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
                else:
                    eta_str = f"ETA: {int(minutes):02d}:{int(seconds):02d}"
                
                # Add elapsed time
                if elapsed_hours > 0:
                    eta_str += f" | Elapsed: {int(elapsed_hours):02d}:{int(elapsed_minutes):02d}:{int(elapsed_seconds):02d}"
                else:
                    eta_str += f" | Elapsed: {int(elapsed_minutes):02d}:{int(elapsed_seconds):02d}"
                
                # Add average time per chapter to display
                avg_time_min = int(avg_time_per_chapter // 60)
                avg_time_sec = int(avg_time_per_chapter % 60)
                if avg_time_min > 0:
                    eta_str += f" | {avg_time_min}m {avg_time_sec}s/ch"
                else:
                    eta_str += f" | {avg_time_sec}s/ch"
                
                # Update progress with ETA
                progress.update(download_task, advance=1, eta=eta_str)
    else:
        # Fallback to standard output if Rich is not available
        for i, chapter in chapters_to_process:
            print(f"Fetching chapter {i+1}/{len(chapters_to_process)}: {chapter['title']}...")
            chapter_content = scraper.get_chapter_content(chapter['url'], chapter['title'])
            
            # Create a new chapter object to avoid modifying the original
            chapter_copy = chapter.copy()
            chapter_copy['content'] = chapter_content['content']
            chapter_copy['title'] = chapter_content['title']
            chapters_to_download.append(chapter_copy)
    
    # Download novel
    try:
        # Make sure novel_info is also translated if translation is enabled
        if scraper.translation_config.get("enabled", False):
            if RICH_AVAILABLE:
                # Reuse the console object if it exists in the current scope
                if 'console' not in locals():
                    console = Console()
                console.print("[yellow]Applying translations to novel information...[/yellow]")
            else:
                print("Applying translations to novel information...")
                
            # Create a copy to avoid modifying the original
            translated_novel_info = novel_info.copy()
            
            # Translate title and description if needed
            if scraper.translation_config.get("translate_title", True):
                translated_novel_info['title'] = scraper.parser.translate_text(novel_info['title'])
            
            if scraper.translation_config.get("translate_content", True):
                translated_novel_info['description'] = scraper.parser.translate_text(novel_info['description'])
                
            # Use translated novel info for download
            novel_info_for_download = translated_novel_info
        else:
            novel_info_for_download = novel_info
            
        if RICH_AVAILABLE:
            # Reuse the console object if it exists in the current scope
            if 'console' not in locals():
                console = Console()
            with console.status("[bold green]Creating output file...", spinner="dots"):
                filepath = download_novel(
                    novel_info_for_download, 
                    chapters_to_download, 
                    format_type=format_type,
                    include_novel_info=include_info,
                    chapter_range=chapter_range
                )
            console.print(f"[bold green]Novel downloaded successfully:[/bold green] {filepath}")
        else:
            print("Creating output file...")
            filepath = download_novel(
                novel_info_for_download, 
                chapters_to_download, 
                format_type=format_type,
                include_novel_info=include_info,
                chapter_range=chapter_range
            )
            print(f"Novel downloaded successfully: {filepath}")
    except Exception as e:
        if RICH_AVAILABLE:
            # Reuse the console object if it exists in the current scope
            if 'console' not in locals():
                console = Console()
            console.print(f"[bold red]Error downloading novel:[/bold red] {e}")
        else:
            print(f"Error downloading novel: {e}")
        # Log the full error details in debug mode
        logger.debug(f"Error details: {e}", exc_info=True)


def interactive_mode(config):
    """Run the scraper in interactive mode."""
    print("Syosetu Novel Scraper")
    print("=====================")
    
    # Get site type
    print("\nAvailable Syosetu sites:")
    for i, site in enumerate(SyosetuScraper.SITES.keys(), 1):
        print(f"{i}. {site} ({SyosetuScraper.SITES[site]})")
    
    site_choice = input("\nSelect site type (default is 1 for ncode): ").strip() or "1"
    try:
        site_index = int(site_choice) - 1
        site_types = list(SyosetuScraper.SITES.keys())
        site_type = site_types[site_index]
    except (ValueError, IndexError):
        print("Invalid choice, using 'ncode' as default.")
        site_type = 'ncode'
    
    # Show translation status
    translation_config = config.get("translation", {})
    translation_enabled = translation_config.get("enabled", False)
    translation_service = translation_config.get("service", "none")
    target_language = translation_config.get("target_language", "en")
    
    print(f"\nTranslation: {'Enabled' if translation_enabled else 'Disabled'}")
    if translation_enabled:
        print(f"Translation service: {translation_service}")
        print(f"Target language: {target_language}")
    
    # Check if cloudscraper is needed but not available
    if site_type == 'hameln' and not CLOUDSCRAPER_AVAILABLE:
        print("\nWARNING: Hameln site requires cloudscraper for chapter access.")
        print("Install it with: pip install cloudscraper")
        install_choice = input("Install cloudscraper now? (y/n): ").lower().strip()
        if install_choice == 'y':
            try:
                print("Installing cloudscraper...")
                subprocess.check_call([sys.executable, "-m", "pip", "install", "cloudscraper"])
                print("cloudscraper installed successfully!")
                # Reload the module
                import cloudscraper
                globals()['CLOUDSCRAPER_AVAILABLE'] = True
                globals()['cloudscraper'] = cloudscraper
            except Exception as e:
                print(f"Failed to install cloudscraper: {e}")
                print("Please install manually with: pip install cloudscraper")
    
    scraper = SyosetuScraper(site_type=site_type, config=config)
    
    # Get novel ID
    novel_id = input("\nEnter the Syosetu novel ID (e.g., n9669bk): ").strip()
    
    try:
        # Get novel info
        print("\nFetching novel information...")
        novel_info = scraper.get_novel_info(novel_id)
        
        # Try to get terminal width, default to 100 if not available
        try:
            import shutil
            terminal_width = shutil.get_terminal_size().columns
            width = min(terminal_width, 100)  # Cap at 100 to avoid too wide displays
        except:
            width = 100
            
        border = "=" * width
        separator = f"|{'-' * (width - 2)}|"
        
        # Print novel info in a formatted box
        print(f"\n{border}")
        
        # Center the title with padding - handle long titles with wrapping
        title = novel_info['title']
        if len(title) > width - 10:
            # Split title into multiple lines
            words = title.split()
            title_lines = []
            current_line = ""
            
            for word in words:
                if len(current_line + " " + word) > width - 10:
                    if current_line:
                        title_lines.append(current_line)
                    current_line = word
                else:
                    current_line = (current_line + " " + word).strip()
            
            if current_line:
                title_lines.append(current_line)
                
            # Print each title line centered
            for line in title_lines:
                title_padding_left = (width - len(line) - 2) // 2
                title_padding_right = width - len(line) - 2 - title_padding_left
                print(f"|{' ' * title_padding_left}{line}{' ' * title_padding_right}|")
        
        # Author line
        author = f"By : {novel_info['author']}"
        author_padding_left = (width - len(author) - 2) // 2
        author_padding_right = width - len(author) - 2 - author_padding_left
        print(f"|{' ' * author_padding_left}{author}{' ' * author_padding_right}|")
        
        # Main separator
        print(separator)
        
        # Fixed column width for labels
        label_width = 15
        content_width = width - label_width - 4  # 5 for "| " + " | " + "|"
        
        # URL with label in fixed column
        url = novel_info['url']
        print(f"| Url{' ' * (label_width - 4)}| {url}{' ' * max(0, content_width - len(url))}|")
        
        # Separator between sections
        print(separator)
        
        # Metadata/Tags
        if novel_info['metadata']:
            tags = []
            for key, value in novel_info['metadata'].items():
                if isinstance(value, list):
                    tags.extend(value)
                elif key.lower() in ('keywords', 'tags', 'genre'):
                    tags.append(str(value))
            
            if tags:
                tags_str = ", ".join(tags)
                # Handle long tag lists with wrapping
                if len(tags_str) > content_width:
                    # Split tags into multiple lines
                    current_line = ""
                    tag_lines = []
                    
                    for tag in tags_str.split(", "):
                        if len(current_line + ", " + tag) > content_width:
                            tag_lines.append(current_line)
                            current_line = tag
                        else:
                            if current_line:
                                current_line += ", " + tag
                            else:
                                current_line = tag
                    
                    if current_line:
                        tag_lines.append(current_line)
                    
                    # Print first line with label
                    print(f"| Tags{' ' * (label_width - 5)}| {tag_lines[0]},{' ' * max(0, content_width - len(tag_lines[0]) - 1)}|")
                    
                    # Print remaining lines with proper alignment
                    for line in tag_lines[1:]:
                        print(f"| {' ' * (label_width - 1)}| {line}{' ' * max(0, content_width - (len(line) ))}|")
                else:
                    print(f"| Tags{' ' * (label_width - 5)}| {tags_str}{' ' * max(0, content_width - len(tags_str))}|")
                
                # Separator after tags
                print(separator)
        
        # Description with word wrapping
        desc_words = novel_info['description'].split()
        desc_lines = []
        current_line = ""
        
        for word in desc_words:
            if len(current_line + " " + word) > content_width:
                desc_lines.append(current_line)
                current_line = word
            else:
                current_line = (current_line + " " + word).strip()
        
        if current_line:
            desc_lines.append(current_line)
        
        # Print description lines
        if desc_lines:
            # First line with label
            print(f"| Description{' ' * (label_width - 12)}| {desc_lines[0]}{' ' * max(0, content_width - len(desc_lines[0]))}|")
            
            # Remaining lines with proper alignment
            for line in desc_lines[1:]:
                print(f"| {' ' * (label_width - 1)}| {line}{' ' * max(0, content_width - len(line))}|")
            
            # Separator after description
            print(separator)
        
        # Get chapter list - don't print a separate message
        chapters = scraper.get_chapter_list(novel_id)
        
        content_width = content_width

        if chapters:
            # Chapter list with proper formatting
            # print(f"| Chapter List{' ' * (label_width - 13)}| {' ' * (content_width)}|")
            
            # Show chapters in the box format
            max_display = 10  # Show up to 10 chapters
            first_chapter = True
            for i, chapter in enumerate(chapters[:max_display]):
                chapter_title = f"{chapter['index']}. {chapter['title']}"
                
                # Handle long chapter titles with wrapping
                if len(chapter_title) > content_width:
                    # Split chapter title into multiple lines
                    words = chapter_title.split()
                    ch_lines = []
                    current_line = ""
                    
                    for word in words:
                        if len(current_line + " " + word) > content_width:
                            ch_lines.append(current_line)
                            current_line = word
                        else:
                            current_line = (current_line + " " + word).strip()
                    
                    if current_line:
                        ch_lines.append(current_line)
                    
                    # Print first line with proper padding
                    # print(f"| {' ' * (label_width - 1)}| {ch_lines[0]}{' ' * max(0, content_width - len(ch_lines[0]))}|")
                    print(f"| Chapter List{' ' * (label_width - 13)}| {ch_lines[0]}{' ' * max(0, content_width - len(ch_lines[0]))}|")

                    # Print remaining lines if any with proper alignment
                    for line in ch_lines[1:]:
                        print(f"| {' ' * (label_width - 1)}| {line}{' ' * max(0, content_width - len(line))}|")
                else:
                    if first_chapter:
                        print(f"| Chapter List{' ' * (label_width - 13)}| {chapter_title}{' ' * max(0, content_width - len(chapter_title))}|")
                        first_chapter = False
                    else:
                        print(f"| {' ' * (label_width - 1)}| {chapter_title}{' ' * max(0, content_width - len(chapter_title))}|")
            
            if len(chapters) > max_display:
                more_text = f"... and {len(chapters) - max_display} more chapters"
                print(f"| {' ' * (label_width - 1)}| {more_text}{' ' * max(0, content_width - len(more_text))}|")
            
            # Close the box
            print(border)
            
            # Ask if user wants to download chapters
            download_choice = input("\nDo you want to download chapters? (y/n): ").lower().strip()
            if download_choice == 'y':
                chapter_input = input("Enter chapter number to download (0 for all, range like 1-5 for multiple): ").strip()
                download_chapters(scraper, novel_id, novel_info, chapters, chapter_input)
            else:
                # Ask if user wants to view a chapter
                view_choice = input("\nDo you want to view a chapter? (y/n): ").lower().strip()
                if view_choice == 'y':
                    chapter_num = input("Enter chapter number to view: ").strip()
                    try:
                        chapter_idx = int(chapter_num) - 1
                        if 0 <= chapter_idx < len(chapters):
                            print(f"\nDownloading chapter: {chapters[chapter_idx]['title']}")
                            chapter_content = scraper.get_chapter_content(chapters[chapter_idx]['url'], chapters[chapter_idx]['title'])
                            
                            print(f"\n{chapter_content['title']}")
                            print("=" * len(chapter_content['title']))
                            print(chapter_content['content'])
                        else:
                            print("Invalid chapter number.")
                    except ValueError:
                        print("Invalid input. Please enter a number.")
        else:
            print("No chapters found.")
            
    except Exception as e:
        logger.error(f"Error: {e}")
        print(f"An error occurred: {e}")
        # Log the full error details in debug mode
        logger.debug(f"Error details: {e}", exc_info=True)


def main():
    """Main entry point for the application."""
    # Set up command line arguments
    parser = setup_cli_args()
    
    # Add application-specific arguments
    parser.add_argument("--interactive", action="store_true", help="Run in interactive mode")
    parser.add_argument("--site", choices=list(SyosetuScraper.SITES.keys()), help="Site type to scrape")
    parser.add_argument("--novel-id", help="Novel ID to scrape")
    parser.add_argument("--chapter", help="Chapter number to download (0 for all, or range like 1-5)")
    parser.add_argument("--download", choices=["pdf", "epub"], help="Download novel in specified format")
    parser.add_argument("--include-info", action="store_true", help="Include novel info in download")
    parser.add_argument("--install-deps", action="store_true", help="Install required dependencies")
    parser.add_argument("--no-rich", action="store_true", help="Disable Rich progress display")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    
    # Parse arguments
    args = parser.parse_args()
    
    # Install dependencies if requested
    if args.install_deps:
        print("Installing required dependencies...")
        try:
            # Include rich in the dependencies
            subprocess.check_call([sys.executable, "-m", "pip", "install", "cloudscraper", "ebooklib", "fpdf2", "rich"])
            print("Dependencies installed successfully!")
            # Reload modules
            importlib.reload(sys.modules[__name__])
            # Try to import rich again
            try:
                from rich.progress import Progress, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn
                from rich.console import Console
                globals()["RICH_AVAILABLE"] = True
            except ImportError:
                pass
        except Exception as e:
            print(f"Failed to install dependencies: {e}")
    
    # Process configuration arguments
    config = process_cli_args(args)
    
    # Override Rich availability if --no-rich is specified
    if args.no_rich:
        globals()["RICH_AVAILABLE"] = False
        
    # Enable debug logging if requested
    if args.debug:
        logger.setLevel(logging.DEBUG)
        # Add a handler for stdout
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        logger.debug("Debug logging enabled")
    
    # If no action arguments provided, default to interactive mode
    if not (args.show_config or args.reset_config or args.novel_id):
        args.interactive = True
    
    # Run in interactive mode if requested
    if args.interactive:
        interactive_mode(config)
        return
    
    # If novel ID is provided, scrape it
    if args.novel_id:
        site_type = args.site or 'ncode'
        scraper = SyosetuScraper(site_type=site_type, config=config)
        
        try:
            # Get novel info
            print(f"Fetching novel information for {args.novel_id}...")
            novel_info = scraper.get_novel_info(args.novel_id)
            
            # Try to get terminal width, default to 100 if not available
            try:
                import shutil
                terminal_width = shutil.get_terminal_size().columns
                width = min(terminal_width, 100)  # Cap at 100 to avoid too wide displays
            except:
                width = 100
                
            border = "=" * width
            separator = f"|{'-' * (width - 2)}|"
            label_width = 15
            content_width = width - label_width - 5  # 5 for "| " + " | " + "|"
            
            # Print novel info in a formatted box
            print(f"\n{border}")
            
            # Center the title with padding - handle long titles with wrapping
            title = novel_info['title']
            if len(title) > width - 10:
                # Split title into multiple lines
                words = title.split()
                title_lines = []
                current_line = ""
                
                for word in words:
                    if len(current_line + " " + word) > width - 10:
                        if current_line:
                            title_lines.append(current_line)
                        current_line = word
                    else:
                        current_line = (current_line + " " + word).strip()
                
                if current_line:
                    title_lines.append(current_line)
                    
                # Print each title line centered
                for line in title_lines:
                    title_padding_left = (width - len(line) - 2) // 2
                    title_padding_right = width - len(line) - 2 - title_padding_left
                    print(f"|{' ' * title_padding_left}{line}{' ' * title_padding_right}|")
            else:
                # Single line title
                title_padding_left = (width - len(title) - 2) // 2
                title_padding_right = width - len(title) - 2 - title_padding_left
                print(f"|{' ' * title_padding_left}{title}{' ' * title_padding_right}|")
            
            # Author line
            author = f"By : {novel_info['author']}"
            author_padding_left = (width - len(author) - 2) // 2
            author_padding_right = width - len(author) - 2 - author_padding_left
            print(f"|{' ' * author_padding_left}{author}{' ' * author_padding_right}|")
            
            # Main separator
            print(separator)
            
            # URL with label in fixed column
            url = novel_info['url']
            print(f"| Url{' ' * (label_width - 3)}| {url}{' ' * max(0, content_width - len(url))}|")
            
            # Get chapter list
            chapters = scraper.get_chapter_list(args.novel_id)
            
            # Chapter count with separator
            print(separator)
            chapter_count = f"{len(chapters)}"
            print(f"| Chapters{' ' * (label_width - 8)}| {chapter_count}{' ' * max(0, content_width - len(chapter_count))}|")
            
            # Chapter list preview
            if chapters:
                print(separator)
                print(f"| Chapter List{' ' * (label_width - 12)}| {' ' * (content_width - 1)}|")
                
                # Show a few chapters as preview
                max_preview = 5
                for i, chapter in enumerate(chapters[:max_preview]):
                    chapter_title = f"{chapter['index']}. {chapter['title']}"
                    
                    # Handle long chapter titles with wrapping
                    if len(chapter_title) > content_width:
                        # Split chapter title into multiple lines
                        words = chapter_title.split()
                        ch_lines = []
                        current_line = ""
                        
                        for word in words:
                            if len(current_line + " " + word) > content_width:
                                ch_lines.append(current_line)
                                current_line = word
                            else:
                                current_line = (current_line + " " + word).strip()
                        
                        if current_line:
                            ch_lines.append(current_line)
                        
                        # Print first line with proper padding
                        print(f"| {' ' * (label_width - 1)}| {ch_lines[0]}{' ' * max(0, content_width - len(ch_lines[0]))}|")
                        
                        # Print remaining lines if any with proper alignment
                        for line in ch_lines[1:]:
                            print(f"| {' ' * (label_width - 1)}| {line}{' ' * max(0, content_width - len(line))}|")
                    else:
                        print(f"| {' ' * (label_width - 1)}| {chapter_title}{' ' * max(0, content_width - len(chapter_title))}|")
                
                if len(chapters) > max_preview:
                    more_text = f"... and {len(chapters) - max_preview} more chapters"
                    print(f"| {' ' * (label_width - 1)}| {more_text}{' ' * max(0, content_width - len(more_text))}|")
            
            # Close the box
            print(border)
            
            # Download novel if requested
            if args.download:
                if args.chapter:
                    download_chapters(scraper, args.novel_id, novel_info, chapters, args.chapter)
                else:
                    # Download all chapters
                    download_chapters(scraper, args.novel_id, novel_info, chapters, "0")
            # Display specific chapter if requested
            elif args.chapter and args.chapter.isdigit():
                chapter_idx = int(args.chapter) - 1
                if 0 <= chapter_idx < len(chapters):
                    print(f"Downloading chapter {args.chapter}: {chapters[chapter_idx]['title']}")
                    chapter_content = scraper.get_chapter_content(chapters[chapter_idx]['url'], chapters[chapter_idx]['title'])
                    
                    print(f"\n{chapter_content['title']}")
                    print("=" * len(chapter_content['title']))
                    print(chapter_content['content'])
                else:
                    print(f"Error: Chapter {args.chapter} not found. Valid range: 1-{len(chapters)}")
            
        except Exception as e:
            logger.error(f"Error: {e}")
            print(f"An error occurred: {e}")
            # Log the full error details in debug mode
            logger.debug(f"Error details: {e}", exc_info=True)


if __name__ == "__main__":
    main()