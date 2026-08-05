from pathlib import Path
import yaml

from ucoolele_song_convert.song_model import Song, is_song_yaml_document, ascii_yaml_values

def generateSongBlob(songData):
    return Song.from_yaml_dict(songData).to_bytes()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Convert YAML songs to binary format.")
    parser.add_argument("songs_yaml_dir", help="Directory where YAML song files are located")
    parser.add_argument("-o", "--output", default="bin", help="Output directory")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    songsDir = Path(args.songs_yaml_dir)

    totalCoreBlobSizeB = 0
    for songYaml in songsDir.iterdir():
        if not songYaml.is_file() or songYaml.suffix.lower() not in {".yaml", ".yml"}:
            continue

        with open(songYaml, "r", encoding="utf-8") as f:
            song = ascii_yaml_values(yaml.safe_load(f))

        if not is_song_yaml_document(song):
            print(f"Skipping {songYaml.name}: not a song YAML document")
            continue

        songBlob = generateSongBlob(song)

        # Write binary file
        output_path = output_dir / (songYaml.stem + ".bin")
        with open(output_path, "wb") as out_file:
            out_file.write(songBlob)

        print(f"✅ Wrote {output_path.name} ({len(songBlob)} bytes)")
        totalCoreBlobSizeB += len(songBlob)

    print(f"Total size of the song binaries is {totalCoreBlobSizeB} bytes")


if __name__ == "__main__":
    main()
