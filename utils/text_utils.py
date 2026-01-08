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
    2. Must NOT be a standard single-letter word like 'I' or 'A' 
    """
    if not word: 
        return False
    
    # Must be uppercase
    if not word.isupper():
        return False

    if re.match(r"^[A-Z],$", word):
        return False

    # Exclude specific single-letter words that trigger false positives
    if word in ["I", "A", '"I', "'I", "(I", "(A", "A+"]:
        return False
        
    return True