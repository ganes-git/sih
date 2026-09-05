"""
Vehicle Visual Appearance Embedding Module (Stage 4)
Extracts fixed-length (512-D) visual appearance embeddings from vehicle crops using OpenCLIP.
Inference only, no fine-tuning or training required.

This module provides the secondary identity signal that maintains trajectory continuity
when plate reading is impaired or unavailable.
"""

from typing import List, Optional, Union
import cv2
import numpy as np
import torch
from PIL import Image
import open_clip


class VehicleEmbedder:
    """Extracts L2-normalized visual appearance feature vectors from vehicle crops."""

    def __init__(
        self,
        model_name: str = "ViT-B-32",
        pretrained: str = "laion2b_s34b_b79k",
        device: Optional[str] = None,
    ):
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        self.model, _, self.preprocess = open_clip.create_model_and_transforms(
            model_name, pretrained=pretrained
        )
        self.model.to(self.device)
        self.model.eval()

        # Fixed feature dimension (512 for ViT-B-32)
        self.embedding_dim = 512

    def embed_crop(self, crop_bgr: np.ndarray) -> List[float]:
        """
        Compute an L2-normalized 512-dimensional visual embedding for a vehicle crop.

        Args:
            crop_bgr: OpenCV BGR image array of the vehicle crop.

        Returns:
            List of 512 floats (JSON-serialisable).
        """
        if crop_bgr is None or crop_bgr.size == 0:
            return [0.0] * self.embedding_dim

        # Convert OpenCV BGR to PIL RGB image
        rgb_img = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb_img)

        # Preprocess and add batch dimension
        tensor = self.preprocess(pil_img).unsqueeze(0).to(self.device)

        with torch.no_grad():
            features = self.model.encode_image(tensor)
            # L2 normalize so cosine similarity equals dot product
            features = features / features.norm(dim=-1, keepdim=True)

        return features.squeeze(0).cpu().tolist()

    def embed_batch(self, crops_bgr: List[np.ndarray]) -> List[List[float]]:
        """Compute embeddings for a batch of vehicle crops."""
        if not crops_bgr:
            return []

        tensors = []
        valid_indices = []

        for idx, crop in enumerate(crops_bgr):
            if crop is not None and crop.size > 0:
                rgb_img = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(rgb_img)
                tensors.append(self.preprocess(pil_img))
                valid_indices.append(idx)

        if not tensors:
            return [[0.0] * self.embedding_dim for _ in crops_bgr]

        batch_tensor = torch.stack(tensors).to(self.device)
        with torch.no_grad():
            features = self.model.encode_image(batch_tensor)
            features = features / features.norm(dim=-1, keepdim=True)

        feature_list = features.cpu().tolist()
        result = [[0.0] * self.embedding_dim for _ in crops_bgr]
        for src_idx, orig_idx in enumerate(valid_indices):
            result[orig_idx] = feature_list[src_idx]

        return result


def compute_cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """
    Compute cosine similarity between two L2-normalized embedding vectors.
    Returns float in [-1.0, 1.0], clamped to [0.0, 1.0] for similarity scoring.
    """
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0
    v1 = np.array(vec1, dtype=np.float32)
    v2 = np.array(vec2, dtype=np.float32)
    dot = float(np.dot(v1, v2))
    return max(0.0, min(1.0, dot))


def load_embedder(device: Optional[str] = None) -> VehicleEmbedder:
    """Factory helper to instantiate VehicleEmbedder."""
    return VehicleEmbedder(device=device)
