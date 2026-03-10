# Business Plan Writer

> Feed it a client intake. Get back an investor-ready business plan.

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Groq](https://img.shields.io/badge/Groq-llama--3.3--70b-F55036?style=flat-square)](https://groq.com)
[![Anthropic](https://img.shields.io/badge/Anthropic-Claude-D97706?style=flat-square)](https://anthropic.com)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o-74AA9C?style=flat-square)](https://openai.com)

Five specialized agents. One clean document. No manual drafting.

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

---

## CLI

```
python main.py --intake <path>          Required. Path to client intake JSON.
               --output-dir <path>      Optional. Default: output/documents/
               --no-pdf                 Optional. Skip PDF, produce .docx only.
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
```

Supported providers: `groq` · `anthropic` · `openai`

---

## The Agents

| # | Role | Persona | Output |
|---|------|---------|--------|
| 1 | **Intake Validator** | Decision Anchor | Completeness score, missing field flags |
| 2 | **Market Builder** | Pattern Seer | Market analysis, positioning intel |
| 3 | **Financial Checker** | Finance Dragon | Credibility rating, cash flow risks |
| 4 | **Plan Writer** | Business Plan Architect _(+ SaaS Founder if detected)_ | Full business plan (markdown) |
| 5 | **Critic** | Red Team + Builder-Refiner | 5-dimension quality score, approval decision |

The intake schema covers **12 sections** and **60+ fields**, classified into three tiers: critical, structural, and enhancement. Thin or vague answers are detected regardless of length.

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
