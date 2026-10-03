"""
services/document_service.py
Robust document discovery, loading, chunking, and local relevance retrieval service
for MFG Predictive Maintenance & OEE Command Center.
"""

import os
import pathlib
import re
from typing import Dict, List, Any, Optional

# Determine project root cleanly from file location (services/document_service.py -> root)
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_MANUALS_DIR = PROJECT_ROOT / "data" / "maintenance_manuals"

EXPECTED_DOCUMENTS = [
    "Precision_Mill_Bearing_Manual.txt",
    "Coolant_System_SOP.txt",
    "Spindle_Drive_Belt_SOP.txt"
]

def get_manuals_directory() -> pathlib.Path:
    """Discovers the maintenance_manuals directory within project root."""
    if DEFAULT_MANUALS_DIR.exists() and DEFAULT_MANUALS_DIR.is_dir():
        return DEFAULT_MANUALS_DIR
    
    # Fallback recursive discovery within PROJECT_ROOT
    for root, dirs, files in os.walk(PROJECT_ROOT):
        if "maintenance_manuals" in dirs:
            found = pathlib.Path(root) / "maintenance_manuals"
            if found.is_dir():
                return found
    return DEFAULT_MANUALS_DIR


def load_single_document(file_path: pathlib.Path) -> Dict[str, Any]:
    """Loads a single document file with size, encoding, error handling, and status."""
    filename = file_path.name
    try:
        rel_path = file_path.relative_to(PROJECT_ROOT)
    except Exception:
        rel_path = file_path

    if not file_path.exists():
        return {
            "filename": filename,
            "path": str(file_path),
            "rel_path": str(rel_path),
            "size_bytes": 0,
            "size_kb": 0.0,
            "status": "NOT_FOUND",
            "error": "File does not exist on disk",
            "content": "",
            "chunks": []
        }

    try:
        size_bytes = file_path.stat().st_size
        size_kb = round(size_bytes / 1024.0, 1)
        
        # Try UTF-8 first, fallback to latin-1
        encoding_used = "UTF-8"
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except UnicodeDecodeError:
            encoding_used = "Latin-1"
            with open(file_path, "r", encoding="latin-1") as f:
                content = f.read()

        char_count = len(content)
        line_count = len(content.splitlines())

        # Split content into logical paragraphs/chunks
        lines = [line.strip() for line in content.split("\n")]
        paragraphs = []
        curr = []
        for line in lines:
            if not line:
                if curr:
                    paragraphs.append("\n".join(curr))
                    curr = []
            else:
                curr.append(line)
        if curr:
            paragraphs.append("\n".join(curr))

        # Merge short section headers or titles with their section body
        merged_paragraphs = []
        idx = 0
        while idx < len(paragraphs):
            p = paragraphs[idx]
            if len(p) < 120 and idx + 1 < len(paragraphs):
                merged_paragraphs.append(f"{p}\n{paragraphs[idx+1]}")
                idx += 2
            else:
                merged_paragraphs.append(p)
                idx += 1

        chunks = []
        for i, para in enumerate(merged_paragraphs):
            chunks.append({
                "chunk_id": f"{filename}#p{i+1}",
                "source_file": filename,
                "rel_path": str(rel_path),
                "chunk_text": para,
                "text": para
            })

        return {
            "filename": filename,
            "path": str(file_path),
            "rel_path": str(rel_path),
            "size_bytes": size_bytes,
            "size_kb": size_kb,
            "char_count": char_count,
            "line_count": line_count,
            "encoding": encoding_used,
            "status": "LOADED",
            "error": None,
            "content": content,
            "chunks": chunks
        }
    except Exception as e:
        return {
            "filename": filename,
            "path": str(file_path),
            "rel_path": str(rel_path),
            "size_bytes": 0,
            "size_kb": 0.0,
            "char_count": 0,
            "line_count": 0,
            "encoding": "Unknown",
            "status": "READ_FAILED",
            "error": str(e),
            "content": "",
            "chunks": []
        }


def load_all_documents() -> List[Dict[str, Any]]:
    """Loads all expected maintenance documents from the project manuals directory."""
    manuals_dir = get_manuals_directory()
    results = []
    
    for filename in EXPECTED_DOCUMENTS:
        file_path = manuals_dir / filename
        doc_info = load_single_document(file_path)
        results.append(doc_info)

    return results


def get_document_by_name(filename: str) -> Optional[Dict[str, Any]]:
    """Finds and loads a specific document by filename."""
    manuals_dir = get_manuals_directory()
    file_path = manuals_dir / filename
    return load_single_document(file_path)


def search_within_document(filename: str, search_term: str) -> List[Dict[str, Any]]:
    """Searches for a text term within a single document, returning matching line numbers and text."""
    doc = get_document_by_name(filename)
    if not doc or doc["status"] != "LOADED" or not search_term or not search_term.strip():
        return []

    results = []
    term_lower = search_term.lower().strip()
    lines = doc["content"].splitlines()
    for idx, line in enumerate(lines, 1):
        if term_lower in line.lower():
            results.append({
                "line_num": idx,
                "text": line
            })
    return results


def search_documents(query: str, top_k: int = 3) -> List[Dict[str, Any]]:
    """
    Performs query keyword relevance scoring over loaded document chunks.
    Returns ranked list of matching chunks with source_file, text, and score.
    """
    if not query or not query.strip():
        return []

    docs = load_all_documents()
    stopwords = {"how", "are", "you", "is", "the", "a", "an", "what", "can", "do", "it", "this", "that", "in", "on", "for", "to", "of", "and", "or", "with", "me", "tell", "about", "does", "say", "recommend", "should", "we", "what's"}
    
    # Extract query tokens
    query_words = set(re.findall(r'\b[a-zA-Z0-9_\-]+\b', query.lower())) - stopwords
    
    # Map file-specific query triggers
    doc_boosts = {}
    q_lower = query.lower()
    if "bearing" in q_lower or "mill" in q_lower or "raceway" in q_lower:
        doc_boosts["Precision_Mill_Bearing_Manual.txt"] = 3.0
    if "coolant" in q_lower or "pump" in q_lower or "fluid" in q_lower:
        doc_boosts["Coolant_System_SOP.txt"] = 3.0
    if "belt" in q_lower or "spindle drive" in q_lower or "pulley" in q_lower:
        doc_boosts["Spindle_Drive_Belt_SOP.txt"] = 3.0

    matches = []
    for doc in docs:
        if doc["status"] != "LOADED":
            continue
        
        filename = doc["filename"]
        boost = doc_boosts.get(filename, 1.0)
        
        for chunk in doc["chunks"]:
            text_lower = chunk["text"].lower()
            text_words = set(re.findall(r'\b[a-zA-Z0-9_\-]+\b', text_lower))
            
            # Match count + phrase matching
            exact_matches = sum(1 for w in query_words if w in text_words)
            if exact_matches > 0 or boost > 1.0:
                score = (exact_matches * 2.0) * boost
                matches.append({
                    "score": score,
                    "source_file": filename,
                    "rel_path": chunk["rel_path"],
                    "chunk_id": chunk["chunk_id"],
                    "chunk_text": chunk["text"]
                })

    matches.sort(key=lambda x: x["score"], reverse=True)
    return matches[:top_k]


def get_relevant_document_context(query: str) -> str:
    """Formats top matching document chunks into a clean context string for LLM prompting."""
    matches = search_documents(query, top_k=3)
    if not matches:
        return "No matching document chunks found."

    context_parts = []
    for m in matches:
        context_parts.append(f"Document Source: {m['source_file']}\n{m['chunk_text']}")

    return "\n\n---\n\n".join(context_parts)
