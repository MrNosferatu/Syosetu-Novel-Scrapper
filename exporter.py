#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import subprocess
from typing import Dict, List, Optional
import re
import datetime
import urllib.request

# Try to import required libraries, install if not available
try:
    from ebooklib import epub
    EPUB_AVAILABLE = True
except ImportError:
    EPUB_AVAILABLE = False
    print("Installing ebooklib library...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "ebooklib"])
        from ebooklib import epub
        EPUB_AVAILABLE = True
    except Exception as e:
        print(f"Failed to install ebooklib: {e}")
        EPUB_AVAILABLE = False

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    print("Installing reportlab library...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "reportlab"])
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        REPORTLAB_AVAILABLE = True
    except Exception as e:
        print(f"Failed to install reportlab: {e}")
        REPORTLAB_AVAILABLE = False


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to be safe for all operating systems."""
    invalid_chars = r'[<>:"/\\|?*]'
    sanitized = re.sub(invalid_chars, '_', filename)
    return sanitized[:100]


class EpubExporter:
    """Export novel to EPUB format."""
    
    def __init__(self, novel_info: Dict, chapters: List[Dict]):
        self.novel_info = novel_info
        self.chapters = chapters
        self.book = epub.EpubBook()
        
    def create_epub(self, include_novel_info: bool = True, chapter_range: Optional[List[int]] = None) -> epub.EpubBook:
        # Set metadata
        title = self.novel_info['title']
        self.book.set_title(title)
        self.book.set_language('en')
        self.book.add_author(self.novel_info['author'])
        
        chapters_to_include = []
        
        # Add cover page if novel info is included
        if include_novel_info:
            # Create cover page
            cover_content = f"<h1>{title}</h1>"
            cover_content += f"<p><strong>Author:</strong> {self.novel_info['author']}</p>"
            
            # Add metadata
            if self.novel_info['metadata']:
                for key, value in self.novel_info['metadata'].items():
                    if isinstance(value, list):
                        value_str = ", ".join(value)
                        cover_content += f"<p><strong>{key}:</strong> {value_str}</p>"
                    else:
                        cover_content += f"<p><strong>{key}:</strong> {value}</p>"
            
            # Add description
            cover_content += f"<p>{self.novel_info['description']}</p>"
            cover_content += f"<p><strong>URL:</strong> {self.novel_info['url']}</p>"
            
            # Create cover chapter
            cover = epub.EpubHtml(title='Cover', file_name='cover.xhtml')
            cover.content = f"<html><body>{cover_content}</body></html>"
            self.book.add_item(cover)
            chapters_to_include.append(cover)
            
            # Create TOC page
            toc_content = "<h1>Table of Contents</h1><ul>"
            
            # Filter chapters based on range
            filtered_chapters = self.chapters
            if chapter_range:
                start, end = chapter_range
                filtered_chapters = [ch for ch in self.chapters if start <= ch['index'] <= end]
            
            for chapter in filtered_chapters:
                toc_content += f"<li><a href='chapter_{chapter['index']}.xhtml'>{chapter['title']}</a></li>"
            toc_content += "</ul>"
            
            toc = epub.EpubHtml(title='Table of Contents', file_name='toc.xhtml')
            toc.content = f"<html><body>{toc_content}</body></html>"
            self.book.add_item(toc)
            chapters_to_include.append(toc)
        
        # Add chapters
        current_arc = None
        for chapter in self.chapters:
            # Skip if not in range
            if chapter_range and not (chapter_range[0] <= chapter['index'] <= chapter_range[1]):
                continue
                
            # Check if arc changed
            arc_header = ""
            if 'arc' in chapter and chapter['arc'] != current_arc:
                current_arc = chapter['arc']
                if current_arc:
                    arc_header = f"<h2 class='arc-header'>{current_arc}</h2>"
            
            # Create chapter content
            content = f"<h1>{chapter['title']}</h1>"
            if arc_header:
                content = arc_header + content
                
            if 'content' in chapter:
                # Process newlines before adding to f-string
                processed_content = chapter['content'].replace('\n', '<br/>')
                content += f"<div>{processed_content}</div>"
            
            # Create chapter
            c = epub.EpubHtml(title=chapter['title'], file_name=f"chapter_{chapter['index']}.xhtml")
            c.content = f"<html><body>{content}</body></html>"
            self.book.add_item(c)
            chapters_to_include.append(c)
        
        # Define Table of Contents
        self.book.toc = chapters_to_include
        
        # Add default NCX and Nav
        self.book.add_item(epub.EpubNcx())
        self.book.add_item(epub.EpubNav())
        
        # Define CSS
        style = """
        body { font-family: serif; }
        h1 { text-align: center; }
        h2 { text-align: center; }
        .arc-header { page-break-before: always; }
        """
        nav_css = epub.EpubItem(uid="style_nav", file_name="style/nav.css", media_type="text/css", content=style)
        self.book.add_item(nav_css)
        
        # Create spine
        self.book.spine = chapters_to_include
        
        return self.book
    
    def save(self, filename: str, include_novel_info: bool = True, chapter_range: Optional[List[int]] = None) -> str:
        if not EPUB_AVAILABLE:
            raise ImportError("ebooklib is not available. Cannot create EPUB.")
            
        self.create_epub(include_novel_info, chapter_range)
        
        # Ensure filename has .epub extension
        if not filename.lower().endswith('.epub'):
            filename += '.epub'
            
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(os.path.abspath(filename)), exist_ok=True)
        
        # Write EPUB file
        epub.write_epub(filename, self.book)
        return filename


class JapanesePdfExporter:
    """Export novel to PDF format with Japanese font support."""
    
    def __init__(self, novel_info: Dict, chapters: List[Dict]):
        self.novel_info = novel_info
        self.chapters = chapters
        self.font_path = self._get_japanese_font()
        
    def _get_japanese_font(self):
        """Get a Japanese font file, downloading if necessary."""
        # Directory for fonts
        font_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
        os.makedirs(font_dir, exist_ok=True)
        
        # Font file path
        font_path = os.path.join(font_dir, "NotoSansJP-VariableFont_wght.ttf")
        
        # Download font if it doesn't exist
        if not os.path.exists(font_path):
            print("Downloading Japanese font (Noto Sans JP)...")
            try:
                font_url = "https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@100..900&display=swap"
                urllib.request.urlretrieve(font_url, font_path)
                print("Font downloaded successfully")
            except Exception as e:
                print(f"Failed to download font: {e}")
                print("PDF export may not support Japanese characters")
                return None
        
        return font_path
    
    def create_pdf(self, output_path: str, include_novel_info: bool = True, chapter_range: Optional[List[int]] = None):
        """Create PDF with Japanese font support."""
        if not REPORTLAB_AVAILABLE:
            raise ImportError("reportlab is not available. Cannot create PDF.")
        
        if not self.font_path:
            raise ValueError("Japanese font not available. Cannot create PDF with Japanese characters.")
        
        # Register the font
        font_name = "NotoSansJP"
        pdfmetrics.registerFont(TTFont(font_name, self.font_path))
        
        # Create PDF
        pdf = canvas.Canvas(output_path, pagesize=letter)
        width, height = letter
        
        # Set default font
        pdf.setFont(font_name, 12)
        
        # Helper function to add text with proper wrapping
        def add_text(text, x, y, width, font_size=12, leading=14):
            pdf.setFont(font_name, font_size)
            text_obj = pdf.beginText(x, y)
            text_obj.setFont(font_name, font_size)
            text_obj.setLeading(leading)  # Line spacing
            
            # Better text wrapping for Japanese text
            # For Japanese text, we need character-by-character wrapping
            if any(ord(c) > 127 for c in text):
                # Japanese text - wrap by characters
                current_line = ""
                for char in text:
                    test_line = current_line + char
                    if pdf.stringWidth(test_line, font_name, font_size) < width - 2*x:
                        current_line += char
                    else:
                        text_obj.textLine(current_line)
                        current_line = char
                
                if current_line:
                    text_obj.textLine(current_line)
            else:
                # English text - wrap by words
                words = text.split()
                current_line = []
                
                for word in words:
                    test_line = ' '.join(current_line + [word])
                    if pdf.stringWidth(test_line, font_name, font_size) < width - 2*x:
                        current_line.append(word)
                    else:
                        text_obj.textLine(' '.join(current_line))
                        current_line = [word]
                
                if current_line:
                    text_obj.textLine(' '.join(current_line))
            
            pdf.drawText(text_obj)
            return y - (text_obj.getY() - y + 10)  # Return new y position based on actual text height
        
        # Add cover page if novel info is included
        if include_novel_info:
            # Title
            pdf.setFont(font_name, 24)
            pdf.drawCentredString(width/2, height-100, self.novel_info['title'])
            
            # Author
            pdf.setFont(font_name, 16)
            pdf.drawCentredString(width/2, height-150, f"Author: {self.novel_info['author']}")
            
            # Description
            y_pos = height - 200
            pdf.setFont(font_name, 14)
            pdf.drawString(50, y_pos, "Description:")
            y_pos -= 30
            y_pos = add_text(self.novel_info['description'], 50, y_pos, width-100)
            
            # Metadata
            if self.novel_info['metadata']:
                y_pos -= 20
                pdf.setFont(font_name, 14)
                pdf.drawString(50, y_pos, "Metadata:")
                y_pos -= 20
                
                for key, value in self.novel_info['metadata'].items():
                    if isinstance(value, list):
                        value_str = ", ".join(value)
                        y_pos = add_text(f"{key}: {value_str}", 50, y_pos, width-100)
                    else:
                        y_pos = add_text(f"{key}: {value}", 50, y_pos, width-100)
            
            # URL
            y_pos -= 20
            pdf.drawString(50, y_pos, f"URL: {self.novel_info['url']}")
            
            # Add TOC page
            pdf.showPage()
            pdf.setFont(font_name, 18)
            pdf.drawCentredString(width/2, height-100, "Table of Contents")
            
            # Filter chapters based on range
            filtered_chapters = self.chapters
            if chapter_range:
                start, end = chapter_range
                filtered_chapters = [ch for ch in self.chapters if start <= ch['index'] <= end]
            
            # Add TOC entries
            y_pos = height - 150
            for chapter in filtered_chapters:
                pdf.setFont(font_name, 12)
                toc_entry = f"{chapter['index']}. {chapter['title']}"
                pdf.drawString(50, y_pos, toc_entry)
                y_pos -= 20
                
                # Add new page if needed
                if y_pos < 50:
                    pdf.showPage()
                    pdf.setFont(font_name, 18)
                    pdf.drawCentredString(width/2, height-100, "Table of Contents (continued)")
                    y_pos = height - 150
        
        # Add chapters
        current_arc = None
        for chapter in self.chapters:
            # Skip if not in range
            if chapter_range and not (chapter_range[0] <= chapter['index'] <= chapter_range[1]):
                continue
            
            # New page for each chapter
            pdf.showPage()
            
            # Check if arc changed
            if 'arc' in chapter and chapter['arc'] != current_arc:
                current_arc = chapter['arc']
                if current_arc:
                    pdf.setFont(font_name, 16)
                    pdf.drawCentredString(width/2, height-100, current_arc)
                    y_pos = height - 130
                else:
                    y_pos = height - 100
            else:
                y_pos = height - 100
            
            # Chapter title
            pdf.setFont(font_name, 18)
            pdf.drawCentredString(width/2, y_pos, chapter['title'])
            y_pos -= 40
            
            # Chapter content
            if 'content' in chapter:
                # Split content into paragraphs
                paragraphs = chapter['content'].split('\n')
                for paragraph in paragraphs:
                    if paragraph.strip():
                        y_pos = add_text(paragraph, 50, y_pos, width-100)
                        y_pos -= 10
                    
                    # Add new page if needed
                    if y_pos < 50:
                        pdf.showPage()
                        pdf.setFont(font_name, 12)
                        y_pos = height - 50
        
        # Save the PDF
        pdf.save()
        return output_path
    
    def save(self, filename: str, include_novel_info: bool = True, chapter_range: Optional[List[int]] = None) -> str:
        if not REPORTLAB_AVAILABLE:
            raise ImportError("reportlab is not available. Cannot create PDF.")
            
        # Ensure filename has .pdf extension
        if not filename.lower().endswith('.pdf'):
            filename += '.pdf'
            
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(os.path.abspath(filename)), exist_ok=True)
        
        # Create PDF
        return self.create_pdf(filename, include_novel_info, chapter_range)


def download_novel(novel_info: Dict, chapters: List[Dict], format_type: str = 'epub', 
                  include_novel_info: bool = True, chapter_range: Optional[List[int]] = None) -> str:
    """Download novel in specified format."""
    # Create filename from novel title
    title = sanitize_filename(novel_info['title'])
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Create base directory for downloads
    download_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
    os.makedirs(download_dir, exist_ok=True)
    
    # Create filename
    if chapter_range:
        filename = f"{title}_{chapter_range[0]}-{chapter_range[1]}_{timestamp}"
    else:
        filename = f"{title}_full_{timestamp}"
    
    filepath = os.path.join(download_dir, filename)
    
    # Note: Translation should be applied before this function is called
    # The chapters and novel_info should already contain translated content
    
    # Export based on format
    if format_type.lower() == 'epub':
        if not EPUB_AVAILABLE:
            raise ImportError("ebooklib is not available. Cannot create EPUB.")
        exporter = EpubExporter(novel_info, chapters)
        return exporter.save(filepath + ".epub", include_novel_info, chapter_range)
    elif format_type.lower() == 'pdf':
        if not REPORTLAB_AVAILABLE:
            raise ImportError("reportlab is not available. Cannot create PDF.")
        exporter = JapanesePdfExporter(novel_info, chapters)
        return exporter.save(filepath + ".pdf", include_novel_info, chapter_range)
    else:
        raise ValueError(f"Unsupported format: {format_type}")