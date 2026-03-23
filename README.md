# ConvertToMp3

Simple script to convert FLAC files to MP3 using ffmpeg.


**Files**
- [ConvertToMp3.py](ConvertToMp3.py): Command-line converter script
- [ConvertToMp3PyQt.py](ConvertToMp3PyQt.py): PyQt5-based GUI (recommended)




**Recommended: Use a Python Virtual Environment**

It is best practice to use a Python virtual environment for this project. To create and activate a virtual environment named `.venv` in the project directory:

```bash
python3 -m venv .venv
# Activate the virtual environment (macOS/Linux)
source .venv/bin/activate
# On Windows:
.venv\Scripts\activate
```

Once activated, install dependencies (e.g., PyQt5) inside the venv:
```bash
pip install PyQt5
```

You can deactivate the environment at any time with:
```bash
deactivate
```

**Prerequisites**
- Python 3.8 or newer
- `ffmpeg` installed and available in your `PATH` (or available as a local executable named `ffmpeg` in your current working directory). On macOS you can install it with Homebrew:

  ```bash
  brew install ffmpeg
  ```

**For the GUI:**
- (If using a venv, make sure it is activated first)
- Install PyQt5 with pip:
  ```bash
  pip install PyQt5
  ```
- No system-level dependencies or special Python build required. This works with Homebrew Python, python.org Python, and most other Python distributions.


**Usage**

**Command-line:**
```bash
python ConvertToMp3.py /path/to/flac_directory --artist "Artist Name"
# optional arguments
python ConvertToMp3.py /path/to/flac_directory --artist "Artist Name" --output_dir /path/to/output --bitrate 320k
```
The script will create an `mp3` folder inside the input directory by default (or use `--output_dir`).


**Graphical User Interface:**
```bash
python ConvertToMp3PyQt.py
```
The GUI allows you to:
- Import a `.zip` file containing FLAC files
- Unzip to a target location
- Auto-detect and edit artist/album metadata
- Check for filename conflicts before conversion
- Convert FLAC files to MP3 with a button click
- View logs and status in a scrollable output window


**Features & Notes**
- Converts all `.flac` files in the input directory to `.mp3` using ffmpeg
- Writes metadata tags (`artist`, `album`, and optional `track`) to each MP3 file
- If `ffmpeg` cannot be found, the script exits before converting
- Output files are placed in an `mp3` subfolder by default, or in a custom directory with `--output_dir`
- The GUI supports importing from zip, metadata editing, conflict checking, and conversion with status logging

**Filename Patterns & Auto-Detection**

- The scripts expect FLAC files to be named in one of these patterns for best results:
  - `<Artist>-<track number>-<track name>.flac`
  - `<track number>-<track name>.flac`
- Example:
  - `The Beatles-01-Come Together.flac`
  - `01-Something.flac`
- If the artist is not specified, the scripts will attempt to auto-detect the artist from filenames. If successful, you can confirm or edit the detected artist before proceeding.
- If filenames do not match the expected patterns, auto-detection and track numbering may not work correctly, and the script will warn you.

**Interactive Prompts & Automation**

- If the artist is auto-detected, the script will prompt for confirmation before converting. Press `Enter` or type `y`/`yes` to accept, or `n`/`no` to abort.
- For fully automated or batch use, a non-interactive mode is not currently implemented. (You may want to add a `--yes` flag in the future for automation.)

**Output Filenames**

- Output MP3 filenames are generated from the track name, sanitized for filesystem safety.
- If two tracks have the same name after sanitization, the script will skip the second file and print an error. To avoid this, ensure track names are unique, or consider including the track number in the output filename.

**Troubleshooting & FAQ**

- **ffmpeg not found:** Ensure ffmpeg is installed and available in your PATH, or place an executable named `ffmpeg` in the current directory.
- **No .flac files found:** Check that your input directory contains FLAC files with the correct extension.
- **Filename pattern warnings:** If you see warnings about track numbering or filename patterns, rename your files to match the expected format for best results.
- **Output file already exists:** The script will skip files if the output MP3 already exists. Delete or rename existing files if you want to re-convert.

**Example Directory Structure**

```
input_dir/
	01-First Song.flac
	02-Second Song.flac
	...
```

**Planned Improvements**
- Add a non-interactive mode (e.g., `--yes` flag) for automation.
- Optionally include track numbers in output filenames for uniqueness.
