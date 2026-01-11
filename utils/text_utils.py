# -*- coding: utf-8 -*-
"""
Created on Thu Jan  8 09:19:28 2026

@author: barna
"""
import re

def is_header(word):
    """
    Returns True if the word should be treated as a visual Header.
    Criteria:
    1. Must be ALL CAPS.
    2. Must NOT be 'I' or 'A' (even if surrounded by punctuation like "I, 'I, etc.)
    """
    if not word: 
        return False
    if not word.isupper():
        return False
    core_word = ''.join(filter(str.isalpha, word))
    if core_word in ["I", "A"]:
        return False
    return True

def normalize_text(text):
    if not text: return ""
    text = text.replace('--', '—')
    return re.sub(r'\s*—\s*', '— ', text)

def process_headers(words):
    """
    Consolidates header-like words (ALL CAPS or Numbers) into single strings
    to prevent the RSVP reader from flashing "CHAPTER" then "1" separately.
    """
    processed, stack = [], []
    for word in words:
        is_caps = word.isupper() and any(c.isalpha() for c in word)
        has_quote = '"' in word or "'" in word
        is_number = word.replace('.', '').isdigit() and len(stack) > 0        
        if (is_caps or is_number) and not has_quote: 
            stack.append(word)
        else:
            if stack:
                processed.append(" ".join(stack) if len(stack) <= 10 else stack[0])
                if len(stack) > 10: processed.extend(stack[1:])
                stack = []
            processed.append(word)
    if stack:
        processed.append(" ".join(stack) if len(stack) <= 10 else stack[0])
        if len(stack) > 10: processed.extend(stack[1:])
    return processed