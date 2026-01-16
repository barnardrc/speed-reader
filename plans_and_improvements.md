# Plans and Improvements

## Bug Fixes
*   [ ] **AI Backend Error Handling**: The current `_check_ollama` implementation in `ai_backend.py` catches general exceptions silently in some places. Needs better logging and specific error messages for the user.
*   [ ] **PDF Footnote Heuristic**: The font size/position heuristic for footnotes in `book_loader.py` (`is_low` and `is_small`) is somewhat fragile and may not work for all PDF layouts. Consider adding a fallback or user toggle.

## Improvements
*   [ ] **Unit Testing**: There are currently no unit tests. Implement `pytest` suite for core logic:
    *   `utils/text_utils.py` (Text normalization)
    *   `utils/book_loader.py` (File parsing logic)
    *   `utils/ai_backend.py` (Mocked API calls)
*   [ ] **Code Refactoring**: `WordDisplay` in `main.py` is very large (God Object). Refactor by moving:
    *   Input handling to a `InputController`.
    *   Overlay logic to `OverlayManager`.
*   [ ] **File Support**: Add support for `.txt` and `.mobi` files to increase versatility.
*   [ ] **Performance**: For very large books, `BookLoader` loads everything into memory (`words` list). Implement lazy loading or chunking for better memory usage.
*   [ ] **Accessibility**: Add keyboard shortcuts configuration and screen reader support verification.
*   [ ] **Dependency Management**: `requirements.txt` exists, but ensure all specific versions for PyQt6 and opencv (for eye tracking) are pinned to avoid breaking changes.

## Feature Requests
*   **Cloud AI Support**: Logic exists for "Cloud" backend in `ai_backend.py` but is unimplemented. Add integration for OpenAI or Anthropic APIs.
*   **Reading Stats**: Track time spent reading and WPM history to show user progress over time.
