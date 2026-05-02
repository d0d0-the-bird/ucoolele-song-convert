# ucoolele-song-convert

Python package for converting Ucoolele song YAML files into binary assets and generated C++ song library sources.

## Install

```bash
pip install .
```

## Library Usage

```python
from ucoolele_song_convert.generate_bin import generateSongBlob
from ucoolele_song_convert.generate_sources import generateSources
```

## CLI Usage

```bash
ucoolele-generate-bin song-examples -o bin
ucoolele-generate-sources core_songs.yaml -b bin -o source
```
