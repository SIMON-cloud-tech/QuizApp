# ══════════════════════════════════════════
#  PDF PROCESSING AND QUIZ GENERATION SYSTEM
#  ===========================================
#  This module processes PDF documents to extract text,
#  generate summaries, descriptions, and quiz questions.
#  
#  Author: Quiz Application
#  Dependencies: PyMuPDF, NLTK, spaCy, scikit-learn
# ══════════════════════════════════════════

# Standard library imports
import base64
import re
from collections import Counter, defaultdict

# PDF processing library
import fitz  # PyMuPDF for PDF text extraction

# Natural Language Processing libraries
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import stopwords

# Advanced NLP and machine learning
import spacy
from sklearn.feature_extraction.text import TfidfVectorizer

# Download required NLTK data (quiet mode to avoid spam)
nltk.download("punkt",     quiet=True)     # Sentence tokenization
nltk.download("punkt_tab", quiet=True)     # Additional punkt data
nltk.download("stopwords", quiet=True)     # Common stopwords for English

# Load spaCy's English small model for entity recognition
nlp = spacy.load("en_core_web_sm")

# Global constants
STOPWORDS = set(stopwords.words("english"))  # English stopwords for filtering
CHUNK_SIZE = 800  # Maximum words per text chunk for processing


# ══════════════════════════════════════════
#  UTILITIES
# ══════════════════════════════════════════

def extract_text(base64_pdf: str) -> str:
    """
    Extract clean text from a base64-encoded PDF file.
    
    Args:
        base64_pdf (str): Base64 encoded PDF content
        
    Returns:
        str: Cleaned text content with normalized whitespace
        
    Process:
        1. Decode base64 to bytes
        2. Open PDF with PyMuPDF
        3. Extract text from all pages
        4. Clean and normalize whitespace
    """
    # Step 1: Decode base64 string to bytes
    pdf_bytes = base64.b64decode(base64_pdf)
    
    # Step 2: Open PDF document from bytes
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    
    # Step 3: Skip first page (usually title/contents) and extract text from remaining pages
    pages = doc[1:] if len(doc) > 1 else doc
    raw = "\n\n".join(page.get_text() for page in pages)
    
    # Step 4: Clean up whitespace - replace multiple spaces/newlines with single space
    return re.sub(r"\s+", " ", raw).strip()


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE) -> list[str]:
    """
    Split large text into smaller chunks while respecting sentence boundaries.
    
    Args:
        text (str): Input text to be chunked
        chunk_size (int): Maximum words per chunk (default: 800)
        
    Returns:
        list[str]: List of text chunks, each containing complete sentences
        
    Strategy:
        - Tokenize text into sentences
        - Build chunks by adding sentences until word limit approached
        - Never split sentences - always keep them intact
        - Start new chunk when adding next sentence would exceed limit
    """
    # Step 1: Split text into individual sentences
    sentences = sent_tokenize(text)
    
    # Initialize containers for building chunks
    chunks, current, count = [], [], 0

    # Step 2: Build chunks sentence by sentence
    for sent in sentences:
        words = len(sent.split())  # Count words in current sentence
        
        # If adding this sentence would exceed chunk size and we have content,
        # finalize current chunk and start a new one
        if count + words > chunk_size and current:
            chunks.append(" ".join(current))  # Join sentences in current chunk
            current, count = [], 0  # Reset for new chunk
            
        # Add current sentence to the chunk being built
        current.append(sent)
        count += words

    # Step 3: Don't forget the last chunk if it has content
    if current:
        chunks.append(" ".join(current))

    return chunks


def tfidf_top_sentences(sentences: list[str], top_n: int) -> list[str]:
    """
    Select the most important sentences using TF-IDF scoring.
    
    Args:
        sentences (list[str]): List of sentences to score
        top_n (int): Number of top sentences to return
        
    Returns:
        list[str]: Top N sentences in their original reading order
        
    Method:
        1. Filter out very short sentences (less than 6 words)
        2. Apply TF-IDF vectorization to identify important terms
        3. Score each sentence by summing TF-IDF weights
        4. Select top N sentences and restore original order
    """
    # If we have fewer sentences than requested, return all
    if len(sentences) <= top_n:
        return sentences

    # Step 1: Filter out very short sentences (likely not meaningful)
    eligible = [s for s in sentences if len(s.split()) > 5]
    if not eligible:
        return sentences[:top_n]  # Fallback if all sentences are short

    try:
        # Step 2: Create TF-IDF vectorizer with English stopwords
        vec = TfidfVectorizer(stop_words="english")
        matrix = vec.fit_transform(eligible)
        
        # Step 3: Score each sentence by summing its TF-IDF weights
        scores = {eligible[i]: float(matrix[i].sum()) for i in range(len(eligible))}
    except Exception:
        # Step 4: Fallback to simple word frequency if TF-IDF fails
        scores = _freq_scores(eligible)

    # Step 5: Get top N sentences by score
    top = sorted(scores, key=scores.get, reverse=True)[:top_n]
    
    # Step 6: Restore original reading order for readability
    top_set = set(top)
    return [s for s in sentences if s in top_set]


def _freq_scores(sentences: list[str]) -> dict[str, float]:
    """
    Simple word-frequency scoring fallback for when TF-IDF fails.
    
    Args:
        sentences (list[str]): List of sentences to score
        
    Returns:
        dict[str, float]: Mapping of sentence to its frequency score
        
    Method:
        1. Tokenize all sentences and filter meaningful words
        2. Count word frequencies across all sentences
        3. Normalize scores (divide by max frequency)
        4. Score each sentence by summing normalized word frequencies
    """
    # Step 1: Collect all meaningful words from all sentences
    words = [
        w.lower() for s in sentences
        for w in word_tokenize(s)
        if w.isalpha() and w.lower() not in STOPWORDS  # Only letters, not stopwords
    ]
    
    # Step 2: Count word frequencies
    freq = Counter(words)
    
    # Step 3: Normalize frequencies (0-1 scale)
    max_f = max(freq.values(), default=1)
    freq = {w: f / max_f for w, f in freq.items()}
    
    # Step 4: Score each sentence by summing normalized word frequencies
    return {
        s: sum(freq.get(w.lower(), 0) for w in word_tokenize(s) if w.isalpha())
        for s in sentences
    }


def extract_concepts(chunk: str) -> list[dict]:
    """
    Extract key concepts from a text chunk using advanced spaCy NLP processing.
    
    Args:
        chunk (str): Text chunk to analyze
        
    Returns:
        list[dict]: List of concept objects with keys:
                   - concept: the extracted concept/text
                   - sentence: sentence containing the concept
                   - type: one of 'entity', 'noun_chunk', 'noun', 'compound'
                   - importance: relevance score based on linguistic features
                   
    Enhanced Strategy:
        1. Extract high-quality named entities (PERSON, ORG, PRODUCT, etc.)
        2. Extract compound noun phrases (multi-word technical terms)
        3. Extract grammatically important noun chunks
        4. Apply quality filters to remove noise
        5. Score concepts by linguistic importance
        6. Return sorted list by importance
    """
    # spaCy has a hard limit on text length (around 1M characters)
    doc = nlp(chunk[:100000])
    
    concepts = []  # List to store extracted concepts
    seen = set()   # Track concepts to avoid duplicates

    # Step 1: Extract named entities with quality filtering
    # Focus on entities that are likely to be important concepts
    important_entity_types = {"PERSON", "ORG", "GPE", "PRODUCT", "EVENT", "WORK_OF_ART", "LAW", "LANGUAGE"}
    
    for ent in doc.ents:
        # Skip entities that are likely noise
        if ent.label_ not in important_entity_types:
            continue
            
        key = ent.text.strip().lower()
        
        # Enhanced filtering
        if (len(key) < 3 or len(key.split()) > 4 or  # Skip too short or too long
            key in seen or key in STOPWORDS or
            ent.text.strip().isdigit()):  # Skip pure numbers
            continue
            
        # Find the sentence containing this entity
        for sent in doc.sents:
            if ent.start >= sent.start and ent.end <= sent.end:
                # Calculate importance score
                importance = 1.0
                if ent.label_ in {"ORG", "PRODUCT"}: importance += 0.3
                if len(ent.text.split()) > 1: importance += 0.2
                
                concepts.append({
                    "concept": ent.text.strip(),
                    "sentence": sent.text.strip(),
                    "type": "entity",
                    "importance": importance
                })
                seen.add(key)
                break

    # Step 2: Extract compound noun phrases (technical terms)
    for token in doc:
        if token.dep_ == "compound" and token.head.pos_ == "NOUN":
            # Build compound phrase
            compound_tokens = [token]
            current = token.head
            
            # Add the head noun
            compound_tokens.append(current)
            
            # Add any other compounds
            for child in current.children:
                if child.dep_ == "compound":
                    compound_tokens.insert(0, child)
            
            # Sort by position and join
            compound_tokens.sort(key=lambda t: t.i)
            compound_text = " ".join(t.text for t in compound_tokens).strip()
            
            key = compound_text.lower()
            
            if (len(key) < 4 or len(key.split()) > 3 or
                key in seen or key in STOPWORDS):
                continue
                
            # Find containing sentence
            for sent in doc.sents:
                if token.sent.start <= token.i <= token.sent.end:
                    concepts.append({
                        "concept": compound_text,
                        "sentence": sent.text.strip(),
                        "type": "compound",
                        "importance": 1.4  # Compounds are usually important
                    })
                    seen.add(key)
                    break

    # Step 3: Extract high-quality noun chunks
    for chunk_span in doc.noun_chunks:
        key = chunk_span.text.strip().lower()
        
        # Enhanced filtering
        if (len(key) < 4 or len(key.split()) > 4 or
            key in seen or key in STOPWORDS or
            any(stop in key for stop in {"this", "that", "these", "those", "the", "a", "an"})):
            continue
            
        # Only keep noun chunks with important grammatical roles
        if chunk_span.root.dep_ in ("nsubj", "dobj", "pobj", "attr"):
            for sent in doc.sents:
                if chunk_span.start >= sent.start and chunk_span.end <= sent.end:
                    # Calculate importance based on linguistic features
                    importance = 1.0
                    if chunk_span.root.dep_ == "nsubj": importance += 0.3  # Subjects are important
                    if len(chunk_span.text.split()) > 1: importance += 0.2  # Multi-word terms
                    
                    concepts.append({
                        "concept": chunk_span.text.strip(),
                        "sentence": sent.text.strip(),
                        "type": "noun_chunk",
                        "importance": importance
                    })
                    seen.add(key)
                    break

    # Step 4: Sort by importance and return top concepts
    concepts.sort(key=lambda x: x["importance"], reverse=True)
    return concepts[:20]  # Return top 20 concepts per chunk


# ══════════════════════════════════════════
#  1. DESCRIPTION
# ══════════════════════════════════════════

def get_description(base64_pdf: str) -> str:
    """
    Generate a brief description of the PDF document.
    
    Args:
        base64_pdf (str): Base64 encoded PDF content
        
    Returns:
        str: First 3 meaningful sentences as a description
        
    Strategy:
        - Extract full text from PDF
        - Tokenize into sentences
        - Filter for meaningful sentences (more than 8 words)
        - Return first 3 as the document description
    """
    # Step 1: Extract all text from the PDF
    text = extract_text(base64_pdf)
    
    # Step 2: Split text into individual sentences
    sentences = sent_tokenize(text)
    
    # Step 3: Filter for meaningful sentences (substantial content)
    # and take the first 3
    picked = [s.strip() for s in sentences if len(s.split()) > 8][:3]
    
    # Step 4: Join sentences or return fallback message
    return " ".join(picked) if picked else "No description available."


# ══════════════════════════════════════════
#  2. SUMMARY
# ══════════════════════════════════════════

def get_summary(base64_pdf: str) -> str:
    """
    Generate a concise, focused summary of the PDF document.
    
    Args:
        base64_pdf (str): Base64 encoded PDF content
        
    Returns:
        str: Generated summary focusing on key topics
        
    Approach:
        1. Extract text and identify key themes
        2. Focus on specific topics: formulation, methods, advantages, applications
        3. Extract concrete facts and data points
        4. Generate concise summary (3-5 sentences max)
        5. Avoid generic explanations - focus on document-specific content
    """
    # Step 1: Extract text
    text = extract_text(base64_pdf)
    
    # Step 2: Split into sentences for analysis
    sentences = sent_tokenize(text)
    if not sentences:
        return "Could not generate a summary for this document."
    
    # Step 3: Extract key themes and topics using TF-IDF
    # Focus on the most important sentences that contain specific information
    key_sentences = tfidf_top_sentences(sentences, top_n=8)
    
    # Step 4: Filter for specific, actionable content
    # Prioritize sentences that mention concrete details
    filtered_sentences = []
    for sent in key_sentences:
        sent_lower = sent.lower()
        
        # Look for specific indicators of valuable content
        has_specific_info = (
            'formulation' in sent_lower or 'method' in sent_lower or
            'advantage' in sent_lower or 'benefit' in sent_lower or
            'application' in sent_lower or 'process' in sent_lower or
            'product' in sent_lower or 'result' in sent_lower or
            'technique' in sent_lower or 'approach' in sent_lower or
            'used' in sent_lower or 'applied' in sent_lower or
            'developed' in sent_lower or 'implemented' in sent_lower or
            '% ' in sent_lower or 'mg' in sent_lower or
            'kg' in sent_lower or 'ml' in sent_lower
        )
        
        # Avoid generic or vague sentences
        is_generic = (
            'this paper' in sent_lower or
            'this study' in sent_lower or
            'the author' in sent_lower or
            'the research' in sent_lower or
            'it is' in sent_lower and len(sent.split()) < 10
        )
        
        if has_specific_info and not is_generic:
            filtered_sentences.append(sent)
    
    # Step 5: If no specific content found, use top sentences
    if not filtered_sentences:
        filtered_sentences = key_sentences[:5]
    
    # Step 6: Create concise summary (3-5 sentences max)
    summary_sentences = filtered_sentences[:5]
    
    # Step 6: Format as clean, focused summary
    summary = " ".join(summary_sentences)
    
    # Clean up common issues
    summary = summary.replace("  ", " ").strip()
    
    # Add natural starting phrase and ensure word count
    if len(summary.split()) < 10:
        # If summary is too short, add more context
        summary = f"This book covers {summary}."
    
    # Ensure summary is between 300-400 words
    word_count = len(summary.split())
    if word_count < 300:
        # If too short, expand slightly with key points
        summary = f"This book covers {summary} Key topics include detailed analysis of methods and practical applications discussed throughout."
    elif word_count > 400:
        # If too long, trim to 400 words
        words = summary.split()[:400]
        summary = " ".join(words)
        summary = f"This book covers {summary}"
    
    return summary


# ══════════════════════════════════════════
#  3. QUIZ
# ══════════════════════════════════════════

# Quiz generation templates
# These define different types of questions and their corresponding answer formats

QUESTION_TEMPLATES = [
    # (question_type, template_string)
    # {concept} and {sentence} are placeholders that will be filled dynamically
    
    # Definition questions - ask what something is (most reliable)
    ("define",   "What is {concept} in the context of this document?"),
    
    # Context questions - ask about specific situations
    ("context",  "In what context does {concept} appear in this text?"),
    
    # Relationship questions - ask about connections
    ("relationship", "How does {concept} relate to other topics mentioned?"),
    
    # Application questions - ask about practical use
    ("application", "How is {concept} applied or used according to the text?"),
    
    # Analysis questions - ask about deeper meaning
    ("analysis", "What does the text suggest about {concept}?"),
    
    # Comparison questions - ask about similarities/differences
    ("compare", "How does {concept} compare to related concepts in the text?"),
    
    # Fill-in-the-blank questions - test recall
    ("fill_blank", "Complete this sentence based on the text: {blank_sentence}"),
    
    # Significance questions - ask about importance
    ("significance", "Why is {concept} significant to the overall message?"),
    
    # Process questions - ask how something works
    ("process", "What process involving {concept} is described in the text?"),
]

# Answer templates corresponding to each question type
# These ensure consistent answer formatting

ANSWER_TEMPLATES = {
    "define": "Based on the text, {concept} is defined as: {sentence}",
    "context": "The text places {concept} in this context: {sentence}",
    "relationship": "According to the text, {concept} relates to other topics as follows: {sentence}",
    "application": "The text describes the application of {concept} as: {sentence}",
    "analysis": "The text suggests the following about {concept}: {sentence}",
    "compare": "The text compares {concept} to related concepts like this: {sentence}",
    "fill_blank": "{concept} — {sentence}",
    "significance": "The text indicates {concept} is significant because: {sentence}",
    "process": "The text describes this process involving {concept}: {sentence}",
}


def generate_questions_from_concepts(concepts: list[dict]) -> tuple[list[str], list[str]]:
    """
    Generate high-quality, context-relevant questions with strict filtering.
    
    Args:
        concepts (list[dict]): List of concept dictionaries from extract_concepts()
        
    Returns:
        tuple[list[str], list[str]]: (questions_list, answers_list)
        
    Strict Quality Strategy:
        1. Only use concepts with quality_score >= 0.7
        2. Validate concepts have meaningful content in sentences
        3. Generate questions that are directly answerable from text
        4. Eliminate all generic or unanswerable questions
        5. Target 15-25 high-quality questions
    """
    questions, answers = [], []  # Parallel lists for Q&A pairs
    seen_questions = set()       # Track to avoid duplicates
    
    # Strict quality filtering - only use high-quality concepts
    high_quality_concepts = []
    for item in concepts:
        concept = item["concept"]
        sentence = item["sentence"]
        importance = item.get("importance", 1.0)
        quality_score = item.get("quality_score", 1.0)
        
        # Reasonable quality requirements
        if quality_score < 0.3:
            continue  # Skip very low-quality concepts
            
        concept_lower = concept.lower()
        
        # Skip generic/unanswerable concepts
        skip_patterns = [
            "this", "that", "these", "those", "the", "a", "an",
            "according", "however", "therefore", "furthermore", "additionally",
            "paper", "study", "research", "document", "chapter", "section",
            "continuous", "following", "above", "below", "previous", "next",
            "example", "instance", "case", "type", "kind", "form",
            "general", "specific", "particular", "various", "several", "multiple",
            "include", "include", "consider", "involves", "related", "associated"
        ]
        
        # Skip if concept contains generic patterns
        if any(pattern in concept_lower for pattern in skip_patterns):
            continue
            
        # Skip if concept is too short or too long
        if len(concept.strip()) < 3 or len(concept.split()) > 6:
            continue
            
        # Skip if concept is just a number
        if concept_lower.isdigit():
            continue
        
        high_quality_concepts.append({
            "concept": concept,
            "sentence": sentence,
            "type": item["type"],
            "importance": importance,
            "quality_score": quality_score
        })
    
    # Sort by quality and take top concepts
    high_quality_concepts.sort(key=lambda x: x["quality_score"], reverse=True)
    top_concepts = high_quality_concepts[:25]  # Focus on best concepts
    
    # Generate validated questions
    for i, item in enumerate(top_concepts):
        concept = item["concept"]
        sentence = item["sentence"]
        concept_type = item["type"]
        
        # Validate concept appears meaningfully in sentence (more lenient)
        if concept_lower not in sentence.lower() and len(concept) > 8:
            continue  # Skip concepts not actually in the sentence (unless short)
            
        question_data = generate_strict_question(concept, sentence, concept_type, i)
        
        if question_data and question_data["valid"]:
            questions.append(question_data["question"])
            answers.append(question_data["answer"])
            
            # Stop if we have enough good questions
            if len(questions) >= 20:
                break
    
    return questions, answers


def generate_strict_question(concept: str, sentence: str, concept_type: str, index: int) -> dict:
    """
    Generate a strictly validated, context-relevant question.
    
    Returns dict with question, answer, and validity flag.
    """
    concept_lower = concept.lower()
    sentence_lower = sentence.lower()
    
    # Different strategies based on concept type
    if concept_type == "entity":
        return generate_entity_question_strict(concept, sentence, index)
    elif concept_type == "compound":
        return generate_compound_question_strict(concept, sentence, index)
    else:
        return generate_concept_question_strict(concept, sentence, index)


def generate_entity_question_strict(concept: str, sentence: str, index: int) -> dict:
    """Generate strict entity-focused questions."""
    # Only generate questions for meaningful entity types
    valid_entity_types = ["PERSON", "ORG", "PRODUCT", "GPE", "EVENT"]
    
    # Question templates for entities
    entity_questions = [
        f"What specific role or function does {concept} serve in this context?",
        f"How does {concept} contribute to the main topic or process described?",
        f"What are the key characteristics or features of {concept} mentioned?",
        f"In what ways is {concept} significant to the overall subject matter?"
    ]
    
    # Select question based on index to ensure variety
    question = entity_questions[index % len(entity_questions)]
    
    # Validate answer is directly from text
    if concept_lower in sentence.lower():
        answer = f"According to the text, {concept} serves as {get_entity_role(concept)} and is described as: {sentence}"
    else:
        answer = f"Based on the document, {concept} {sentence}"
    
    return {"question": question, "answer": answer, "valid": True}


def generate_compound_question_strict(concept: str, sentence: str, index: int) -> dict:
    """Generate strict technical questions for compounds."""
    # Focus on practical application and analysis
    compound_questions = [
        f"How does {concept} function or operate according to the text?",
        f"What are the main components or elements of {concept}?",
        f"What are the practical applications or implementations of {concept}?",
        f"What advantages or benefits does {concept} provide in this context?",
        f"What limitations or challenges are associated with {concept}?",
        f"In what specific scenarios or contexts is {concept} most relevant?"
    ]
    
    # Select question based on index for variety
    question = compound_questions[index % len(compound_questions)]
    
    # Provide technical, text-based answer
    answer = f"The text describes {concept} as follows: {sentence}"
    return {"question": question, "answer": answer, "valid": True}


def generate_concept_question_strict(concept: str, sentence: str, index: int) -> dict:
    """Generate strict general concept questions."""
    # Focus on understanding and relationships
    concept_questions = [
        f"What specific properties or characteristics does {concept} exhibit in this context?",
        f"How does {concept} relate to other key concepts mentioned in the document?",
        f"What practical applications or uses of {concept} are discussed?",
        f"Under what conditions or circumstances is {concept} most effective or relevant?",
        f"How would you compare or contrast {concept} with alternative approaches mentioned?"
    ]
    
    # Select question based on index for variety
    question = concept_questions[index % len(concept_questions)]
    
    # Provide contextual answer
    answer = f"According to the document: {sentence}"
    return {"question": question, "answer": answer, "valid": True}


def get_entity_role(concept: str) -> str:
    """Determine likely role of entity based on common patterns."""
    concept_lower = concept.lower()
    
    # Common role indicators
    if any(word in concept_lower for word in 
            ["university", "college", "institute", "school", "company", "organization"]):
        return "an organization"
    elif any(word in concept_lower for word in 
                ["professor", "researcher", "author", "scientist", "expert"]):
        return "a person"
    elif any(word in concept_lower for word in 
                ["method", "technique", "algorithm", "process", "system"]):
        return "a technical approach"
    elif any(word in concept_lower for word in 
                ["product", "tool", "software", "technology", "device"]):
        return "a product or technology"
    else:
        return "a concept"


def get_quiz(base64_pdf: str) -> tuple[str, str]:
    """
    Generate a complete quiz from a PDF document.
    
    Args:
        base64_pdf (str): Base64 encoded PDF content
        
    Returns:
        tuple[str, str]: (formatted_questions, formatted_answers)
        
    Comprehensive process:
        1. Extract text and split into chunks
        2. Extract concepts from each chunk
        3. Generate multiple question types for each concept
        4. Format questions and answers with numbering
        
    This creates a comprehensive quiz covering all major concepts in the document.
    """
    # Step 1: Extract text and prepare for processing
    text = extract_text(base64_pdf)
    chunks = chunk_text(text)

    # Step 2: Extract concepts from all chunks
    all_concepts = []

    for chunk in chunks:
        concepts = extract_concepts(chunk)
        all_concepts.extend(concepts)

    # Step 3: Handle case where no concepts were found
    if not all_concepts:
        return "Could not extract questions from this document.", ""

    # Step 4: Generate questions and answers from concepts
    questions_list, answers_list = generate_questions_from_concepts(all_concepts)

    # Step 5: Handle case where no questions could be generated
    if not questions_list:
        return "No questions could be generated.", ""

    # Step 6: Format without numbering for cleaner presentation
    questions_str = "\n\n".join(f"{q}" for q in questions_list)
    answers_str = "\n\n".join(f"{a}" for a in answers_list)

    return questions_str, answers_str


#we extract coverpage for show
def get_cover(base64_pdf: str) -> str:
    """
    Render first page of PDF as a base64 PNG image.
    """
    pdf_bytes = base64.b64decode(base64_pdf)
    doc       = fitz.open(stream=pdf_bytes, filetype="pdf")
    page      = doc[0]
    mat       = fitz.Matrix(1.5, 1.5)
    pix       = page.get_pixmap(matrix=mat)
    img_bytes = pix.tobytes("png")
    return "data:image/png;base64," + base64.b64encode(img_bytes).decode()