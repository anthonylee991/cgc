"""Benchmark: v1 (GliNER+GliREL) vs v2 (GLiNER2) extraction pipelines.

Compares both pipelines on a set of test texts with known ground truth triplets.
Measures: Precision, Recall, F1, latency, and model load time.

Usage:
    python benchmarks/extraction_benchmark.py
    python benchmarks/extraction_benchmark.py --v1-only
    python benchmarks/extraction_benchmark.py --v2-only
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

# Fix Windows console encoding
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from cgc.core.triplet import Triplet  # noqa: E402, I001


# ── Ground Truth Test Cases ──────────────────────────────────────────────────

@dataclass
class TestCase:
    """A test case with input text and expected triplets."""
    name: str
    text: str
    expected_triplets: list[dict]  # Each dict: {subject, predicate_contains, object}
    domain: str | None = None


TEST_CASES: list[TestCase] = [
    TestCase(
        name="tech_startup_basic",
        text=(
            "Elon Musk founded SpaceX in 2002. The company is headquartered in "
            "Hawthorne, California. SpaceX uses Python and C++ for its flight software. "
            "Gwynne Shotwell serves as President and COO of SpaceX."
        ),
        expected_triplets=[
            {"subject": "Elon Musk", "predicate_contains": "FOUND", "object": "SpaceX"},
            {"subject": "SpaceX", "predicate_contains": "LOCATED", "object": "Hawthorne"},
            {"subject": "SpaceX", "predicate_contains": "USE", "object": "Python"},
            {"subject": "Gwynne Shotwell", "predicate_contains": "LEAD", "object": "SpaceX"},
        ],
    ),
    TestCase(
        name="corporate_relationships",
        text=(
            "Microsoft acquired GitHub in 2018 for $7.5 billion. Satya Nadella, "
            "CEO of Microsoft, announced the deal. GitHub is based in San Francisco "
            "and was developed by Tom Preston-Werner, Chris Wanstrath, and PJ Hyett."
        ),
        expected_triplets=[
            {"subject": "Microsoft", "predicate_contains": "ACQUI", "object": "GitHub"},
            {"subject": "Satya Nadella", "predicate_contains": "LEAD", "object": "Microsoft"},
            {"subject": "GitHub", "predicate_contains": "LOCATED", "object": "San Francisco"},
            {"subject": "GitHub", "predicate_contains": "DEVELOP", "object": "Tom Preston-Werner"},
        ],
    ),
    TestCase(
        name="employment_and_reporting",
        text=(
            "Sarah Chen works at Anthropic as a research scientist. She reports to "
            "Dario Amodei, who leads the company. Anthropic is located in "
            "San Francisco and uses Python for its AI research."
        ),
        expected_triplets=[
            {"subject": "Sarah Chen", "predicate_contains": "WORKS", "object": "Anthropic"},
            {"subject": "Sarah Chen", "predicate_contains": "REPORT", "object": "Dario Amodei"},
            {"subject": "Dario Amodei", "predicate_contains": "LEAD", "object": "Anthropic"},
            {"subject": "Anthropic", "predicate_contains": "LOCATED", "object": "San Francisco"},
            {"subject": "Anthropic", "predicate_contains": "USE", "object": "Python"},
        ],
    ),
    TestCase(
        name="technology_stack",
        text=(
            "Netflix built its streaming platform with Java and React. The service "
            "uses Apache Kafka for real-time data processing and is deployed to "
            "Amazon Web Services. Netflix competes with Disney Plus and HBO Max."
        ),
        expected_triplets=[
            {"subject": "Netflix", "predicate_contains": "USE", "object": "Java"},
            {"subject": "Netflix", "predicate_contains": "USE", "object": "React"},
            {"subject": "Netflix", "predicate_contains": "USE", "object": "Kafka"},
            {"subject": "Netflix", "predicate_contains": "COMPET", "object": "Disney"},
        ],
    ),
    TestCase(
        name="mixed_relations",
        text=(
            "Tim Cook leads Apple, which is headquartered in Cupertino, California. "
            "Apple owns Beats Electronics and partners with TSMC for chip manufacturing. "
            "The iPhone was developed by Apple and uses the A17 Pro chip."
        ),
        expected_triplets=[
            {"subject": "Tim Cook", "predicate_contains": "LEAD", "object": "Apple"},
            {"subject": "Apple", "predicate_contains": "LOCATED", "object": "Cupertino"},
            {"subject": "Apple", "predicate_contains": "OWN", "object": "Beats"},
            {"subject": "Apple", "predicate_contains": "PARTNER", "object": "TSMC"},
            {"subject": "iPhone", "predicate_contains": "DEVELOP", "object": "Apple"},
        ],
    ),
    TestCase(
        name="simple_facts",
        text=(
            "Google was founded by Larry Page and Sergey Brin at Stanford University. "
            "The company is based in Mountain View. Google uses TensorFlow for machine learning."
        ),
        expected_triplets=[
            {"subject": "Larry Page", "predicate_contains": "FOUND", "object": "Google"},
            {"subject": "Google", "predicate_contains": "LOCATED", "object": "Mountain View"},
            {"subject": "Google", "predicate_contains": "USE", "object": "TensorFlow"},
        ],
    ),
    TestCase(
        name="organizational_structure",
        text=(
            "Jensen Huang is the CEO of NVIDIA. NVIDIA is headquartered in Santa Clara. "
            "The company acquired Mellanox Technologies in 2020. NVIDIA provides GPUs "
            "that are used by OpenAI for training large language models."
        ),
        expected_triplets=[
            {"subject": "Jensen Huang", "predicate_contains": "LEAD", "object": "NVIDIA"},
            {"subject": "NVIDIA", "predicate_contains": "LOCATED", "object": "Santa Clara"},
            {"subject": "NVIDIA", "predicate_contains": "ACQUI", "object": "Mellanox"},
            {"subject": "NVIDIA", "predicate_contains": "PROVIDE", "object": "GPU"},
        ],
    ),
    TestCase(
        name="partner_and_subsidiary",
        text=(
            "Amazon Web Services is a subsidiary of Amazon. AWS partners with "
            "Databricks for data analytics. Andy Jassy manages AWS and reports to "
            "the Amazon board. AWS is located in Seattle."
        ),
        expected_triplets=[
            {"subject": "Amazon Web Services", "predicate_contains": "SUBSIDIARY", "object": "Amazon"},
            {"subject": "AWS", "predicate_contains": "PARTNER", "object": "Databricks"},
            {"subject": "Andy Jassy", "predicate_contains": "MANAGE", "object": "AWS"},
            {"subject": "AWS", "predicate_contains": "LOCATED", "object": "Seattle"},
        ],
    ),
    TestCase(
        name="conversational_preferences",
        text=(
            "I work at DataCorp as a senior engineer. My favorite programming language "
            "is Rust. I prefer using PostgreSQL over MySQL for databases. "
            "Our team uses Docker and Kubernetes for deployment."
        ),
        expected_triplets=[
            {"subject": "I", "predicate_contains": "WORK", "object": "DataCorp"},
            {"subject": "favorite", "predicate_contains": "Rust", "object": "Rust"},
        ],
    ),
    TestCase(
        name="complex_multi_hop",
        text=(
            "Mark Zuckerberg founded Meta, formerly known as Facebook. Meta acquired "
            "Instagram in 2012 and WhatsApp in 2014. The company is headquartered in "
            "Menlo Park and uses PyTorch for its AI research. Meta competes with "
            "Google in the advertising market."
        ),
        expected_triplets=[
            {"subject": "Mark Zuckerberg", "predicate_contains": "FOUND", "object": "Meta"},
            {"subject": "Meta", "predicate_contains": "ACQUI", "object": "Instagram"},
            {"subject": "Meta", "predicate_contains": "ACQUI", "object": "WhatsApp"},
            {"subject": "Meta", "predicate_contains": "LOCATED", "object": "Menlo Park"},
            {"subject": "Meta", "predicate_contains": "USE", "object": "PyTorch"},
            {"subject": "Meta", "predicate_contains": "COMPET", "object": "Google"},
        ],
    ),
]


# ── Scoring ──────────────────────────────────────────────────────────────────

def triplet_matches_expected(triplet: Triplet, expected: dict) -> bool:
    """Check if an extracted triplet matches an expected ground truth entry.

    Uses fuzzy matching: subject/object must contain the expected string,
    predicate must contain the expected substring.
    """
    sub = triplet.subject.lower()
    pred = triplet.predicate.upper()
    obj = triplet.object.lower()

    exp_sub = expected["subject"].lower()
    exp_pred = expected["predicate_contains"].upper()
    exp_obj = expected["object"].lower()

    sub_match = exp_sub in sub or sub in exp_sub
    pred_match = exp_pred in pred
    obj_match = exp_obj in obj or obj in exp_obj

    return sub_match and pred_match and obj_match


@dataclass
class CaseResult:
    """Results for a single test case."""
    name: str
    expected_count: int
    extracted_count: int
    matched_count: int
    precision: float
    recall: float
    f1: float
    latency_ms: float
    extracted_triplets: list[Triplet] = field(default_factory=list)
    matched_expected: list[dict] = field(default_factory=list)
    missed_expected: list[dict] = field(default_factory=list)


@dataclass
class BenchmarkResult:
    """Aggregate benchmark results."""
    pipeline: str
    cases: list[CaseResult]
    model_load_time_ms: float
    total_time_ms: float

    @property
    def avg_precision(self) -> float:
        return sum(c.precision for c in self.cases) / len(self.cases) if self.cases else 0

    @property
    def avg_recall(self) -> float:
        return sum(c.recall for c in self.cases) / len(self.cases) if self.cases else 0

    @property
    def avg_f1(self) -> float:
        return sum(c.f1 for c in self.cases) / len(self.cases) if self.cases else 0

    @property
    def macro_f1(self) -> float:
        """Macro F1: compute P/R across all cases, then F1."""
        total_matched = sum(c.matched_count for c in self.cases)
        total_expected = sum(c.expected_count for c in self.cases)
        total_extracted = sum(c.extracted_count for c in self.cases)
        p = total_matched / total_extracted if total_extracted else 0
        r = total_matched / total_expected if total_expected else 0
        return 2 * p * r / (p + r) if (p + r) else 0

    @property
    def avg_latency_ms(self) -> float:
        return sum(c.latency_ms for c in self.cases) / len(self.cases) if self.cases else 0


# ── Benchmark Runner ─────────────────────────────────────────────────────────

def run_benchmark(pipeline: str, test_cases: list[TestCase]) -> BenchmarkResult:
    """Run the benchmark for a given pipeline."""
    from cgc.discovery.extractor import HybridExtractor

    print(f"\n{'='*70}")
    print(f"  BENCHMARK: {pipeline.upper()} PIPELINE")
    print(f"{'='*70}")

    # Create extractor
    extractor = HybridExtractor(pipeline=pipeline)

    # Measure model load time (first extraction triggers lazy loading)
    print("\n  Loading models (first extraction)...")
    load_start = time.perf_counter()
    _ = extractor.extract_triplets("Warm-up text: John works at Google.")
    load_time_ms = (time.perf_counter() - load_start) * 1000
    print(f"  Model load time: {load_time_ms:.0f}ms")

    # Run test cases
    cases: list[CaseResult] = []
    total_start = time.perf_counter()

    for tc in test_cases:
        print(f"\n  [{tc.name}]")

        start = time.perf_counter()
        triplets = extractor.extract_triplets(tc.text, domain=tc.domain)
        latency_ms = (time.perf_counter() - start) * 1000

        # Score: which expected triplets were found?
        matched_expected = []
        missed_expected = []

        for exp in tc.expected_triplets:
            found = any(triplet_matches_expected(t, exp) for t in triplets)
            if found:
                matched_expected.append(exp)
            else:
                missed_expected.append(exp)

        # Precision: of extracted triplets, how many match any expected?
        matched_extracted = 0
        for t in triplets:
            if any(triplet_matches_expected(t, exp) for exp in tc.expected_triplets):
                matched_extracted += 1

        precision = matched_extracted / len(triplets) if triplets else 0
        recall = len(matched_expected) / len(tc.expected_triplets) if tc.expected_triplets else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0

        case_result = CaseResult(
            name=tc.name,
            expected_count=len(tc.expected_triplets),
            extracted_count=len(triplets),
            matched_count=len(matched_expected),
            precision=precision,
            recall=recall,
            f1=f1,
            latency_ms=latency_ms,
            extracted_triplets=triplets,
            matched_expected=matched_expected,
            missed_expected=missed_expected,
        )
        cases.append(case_result)

        # Print case summary
        print(f"    Expected: {len(tc.expected_triplets)} | Extracted: {len(triplets)} | "
              f"Matched: {len(matched_expected)}")
        print(f"    P={precision:.2f} R={recall:.2f} F1={f1:.2f} | {latency_ms:.0f}ms")

        if missed_expected:
            print("    Missed:")
            for m in missed_expected:
                print(f"      - ({m['subject']}, *{m['predicate_contains']}*, {m['object']})")

        if triplets:
            print("    Extracted triplets:")
            for t in triplets:
                marker = ""
                if any(triplet_matches_expected(t, exp) for exp in tc.expected_triplets):
                    marker = " [match]"
                print(f"      ({t.subject}, {t.predicate}, {t.object}) "
                      f"[{t.confidence:.2f}]{marker}")

    total_time_ms = (time.perf_counter() - total_start) * 1000

    result = BenchmarkResult(
        pipeline=pipeline,
        cases=cases,
        model_load_time_ms=load_time_ms,
        total_time_ms=total_time_ms,
    )

    return result


def print_comparison(v1_result: BenchmarkResult | None, v2_result: BenchmarkResult | None):
    """Print side-by-side comparison of v1 and v2 results."""
    results = [r for r in [v1_result, v2_result] if r is not None]
    if not results:
        return

    print(f"\n{'='*70}")
    print("  COMPARISON SUMMARY")
    print(f"{'='*70}\n")

    # Header
    header = f"  {'Metric':<25}"
    for r in results:
        header += f" {r.pipeline:>12}"
    if len(results) == 2:
        header += f" {'Delta':>12}"
    print(header)
    print(f"  {'-'*25}" + f" {'-'*12}" * len(results) + (" " + "-" * 12 if len(results) == 2 else ""))

    def row(label, vals, fmt=".2f", higher_better=True):
        line = f"  {label:<25}"
        for v in vals:
            line += f" {v:>12{fmt}}"
        if len(vals) == 2:
            delta = vals[1] - vals[0]
            sign = "+" if delta > 0 else ""
            indicator = ""
            if abs(delta) > 0.01:
                if (delta > 0 and higher_better) or (delta < 0 and not higher_better):
                    indicator = " [+]"
                else:
                    indicator = " [-]"
            line += f" {sign}{delta:>10{fmt}}{indicator}"
        print(line)

    row("Avg Precision", [r.avg_precision for r in results])
    row("Avg Recall", [r.avg_recall for r in results])
    row("Avg F1", [r.avg_f1 for r in results])
    row("Macro F1", [r.macro_f1 for r in results])
    print()
    row("Model Load (ms)", [r.model_load_time_ms for r in results], fmt=".0f", higher_better=False)
    row("Avg Latency (ms)", [r.avg_latency_ms for r in results], fmt=".0f", higher_better=False)
    row("Total Time (ms)", [r.total_time_ms for r in results], fmt=".0f", higher_better=False)
    print()

    total_expected = sum(c.expected_count for c in results[0].cases)
    for r in results:
        total_matched = sum(c.matched_count for c in r.cases)
        total_extracted = sum(c.extracted_count for c in r.cases)
        print(f"  {r.pipeline}: {total_matched}/{total_expected} expected found, "
              f"{total_extracted} total extracted")

    # Per-case F1 comparison
    if len(results) == 2:
        print(f"\n  {'Case':<30} {'v1 F1':>8} {'v2 F1':>8} {'Winner':>8}")
        print(f"  {'-'*30} {'-'*8} {'-'*8} {'-'*8}")
        v1_wins = 0
        v2_wins = 0
        ties = 0
        for c1, c2 in zip(results[0].cases, results[1].cases):
            winner = "tie"
            if c1.f1 > c2.f1 + 0.01:
                winner = "v1"
                v1_wins += 1
            elif c2.f1 > c1.f1 + 0.01:
                winner = "v2"
                v2_wins += 1
            else:
                ties += 1
            print(f"  {c1.name:<30} {c1.f1:>8.2f} {c2.f1:>8.2f} {winner:>8}")
        print(f"\n  Score: v1={v1_wins} | v2={v2_wins} | ties={ties}")


def main():
    parser = argparse.ArgumentParser(description="Benchmark extraction pipelines")
    parser.add_argument("--v1-only", action="store_true", help="Only run v1 pipeline")
    parser.add_argument("--v2-only", action="store_true", help="Only run v2 pipeline")
    parser.add_argument("--cases", type=str, help="Comma-separated case names to run")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    args = parser.parse_args()

    # Filter cases if specified
    cases = TEST_CASES
    if args.cases:
        names = {n.strip() for n in args.cases.split(",")}
        cases = [tc for tc in TEST_CASES if tc.name in names]
        if not cases:
            print(f"No matching cases. Available: {', '.join(tc.name for tc in TEST_CASES)}")
            return

    v1_result = None
    v2_result = None

    if not args.v2_only:
        try:
            v1_result = run_benchmark("v1", cases)
        except Exception as e:
            print(f"\n  v1 pipeline failed: {e}")

    if not args.v1_only:
        try:
            v2_result = run_benchmark("v2", cases)
        except Exception as e:
            print(f"\n  v2 pipeline failed: {e}")

    print_comparison(v1_result, v2_result)

    if args.json:
        output = {}
        for label, result in [("v1", v1_result), ("v2", v2_result)]:
            if result:
                output[label] = {
                    "avg_precision": result.avg_precision,
                    "avg_recall": result.avg_recall,
                    "avg_f1": result.avg_f1,
                    "macro_f1": result.macro_f1,
                    "model_load_time_ms": result.model_load_time_ms,
                    "avg_latency_ms": result.avg_latency_ms,
                    "total_time_ms": result.total_time_ms,
                    "cases": [
                        {
                            "name": c.name,
                            "precision": c.precision,
                            "recall": c.recall,
                            "f1": c.f1,
                            "latency_ms": c.latency_ms,
                            "expected": c.expected_count,
                            "extracted": c.extracted_count,
                            "matched": c.matched_count,
                        }
                        for c in result.cases
                    ],
                }
        print(f"\n{json.dumps(output, indent=2)}")


if __name__ == "__main__":
    main()
