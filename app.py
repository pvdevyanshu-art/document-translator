import os
import io
import google.generativeai as genai
from flask import Flask, render_template, request, send_file, flash, redirect, url_for
from dotenv import load_dotenv
import PyPDF2
import docx
from fpdf import FPDF

# Load environment variables from .env file
load_dotenv()

# Configure the Gemini API
try:
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
except Exception as e:
    print(f"Error configuring Gemini API: {e}")
    # Exit or handle the absence of API key appropriately
    exit()


app = Flask(__name__)
app.secret_key = 'your_super_secret_key' # Needed for flashing messages

# Supported languages dictionary
LANGUAGES = {
    'en': 'English', 'es': 'Spanish', 'fr': 'French', 'de': 'German', 'it': 'Italian',
    'pt': 'Portuguese', 'nl': 'Dutch', 'ru': 'Russian', 'ja': 'Japanese', 'ko': 'Korean',
    'zh': 'Chinese (Simplified)', 'ar': 'Arabic', 'hi': 'Hindi'
}

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

def chunk_text(text, chunk_size=4000):
    """Splits text into smaller chunks based on paragraphs."""
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
    
    source_language = LANGUAGES.get(source_lang, "auto-detect")
    target_language = LANGUAGES.get(target_lang, "English")

    prompt = (f"Translate the following text from {source_language} to {target_language}. "
              "Provide ONLY the translated text, without any additional explanations, context, or conversational text. "
              "Preserve paragraph breaks.\n\n"
              f"Text to translate:\n---\n{text_to_translate}\n---")

    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"An error occurred during translation: {e}")
        return f"[[Error during translation: {e}]]"


def create_translated_pdf(text):
    """Creates a PDF document from the translated text using a Unicode font."""
    pdf = FPDF()
    pdf.add_page()
    
    # Add the Unicode font. The 'uni=True' part is crucial.
    pdf.add_font('DejaVu', '', 'DejaVuSans.ttf', uni=True)
    pdf.set_font('DejaVu', '', 12)
    
    # Write the text to the PDF
    pdf.multi_cell(0, 10, text)
    
    # Save the PDF to a byte stream
    pdf_buffer = io.BytesIO()
    # Use 'latin-1' encoding as a container, which is standard for FPDF's internal handling
    pdf_content = pdf.output(dest='S').encode('latin-1')
    pdf_buffer.write(pdf_content)
    pdf_buffer.seek(0)
    return pdf_buffer

# --- Flask Routes ---

@app.route('/', methods=['GET'])
def index():
    """Renders the main page."""
    return render_template('index.html', languages=LANGUAGES)

@app.route('/translate', methods=['POST'])
def translate_document():
    """Handles the document translation process."""
    if 'file' not in request.files:
        flash('No file part')
        return redirect(url_for('index'))
    
    file = request.files['file']
    source_lang = request.form.get('source_lang')
    target_lang = request.form.get('target_lang')

    if file.filename == '':
        flash('No selected file')
        return redirect(url_for('index'))

    if file:
        filename = file.filename
        original_text = ""
        
        try:
            if filename.endswith('.pdf'):
                original_text = extract_text_from_pdf(file.stream)
            elif filename.endswith('.docx'):
                original_text = extract_text_from_docx(file.stream)
            else:
                flash('Unsupported file type. Please upload a .pdf or .docx file.')
                return redirect(url_for('index'))
        except Exception as e:
            flash(f"Error reading file: {e}")
            return redirect(url_for('index'))

        if not original_text.strip():
            flash("Could not extract any text from the document.")
            return redirect(url_for('index'))
            
        # Chunk and translate the text
        text_chunks = chunk_text(original_text)
        translated_text = ""
        for i, chunk in enumerate(text_chunks):
            print(f"Translating chunk {i+1}/{len(text_chunks)}...")
            translated_text += translate_text(chunk, target_lang, source_lang) + "\n"
        
        print("Translation complete. Generating PDF...")
        
        # Create the translated PDF and send it for download
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