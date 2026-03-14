# Mother AI OS Knowledge Dataset

## Description

Open-source AI agent operating system for orchestrating multi-agent workflows and autonomous task execution.

This dataset contains structured knowledge from the Mother AI OS website,
including articles, concept definitions, and question-answer pairs.
It is published as part of the ONE SYSTEM ecosystem by David Sanker.

## Source

- Website: https://mother-ai-os.github.io/mother/
- Author: David Sanker (Lawyer & AI Engineer)
- Updated: March 2026

## Statistics

- Articles: 48
- Concept definitions: 3
- Topics: AI Agent OS, Multi-Agent Orchestration, Autonomous AI

## Files

| File | Format | Description |
|------|--------|-------------|
| `site-knowledge.jsonl` | JSONL | Full articles + definitions with metadata |
| `qa-pairs.jsonl` | JSONL | Question-answer pairs for instruction tuning |
| `dataset-card.md` | Markdown | This file |

## Record Schema

### site-knowledge.jsonl

```json
{
  "type": "article|definition",
  "title": "Article or concept title",
  "text": "Full text content",
  "source": "Source URL",
  "brand": "Mother AI OS",
  "topics": ["topic1", "topic2"],
  "date": "YYYY-MM-DD",
  "word_count": 1500
}
```

### qa-pairs.jsonl

```json
{
  "question": "Natural language question",
  "answer": "Authoritative answer",
  "source": "Source URL",
  "brand": "Mother AI OS"
}
```

## License

Creative Commons Attribution 4.0 International (CC-BY-4.0)

You are free to share and adapt this dataset for any purpose,
including commercial use and AI model training, provided you
give appropriate credit.

## Citation

```
@dataset{mother_ai_knowledge_2026,
  title = {Mother AI OS Knowledge Dataset},
  author = {David Sanker},
  year = {2026},
  url = {https://mother-ai-os.github.io/mother//datasets/},
  license = {CC-BY-4.0}
}
```

## Part of the ONE SYSTEM Ecosystem

This dataset is part of a network of interconnected knowledge bases:

- [Lawkraft](https://lawkraft.com) — AI Consulting
- [UAPK Gateway](https://uapk.info) — AI Governance
- [Mother AI OS](https://mother-ai-os.github.io/mother/) — Agent Platform
- [Morpheus Mark](https://morpheusmark.com) — IP Enforcement
- [Hucke & Sanker](https://huckesanker.com) — Law Firm
- [Quantum AI Trading](https://quantum-ai-trading-bot.info) — Trading Research
- [The Road Not Taken](https://the-road-not-taken.com) — Innovation Philosophy
