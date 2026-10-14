# Security Research Assistant PoC

## What it does

This proof of concept turns official defence and security strategy PDFs into traceable, reviewable threat-category evidence:

Official PDF → extraction and cleaning → traceable source passages → deterministic threat matching → mentions per 1,000 words → human verification.

## Threat categories

- Russia
- Hybrid
- Cyber
- China
- Migration

Hybrid and Cyber are separate categories.

## Documents in demo

- Latvia — State Defence Concept 2023–2027
- United Kingdom — Strategic Defence Review 2025
- Netherlands — Defence White Paper 2024

## Methodology

The baseline uses a compact English dictionary with deterministic regular-expression and phrase matching. Frequencies are normalized as category mentions per 1,000 analysed words, and every match retains PDF-page and source-passage traceability. Researchers can mark matches Relevant or Irrelevant without changing matcher output.

This PoC does not reproduce SETA's original multilingual dictionary exactly. Its current Russia-frequency ordering is Latvia > Netherlands > United Kingdom; this is a result of the compact PoC methodology and is not a claim that the source report's full ordering was reproduced.

## Local run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app/app.py
```

## Docker

Build the image:

```bash
docker build -t security-research-assistant .
```

Run it:

```bash
docker run --rm -p 8501:8501 security-research-assistant
```

Then open [http://localhost:8501](http://localhost:8501).

The image includes the existing processed analysis outputs so the demo can start without running PDF extraction inside the container.

## Researcher verification

Source matches can be marked Relevant or Irrelevant, or cleared back to Unreviewed. Decisions are stored under `data/reviews/`, separately from deterministic matcher results.

## Limitations

- The original SETA multilingual dictionary is unavailable.
- The baseline uses a compact English-only dictionary.
- Mention frequency is not a measure of threat severity.
- The Netherlands two-page spread layout requires document-specific extraction and segmentation handling.
- Semantic framing and LLM-based interpretation are outside this baseline.
