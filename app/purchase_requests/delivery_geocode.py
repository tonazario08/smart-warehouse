"""Bounded, offline search of a curated OSM regional index. No network or query storage."""

import json
import re
import unicodedata
from collections import defaultdict
from functools import cached_property
from hashlib import sha256
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

INDEX_LIMIT = 20 * 1024 * 1024
REGION = (106.35, 10.30, 107.10, 11.20)
SOURCES = frozenset({
    "https://overpass-api.de/api/interpreter",
    "https://download.geofabrik.de/asia/vietnam.html",
    "https://download.bbbike.org/osm/bbbike/Saigon/",
    "https://download.bbbike.org/osm/bbbike/Saigon/Saigon.osm.gz",
})
HOUSE = re.compile(r"[0-9]{1,7}[a-z]?(?:[/.-][0-9]{1,7}[a-z]?)*")
CITY = frozenset({
    "tp hcm", "tphcm", "ho chi minh", "thanh pho ho chi minh", "tp ho chi minh",
    "sai gon", "viet nam", "vietnam",
})


def fold(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value.casefold().replace("đ", "d"))
    return re.sub(r"[^a-z0-9/.-]+", " ", "".join(
        char for char in folded if not unicodedata.combining(char)
    )).strip()


def name_key(value: str) -> str:
    return " ".join(re.sub(r"[/.-]+", " ", fold(value)).split())


def street_key(value: str) -> str:
    return re.sub(r"^duong +", "", name_key(value))


def area_key(value: str) -> str:
    key = name_key(value)
    return re.sub(r"^q +(?=\d)", "quan ", re.sub(r"^p +(?=\d)", "phuong ", key))


class GeocodeAddressBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    address: str = Field(min_length=2, max_length=300, strict=True)


class Candidate(BaseModel):
    label: str
    latitude: float
    longitude: float
    precision: Literal["house_number", "approximate"]


class GeocodeResult(BaseModel):
    status: Literal["matches", "no_match", "unavailable"]
    candidates: list[Candidate] = Field(default_factory=list)


class _Entry(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    street: str = Field(min_length=2, max_length=160)
    house_number: str | None = Field(default=None, max_length=40)
    local_area: str | None = Field(default=None, max_length=160)
    latitude: float = Field(allow_inf_nan=False)
    longitude: float = Field(allow_inf_nan=False)

    def candidate(self) -> Candidate:
        label = f"{self.house_number} {self.street}" if self.house_number else self.street
        if self.local_area:
            label += f", {self.local_area}"
        return Candidate(
            label=label, latitude=self.latitude, longitude=self.longitude,
            precision="house_number" if self.house_number else "approximate",
        )


class _Index(BaseModel):
    model_config = ConfigDict(extra="forbid")
    format: Literal["b2b-osm-address-v1"]
    source_url: str
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    bounds: tuple[float, float, float, float]
    entries: list[_Entry] = Field(min_length=1, max_length=100_000)


class DeliveryGeocoder:
    def __init__(self, path: Path | None, expected_digest: str | None = None) -> None:
        self.path = path
        self.expected_digest = expected_digest

    @cached_property
    def _streets(self) -> dict[str, tuple[_Entry, ...]] | None:
        if self.path is None:
            return None
        try:
            with self.path.open("rb") as stream:
                contents = stream.read(INDEX_LIMIT + 1)
            if len(contents) > INDEX_LIMIT:
                return None
            if self.expected_digest is not None:
                if sha256(contents).hexdigest() != self.expected_digest:
                    return None
            index = _Index.model_validate(json.loads(contents))
            west, south, east, north = index.bounds
            if index.source_url not in SOURCES or not (
                REGION[0] <= west < east <= REGION[2] and REGION[1] <= south < north <= REGION[3]
            ):
                return None
            groups: dict[str, list[_Entry]] = defaultdict(list)
            for entry in index.entries:
                if not (west <= entry.longitude <= east and south <= entry.latitude <= north):
                    return None
                key = street_key(entry.street)
                if key and (not entry.house_number or HOUSE.fullmatch(fold(entry.house_number))):
                    groups[key].append(entry)
            return {key: tuple(rows) for key, rows in groups.items()} or None
        except (OSError, ValueError):
            return None

    def find(self, address: str) -> GeocodeResult:
        streets = self._streets
        if streets is None:
            return GeocodeResult(status="unavailable")
        first, *rest = [fold(part).strip(".") for part in address.split(",")]
        areas = {area_key(part) for part in rest if part and area_key(part) not in CITY}
        whole = street_key(first)
        number = None
        if whole not in streets and " " in first:
            leading, trailing = first.split(" ", 1)
            if HOUSE.fullmatch(leading):
                number, whole = leading, street_key(trailing)
        houses, roads = [], []
        for entry in streets.get(whole, ()):
            if areas:
                known_areas = {area_key(part) for part in (entry.local_area or "").split(",")}
                if not areas.issubset(known_areas):
                    continue
            if entry.house_number is None:
                roads.append(entry)
            elif number and fold(entry.house_number) == number:
                houses.append(entry)
        # Never pick the first match for the client. Bound returned candidates,
        # and fail closed rather than hiding ambiguity in a truncated result.
        matches = houses or roads
        candidates = {
            (entry.latitude, entry.longitude, entry.candidate().label): entry.candidate()
            for entry in matches
        }
        if not 1 <= len(candidates) <= 8:
            return GeocodeResult(status="no_match")
        return GeocodeResult(
            status="matches", candidates=[candidates[key] for key in sorted(candidates)]
        )
