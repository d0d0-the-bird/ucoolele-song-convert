import yaml
from pathlib import Path
import re
from datetime import datetime, timezone
from importlib.resources import files

from ucoolele_song_convert.song_model import Song



# Utility functions
def to_enum_id(name: str, shortId: str) -> str:
    return re.sub(r'\W+', '_', name).upper()+ '_' + shortId.upper()

def to_var_name(name: str, shortId: str) -> str:
    parts = re.findall(r'\w+', name)
    return  parts[0].lower() + ''.join(p.capitalize() for p in parts[1:]) + 'Data' + '_' + shortId

def to_comment(name: str, shortId: str) -> str:
    return name.strip() + ', Song short ID: ' + shortId.upper()


def read_template(template_name: str) -> str:
    return files("ucoolele_song_convert.templates").joinpath(template_name).read_text()


def format_timestamp_comment(timestamp: int):
    decoded = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    return f"timestamp: {timestamp} ({decoded.strftime('%Y-%m-%d %H:%M:%S UTC')})"


def format_row(binary_value: bytes, comment: str):
    if len(binary_value) % 4 != 0:
        raise ValueError(f"Row is not aligned to 4-byte uint32_t values: {comment}")

    uint32_list = [int.from_bytes(binary_value[i:i+4], byteorder='little') for i in range(0, len(binary_value), 4)]
    values = ', '.join(f'0x{val:08X}' for val in uint32_list)
    return f"    {values}, // {comment}"


def format_object_comment(song_object):
    fields = {member.name: member.pretty_value for member in song_object.iter_binary_members()}
    object_type = fields["objectType"]

    if object_type == "NOTE":
        return (
            f"NOTE w={fields['wire']} f={fields['fret']} n={fields['name']} a={fields['accidental']} "
            f"o={fields['octave']} fi={fields['finger']} startTime={fields['startTime_ms']}ms "
            f"duration={fields['duration_ms']}ms"
        )

    if object_type == "CHORD":
        return (
            f"CHORD w1={fields['wire1']} w2={fields['wire2']} w3={fields['wire3']} w4={fields['wire4']} "
            f"f1={fields['wireFinger1']} f2={fields['wireFinger2']} f3={fields['wireFinger3']} f4={fields['wireFinger4']} "
            f"startTime={fields['startTime_ms']}ms duration={fields['duration_ms']}ms"
        )

    if object_type == "STRUM":
        return f"STRUM dir={fields['direction']} startTime={fields['startTime_ms']}ms"

    raise ValueError(f"Unsupported object type for source comment: {object_type}")


def iter_song_rows(song):
    header_members = song.iter_header_binary_members()
    color_block = b"".join(member.binary_value for member in header_members[4:7])

    yield header_members[0].binary_value, f"{header_members[0].name}: {header_members[0].pretty_value}"
    yield header_members[1].binary_value, format_timestamp_comment(header_members[1].pretty_value)
    yield header_members[2].binary_value, f"{header_members[2].name}: {header_members[2].pretty_value}"
    yield header_members[3].binary_value, f"{header_members[3].name}: {header_members[3].pretty_value}"
    yield color_block, "fretColorTable[13], fingerColorTable[5], reserved"
    yield header_members[7].binary_value, f"{header_members[7].name}: {header_members[7].pretty_value}"
    yield header_members[8].binary_value, f"{header_members[8].name}: {header_members[8].pretty_value}"

    for song_object in song.objects:
        yield song_object.to_bytes(), format_object_comment(song_object)


# Generator function
def generateSources(songs):

    HEADER_TEMPLATE = read_template("song_library.h.template")
    SOURCE_TEMPLATE = read_template("song_library.cpp.template")

    enum_entries = []
    data_arrays = []
    table_entries = []

    for song in songs:
        shortId = song.unique_id[:7]
        name = song.name
        enum_id = to_enum_id(name, shortId)
        var_name = to_var_name(name, shortId)
        comment = to_comment(name, shortId)

        lines = [format_row(binary_value, row_comment) for binary_value, row_comment in iter_song_rows(song)]
        hex_values = '\n'.join(lines)

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

    parser = argparse.ArgumentParser(description="Create sources from song YAML files for Ucoolele firmware project")
    parser.add_argument("core_songs_yaml_path", help="YAML containing paths to song YAML files")
    parser.add_argument("-o", "--output", default="source", help="Output directory for C++ sources of core songs")
    args = parser.parse_args()

    with open(args.core_songs_yaml_path, "r") as f:
        yaml_files = yaml.safe_load(f)

    songs = []
    totalCoreBlobSizeB = 0
    for yaml_path in yaml_files:
        yaml_path = Path(yaml_path)

        with open(yaml_path, "r") as f:
            song_data = yaml.safe_load(f)

        song = Song.from_yaml_dict(song_data)
        song_blob = song.to_bytes()
        songs.append(song)

        print(f"✅ Read {yaml_path.name} ({len(song_blob)} bytes when serialized)")
        totalCoreBlobSizeB += len(song_blob)

    print(f"Total size of the core songs that go to Ucoolele is {totalCoreBlobSizeB} bytes")

    h, cpp = generateSources(songs)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(output_dir / 'song_library.h', 'w') as h_file:
        h_file.write(h)

    with open(output_dir / 'song_library.cpp', 'w') as cpp_file:
        cpp_file.write(cpp)

    print(f"Generated sources!")


if __name__ == "__main__":
    main()
