# Progress Log

## Before 1/16
### Features Implemented
*   **Core Application Structure**
    *   Main window with PyQt6 (`main.py`).
    *   RSVP (Rapid Serial Visual Presentation) display functionality.
    *   Dark theme UI styling.
    *   Responsive sidebar for navigation.

*   **File Handling** (`utils/book_loader.py`)
    *   **PDF Support**: Text extraction, header detection, and heuristic-based footnote detection using PyMuPDF (fitz).
    *   **EPUB Support**: Container parsing, OPF manifest reading, and HTML/XML text extraction using BeautifulSoup4.
    *   Asynchronous loading with progress bars.

*   **AI Integration** (`utils/ai.py`, `utils/ai_backend.py`)
    *   **Local LLM Support**: Connector for Ollama API.
    *   **Comprehension Checks**: System to generate questions based on reading context.
    *   **Entity Extraction**: Side panel showing key entities in the text.
    *   **Question Panel**: UI for interactive questions and feedback.
    *   **Sequential Worker**: Queue-based background worker for AI tasks.

*   **Eye Tracking** (`utils/eye_tracking/`)
    *   **Camera Integration**: Webcam access for gaze detection.
    *   **Auto-Pause**: Feature to pause reading when user looks away (`eyes_off` logic).
    *   Debug window for camera feed.

*   **User Settings** (`utils/settings.py`)
    *   JSON-based configuration persistence.
    *   Pause configuration (smart pauses for punctuation).
    *   Visual settings (WPM, opacity, context range).

*   **UI Components** (`ui/`)
    *   Controls bar for WPM and settings.
    *   Tutorial overlay for first-time users.
    *   Dialogs for Pause settings and AI configuration.
