# SMART

[![DOI](https://zenodo.org/badge/1276008767.svg)](https://doi.org/10.5281/zenodo.20784735)

Reference implementation of **SMART** - *Structured, Meaningful, Auditable, Responsible, and Transparent* - a framework for documenting clinical AI, described in the accompanying research paper.

SMART has three parts:

- a **schema-validated model card template** (seven sections) aligned with the OMOP Common Data Model;
- a **governed lifecycle** with role-based approval; and
- a **blockchain audit trail** that records a content hash of each card version.

Only the content hash, content URI, lifecycle status, and the actor addresses are written on-chain; the full card content is held off-chain.

## Demo

<video src="https://github.com/AnkurLohachab/SMART/raw/main/smart-explainer.mp4" controls width="100%"></video>

A short walkthrough of SMART and the model-card lifecycle ([smart-explainer.mp4](smart-explainer.mp4)).

## Components

| Layer | Stack | Responsibility |
| --- | --- | --- |
| Template & schema | [`smart-model-card`](https://pypi.org/project/smart-model-card/) (MIT) | Seven-section schema, controlled enumerations, subgroup/metric checks, JSON/HTML/Markdown export |
| OMOP integration | [`smart-omop`](https://pypi.org/project/smart-omop/) (MIT) | Cohort definitions and concept resolution against the OHDSI WebAPI |
| Smart contracts | Solidity / Hardhat | Lifecycle state machine, role-based access, SHA-256 hash anchoring, soulbound provenance |
| Backend | FastAPI | Lifecycle endpoints, Neo4j writes, MinIO storage, OHDSI proxy |
| Frontend | Next.js | Authoring UI, lifecycle dashboards, registry |
| Storage | MinIO + Neo4j | Card JSON (MinIO); lineage / status / event graph (Neo4j) |

The template and OMOP integration are the separately published packages [`smart-model-card`](https://pypi.org/project/smart-model-card/) and [`smart-omop`](https://pypi.org/project/smart-omop/); this repository is the surrounding framework (contracts, services, and the requirements-analysis pipeline).

## Repository structure

```
SMART/
  backend/                  FastAPI service: lifecycle API, OHDSI proxy, Neo4j/MinIO I/O
    app/                    routes/, utils/, models, config, main.py
  frontend/                 Next.js app: authoring UI, lifecycle dashboards, registry
    app/, components/, lib/, contexts/, config/
  contracts/                Hardhat / Solidity
    src/                    account/, core/, lifecycle/, utils/  (deployed, Sourcify-verified)
    scripts/                deploy-local.js
    tests/
  requirements-analysis/    regulatory requirements-extraction pipeline
    extractors/             regex + LLM extractors (pluggable Protocol)
    lib/                    canonicalisation, partition, coverage mapping
    vocabulary/             closed-vocabulary CSVs
    sample_results/         committed pipeline outputs
    run.py
  evaluation/
    sample_results/         gas-benchmarks/, tamper-detection/, lineage-reconstruction/,
                            separation-of-duties/, bytecode-identity/, determinism/
  offchain/                 standalone Neo4j + MinIO compose
  docker-compose.yml        full local stack
  docker-compose.amoy.yml   Polygon Amoy deployment overlay
  smart-explainer.mp4       explainer video
```

## Lifecycle states

Created -> InEvaluation -> {Validated, Rejected, RevisionRequested -> Revised} -> Published -> Deprecated.

Rejection and Deprecation are terminal. Each transition is gated by a smart-contract role (AIDeveloper, Authenticator, Publisher, Admin), and every transition writes an audit record (actor, from/to state, content hash, timestamp) to the ledger.

## Quick start

Prerequisites: Docker + Docker Compose, Node.js 20+, Python 3.11+.

```bash
cp backend/.env.example backend/.env          # then fill in values
cp frontend/.env.local.example frontend/.env.local
docker compose up -d
# wait for hardhat, neo4j, minio, backend, frontend to become healthy
open http://localhost:3000
```

This brings up the local stack: a Hardhat node with the contracts deployed, Neo4j, MinIO, the FastAPI backend, and the Next.js frontend. `docker-compose.amoy.yml` is an overlay for running the backend against the Polygon Amoy testnet instead of a local chain.

### Local development keys

No private keys are committed to this repository. For local development, `npx hardhat node` prints a set of funded test accounts and their private keys; copy the ones you need into `backend/.env`:

- `RELAYER_PRIVATE_KEY` - the account the backend uses to relay transactions.
- `HARDHAT_TEST_ACCOUNTS` - a JSON map `{"address": "private_key", ...}` of the test signers used to act as the AIDeveloper / Authenticator / Publisher roles locally.

These are local throwaway accounts only. For a testnet deployment, set `AMOY_PRIVATE_KEY` and the deployer address via the environment instead (see `docker-compose.amoy.yml`).

### Deployed contracts (Amoy)

The addresses and role hashes in `docker-compose.amoy.yml` are my Amoy deployment. They're public, so you can check them on PolygonScan. To run your own, redeploy on Amoy and swap in your addresses (and the role hashes if you rename any roles).

## Requirements-analysis pipeline

This pipeline ingests the regulatory corpus, extracts `(bearer, predicate, artefact)` obligation tuples, canonicalises them against a closed vocabulary, partitions them into equivalence classes (the provision count *N*), and maps each to a SMART component.

```
ingest (PDF/HTML -> paragraphs) -> extract (regex + LLM extractors, same Protocol)
  -> canonicalise (closed vocabulary) -> partition (equivalence classes)
  -> coverage (map to SMART Schema / Lifecycle / Chain)
```

- Extractors are pluggable: `RegexExtractor` (deterministic baseline) plus LLM extractors. Reviewers can swap the model or the `vocabulary/*.csv` files and observe the sensitivity of *N*.
- Run (container-only): `cd requirements-analysis && docker compose run --rm requirements-analysis python run.py`
- Outputs land in `requirements-analysis/sample_results/`: `provisions.csv` (one row per provision), `partition.json` (source clauses per provision), and `provision_breakdown.json`.

### Source corpus

The pipeline operates on the public documents below. They are **not redistributed** here; retrieve them from the official publishers and place them in `requirements-analysis/docs/` to run the pipeline.

| File | Document | Publisher | Access |
| --- | --- | --- | --- |
| `eu_mdr_2017_745.pdf` | Regulation (EU) 2017/745 (EU MDR) | EUR-Lex, ELI `reg/2017/745/oj` | Open |
| `eu_ai_act_2024_1689.pdf` | Regulation (EU) 2024/1689 (AI Act) | EUR-Lex, ELI `reg/2024/1689/oj` | Open |
| `fda_ai_ml_action_plan_2021.pdf` | AI/ML-Based SaMD Action Plan | U.S. FDA | Open |
| `fda_pccp_guidance_2024.pdf` | Predetermined Change Control Plan guidance | U.S. FDA | Open |
| `fda_lifecycle_draft_2025.pdf` | AI-Enabled Device Software Lifecycle Management (draft, FDA-2024-D-4488) | U.S. FDA | Open |
| `tripod_ai_2024.pdf` | TRIPOD+AI statement | BMJ | Open access |
| `iso_29119_11_2020_landing.html` | ISO/IEC TR 29119-11:2020 | ISO | **Paywalled** - abstract/scope only; not redistributable |
| `iso_24028_2020_landing.html` | ISO/IEC TR 24028:2020 | ISO | **Paywalled** - abstract/scope only; not redistributable |

## Evaluation results

`evaluation/sample_results/` holds committed outputs from the on-chain evaluation, grouped by experiment. Each `run-NN` is one independent execution; replicate runs back the pooled statistics in the `*_aggregated.json` files.

| Folder | Experiment |
| --- | --- |
| `gas-benchmarks/` | Per-operation gas cost on Polygon Amoy (18 replicate runs) |
| `tamper-detection/` | Insider-tamper attempts, independent on-chain verification, liveness, bytecode attestation |
| `lineage-reconstruction/` | Version-lineage reconstruction from on-chain records |
| `separation-of-duties/` | Role / conflict-of-interest enforcement attack matrix |
| `bytecode-identity/` | Byte-identity check (contracts compiled twice) |
| `determinism/` | Run-to-run determinism of the evaluation harness |

All wallet addresses and transaction hashes in these files are public Polygon Amoy testnet data, independently verifiable on PolygonScan.

## Third-party services

The Docker setup pulls two external services as unmodified official images; they run as separate network services and do not affect this repository's MIT license:

- **MinIO** (`minio/minio`) - object storage, licensed AGPL-3.0.
- **Neo4j Community** (`neo4j:*-community`) - graph database, licensed GPL-3.0. (Do not substitute the Enterprise image without a commercial license.)

## Author

**Ankur Lohachab** - ankur.lohachab@maastrichtuniversity.nl
Department of Advanced Computing Sciences (DACS), Maastricht University

## License

MIT - see [LICENSE](LICENSE).

## Citation

If you use this work, please cite the accompanying paper (citation to be added on acceptance) and the archived release: https://doi.org/10.5281/zenodo.20784735.

## Note

I have refactored this repository relative to the code used for the paper's experiments: I reorganised it for clarity, so its directory structure and some implementation details differ from the research version, while the framework's documented behaviour is unchanged. If you encounter any issues, please contact me at ankur.lohachab@maastrichtuniversity.nl.
