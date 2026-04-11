# ══════════════════════════════════════════
#  FLASK WEB SERVER FOR PDF PROCESSING API
#  ======================================
#  This module provides a REST API for processing PDF documents
#  and generating descriptions, summaries, and quiz questions.
#  
#  Endpoints:
#    - POST /describe  : Generate document description
#    - POST /summarize : Generate document summary  
#    - POST /quiz      : Generate quiz questions
#  
#  Author: Quiz Application
#  Dependencies: Flask, Flask-CORS
# ══════════════════════════════════════════

# Flask framework imports
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

# Import processing functions from the process module
from process import get_description, get_summary, get_quiz, get_cover

# Initialize Flask application
app = Flask(__name__)

# Enable Cross-Origin Resource Sharing (CORS) for all routes
# This allows the frontend to make requests to this API from different domains
CORS(app) 

@app.route("/")
def index():
    """Serve the main index.html file"""
    return send_from_directory(".", "index.html")

@app.route("/<path:filename>")
def static_files(filename):
    """Serve static files (CSS, JS, images)"""
    return send_from_directory(".", filename)


@app.route("/describe", methods=["POST"])
def describe():
    """
    Generate a description for the uploaded PDF document.
    
    Endpoint: POST /describe
    
    Request Body (JSON):
        {
            "base64": "<base64_encoded_pdf_content>"
        }
        
    Response (JSON):
        {
            "description": "<generated_description>"
        }
        
    Process:
        1. Extract base64 PDF from request
        2. Call get_description() function
        3. Return description as JSON response
    """
    # Step 1: Extract JSON data from request
    data = request.json
    
    # Step 2: Generate description using the processing function
    description = get_description(data["base64"])
    
    # Step 3: Return description as JSON response
    return jsonify({"description": description})


@app.route("/summarize", methods=["POST"])
def summarize():
    """
    Generate a summary for the uploaded PDF document.
    
    Endpoint: POST /summarize
    
    Request Body (JSON):
        {
            "base64": "<base64_encoded_pdf_content>"
        }
        
    Response (JSON):
        {
            "summary": "<generated_summary>"
        }
        
    Process:
        1. Extract base64 PDF from request
        2. Call get_summary() function
        3. Return summary as JSON response
    """
    # Step 1: Extract JSON data from request
    data = request.json
    
    # Step 2: Generate summary using the processing function
    summary = get_summary(data["base64"])
    
    # Step 3: Return summary as JSON response
    return jsonify({"summary": summary})


@app.route("/quiz", methods=["POST"])
def quiz():
    """
    Generate quiz questions and answers for the uploaded PDF document.
    
    Endpoint: POST /quiz
    
    Request Body (JSON):
        {
            "base64": "<base64_encoded_pdf_content>"
        }
        
    Response (JSON):
        {
            "questions": "<formatted_quiz_questions>",
            "answers": "<formatted_quiz_answers>"
        }
        
    Process:
        1. Extract base64 PDF from request
        2. Call get_quiz() function (returns questions and answers)
        3. Return both as JSON response
    """
    # Step 1: Extract JSON data from request
    data = request.json
    
    # Step 2: Generate quiz questions and answers
    questions, answers = get_quiz(data["base64"])
    
    # Step 3: Return both questions and answers as JSON response
    return jsonify({"questions": questions, "answers": answers})
    #for the cover of the book
@app.route("/cover", methods=["POST"])
def cover():
    data = request.json
    img  = get_cover(data["base64"])
    return jsonify({"cover": img})

# ══════════════════════════════════════════
#  SERVER STARTUP
# ══════════════════════════════════════════

if __name__ == "__main__":
    """
    Start the Flask development server.
    
    This block runs only when the script is executed directly
    (not when imported as a module).
    
    
    Server Configuration:
        - Port: 5000 (standard Flask development port)
        - Debug: True (enables auto-reload and detailed error pages)
        - Host: localhost (default)
        
    Access URLs:
        - http://localhost:5000/describe
        - http://localhost:5000/summarize  
        - http://localhost:5000/quiz
    """
    # Start the Flask development server
    app.run(port=5000, debug=True)