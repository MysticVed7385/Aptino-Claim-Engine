# Policy-Aware Multi-Agent RAG Claim Decision Engine

A policy-aware insurance claim analysis system that combines hybrid retrieval,
policy evidence extraction, multi-agent orchestration, rule-based decision
analysis, citation validation, and a FastAPI/Streamlit interface.

The system analyzes claim cases against an authoritative policy document and
produces a structured decision with supporting policy citations. It abstains
(`NEEDS_REVIEW`) when the available evidence does not support a safe
conclusion.

> **Not financial or medical advice.** Built as a decision-support prototype
> for a take-home assignment. It does not replace human claim adjudication.

---

## Live Demo

| | URL |
|---|---|
| **Frontend (Streamlit)** |  https://aptino-pdf-rag-claim-engine.streamlit.app/ |
| **Backend API (FastAPI)** | https://aptino-claim-engine-production.up.railway.app |
| **GitHub** | https://github.com/MysticVed7385/Aptino-Claim-Engine |

> The backend is exposed via a Cloudflare tunnel and requires the host machine
> to be online. See [Local Setup](#local-setup) to run it independently.

---

## Features

- PDF policy ingestion
- Page-aware and section-aware document chunking
- Dense vector retrieval using SentenceTransformers and FAISS
- Sparse retrieval using BM25
- Reciprocal Rank Fusion for hybrid retrieval
- Cross-encoder reranking
- Multi-agent claim analysis workflow
- Structured claim and decision schemas using Pydantic
- Evidence-based policy citations
- Citation and page-number validation
- Conservative `NEEDS_REVIEW` fallback
- FastAPI REST API
- Streamlit user interface
- Evaluation on 12 public and 5 additional test cases
- Failure analysis documentation

---

## System Architecture

```text
Policy PDF
    |
    v
PDF Ingestion -> Page Extraction -> Document Chunking
    |
    v
Policy Chunks + Page Metadata + Section Metadata + Chunk IDs
    |
    +----------------------+----------------------+
    v                      v
Dense Retrieval       Sparse Retrieval
SentenceTransformers  BM25
FAISS
    |                      |
    +----------+-----------+
               v
    Reciprocal Rank Fusion
               |
               v
       Cross-Encoder Reranking
               |
               v
       Multi-Agent Workflow
               |
     +---------+---------+
     v         v         v
Case       Policy     Coverage
Analysis   Evidence   Agent
Agent      Agent
     +---------+---------+
               v
         Decision Agent
               |
               v
        Validation Agent
               |
               v
          Final Decision
          - Findings
          - Limits
          - Missing Evidence
          - Policy Citations
          - Validation Result