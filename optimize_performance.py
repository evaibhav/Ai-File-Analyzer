#!/usr/bin/env python3
"""
Performance optimization script for AI File Analyzer
Run this script to optimize your Ollama setup for faster analysis
"""

import requests
import json
import time
import subprocess
import sys

def check_ollama_connection():
    """Check if Ollama is running"""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            print("✅ Ollama is running")
            return True
        else:
            print("❌ Ollama is not responding")
            return False
    except:
        print("❌ Cannot connect to Ollama")
        return False

def get_available_models():
    """Get list of available models"""
    try:
        response = requests.get("http://localhost:11434/api/tags")
        if response.status_code == 200:
            models = response.json().get('models', [])
            return [model['name'] for model in models]
        return []
    except:
        return []

def install_fast_models():
    """Install recommended fast models"""
    fast_models = [
        "llama3.2:1b",
        "phi3:mini", 
        "qwen2:0.5b"
    ]
    
    print("Installing fast models for better performance...")
    for model in fast_models:
        print(f"Installing {model}...")
        try:
            result = subprocess.run(
                ["ollama", "pull", model], 
                capture_output=True, 
                text=True,
                timeout=300
            )
            if result.returncode == 0:
                print(f"✅ {model} installed successfully")
            else:
                print(f"❌ Failed to install {model}: {result.stderr}")
        except subprocess.TimeoutExpired:
            print(f"⏱️ {model} installation timed out")
        except Exception as e:
            print(f"❌ Error installing {model}: {e}")

def benchmark_models():
    """Benchmark different models for performance"""
    models = get_available_models()
    test_prompt = "Summarize this text in one sentence: This is a sample document about artificial intelligence and machine learning applications."
    
    print("\n🔍 Benchmarking models...")
    results = []
    
    for model in models:
        if any(fast in model for fast in ["1b", "mini", "0.5b", "llama3.2"]):
            print(f"Testing {model}...")
            
            start_time = time.time()
            try:
                payload = {
                    "model": model,
                    "prompt": test_prompt,
                    "stream": False,
                    "options": {
                        "max_tokens": 100
                    }
                }
                
                response = requests.post(
                    "http://localhost:11434/api/generate",
                    json=payload,
                    timeout=30
                )
                
                if response.status_code == 200:
                    end_time = time.time()
                    duration = end_time - start_time
                    results.append((model, duration))
                    print(f"✅ {model}: {duration:.2f}s")
                else:
                    print(f"❌ {model}: Failed to respond")
                    
            except Exception as e:
                print(f"❌ {model}: Error - {e}")
    
    # Sort by performance
    results.sort(key=lambda x: x[1])
    
    print("\n📊 Performance Results (fastest first):")
    for model, duration in results:
        print(f"{model}: {duration:.2f}s")
    
    if results:
        print(f"\n🏆 Fastest model: {results[0][0]} ({results[0][1]:.2f}s)")
        return results[0][0]
    
    return None

def update_app_config(fastest_model):
    """Update app.py with the fastest model"""
    if not fastest_model:
        return
    
    print(f"\n🔧 Updating app.py to use {fastest_model}...")
    
    try:
        with open('app.py', 'r') as f:
            content = f.read()
        
        # Update the models_to_try list
        old_line = 'models_to_try = ["llama3.2:1b", "phi3:mini", "qwen2:0.5b", "llama2"]'
        new_line = f'models_to_try = ["{fastest_model}", "llama3.2:1b", "phi3:mini", "qwen2:0.5b", "llama2"]'
        
        content = content.replace(old_line, new_line)
        
        with open('app.py', 'w') as f:
            f.write(content)
        
        print("✅ app.py updated with fastest model")
        
    except Exception as e:
        print(f"❌ Failed to update app.py: {e}")

def main():
    print("🚀 AI File Analyzer Performance Optimizer")
    print("=" * 50)
    
    # Check Ollama connection
    if not check_ollama_connection():
        print("Please start Ollama first: ollama serve")
        sys.exit(1)
    
    # Get current models
    models = get_available_models()
    print(f"📋 Current models: {models}")
    
    # Install fast models if needed
    fast_models = ["llama3.2:1b", "phi3:mini", "qwen2:0.5b"]
    missing_models = [model for model in fast_models if model not in models]
    
    if missing_models:
        print(f"📦 Missing fast models: {missing_models}")
        install_fast_models()
    else:
        print("✅ All recommended fast models are installed")
    
    # Benchmark models
    fastest_model = benchmark_models()
    
    # Update app configuration
    update_app_config(fastest_model)
    
    print("\n🎉 Optimization complete!")
    print("Restart your Flask application to use the optimized settings.")

if __name__ == "__main__":
    main()