import os
import io
import google.generativeai as genai
from flask import Flask, render_template, request, send_file, flash, redirect, url_for
from dotenv import load_dotenv
import PyPDF2
import docx
from fpdf import FPDF
from PIL import Image
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Load environment variables from .env file
load_dotenv()

# Configure the Gemini API
try:
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
except Exception as e:
    print(f"Error configuring Gemini API: {e}")
    exit()


app = Flask(__name__)
app.secret_key = 'your_super_secret_key'

# --- Helper Functions ---

def extract_text_from_pdf(file_stream):
    """Extracts text from a PDF file stream."""
    text = ""
    reader = PyPDF2.PdfReader(file_stream)
    for page in reader.pages:
        text += page.extract_text() or ""
    return text

def extract_text_from_docx(file_stream):
    """Extracts text from a DOCX file stream."""
    text = ""
    doc = docx.Document(file_stream)
    for para in doc.paragraphs:
        text += para.text + "\n"
    return text

def extract_text_from_image(file_stream, lang_code):
    """Extracts text from an image using the specified language code."""
    try:
        image = Image.open(file_stream)
        # Use the lang_code variable to tell Tesseract which language to use
        text = pytesseract.image_to_string(image, lang=lang_code)
        return text
    except Exception as e:
        print(f"AN ERROR OCCURRED DURING OCR: {e}")
        return ""

def chunk_text(text, chunk_size=4000):
    """Splits text into smaller chunks."""
    paragraphs = text.split('\n')
    chunks = []
    current_chunk = ""
    for para in paragraphs:
        if len(current_chunk) + len(para) + 1 < chunk_size:
            current_chunk += para + "\n"
        else:
            chunks.append(current_chunk)
            current_chunk = para + "\n"
    if current_chunk:
        chunks.append(current_chunk)
    return chunks

def translate_text(text_to_translate, target_lang, source_lang="auto"):
    """Translates a text chunk using the Gemini API."""
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = (f"Translate the following text to {target_lang}. "
              "Provide ONLY the translated text, without any additional explanations or context. "
              "Preserve paragraph breaks.\n\n"
              f"Text to translate:\n---\n{text_to_translate}\n---")

    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"An error occurred during translation: {e}")
        return f"[[Error during translation: {e}]]"

def create_translated_pdf(text):
    """Creates a PDF document from the translated text."""
    pdf = FPDF()
    pdf.add_page()
    pdf.add_font('DejaVu', '', 'DejaVuSans.ttf', uni=True)
    pdf.set_font('DejaVu', '', 12)
    pdf.multi_cell(0, 10, text)
    pdf_buffer = io.BytesIO()
    # Updated line to work with newer fpdf2 versions
    pdf_content = pdf.output(dest='S')
    pdf_buffer.write(pdf_content)
    pdf_buffer.seek(0)
    return pdf_buffer

# --- Flask Routes ---

@app.route('/', methods=['GET'])
def index():
    """Renders the main page."""
    return render_template('index.html')

@app.route('/translate', methods=['POST'])
def translate_document():
    """Handles the document translation process."""
    if 'file' not in request.files:
        flash('No file part')
        return redirect(url_for('index'))
    
    file = request.files['file']
    target_lang = request.form.get('target_lang')

    # Get the combined language value (e.g., "es|spa") and split it
    source_lang_full = request.form.get('source_lang', 'auto|eng').split('|')
    source_lang = source_lang_full[0]      # For Gemini (e.g., 'es' or 'auto')
    ocr_lang_code = source_lang_full[1]  # For Tesseract (e.g., 'spa' or 'eng')

    if file.filename == '':
        flash('No selected file')
        return redirect(url_for('index'))

    if file:
        filename = file.filename
        original_text = ""
        
        try:
            filename_lower = filename.lower()
    
            if filename_lower.endswith('.pdf'):
                original_text = extract_text_from_pdf(file.stream)
            elif filename_lower.endswith('.docx'):
                original_text = extract_text_from_docx(file.stream)
            elif filename_lower.endswith('.txt'):
                original_text = file.stream.read().decode('utf-8')
            elif filename_lower.endswith(('.png', '.jpg', '.jpeg')):
                # Pass the OCR language code to the extraction function
                original_text = extract_text_from_image(file.stream, ocr_lang_code)
            else:
                flash('Unsupported file type. Please upload a .pdf, .docx, .txt, or image file.')
                return redirect(url_for('index'))

        except Exception as e:
            flash(f"Error reading file: {e}")
            return redirect(url_for('index'))

        if not original_text.strip():
            flash("Could not extract any text from the document.")
            return redirect(url_for('index'))
            
        text_chunks = chunk_text(original_text)
        translated_text = ""
        for i, chunk in enumerate(text_chunks):
            print(f"Translating chunk {i+1}/{len(text_chunks)}...")
            translated_text += translate_text(chunk, target_lang, source_lang) + "\n"
        
        print("Translation complete. Generating PDF...")
        
        pdf_buffer = create_translated_pdf(translated_text)
        
        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name=f'translated_{filename}.pdf',
            mimetype='application/pdf'
        )

    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
