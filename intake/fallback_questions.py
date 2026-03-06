"""
intake/fallback_questions.py
Follow-up questions triggered when a Tier 2 field answer is thin or vague.

Each entry maps a field name to 3 targeted follow-up questions.
Agent 1 (Validator) uses these to request more detail from the user
during the interactive intake phase (Phase 2).
"""

FALLBACK_QUESTIONS: dict[str, list[str]] = {
    # ── Business Information ───────────────────────────────────────────────────
    "business_stage": [
        "Is this business currently generating revenue, or is it pre-launch?",
        "How long has the business been operating (if at all)?",
        "What phase would you describe it as — idea, early traction, or established?",
    ],
    "funding_purpose": [
        "Are you applying for a bank loan, SBA loan, grant, or seeking an investor?",
        "Is this plan for a specific lender or institution — and do you know their requirements?",
        "What will the funded capital primarily be used for?",
    ],
    "funding_amount": [
        "What is the total dollar amount you are seeking to raise or borrow?",
        "Is this a one-time funding need or an ongoing line of credit?",
        "What is the minimum amount that would allow the business to launch or hit the next milestone?",
    ],
    "location": [
        "Where is the business physically located or operating from?",
        "Do you serve clients locally, regionally, or nationwide?",
        "Will you have a physical office, clinic, or retail space — or operate remotely?",
    ],

    # ── Management Details ─────────────────────────────────────────────────────
    "management_team": [
        "Who else besides the owner is involved in running the business day-to-day?",
        "What key roles are filled, and what are those people's qualifications?",
        "Is any team member a co-founder or equity holder?",
    ],
    "hiring_plans": [
        "What are the first roles you plan to hire for, and when?",
        "Will you use employees, contractors, or both?",
        "What is the estimated annual cost for planned hires in Year 1?",
    ],

    # ── Product / Service Summary ──────────────────────────────────────────────
    "service_delivery": [
        "Do clients come to you, or do you go to them — or is it remote/virtual?",
        "How long does a typical service engagement last (per session, per project, ongoing)?",
        "What software, tools, or platforms support your service delivery?",
    ],
    "pricing_structure": [
        "What does a single session or engagement cost the client?",
        "Do you bill insurance, accept self-pay, or both?",
        "Do you offer packages, memberships, or any other bundled pricing?",
    ],
    "differentiators": [
        "What do clients say is the main reason they chose you over others?",
        "Is there a credential, specialty, method, or niche that sets you apart?",
        "What do competitors NOT offer that you do?",
    ],

    # ── Sales Strategy ─────────────────────────────────────────────────────────
    "sales_process": [
        "How does a potential client first find out about you?",
        "What steps happen between first contact and becoming a paying client?",
        "How long does it typically take to convert a lead into a client?",
    ],
    "payment_terms": [
        "Do clients pay at the time of service, or do you bill after?",
        "Do you work with health insurance panels, and if so which ones?",
        "What is your cancellation or no-show policy and associated fees?",
    ],
    "retention_strategy": [
        "What keeps clients coming back beyond the initial engagement?",
        "Do you have a formal follow-up process for inactive clients?",
        "What is your typical client lifespan (how long do clients stay)?",
    ],
    "referral_sources": [
        "Where do most of your new clients come from today (or where do you expect them to come from)?",
        "Do you have formal referral relationships with other providers or organizations?",
        "Have you or will you pursue insurance panel listings to drive referrals?",
    ],

    # ── Market Analysis ────────────────────────────────────────────────────────
    "market_size": [
        "How large is the potential client base in your target geographic area?",
        "Is the demand for your service growing, stable, or declining in your market?",
        "Are there any published statistics or data on the size of your specific market?",
    ],
    "industry_state": [
        "What major trends are shaping your industry right now?",
        "Is your industry experiencing growth — and what is driving it?",
        "Are there regulatory changes or reimbursement shifts affecting providers like you?",
    ],
    "customer_pain_points": [
        "What is the core problem your ideal client is trying to solve?",
        "Why is the existing set of options (other providers, alternatives) insufficient for them?",
        "What emotional or practical frustrations motivate your target client to seek help?",
    ],

    # ── Advertising Strategy ───────────────────────────────────────────────────
    "marketing_budget": [
        "How much do you plan to spend on marketing per month in Year 1?",
        "Is this budget split across multiple channels, or concentrated in one area?",
        "At what revenue milestone would you increase the marketing budget?",
    ],
    "digital_presence": [
        "Do you have or plan to build a website, and what is its purpose?",
        "Which social media platforms are most relevant to your target clients?",
        "Are you investing in SEO, Google Ads, or any paid digital channels?",
    ],

    # ── Competition ────────────────────────────────────────────────────────────
    "market_gaps": [
        "Who is currently underserved in your market that you can specifically reach?",
        "What unmet need does your business address that competitors ignore?",
        "Is there a geographic area, demographic, or specialty niche with too few providers?",
    ],

    # ── Strategy and Implementation ────────────────────────────────────────────
    "near_term_priorities": [
        "What are the 3 most important things you need to accomplish in the next 90 days?",
        "What must be true for the business to be operationally ready to serve clients?",
        "Which tasks or decisions have the highest leverage on your success right now?",
    ],
    "key_risks": [
        "What is the biggest threat to the success of this business?",
        "What happens if client acquisition takes longer than expected — what's the fallback?",
        "Are there regulatory, licensing, or compliance risks that could delay or disrupt operations?",
    ],

    # ── Milestones ─────────────────────────────────────────────────────────────
    "twenty_four_month_goals": [
        "Where do you want the business to be in 24 months in terms of revenue and client volume?",
        "Will you have hired staff, expanded locations, or added services by then?",
        "What does success look like to you personally at the 2-year mark?",
    ],
    "key_metrics": [
        "What numbers do you track weekly or monthly to know the business is healthy?",
        "What is your target revenue by end of Year 1?",
        "At what client volume or revenue level will you consider the business stable?",
    ],

    # ── Financial Information ──────────────────────────────────────────────────
    "break_even_point": [
        "At what monthly revenue does the business cover all expenses?",
        "How many clients per month does that require at your current pricing?",
        "How many months do you project it will take to reach break-even?",
    ],

    # ── Income ─────────────────────────────────────────────────────────────────
    "annual_revenue_projection": [
        "What is your projected total revenue for Year 1?",
        "What do you expect Year 2 revenue to be, and what drives that growth?",
        "Are your projections based on a specific client volume target?",
    ],
    "revenue_sources": [
        "Do you have multiple service lines or offerings — and how much does each contribute?",
        "What percentage of revenue comes from insurance vs. self-pay vs. other sources?",
        "Are there any one-time revenue events (grants, consulting contracts) you're projecting?",
    ],

    # ── Expenses ───────────────────────────────────────────────────────────────
    "payroll": [
        "What is the owner's planned monthly draw or salary?",
        "Will you pay any employees or contractors in Year 1, and what is the estimated cost?",
        "How does payroll change in Year 2 as you grow?",
    ],
    "rent_utilities": [
        "What is your monthly rent or office/clinic cost?",
        "Are you working from home, subleasing, or signing a commercial lease?",
        "What utilities, internet, or facility costs are included in your overhead?",
    ],
    "other_operating": [
        "What software subscriptions, EHR, billing platforms, or tools do you pay for monthly?",
        "What professional fees (accountant, attorney, malpractice insurance) do you carry?",
        "Are there licensing, credentialing, or association fees relevant to your practice?",
    ],
}
