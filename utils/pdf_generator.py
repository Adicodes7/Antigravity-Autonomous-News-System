import tempfile
import logging
import os
import urllib.request
from fpdf import FPDF

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def _ensure_unicode_font():
    """Ensures the FreeSans true type font is available locally.
    FreeSans natively supports both English (Latin) and Hindi (Devanagari) characters
    so URLs and special symbols won't get stripped.
    """
    font_dir = os.path.dirname(os.path.abspath(__file__))
    font_path = os.path.join(font_dir, "FreeSans.ttf")
    
    if not os.path.exists(font_path):
        logger.info("FreeSans.ttf not found. Downloading for Universal PDF support...")
        url = "https://github.com/opensourcedesign/fonts/raw/master/gnu-freefont_freesans/FreeSans.ttf"
        try:
            urllib.request.urlretrieve(url, font_path)
            logger.info("Successfully downloaded FreeSans.ttf!")
        except Exception as e:
            logger.error(f"Failed to download font: {e}")
            
    return font_path

def generate_pdf(content: str) -> str:
    """
    Generates a PDF from the given content with Unicode support.
    """
    try:
        pdf = FPDF()
        pdf.add_page()
        
        font_path = _ensure_unicode_font()
        
        if os.path.exists(font_path):
            # Load FreeSans which has both Latin and Devanagari glyphs
            pdf.add_font("FreeSans", fname=font_path)
            pdf.set_font("FreeSans", size=12)
        else:
            # Emergency Fallback if download fails (will strip Hindi)
            pdf.set_font("Helvetica", size=12)
            content = content.encode('ascii', 'ignore').decode('ascii')
        
        # Add generated content with multi_cell for wrapping text
        pdf.multi_cell(0, 7, text=content)
        
        # Create a temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        temp_path = temp_file.name
        temp_file.close()
        
        pdf.output(temp_path)
        logger.info(f"PDF successfully generated at {temp_path}")
        return temp_path
    except Exception as e:
        logger.error(f"Error generating PDF: {e}")
        return ""
