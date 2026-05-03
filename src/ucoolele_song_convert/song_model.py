from abc import ABC, abstractmethod
from dataclasses import dataclass
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


def pack_color_table(colors, target_length):
    scaled_colors = [scale_color(color) for color in colors]
    while len(scaled_colors) < target_length:
        scaled_colors.append([0, 0, 0])
    return b"".join(struct.pack("BBB", *color) for color in scaled_colors), scaled_colors


@dataclass(frozen=True)
class BinaryField:
    name: str
    pretty_value: object
    binary_value: bytes


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

    def to_bytes(self):
        raise NotImplementedError

    @abstractmethod
    def iter_binary_members(self):
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

    def iter_binary_members(self):
        blob = self.to_bytes()
        return [
            BinaryField("objectType", "NOTE", blob[0:1]),
            BinaryField("wire", self.wire, blob[1:2]),
            BinaryField("fret", self.fret, blob[2:4]),
            BinaryField("name", self.name, blob[4:5]),
            BinaryField("accidental", self.accidental, blob[5:6]),
            BinaryField("octave", self.octave, blob[6:7]),
            BinaryField("finger", self.finger, blob[7:8]),
            BinaryField("startTime_ms", self.start_time_ms, blob[8:12]),
            BinaryField("duration_ms", self.duration_ms, blob[12:16]),
        ]


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

    def iter_binary_members(self):
        blob = self.to_bytes()
        return [
            BinaryField("objectType", "CHORD", blob[0:1]),
            BinaryField("wire1", self.wire1, blob[1:2]),
            BinaryField("wire2", self.wire2, blob[2:3]),
            BinaryField("wire3", self.wire3, blob[3:4]),
            BinaryField("wire4", self.wire4, blob[4:5]),
            BinaryField("wireFinger1", self.wire_finger1, blob[5:6]),
            BinaryField("wireFinger2", self.wire_finger2, blob[6:7]),
            BinaryField("wireFinger3", self.wire_finger3, blob[7:8]),
            BinaryField("wireFinger4", self.wire_finger4, blob[8:9]),
            BinaryField("reserved_byte", 0, blob[9:10]),
            BinaryField("reserved_short", 0, blob[10:12]),
            BinaryField("startTime_ms", self.start_time_ms, blob[12:16]),
            BinaryField("duration_ms", self.duration_ms, blob[16:20]),
        ]


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

    def iter_binary_members(self):
        blob = self.to_bytes()
        return [
            BinaryField("objectType", "STRUM", blob[0:1]),
            BinaryField("direction", self.direction, blob[1:2]),
            BinaryField("reserved_short", 0, blob[2:4]),
            BinaryField("startTime_ms", self.start_time_ms, blob[4:8]),
        ]


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

    def iter_header_binary_members(self):
        fret_color_table_binary, fret_color_table = pack_color_table(self.fret_color_table, 13)
        finger_color_table_binary, finger_color_table = pack_color_table(self.finger_color_table, 5)

        return [
            BinaryField("uniqueId", self.unique_id, self._unique_id_bytes()),
            BinaryField("timestamp", self.timestamp, self._timestamp_bytes()),
            BinaryField("name", self.name, self._name_bytes()),
            BinaryField("songPlayStyle", self.song_play_style, self._song_play_style_bytes()),
            BinaryField("fretColorTable", fret_color_table, fret_color_table_binary),
            BinaryField("fingerColorTable", finger_color_table, finger_color_table_binary),
            BinaryField("reserved", [0, 0], self._reserved_bytes()),
            BinaryField("songDuration_ms", self.song_duration_ms, self._song_duration_bytes()),
            BinaryField("object_count", len(self.objects), self._object_count_bytes()),
        ]

    def _unique_id_bytes(self):
        return bytes.fromhex(self.unique_id.ljust(64, "0"))[:32]

    def _timestamp_bytes(self):
        return struct.pack("<I", self.timestamp)

    def _name_bytes(self):
        return sanitize_string(self.name, 64)

    def _song_play_style_bytes(self):
        return sanitize_string(self.song_play_style, 16)

    def _reserved_bytes(self):
        return struct.pack("BB", 0, 0)

    def _song_duration_bytes(self):
        return struct.pack("<I", self.song_duration_ms)

    def _object_count_bytes(self):
        return struct.pack("<I", len(self.objects))

    def to_bytes(self):
        header_members = self.iter_header_binary_members()
        return b"".join(
            [member.binary_value for member in header_members]
            + [song_object.to_bytes() for song_object in self.objects]
        )
