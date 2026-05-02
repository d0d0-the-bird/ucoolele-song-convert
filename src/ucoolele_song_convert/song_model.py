from abc import ABC, abstractmethod
from enum import Enum
import struct


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
    return s.encode("utf-8")[:length].ljust(length, b"\x00")


def scale_color(rgb_float):
    return [int(x * 255) for x in rgb_float]


def is_song_yaml_document(document):
    return isinstance(document, dict) and REQUIRED_SONG_FIELDS.issubset(document.keys())


class SongObject(ABC):
    @classmethod
    def from_yaml_dict(cls, data):
        object_type = data["type"]
        if object_type == "NOTE":
            return NoteObject(data)
        if object_type == "CHORD":
            return ChordObject(data)
        if object_type == "STRUM":
            return StrumObject(data)

        raise ValueError(f"Unsupported song object type: {object_type}")

    @abstractmethod
    def to_bytes(self):
        raise NotImplementedError


class NoteObject(SongObject):
    def __init__(self, data):
        self.wire = data["wire"]
        self.fret = data["fret"]
        self.name = data["name"]
        self.accidental = data["accidental"]
        self.octave = data["octave"]
        self.finger = data["finger"]
        self.start_time_ms = data["startTime_ms"]
        self.duration_ms = data["duration_ms"]

    def to_bytes(self):
        return struct.pack(
            "<BBHBBBBII",
            SongObjectType.NOTE.value,
            self.wire,
            self.fret,
            NoteName[self.name].value,
            NoteAccidental[self.accidental].value,
            self.octave,
            PlayFinger[self.finger].value,
            self.start_time_ms,
            self.duration_ms,
        )


class ChordObject(SongObject):
    def __init__(self, data):
        self.wire1 = data["wire1"]
        self.wire2 = data["wire2"]
        self.wire3 = data["wire3"]
        self.wire4 = data["wire4"]
        self.wire_finger1 = data["wireFinger1"]
        self.wire_finger2 = data["wireFinger2"]
        self.wire_finger3 = data["wireFinger3"]
        self.wire_finger4 = data["wireFinger4"]
        self.start_time_ms = data["startTime_ms"]
        self.duration_ms = data["duration_ms"]

    def to_bytes(self):
        return struct.pack(
            "<BBBBBBBBBBHII",
            SongObjectType.CHORD.value,
            self.wire1,
            self.wire2,
            self.wire3,
            self.wire4,
            PlayFinger[self.wire_finger1].value,
            PlayFinger[self.wire_finger2].value,
            PlayFinger[self.wire_finger3].value,
            PlayFinger[self.wire_finger4].value,
            0,
            0,
            self.start_time_ms,
            self.duration_ms,
        )


class StrumObject(SongObject):
    def __init__(self, data):
        self.direction = data["direction"]
        self.start_time_ms = data["startTime_ms"]

    def to_bytes(self):
        return struct.pack(
            "<BBHI",
            SongObjectType.STRUM.value,
            StrumDirection[self.direction].value,
            0,
            self.start_time_ms,
        )


class Song:
    def __init__(
        self,
        unique_id,
        timestamp,
        name,
        song_play_style,
        fret_color_table,
        finger_color_table,
        song_duration_ms,
        objects,
    ):
        self.unique_id = unique_id
        self.timestamp = timestamp
        self.name = name
        self.song_play_style = song_play_style
        self.fret_color_table = fret_color_table
        self.finger_color_table = finger_color_table
        self.song_duration_ms = song_duration_ms
        self.objects = objects

    @classmethod
    def from_yaml_dict(cls, data):
        return cls(
            unique_id=data["uniqueId"],
            timestamp=data["timestamp"],
            name=data["name"],
            song_play_style=data["songPlayStyle"],
            fret_color_table=data["fretColorTable"],
            finger_color_table=data["fingerColorTable"],
            song_duration_ms=data["songDuration_ms"],
            objects=[SongObject.from_yaml_dict(song_object) for song_object in data["objects"]],
        )

    def to_bytes(self):
        unique_id_bytes = bytes.fromhex(self.unique_id.ljust(64, "0"))[:32]
        timestamp = struct.pack("<I", self.timestamp)
        name = sanitize_string(self.name, 64)
        play_style = sanitize_string(self.song_play_style, 16)

        fret_color_table = [scale_color(color) for color in self.fret_color_table]
        while len(fret_color_table) < 13:
            fret_color_table.append([0, 0, 0])

        finger_color_table = [scale_color(color) for color in self.finger_color_table]
        while len(finger_color_table) < 5:
            finger_color_table.append([0, 0, 0])

        reserved = struct.pack("BB", 0, 0)
        song_duration = struct.pack("<I", self.song_duration_ms)
        object_bin_data = b"".join(song_object.to_bytes() for song_object in self.objects)
        object_count = struct.pack("<I", len(self.objects))

        return b"".join(
            [
                unique_id_bytes,
                timestamp,
                name,
                play_style,
                b"".join(struct.pack("BBB", *color) for color in fret_color_table),
                b"".join(struct.pack("BBB", *color) for color in finger_color_table),
                reserved,
                song_duration,
                object_count,
                object_bin_data,
            ]
        )
