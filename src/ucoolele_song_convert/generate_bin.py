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


class SongObjectType(Enum):
    NOTE = 0
    CHORD = 1
    STRUM = 2


class StrumDirection(Enum):
    DOWN = 0
    UP = 1


REQUIRED_SONG_FIELDS = {
    "uniqueId",
    "timestamp",
    "name",
    "songPlayStyle",
    "fretColorTable",
    "fingerColorTable",
    "songDuration_ms",
    "objects",
}


def sanitize_string(s, length):
    """Sanitize and pad string to a fixed length."""
    return s.encode("utf-8")[:length].ljust(length, b'\x00')

def scale_color(rgb_float):
    """Convert RGB [0.0–1.0] to [0–255]."""
    return [int(x * 255) for x in rgb_float]


def isSongYamlDocument(document):
    return isinstance(document, dict) and REQUIRED_SONG_FIELDS.issubset(document.keys())


# Song blob layout, little-endian:
# - uniqueId: 32 bytes
# - timestamp: uint32
# - name: 64 bytes
# - songPlayStyle: 16 bytes
# - fretColorTable: 13 * RGB bytes
# - fingerColorTable: 5 * RGB bytes
# - reserved: 2 bytes
# - songDuration_ms: uint32
# - object_count: uint32
# - object data stream
#
# NOTE object layout, 16 bytes total:
# - objectType: uint8
# - wire: uint8
# - fret: uint16
# - name: uint8
# - accidental: uint8
# - octave: uint8
# - finger: uint8
# - startTime_ms: uint32
# - duration_ms: uint32
#
# CHORD object layout, 20 bytes total:
# - objectType: uint8
# - wire1: uint8
# - wire2: uint8
# - wire3: uint8
# - wire4: uint8
# - wireFinger1: uint8
# - wireFinger2: uint8
# - wireFinger3: uint8
# - wireFinger4: uint8
# - reserved: uint8
# - reserved: uint16
# - startTime_ms: uint32
# - duration_ms: uint32
#
# STRUM object layout, 8 bytes total:
# - objectType: uint8
# - direction: uint8
# - reserved: uint16
# - startTime_ms: uint32
#
# Object type enum values must match the firmware definitions.


def packNoteObject(note):
    return struct.pack(
        "<BBHBBBBII",
        SongObjectType.NOTE.value,
        note["wire"],
        note["fret"],
        NoteName[note["name"]].value,
        NoteAccidental[note["accidental"]].value,
        note["octave"],
        PlayFinger[note["finger"]].value,
        note["startTime_ms"],
        note["duration_ms"],
    )


def packChordObject(chord):
    return struct.pack(
        "<BBBBBBBBBBHII",
        SongObjectType.CHORD.value,
        chord["wire1"],
        chord["wire2"],
        chord["wire3"],
        chord["wire4"],
        PlayFinger[chord["wireFinger1"]].value,
        PlayFinger[chord["wireFinger2"]].value,
        PlayFinger[chord["wireFinger3"]].value,
        PlayFinger[chord["wireFinger4"]].value,
        0,
        0,
        chord["startTime_ms"],
        chord["duration_ms"],
    )


def packStrumObject(strum):
    return struct.pack(
        "<BBHI",
        SongObjectType.STRUM.value,
        StrumDirection[strum["direction"]].value,
        0,
        strum["startTime_ms"],
    )

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

    serialized_objects = []
    for songObject in songData["objects"]:
        if songObject["type"] == "NOTE":
            serialized_objects.append(packNoteObject(songObject))
            continue

        if songObject["type"] == "CHORD":
            serialized_objects.append(packChordObject(songObject))
            continue

        if songObject["type"] == "STRUM":
            serialized_objects.append(packStrumObject(songObject))
            continue

    object_count = struct.pack("<I", len(serialized_objects))
    object_bin_data = b"".join(serialized_objects)

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
        object_count,
        object_bin_data
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

        if not isSongYamlDocument(song):
            print(f"Skipping {songYaml.name}: not a song YAML document")
            continue

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
