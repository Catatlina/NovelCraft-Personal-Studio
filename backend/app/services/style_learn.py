"""M3: Style learning + similarity check for imitation prevention."""
from __future__ import annotations


def learn_style(samples: list[str]) -> dict:
    """Extract style card from sample texts. Returns statistical features only."""
    if not samples:
        return {}

    total_chars = sum(len(s) for s in samples)
    # Statistical features (no raw text copying)
    style_card = {
        "avg_sentence_length": _avg_sentence_len(samples),
        "total_samples": len(samples),
        "total_chars": total_chars,
        "estimated_tokens": total_chars // 2,
        "dialogue_ratio": _dialogue_ratio(samples),
        "paragraph_density": _paragraph_density(samples),
    }
    # Extract common motifs via word frequency (top 10)
    motifs = _extract_motifs(samples, top_n=10)
    if motifs:
        style_card["common_motifs"] = motifs
    return style_card


def check_similarity(original: str, generated: str) -> dict:
    """Check similarity between original and generated text. Returns score and verdict."""
    # Normalized 5-gram overlap
    orig_grams = _ngrams(original, 5)
    gen_grams = _ngrams(generated, 5)
    if not orig_grams or not gen_grams:
        return {"similarity": 0.0, "verdict": "pass", "action": "none"}

    overlap = len(orig_grams & gen_grams)
    ngram_sim = overlap / max(len(orig_grams), 1)

    # Character-level similarity (simplified cosine)
    char_sim = _char_overlap(original, generated)

    sim = max(ngram_sim, char_sim)

    if sim >= 0.75:
        verdict, action = "blocked", "强制重写"
    elif sim >= 0.6:
        verdict, action = "warning", "人工确认"
    else:
        verdict, action = "pass", "放行"

    return {"similarity": round(sim, 4), "verdict": verdict, "action": action,
            "ngram_similarity": round(ngram_sim, 4), "char_similarity": round(char_sim, 4)}


def _avg_sentence_len(samples: list[str]) -> float:
    sentences = []
    for s in samples:
        sentences.extend([x.strip() for x in s.replace("！","。").replace("？","。").replace("！","。").split("。") if x.strip()])
    return round(sum(len(s) for s in sentences) / max(len(sentences), 1), 1)


def _dialogue_ratio(samples: list[str]) -> float:
    dialogue_chars = sum(s.count("「") + s.count("」") + s.count("\"") + s.count("：") for s in samples)
    total = max(sum(len(s) for s in samples), 1)
    return round(dialogue_chars / total, 3)


def _paragraph_density(samples: list[str]) -> float:
    paras = sum(len(s.split("\n\n")) for s in samples)
    return round(paras / max(len(samples), 1), 1)


def _extract_motifs(samples: list[str], top_n: int = 10) -> list[str]:
    """Extract common 2-char motifs."""
    from collections import Counter
    counter = Counter()
    for s in samples:
        for i in range(len(s) - 1):
            bigram = s[i:i+2]
            if bigram.strip() and not bigram[0].isspace() and not bigram[1].isspace():
                counter[bigram] += 1
    return [w for w, _ in counter.most_common(top_n)]


def _ngrams(text: str, n: int) -> set:
    chars = text.replace(" ", "").replace("\n", "")
    return {chars[i:i+n] for i in range(len(chars) - n + 1)} if len(chars) >= n else set()


def _char_overlap(a: str, b: str) -> float:
    set_a = set(a.replace(" ", ""))
    set_b = set(b.replace(" ", ""))
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / max(len(set_a | set_b), 1)
