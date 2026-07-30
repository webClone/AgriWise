"""
Layer 5 Genetical Engine — Host-Pathogen Interaction & Susceptibility AI Model (v7.0)

Predicts genomic vulnerability based on host resistance (PRRs and NBS-LRRs)
vs pathogen virulence (PAMPs and effectors) and Host-Induced Gene Silencing (HIGS).
Uses a simulated Multi-Head Attention ML model to calculate ligand-receptor recognition
specificity and compute final susceptibility logits.

Scientific References:
1. Jones, J. D., & Dangl, J. L. (2006). The plant immune system. Nature, 444(7117), 323-329.
   - Outlines the zigzag model of plant immunity: PRR-mediated PTI and NBS-LRR-mediated ETI.
2. Baulcombe, D. (2004). RNA silencing in plants. Nature, 431(7006), 356-363.
   - Details the mechanisms of RNA interference and HIGS in plant-pathogen interactions.
3. Vaswani, A., et al. (2017). Attention is all you need. Advances in neural information processing systems, 30.
   - Establishes the Multi-Head Attention mechanism used to map cross-layer genetic tokens.
"""

from typing import Dict, List, Any, Optional
import math
from layer5_bio.schema import ThreatId, EvidenceLogit
from layer3_decision.schema import Driver

# ── PTI and ETI Genetic Repositories ────────────────────────────────────────

# Host Pattern Recognition Receptors (PRRs) detecting Pathogen-Associated Molecular Patterns (PAMPs)
# Mapped as baseline immunity (PAMP-Triggered Immunity / PTI)
HOST_PRR_REGISTRY: Dict[str, List[str]] = {
    "wheat": ["FLS2", "EFR", "LYK5"],
    "maize": ["FLS2", "BAK1"],
    "citrus": ["FLS2", "LORE"],
    "tomato": ["FLS2", "EFR", "CORE", "FLS3"],
}

PATHOGEN_PAMP_REGISTRY: Dict[ThreatId, List[str]] = {
    ThreatId.FUNGAL_LEAF_SPOT: ["Chitin", "Beta-glucan"],
    ThreatId.FUNGAL_RUST: ["Chitin", "Basidiomycete_PAMP"],
    ThreatId.DOWNY_MILDEW: ["Beta-glucan", "Oomycete_cellulose"],
    ThreatId.POWDERY_MILDEW: ["Chitin", "Ascomycete_PAMP"],
    ThreatId.BACTERIAL_BLIGHT: ["flg22", "elf18", "csp22"],
    ThreatId.CHEWING_INSECTS: ["Volcitin", "Insect_derived_elicitin"],
    ThreatId.SUCKING_INSECTS: ["Saliva_elicitin"],
    ThreatId.BORERS: ["Frass_PAMP"],
    ThreatId.WEED_PRESSURE: ["DAMP_damage_associated"],
}

# Host NBS-LRR R-Gene Profiles (Effector-Triggered Immunity / ETI)
VARIETY_R_GENE_PROFILES: Dict[str, List[str]] = {
    # Wheat varieties
    "giza 168": ["Lr34", "Sr2", "Yr18", "Pm3"],
    "egypt 1": ["Lr34", "Yr18"],
    "sids 12": ["Sr2", "Pm3"],
    "misr 1": ["Lr34", "Sr2", "Yr18"],
    "sakha 93": ["Lr13", "Sr31", "Yr9"],
    
    # Maize varieties
    "pioneer 30g30": ["Ht1", "Ht2", "Rpp1"],
    "dkc 6777": ["Ht1", "Rpp1"],
    "sc 10": ["Ht2"],
    
    # Citrus varieties
    "navelina": ["Xantho_R1", "Cs_R_gene"],
    "valencia": ["Xantho_R1"],
    "shamouti": ["Cs_R_gene"],
    
    # Tomato varieties
    "marmande": ["I-2", "Ve1", "Ve2", "Mi-1"],
    "roma": ["Ve1", "Ve2"],
    "san marzano": ["I-2", "Mi-1"],
}

# Pathogen Effector Profiles (Virulence factors targeting host cell proteins)
PATHOGEN_EFFECTOR_PROFILES: Dict[ThreatId, List[str]] = {
    ThreatId.FUNGAL_LEAF_SPOT: ["Avr-Lr34", "Avr-Pm3", "Fungal_effector_FLS1"],
    ThreatId.FUNGAL_RUST: ["Avr-Sr2", "Avr-Yr18", "Avr-Sr31", "Avr-Yr9", "Haustorial_effector_R1", "Avr-Rps1a", "Avr-Rps3a"],
    ThreatId.DOWNY_MILDEW: ["Avr-Rpp1", "Oomycete_effector_A", "RxLR_effector_DM1"],
    ThreatId.POWDERY_MILDEW: ["Avr-Pm3", "Mildew_effector_M1", "CSEPs_effector"],
    ThreatId.BACTERIAL_BLIGHT: ["Avr-Xantho_R1", "Avr-Cs_R_gene", "TAL_effector_T1", "Type_III_effector_B1"],
    ThreatId.CHEWING_INSECTS: ["Bt_cry1Ac_resistance", "Insect_gut_protease"],
    ThreatId.SUCKING_INSECTS: ["Insect_saliva_effector"],
    ThreatId.BORERS: ["Borer_digestive_amylase"],
    ThreatId.WEED_PRESSURE: ["Herbicide_target_mutant"],
}

# Host-Induced Gene Silencing (HIGS) Target Registry
# If the variety expresses RNAi target matching pathogen housekeeping genes
HOST_HIGS_TARGETS: Dict[str, List[str]] = {
    "wheat": ["chitin_synthase_A", "beta_tubulin"],
    "tomato": ["dicer_like_pathogen", "ribosomal_protein_L4"],
}

PATHOGEN_ESSENTIAL_GENES: Dict[ThreatId, List[str]] = {
    ThreatId.FUNGAL_LEAF_SPOT: ["chitin_synthase_A", "beta_tubulin"],
    ThreatId.FUNGAL_RUST: ["chitin_synthase_A", "translation_elongation_factor"],
    ThreatId.DOWNY_MILDEW: ["oomycete_cellulose_synthase", "beta_tubulin"],
    ThreatId.POWDERY_MILDEW: ["chitin_synthase_A", "cytoskeletal_actin"],
    ThreatId.BACTERIAL_BLIGHT: ["rna_polymerase_beta", "gyrase_A"],
}

# Genetic vocabulary token embeddings (4-dimensional mapping for simulated Multi-Head Attention)
GENETIC_VOCAB_EMBEDDINGS: Dict[str, List[float]] = {
    # Host PRRs
    "FLS2": [0.35, 0.40, -0.20, 0.60],
    "EFR": [0.30, 0.35, -0.15, 0.55],
    "LYK5": [0.45, 0.20, -0.30, 0.50],
    "BAK1": [0.25, 0.50, -0.10, 0.65],
    "LORE": [0.15, 0.30, -0.25, 0.45],
    "CORE": [0.40, 0.30, -0.20, 0.50],
    "FLS3": [0.38, 0.38, -0.18, 0.58],

    # Pathogen PAMPs
    "Chitin": [-0.30, -0.45, 0.25, -0.50],
    "Beta-glucan": [-0.25, -0.40, 0.20, -0.45],
    "Basidiomycete_PAMP": [-0.35, -0.38, 0.15, -0.48],
    "Oomycete_cellulose": [-0.20, -0.35, 0.30, -0.40],
    "flg22": [-0.40, -0.50, 0.10, -0.60],
    "elf18": [-0.35, -0.45, 0.08, -0.55],
    "csp22": [-0.30, -0.40, 0.12, -0.50],
    "Volcitin": [-0.15, -0.30, 0.35, -0.35],
    "Insect_derived_elicitin": [-0.20, -0.25, 0.40, -0.30],
    "Saliva_elicitin": [-0.18, -0.28, 0.38, -0.32],
    "Frass_PAMP": [-0.10, -0.20, 0.45, -0.25],
    "DAMP_damage_associated": [-0.05, -0.15, 0.50, -0.10],

    # Host R-genes
    "Lr34": [0.85, -0.15, 0.45, 0.20],
    "Sr2": [0.12, 0.90, -0.30, 0.40],
    "Yr18": [0.75, -0.20, 0.50, 0.15],
    "Pm3": [0.30, 0.40, 0.80, -0.10],
    "Lr13": [0.50, -0.10, 0.30, 0.60],
    "Sr31": [0.10, 0.85, -0.20, 0.30],
    "Yr9": [0.60, -0.30, 0.40, 0.20],
    "Ht1": [0.90, 0.10, 0.20, -0.30],
    "Ht2": [0.80, 0.20, 0.10, -0.40],
    "Rpp1": [-0.10, 0.70, 0.60, 0.20],
    "Xantho_R1": [0.20, -0.80, 0.90, 0.10],
    "Cs_R_gene": [0.15, -0.75, 0.85, 0.20],
    "I-2": [0.45, 0.45, 0.50, 0.50],
    "Ve1": [0.30, 0.60, -0.10, 0.70],
    "Ve2": [0.25, 0.65, -0.15, 0.75],
    "Mi-1": [-0.50, 0.80, 0.30, -0.20],
    
    # Pathogen effectors/virulence factors
    "Avr-Lr34": [-0.80, 0.20, -0.40, -0.10],
    "Avr-Pm3": [-0.25, -0.35, -0.75, 0.15],
    "Avr-Sr2": [-0.10, -0.85, 0.25, -0.35],
    "Avr-Yr18": [-0.70, 0.25, -0.45, -0.10],
    "Avr-Sr31": [-0.05, -0.80, 0.15, -0.25],
    "Avr-Yr9": [-0.55, 0.35, -0.35, -0.15],
    "Avr-Rpp1": [0.15, -0.65, -0.55, -0.15],
    "Oomycete_effector_A": [-0.30, 0.40, -0.40, 0.50],
    "Mildew_effector_M1": [-0.10, -0.20, 0.50, -0.60],
    "Avr-Xantho_R1": [-0.15, 0.75, -0.85, -0.05],
    "Avr-Cs_R_gene": [-0.10, 0.70, -0.80, -0.15],
    "TAL_effector_T1": [-0.40, 0.50, -0.50, 0.40],
    "Bt_cry1Ac_resistance": [0.60, 0.60, -0.20, -0.20],
    "Insect_gut_protease": [-0.20, 0.30, 0.70, -0.50],
    "Insect_saliva_effector": [0.10, -0.30, 0.80, -0.20],
    "Borer_digestive_amylase": [0.30, 0.20, -0.60, 0.50],
    "Herbicide_target_mutant": [-0.50, -0.50, 0.50, 0.50],
    "Fungal_effector_FLS1": [-0.35, -0.40, 0.10, -0.45],
    "Haustorial_effector_R1": [-0.45, -0.10, 0.35, -0.30],
    "RxLR_effector_DM1": [-0.50, 0.10, -0.40, -0.20],
    "CSEPs_effector": [-0.40, -0.30, 0.20, -0.50],
    "Type_III_effector_B1": [-0.48, 0.30, -0.60, 0.10],
    
    # Soybean Legume specific NBS-LRR genes and effectors
    "Rps1a": [0.40, 0.50, 0.40, 0.40],
    "Rps3a": [0.35, 0.55, 0.35, 0.45],
    "Avr-Rps1a": [-0.40, -0.50, -0.40, 0.40],
    "Avr-Rps3a": [-0.35, -0.55, -0.35, 0.45],
}

DEFAULT_EMBEDDING = [0.0, 0.0, 0.0, 0.0]

# ── Simulated Multi-Head Attention AI Classifier ────────────────────────────────

class MultiHeadAttentionGeneticsClassifier:
    """Simulated Multi-Head Cross-Attention neural network modeling ligand-receptor interactions.

    Query (Q): Host receptors (PRRs + R-genes)
    Key (K): Pathogen ligands (PAMPs + Effectors)
    Value (V): Virulence/suppression vectors of pathogen ligands

    Calculates:
      Cross-Attention = Softmax(Q * K_T / sqrt(d_k)) * V
      Followed by LayerNorm and a Feed-Forward network.
    """

    def __init__(self, seed_name: str, embed_dim: int = 4, num_heads: int = 2):
        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads
        
        # Deterministic initialization based on variety + threat seed
        h = sum(ord(c) for c in seed_name)
        
        # Linear projection matrices for Q, K, V
        self.W_q = self._init_matrix(h + 1, embed_dim, embed_dim)
        self.W_k = self._init_matrix(h + 2, embed_dim, embed_dim)
        self.W_v = self._init_matrix(h + 3, embed_dim, embed_dim)
        self.W_o = self._init_matrix(h + 4, embed_dim, embed_dim)
        
        # Feed-forward network (FFN) weights
        self.W1 = self._init_matrix(h + 5, embed_dim, 8)
        self.b1 = [math.sin(h + i) * 0.1 for i in range(8)]
        self.W2 = [math.cos(h + i) * 0.5 for i in range(8)]
        self.b2 = 0.15

    def _init_matrix(self, seed: int, rows: int, cols: int) -> List[List[float]]:
        mat = []
        for r in range(rows):
            row = []
            for c in range(cols):
                row.append(math.sin(seed + r * 1.3 + c * 1.7) * 0.4)
            mat.append(row)
        return mat

    def _matmul(self, vec: List[float], mat: List[List[float]]) -> List[float]:
        out = [0.0] * len(mat[0])
        for c in range(len(mat[0])):
            val = 0.0
            for r in range(len(vec)):
                val += vec[r] * mat[r][c]
            out[c] = val
        return out

    def forward(self, host_embs: List[List[float]], path_embs: List[List[float]]) -> float:
        """Runs the cross-attention layers. Returns susceptibility value in [0, 1]."""
        if not host_embs or not path_embs:
            return 0.5
            
        # 1. Project host embeddings to Q, pathogen embeddings to K, V
        Q_seq = [self._matmul(q, self.W_q) for q in host_embs]
        K_seq = [self._matmul(k, self.W_k) for k in path_embs]
        V_seq = [self._matmul(v, self.W_v) for v in path_embs]
        
        # 2. Compute attention maps per query
        scale = math.sqrt(self.head_dim)
        attention_outs = []
        
        for q in Q_seq:
            # Multi-head attention simulation
            head_outputs = []
            for h_idx in range(self.num_heads):
                h_start = h_idx * self.head_dim
                h_end = h_start + self.head_dim
                
                q_head = q[h_start:h_end]
                
                # Calculate scores (dot product)
                scores = []
                for k in K_seq:
                    k_head = k[h_start:h_end]
                    dot = sum(qi * ki for qi, ki in zip(q_head, k_head))
                    scores.append(dot / scale)
                
                # Softmax
                max_score = max(scores) if scores else 0.0
                exp_scores = [math.exp(s - max_score) for s in scores]
                sum_exp = sum(exp_scores)
                attn_weights = [es / sum_exp for es in exp_scores]
                
                # Weighted sum of values
                out_head = [0.0] * self.head_dim
                for weight, v in zip(attn_weights, V_seq):
                    v_head = v[h_start:h_end]
                    for d in range(self.head_dim):
                        out_head[d] += weight * v_head[d]
                head_outputs.extend(out_head)
                
            # Output projection
            proj_out = self._matmul(head_outputs, self.W_o)
            # Residual connection
            fused = [qi + pi for qi, pi in zip(q, proj_out)]
            attention_outs.append(fused)
            
        # Average attention outputs across sequence length to yield a single representation
        seq_len = len(attention_outs)
        fused_representation = [0.0] * self.embed_dim
        for vec in attention_outs:
            for d in range(self.embed_dim):
                fused_representation[d] += vec[d] / seq_len
                
        # 3. Feed Forward Network (FFN)
        hidden = self._matmul(fused_representation, self.W1)
        hidden_activated = [max(0.0, h_val + b) for h_val, b in zip(hidden, self.b1)]  # ReLU
        
        out_logit = self.b2 + sum(hi * w for hi, w in zip(hidden_activated, self.W2))
        
        # Sigmoid activation to bound output
        susceptibility = 1.0 / (1.0 + math.exp(-max(-10.0, min(10.0, out_logit))))
        return susceptibility


def _get_embedding(name: str) -> List[float]:
    return GENETIC_VOCAB_EMBEDDINGS.get(name, DEFAULT_EMBEDDING)


def run_genetical_engine(
    crop_type: str,
    variety: Optional[str],
    threat_id: ThreatId,
    plot_context: Dict[str, Any]
) -> Dict[str, Any]:
    """Execute advanced Host-Pathogen Interaction & Susceptibility Model.
    
    Models PTI, ETI, and HIGS dynamics, and predicts susceptibility with
    simulated Multi-Head Cross-Attention.
    
    Returns a dict with:
      - susceptibility_score: [0, 1]
      - matching_r_genes: list of matching resistant host genes
      - match_found: bool indicating whether active ETI occurred
      - evidence_logit: EvidenceLogit instance to be injected
    """
    crop_type = (crop_type or "").lower().strip()
    var_key = (variety or "").lower().strip()
    
    # Resolve canonical crop code and architecture class to support 200+ crops
    canonical_crop = crop_type
    arch = "cereal"
    try:
        from crop_database import resolve_crop_code, get_crop
        canonical_crop = resolve_crop_code(crop_type)
        crop_spec = get_crop(canonical_crop)
        if crop_spec:
            arch = crop_spec.architecture
    except Exception:
        # Fallback to structural heuristic if crop_database is not available
        if "wheat" in crop_type:
            arch = "cereal"
        elif "maize" in crop_type or "corn" in crop_type:
            arch = "maize"
        elif "citrus" in crop_type or "orange" in crop_type:
            arch = "perennial"
        elif "tomato" in crop_type:
            arch = "vegetable"
            
    # 1. Resolve PAMPs & PRRs (PAMP-Triggered Immunity / PTI)
    prrs = HOST_PRR_REGISTRY.get(canonical_crop)
    if not prrs:
        if arch in ("cereal", "rice"):
            prrs = ["FLS2", "BAK1", "LYK5"]
        elif arch == "maize":
            prrs = ["FLS2", "BAK1"]
        elif arch == "legume":
            prrs = ["FLS2", "BAK1", "EFR"]
        elif arch in ("vegetable", "cotton"):
            prrs = ["FLS2", "EFR", "CORE", "FLS3"]
        elif arch in ("perennial", "tropical_tree"):
            prrs = ["FLS2", "LORE", "BAK1"]
        else:
            prrs = ["FLS2", "BAK1"]
            
    pamps = PATHOGEN_PAMP_REGISTRY.get(threat_id, [])
    
    # 2. Resolve Host R-genes & Pathogen Effectors (Effector-Triggered Immunity / ETI)
    host_genes = VARIETY_R_GENE_PROFILES.get(var_key)
    if not host_genes:
        if canonical_crop in HOST_PRR_REGISTRY:
            if canonical_crop == "wheat":
                host_genes = VARIETY_R_GENE_PROFILES["egypt 1"]
            elif canonical_crop == "maize":
                host_genes = VARIETY_R_GENE_PROFILES["sc 10"]
            elif canonical_crop == "citrus":
                host_genes = VARIETY_R_GENE_PROFILES["valencia"]
            elif canonical_crop == "tomato":
                host_genes = VARIETY_R_GENE_PROFILES["roma"]
        else:
            if arch in ("cereal", "rice"):
                host_genes = ["Lr34", "Sr2", "Yr18", "Pm3"]
            elif arch == "maize":
                host_genes = ["Ht1", "Ht2", "Rpp1"]
            elif arch == "legume":
                host_genes = ["Rps1a", "Rps3a"]
            elif arch in ("vegetable", "cotton"):
                host_genes = ["Ve1", "Ve2", "I-2"]
            elif arch in ("perennial", "tropical_tree"):
                host_genes = ["Xantho_R1", "Cs_R_gene"]
            else:
                host_genes = []
            
    effectors = PATHOGEN_EFFECTOR_PROFILES.get(threat_id, [])
    
    # 3. Check NBS-LRR gene-for-gene recognition matches (ETI)
    matching_r_genes = []
    for g in host_genes:
        target_avr = f"Avr-{g}"
        if target_avr in effectors:
            matching_r_genes.append(g)
            
    eti_active = len(matching_r_genes) > 0
    
    # 4. Resolve HIGS (Host-Induced Gene Silencing) targeting
    higs_genes = HOST_HIGS_TARGETS.get(canonical_crop)
    if not higs_genes:
        if arch in ("cereal", "rice", "maize"):
            higs_genes = ["chitin_synthase_A", "beta_tubulin"]
        elif arch in ("legume", "vegetable", "cotton"):
            higs_genes = ["dicer_like_pathogen", "ribosomal_protein_L4"]
        else:
            higs_genes = ["chitin_synthase_A", "ribosomal_protein_L4"]
            
    essential_pathogen_genes = PATHOGEN_ESSENTIAL_GENES.get(threat_id, [])
    silenced_genes = [g for g in higs_genes if g in essential_pathogen_genes]
    higs_active = len(silenced_genes) > 0
    
    # 5. Fetch Embeddings for Attention Engine
    host_tokens = prrs + host_genes
    host_embs = [_get_embedding(tok) for tok in host_tokens]
    if not host_embs:
        host_embs = [DEFAULT_EMBEDDING]
        
    path_tokens = pamps + effectors
    path_embs = [_get_embedding(tok) for tok in path_tokens]
    if not path_embs:
        path_embs = [DEFAULT_EMBEDDING]
        
    # 6. Multi-Head Cross-Attention Susceptibility Prediction
    seed_name = f"{canonical_crop}_{var_key}_{threat_id.value}"
    classifier = MultiHeadAttentionGeneticsClassifier(seed_name)
    base_susceptibility = classifier.forward(host_embs, path_embs)
    
    # Apply biological suppression scales
    logit_delta = 0.0
    notes = "No active molecular immunity detected."
    
    # PTI provides a minor constant suppression
    pti_suppression = 0.85 if len(prrs) > 0 and len(pamps) > 0 else 1.0
    susceptibility_score = base_susceptibility * pti_suppression
    
    if eti_active:
        # ETI (gene-for-gene) yields dramatic suppression (e.g. hypersensitive response)
        susceptibility_score *= 0.12
        logit_delta -= 2.2
        notes = f"Effector-Triggered Immunity active: {matching_r_genes} recognizes pathogen. Hypersensitive response triggered."
    elif higs_active:
        # HIGS provides medium-to-strong post-transcriptional gene silencing
        susceptibility_score *= 0.35
        logit_delta -= 1.4
        notes = f"Host-Induced Gene Silencing active: RNAi targets essential pathogen genes {silenced_genes}."
    else:
        # Normal susceptibility mapping to logit delta
        if len(host_genes) > 0:
            logit_delta = (susceptibility_score - 0.5) * 2.0  # range [-1.0, 1.0]
            notes = "Unregulated host susceptibility; pathogen effector virulence active."
            
    # Compile final evidence logit
    evidence = EvidenceLogit(
        driver=Driver.GDD,
        condition=f"Molecular Genetics: {variety or 'Default'} vs {threat_id.value}",
        logit_delta=round(logit_delta, 4),
        weight=0.9,
        source_refs={
            "host_prrs": prrs,
            "pathogen_pamps": pamps,
            "host_r_genes": host_genes,
            "pathogen_effectors": effectors,
            "higs_silenced_targets": silenced_genes,
            "eti_active": eti_active,
            "higs_active": higs_active,
            "susceptibility_score": round(susceptibility_score, 4),
            "notes": notes
        }
    )
    
    return {
        "susceptibility_score": round(susceptibility_score, 4),
        "matching_r_genes": matching_r_genes,
        "match_found": eti_active,
        "evidence_logit": evidence
    }
