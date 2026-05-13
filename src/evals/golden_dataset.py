"""
Golden Q&A dataset for RAGAS evaluation.

Property: Riverside Commons — 120-unit Class B multifamily in Austin, TX.
This is a fictional deal used exclusively for eval and testing.

Each entry has:
  question     — what a user or agent might ask the RAG system
  ground_truth — the correct answer (used by RAGAS for answer correctness)
  context      — the passage the RAG system should retrieve to answer it

These triples simulate the output of our RAG pipeline. In CI, they substitute
for live retrieval so evals don't require a running pgvector instance.
"""

DEAL_DOCUMENT = """
INVESTMENT MEMORANDUM — RIVERSIDE COMMONS
Prepared by: Westbrook Capital Partners, LLC
Date: March 2025

PROPERTY OVERVIEW
Property Name: Riverside Commons
Property Type: Multifamily — Class B Garden-Style
Address: 4820 Riverside Drive, Austin, TX 78741
Year Built: 2018
Units: 120 (mix of 1BR and 2BR)
Gross Building Area: 98,400 SF

FINANCIAL SUMMARY
Purchase Price: $18,000,000
Price Per Unit: $150,000
Net Operating Income (NOI): $990,000 (trailing 12 months)
Capitalization Rate: 5.50%
Gross Rent Multiplier (GRM): 10.2x

DEBT STRUCTURE
Loan Amount: $13,500,000
Loan-to-Value (LTV): 75.0%
Interest Rate: 6.25% (fixed, 10-year term)
Annual Debt Service: $773,438
Debt Service Coverage Ratio (DSCR): 1.28x

OPERATIONS
Current Occupancy: 93% (physical); 92% (economic)
Vacancy Rate: 7.0%
Average Monthly Rent: $1,375
Average Rent PSF: $1.68

CAPITAL EXPENDITURE RESERVE
Replacement Reserves: $250,000/year ($2,083/unit)
Estimated Deferred Maintenance: $180,000 (roofing, HVAC partial)

RED FLAGS NOTED BY BROKER
- Three units with active lease disputes as of January 2025
- HVAC systems in Building C showing signs of age (estimated 2-3 year useful life remaining)
- Market vacancy trending upward (7.1% Q3 2024 → 7.8% Q4 2024)

SPONSORSHIP
Sponsor: Westbrook Capital Partners, LLC
Track Record: 8 multifamily acquisitions in Texas since 2017, 2 dispositions at or above proforma
"""

GOLDEN_QA_PAIRS: list[dict] = [
    {
        "question": "What is the purchase price for Riverside Commons?",
        "ground_truth": "The purchase price for Riverside Commons is $18,000,000 ($150,000 per unit).",
        "context": "Purchase Price: $18,000,000\nPrice Per Unit: $150,000",
    },
    {
        "question": "What is the cap rate on this deal?",
        "ground_truth": "The capitalization rate is 5.50%, calculated on trailing 12-month NOI of $990,000.",
        "context": "Net Operating Income (NOI): $990,000 (trailing 12 months)\nCapitalization Rate: 5.50%",
    },
    {
        "question": "What is the debt service coverage ratio?",
        "ground_truth": "The DSCR is 1.28x, calculated as NOI of $990,000 divided by annual debt service of $773,438.",
        "context": "Annual Debt Service: $773,438\nDebt Service Coverage Ratio (DSCR): 1.28x",
    },
    {
        "question": "What is the loan-to-value ratio?",
        "ground_truth": "The LTV is 75.0%, with a loan amount of $13,500,000 against a purchase price of $18,000,000.",
        "context": "Loan Amount: $13,500,000\nLoan-to-Value (LTV): 75.0%",
    },
    {
        "question": "How many units does the property have?",
        "ground_truth": "Riverside Commons has 120 units (a mix of 1-bedroom and 2-bedroom).",
        "context": "Units: 120 (mix of 1BR and 2BR)",
    },
    {
        "question": "What is the current vacancy rate?",
        "ground_truth": (
            "The current physical vacancy rate is 7.0% (93% occupancy). "
            "Market vacancy has been trending upward from 7.1% in Q3 2024 to 7.8% in Q4 2024."
        ),
        "context": (
            "Vacancy Rate: 7.0%\n"
            "Market vacancy trending upward (7.1% Q3 2024 → 7.8% Q4 2024)"
        ),
    },
    {
        "question": "What red flags are noted in the deal document?",
        "ground_truth": (
            "Three red flags: (1) three units with active lease disputes as of January 2025, "
            "(2) HVAC systems in Building C nearing end of life (2-3 years remaining), "
            "(3) market vacancy trending upward."
        ),
        "context": (
            "RED FLAGS NOTED BY BROKER\n"
            "- Three units with active lease disputes as of January 2025\n"
            "- HVAC systems in Building C showing signs of age (estimated 2-3 year useful life remaining)\n"
            "- Market vacancy trending upward (7.1% Q3 2024 → 7.8% Q4 2024)"
        ),
    },
    {
        "question": "What is the annual NOI for Riverside Commons?",
        "ground_truth": "The trailing 12-month Net Operating Income (NOI) is $990,000.",
        "context": "Net Operating Income (NOI): $990,000 (trailing 12 months)",
    },
    {
        "question": "What is the sponsor's track record?",
        "ground_truth": (
            "Westbrook Capital Partners has completed 8 multifamily acquisitions in Texas since 2017, "
            "with 2 dispositions at or above proforma."
        ),
        "context": (
            "Sponsor: Westbrook Capital Partners, LLC\n"
            "Track Record: 8 multifamily acquisitions in Texas since 2017, "
            "2 dispositions at or above proforma"
        ),
    },
    {
        "question": "What is the average monthly rent per unit?",
        "ground_truth": "The average monthly rent is $1,375 per unit ($1.68 per square foot).",
        "context": "Average Monthly Rent: $1,375\nAverage Rent PSF: $1.68",
    },
]
