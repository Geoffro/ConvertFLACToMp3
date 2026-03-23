
import os
import argparse
import re
import sys
import shutil
import subprocess

def list_flac_files(input_dir):
    return [f for f in os.listdir(input_dir) if f.lower().endswith('.flac')]

def parse_track_info(base):
    """
    Extract track number and name from filename base.
    Returns (track_number, track_name)
    """

    # Pattern: <Artist>-<track number>-<track name>
    match = re.match(r'^(.+?)-\s*(\d+)\s*-\s*(.+)$', base)
    if match:
        return match.group(2).strip(), match.group(3).strip()

    # Pattern: <track number>-<track name>
    match = re.match(r'^(\d+)\s*-\s*(.+)$', base)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return None, base.strip()

def clean_album_name(folder_name):
    # Remove patterns like "(1999)", "[1999]", "1999"
    cleaned = re.sub(r"[\(\[]?\b\d{4}\b[\)\]]?", "", folder_name)
    return cleaned.strip()

def check_ffmpeg():
    # Check for ffmpeg in PATH or local directory
    ffmpeg_path = shutil.which('ffmpeg')
    if not ffmpeg_path:
        local_ffmpeg = os.path.join(os.getcwd(), 'ffmpeg')
        if os.path.isfile(local_ffmpeg) and os.access(local_ffmpeg, os.X_OK):
            ffmpeg_path = local_ffmpeg
    if not ffmpeg_path:
        print("ffmpeg not found in PATH or local directory. Aborting.")
        return None
    
    return ffmpeg_path

def convert_flac_to_mp3(input_dir, output_dir, bitrate, artist):

    ffmpeg_path = check_ffmpeg()
    if not ffmpeg_path:
        return

    folder_name = os.path.basename(os.path.normpath(input_dir))
    album_name = clean_album_name(folder_name)
    tracks_numbered = all_tracks_numbered(input_dir)

    print(f"Artist: {artist}")
    print(f"Album:  {album_name}")

    os.makedirs(output_dir, exist_ok=True)

    for filename in list_flac_files(input_dir):
        flac_path = os.path.join(input_dir, filename)
        base = os.path.splitext(filename)[0]
        track_number, track_name = parse_track_info(base)

        if tracks_numbered and not track_number:
            print(f"Warning: tracks are not properly numbered. Using track name: {track_name}")

        # Sanitize filename for filesystem
        safe_name = re.sub(r'[\\/:"*?<>|]+', '', track_name)
        safe_name = re.sub(r'\s+', ' ', safe_name).strip()
        mp3_path = os.path.join(output_dir, f"{safe_name}.mp3")

        if os.path.exists(mp3_path):
            print(f"Error: output file already exists, skipping: {mp3_path}")
            continue

        cmd = [
            ffmpeg_path,
            '-i', flac_path,
            '-b:a', bitrate,
            '-y', # overwrite output if needed
            '-metadata', f'artist={artist}',
            '-metadata', f'album={album_name}'
        ]
        if track_number:
            cmd += ['-metadata', f'track={track_number}']
        cmd += [mp3_path]

        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode == 0:
                print(f"Converted: {filename} -> {mp3_path}")
            else:
                print(f"Failed to convert {filename}: {result.stderr.decode().strip()}")
        except Exception as e:
            print(f"Failed to convert {filename}: {e}")

def detect_artist_from_filenames(input_dir):
    files = list_flac_files(input_dir)
    if not files:
        print("No .flac files found in the input directory.")
        return None

    # Pattern: <Artist>-<track number>-<track name>
    pattern = re.compile(r'^(.+?)-\s*\d+\s*-\s*.+$', re.IGNORECASE)
    artists = set()

    for f in files:
        base = os.path.splitext(f)[0]
        m = pattern.match(base)
        if not m:
            return None
        artists.add(m.group(1).strip())

    if len(artists) == 1:
        return artists.pop()
    return None

# Check if all tracks are numbered in the format <Artist>-<track number>-<track name>.
# In some cases, the artist may not be present, but will still follow the pattern <track number>-<track name>. This is also acceptable, but the track number must be present and sequential starting from 1.
# This also checks that all files match the pattern, which is necessary for auto-detection to work properly.
def all_tracks_numbered(input_dir):
    files = list_flac_files(input_dir)
    if not files:
        print("No .flac files found in the input directory.")
        return False

    pattern = re.compile(r'^(.+?-\s*)?(\d+)\s*-\s*.+$', re.IGNORECASE)
    track_numbers = set()

    for f in files:
        base = os.path.splitext(f)[0]
        m = pattern.match(base)
        if not m:
            print(f"Warning: file does not match expected pattern and may not be properly numbered: {f}")
            return False
        track_numbers.add(int(m.group(2)))

    # Check if track numbers are sequential starting from 1
    expected_tracks = set(range(1, max(track_numbers) + 1))
    if track_numbers != expected_tracks:
        print(f"Warning: track numbers are not sequential starting from 1. Detected track numbers: {sorted(track_numbers)}")
        return False

    return True

if __name__ == "__main__":

    ffmpeg_path = check_ffmpeg()
    if not ffmpeg_path:
        sys.exit(0)

    parser = argparse.ArgumentParser(description="Convert FLAC files to MP3 format.")
    parser.add_argument("input_dir", type=str, help="Path to the input directory containing FLAC files.")
    parser.add_argument("--artist", type=str, required=False, help="Artist name (optional). If omitted the script will try to auto-detect from filenames.")
    parser.add_argument("--output_dir", type=str, default=None, help="Output directory (default: input_dir/mp3).")
    parser.add_argument("--bitrate", type=str, default="192k", help="Bitrate for MP3 files (default: 192k).")

    args = parser.parse_args()

    output_directory = args.output_dir or os.path.join(args.input_dir, "mp3")

    # Determine artist: use provided, else attempt autodetect and prompt
    if args.artist:
        artist = args.artist
    else:
        detected = detect_artist_from_filenames(args.input_dir)
        if not detected:
            print("Could not detect a consistent artist from filenames. Aborting without conversion.")
            sys.exit(0)

        # Prompt user to confirm
        try:
            resp = input(f"Detected artist '{detected}' from filenames. Use this artist? [Y/n]: ").strip().lower()
        except KeyboardInterrupt:
            print("\nUser cancelled. Aborting.")
            sys.exit(0)

        if resp in ('', 'y', 'yes'):
            all_tracks_numbered(args.input_dir)  # Warn if tracks are not properly numbered, but continue anyway
            artist = detected
        else:
            print("Artist not confirmed. Aborting without conversion.")
            sys.exit(0)

    convert_flac_to_mp3(args.input_dir, output_directory, args.bitrate, artist)
