# Hybrid Knowledge Graph Extraction Architecture

A technical reference for implementing subject-predicate-object triplet extraction using a combination of neural NER (GliNER) and regex pattern matching.

---

## Overview

This hybrid approach achieves **91.89% F1 score** on conversational text by combining:

1. **Pattern Matching** (high precision) - Regex rules for common conversational structures
2. **GliNER Neural NER** (high recall) - ONNX model for named entity recognition

Pattern matching runs first and takes priority. GliNER fills gaps for named entities that patterns miss.

---

## Performance Comparison

| Extractor | Precision | Recall | F1 Score |
|-----------|-----------|--------|----------|
| GliNER only | 52.63% | 52.63% | 52.63% |
| Patterns only | 93.75% | 78.95% | 85.71% |
| **Hybrid** | **94.44%** | **89.47%** | **91.89%** |

---

## Data Structures

### Triplet

```rust
pub struct Triplet {
    pub subject: String,           // Entity 1 (e.g., "I", "Alice", "My API key")
    pub predicate: String,         // Relationship (e.g., "prefer", "is", "work at")
    pub object: String,            // Entity 2 (e.g., "dark mode", "engineer", "Google")
    pub confidence: f32,           // 0.0 - 1.0
    pub source_span: (usize, usize), // Character offsets in original text
}
```

---

## Component 1: Pattern Matching

### Why Patterns?

GliNER (trained on formal NER datasets) struggles with:
- Pronouns ("I", "you", "my")
- Possessive phrases ("My name is", "My API key is")
- Preference statements ("I prefer", "I like")
- Informal relationships ("X is my Y")

Patterns handle these with near-perfect precision.

### Pattern Rules

```rust
// 1. "I prefer X" / "I like X" / "I love X" / "I use X"
r"(?i)\bI\s+(prefer|like|love|enjoy|use|want|need)\s+(.+?)(?:\.|$)"
// Example: "I prefer dark mode" → (I, prefer, dark mode)

// 2. "I am a X" / "I'm a X"
r"(?i)\bI(?:'m|\s+am)\s+(?:a\s+)?(.+?)(?:\.|$)"
// Example: "I am a software engineer" → (I, am, software engineer)

// 3. "I work at X" / "I work for X"
r"(?i)\bI\s+work\s+(at|for)\s+(.+?)(?:\.|$)"
// Example: "I work at Google" → (I, work at, Google)

// 4. "I live in X"
r"(?i)\bI\s+live\s+in\s+(.+?)(?:\.|$)"
// Example: "I live in Seattle" → (I, live in, Seattle)

// 5. "My X is Y" (name, API key, favorite, etc.)
r"(?i)\bMy\s+(\w+(?:\s+\w+)?)\s+is\s+(.+?)(?:\.|$)"
// Example: "My name is Alice" → (My name, is, Alice)
// Example: "My API key is sk-1234" → (My API key, is, sk-1234)

// 6. "My favorite X is Y"
r"(?i)\bMy\s+favorite\s+(\w+)\s+is\s+(.+?)(?:\.|$)"
// Example: "My favorite language is Rust" → (My favorite language, is, Rust)

// 7. "X is my Y" (relationships)
r"(?i)\b(\w+)\s+is\s+my\s+(.+?)(?:\.|$)"
// Example: "Alice is my manager" → (Alice, is, my manager)

// 8. "The X is Y" (constants, settings)
r"(?i)\bThe\s+(\w+(?:\s+\w+)?)\s+is\s+(.+?)(?:\.|$)"
// Example: "The database URL is postgres://..." → (database URL, is, postgres://...)

// 9. "Use X for Y" / "Use port X"
r"(?i)\bUse\s+(?:port\s+)?(\S+)\s+(?:for\s+)?(.+?)(?:\.|$)"
// Example: "Use port 8080 for the server" → (server, uses port, 8080)

// 10. "X uses Y" / "X prefers Y" (projects, tools)
r"(?i)\b(?:my\s+)?(\w+(?:\s+project)?)\s+(uses|prefers|requires)\s+(.+?)(?:\.|$)"
// Example: "My project uses React" → (project, uses, React)
```

### Pattern Implementation

```rust
struct ConversationalPattern {
    regex: Regex,
    extractor: fn(&Captures, &str) -> Option<Triplet>,
    confidence: f32,  // Typically 0.85-0.90
}

impl PatternMatcher {
    pub fn extract_triplets(&self, text: &str) -> Vec<Triplet> {
        let mut triplets = Vec::new();
        let mut seen_spans: Vec<(usize, usize)> = Vec::new();

        for pattern in &self.patterns {
            for caps in pattern.regex.captures_iter(text) {
                if let Some(triplet) = (pattern.extractor)(&caps, text) {
                    // Avoid overlapping extractions
                    let dominated = seen_spans.iter().any(|(s, e)| {
                        triplet.source_span.0 >= *s && triplet.source_span.1 <= *e
                    });
                    if !dominated {
                        seen_spans.push(triplet.source_span);
                        triplets.push(triplet);
                    }
                }
            }
        }
        triplets
    }
}
```

---

## Component 2: GliNER Neural NER

### Model

- **Model**: `gliner_small-v2.1` (ONNX format)
- **Source**: https://huggingface.co/onnx-community/gliner_small-v2.1
- **License**: Apache 2.0
- **Size**: ~50MB

### Entity Labels

```rust
vec![
    // Traditional NER
    "person",
    "organization",
    "location",
    // Technical
    "software",
    "programming language",
    "technology",
    // Conversational
    "preference",
    "setting",
    "value",
    "identifier",
    "project",
    "tool",
]
```

### GliNER Extraction Logic

GliNER returns entity spans with labels and confidence scores. Triplets are formed by:

1. Run inference to get all entity spans
2. For each pair of entities (e1, e2) where e1 appears before e2:
3. Extract text between them as the predicate
4. Confidence = average of both entity confidences

```rust
pub fn extract_triplets(&self, text: &str) -> Result<Vec<Triplet>> {
    let input = TextInput::new(vec![text.to_string()], labels)?;
    let output = self.engine.inference(input)?;

    let mut triplets = Vec::new();

    if let Some(entities) = output.spans.first() {
        for i in 0..entities.len() {
            for j in 0..entities.len() {
                if i == j { continue; }

                let e1 = &entities[i];
                let e2 = &entities[j];
                let (e1_start, e1_end) = e1.offsets();
                let (e2_start, e2_end) = e2.offsets();

                // e1 must come before e2
                if e1_start < e2_start {
                    let predicate = text[e1_end..e2_start].trim().to_string();
                    if !predicate.is_empty() {
                        triplets.push(Triplet {
                            subject: e1.text().to_string(),
                            predicate,
                            object: e2.text().to_string(),
                            confidence: (e1.probability() + e2.probability()) / 2.0,
                            source_span: (e1_start, e2_end),
                        });
                    }
                }
            }
        }
    }
    Ok(triplets)
}
```

---

## Component 3: Hybrid Combiner

### Strategy

1. Run pattern matching first (high precision)
2. Run GliNER second (catches named entities)
3. Deduplicate based on span overlap and semantic similarity
4. Pattern results take priority over GliNER

### Deduplication Logic

```rust
pub fn extract_triplets(&self, text: &str) -> Result<Vec<Triplet>> {
    // Pattern matching first
    let pattern_triplets = self.patterns.extract_triplets(text);

    // GliNER second
    let gliner_triplets = self.gliner.extract_triplets(text)?;

    // Merge, avoiding duplicates
    let mut final_triplets = pattern_triplets.clone();

    for gt in gliner_triplets {
        let dominated = pattern_triplets.iter().any(|pt| {
            spans_overlap(pt.source_span, gt.source_span)
                || triplets_similar(pt, &gt)
        });

        if !dominated {
            final_triplets.push(gt);
        }
    }

    // Sort by position
    final_triplets.sort_by_key(|t| t.source_span.0);
    Ok(final_triplets)
}

fn spans_overlap(a: (usize, usize), b: (usize, usize)) -> bool {
    let overlap_start = a.0.max(b.0);
    let overlap_end = a.1.min(b.1);
    if overlap_start >= overlap_end { return false; }

    let overlap_len = overlap_end - overlap_start;
    let a_len = a.1 - a.0;
    let b_len = b.1 - b.0;

    // >50% overlap = duplicate
    overlap_len * 2 > a_len || overlap_len * 2 > b_len
}

fn triplets_similar(a: &Triplet, b: &Triplet) -> bool {
    fuzzy_eq(&a.subject, &b.subject) && fuzzy_eq(&a.object, &b.object)
}

fn fuzzy_eq(a: &str, b: &str) -> bool {
    let a_lower = a.to_lowercase();
    let b_lower = b.to_lowercase();
    a_lower == b_lower || a_lower.contains(&b_lower) || b_lower.contains(&a_lower)
}
```

---

## Rust Dependencies

```toml
[dependencies]
ort = { version = "2.0.0-rc.9", features = ["load-dynamic"] }
gline-rs = { version = "1.0.1", features = ["load-dynamic"] }
regex = "1.10"
```

Also requires `onnxruntime.dll` (Windows) or `libonnxruntime.so` (Linux) at runtime.

---

## Model Download

```rust
// Download from HuggingFace on first run
let model_url = "https://huggingface.co/onnx-community/gliner_small-v2.1/resolve/main/onnx/model.onnx";
let tokenizer_url = "https://huggingface.co/onnx-community/gliner_small-v2.1/resolve/main/tokenizer.json";

// Store locally
let model_dir = dirs::home_dir().unwrap().join(".myapp/models/gliner_small-v2.1");
```

---

## Benchmarking

Create test cases as JSON:

```json
[
  {
    "id": "pref-dark-mode",
    "text": "I prefer dark mode",
    "expected": [
      { "subject": "I", "predicate": "prefer", "object": "dark mode" }
    ]
  }
]
```

Measure precision, recall, F1:

```
Precision = TP / (TP + FP)
Recall = TP / (TP + FN)
F1 = 2 * (P * R) / (P + R)
```

Use fuzzy matching for evaluation (case-insensitive, substring containment).

---

## When to Use Each Approach

| Text Type | Best Approach |
|-----------|---------------|
| Conversational ("I prefer...", "My name is...") | Patterns |
| Formal documents with named entities | GliNER |
| Mixed content | Hybrid |
| Domain-specific (legal, medical) | Custom patterns + fine-tuned NER |

---

## Future Improvements

1. **Add more patterns** as you discover common user phrases
2. **Predicate normalization** - Clean extracted predicates (remove punctuation, normalize verbs)
3. **Confidence calibration** - Weight pattern confidence vs GliNER confidence
4. **Larger GliNER model** - `gliner_medium-v2.1` or `gliner_large-v2.1` for better recall
5. **Sentence boundary detection** - Prevent patterns from capturing across sentences
