# ══════════════════════════════════════════
#  PDF PROCESSING AND QUIZ GENERATION SYSTEM
#  ===========================================
#  This module processes PDF documents to extract text,
#  generate summaries, descriptions, and quiz questions
#  using Google Gemini AI API.
#
#  Author: Quiz Application
#  Dependencies: PyMuPDF, google-generativeai, python-dotenv
# ══════════════════════════════════════════

import base64
import re
import os

# PDF processing library
import fitz  # PyMuPDF for PDF text extraction

# Gemini AI
import google.generativeai as genai

# Load environment variables from .env
from dotenv import load_dotenv
load_dotenv()

# Configure Gemini with API key from .env
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")

# Global constants
CHUNK_SIZE = 800  # Maximum words per text chunk


# ══════════════════════════════════════════
#  UTILITIES
# ══════════════════════════════════════════

def extract_text(base64_pdf: str) -> str:
    """
    Extract clean text from a base64-encoded PDF file.
    """
    pdf_bytes = base64.b64decode(base64_pdf)
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = doc[1:] if len(doc) > 1 else doc
    raw = "\n\n".join(page.get_text() for page in pages)
    return re.sub(r"\s+", " ", raw).strip()


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE) -> list[str]:
    """
    Split large text into smaller chunks by word count.
    """
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size):
        chunks.append(" ".join(words[i:i + chunk_size]))
    return chunks


def call_gemini(prompt: str) -> str:
    """
    Call Gemini API with a prompt and return the text response.
    """
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"Error generating response: {str(e)}"


# ══════════════════════════════════════════
#  1. DESCRIPTION
# ══════════════════════════════════════════

def get_description(base64_pdf: str) -> str:
    """
    Generate a brief description of the PDF document using Gemini.
    """
    text = extract_text(base64_pdf)

    # Use first 1500 words — enough for Gemini to understand the document
    preview = " ".join(text.split()[:1500])

    prompt = f"""You are a helpful assistant. Read the following text extracted from a PDF document and write a brief 2-3 sentence description of what the document is about. Be specific and concise.

Text:
{preview}

Description:"""

    return call_gemini(prompt)


# ══════════════════════════════════════════
#  2. SUMMARY
# ══════════════════════════════════════════

def get_summary(base64_pdf: str) -> str:
    """
    Generate a detailed summary of the PDF document using Gemini.
    """
    text = extract_text(base64_pdf)

    # Use up to 3000 words for summary — more context = better summary
    preview = " ".join(text.split()[:3000])

    prompt = f"""You are a helpful assistant. Read the following text extracted from a PDF document and write a clear, detailed summary in 150-250 words. Cover the main topics, key points, and any important findings or conclusions. Be specific to the content — avoid vague statements.

Text:
{preview}

Summary:"""

    return call_gemini(prompt)


# ══════════════════════════════════════════
#  3. QUIZ
# ══════════════════════════════════════════

def get_quiz(base64_pdf: str) -> tuple[str, str]:
    """
    Generate quiz questions and answers from the PDF using Gemini.

    Returns:
        tuple[str, str]: (formatted_questions, formatted_answers)
    """
    text = extract_text(base64_pdf)
    chunks = chunk_text(text)

    all_questions = []
    all_answers = []
    question_number = 1

    # Process each chunk and generate questions from it
    for chunk in chunks[:5]:  # Limit to first 5 chunks to stay within API limits
        prompt = f"""You are a quiz generator. Read the following text and generate 3 to 5 meaningful, specific quiz questions based on the content. 

Rules:
- Questions must be directly answerable from the text
- Avoid vague or generic questions
- Each answer must be a clear, complete sentence taken or derived from the text
- Format your response EXACTLY like this, with no extra text:

Q: [question here]
A: [answer here]

Q: [question here]
A: [answer here]

Text:
{chunk}"""

        response = call_gemini(prompt)

        # Parse the Q: A: format from Gemini's response
        pairs = re.findall(r"Q:\s*(.+?)\nA:\s*(.+?)(?=\nQ:|\Z)", response, re.DOTALL)

        for q, a in pairs:
            all_questions.append(f"{question_number}. {q.strip()}")
            all_answers.append(f"{question_number}. {a.strip()}")
            question_number += 1

        # Stop if we have enough questions
        if question_number > 20:
            break

    if not all_questions:
        return "Could not generate questions from this document.", ""

    return "\n\n".join(all_questions), "\n\n".join(all_answers)


# ══════════════════════════════════════════
#  COVER IMAGE
# ══════════════════════════════════════════

def get_cover(base64_pdf: str) -> str:
    """
    Render first page of PDF as a base64 PNG image.
    """
    pdf_bytes = base64.b64decode(base64_pdf)
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[0]
    mat = fitz.Matrix(1.5, 1.5)
    pix = page.get_pixmap(matrix=mat)
    img_bytes = pix.tobytes("png")
    return "data:image/png;base64," + base64.b64encode(img_bytes).decode()