"""Conservative non-sensitive employer answers grounded in the approved profile.

Never infer demographics, non-compete restrictions, privacy-policy consent,
work eligibility beyond approved wording or applicant history at an employer.
"""
import re
import html

LINKEDIN = "https://www.linkedin.com/in/raomahin/"

PRIOR_EMPLOYER_NAMES = (
    "doordash", "mozilla", "xometry", "stackadapt", "fc cincinnati",
    "eagle business credit", "burris logistics", "honor foods",
    "trinity logistics", "sunny morning foods", "r.w. zant",
)

def _salary_midpoint(job, label):
    """Only accept one unambiguous advertised annual BASE salary range."""
    text=html.unescape(re.sub(r"<[^>]+>", " ", job.get("content","") or ""))
    ranges=[]
    for source in (label, text):
        for m in re.finditer(r"\$([\d,]{5,8})\s*(?:-|–|—|to)\s*\$([\d,]{5,8})",source,re.I):
            left,right=int(m[1].replace(",","")),int(m[2].replace(",",""))
            context=source[max(0,m.start()-110):m.end()+70].lower()
            if 40000<=left<right<=450000 and any(word in context for word in ("salary","base pay","compensation","pay range","starting")):
                ranges.append((left,right))
    unique=set(ranges)
    if len(unique)!=1:
        return None
    a,b=next(iter(unique))
    return (a+b)//2

def confirmed_fact(label, app, job, profile):
    p=profile.get("_confirmed",{})
    if not p:
        return None
    q=re.sub(r"\s+"," ",label or "").strip().lower()
    if p.get("prior_employment_at_named_employers") == "none":
        if re.search(r"(?:have you|were you).*?(?:worked|employed|previously employed)",q):
            if any(name in q for name in PRIOR_EMPLOYER_NAMES) or any(name in app.get("company","").lower() for name in PRIOR_EMPLOYER_NAMES):
                return "No"
        if "previously worked at" in q and any(name in q for name in PRIOR_EMPLOYER_NAMES):
            return "No"
    if p.get("restrictive_agreements") == "none":
        if re.search(r"non[- ]?compete|non[- ]?solicit|confidentiality agreement",q):
            if re.search(r"do you have|are you subject|have you signed",q):
                return "No"
    if p.get("recruiter_sms") == "yes":
        if ("sms" in q or "whatsapp" in q) and re.search(r"receive|recruit|contact|communications",q):
            return "Yes"
    if p.get("specialized_experience") == "none":
        if re.search(r"fortune 500.*(?:customer|client)|(?:customer|client).*fortune 500",q):
            return "No"
        if re.search(r"experience (?:in|with).*?(?:aerospace|defen[sc]e|biotech|architectural specification|\ba&d\b)",q):
            return "No"
    if p.get("salary_preference") == "advertised_range_midpoint":
        if re.search(r"(?:(?:expected|desired|looking for).{0,35}(?:salary|base pay|compensation)|(?:salary|compensation).{0,35}(?:range|expectation))",q):
            # Total compensation is not inferred without incentives information.
            if "total compensation" in q and "base" in q:
                return None
            midpoint=_salary_midpoint(job,label)
            if midpoint is not None:
                return "$"+format(midpoint,",")
            # Baseline 80K-100K previously approved; use $90K midpoint.
            return "$90,000"
    return None

def fact_answer(label, app, job, profile):
    confirmation=confirmed_fact(label,app,job,profile)
    if confirmation is not None:
        return confirmation
    q=re.sub(r"\s+"," ",label or "").strip().lower()
    if (re.search(r"are you currently authorized to work in the country",q)
            and re.search(r"country (?:outlined|listed) for this job",q)):
        loc=(job.get("location") or {}).get("name","")
        if re.search(r"\b(?:united states|usa|u\.s\.|chicago|new york|california|illinois|remote[- ]us)\b",loc,re.I):
            return "Yes"
    if re.search(r"linkedin\s*(?:profile|url)?",q):
        return LINKEDIN
    if re.search(r"(?:what|which|your).*?(?:time\s*zone|timezone)|(?:time\s*zone|timezone) you most",q):
        return "Central Time (CT)"
    if re.search(r"(?:confirm|are you|only considering).*?(?:based|located).*?(?:usa|united states)|based in the usa",q):
        return "Yes, I am based in Chicago, Illinois, USA."
    if re.search(r"\b(?:travel|traveling)\b",q) and re.search(r"\b(?:10-15%|50%|commit|comfortable)\b",q):
        return "Yes, I am comfortable with the stated travel requirements."
    if re.search(r"how did you (?:initially )?hear about",q):
        return "Online job posting."
    if re.search(r"how soon (?:would you be|are you) available to start",q):
        return "Three weeks"
    if re.search(r"what state do you (?:currently )?reside in|what is your state of residence",q):
        return "Illinois"
    if re.search(r"what city and state do you live in|what is your current (?:city|location)",q):
        return "Chicago, Illinois"
    if re.search(r"^(?:current employer|current job title)$",q):
        experience=profile.get("verified_experience") or []
        current=next((e for e in experience if e.get("period","").lower().endswith("present")),None)
        if current:
            return current.get("employer") if q=="current employer" else current.get("role")
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
