import yaml
import struct
from pathlib import Path
from enum import Enum


class PlayFinger(Enum):
    NONE = 0
    INDEX = 1
    MIDDLE = 2
    RING = 3
    PINKY = 4


class NoteName(Enum):
    C = 0
    D = 1
    E = 2
    F = 3
    G = 4
    A = 5
    B = 6


class NoteAccidental(Enum):
    NONE = 0
    SHARP = 1
    FLAT = 2


def sanitize_string(s, length):
    """Sanitize and pad string to a fixed length."""
    return s.encode("utf-8")[:length].ljust(length, b'\x00')

def scale_color(rgb_float):
    """Convert RGB [0.0–1.0] to [0–255]."""
    return [int(x * 255) for x in rgb_float]

def generateSongBlob(songData):

    # Extract and process fields
    unique_id_hex = songData["uniqueId"]
    unique_id_bytes = bytes.fromhex(unique_id_hex.ljust(64, '0'))[:32]

    timestamp = struct.pack("<I", songData["timestamp"])

    name = sanitize_string(songData["name"], 64)
    play_style = sanitize_string(songData["songPlayStyle"], 16)

    fret_colors = songData["fretColorTable"]
    fret_color_table = [scale_color(c) for c in fret_colors]
    while len(fret_color_table) < 13:
        fret_color_table.append([0, 0, 0])  # pad to 13

    finger_colors = songData["fingerColorTable"]
    finger_color_table = [scale_color(c) for c in finger_colors]
    while len(finger_color_table) < 5:
        finger_color_table.append([0, 0, 0])  # pad to 5

    reserved = struct.pack("BB", 0, 0)

    song_duration = struct.pack("<I", songData["songDuration_ms"])

    notes = [
        note for note in songData["objects"]
        if note["type"] == "NOTE"
    ]
    note_count = struct.pack("<I", len(notes))

    # Prepare note binary data
    note_bin_data = b""
    for note in notes:
        note_bin_data += struct.pack(
            "<HHBBBBII",
            note["wire"],
            note["fret"],
            NoteName[note["name"]].value,
            NoteAccidental[note["accidental"]].value,
            note["octave"],
            PlayFinger[note["finger"]].value,
            note["startTime_ms"],
            note["duration_ms"]
        )

    # Build full binary blob
    binary_blob = b"".join([
        unique_id_bytes,
        timestamp,
        name,
        play_style,
        b"".join(struct.pack("BBB", *color) for color in fret_color_table),
        b"".join(struct.pack("BBB", *color) for color in finger_color_table),
        reserved,
        song_duration,
        note_count,
        note_bin_data
    ])

    return binary_blob


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Convert YAML songs to binary format.")
    parser.add_argument("songs_yaml_dir", help="Directory where YAML song files are located")
    parser.add_argument("-o", "--output", default="bin", help="Output directory")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    songsDir = Path(args.songs_yaml_dir)

    songBlobs = []
    allSongsData = []
    totalCoreBlobSizeB = 0
    for songYaml in songsDir.iterdir():
        if not songYaml.is_file():
            continue

        with open(songYaml, "r") as f:
            song = yaml.safe_load(f)
        allSongsData.append(song)

        songBlob = generateSongBlob(song)
        songBlobs.append(songBlob)

        # Write binary file
        output_path = output_dir / (songYaml.stem + ".bin")
        with open(output_path, "wb") as out_file:
            out_file.write(songBlob)

        print(f"✅ Wrote {output_path.name} ({len(songBlob)} bytes)")
        totalCoreBlobSizeB += len(songBlob)

    print(f"Total size of the song binaries is {totalCoreBlobSizeB} bytes")


if __name__ == "__main__":
    main()
