# Speed Reader

A desktop rapid serial visual presentation (RSVP) reader for EPUB and PDF
documents. Speed Reader displays text one unit at a time, preserves chapter and
page navigation, adjusts pauses around punctuation, and can optionally use a
local Ollama model for reading assistance.

Experimental eye tracking can pause the reader when the user looks away. That
feature currently targets a Raspberry Pi-style camera pipeline using GStreamer
and `libcamerasrc`; it is optional and not required for ordinary reading.

## Features

- EPUB and PDF import with chapters, page mapping, and footnote extraction
- configurable reading speed and punctuation-aware pauses
- context, progress, and queue views
- optional local AI questions and entity summaries through Ollama
- optional camera-based gaze pause/resume
- local settings and reading-position persistence

The application processes documents on the local computer. Ollama requests are
sent to the configured Ollama endpoint, which defaults to
`http://localhost:11434`.

## Requirements

- Python 3.10 or newer
- a desktop environment supported by PyQt6
- optional: [Ollama](https://ollama.com/) for local AI features
- optional: OpenCV-compatible camera/GStreamer setup for eye tracking

## Installation

Clone the repository, then run the setup helper for your platform:

```bash
git clone https://github.com/barnardrc/speed-reader.git
cd speed-reader
```

Windows:

```bat
setup.bat
```

Linux or macOS:

```bash
chmod +x setup.sh
./setup.sh
```

The helper creates a local virtual environment, installs
`requirements.txt`, and offers to configure Ollama. Review installation prompts
before approving optional software downloads.

For a manual setup:

```bash
python -m venv venv
```

Windows:

```bat
venv\Scripts\activate
python -m pip install -r requirements.txt
python main.py
```

Linux or macOS:

```bash
source venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

## Usage

1. Start the application.
2. Select **Open** and choose an EPUB or PDF that you are permitted to use.
3. Choose the reading speed and pause behavior.
4. Enable local AI or eye tracking only if those optional services are
   available.

Books and settings are intentionally excluded from version control. This
repository does not provide copyrighted reading material or instructions for
circumventing digital-rights protections. For tests and demonstrations, use
public-domain material or fixtures you created yourself.

## Development checks

The lightweight test suite covers text normalization without requiring the GUI
or optional camera stack:

```bash
python -m unittest discover -s tests -v
python -m compileall -q .
```

## Status

This is an experimental personal project. Eye tracking is hardware-specific,
and the installer has not yet been verified across every supported operating
system. Bug reports should include the operating system, Python version, and
whether Ollama or eye tracking was enabled.

## License

Licensed under the GNU General Public License v3.0. See [LICENSE](LICENSE).
