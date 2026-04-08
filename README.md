# Business Plan Writer

> Feed it a client intake. Get back an investor-ready business plan.

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Groq](https://img.shields.io/badge/Groq-llama--3.3--70b-F55036?style=flat-square)](https://groq.com)
[![Anthropic](https://img.shields.io/badge/Anthropic-Claude-D97706?style=flat-square)](https://anthropic.com)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o-74AA9C?style=flat-square)](https://openai.com)

Five specialized agents. One clean document. No manual drafting.
Each agent now applies expert personas as internal reasoning lenses (not extra agents).

---

## How it works

```
  intake.json
       │
       ▼
  ┌────────────┐     ┌────────────┐     ┌────────────┐     ┌────────────┐     ┌────────────┐
  │  Agent 1   │────▶│  Agent 2   │────▶│  Agent 3   │────▶│  Agent 4   │────▶│  Agent 5   │
  │ Validator  │     │  Market    │     │ Financial  │     │   Writer   │     │   Critic   │
  │            │     │  Builder   │     │  Checker   │     │            │     │            │
  └────────────┘     └────────────┘     └────────────┘     └────────────┘     └────────────┘
  llama-3.3-70b      llama-3.3-70b      llama-3.3-70b      ★ configurable     llama-3.3-70b
  Groq (default)     Groq (default)     Groq (default)     per-agent env      Groq (default)
       │                   │                  │                   │                  │
       ▼                   ▼                  ▼                   ▼                  ▼
  Completeness        Market Intel       Financial           Full Plan          Quality Score
  Score + Flags       + Positioning      Credibility         (markdown)         + Approval
                                         Rating

                                                                  │
                                                     ┌────────────┴────────────┐
                                                     ▼                         ▼
                                                  plan.docx                plan.pdf
                                               (python-docx)          (docx2pdf / reportlab)
```

> **Agent 4** supports a separate `LLM_PROVIDER_WRITER` + `LLM_MODEL_WRITER` — run a premium model (e.g. Claude Sonnet) just for the writing step while keeping other agents on fast, free-tier Groq.
>
> **SaaS detection** is automatic — tech/software clients get an enriched founder-persona loaded transparently.

---

## Quickstart

```bash
git clone https://github.com/WBHankins93/business-plan-writer.git
cd business-plan-writer

python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env.local   # add your API keys
venv/bin/python main.py --intake sample_intake/sample_client.json
```

Output lands in `output/documents/` as both `.docx` and `.pdf`.

Run tests:

```bash
python -m unittest discover -s tests -p "test_*.py"
```

---

## CLI

```
python main.py --intake <path>          Required. Path to client intake JSON.
               --output-dir <path>      Optional. Default: output/documents/
               --no-pdf                 Optional. Skip PDF, produce .docx only.
               --allow-unready          Optional. Continue even if Agent 1 says intake is not ready.
```

---

## Configuration

```bash
# .env.local

# Standard agents (1, 2, 3, 5)
LLM_PROVIDER=groq
LLM_MODEL=llama-3.3-70b-versatile

# Agent 4 — writer (optional override for higher quality)
LLM_PROVIDER_WRITER=anthropic
LLM_MODEL_WRITER=claude-sonnet-4-6

# API keys
GROQ_API_KEY=...
ANTHROPIC_API_KEY=...
OPENAI_API_KEY=...

# Reliability controls (optional)
LLM_TIMEOUT_SECONDS=60
LLM_MAX_RETRIES=3
LLM_RETRY_BACKOFF_SECONDS=1.25
```

Supported providers: `groq` · `anthropic` · `openai`

---

## The 5-Agent Pipeline (Persona-Enhanced)

| # | Role | Internal persona lens | Output |
|---|------|---------|--------|
| 1 | **Intake Validator** | Startup Operator | Completeness score, missing field flags, actionability checks |
| 2 | **Market Builder** | GTM Strategist + VC Partner | Market analysis with ICP, positioning, channel and market logic |
| 3 | **Financial Checker** | Financial Analyst + Startup Operator | Credibility rating, cash flow risks, assumption quality |
| 4 | **Plan Writer** | Business Plan Architect _(+ SaaS Founder if detected)_ | Full business plan (markdown) |
| 5 | **Critic** | Red Team + VC Partner + GTM Strategist | Stress-tested critique, confidence score, GO/CONDITIONAL/NO-GO |

The intake schema covers **12 sections** and **60+ fields**, classified into three tiers: critical, structural, and enhancement. Thin or vague answers are detected regardless of length.

### Why this improves output quality

- **No architecture churn:** pipeline remains the same 5-agent sequence.
- **Higher decision quality:** each agent applies role-specific expert heuristics instead of generic prose generation.
- **Better risk handling:** disagreements and weak assumptions are surfaced explicitly, with conservative defaults in evaluation stages.
- **No persona bleed:** personas are scoped by agent role and do not create a new orchestration layer.

---

## Stack

- **Runtime:** Python 3.11+, Groq SDK, Anthropic SDK, OpenAI SDK
- **Documents:** `python-docx`, `docx2pdf`, `reportlab`
- **Console:** `rich`
- **Prompts:** local layered identity system (`foundation → standards → persona`)

---

## Status

Phase 1 — core pipeline — is complete and end-to-end functional.

**Phase 2** (in development): CLI intake questionnaire + Next.js web app with FastAPI backend.
