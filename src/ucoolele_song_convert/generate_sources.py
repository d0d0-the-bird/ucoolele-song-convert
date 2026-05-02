import yaml
from pathlib import Path
import re
import os
import sys
from datetime import datetime, timezone



# Utility functions
def to_enum_id(name: str, shortId: str) -> str:
    return re.sub(r'\W+', '_', name).upper()+ '_' + shortId.upper()

def to_var_name(name: str, shortId: str) -> str:
    parts = re.findall(r'\w+', name)
    return  parts[0].lower() + ''.join(p.capitalize() for p in parts[1:]) + 'Data' + '_' + shortId

def to_comment(name: str, shortId: str) -> str:
    return name.strip() + ', Song short ID: ' + shortId.upper()

def get_script_dir():
    if hasattr(sys, '_getframe') and '__file__' in globals():
        return os.path.dirname(os.path.abspath(__file__))
    else:
        return os.getcwd()  # fallback for interactive mode


# Generator function
def generateSources(song_blobs, song_metadata):
    assert len(song_blobs) == len(song_metadata), "Mismatched song data and metadata lengths."

    with open(get_script_dir() + '/templates/song_library.h.template') as f:
        HEADER_TEMPLATE = f.read()
    with open(get_script_dir() + '/templates/song_library.cpp.template') as f:
        SOURCE_TEMPLATE = f.read()

    enum_entries = []
    data_arrays = []
    table_entries = []

    for i, (blob, meta) in enumerate(zip(song_blobs, song_metadata)):
        shortId = meta['uniqueId'][:7]
        name = meta['name']
        enum_id = to_enum_id(name, shortId)
        var_name = to_var_name(name, shortId)
        comment = to_comment(name, shortId)

        # Break bytes into uint32_t values
        if len(blob) % 4 != 0:
            raise ValueError(f"Blob for '{name}' is not aligned to 4-byte uint32_t values.")

        uint32_list = [int.from_bytes(blob[i:i+4], byteorder='little') for i in range(0, len(blob), 4)]

        lines = []
        for i in range(0, len(uint32_list), 4):
            chunk = uint32_list[i:i+4]
            line = '    ' + ', '.join(f'0x{val:08X}' for val in chunk)  # 4 spaces indent
            lines.append(line)
        hex_values = ',\n'.join(lines)

        array_def = \
            f"static const uint32_t {var_name}[] =\n" + \
             "{\n" + \
            f"{hex_values}\n" + \
             "};"

        enum_entries.append(f"{enum_id}")
        data_arrays.append(array_def)
        table_entries.append(f"{{sizeof({var_name}), {var_name}}}, // {comment}")

    # Get current UTC datetime
    now = datetime.now(timezone.utc)

    # Generate each value
    build_time = now.strftime("%H:%M:%S %Z")       # e.g., "14:37:09 UTC"
    build_date = now.strftime("%Y-%m-%d")       # e.g., "2025-10-29"
    build_timestamp = int(now.timestamp())      # e.g., 1761747429

    header_output = HEADER_TEMPLATE \
        .replace("{{build_time}}", build_time) \
        .replace("{{build_date}}", build_date) \
        .replace("{{build_timestamp}}", str(build_timestamp)) \
        .replace("{{enum_entries}}", ', \\\n    '.join(enum_entries))
    source_output = SOURCE_TEMPLATE \
        .replace("{{build_time}}", build_time) \
        .replace("{{build_date}}", build_date) \
        .replace("{{build_timestamp}}", str(build_timestamp)) \
        .replace("{{song_data_arrays}}", '\n\n'.join(data_arrays)) \
        .replace("{{song_table_entries}}", ',\n    '.join(table_entries))

    return header_output, source_output


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Create sources from song binaries for Ucoolele firmware project")
    parser.add_argument("core_songs_yaml_path", help="YAML containing paths to BIN song files")
    parser.add_argument("-b", "--binaries", default="bin", help="Song binaries directory")
    parser.add_argument("-o", "--output", default="source", help="Output directory for C++ sources of core songs")
    args = parser.parse_args()

    with open(args.core_songs_yaml_path, "r") as f:
        yaml_files = yaml.safe_load(f)

    songBlobs = []
    allSongsData = []
    totalCoreBlobSizeB = 0
    for yaml_path in yaml_files:
        yaml_path = Path(yaml_path)

        with open(yaml_path, "r") as f:
            song = yaml.safe_load(f)
        allSongsData.append(song)

        binPath = Path(args.binaries) / (yaml_path.stem + ".bin")
        with open(binPath, 'rb') as f :
            songBlob = f.read()
        songBlobs.append(songBlob)

        print(f"✅ Read {binPath.name} ({len(songBlob)} bytes)")
        totalCoreBlobSizeB += len(songBlob)

    print(f"Total size of the core songs that go to Ucoolele is {totalCoreBlobSizeB} bytes")

    h, cpp = generateSources(songBlobs, allSongsData)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(output_dir / 'song_library.h', 'w') as h_file:
        h_file.write(h)

    with open(output_dir / 'song_library.cpp', 'w') as cpp_file:
        cpp_file.write(cpp)

    print(f"Generated sources!")


if __name__ == "__main__":
    main()
