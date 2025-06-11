# Syosetu Novel Scraper

A flexible Python scraper for Japanese web novels from various Syosetu sites with translation capabilities.

## Supported Sites

- ncode.syosetu.com (Under Development)
- novel18.syosetu.com (Under Development)
- mnlt.syosetu.com (Under Development)
- yomou.syosetu.com (Under Development)
- syosetu.org (Under Development)

## Setup

1. Ensure you have Python 3.7+ installed
2. Set up the virtual environment:
   ```
   python -m venv venv
   ```
3. Activate the virtual environment:
   - Windows: `venv\Scripts\activate`
   - macOS/Linux: `source venv/bin/activate`
4. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
5. For Hameln site support, install cloudscraper:
   ```
   pip install cloudscraper
   ```

## Usage

### Interactive Mode

Run the main script without arguments for interactive mode:
```
python main.py
```

Follow the prompts to:
1. Select which Syosetu site to scrape from
2. View translation settings
3. Enter a novel ID
4. View novel information and chapter list
5. Download chapters as PDF or EPUB, or view a specific chapter

### Command Line Interface

The scraper supports command line arguments for configuration and automation:

```
python main.py --site ncode --novel-id n9669bk --chapter 1
```

#### Download Options

- `--chapter CHAPTER` - Chapter number to download (0 for all, or range like 1-5)
- `--download FORMAT` - Download novel in specified format (pdf or epub)
- `--include-info` - Include novel information in download

Example:
```
python main.py --site ncode --novel-id n9669bk --chapter 1-10 --download epub --include-info
```

#### Configuration Options

- `--translation enable|disable` - Enable or disable translation
- `--translator SERVICE` - Select translation service (see below)
- `--api-key KEY` - Set API key for translation service
- `--target-lang LANG` - Set target language code (e.g., en, fr, es)
- `--translate-title yes|no` - Whether to translate chapter titles
- `--translate-content yes|no` - Whether to translate chapter content
- `--delay SECONDS` - Set delay between requests in seconds

## Features

- Support for multiple Syosetu sites with different HTML structures
- Fetch novel information (title, author, description, metadata)
- List all chapters of a novel
- Download chapters as PDF or EPUB
- View chapter content in terminal
- Configurable request delay to be respectful to servers
- Error handling and logging
- Translation support for novel content using multiple translation services
- Content chunking for better translation results (1000 character limit per chunk)
- Graceful handling of translation errors
- Reuse of chapter titles from chapter list for Hameln site

## Translation

The scraper supports translating novel content using various translation services:

### Supported Translation Services

- `google` - Google Translate (no API key required)
- `deepl` - DeepL API (requires API key)
- `mymemory` - MyMemory Translation API (no API key required for limited usage)
- `linguee` - Linguee Dictionary (no API key required)
- `libre` - LibreTranslate (no API key required for public instances)
- `microsoft` - Microsoft Translator (requires API key)
- `papago` - Papago Translator (requires API key)
- `yandex` - Yandex Translator (requires API key)
- `chatgpt` - ChatGPT (requires API key)

### Examples

Enable Google Translate:
```
python main.py --translation enable --translator google
```

Use DeepL with API key:
```
python main.py --translation enable --translator deepl --api-key YOUR_API_KEY
```

## Notes

- This scraper is designed to be flexible and handle different HTML structures across Syosetu sites.
- For Hameln site, the scraper reuses chapter titles from the chapter list to avoid issues with inconsistent HTML structure.
- Translation is done in chunks of approximately 3000 characters to avoid API limits and improve translation quality.
- Newlines are preserved during translation by using special markers.
- If translation fails for any reason, the original text is used instead.