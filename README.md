# ConvertToMp3

Simple script to turn an album into tagged MP3s using ffmpeg. FLAC files are encoded to MP3; files that are already MP3 are copied and retagged without a lossy re-encode.



**Files**
- [ConvertToMp3.py](ConvertToMp3.py): Command-line converter script
- [ConvertToMp3GUI.py](ConvertToMp3GUI.py): PyQt5-based GUI (recommended)




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
python ConvertToMp3GUI.py
```
The GUI allows you to:
- Import a `.zip` file or an already unzipped folder containing FLAC or MP3 files
- Unzip to a target location (default: next to the zip file, or user-specified)
- Auto-detect and edit artist/album metadata (album from top-level folder, artist from filenames)
- Handles multi-disk albums (disks as subfolders like 01, 02, Disc 1, etc.)
- Check for filename conflicts before conversion
- Convert FLAC files to MP3 with a button click (MP3 sources are copied and retagged instead)
- Output all MP3s to an `mp3` subfolder inside the chosen output directory, preserving disk subfolders if present
- View logs and status in a scrollable output window, with real-time updates and a completion message
- Add the album to Apple Music with a button click (macOS only) — the converted `mp3` output if there is one, otherwise the imported folder itself when it was already MP3



**Features & Notes**
- Converts all `.flac` files in the input directory (and subfolders) to `.mp3` using ffmpeg
- Handles albums that are already MP3. In the GUI, if *every* file is already an MP3 there is nothing to convert: the Convert button is disabled and **Add to Apple Music** imports the files directly from where they are, with the tags they already have. In a mixed FLAC/MP3 album the MP3s are stream-copied (`-c copy`) into the output folder so the whole album ends up together — the audio is untouched, only tags are rewritten, the bitrate setting does not apply to them, and existing tags that are not overwritten (e.g. `genre`, `year`) carry through
- An `mp3` subfolder at the top level of the imported folder is skipped during scanning, so re-importing a folder you have already converted will not pick up its own output
- Writes metadata tags (`artist`, `album`, `track`, and `disc` if multi-disk) to each MP3 file
- If `ffmpeg` cannot be found, the script exits before converting
- Output files are placed in an `mp3` subfolder inside the output directory (with disk subfolders if needed)
- The GUI supports importing from zip or folder, metadata editing, conflict checking, and conversion with real-time status logging


**Filename Patterns & Auto-Detection**

- The scripts expect source files to be named in one of these patterns for best results:
  - `<Artist>-<track number>-<track name>.flac`
  - `<track number>-<track name>.flac`
- Example:
  - `The Beatles-01-Come Together.flac`
  - `01-Something.flac`
- If the artist is not specified, the scripts will attempt to auto-detect the artist from filenames. If successful, you can confirm or edit the detected artist before proceeding.
- If filenames do not match the expected patterns, auto-detection and track numbering may not work correctly, and the script will warn you.
- For multi-disk albums, disk folders can be named `01`, `02`, `Disc 1`, `CD2`, etc. The GUI will detect and tag the correct disk number.

**Interactive Prompts & Automation**

- If the artist is auto-detected, the script will prompt for confirmation before converting. Press `Enter` or type `y`/`yes` to accept, or `n`/`no` to abort.
- For fully automated or batch use, a non-interactive mode is not currently implemented. (You may want to add a `--yes` flag in the future for automation.)


**Output Structure**

- All converted MP3s are placed in an `mp3` subfolder inside the output directory you choose (or next to the zip file by default).
- For multi-disk albums, each disk's tracks are placed in a subfolder (e.g., `mp3/Disc 1/`).
- Output MP3 filenames are generated from the track name, sanitized for filesystem safety.
- If two tracks have the same name after sanitization, the script will skip the second file and print an error. To avoid this, ensure track names are unique, or consider including the track number in the output filename.

**Troubleshooting & FAQ**

- **ffmpeg not found:** Ensure ffmpeg is installed and available in your PATH, or place an executable named `ffmpeg` in the current directory.
- **No FLAC or MP3 files found:** Check that your input directory contains files with the correct extension.
- **Filename pattern warnings:** If you see warnings about track numbering or filename patterns, rename your files to match the expected format for best results.
- **Output file already exists:** The script will skip files if the output MP3 already exists. Delete or rename existing files if you want to re-convert.


**Example Directory Structure**

```
O (2002)/
  01/
    01-First Song.flac
    02-Second Song.flac
  02/
    01-Another Song.flac
    02-Yet Another.flac
```

After conversion (output dir = `O (2002)`):
```
O (2002)/
  mp3/
    Disc 1/
      First Song.mp3
      Second Song.mp3
    Disc 2/
      Another Song.mp3
      Yet Another.mp3
```
