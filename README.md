# ucoolele-song-convert

Python package for converting Ucoolele song YAML files into binary assets and generated C++ song library sources.

## Install

```bash
pip install git+https://github.com/d0d0-the-bird/ucoolele-song-convert.git
```

For local development from this checkout:

```bash
pip install -e .
```

## Library Usage

```python
from pathlib import Path

import yaml

from ucoolele_song_convert import Song
from ucoolele_song_convert.generate_bin import generateSongBlob
from ucoolele_song_convert.generate_sources import generateSources

song_data = yaml.safe_load(Path("song-examples/Jingle Bells.yaml").read_text())
song = Song.from_yaml_dict(song_data)

blob = song.to_bytes()
```

Example after installing from GitHub:

```python
from pathlib import Path

import yaml

from ucoolele_song_convert import Song
from ucoolele_song_convert.generate_sources import generateSources

song_paths = [
    Path("song-examples/Jingle Bells.yaml"),
    Path("song-examples/Simple Chord Song.yaml"),
]

songs = [Song.from_yaml_dict(yaml.safe_load(path.read_text())) for path in song_paths]
header_text, source_text = generateSources(songs)
print(header_text[:120])
print(source_text[:120])
```

## CLI Usage

```bash
ucoolele-generate-bin song-examples -o bin
ucoolele-generate-sources song-examples/example_songs.yaml -o source
```

## Local Wrapper Scripts

```bash
python3 src/generate_bin.py song-examples -o bin
python3 src/generate_sources.py song-examples/example_songs.yaml -o source
```
