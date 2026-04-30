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
nltk.download("punkt",     quiet=True)
nltk.download("punkt_tab", quiet=True)
nltk.download("stopwords", quiet=True)

# Load spaCy's English small model for entity recognition
nlp = spacy.load("en_core_web_sm")

# Global constants
STOPWORDS = set(stopwords.words("english"))
CHUNK_SIZE = 800


# ══════════════════════════════════════════
#  UTILITIES
# ══════════════════════════════════════════

def extract_text(base64_pdf: str) -> str:
    pdf_bytes = base64.b64decode(base64_pdf)
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = doc[1:] if len(doc) > 1 else doc
    raw = "\n\n".join(page.get_text() for page in pages)
    return re.sub(r"\s+", " ", raw).strip()


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE) -> list[str]:
    sentences = sent_tokenize(text)
    chunks, current, count = [], [], 0
    for sent in sentences:
        words = len(sent.split())
        if count + words > chunk_size and current:
            chunks.append(" ".join(current))
            current, count = [], 0
        current.append(sent)
        count += words
    if current:
        chunks.append(" ".join(current))
    return chunks


def tfidf_top_sentences(sentences: list[str], top_n: int) -> list[str]:
    if len(sentences) <= top_n:
        return sentences
    eligible = [s for s in sentences if len(s.split()) > 5]
    if not eligible:
        return sentences[:top_n]
    try:
        vec = TfidfVectorizer(stop_words="english")
        matrix = vec.fit_transform(eligible)
        scores = {eligible[i]: float(matrix[i].sum()) for i in range(len(eligible))}
    except Exception:
        scores = _freq_scores(eligible)
    top = sorted(scores, key=scores.get, reverse=True)[:top_n]
    top_set = set(top)
    return [s for s in sentences if s in top_set]


def _freq_scores(sentences: list[str]) -> dict[str, float]:
    words = [
        w.lower() for s in sentences
        for w in word_tokenize(s)
        if w.isalpha() and w.lower() not in STOPWORDS
    ]
    freq = Counter(words)
    max_f = max(freq.values(), default=1)
    freq = {w: f / max_f for w, f in freq.items()}
    return {
        s: sum(freq.get(w.lower(), 0) for w in word_tokenize(s) if w.isalpha())
        for s in sentences
    }


def extract_concepts(chunk: str) -> list[dict]:
    doc = nlp(chunk[:100000])
    concepts = []
    seen = set()

    important_entity_types = {"PERSON", "ORG", "GPE", "PRODUCT", "EVENT", "WORK_OF_ART", "LAW", "LANGUAGE"}

    for ent in doc.ents:
        if ent.label_ not in important_entity_types:
            continue
        key = ent.text.strip().lower()
        if (len(key) < 3 or len(key.split()) > 4 or
                key in seen or key in STOPWORDS or
                ent.text.strip().isdigit()):
            continue
        for sent in doc.sents:
            if ent.start >= sent.start and ent.end <= sent.end:
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

    for token in doc:
        if token.dep_ == "compound" and token.head.pos_ == "NOUN":
            compound_tokens = [token, token.head]
            for child in token.head.children:
                if child.dep_ == "compound":
                    compound_tokens.insert(0, child)
            compound_tokens.sort(key=lambda t: t.i)
            compound_text = " ".join(t.text for t in compound_tokens).strip()
            key = compound_text.lower()
            if (len(key) < 4 or len(key.split()) > 3 or
                    key in seen or key in STOPWORDS):
                continue
            for sent in doc.sents:
                if token.sent.start <= token.i <= token.sent.end:
                    concepts.append({
                        "concept": compound_text,
                        "sentence": sent.text.strip(),
                        "type": "compound",
                        "importance": 1.4
                    })
                    seen.add(key)
                    break

    for chunk_span in doc.noun_chunks:
        key = chunk_span.text.strip().lower()
        if (len(key) < 4 or len(key.split()) > 4 or
                key in seen or key in STOPWORDS or
                any(stop in key for stop in {"this", "that", "these", "those", "the", "a", "an"})):
            continue
        if chunk_span.root.dep_ in ("nsubj", "dobj", "pobj", "attr"):
            for sent in doc.sents:
                if chunk_span.start >= sent.start and chunk_span.end <= sent.end:
                    importance = 1.0
                    if chunk_span.root.dep_ == "nsubj": importance += 0.3
                    if len(chunk_span.text.split()) > 1: importance += 0.2
                    concepts.append({
                        "concept": chunk_span.text.strip(),
                        "sentence": sent.text.strip(),
                        "type": "noun_chunk",
                        "importance": importance
                    })
                    seen.add(key)
                    break

    concepts.sort(key=lambda x: x["importance"], reverse=True)
    return concepts[:20]


# ══════════════════════════════════════════
#  1. DESCRIPTION
# ══════════════════════════════════════════

def get_description(base64_pdf: str) -> str:
    text = extract_text(base64_pdf)
    sentences = sent_tokenize(text)
    picked = [s.strip() for s in sentences if len(s.split()) > 8][:3]
    return " ".join(picked) if picked else "No description available."


# ══════════════════════════════════════════
#  2. SUMMARY
# ══════════════════════════════════════════

def get_summary(base64_pdf: str) -> str:
    text = extract_text(base64_pdf)
    sentences = sent_tokenize(text)
    if not sentences:
        return "Could not generate a summary for this document."

    key_sentences = tfidf_top_sentences(sentences, top_n=8)

    filtered_sentences = []
    for sent in key_sentences:
        sent_lower = sent.lower()
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
        is_generic = (
            'this paper' in sent_lower or
            'this study' in sent_lower or
            'the author' in sent_lower or
            'the research' in sent_lower or
            'it is' in sent_lower and len(sent.split()) < 10
        )
        if has_specific_info and not is_generic:
            filtered_sentences.append(sent)

    if not filtered_sentences:
        filtered_sentences = key_sentences[:5]

    summary_sentences = filtered_sentences[:5]
    summary = " ".join(summary_sentences).replace("  ", " ").strip()

    word_count = len(summary.split())
    if word_count < 300:
        summary = f"This document covers {summary} Key topics include detailed analysis of methods and practical applications discussed throughout."
    elif word_count > 400:
        summary = " ".join(summary.split()[:400])

    return summary


# ══════════════════════════════════════════
#  3. QUIZ
# ══════════════════════════════════════════

QUESTION_TEMPLATES = [
    ("define",        "What is {concept} in the context of this document?"),
    ("context",       "In what context does {concept} appear in this text?"),
    ("relationship",  "How does {concept} relate to other topics mentioned?"),
    ("application",   "How is {concept} applied or used according to the text?"),
    ("analysis",      "What does the text suggest about {concept}?"),
    ("compare",       "How does {concept} compare to related concepts in the text?"),
    ("fill_blank",    "Complete this sentence based on the text: {blank_sentence}"),
    ("significance",  "Why is {concept} significant to the overall message?"),
    ("process",       "What process involving {concept} is described in the text?"),
]

ANSWER_TEMPLATES = {
    "define":       "Based on the text, {concept} is defined as: {sentence}",
    "context":      "The text places {concept} in this context: {sentence}",
    "relationship": "According to the text, {concept} relates to other topics as follows: {sentence}",
    "application":  "The text describes the application of {concept} as: {sentence}",
    "analysis":     "The text suggests the following about {concept}: {sentence}",
    "compare":      "The text compares {concept} to related concepts like this: {sentence}",
    "fill_blank":   "{concept} — {sentence}",
    "significance": "The text indicates {concept} is significant because: {sentence}",
    "process":      "The text describes this process involving {concept}: {sentence}",
}


def generate_questions_from_concepts(concepts: list[dict]) -> tuple[list[str], list[str]]:
    questions, answers = [], []
    seen_questions = set()

    high_quality_concepts = []
    for item in concepts:
        concept = item["concept"]
        sentence = item["sentence"]
        importance = item.get("importance", 1.0)
        quality_score = item.get("quality_score", 1.0)

        if quality_score < 0.3:
            continue

        concept_lower = concept.lower()
        skip_patterns = [
            "this", "that", "these", "those", "the", "a", "an",
            "according", "however", "therefore", "furthermore", "additionally",
            "paper", "study", "research", "document", "chapter", "section",
            "continuous", "following", "above", "below", "previous", "next",
            "example", "instance", "case", "type", "kind", "form",
            "general", "specific", "particular", "various", "several", "multiple",
        ]

        if any(pattern in concept_lower for pattern in skip_patterns):
            continue
        if len(concept.strip()) < 3 or len(concept.split()) > 6:
            continue
        if concept_lower.isdigit():
            continue

        high_quality_concepts.append({
            "concept": concept,
            "sentence": sentence,
            "type": item["type"],
            "importance": importance,
            "quality_score": quality_score
        })

    high_quality_concepts.sort(key=lambda x: x["quality_score"], reverse=True)
    top_concepts = high_quality_concepts[:25]

    for i, item in enumerate(top_concepts):
        concept = item["concept"]
        sentence = item["sentence"]
        concept_type = item["type"]
        concept_lower = concept.lower()

        if concept_lower not in sentence.lower() and len(concept) > 8:
            continue

        question_data = generate_strict_question(concept, sentence, concept_type, i)

        if question_data and question_data["valid"]:
            questions.append(question_data["question"])
            answers.append(question_data["answer"])
            if len(questions) >= 20:
                break

    return questions, answers


def generate_strict_question(concept: str, sentence: str, concept_type: str, index: int) -> dict:
    if concept_type == "entity":
        return generate_entity_question_strict(concept, sentence, index)
    elif concept_type == "compound":
        return generate_compound_question_strict(concept, sentence, index)
    else:
        return generate_concept_question_strict(concept, sentence, index)


def generate_entity_question_strict(concept: str, sentence: str, index: int) -> dict:
    entity_questions = [
        f"What specific role or function does {concept} serve in this context?",
        f"How does {concept} contribute to the main topic or process described?",
        f"What are the key characteristics or features of {concept} mentioned?",
        f"In what ways is {concept} significant to the overall subject matter?"
    ]
    question = entity_questions[index % len(entity_questions)]
    concept_lower = concept.lower()
    if concept_lower in sentence.lower():
        answer = f"According to the text, {concept} serves as {get_entity_role(concept)} and is described as: {sentence}"
    else:
        answer = f"Based on the document, {concept} {sentence}"
    return {"question": question, "answer": answer, "valid": True}


def generate_compound_question_strict(concept: str, sentence: str, index: int) -> dict:
    compound_questions = [
        f"How does {concept} function or operate according to the text?",
        f"What are the main components or elements of {concept}?",
        f"What are the practical applications or implementations of {concept}?",
        f"What advantages or benefits does {concept} provide in this context?",
        f"What limitations or challenges are associated with {concept}?",
        f"In what specific scenarios or contexts is {concept} most relevant?"
    ]
    question = compound_questions[index % len(compound_questions)]
    answer = f"The text describes {concept} as follows: {sentence}"
    return {"question": question, "answer": answer, "valid": True}


def generate_concept_question_strict(concept: str, sentence: str, index: int) -> dict:
    concept_questions = [
        f"What specific properties or characteristics does {concept} exhibit in this context?",
        f"How does {concept} relate to other key concepts mentioned in the document?",
        f"What practical applications or uses of {concept} are discussed?",
        f"Under what conditions or circumstances is {concept} most effective or relevant?",
        f"How would you compare or contrast {concept} with alternative approaches mentioned?"
    ]
    question = concept_questions[index % len(concept_questions)]
    answer = f"According to the document: {sentence}"
    return {"question": question, "answer": answer, "valid": True}


def get_entity_role(concept: str) -> str:
    concept_lower = concept.lower()
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
    text = extract_text(base64_pdf)
    chunks = chunk_text(text)

    all_concepts = []
    for chunk in chunks:
        concepts = extract_concepts(chunk)
        all_concepts.extend(concepts)

    if not all_concepts:
        return "Could not extract questions from this document.", ""

    questions_list, answers_list = generate_questions_from_concepts(all_concepts)

    if not questions_list:
        return "No questions could be generated.", ""

    questions_str = "\n\n".join(f"{q}" for q in questions_list)
    answers_str = "\n\n".join(f"{a}" for a in answers_list)

    return questions_str, answers_str


# ══════════════════════════════════════════
#  COVER IMAGE
# ══════════════════════════════════════════

def get_cover(base64_pdf: str) -> str:
    pdf_bytes = base64.b64decode(base64_pdf)
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[0]
    mat = fitz.Matrix(1.5, 1.5)
    pix = page.get_pixmap(matrix=mat)
    img_bytes = pix.tobytes("png")
    return "data:image/png;base64," + base64.b64encode(img_bytes).decode()