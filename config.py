"""Everything you might want to change lives in this file."""

# ---------------------------------------------------------------------------
# 1. Companies read directly from their official job feeds (free)
# ---------------------------------------------------------------------------
# The slug is the last part of the company's careers URL:
#   boards.greenhouse.io/<slug>   jobs.lever.co/<slug>   jobs.ashbyhq.com/<slug>
# Many slugs below are best guesses. Any that fail are listed at the bottom
# of the daily email so you can fix or delete them.
GREENHOUSE = [
    # already working or on your target list
    "stripe", "instacart", "affirm", "okta", "doordashusa", "via",
    "lyft", "brex", "gusto", "airwallex", "block", "samsara", "flexport",
    "databricks", "scaleai", "faire", "twilio", "datadog", "hubspot", "wayfair",
    # fintech and payments
    "robinhood", "coinbase", "chime", "sofi", "marqeta", "navan", "carta",
    "adyen", "intercom",
    # marketplaces, consumer and logistics
    "airbnb", "pinterest", "etsy", "turo", "opendoor", "thumbtack",
    "project44", "warbyparker", "sweetgreen", "thrivemarket", "nuro",
    "reddit", "discord", "squarespace",
    # software and data
    "dropbox", "asana", "figma", "gitlab", "mongodb", "elastic", "cloudflare",
    "toast", "pagerduty", "amplitude", "braze", "fivetran", "airtable",
    "webflow", "vercel", "datarobot", "gleanwork", "6sense",
]
LEVER = ["plaid", "palantir", "spotify"]
ASHBY = [
    "elevenlabs", "ramp", "openai", "perplexity-ai", "cohere",
    "notion", "linear", "rippling", "deel", "harvey", "sierra", "decagon",
    "mercury", "writer", "supabase",
]

# Nicer names for the email (slugs are ugly). Anything missing is auto-formatted.
COMPANY_NAMES = {
    "doordashusa": "DoorDash", "scaleai": "Scale AI", "perplexity-ai": "Perplexity",
    "openai": "OpenAI", "elevenlabs": "ElevenLabs", "hubspot": "HubSpot",
    "mongodb": "MongoDB", "gitlab": "GitLab", "pagerduty": "PagerDuty",
    "gleanwork": "Glean", "warbyparker": "Warby Parker", "thrivemarket": "Thrive Market",
    "datarobot": "DataRobot", "project44": "project44", "6sense": "6sense",
    "sofi": "SoFi", "fivetran": "Fivetran", "elastic": "Elastic",
    "plaid": "Plaid", "ramp": "Ramp", "cohere": "Cohere", "deel": "Deel",
}

# ---------------------------------------------------------------------------
# 2. Your target companies. Jobs here get a bonus. Names are matched as
#    whole words. Use "|" for alternate names.
# ---------------------------------------------------------------------------
TARGET_COMPANIES = [
    "Uber", "DoorDash", "Salesforce", "Stripe", "Amazon", "Google", "SAP",
    "Deloitte", "EY|Ernst & Young", "P&G|Procter & Gamble", "Coca-Cola|Coca Cola",
    "Walmart", "Target", "Via", "Okta", "Carvana", "Affirm", "Fidelity",
    "Instacart", "LinkedIn", "NVIDIA", "PayPal", "Mastercard",
]

# Companies whose jobs should use your AI/Tech resume.
AI_COMPANIES = [
    "OpenAI", "Anthropic", "ElevenLabs", "Databricks", "Scale AI", "Glean",
    "Perplexity", "Cohere", "NVIDIA", "Mistral", "Hugging Face", "Runway",
    "Harvey", "Sierra", "Decagon", "Anysphere", "Cursor", "Writer", "DataRobot",
]

# ---------------------------------------------------------------------------
# 3. Adzuna search (needs free keys, skipped if not set).
#    This is how big employers on Workday or their own sites get covered.
#    The free plan is roughly 1,000 searches a month, so keep this under
#    about 30 searches a day (queries x locations + companies).
# ---------------------------------------------------------------------------
ADZUNA_QUERIES = [
    "partnerships manager",
    "business development manager",
    "key account manager",
    "category manager",
    "revenue growth management",
    "commercial manager",
    "customer development manager",
    "sales manager",
]
ADZUNA_LOCATIONS = [""]  # "" = all of the US

# One search per company, for employers you cannot read directly.
ADZUNA_COMPANIES = [
    "Uber", "Salesforce", "Amazon", "Google", "SAP", "Deloitte", "EY",
    "Procter & Gamble", "Coca-Cola", "Walmart", "Target", "Carvana",
    "Fidelity", "LinkedIn", "NVIDIA", "PayPal", "Mastercard", "Unilever",
    "Colgate-Palmolive", "Reckitt", "PepsiCo", "Mondelez", "Kimberly-Clark",
]
ADZUNA_COMPANY_WORDS = (
    "partnership partnerships business development account category vendor "
    "channel revenue strategy"
)

# ---------------------------------------------------------------------------
# 4. Which job titles count (policy track is off for now)
# ---------------------------------------------------------------------------
# Checked in this order. The first track that matches the title wins.
TRACKS = {
    "partnerships": {
        "label": "Partnerships / BD",
        "weight": 40,
        "patterns": [
            r"partner", r"business development", r"\bbd\b",
            r"alliances?", r"channel", r"customer development",
        ],
    },
    "category": {
        "label": "Category / RGM / Strategy",
        "weight": 38,
        "patterns": [
            r"category (manager|management|lead|analyst|strategy)",
            r"revenue growth", r"\brgm\b",
            r"commercial (manager|lead|analyst|operations|excellence|planning|strategy|finance)",
            r"pricing strategy", r"revenue management",
            r"trade (planning|terms|strategy)", r"demand planning",
            r"supplier", r"vendor manager",
            r"marketplace (manager|lead|operations|strategy)",
            r"market research", r"\bbuyer\b",
        ],
    },
    "accounts": {
        "label": "Account Management",
        "weight": 35,
        "patterns": [
            r"account manage", r"key account", r"strategic account",
            r"national account", r"account executive", r"customer business",
            r"sales manager",
            r"customer account",
        ],
    },
    # Corporate roles close to your background. Lower weight than the three above.
    "corporate": {
        "label": "Corporate / Commercial Ops",
        "weight": 28,
        "patterns": [
            r"business operations", r"commercial operations", r"sales operations",
            r"strategy (and|&) operations", r"strategy (manager|lead)",
        ],
    },
}

# Titles containing any of these are dropped.
# Director and above are out. Entry-level and field sales are out.
EXCLUDE_TITLE = [
    r"director", r"\bvp\b", r"vice president", r"head of", r"chief",
    r"\bpresident\b", r"\bintern", r"junior", r"\bjr\b", r"entry.level",
    r"sales development", r"\bsdr\b", r"\bbdr\b", r"representative", r"\brep\b",
    r"territory", r"district", r"account developer",
    r"engineer", r"developer", r"software", r"technical", r"data scientist",
    r"recruit", r"talent", r"designer", r"counsel", r"attorney",
    r"accountant", r"human resources", r"people partner", r"business partner",
    r"finance partner", r"strategic finance",
    r"coordinator", r"assistant", r"administrator",
    r"marketing", r"financial manager", r"financial analyst", r"\bsupport\b",
    r"sourcing", r"procurement", r"\bsmb\b", r"small business", r"new business",
]

# ---------------------------------------------------------------------------
# 5. Locations (US only)
# ---------------------------------------------------------------------------
US_ONLY = True
# Priority cities. A match gets the top location score.
TIER1_CITIES = [
    "new york", "nyc", "brooklyn", "manhattan",
    "chicago",
    "los angeles", "santa monica", "san francisco", "bay area", "palo alto",
    "oakland", "san jose", "mountain view", "sunnyvale", "menlo park",
    "redwood city",
    "houston", "dallas", "austin", "texas",
    "boston", "massachusetts",
    "atlanta",
]
LOC_POINTS_TIER1 = 15
LOC_POINTS_REMOTE = 9    # remote in the US
LOC_POINTS_OTHER_US = 5  # any other US city

# ---------------------------------------------------------------------------
# 6. Scoring
# ---------------------------------------------------------------------------
POSITIVE_KEYWORDS = [
    "partnership", "channel", "reseller", "marketplace", "saas", "p&l",
    "key account", "strategic account", "enterprise", "category management",
    "supplier", "vendor", "negotiat", "last-mile", "last mile",
    "ride-hailing", "ride hailing", "e-commerce", "ecommerce", "fmcg", "cpg",
    "pricing", "forecast", "go-to-market", "gtm", "amazon", "wholesale",
    "b2b", "fintech", "payments", "emerging markets", "artificial intelligence",
]
NEGATIVE_KEYWORDS = [
    "territory", "field sales", "merchandis", "store visits", "cold calling",
    "door-to-door", "commission only", "security clearance",
]

TARGET_COMPANY_BONUS = 8     # company is on your target list
NEW_COMPANY_BONUS = 8        # you have not applied there before
ATS_BONUS = 6                # read directly from the company's own job feed
COMPANY_COOLDOWN_DAYS = 60   # recent application = penalty and a warning flag
MAX_PER_COMPANY = 2          # most roles from one company in one email

# Visa sponsorship signals. Many postings say nothing, so "unknown" stays in.
DROP_NO_SPONSORSHIP = False  # False = keep them, labelled "Says no sponsorship"
NO_SPONSOR_PENALTY = 10      # ranks them a little lower. Set to 0 for no penalty.
SAYS_SPONSORS_BONUS = 15
ON_SPONSOR_LIST_BONUS = 10   # company is in sponsors.csv

# Words searched on each Workday board. Titles are then judged by TRACKS and
# EXCLUDE_TITLE above, exactly as for every other source.
WORKDAY_TERMS = [
    "partnership", "business development", "account manager", "key account",
    "category", "revenue growth", "channel", "customer business",
    "commercial", "customer development", "pricing strategy", "revenue management",
    "sales manager", "sales operations", "business operations",
]
FETCH_BUDGET_S = 2400   # stop reading more Workday companies after 40 minutes

MAX_AGE_HOURS = 720           # 30 days. Each job is only emailed once.
ADZUNA_MAX_DAYS = 30
FRESH_24H_BONUS = 10         # newer postings rank higher
FRESH_72H_BONUS = 5
DEBUG_COMPANIES = ["Lyft"]  # prints what happened to these companies in the run log
MIN_SCORE = 50
TOP_N = 25
LLM_POOL = 40
MIN_FIT = 5
LLM_MODEL = "claude-haiku-5-5"

PROFILE_SUMMARY = """
Mahin Rao. Based in Chicago. US job search, open to relocation and remote.
10+ years of commercial experience across FMCG, enterprise SaaS, e-commerce
and B2B partnerships in Pakistan and MENAP.
- Retailo Technologies: Senior Category Manager and Senior BD Manager.
  Launched a BNPL product, managed supplier joint business plans with 125+
  partners, sold a patented SaaS platform, built a $2M+ pipeline.
- Leverify LLC: Partnership Manager, North America. Owned supplier
  relationships, buying, margins, credit terms, forecasting and Amazon FBA
  inventory for an electronics wholesale distributor (about $4M a year with
  one supplier). Managed a team.
- Packages Limited: B2B account owner for a $7.9M portfolio selling packaging
  to Unilever, Colgate and Reckitt. Won back $3.6M of Colgate volume.
- Hilal Foods: built an institutional B2B sales channel from zero.
- Strengths: quota-carrying sales, strategic and enterprise account
  management, partner channels (SI, affiliate, reseller), negotiating $2M+
  deals with Director and Head level stakeholders, category management, P&L
  ownership. Managed 3 to 4 reports.
- Education: MA Public Policy (Harris, UChicago), MBA (IBA Karachi),
  BBA (NUCES). Also AI governance and TA work at Chicago Booth.
- Has NOT run a field retail sales territory.
- Has little US employer history, so one level below his experience is fine.
Targets: commercial roles (partnerships, BD, account management, category
management, revenue growth management, vendor management) at CPG, retail,
e-commerce, marketplace, fintech, SaaS, and AI companies. Level: Associate to
Senior Manager. Not Director. Not policy roles.
""".strip()
