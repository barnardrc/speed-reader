# speed-reader

A speed reading application powered by local AI.

#### De-DRM Guide
*Credit to u/caelypso299*
[2024 Guide to DeDRM Kindle Books](https://www.reddit.com/r/Calibre/comments/1c2ryfz/2024_guide_to_dedrm_kindle_books/)

---

### Installation
This project includes automated setup scripts that handle dependencies, virtual environments, and AI model configuration.

1. **Clone the repository:**
 ```bash
 git clone [https://github.com/barnardrc/speed-reader](https://github.com/barnardrc/speed-reader)
 cd speed-reader
 ```
2. Run the setup script:

Windows: Double-click setup.bat (or run it from the command line).

Linux / macOS: Run the setup script from the terminal:

```Bash

chmod +x setup.sh  # (Only needed the first time)
./setup.sh
```
_Follow the on-screen prompts to install dependencies and the required AI model._

#### Running the Application
Once installation is complete, use the shortcut created in the root folder:

Windows: Double-click run.bat

Linux / macOS: Run the shell script:

```Bash

./run.sh
```
#### Manual Run (Alternative)
If you prefer to run it manually without the shortcuts:

#### Windows:

```DOS
venv\Scripts\activate
python main.py
```
#### Linux / macOS:

```Bash

source venv/bin/activate
python main.py
```
