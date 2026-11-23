"""Conservative non-sensitive employer answers grounded in the approved profile.

Never infer demographics, non-compete restrictions, privacy-policy consent,
work eligibility beyond approved wording or applicant history at an employer.
"""
import re

LINKEDIN = "https://www.linkedin.com/in/raomahin/"

def fact_answer(label, app, job, profile):
    q=re.sub(r"\s+"," ",label or "").strip().lower()
    if re.search(r"linkedin\s*(?:profile|url)?",q):
        return LINKEDIN
    if re.search(r"(?:what|which|your)\s+(?:time\s*zone|timezone)|time zone you most",q):
        return "Central Time (CT)"
    if re.search(r"confirm (?:you.re|you are) based in (?:the\s+)?(?:usa|united states)|based in the usa",q):
        return "Yes, I am based in Chicago, Illinois, USA."
    if re.search(r"\b(?:travel|traveling)\b",q) and re.search(r"\b(?:10-15%|50%|commit|comfortable)\b",q):
        return "Yes, I am comfortable with the stated travel requirements."
    if re.search(r"how did you (?:initially )?hear about (?:this|the) job",q):
        return "Online job posting."
    if re.search(r"\b(?:are you|do you)\s+(?:at least|over)\s+18\b",q):
        return "Yes"
    if re.search(r"(?:compensation|pay|salary)\s+range",q) and re.search(r"comfortable moving forward|feel comfortable|meets your expectations",q):
        # User's baseline target is below many published ranges, but do not
        # infer acceptance of an exact new offer; only willingness to discuss.
        return "Yes, I am comfortable discussing the published range."
    if re.search(r"what excites you about this (?:position|role)|why (?:are you interested|do you want) to work",q):
        experience=profile.get("verified_experience") or []
        commercial=next((e for e in experience if e.get("employer")=="Leverify LLC"),None)
        if commercial:
            evidence=commercial.get("evidence","commercial strategy and supplier partnerships")
            return ("The "+app.get("title","role")+" at "+app.get("company","this company")+
                    " aligns with my focus on enterprise relationships, commercial strategy and strategic partnerships. "+
                    "At Leverify, my work included "+evidence+".")
    if re.search(r"at least two years (?:of )?(?:inside sales|business development|outbound)",q):
        return "Yes, I have more than ten years of commercial sales and business development experience."
    if re.search(r"experience .*?(?:cash flow|business funding|financial solutions)",q):
        return "At Leverify, I negotiated a $700K supplier credit facility and improved working capital through supplier partnerships and commercial operations."
    if re.search(r"have you sourced new business through outbound prospecting",q):
        return "Yes, I have developed new business through B2B sales outreach and partnerships."
    return None
