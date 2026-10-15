"""Everything you might want to change lives in this file."""

# ---------------------------------------------------------------------------
# 1. Companies to watch (free, official job feeds)
# ---------------------------------------------------------------------------
# The slug is the last part of the company's careers URL:
#   boards.greenhouse.io/<slug>    jobs.lever.co/<slug>    jobs.ashbyhq.com/<slug>
# Some slugs below are best guesses. Any that fail are listed at the bottom
# of the daily email so you can fix or delete them.
GREENHOUSE = [
    "block", "gusto", "airwallex", "lyft", "instacart",
    "stripe", "brex", "samsara", "flexport",
]
LEVER = ["wellhub"]
ASHBY = ["elevenlabs", "ramp", "openai"]

# ---------------------------------------------------------------------------
# 2. Aggregator search (Adzuna). Needs free keys, skipped if not set.
# ---------------------------------------------------------------------------
ADZUNA_QUERIES = [
    "partnerships manager",
    "business development manager",
    "strategic account manager",
    "category manager",
    "revenue growth management",
    "supplier manager marketplace",
    "commercial strategy manager",
    "policy manager",
]
ADZUNA_LOCATIONS = ["Chicago", "New York", "Los Angeles", "San Francisco"]

# ---------------------------------------------------------------------------
# 3. Which job titles count
# ---------------------------------------------------------------------------
# Checked in this order. The first track that matches the title wins.
TRACKS = {
    "policy": {
        "label": "Policy",
        "weight": 28,
        "patterns": [
            r"\bpolicy\b", r"public affairs", r"government (affairs|relations)",
            r"regulatory", r"public sector",
        ],
    },
    "partnerships": {
        "label": "Partnerships / BD",
        "weight": 40,
        "patterns": [
            r"partner", r"business development", r"\bbd\b",
            r"alliances?", r"channel",
        ],
    },
    "category": {
        "label": "Category / RGM / Strategy",
        "weight": 38,
        "patterns": [
            r"category (manager|management|lead|analyst|strategy)",
            r"revenue growth", r"\brgm\b",
            r"commercial (strategy|finance)", r"trade strategy",
            r"supplier", r"vendor manager", r"marketplace",
            r"market research",
        ],
    },
    "accounts": {
        "label": "Account Management",
        "weight": 35,
        "patterns": [
            r"account manage", r"key account", r"strategic account",
        ],
    },
}

# Titles containing any of these are dropped. Level target is Manager or
# Senior Associate, so Director and above are out. Field sales is out.
EXCLUDE_TITLE = [
    r"director", r"\bvp\b", r"vice president", r"head of", r"chief",
    r"\bpresident\b", r"\bintern", r"junior", r"\bjr\b", r"entry.level",
    r"sales development", r"\bsdr\b", r"\bbdr\b", r"representative",
    r"territory", r"district", r"account developer",
    r"engineer", r"developer", r"software", r"technical", r"data scientist",
    r"recruit", r"talent", r"designer", r"counsel", r"attorney",
    r"accountant", r"human resources", r"people partner", r"business partner",
    r"coordinator", r"assistant", r"administrator",
]

# ---------------------------------------------------------------------------
# 4. Locations
# ---------------------------------------------------------------------------
PREFERRED_LOCATIONS = [
    "chicago", "new york", "nyc", "brooklyn", "los angeles",
    "san francisco", "bay area", "palo alto", "oakland", "remote",
]

# ---------------------------------------------------------------------------
# 5. Scoring
# ---------------------------------------------------------------------------
# Words in the job description that add 2 points each (max 24 total).
POSITIVE_KEYWORDS = [
    "partnership", "channel", "reseller", "marketplace", "saas", "p&l",
    "key account", "strategic account", "enterprise", "category management",
    "supplier", "vendor", "negotiat", "last-mile", "last mile",
    "ride-hailing", "ride hailing", "e-commerce", "ecommerce", "fmcg", "cpg",
    "pricing", "forecast", "go-to-market", "gtm", "amazon", "wholesale",
    "b2b", "fintech", "payments", "emerging markets", "artificial intelligence",
]
# Words that subtract 8 points each (max 24 total).
NEGATIVE_KEYWORDS = [
    "territory", "field sales", "merchandis", "store visits", "cold calling",
    "door-to-door", "commission only", "security clearance",
]

MAX_AGE_HOURS = 48     # only jobs posted in the last N hours
MIN_SCORE = 40         # rule score needed to be considered at all
TOP_N = 25             # jobs in the daily email
LLM_POOL = 40          # how many top rule-scored jobs get an LLM review
MIN_FIT = 5            # LLM fit score (1 to 10) below this is dropped
LLM_MODEL = "claude-haiku-5-5"

# Short summary sent to the LLM so it can judge fit. Edit freely.
PROFILE_SUMMARY = """
Mahin Rao. Based in Chicago, open to NY, LA, SF and relocation.
10+ years of commercial experience across FMCG, enterprise SaaS, e-commerce
and B2B partnerships in Pakistan and MENAP.
- Retailo Technologies: Senior Category Manager and Senior BD Manager.
  Launched a BNPL product, managed supplier joint business plans, sold SaaS,
  built a $2M+ pipeline.
- Leverify LLC: Partnership Manager, North America. Owned supplier
  relationships, buying, margins, credit terms, forecasting and Amazon FBA
  inventory for an electronics wholesale distributor (about $4M a year
  with one supplier). Managed a team.
- Packages Limited: B2B account owner for a $7.9M portfolio selling packaging
  to Unilever, Colgate and Reckitt.
- Hilal Foods: built an institutional sales channel from zero.
- Strengths: quota-carrying sales, strategic and enterprise account
  management (10 years, 8 at enterprise level), partner channels (SI,
  affiliate, reseller), negotiating $2M+ deals with Director and Head level
  stakeholders, category management, P&L ownership. Managed 3 to 4 reports.
- Education: MA Public Policy (Harris, UChicago), MBA (IBA Karachi),
  BBA (NUCES). Also AI governance and TA work at Chicago Booth.
- Has NOT run a field retail sales territory.
Target level: Manager or Senior Associate, not Director.
Target order: 1) startups, tech, last-mile, ride-hailing; 2) commercial
BD, sales, partnerships, category management; 3) policy.
""".strip()
