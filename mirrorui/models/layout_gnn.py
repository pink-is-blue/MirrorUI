from __future__ import annotations

from typing import List
import torch
from torch import nn


class LayoutGraphEncoder(nn.Module):
    def __init__(self, in_dim: int = 32, hidden_dim: int = 64, layers: int = 2):
        super().__init__()
        self.layers = nn.ModuleList()
        self.layers.append(nn.Linear(in_dim, hidden_dim))
        for _ in range(max(0, layers - 1)):
            self.layers.append(nn.Linear(hidden_dim, hidden_dim))
        self.activation = nn.GELU()

    def forward(self, node_features: torch.Tensor) -> torch.Tensor:
        x = node_features
        for layer in self.layers:
            x = self.activation(layer(x))
        return x

    def encode(self, feature_rows: List[List[float]]) -> List[float]:
        if not feature_rows:
            return []
        x = torch.tensor(feature_rows, dtype=torch.float32)
        with torch.no_grad():
            out = self.forward(x)
        return out.mean(dim=0).tolist()
