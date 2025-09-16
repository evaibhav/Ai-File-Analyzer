from flask import Flask, request, render_template, flash, redirect, url_for, jsonify
import os
import requests
import json
import re
import time
from werkzeug.utils import secure_filename
import PyPDF2
import docx
import pandas as pd
from openpyxl import load_workbook
import nltk
import textstat
from langdetect import detect
from collections import Counter
import threading
from concurrent.futures import ThreadPoolExecutor

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

# Download NLTK data (run once)
try:
    nltk.download('punkt', quiet=True)
    nltk.download('stopwords', quiet=True)
except:
    pass

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def preprocess_text(text):
    """Clean and preprocess text for better analysis"""
    # Remove extra whitespace and normalize
    text = re.sub(r'\s+', ' ', text.strip())
    # Remove special characters but keep basic punctuation
    text = re.sub(r'[^\w\s\.,!?;:\-()]', '', text)
    return text

def extract_key_content(text, max_chars=1500):
    """Extract key content from text to reduce processing time"""
    # Clean the text first
    text = preprocess_text(text)
    
    # If text is short enough, return as is
    if len(text) <= max_chars:
        return text
    
    # Split into sentences
    sentences = nltk.sent_tokenize(text)
    
    # If we have few sentences, take first portion
    if len(sentences) <= 10:
        return text[:max_chars]
    
    # Extract key sentences from beginning, middle, and end
    total_sentences = len(sentences)
    key_sentences = []
    
    # Take first 40% of sentences
    key_sentences.extend(sentences[:int(total_sentences * 0.4)])
    
    # Take middle 20% of sentences
    middle_start = int(total_sentences * 0.4)
    middle_end = int(total_sentences * 0.6)
    key_sentences.extend(sentences[middle_start:middle_end])
    
    # Take last 20% of sentences
    key_sentences.extend(sentences[int(total_sentences * 0.8):])
    
    # Join and truncate if still too long
    extracted_text = ' '.join(key_sentences)
    if len(extracted_text) > max_chars:
        extracted_text = extracted_text[:max_chars] + "..."
    
    return extracted_text

def get_text_summary(text):
    """Get basic text statistics"""
    try:
        word_count = len(text.split())
        char_count = len(text)
        
        # Reading level
        reading_level = textstat.flesch_reading_ease(text)
        
        # Language detection
        try:
            language = detect(text)
        except:
            language = "unknown"
        
        return {
            'word_count': word_count,
            'char_count': char_count,
            'reading_level': reading_level,
            'language': language
        }
    except:
        return {
            'word_count': 0,
            'char_count': 0,
            'reading_level': 0,
            'language': "unknown"
        }

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
                # Limit to first 10 pages for faster processing
                max_pages = min(10, len(pdf_reader.pages))
                for i in range(max_pages):
                    text += pdf_reader.pages[i].extract_text() + "\n"
                return text
        
        elif file_extension == 'docx':
            doc = docx.Document(filepath)
            text = ""
            # Limit to first 50 paragraphs
            for i, paragraph in enumerate(doc.paragraphs):
                if i >= 50:
                    break
                text += paragraph.text + "\n"
            return text
        
        elif file_extension in ['xlsx', 'csv']:
            if file_extension == 'xlsx':
                df = pd.read_excel(filepath, nrows=1000)  # Limit rows
            else:
                df = pd.read_csv(filepath, nrows=1000)  # Limit rows
            
            # Convert dataframe to text representation
            text = f"Data Summary:\n"
            text += f"Shape: {df.shape}\n"
            text += f"Columns: {list(df.columns)}\n\n"
            text += "First 5 rows:\n"
            text += df.head().to_string()
            
            # Add basic statistics for numeric columns
            numeric_cols = df.select_dtypes(include=['number']).columns
            if len(numeric_cols) > 0:
                text += "\n\nNumeric Data Summary:\n"
                text += df[numeric_cols].describe().to_string()
            
            return text
        
        else:
            return "Unsupported file type"
            
    except Exception as e:
        return f"Error reading file: {str(e)}"

def create_optimized_prompt(text_content, user_prompt, text_stats):
    """Create an optimized prompt for faster processing"""
    
    # Create context about the document
    context = f"""
Document Info:
- Length: {text_stats['word_count']} words
- Language: {text_stats['language']}
- Reading Level: {text_stats['reading_level']:.1f}

User Request: {user_prompt}

Document Content:
{text_content}

Please provide a concise analysis focused on the user's request."""
    
    return context

def analyze_with_ollama_optimized(text_content, user_prompt):
    """Optimized Ollama analysis with streaming and better prompting"""
    try:
        # Get text statistics
        text_stats = get_text_summary(text_content)
        
        # Extract key content to reduce processing time
        key_content = extract_key_content(text_content, max_chars=1200)
        
        # Create optimized prompt
        optimized_prompt = create_optimized_prompt(key_content, user_prompt, text_stats)
        
        # Ollama API endpoint
        url = "http://localhost:11434/api/generate"
        
        # Use a smaller, faster model if available
        models_to_try = ["llama3.2:1b", "phi3:mini", "qwen2:0.5b", "llama2"]
        
        for model in models_to_try:
            try:
                # Check if model exists
                check_url = "http://localhost:11434/api/tags"
                response = requests.get(check_url, timeout=5)
                
                if response.status_code == 200:
                    available_models = [m['name'] for m in response.json().get('models', [])]
                    if model in available_models:
                        break
            except:
                continue
        else:
            model = "llama2"  # fallback
        
        # Request payload with optimizations
        payload = {
            "model": model,
            "prompt": optimized_prompt,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "top_p": 0.9,
                "max_tokens": 500,  # Limit response length
                "stop": ["</analysis>", "---"]
            }
        }
        
        # Make request with timeout
        response = requests.post(url, json=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            analysis = result.get('response', 'No response received')
            
            # Add document statistics to the response
            stats_info = f"""
📊 Document Statistics:
• Words: {text_stats['word_count']:,}
• Characters: {text_stats['char_count']:,}
• Language: {text_stats['language'].upper()}
• Reading Level: {text_stats['reading_level']:.1f} (Flesch Score)

🤖 AI Analysis:
{analysis}
"""
            return stats_info
        else:
            return f"Error: Ollama API returned status {response.status_code}"
            
    except requests.exceptions.Timeout:
        return "Analysis timed out. Please try with a smaller file or simpler prompt."
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
    start_time = time.time()
    
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
        extract_start = time.time()
        text_content = extract_text_from_file(filepath)
        extract_time = time.time() - extract_start
        
        # Analyze with Ollama
        analysis_start = time.time()
        analysis = analyze_with_ollama_optimized(text_content, user_prompt)
        analysis_time = time.time() - analysis_start
        
        # Clean up uploaded file
        try:
            os.remove(filepath)
        except:
            pass
        
        total_time = time.time() - start_time
        
        # Add processing time info
        time_info = f"""
⏱️ Processing Time:
• File extraction: {extract_time:.2f}s
• AI analysis: {analysis_time:.2f}s
• Total time: {total_time:.2f}s

{analysis}
"""
        
        return render_template('index.html', 
                             analysis=time_info, 
                             filename=filename,
                             prompt=user_prompt)
    else:
        flash('Invalid file type. Allowed types: txt, pdf, docx, xlsx, csv')
        return redirect(request.url)

@app.route('/health')
def health_check():
    """Health check endpoint"""
    try:
        # Check Ollama connection
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            return jsonify({"status": "healthy", "ollama": "connected"})
        else:
            return jsonify({"status": "unhealthy", "ollama": "disconnected"})
    except:
        return jsonify({"status": "unhealthy", "ollama": "disconnected"})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)