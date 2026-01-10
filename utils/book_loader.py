# -*- coding: utf-8 -*-
"""
Created on Sat Jan 10 11:27:42 2026

@author: barna
"""

# utils/book_loader.py
import os
import fitz  # PyMuPDF
import zipfile
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from PyQt6.QtCore import QThread, pyqtSignal
from utils.text_utils import normalize_text, process_headers

class BookLoader(QThread):
    progress_updated = pyqtSignal(int)
    finished_loading = pyqtSignal(list, list, dict, dict)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path
        
    def run(self):
        try:
            words, chapters, page_map, footnotes = [], [], {}, {}
            if self.file_path.lower().endswith('.pdf'): 
                words, chapters, page_map, footnotes = self._load_pdf()
            elif self.file_path.lower().endswith('.epub'): 
                words, chapters, page_map = self._load_epub()
            else: 
                raise ValueError("Unsupported file format")
            
            if self.isInterruptionRequested(): return
            self.finished_loading.emit(words, chapters, page_map, footnotes)
        except Exception as e: 
            self.error_occurred.emit(str(e))
            
    def _load_pdf(self):
        words_list, chapters, current_word_count = [], [], 0
        footnotes_map = {} # { page_num: "text content" }
        
        doc = fitz.open(self.file_path)
        total_pages = len(doc)
        page_map = {} 
        
        for i, page in enumerate(doc):
            if self.isInterruptionRequested(): 
                doc.close()
                return [], [], {}, {}
                
            self.progress_updated.emit(int((i / total_pages) * 100))
            page_num = i + 1
            page_map[page_num] = current_word_count
            
            # --- FOOTNOTE DETECTION LOGIC ---
            page_dict = page.get_text("dict", flags=0)
            blocks = page_dict.get("blocks", [])
            page_height = page.rect.height
            
            # 1. Determine Body Font Size
            font_sizes = {}
            for b in blocks:
                if b['type'] != 0: continue 
                for line in b['lines']:
                    for span in line['spans']:
                        size = round(span['size'], 1)
                        weight = len(span['text'].strip())
                        if weight > 0:
                            font_sizes[size] = font_sizes.get(size, 0) + weight
            
            body_size = max(font_sizes, key=font_sizes.get) if font_sizes else 12.0
            
            main_text_blocks = []
            footnote_blocks = []
            
            for b in blocks:
                if b['type'] != 0: continue
                
                block_text = []
                block_size_sum = 0
                char_count = 0
                
                for line in b['lines']:
                    for span in line['spans']:
                        text = span['text']
                        block_text.append(text)
                        block_size_sum += span['size'] * len(text)
                        char_count += len(text)
                
                full_block_text = " ".join(block_text).strip()
                if not full_block_text: continue
                
                avg_size = (block_size_sum / char_count) if char_count > 0 else 0
                y_pos = b['bbox'][1]
                
                # Heuristics
                is_low = y_pos > (page_height * 0.60)
                is_small = avg_size < (body_size - 0.5)
                is_page_num = (y_pos > page_height * 0.93) and (len(full_block_text) < 5)

                if is_page_num:
                    continue 
                elif is_low and is_small:
                    footnote_blocks.append(full_block_text)
                else:
                    main_text_blocks.append(full_block_text)
            
            # --- STORAGE ---
            if footnote_blocks:
                footnotes_map[page_num] = "\n\n".join(footnote_blocks)

            # Assemble ONLY main text
            full_page_text = " ".join(main_text_blocks)
            full_page_text = normalize_text(full_page_text)
            
            processed_words = process_headers(full_page_text.split())
            
            words_list.extend(processed_words)
            current_word_count += len(processed_words)

        # TOC Handling
        toc = doc.get_toc()
        for item in toc:
            if len(item) >= 3:
                title = item[1]
                page_num = item[2]
                if page_num > 0 and page_num in page_map:
                    chapters.append((title, page_map[page_num]))

        if not chapters:
            for i in range(total_pages):
                if (i + 1) in page_map: 
                    chapters.append((f"Page {i+1}", page_map[i + 1]))
                    
        doc.close()
        return words_list, chapters, page_map, footnotes_map

    def _load_epub(self):
        words_list, chapters, current_word_count = [], [], 0
        
        with zipfile.ZipFile(self.file_path, 'r') as z:
            container_xml = z.read('META-INF/container.xml')
            container_root = ET.fromstring(container_xml)
            rootfile_path = next(node.attrib['full-path'] for node in container_root.iter() if 'full-path' in node.attrib)
            opf_data = z.read(rootfile_path)
            opf_root = ET.fromstring(opf_data)
            opf_dir = os.path.dirname(rootfile_path)
            manifest = {item.attrib['id']: item.attrib['href'] for item in opf_root.findall(".//{*}manifest/{*}item")}
            
            toc_titles = {}
            try:
                spine_node = opf_root.find(".//{*}spine")
                toc_id = spine_node.attrib.get('toc')
                if toc_id and toc_id in manifest:
                    toc_full_path = os.path.join(opf_dir, manifest[toc_id]).replace('\\', '/')
                    toc_root = ET.fromstring(z.read(toc_full_path))
                    for nav in toc_root.findall(".//{*}navPoint"):
                        label = nav.find(".//{*}navLabel/{*}text")
                        content = nav.find(".//{*}content")
                        if label is not None and content is not None:
                            src = content.attrib.get('src', '').split('#')[0]
                            toc_titles[src] = label.text.strip()
            except: pass
            
            spine_ids = [item.attrib['idref'] for item in opf_root.findall(".//{*}spine/{*}itemref")]
            total_items = len(spine_ids)
            
            for i, item_id in enumerate(spine_ids):
                if self.isInterruptionRequested(): return [], [], {}
                self.progress_updated.emit(int((i / total_items) * 100))
                
                if item_id in manifest:
                    rel_path = manifest[item_id]
                    full_path = os.path.join(opf_dir, rel_path).replace('\\', '/')
                    try:
                        soup = BeautifulSoup(z.read(full_path), 'html.parser')
                        
                        # Determine Title
                        title = toc_titles.get(rel_path)
                        if not title and soup.title: title = soup.title.string.strip()
                        if not title:
                            h = soup.find(['h1', 'h2', 'h3'])
                            if h: title = h.get_text().strip()[:40]
                        if not title: title = f"Section {len(chapters)+1}"
                        
                        chapters.append((title, current_word_count))
                        
                        raw_text = soup.get_text(separator=' ')
                        normalized = normalize_text(raw_text)
                        
                        processed_words = process_headers(normalized.split())
                        
                        words_list.extend(processed_words)
                        current_word_count += len(processed_words)
                    except KeyError: continue
            
        # GENERATE PAGE MAP
        WORDS_PER_PAGE = 300
        page_map = {}
        total_words = len(words_list)
        
        page_num = 1
        for idx in range(0, total_words, WORDS_PER_PAGE):
            page_map[page_num] = idx
            page_num += 1
            
        return words_list, chapters, page_map