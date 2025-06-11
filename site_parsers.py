#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
from bs4 import BeautifulSoup
from typing import Dict, List, Optional, Any
import re
from translator import BaseTranslator, get_translator


class BaseSiteParser:
    """Base parser class for Syosetu sites."""
    
    def __init__(self):
        """Initialize the parser."""
        self.translator = None
        self.translation_config = {
            "enabled": False,
            "target_language": "en",
            "translate_title": True,
            "translate_content": True
        }
    
    def configure_translator(self, translation_config: Dict[str, Any]):
        """Configure the translator based on configuration.
        
        Args:
            translation_config (Dict[str, Any]): Translation configuration
        """
        self.translation_config = translation_config
        if translation_config.get("enabled", False):
            service = translation_config.get("service", "google")
            api_key = translation_config.get("api_key", "")
            target_language = translation_config.get("target_language", "en")
            concurrent_requests = translation_config.get("concurrent_requests", 3)
            request_delay = translation_config.get("request_delay", 0.1)
            max_retries = translation_config.get("max_retries", 3)
            self.translator = get_translator(
                service, 
                api_key, 
                target_language, 
                concurrent_requests, 
                request_delay,
                max_retries
            )
        else:
            self.translator = None
    
    def translate_text(self, text: str) -> str:
        """Translate text if translation is enabled.
        
        Args:
            text (str): Text to translate
            
        Returns:
            str: Translated text or original text
        """
        if not self.translator or not self.translation_config.get("enabled", False) or not text:
            return text
        
        try:
            # Replace newlines with a special marker before translation
            text_for_translation = text.replace('\n\n', ' PARAGRAPH_BREAK ')
            
            target_lang = self.translation_config.get("target_language", "en")
            translated_text = self.translator.translate_text(text_for_translation, target_lang)
            
            # Restore newlines after translation
            return translated_text.replace(' PARAGRAPH_BREAK ', '\n\n')
        except Exception as e:
            print(f"Translation error: {e}")
            return text
    
    def batch_translate(self, texts: List[str]) -> List[str]:
        """Batch translate multiple texts if translation is enabled.
        
        Args:
            texts (List[str]): List of texts to translate
            
        Returns:
            List[str]: List of translated texts or original texts
        """
        if not self.translator or not self.translation_config.get("enabled", False) or not texts:
            return texts
        
        try:
            # Replace newlines with a special marker before translation
            texts_for_translation = [text.replace('\n\n', ' PARAGRAPH_BREAK ') for text in texts]
            
            target_lang = self.translation_config.get("target_language", "en")
            translated_texts = self.translator.batch_translate(texts_for_translation, target_lang)
            
            # Restore newlines after translation
            return [text.replace(' PARAGRAPH_BREAK ', '\n\n') for text in translated_texts]
        except Exception as e:
            print(f"Translation error: {e}")
            return texts
    
    def parse_novel_info(self, soup: BeautifulSoup, url: str) -> Dict:
        """Parse novel information from soup.
        
        Args:
            soup (BeautifulSoup): Parsed HTML
            url (str): Novel URL
            
        Returns:
            dict: Novel information
        """
        raise NotImplementedError("Subclasses must implement this method")
    
    def parse_chapter_list(self, soup: BeautifulSoup, novel_id: str, base_url: str) -> List[Dict]:
        """Parse chapter list from soup.
        
        Args:
            soup (BeautifulSoup): Parsed HTML
            novel_id (str): Novel ID
            base_url (str): Base URL of the site
            
        Returns:
            list: List of chapter information
        """
        raise NotImplementedError("Subclasses must implement this method")
    
    def parse_chapter_content(self, soup: BeautifulSoup, url: str) -> Dict:
        """Parse chapter content from soup.
        
        Args:
            soup (BeautifulSoup): Parsed HTML
            url (str): Chapter URL
            
        Returns:
            dict: Chapter content and metadata
        """
        raise NotImplementedError("Subclasses must implement this method")


class NcodeParser(BaseSiteParser):
    """Parser for ncode.syosetu.com."""
    
    def parse_novel_info(self, soup: BeautifulSoup, url: str) -> Dict:
        # Extract novel title
        title_elem = soup.select_one('.novel_title')
        title = title_elem.text.strip() if title_elem else "Unknown Title"
        
        # Extract author
        author_elem = soup.select_one('.novel_writername')
        author = author_elem.text.strip().replace('作者：', '') if author_elem else "Unknown Author"
        
        # Extract description
        desc_elem = soup.select_one('#novel_ex')
        description = desc_elem.text.strip() if desc_elem else "No description available"
        
        # Extract metadata
        metadata = {}
        
        # Genre
        genre_elem = soup.select_one('.novel_genre')
        if genre_elem:
            metadata['genre'] = genre_elem.text.strip()
        
        # Keywords
        keyword_elems = soup.select('.keyword a')
        if keyword_elems:
            metadata['keywords'] = [k.text.strip() for k in keyword_elems]
        
        # Apply translation if enabled
        if self.translation_config.get("enabled", False):
            # Batch translate all text elements
            to_translate = [title, author, description]
            if 'genre' in metadata:
                to_translate.append(metadata['genre'])
            
            keywords = metadata.get('keywords', [])
            to_translate.extend(keywords)
            
            translated = self.batch_translate(to_translate)
            
            # Assign translated values
            title = translated[0]
            author = translated[1]
            description = translated[2]
            
            idx = 3
            if 'genre' in metadata:
                metadata['genre'] = translated[idx]
                idx += 1
            
            if keywords:
                metadata['keywords'] = translated[idx:idx+len(keywords)]
        
        return {
            'title': title,
            'author': author,
            'description': description,
            'url': url,
            'metadata': metadata
        }
    
    def parse_chapter_list(self, soup: BeautifulSoup, novel_id: str, base_url: str) -> List[Dict]:
        chapters = []
        chapter_elems = soup.select('.novel_sublist2')
        chapter_titles = []
        
        for index, chapter in enumerate(chapter_elems, 1):
            link = chapter.select_one('a')
            if link:
                title = link.text.strip()
                chapter_titles.append(title)
                href = link.get('href')
                # Extract chapter number from href if possible
                chapter_num = href.split('/')[-1] if href else str(index)
                
                chapters.append({
                    'index': index,
                    'title': title,  # Will be replaced with translated title
                    'chapter_num': chapter_num,
                    'url': f"{base_url}{href}" if href and href.startswith('/') else None
                })
        
        # Translate all chapter titles at once if enabled
        if self.translation_config.get("enabled", False) and chapter_titles:
            translated_titles = self.batch_translate(chapter_titles)
            for i, translated_title in enumerate(translated_titles):
                if i < len(chapters):
                    chapters[i]['title'] = translated_title
        
        return chapters
    
    def parse_chapter_content(self, soup: BeautifulSoup, url: str) -> Dict:
        # Extract chapter title
        title_elem = soup.select_one('.novel_subtitle')
        title = title_elem.text.strip() if title_elem else "Unknown Chapter"
        
        # Extract chapter content
        content_elem = soup.select_one('#novel_honbun')
        content = ""
        chunks = []
        
        if content_elem:
            paragraphs = [p.text.strip() for p in content_elem.find_all('p') if p.text.strip()]
            if not paragraphs:  # If no <p> tags, get the text directly
                paragraphs = [line.strip() for line in content_elem.text.split('\n') if line.strip()]
            
            # Create chunks of approximately 1000 characters
            current_chunk = []
            current_length = 0
            chunk_limit = 1000
            
            for paragraph in paragraphs:
                # If adding this paragraph would exceed the limit, save the current chunk
                if current_length + len(paragraph) + 2 > chunk_limit and current_chunk:  # +2 for '\n\n'
                    chunks.append('\n\n'.join(current_chunk))
                    current_chunk = []
                    current_length = 0
                
                # Add paragraph to current chunk
                current_chunk.append(paragraph)
                current_length += len(paragraph) + 2  # +2 for '\n\n'
            
            # Add the last chunk if it's not empty
            if current_chunk:
                chunks.append('\n\n'.join(current_chunk))
            
            # Join all paragraphs for the full content
            content = '\n\n'.join(paragraphs)
        
        # Apply translation if enabled
        if self.translation_config.get("enabled", False):
            # Always try to translate the title
            try:
                title = self.translate_text(title)
            except Exception as e:
                print(f"Title translation error: {e}")
                # Keep original title if translation fails
            
            # Try to translate content chunks if available
            if chunks and self.translation_config.get("translate_content", True):
                try:
                    # Translate each chunk separately
                    translated_chunks = []
                    for chunk in chunks:
                        try:
                            chunk_translated = self.translate_text(chunk)
                            translated_chunks.append(chunk_translated)
                        except Exception as e:
                            print(f"Chunk translation error: {e}")
                            translated_chunks.append(chunk)  # Keep original chunk if translation fails
                    
                    chunks = translated_chunks
                    # Combine translated chunks for full content
                    content = '\n\n'.join(chunks)
                except Exception as e:
                    print(f"Content translation error: {e}")
                    # Keep original content if translation fails
        
        return {
            'title': title,
            'url': url,
            'content': content or "No content available",
            'chunks': chunks or ["No content available"]
        }


class Novel18Parser(BaseSiteParser):
    """Parser for novel18.syosetu.com."""
    
    def parse_novel_info(self, soup: BeautifulSoup, url: str) -> Dict:
        # Extract novel title
        title_elem = soup.select_one('.novel_title')
        title = title_elem.text.strip() if title_elem else "Unknown Title"
        
        # Extract author
        author_elem = soup.select_one('.novel_writername')
        author = author_elem.text.strip().replace('作者：', '') if author_elem else "Unknown Author"
        
        # Extract description
        desc_elem = soup.select_one('#novel_ex')
        description = desc_elem.text.strip() if desc_elem else "No description available"
        
        # Extract metadata
        metadata = {}
        
        # Age verification notice
        age_elem = soup.select_one('.contents1')
        if age_elem and "18禁" in age_elem.text:
            metadata['age_restricted'] = True
        
        # Keywords
        keyword_elems = soup.select('.keyword a')
        if keyword_elems:
            metadata['keywords'] = [k.text.strip() for k in keyword_elems]
        
        # Apply translation if enabled
        if self.translation_config.get("enabled", False):
            # Batch translate all text elements
            to_translate = [title, author, description]
            
            keywords = metadata.get('keywords', [])
            to_translate.extend(keywords)
            
            translated = self.batch_translate(to_translate)
            
            # Assign translated values
            title = translated[0]
            author = translated[1]
            description = translated[2]
            
            if keywords:
                metadata['keywords'] = translated[3:3+len(keywords)]
        
        return {
            'title': title,
            'author': author,
            'description': description,
            'url': url,
            'metadata': metadata
        }
    
    def parse_chapter_list(self, soup: BeautifulSoup, novel_id: str, base_url: str) -> List[Dict]:
        chapters = []
        chapter_elems = soup.select('.novel_sublist2')
        chapter_titles = []
        
        for index, chapter in enumerate(chapter_elems, 1):
            link = chapter.select_one('a')
            if link:
                title = link.text.strip()
                chapter_titles.append(title)
                href = link.get('href')
                # Extract chapter number from href if possible
                chapter_num = href.split('/')[-1] if href else str(index)
                
                chapters.append({
                    'index': index,
                    'title': title,  # Will be replaced with translated title
                    'chapter_num': chapter_num,
                    'url': f"{base_url}{href}" if href and href.startswith('/') else None
                })
        
        # Translate all chapter titles at once if enabled
        if self.translation_config.get("enabled", False) and chapter_titles:
            translated_titles = self.batch_translate(chapter_titles)
            for i, translated_title in enumerate(translated_titles):
                if i < len(chapters):
                    chapters[i]['title'] = translated_title
        
        return chapters
    
    def parse_chapter_content(self, soup: BeautifulSoup, url: str) -> Dict:
        # Similar to NcodeParser but might have different elements
        title_elem = soup.select_one('.novel_subtitle')
        title = title_elem.text.strip() if title_elem else "Unknown Chapter"
        
        content_elem = soup.select_one('#novel_honbun')
        content = ""
        chunks = []
        
        if content_elem:
            paragraphs = [p.text.strip() for p in content_elem.find_all('p') if p.text.strip()]
            if not paragraphs:
                paragraphs = [line.strip() for line in content_elem.text.split('\n') if line.strip()]
            
            # Create chunks of approximately 1000 characters
            current_chunk = []
            current_length = 0
            chunk_limit = 1000
            
            for paragraph in paragraphs:
                # If adding this paragraph would exceed the limit, save the current chunk
                if current_length + len(paragraph) + 2 > chunk_limit and current_chunk:  # +2 for '\n\n'
                    chunks.append('\n\n'.join(current_chunk))
                    current_chunk = []
                    current_length = 0
                
                # Add paragraph to current chunk
                current_chunk.append(paragraph)
                current_length += len(paragraph) + 2  # +2 for '\n\n'
            
            # Add the last chunk if it's not empty
            if current_chunk:
                chunks.append('\n\n'.join(current_chunk))
            
            # Join all paragraphs for the full content
            content = '\n\n'.join(paragraphs)
        
        # Apply translation if enabled
        if self.translation_config.get("enabled", False):
            # Always try to translate the title
            try:
                title = self.translate_text(title)
            except Exception as e:
                print(f"Title translation error: {e}")
                # Keep original title if translation fails
            
            # Try to translate content chunks if available
            if chunks and self.translation_config.get("translate_content", True):
                try:
                    # Translate each chunk separately
                    translated_chunks = []
                    for chunk in chunks:
                        try:
                            chunk_translated = self.translate_text(chunk)
                            translated_chunks.append(chunk_translated)
                        except Exception as e:
                            print(f"Chunk translation error: {e}")
                            translated_chunks.append(chunk)  # Keep original chunk if translation fails
                    
                    chunks = translated_chunks
                    # Combine translated chunks for full content
                    content = '\n\n'.join(chunks)
                except Exception as e:
                    print(f"Content translation error: {e}")
                    # Keep original content if translation fails
        
        return {
            'title': title,
            'url': url,
            'content': content or "No content available",
            'chunks': chunks or ["No content available"]
        }


class MobileParser(BaseSiteParser):
    """Parser for mnlt.syosetu.com (mobile site)."""
    
    def parse_novel_info(self, soup: BeautifulSoup, url: str) -> Dict:
        # Mobile site has different HTML structure
        title_elem = soup.select_one('h1')
        title = title_elem.text.strip() if title_elem else "Unknown Title"
        
        author_elem = soup.select_one('.novel_writername')
        author = author_elem.text.strip().replace('作者：', '') if author_elem else "Unknown Author"
        
        desc_elem = soup.select_one('.novel_introduction')
        description = desc_elem.text.strip() if desc_elem else "No description available"
        
        metadata = {}
        
        # Apply translation if enabled
        if self.translation_config.get("enabled", False):
            # Batch translate all text elements
            translated = self.batch_translate([title, author, description])
            title = translated[0]
            author = translated[1]
            description = translated[2]
        
        return {
            'title': title,
            'author': author,
            'description': description,
            'url': url,
            'metadata': metadata
        }
    
    def parse_chapter_list(self, soup: BeautifulSoup, novel_id: str, base_url: str) -> List[Dict]:
        chapters = []
        chapter_elems = soup.select('.chapter_title')
        chapter_titles = []
        
        for index, chapter in enumerate(chapter_elems, 1):
            link = chapter.select_one('a') or chapter
            if hasattr(link, 'get') and link.get('href'):
                title = link.text.strip()
                chapter_titles.append(title)
                href = link.get('href')
                # Extract chapter number from href if possible
                chapter_num = href.split('/')[-1] if href else str(index)
                
                chapters.append({
                    'index': index,
                    'title': title,  # Will be replaced with translated title
                    'chapter_num': chapter_num,
                    'url': f"{base_url}{href}" if href and href.startswith('/') else None
                })
        
        # Translate all chapter titles at once if enabled
        if self.translation_config.get("enabled", False) and chapter_titles:
            translated_titles = self.batch_translate(chapter_titles)
            for i, translated_title in enumerate(translated_titles):
                if i < len(chapters):
                    chapters[i]['title'] = translated_title
        
        return chapters
    
    def parse_chapter_content(self, soup: BeautifulSoup, url: str) -> Dict:
        title_elem = soup.select_one('h1')
        title = title_elem.text.strip() if title_elem else "Unknown Chapter"
        
        content_elem = soup.select_one('.novel_content')
        content = ""
        chunks = []
        
        if content_elem:
            paragraphs = [p.text.strip() for p in content_elem.find_all('p') if p.text.strip()]
            if not paragraphs:
                paragraphs = [line.strip() for line in content_elem.text.split('\n') if line.strip()]
            
            # Create chunks of approximately 1000 characters
            current_chunk = []
            current_length = 0
            chunk_limit = 1000
            
            for paragraph in paragraphs:
                # If adding this paragraph would exceed the limit, save the current chunk
                if current_length + len(paragraph) + 2 > chunk_limit and current_chunk:  # +2 for '\n\n'
                    chunks.append('\n\n'.join(current_chunk))
                    current_chunk = []
                    current_length = 0
                
                # Add paragraph to current chunk
                current_chunk.append(paragraph)
                current_length += len(paragraph) + 2  # +2 for '\n\n'
            
            # Add the last chunk if it's not empty
            if current_chunk:
                chunks.append('\n\n'.join(current_chunk))
            
            # Join all paragraphs for the full content
            content = '\n\n'.join(paragraphs)
        
        # Apply translation if enabled
        if self.translation_config.get("enabled", False):
            # Always try to translate the title
            try:
                title = self.translate_text(title)
            except Exception as e:
                print(f"Title translation error: {e}")
                # Keep original title if translation fails
            
            # Try to translate content chunks if available
            if chunks and self.translation_config.get("translate_content", True):
                try:
                    # Translate each chunk separately
                    translated_chunks = []
                    for chunk in chunks:
                        try:
                            chunk_translated = self.translate_text(chunk)
                            translated_chunks.append(chunk_translated)
                        except Exception as e:
                            print(f"Chunk translation error: {e}")
                            translated_chunks.append(chunk)  # Keep original chunk if translation fails
                    
                    chunks = translated_chunks
                    # Combine translated chunks for full content
                    content = '\n\n'.join(chunks)
                except Exception as e:
                    print(f"Content translation error: {e}")
                    # Keep original content if translation fails
        
        return {
            'title': title,
            'url': url,
            'content': content or "No content available",
            'chunks': chunks or ["No content available"]
        }


class HamelnParser(BaseSiteParser):
    """Parser for syosetu.org (Hameln)."""
    def parse_novel_info(self, soup: BeautifulSoup, url: str) -> Dict:
        # Extract novel title
        title_elem = soup.select_one('span[itemprop="name"]')        
        title = title_elem.text.strip() if title_elem else "Unknown Title"
        # Extract author
        author_elem = soup.select_one('span[itemprop="author"]')
        author = author_elem.text.strip() if author_elem else "Unknown Author"
        
        # Extract description
        desc_elem = soup.select_one('div#maind .ss:nth-of-type(2)')        
        description = desc_elem.text.strip() if desc_elem else "No description available"
        # Extract metadata
        metadata = {}
        
        # Genre/Tags
        tag_elems = soup.select('span[itemprop="keywords"]')
        if tag_elems:
            metadata['tags'] = [t.text.strip() for t in tag_elems]
        
        # Apply translation if enabled
        if self.translation_config.get("enabled", False):
            # Batch translate all text elements
            to_translate = [title, author, description]
            
            tags = metadata.get('tags', [])
            to_translate.extend(tags)
            
            translated = self.batch_translate(to_translate)
            
            # Assign translated values
            title = translated[0]
            author = translated[1]
            description = translated[2]
            
            if tags:
                metadata['tags'] = translated[3:3+len(tags)]
        
        return {
            'title': title,
            'author': author,
            'description': description,
            'url': url,
            'metadata': metadata
        }
    
    def parse_chapter_list(self, soup: BeautifulSoup, novel_id: str, base_url: str) -> List[Dict]:
        chapters = []
        current_arc = ""
        chapter_titles = []
        arc_titles = []
        
        # Find all story sections within .ss tables
        story_tables = soup.select('div.ss table')
        
        for table in story_tables:
            # Check first row for arc title
            arc_row = table.select_one('tr td strong')
            if arc_row:
                current_arc = arc_row.text.strip()
                arc_titles.append(current_arc)
                continue
                
            # Get chapter rows
            chapter_rows = table.select('tr.bgcolor3, tr.bgcolor2')
            
            for index, row in enumerate(chapter_rows, 1):
                link = row.select_one('a')
                if link:
                    title = link.text.strip()
                    chapter_titles.append(title)
                    href = link.get('href')
                    # Extract chapter number from href if possible
                    match = re.search(r'(\d+)\.html$', href) if href else None
                    chapter_num = match.group(1) if match else str(index)
                    
                    # Get publish date if available
                    date_elem = row.select_one('time')
                    publish_date = date_elem.get('datetime') if date_elem else None
                    
                    chapters.append({
                        'index': index,
                        'title': title,  # Will be replaced with translated title
                        'chapter_num': chapter_num,
                        'url': None,  # Will be formatted by the main class
                        'arc': current_arc,  # Will be replaced with translated arc
                        'publish_date': publish_date
                    })
        
        # Translate all titles at once if enabled
        if self.translation_config.get("enabled", False):
            # Translate arc titles
            if arc_titles:
                translated_arcs = self.batch_translate(arc_titles)
                arc_map = dict(zip(arc_titles, translated_arcs))
                
                # Update arc titles in chapters
                for chapter in chapters:
                    if chapter['arc'] in arc_map:
                        chapter['arc'] = arc_map[chapter['arc']]
            
            # Translate chapter titles
            if chapter_titles:
                translated_titles = self.batch_translate(chapter_titles)
                for i, translated_title in enumerate(translated_titles):
                    if i < len(chapters):
                        chapters[i]['title'] = translated_title
        
        return chapters    
    
    def parse_chapter_content(self, soup: BeautifulSoup, url: str, chapter_title: str = None) -> Dict:
        # Use provided chapter title if available, otherwise extract from page
        if chapter_title:
            title = chapter_title
        else:
            # Try to find title in different possible locations
            title_elem = soup.select_one('p span[style="font-size:120%"] a')
            if not title_elem:
                title_elem = soup.select_one('span[style="font-size:120%"]')
            title = title_elem.text.strip() if title_elem else "Unknown Chapter"
        
        # Extract chapter content
        content_elem = soup.select_one('#novel_content')
        if not content_elem:
            content_elem = soup.select_one('#honbun')
        content = ""
        chunks = []
        
        if content_elem:
            paragraphs = [p.text.strip() for p in content_elem.find_all('p') if p.text.strip()]
            if not paragraphs:  # If no <p> tags, get the text directly
                paragraphs = [line.strip() for line in content_elem.text.split('\n') if line.strip()]
            
            # Create chunks of approximately 1000 characters
            current_chunk = []
            current_length = 0
            chunk_limit = 1000
            
            for paragraph in paragraphs:
                # If adding this paragraph would exceed the limit, save the current chunk
                if current_length + len(paragraph) + 2 > chunk_limit and current_chunk:  # +2 for '\n\n'
                    chunks.append('\n\n'.join(current_chunk))
                    current_chunk = []
                    current_length = 0
                
                # Add paragraph to current chunk
                current_chunk.append(paragraph)
                current_length += len(paragraph) + 2  # +2 for '\n\n'
            
            # Add the last chunk if it's not empty
            if current_chunk:
                chunks.append('\n\n'.join(current_chunk))
            
            # Join all paragraphs for the full content
            content = '\n\n'.join(paragraphs)
        
        # Apply translation if enabled
        if self.translation_config.get("enabled", False):
            # Always try to translate the title
            try:
                title = self.translate_text(title)
            except Exception as e:
                print(f"Title translation error: {e}")
                # Keep original title if translation fails
            
            # Try to translate content chunks if available
            if chunks and self.translation_config.get("translate_content", True):
                try:
                    # Translate each chunk separately
                    translated_chunks = []
                    for chunk in chunks:
                        try:
                            chunk_translated = self.translate_text(chunk)
                            translated_chunks.append(chunk_translated)
                            time.sleep(5) # Wait 5 seconds between chunks
                            # print('chunk translated : ', chunk_translated)

                        except Exception as e:
                            print(f"Chunk translation error: {e}")
                            translated_chunks.append(chunk)  # Keep original chunk if translation fails
                    
                    chunks = translated_chunks
                    # Combine translated chunks for full content
                    content = '\n\n'.join(chunks)
                except Exception as e:
                    print(f"Content translation error: {e}")
                    # Keep original content if translation fails
        
        return {
            'title': title,
            'url': url,
            'content': content or "No content available",
            'chunks': chunks or ["No content available"]
        }


# Factory function to get the appropriate parser
def get_parser(site_type: str, translation_config: Optional[Dict[str, Any]] = None) -> BaseSiteParser:
    """Get the appropriate parser for the site type.
    
    Args:
        site_type (str): Type of Syosetu site
        translation_config (Dict[str, Any], optional): Translation configuration
        
    Returns:
        BaseSiteParser: Parser for the site
    """
    parsers = {
        'ncode': NcodeParser(),
        'novel18': Novel18Parser(),
        'mnlt': MobileParser(),
        'yomou': NcodeParser(),  # Yomou uses similar structure to ncode
        'hameln': HamelnParser(),
    }
    
    parser = parsers.get(site_type, NcodeParser())
    
    # Configure translator if translation config is provided
    if translation_config:
        parser.configure_translator(translation_config)
    
    return parser