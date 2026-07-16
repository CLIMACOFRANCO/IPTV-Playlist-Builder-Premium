# Tavily Agent Skills adoption plan

## Purpose and boundary

This document proposes, but does not install or authorize, an acquisition layer for future IPTV domain-family micro-pilots. Tavily Agent Skills would acquire preserved evidence; Attribution-First V4 would remain the separate decision layer. A score or acquisition result cannot establish an official domain or owner.

## Proposed architecture

1. ChatGPT supports human review, scope selection and authorization decisions.
2. Codex prepares deterministic plans, allowlists, query hashes, checkpoints, evidence normalization and V4 evaluation.
3. PowerShell runs only explicitly approved local commands and keeps the operator-visible credit ledger.
4. Tavily Agent Skills perform only the authorized acquisition stage.
5. V4 deduplicates evidence, preserves independence groups and applies identity gates after acquisition.

The permitted-by-default planning set is `tavily-map`, `tavily-extract`, `tavily-search` and `tavily-best-practices`. `tavily-crawl` and `tavily-research` are blocked by default. No skill is installed by this milestone.

## Human authorization gates

- A named family, exact domain allowlist, output directory and credit cap require approval before acquisition.
- Map runs first. A human reviews its paths before Extract.
- Extract uses only approved URLs. Search is available only for gaps that remain after Map and Extract.
- Crawl requires a separate decision and is justified only for a compact first-party subtree that Map exposed but Extract could not cover.
- Research is excluded from the base budget and requires a separate future protocol.

## Credit ledger

The reported panel state is 548/4000 credits used. This is operational context, not permission. The proposed cap per family is 20 credits for Map, 30 for Extract and 30 for Search: 80 base, 120 absolute maximum. A possible Crawl allowance of 40 is outside the base and remains blocked. Research receives no base allocation.

Every call would record planned maximum, actual debit, cumulative family debit, monthly debit, remaining reserve, authorization reference and supporting output IDs. Work stops at the family cap, after two stages add no attributable evidence category, when a material reseller/template conflict dominates, or when the V4 identity gate is already satisfied.

## Deduplication and allowlists

Exact queries are normalized, hashed and compared with historical query ledgers before authorization. Repeated hashes are rejected. Map and Extract use exact registrable-domain and URL allowlists; redirects, subdomains and payment endpoints require explicit classification. Generic searches, reviews, directories and social networks are excluded unless they are the precise unresolved evidence gap.

## Raw evidence, checkpoints and traceability

Raw responses are append-only and content-hashed. Each request receives a checkpoint state and physical request counter. Normalized findings retain `source_run`, `source_artifact`, URL, content hash, provenance, independence group and non-empty `supporting_row_ids`. Interrupted runs resume only from durable states; completed requests and query hashes are never repeated.

Codex would integrate preserved outputs offline, classify brand, contact, legal-template, application, payment, infrastructure and identity signals separately, and then apply V4. Generic pronouns, copyright, structured data, analytics, checkout links and name similarity cannot become strong identity evidence by themselves.

## Risks and acceptance criteria

Principal risks are credit drift, repeated queries, broad crawling, cross-domain redirects, template text, reseller promotion, review dependence and accidental identity overclaim. Acceptance requires zero out-of-scope URLs, exact budget reconciliation, complete raw evidence, deterministic normalization, non-empty supporting IDs, immutable source hashes and V4 abstention whenever a gate fails.

## Proposed pilot

After explicit human selection, use the highest-ranked offline family in a separate micro-pilot. Run Map with depth 2 and limit 30; review paths; Extract up to six legal/contact/payment URLs with three chunks each; then authorize at most three domain-restricted Search queries only if named entity, controller, jurisdiction, merchant or publisher gaps remain. Crawl and Research stay blocked. The pilot is successful if it improves attributable identity coverage per credit while preserving V4 abstention and reproducibility.
