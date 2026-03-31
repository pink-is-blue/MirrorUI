from __future__ import annotations

from typing import List
import torch
from torch import nn


class HybridVisionDomTransformer(nn.Module):
    def __init__(self, in_dim: int = 64, hidden_dim: int = 128, heads: int = 4, layers: int = 2, out_dim: int = 64):
        super().__init__()
        self.proj = nn.Linear(in_dim, hidden_dim)
        encoder = nn.TransformerEncoderLayer(d_model=hidden_dim, nhead=heads, batch_first=True)
        decoder = nn.TransformerDecoderLayer(d_model=hidden_dim, nhead=heads, batch_first=True)
        self.encoder = nn.TransformerEncoder(encoder, num_layers=layers)
        self.decoder = nn.TransformerDecoder(decoder, num_layers=layers)
        self.head = nn.Linear(hidden_dim, out_dim)

    def forward(self, src: torch.Tensor, tgt: torch.Tensor) -> torch.Tensor:
        src_proj = self.proj(src)
        tgt_proj = self.proj(tgt)
        memory = self.encoder(src_proj)
        out = self.decoder(tgt_proj, memory)
        return self.head(out)

    def infer_action_latent(self, fused_features: List[List[float]]) -> List[float]:
        if not fused_features:
            return []
        src = torch.tensor([fused_features], dtype=torch.float32)
        tgt = src[:, : min(4, src.shape[1]), :]
        with torch.no_grad():
            logits = self.forward(src, tgt)
        return logits.mean(dim=(0, 1)).tolist()
