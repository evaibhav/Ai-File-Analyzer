from flask import Flask, request, render_template, flash, redirect, url_for
import os
import requests
import json
from werkzeug.utils import secure_filename
import PyPDF2
import docx
import pandas as pd
from openpyxl import load_workbook

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'docx', 'xlsx', 'csv'}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# Create uploads directory if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_file(filepath):
    """Extract text content from uploaded file based on file type"""
    try:
        file_extension = filepath.split('.')[-1].lower()
        
        if file_extension == 'txt':
            with open(filepath, 'r', encoding='utf-8') as file:
                return file.read()
        
        elif file_extension == 'pdf':
            with open(filepath, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
                return text
        
        elif file_extension == 'docx':
            doc = docx.Document(filepath)
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            return text
        
        elif file_extension in ['xlsx', 'csv']:
            if file_extension == 'xlsx':
                df = pd.read_excel(filepath)
            else:
                df = pd.read_csv(filepath)
            
            # Convert dataframe to text representation
            text = f"Data Summary:\n"
            text += f"Shape: {df.shape}\n"
            text += f"Columns: {list(df.columns)}\n\n"
            text += "First 5 rows:\n"
            text += df.head().to_string()
            text += "\n\nData Info:\n"
            text += df.describe().to_string()
            return text
        
        else:
            return "Unsupported file type"
            
    except Exception as e:
        return f"Error reading file: {str(e)}"

def analyze_with_ollama(text_content, user_prompt):
    """Send text to Ollama for analysis"""
    try:
        # Ollama API endpoint (default local installation)
        url = "http://localhost:11434/api/generate"
        
        # Prepare the prompt
        full_prompt = f"""
        Please analyze the following content based on this request: {user_prompt}
        
        Content to analyze:
        {text_content[:4000]}  # Limit content to avoid token limits
        
        Please provide a detailed analysis.
        """
        
        # Request payload
        payload = {
            "model": "llama2",  # You can change this to any model you have installed
            "prompt": full_prompt,
            "stream": False
        }
        
        # Make request to Ollama
        response = requests.post(url, json=payload)
        
        if response.status_code == 200:
            result = response.json()
            return result.get('response', 'No response received')
        else:
            return f"Error: Ollama API returned status {response.status_code}"
            
    except requests.exceptions.ConnectionError:
        return "Error: Could not connect to Ollama. Make sure Ollama is running on localhost:11434"
    except Exception as e:
        return f"Error analyzing content: {str(e)}"

@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload and analysis"""
    if 'file' not in request.files:
        flash('No file selected')
        return redirect(request.url)
    
    file = request.files['file']
    user_prompt = request.form.get('prompt', '').strip()
    
    if file.filename == '':
        flash('No file selected')
        return redirect(request.url)
    
    if not user_prompt:
        flash('Please provide an analysis prompt')
        return redirect(request.url)
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Extract text from file
        text_content = extract_text_from_file(filepath)
        
        # Analyze with Ollama
        analysis = analyze_with_ollama(text_content, user_prompt)
        
        # Clean up uploaded file
        os.remove(filepath)
        
        return render_template('index.html', 
                             analysis=analysis, 
                             filename=filename,
                             prompt=user_prompt)
    else:
        flash('Invalid file type. Allowed types: txt, pdf, docx, xlsx, csv')
        return redirect(request.url)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)