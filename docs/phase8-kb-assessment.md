# Phase 8 — ADP Knowledge Base Assessment

**Date:** 2026-10-13
**Branch:** `feature/organiser-integration`
**Commit:** `f5be9cb`

## Finding: The App Does NOT Use ADP Knowledge-Base Retrieval

The running application **sends local policy clauses inline in the LLM prompt**. It does not retrieve from an ADP knowledge base.

### How Policy Clauses Currently Reach the Agents

1. `agents/context.py:load_policy_clauses()` parses `docs/ryde_dispute_policy.md` locally at startup into a `{clause_id: section_text}` dict.
2. `agents/context.py:relevant_clauses(dispute_type)` filters to the relevant clauses (NS-* or RD-* plus E-* and S-*).
3. The clause dict is passed through the LangGraph state to the advocate and judge agents.
4. Each agent's `_build_user_message()` includes the clauses as a `"relevant_clauses"` JSON field in the user message sent to ADP.
5. The ADP call in `agents/llm.py:_call_adp()` sends `{SystemRole, Contents: [{Type: "text", Text: user_message}]}` — a plain chat completion. No knowledge-base retrieval, no RAG, no document upload.

### Clause Citation Validation

The Judge and advocate agents validate cited clause IDs **locally** against the `clauses` dict passed to them. If an agent cites a clause ID not in the dict, the system retries with an error message, then drops the invalid citation. This ensures clause citations are always correct regardless of LLM hallucination.

### Why This Is Sufficient for the Hackathon MVP

- The policy document is small (~30 clauses, ~3,000 words) — fits easily in the context window.
- Local parsing enables deterministic clause ID validation, preventing hallucinated citations.
- The formula outcomes are computed in Python, not by the LLM — the LLM only provides findings (booleans), confidence, and explanations.
- Adding ADP KB retrieval would add latency and an external dependency without improving accuracy for this policy size.

## Stretch Goal: ADP Knowledge-Base Upload

If time permits after MVP stability is confirmed, the following steps would integrate the ADP knowledge base:

### 1. Prepare Clean Policy File

The existing `docs/ryde_dispute_policy.md` is already structured with numbered clause IDs (`### NS-1.1 — Title`) and is suitable for KB ingestion. However, it contains internal notes (`Classification`, `Source`, `Python computation`) that should be stripped for the KB version — agents only need the Rule, Evidence required, and Expected outcome.

A clean KB-ready file would contain only:
- Clause ID and title
- Rule text
- Evidence required
- Expected outcome

### 2. Upload Through ADP Workflow

This requires:
- Access to the ADP console (web UI or API)
- Creating a knowledge base instance
- Uploading the clean policy file
- Configuring the ADP app to use the knowledge base for retrieval

**Note:** This step requires console access and cannot be automated from the codebase alone. It would need to be done by Marcus or Damien through the Tencent Cloud ADP dashboard.

### 3. Modify LLM Client for KB-Enabled Calls

The current `_call_adp()` sends a plain chat completion. To use KB retrieval, the ADP app must be configured with the knowledge base attached, and the `AppKey` used must correspond to a KB-enabled app. The code itself may not need changes if the KB is attached at the ADP app level — the retrieval would happen server-side before the LLM generates its response.

### 4. Test Citations

After KB upload, run representative questions and verify:
- Agents cite correct clause IDs from the KB
- Citations match the locally validated set
- No hallucinated clause IDs
- Explanations reference accurate policy text

### 5. Limitations

- If both the local `relevant_clauses` dict and the KB are active, there's a risk of conflicting policy versions. The brief says: "keep conflicting policy versions out of the same active retrieval scope unless clearly version-filtered."
- The current HACKATHON_2026 policy and the organiser v2.1 policy have different thresholds (e.g., 8-min vs 5-min no-show). Only one should be in the active KB scope.
- KB retrieval adds latency (~1-2s per call) on top of the current ~7s per LLM call.

## Recommendation

**Mark ADP knowledge-base integration as a stretch goal.** The current inline-clause architecture is stable, accurate (11/11 live tests passed), and fast (mean 21.6s per case). KB integration risks MVP stability for minimal accuracy gain given the small policy size.

If pursued, it should be done after the hackathon submission deadline or as a demo-only feature with screenshots of the ADP console configuration.
