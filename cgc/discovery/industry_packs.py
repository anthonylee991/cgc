"""Domain-specific industry packs for targeted extraction.

Each pack defines entity and relation labels tuned for a specific industry.
The domain router selects the appropriate pack based on document content.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class IndustryPack:
    """A domain-specific label set for extraction."""

    id: str
    name: str
    description: str
    examples: list[str] = field(default_factory=list)
    entity_labels: list[str] = field(default_factory=list)
    relation_labels: list[str] = field(default_factory=list)


# --- Pack definitions ---

GENERAL_BUSINESS = IndustryPack(
    id="general_business",
    name="General Business",
    description="General business documents covering organizations, people, locations, products, and standard business relationships.",
    examples=[
        "The company reported quarterly earnings.",
        "John Smith manages the sales department.",
        "Our headquarters are located in New York.",
    ],
    entity_labels=[
        "person", "organization", "company", "location", "date",
        "role", "department", "product", "money", "event",
    ],
    relation_labels=[
        "founded", "leads", "works at", "located in", "member of",
        "reports to", "manages", "owns", "provides", "partner of",
    ],
)

TECH_STARTUP = IndustryPack(
    id="tech_startup",
    name="Tech / Startup",
    description="Technology companies, software products, programming, APIs, frameworks, cloud platforms, funding rounds, and startup ecosystems.",
    examples=[
        "The startup raised a Series B round.",
        "Built with React and deployed on AWS.",
        "The CTO founded the company in 2020.",
    ],
    entity_labels=[
        "person", "company", "product", "technology", "framework",
        "programming language", "investor", "funding_round", "location",
        "startup", "platform", "api", "feature",
    ],
    relation_labels=[
        "founded", "leads", "built with", "integrates with",
        "invested in", "acquired", "uses", "developed by",
        "competes with", "partners with", "headquartered in",
        "launched", "maintains",
    ],
)

ECOMMERCE_RETAIL = IndustryPack(
    id="ecommerce_retail",
    name="E-Commerce / Retail",
    description="Online shopping, product catalogs, customer orders, shipping, pricing, inventory, reviews, and retail operations.",
    examples=[
        "Customer purchased 3 units at $29.99 each.",
        "Product shipped from warehouse in Dallas.",
        "The item belongs to the Electronics category.",
    ],
    entity_labels=[
        "customer", "product", "order", "category", "brand", "seller",
        "store", "warehouse", "sku", "price", "discount",
        "payment_method", "shipping_method", "address", "date",
        "quantity", "review",
    ],
    relation_labels=[
        "purchased", "ordered", "reviewed", "added to cart",
        "wishlisted", "returned", "shipped to", "sold by",
        "belongs to category", "manufactured by", "priced at",
        "discounted by", "paid with", "delivered to", "rated",
        "recommended",
    ],
)

LEGAL_CORPORATE = IndustryPack(
    id="legal_corporate",
    name="Legal / Corporate",
    description="Legal documents, contracts, corporate governance, regulations, statutes, court cases, attorneys, and legal obligations.",
    examples=[
        "The agreement was executed by both parties.",
        "Section 4.2 governs termination rights.",
        "Attorney filed a motion in federal court.",
    ],
    entity_labels=[
        "person", "organization", "contract", "statute", "regulation",
        "court", "attorney", "judge", "obligation", "clause",
        "jurisdiction", "date", "party", "document", "penalty",
    ],
    relation_labels=[
        "governs", "applies to", "signed by", "filed by",
        "represents", "obligates", "amends", "supersedes",
        "references", "violates", "enforces", "terminates",
    ],
)

FINANCE_INVESTMENT = IndustryPack(
    id="finance_investment",
    name="Finance / Investment",
    description="Financial markets, investments, securities, banking, funds, valuations, trading, and portfolio management.",
    examples=[
        "The fund returned 12% in Q3.",
        "Stock price reached $150 per share.",
        "The acquisition was valued at $2B.",
    ],
    entity_labels=[
        "person", "company", "fund", "security", "stock", "bond",
        "exchange", "index", "valuation", "currency", "date",
        "portfolio", "asset", "transaction", "money",
    ],
    relation_labels=[
        "invested in", "acquired", "valued at", "listed on",
        "manages", "owns", "trades", "underwrites",
        "reports to", "audits", "funds", "divested",
    ],
)

HR_PEOPLE = IndustryPack(
    id="hr_people",
    name="HR / People",
    description="Human resources, employee management, skills, certifications, hiring, compensation, benefits, organizational structure, and workforce management.",
    examples=[
        "Employee holds a PMP certification.",
        "Salary range is $80K-$120K for this role.",
        "Reports to the VP of Engineering.",
    ],
    entity_labels=[
        "person", "role", "department", "skill", "certification",
        "degree", "institution", "salary", "benefit", "location",
        "date", "experience_level", "employment_type", "organization",
    ],
    relation_labels=[
        "works at", "reports to", "manages", "has skill",
        "certified in", "graduated from", "hired by",
        "promoted to", "transferred to", "belongs to",
        "earns", "entitled to",
    ],
)

HEALTHCARE_MEDICAL = IndustryPack(
    id="healthcare_medical",
    name="Healthcare / Medical",
    description="Medical records, patient care, diagnoses, medications, procedures, clinical trials, and healthcare systems.",
    examples=[
        "Patient diagnosed with Type 2 diabetes.",
        "Prescribed 500mg Metformin twice daily.",
        "Procedure performed by Dr. Johnson.",
    ],
    entity_labels=[
        "patient", "physician", "medication", "diagnosis", "procedure",
        "dosage", "condition", "hospital", "department", "date",
        "lab_result", "insurance", "device", "symptom",
    ],
    relation_labels=[
        "diagnosed with", "prescribed", "performed by",
        "treated at", "administered", "referred to",
        "allergic to", "contraindicated with", "monitors",
        "specializes in",
    ],
)

REAL_ESTATE = IndustryPack(
    id="real_estate",
    name="Real Estate",
    description="Property listings, real estate transactions, brokers, tenants, landlords, zoning, valuations, and property management.",
    examples=[
        "3-bedroom house listed at $450,000.",
        "Property zoned for commercial use.",
        "Tenant signed a 2-year lease.",
    ],
    entity_labels=[
        "property", "person", "company", "broker", "tenant", "landlord",
        "location", "zoning", "valuation", "date", "money",
        "property_type", "amenity", "contract",
    ],
    relation_labels=[
        "listed by", "purchased by", "located in", "zoned as",
        "valued at", "leased to", "managed by", "owned by",
        "inspected by", "financed by", "built by",
    ],
)

SUPPLY_CHAIN = IndustryPack(
    id="supply_chain",
    name="Supply Chain / Logistics",
    description="Supply chain management, manufacturing, warehousing, shipping, procurement, inventory, carriers, and logistics operations.",
    examples=[
        "Shipment dispatched from Shanghai warehouse.",
        "Supplier delivers 10,000 units monthly.",
        "Carrier ETA is 5 business days.",
    ],
    entity_labels=[
        "supplier", "manufacturer", "warehouse", "shipment", "carrier",
        "product", "sku", "location", "port", "route",
        "date", "quantity", "cost", "contract", "person",
    ],
    relation_labels=[
        "supplies", "manufactures", "ships to", "stored at",
        "transported by", "ordered from", "delivered to",
        "sourced from", "routes through", "dispatched from",
    ],
)

RESEARCH_ACADEMIC = IndustryPack(
    id="research_academic",
    name="Research / Academic",
    description="Academic research, scientific papers, journals, conferences, grants, citations, methodologies, and research institutions.",
    examples=[
        "Paper published in Nature in 2024.",
        "Research funded by NSF grant.",
        "Study conducted at MIT.",
    ],
    entity_labels=[
        "researcher", "institution", "journal", "paper", "grant",
        "conference", "methodology", "dataset", "topic",
        "date", "funding_agency", "degree", "department",
    ],
    relation_labels=[
        "authored by", "published in", "funded by",
        "affiliated with", "cited by", "presented at",
        "supervised by", "collaborates with", "studies",
        "peer reviewed by",
    ],
)

GOVERNMENT_PUBLIC = IndustryPack(
    id="government_public",
    name="Government / Public Sector",
    description="Government agencies, legislation, regulations, public policy, permits, jurisdictions, and public administration.",
    examples=[
        "The bill was signed into law in 2023.",
        "Agency issued a permit for construction.",
        "Regulation applies to all financial institutions.",
    ],
    entity_labels=[
        "agency", "legislation", "regulation", "policy", "jurisdiction",
        "permit", "person", "department", "organization", "date",
        "budget", "program", "district", "office",
    ],
    relation_labels=[
        "enacted by", "regulates", "governs", "applies to",
        "issued by", "funded by", "oversees", "reports to",
        "administers", "enforces", "amends",
    ],
)


# --- Expansion packs ---

ACCOUNTING_REPORTING = IndustryPack(
    id="accounting_reporting",
    name="Accounting & Financial Reporting",
    description="Financial statements, accounting standards, auditing, IFRS, GAAP, consolidation, balance sheet, income statement",
    examples=[
        "consolidated statement of financial position", "balance sheet",
        "income statement", "cash flow statement", "IFRS", "GAAP",
        "depreciation", "amortization", "goodwill impairment",
        "notes to financial statements", "audit opinion", "retained earnings",
        "deferred tax", "lease liability", "right-of-use asset",
    ],
    entity_labels=[
        "reporting_entity", "financial_statement", "line_item", "asset",
        "liability", "equity_component", "accounting_standard",
        "reporting_period", "currency", "auditor", "money",
        "accounting_policy", "person", "company", "date",
    ],
    relation_labels=[
        "reported in", "subsidiary of", "consolidates", "recognized under",
        "component of", "measured at", "denominated in", "audited by",
        "for period", "located in", "owns", "manages",
    ],
)

INSURANCE = IndustryPack(
    id="insurance",
    name="Insurance",
    description="Insurance policies, claims processing, underwriting, risk assessment, actuarial analysis",
    examples=[
        "insurance policy", "premium calculation", "claim filed",
        "underwriting criteria", "actuarial table", "deductible",
        "coverage limit", "beneficiary", "risk assessment",
        "reinsurance", "loss ratio", "policyholder",
    ],
    entity_labels=[
        "policyholder", "insurer", "claim", "policy", "coverage_type",
        "premium", "deductible", "beneficiary", "adjuster", "risk_class",
        "peril", "exclusion", "person", "company", "money", "date",
    ],
    relation_labels=[
        "insured by", "covers", "filed by", "excludes", "underwritten by",
        "claimed against", "beneficiary of", "adjusts", "reinsured by",
        "applies to", "located in", "owns",
    ],
)

MANUFACTURING_ENGINEERING = IndustryPack(
    id="manufacturing_engineering",
    name="Manufacturing & Engineering",
    description="Product manufacturing, engineering specifications, quality control, industrial processes, BOM",
    examples=[
        "bill of materials", "engineering specification", "quality control",
        "ISO 9001", "tolerance", "assembly line", "CAD drawing",
        "material properties", "manufacturing process", "defect rate",
        "standard operating procedure", "production run", "machining",
    ],
    entity_labels=[
        "part", "assembly", "specification", "material", "process",
        "machine", "quality_standard", "tolerance", "supplier", "defect",
        "measurement", "person", "company", "location", "date",
    ],
    relation_labels=[
        "component of", "manufactured by", "meets standard", "tested with",
        "specified as", "supplied by", "assembled in", "made from",
        "produces", "inspected by", "located in", "owns",
    ],
)

MARKETING_SALES = IndustryPack(
    id="marketing_sales",
    name="Marketing & Sales",
    description="Marketing strategy, sales pipeline, competitive analysis, market research, campaigns, branding",
    examples=[
        "marketing campaign", "target audience", "market share",
        "competitive analysis", "brand positioning", "sales pipeline",
        "conversion rate", "customer acquisition", "go-to-market strategy",
        "market segment", "pricing strategy", "lead generation",
    ],
    entity_labels=[
        "brand", "campaign", "channel", "competitor", "market_segment",
        "target_audience", "kpi", "metric", "feature", "pricing_tier",
        "person", "company", "product", "location", "date", "money",
    ],
    relation_labels=[
        "competes with", "targets", "outperforms", "priced at",
        "launched in", "distributed through", "acquired", "sponsors",
        "positions against", "leads", "located in", "owns",
    ],
)

ENERGY_ENVIRONMENT = IndustryPack(
    id="energy_environment",
    name="Energy & Environment",
    description="Energy production, environmental compliance, sustainability, ESG reporting, carbon emissions, renewables",
    examples=[
        "carbon emissions", "sustainability report", "ESG score",
        "renewable energy", "solar panel", "wind farm", "carbon footprint",
        "environmental impact assessment", "greenhouse gas", "net zero",
        "energy audit", "waste management", "regulatory compliance",
    ],
    entity_labels=[
        "emission", "energy_source", "facility", "environmental_regulation",
        "metric", "target", "carbon_credit", "pollutant", "renewable_source",
        "person", "company", "location", "date", "money",
    ],
    relation_labels=[
        "emits", "complies with", "targets reduction of", "generates",
        "certified by", "located in", "operates", "monitors",
        "regulated by", "funded by", "owns", "manages",
    ],
)

SOFTWARE_ENGINEERING = IndustryPack(
    id="software_engineering",
    name="Software Engineering",
    description="Software architecture, API design, microservices, databases, DevOps, code, deployments, dependencies",
    examples=[
        "microservice architecture", "REST API endpoint", "database schema",
        "CI/CD pipeline", "deployment", "Docker container", "Kubernetes",
        "code review", "pull request", "migration", "dependency",
        "incident postmortem", "load balancer", "message queue",
    ],
    entity_labels=[
        "service", "microservice", "api", "endpoint", "database",
        "repository", "library", "dependency", "framework",
        "programming_language", "architecture_pattern", "protocol",
        "version", "environment", "vulnerability", "person", "company",
    ],
    relation_labels=[
        "depends on", "implements", "extends", "calls", "deployed to",
        "written in", "exposes", "consumes", "migrated from", "replaces",
        "compatible with", "vulnerable to", "developed by", "maintains",
    ],
)


# --- Registry ---

ALL_PACKS: list[IndustryPack] = [
    # Starter packs
    GENERAL_BUSINESS,
    TECH_STARTUP,
    ECOMMERCE_RETAIL,
    LEGAL_CORPORATE,
    FINANCE_INVESTMENT,
    HR_PEOPLE,
    HEALTHCARE_MEDICAL,
    REAL_ESTATE,
    SUPPLY_CHAIN,
    RESEARCH_ACADEMIC,
    GOVERNMENT_PUBLIC,
    # Expansion packs
    ACCOUNTING_REPORTING,
    INSURANCE,
    MANUFACTURING_ENGINEERING,
    MARKETING_SALES,
    ENERGY_ENVIRONMENT,
    SOFTWARE_ENGINEERING,
]

PACK_REGISTRY: dict[str, IndustryPack] = {pack.id: pack for pack in ALL_PACKS}


def get_pack(pack_id: str) -> IndustryPack | None:
    """Get an industry pack by ID."""
    return PACK_REGISTRY.get(pack_id)


def get_all_packs() -> list[IndustryPack]:
    """Get all available industry packs."""
    return list(ALL_PACKS)
