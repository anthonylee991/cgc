"""Structured data extraction using hub-and-spoke model.

Extracts triplets from tabular data (CSV rows, JSON objects) by:
1. Classifying columns into types (primary entity, entity, property, etc.)
2. Building hub-and-spoke graph: primary entity connects to categorical values
3. Deriving relationship types from column names
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from cgc.core.triplet import Triplet


class ColumnType(Enum):
    """Classification types for tabular columns."""

    PRIMARY_ENTITY = "primary_entity"  # Main entity per row (hub node)
    PRIMARY_ID = "primary_id"          # Row identifier (>90% unique, id pattern)
    FOREIGN_KEY = "foreign_key"        # Reference to another entity (<90% unique, id pattern)
    TIMESTAMP = "timestamp"            # Date/time columns
    ENTITY = "entity"                  # Categorical data (≤500 distinct, <60% unique)
    PROPERTY = "property"              # Numeric/text/high-cardinality columns
    TECHNICAL = "technical"            # User agents, hashes, tokens


@dataclass
class ColumnClassification:
    """Classification result for a single column."""

    name: str
    column_type: ColumnType
    unique_ratio: float = 0.0
    cardinality: int = 0
    sample_values: list[str] | None = None


# --- Classification regex patterns ---

_ID_PATTERNS = re.compile(
    r"(?:_id$|^id$|uuid|^pk$|_pk$|_key$|_ref$|_fk$)",
    re.IGNORECASE,
)

_TIMESTAMP_PATTERNS = re.compile(
    r"(?:date|_at$|created|updated|modified|timestamp|month|year|time|_on$|_date$)",
    re.IGNORECASE,
)

_TECHNICAL_PATTERNS = re.compile(
    r"(?:user_agent|useragent|hash|token|session|cookie|fingerprint|ip_address|"
    r"browser|device|os_version|screen_resolution|referrer|utm_)",
    re.IGNORECASE,
)

_UNIQUE_VALUE_PATTERNS = re.compile(
    r"(?:tracking|invoice|serial|receipt|confirmation|reference|ticket|order_number)",
    re.IGNORECASE,
)

_PRIMARY_ENTITY_PATTERNS = re.compile(
    r"^(?:name|customer|client|employee|person|user|company|organization|"
    r"order|account|contact|lead|vendor|supplier|patient|student|"
    r"contractor|freelancer|consultant|worker|staff|member|associate|"
    r"sales_?rep|salesperson|representative|agent|broker|technician|"
    r"driver|engineer|manager|partner|merchant|retailer|distributor|"
    r"manufacturer|provider)s?$|"
    r"_(?:name|customer|client|employee|order|contractor|rep|agent|person)$|"
    r".*_(?:rep|representative|person|name)$",
    re.IGNORECASE,
)

_FORCE_ENTITY_PATTERNS = re.compile(
    r"^(?:product|item|sku|service|category|brand|model|"
    r"city|country|region|state|location|address|"
    r"department|team|role|status|type|tier|level|"
    r"channel|source|campaign|segment|"
    r"project|task|assignment|job|contract|territory|area|zone|"
    r"skill|specialty|certification|qualification)s?$|"
    r"_(?:product|item|sku|category|brand|city|country|region|status|type|project|task)s?$",
    re.IGNORECASE,
)

# --- Column name to relationship type mapping ---

COLUMN_RELATION_MAP: dict[str, str] = {
    "location": "LOCATED_IN",
    "city": "LOCATED_IN",
    "country": "LOCATED_IN",
    "state": "LOCATED_IN",
    "region": "IN_REGION",
    "address": "LOCATED_AT",
    "category": "IN_CATEGORY",
    "status": "HAS_STATUS",
    "type": "IS_TYPE",
    "tier": "HAS_TIER",
    "level": "HAS_LEVEL",
    "department": "IN_DEPARTMENT",
    "team": "ON_TEAM",
    "role": "HAS_ROLE",
    "manager": "MANAGED_BY",
    "supervisor": "SUPERVISED_BY",
    "industry": "IN_INDUSTRY",
    "sector": "IN_SECTOR",
    "brand": "HAS_BRAND",
    "product": "HAS_ITEM",
    "item": "HAS_ITEM",
    "service": "USES_SERVICE",
    "channel": "VIA_CHANNEL",
    "source": "FROM_SOURCE",
    "campaign": "IN_CAMPAIGN",
    "segment": "IN_SEGMENT",
    "salesperson": "ASSIGNED_TO",
    "sales_rep": "ASSIGNED_TO",
    "engineer": "SUPPORTED_BY",
    "owner": "OWNED_BY",
    "project": "ON_PROJECT",
    "task": "ASSIGNED_TASK",
    "skill": "HAS_SKILL",
    "certification": "HAS_CERTIFICATION",
}


class StructuredExtractor:
    """Hub-and-spoke triplet extraction for tabular data.

    1. Classify columns into types using priority-ordered rules
    2. Identify PRIMARY_ENTITY as hub node
    3. Create spoke relations from hub to ENTITY/FOREIGN_KEY columns
    4. Properties become metadata on hub node
    """

    ENTITY_UNIQUENESS_THRESHOLD = 0.6
    MIN_ROWS_FOR_STATS = 5
    MAX_ENTITY_CARDINALITY = 500

    def classify_columns(self, data: list[dict]) -> list[ColumnClassification]:
        """Classify all columns in the dataset."""
        if not data:
            return []

        columns = list(data[0].keys())
        total_rows = len(data)
        classifications = []

        for col in columns:
            values = [row.get(col) for row in data if row.get(col) is not None]
            values_str = [str(v).strip() for v in values if str(v).strip()]

            unique_values = set(values_str)
            cardinality = len(unique_values)
            unique_ratio = cardinality / len(values_str) if values_str else 0.0

            col_lower = col.lower().strip()

            # Priority-ordered classification rules
            col_type = self._classify_column(
                col_lower, values_str, unique_ratio, cardinality, total_rows,
            )

            classifications.append(ColumnClassification(
                name=col,
                column_type=col_type,
                unique_ratio=unique_ratio,
                cardinality=cardinality,
                sample_values=values_str[:5] if values_str else None,
            ))

        # If no PRIMARY_ENTITY found, promote first ENTITY or use first non-ID column
        has_primary = any(c.column_type == ColumnType.PRIMARY_ENTITY for c in classifications)
        if not has_primary:
            for c in classifications:
                if c.column_type == ColumnType.ENTITY:
                    c.column_type = ColumnType.PRIMARY_ENTITY
                    break

        return classifications

    def _classify_column(
        self,
        col_lower: str,
        values: list[str],
        unique_ratio: float,
        cardinality: int,
        total_rows: int,
    ) -> ColumnType:
        """Apply priority-ordered classification rules."""
        # 1. ID patterns
        if _ID_PATTERNS.search(col_lower):
            if unique_ratio > 0.9:
                return ColumnType.PRIMARY_ID
            return ColumnType.FOREIGN_KEY

        # 2. Timestamp patterns
        if _TIMESTAMP_PATTERNS.search(col_lower):
            return ColumnType.TIMESTAMP

        # 3. Technical patterns
        if _TECHNICAL_PATTERNS.search(col_lower):
            return ColumnType.TECHNICAL

        # 4. Unique value patterns (tracking/invoice numbers)
        if _UNIQUE_VALUE_PATTERNS.search(col_lower):
            return ColumnType.PROPERTY

        # 5. Primary entity patterns
        if _PRIMARY_ENTITY_PATTERNS.search(col_lower):
            return ColumnType.PRIMARY_ENTITY

        # 6. Force entity patterns
        if _FORCE_ENTITY_PATTERNS.search(col_lower):
            return ColumnType.ENTITY

        # 7. Numeric columns
        if values and self._is_numeric_column(values):
            return ColumnType.PROPERTY

        # 8. Long strings (avg > 100 chars)
        if values:
            avg_len = sum(len(v) for v in values) / len(values)
            if avg_len > 100:
                return ColumnType.PROPERTY

        # 9. High uniqueness (> 90%)
        if total_rows >= self.MIN_ROWS_FOR_STATS and unique_ratio > 0.9:
            return ColumnType.PROPERTY

        # 10. High cardinality (> 500 distinct)
        if cardinality > self.MAX_ENTITY_CARDINALITY:
            return ColumnType.PROPERTY

        # 11. Low cardinality → ENTITY
        if cardinality <= self.MAX_ENTITY_CARDINALITY and unique_ratio < self.ENTITY_UNIQUENESS_THRESHOLD:
            return ColumnType.ENTITY

        # 12. Default
        return ColumnType.PROPERTY

    def _is_numeric_column(self, values: list[str]) -> bool:
        """Check if most values are numeric."""
        numeric_count = 0
        for v in values[:50]:  # Sample first 50
            try:
                float(v.replace(",", "").replace("$", "").replace("%", ""))
                numeric_count += 1
            except ValueError:
                pass
        return numeric_count / min(len(values), 50) > 0.8

    def extract_triplets(self, data: list[dict]) -> list[Triplet]:
        """Extract triplets from structured data using hub-and-spoke model."""
        if not data:
            return []

        classifications = self.classify_columns(data)
        # Find hub column(s)
        hub_cols = [c for c in classifications if c.column_type == ColumnType.PRIMARY_ENTITY]
        entity_cols = [c for c in classifications if c.column_type == ColumnType.ENTITY]
        fk_cols = [c for c in classifications if c.column_type == ColumnType.FOREIGN_KEY]

        if not hub_cols:
            # No hub found; try to form triplets from entity pairs
            return self._extract_entity_pairs(data, entity_cols)

        triplets = []
        hub_col = hub_cols[0]  # Use first primary entity as hub

        for row in data:
            hub_value = str(row.get(hub_col.name, "")).strip()
            if not hub_value:
                continue

            # Create spoke relations: hub → entity columns
            for entity_col in entity_cols:
                spoke_value = str(row.get(entity_col.name, "")).strip()
                if not spoke_value:
                    continue

                relation = self._derive_relation(entity_col.name)

                triplets.append(Triplet(
                    subject=hub_value,
                    predicate=relation,
                    object=spoke_value,
                    confidence=0.90,
                    metadata={
                        "subject_label": self._infer_label(hub_col.name),
                        "object_label": self._infer_label(entity_col.name),
                        "method": "structured",
                        "hub_column": hub_col.name,
                        "spoke_column": entity_col.name,
                    },
                ))

            # Create spoke relations: hub → foreign key columns
            for fk_col in fk_cols:
                fk_value = str(row.get(fk_col.name, "")).strip()
                if not fk_value:
                    continue

                relation = self._derive_relation(fk_col.name)

                triplets.append(Triplet(
                    subject=hub_value,
                    predicate=relation,
                    object=fk_value,
                    confidence=0.85,
                    metadata={
                        "subject_label": self._infer_label(hub_col.name),
                        "method": "structured",
                        "hub_column": hub_col.name,
                        "spoke_column": fk_col.name,
                    },
                ))

        return triplets

    def _extract_entity_pairs(
        self,
        data: list[dict],
        entity_cols: list[ColumnClassification],
    ) -> list[Triplet]:
        """Fallback: create relations between entity column pairs."""
        triplets = []
        if len(entity_cols) < 2:
            return triplets

        for row in data:
            for i, col_a in enumerate(entity_cols):
                for col_b in entity_cols[i + 1:]:
                    val_a = str(row.get(col_a.name, "")).strip()
                    val_b = str(row.get(col_b.name, "")).strip()
                    if val_a and val_b:
                        relation = f"RELATED_VIA_{col_b.name.upper()}"
                        triplets.append(Triplet(
                            subject=val_a,
                            predicate=relation,
                            object=val_b,
                            confidence=0.70,
                            metadata={
                                "subject_label": self._infer_label(col_a.name),
                                "object_label": self._infer_label(col_b.name),
                                "method": "structured",
                            },
                        ))

        return triplets

    def _derive_relation(self, column_name: str) -> str:
        """Map column name to a relationship type."""
        col_lower = column_name.lower().strip().rstrip("s")

        # Direct mapping
        if col_lower in COLUMN_RELATION_MAP:
            return COLUMN_RELATION_MAP[col_lower]

        # Check with plural stripped
        for key, relation in COLUMN_RELATION_MAP.items():
            if col_lower == key or col_lower.endswith(f"_{key}"):
                return relation

        # Default: HAS_<COLUMN_NAME>
        clean = re.sub(r"[^a-zA-Z0-9_]", "", column_name.upper())
        return f"HAS_{clean}"

    def _infer_label(self, column_name: str) -> str:
        """Infer an entity type label from a column name."""
        col_lower = column_name.lower().strip()

        label_hints = {
            "customer": "person", "client": "person", "employee": "person",
            "person": "person", "user": "person", "name": "person",
            "manager": "person", "agent": "person",
            "company": "organization", "organization": "organization",
            "vendor": "organization", "supplier": "organization",
            "city": "location", "country": "location", "location": "location",
            "region": "location", "state": "location", "address": "location",
            "product": "product", "item": "product", "sku": "product",
            "category": "category", "department": "department",
            "team": "department", "role": "role", "status": "status",
            "project": "project", "brand": "organization",
        }

        for hint, label in label_hints.items():
            if hint in col_lower:
                return label

        return "entity"
