"""
Vehicle Sighting Data Model (Stage 4)
Defines the canonical data model for a unified vehicle sighting event across the camera network.
"""

from typing import List, Optional
from pydantic import BaseModel, Field
import uuid
import time


class Sighting(BaseModel):
    """
    Unified representation of a vehicle sighting event at a specific camera location and timestamp.
    Combines plate recognition, OpenCLIP appearance embedding, and spatio-temporal coordinates.
    """

    sighting_id: str = Field(
        default_factory=lambda: f"SGT_{uuid.uuid4().hex[:10].upper()}",
        description="Unique identifier for the sighting event.",
    )
    camera_id: str = Field(..., description="Capturing camera identifier (e.g. CAM_01).")
    lat: float = Field(..., description="GPS latitude of camera.")
    lon: float = Field(..., description="GPS longitude of camera.")
    timestamp: float = Field(
        default_factory=time.time,
        description="POSIX epoch timestamp (in seconds) of capture.",
    )
    plate_text: Optional[str] = Field(
        None,
        description="Confirmed normalized plate text (e.g. 'TN 07 AB 1234'), or None if unconfirmed.",
    )
    plate_confidence: Optional[float] = Field(
        None,
        description="Multi-frame OCR confidence score (0.0 to 1.0), or None.",
    )
    embedding: List[float] = Field(
        ...,
        description="512-dimensional L2-normalized visual appearance feature vector.",
    )
    snapshot_path: Optional[str] = Field(
        None,
        description="File path to vehicle snapshot crop.",
    )
    unconfirmed_plate: bool = Field(
        False,
        description="True if plate reading was unconfirmed or rejected by threshold.",
    )

    # Convenience aliases for latitude and longitude
    @property
    def latitude(self) -> float:
        return self.lat

    @property
    def longitude(self) -> float:
        return self.lon
