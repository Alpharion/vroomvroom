# Ryde Track: Team Brief

**Tencent Cloud AI CAN DO IT Hackathon Singapore 2026**
**Challenge:** Multi-Agent Autonomous Dispute Resolution System (Digital Native Track, Ryde)

> **Submission deadline: Fri 16 Oct 2026.** We aim to submit on **Thu 15 Oct** to leave a buffer.
> Check the WhatsApp group for the exact cut-off time and the track's detailed judging criteria.

---

## 1. What we're building

An AI system that resolves disputes between Ryde riders and drivers automatically. A dispute is filed, two AI "advocates" gather evidence and argue each side, and an AI "judge" issues a fair ruling with an explanation.

### Must-haves (judged primarily on these)

- [ ] **Rider Advocate Agent**: gathers rider-side evidence and argues the rider's case, citing policy
- [ ] **Driver Advocate Agent**: gathers driver-side evidence and argues the driver's case, citing policy
- [ ] **Judge Agent**: weighs both cases, applies policy, and issues a ruling (refund / compensation / no action) with a **confidence score** and a **plain-language explanation**
- [ ] Works end to end for **at least 2 dispute types**: we're doing **Route Deviation** and **No-Show Charge**
- [ ] **Inter-agent communication is visible** in the UI (judges must be able to see the agents build their cases)

### Evidence the agents use (from Ryde's sample dataset)

- GPS / telemetry: actual vs optimal route, unexpected stops, trip duration vs estimate
- Chat logs: agreements, disagreements, threats
- Payment / fare data: fare breakdown, surge, promo codes
- Behaviour history: past disputes, ratings, account age

### Stretch goals (bonus points, only after the MVP works)

In order of value per hour of work:

1. **Escalation protocol**: low confidence, or any safety-related case, goes to a human reviewer
2. **SLA & routing**: urgent or high-value disputes get prioritised
3. **Policy & Precedent agent**: a knowledge base of policies and past rulings (ADP)
4. **Learning feedback loop**: when a human overrides a ruling, it's saved as a precedent
5. Fraud / bad-faith detection agent
6. Image analysis for damage claims (probably skip)

---

## 2. How it works (architecture)

**Core principle:** code finds the facts, the LLMs argue about them. The agents never calculate distances, fares or refund amounts themselves. This keeps rulings consistent and auditable.

```
Dispute filed
     │
     ▼
Evidence tools (plain code)
  - route_deviation()   → actual vs optimal km/min, % extra, extra fare
  - no_show_check()     → driver distance from pickup, wait time, contact attempts
  - fare_validate()     → surge / promo / breakdown checks
  - history_lookup()    → dispute history, ratings, account age
  - safety_check()      → threat/harassment keywords, speeding (any safety hit → human review)
     │
     ├──────────────┬──────────────┐
     ▼              ▼              │
Rider Advocate   Driver Advocate   │   (run in parallel, same tools,
     │              │              │    same output format)
     └──────┬───────┘              │
            ▼                      │
         Judge  ◄──────────────────┘  (also sees raw evidence)
            │
            ├── confidence high, not safety → ruling issued to both parties
            └── confidence low OR safety    → human review queue
```

### Key design rules

- **Mock policy document with numbered clauses** (e.g. `R-3.2: deviation >20% without rider request → refund the difference`). Agents must cite clause IDs.
- **Refund amounts come from a policy formula in code**, not from the Judge.
- **Every agent output follows a strict schema** (Pydantic), so the Judge can only return a valid ruling.
- **Both advocates are treated identically**: same tools, same output format, same length cap. This prevents the Judge favouring whoever writes more.
- **Judge runs at the lowest temperature** for consistency. ADP's minimum is **0.1**, not 0; the consistency test checks whether that's enough. If not, call the Judge through the direct DeepSeek API at `temperature: 0`.
- **Safety incidents are never auto-resolved.** Always escalate, and say so in the pitch.

---

## 3. Tech stack

| Layer | Choice | Notes |
|---|---|---|
| Backend | Python + FastAPI | |
| Orchestration | **LangGraph** (decided 8 Oct) | Graph = evidence → advocates in parallel → judge → escalation branch. Built-in streaming for the UI. |
| Output schemas | Pydantic | |
| LLM | **DeepSeek-V3.2** via **Tencent Cloud ADP** (decided 10 Oct) | One Standard-mode ADP app shared by all three agents. Prompts live in our code and are sent per call (`SystemRole`); the app's prompt is left empty. AppKey read from `ADP_APP_KEY` in `.env`. |
| Knowledge base | ADP knowledge base | Policy + precedents |
| Frontend | **Streamlit** (Alpha's build, 10 Oct) | Waiting on Marcus to confirm |
| Dev tool | **CodeBuddy** (mandatory) | |
| Deploy | CodeBuddy → CloudBase / EdgeOne / Lighthouse | Live link earns bonus points |
| Visuals | Miora | Cover image, any UI mockups |

**Check current docs** for whichever framework we use. Library APIs change fast; don't trust old tutorials.

---

## 4. Our resources

| Resource | What we get | Use it for |
|---|---|---|
| CodeBuddy / WorkBuddy | **1,000 credits per person** (each person's own account) | Writing code (CodeBuddy); docs, policy, test cases, pitch (WorkBuddy) |
| Miora | **1,000 credits per person** | Cover image, visuals |
| Tencent Cloud ADP | **10,000 credits/month + 1 GB knowledge base per account**, valid 8 Oct – 8 Nov 2026 (see **Billing** in the ADP console) | Running our agents. A short call costs ~1 credit, so a full dispute (3 calls) is roughly 8–12 credits: one account covers ~800+ runs. |
| Ryde sample dataset | Provided by organisers. **DISP-002 (no-show) received**; check for more cases | Evidence for test cases and the input schema |

**Important:** CodeBuddy credits power the coding assistant, *not* our app's agents. Agent LLM calls use ADP's free tokens.

### ADP setup (decided 10 Oct)

- **Everything runs on Marcus's ADP account** (testing, metrics, consistency/fairness runs, live demo), since the knowledge base lives there. Results stay comparable.
- Damien's backend now uses Marcus's AppKey (smoke test passed 10 Oct). Damien's `vroomvroom-dev` app is a spare; switching is a one-line `.env` change.
- ADP's API returns only `TotalTokens` (input/output come back as 0) and seems to exclude ADP's own overhead. Use the **Billing** page to track credits.
- **App settings (must match on every app we use):** Standard mode · Thinking + Generative model **DeepSeek-V3.2** · Temperature **0.1** (lowest allowed; set in the model dropdown) · Deep Thinking **disabled** · Prompt **empty**.
- Each call runs two model calls (a planning "thought model" + generation) and adds ~1,650 tokens of ADP overhead.
- AppKeys are shared by DM only, never in the group chat or the repo.

### Saving tokens

- Credits are not a constraint (see above), but still use **saved/mocked LLM responses** during UI work so reloads are fast
- Keep advocate briefs short
- Only run the 5x consistency test occasionally, not after every change
- Fallback if ADP quota runs out: a direct DeepSeek API key (cheap, but out of pocket)

---

## 5. ⚠️ Proof of tool usage (MANDATORY)

**Without proof, the project is not scored at all.**

- Everyone: **screenshot your CodeBuddy / WorkBuddy chats as you go.** We need **at least 3**, but more is better.
- Spread coding sessions across everyone's accounts (more credits, more screenshots).
- Save a few ADP console screenshots and API call results too.
- **Save some CodeBuddy credits for deployment on Tue 13.** Deploying through CodeBuddy is strong, visible proof.
- Dump all screenshots into the shared folder: `TODO: link`

---

## 6. Roles

| | Damien | Alpha | Marcus |
|---|---|---|---|
| **Role** | Backend & Agents | Frontend & Deployment | Product, Data & Pitch |
| **Owns** | Evidence tools, agent prompts, orchestration, escalation logic | UI, live agent log, ruling cards, deployment, demo video | Mock policy, test cases, ADP setup, knowledge base, all written deliverables |

**Everyone:** use CodeBuddy / WorkBuddy for your own work and screenshot your chats into the shared folder.

### Damien: Backend & Agents
- Repo scaffold in CodeBuddy (Python + FastAPI)
- Evidence tools: `route_deviation()`, `no_show_check()`, `fare_validate()`, `history_lookup()`, with tests
- Refund formulas in code, based on Marcus's policy doc
- Rider Advocate, Driver Advocate and Judge prompts + Pydantic schemas
- Orchestration (LangGraph): advocates in parallel → judge → escalation branch
- Escalation protocol + SLA routing logic
- An API endpoint that streams agent messages for Alpha's UI

### Alpha: Frontend & Deployment
- UI: dispute filing form, live "courtroom" agent log, ruling cards for rider and driver, human review queue
- Build against **mock data first** (using the agreed schemas) so you're not blocked on Damien
- GPS replay map (planned vs actual route) if time allows
- Deploy the app for the live link (CodeBuddy → CloudBase / EdgeOne / Lighthouse)
- Record and edit the demo video (Marcus writes the script)

### Marcus: Product, Data & Pitch
- Get the Ryde sample dataset from the WhatsApp group; clean it into the format Damien needs
- Write the **mock policy doc** with numbered clauses (Route Deviation + No-Show)
- Write 8–10 test cases, including edge cases and a safety case that must escalate
- Set up ADP accounts, check free quota, create the ADP apps and policy/precedent knowledge base, share AppKeys **privately** with Damien
- Run the consistency test and fairness checks (swap advocate order / histories), record results
- Project title, blurb, description with business metrics, architecture diagram, Miora cover image, demo script
- Collect everyone's screenshots; own the final submission

---

## 7. Timeline

Each day lists what each person does, what they hand to someone else, and a **"done when"** check. If a "done when" isn't met, flag it in the group chat that evening so we can re-plan instead of falling behind silently.

**Daily routine:** 10-minute check-in each evening (what's done, what's blocked, tomorrow's plan). Screenshot CodeBuddy / WorkBuddy sessions into the shared folder as you go.

---

### Thu 8 Oct: Setup + agree the schemas

**Everyone (first thing, 30–60 min call)**
- [ ] Confirm roles and decide: Streamlit or React? (Orchestration: LangGraph ✅)
- [ ] Agree the 4 JSON schemas: dispute input, evidence output, advocate brief, ruling. **Base the dispute input on the DISP-002 sample dataset structure.**
- [ ] Write them into `schemas.md` in the repo
- [ ] Create the GitHub repo, shared screenshot folder, and a shared `.env` handling plan (never commit keys)

**Damien**
- [x] Scaffold the repo in CodeBuddy: FastAPI app, folders for `tools/`, `agents/`, `schemas/`, `tests/`, `data/`
- [x] Turn `schemas.md` into Pydantic models
- [x] Load DISP-002 from `data/` and print it from a test script

**Alpha**
- [ ] Scaffold the frontend in CodeBuddy
- [ ] Create a `mock_ruling.json` and `mock_agent_log.json` in the agreed schema shape for UI work
- [ ] Rough page layout: form → courtroom log → ruling cards

**Marcus**
- [ ] Check the WhatsApp group for other sample cases (DISP-001 etc.), especially a **route deviation** case
- [ ] Sign up for ADP; record the free token quota and expiry
- [ ] Start the policy doc: no-show clauses first, **using DISP-002's numbers** (5 min free wait, $5 fee, 8 min threshold)
- [ ] Ask the WhatsApp group whether other AI coding tools are allowed alongside CodeBuddy

**Done when:** schemas agreed and in the repo; repo runs; Alpha has a blank UI; Marcus has the ADP account and a draft no-show policy.

---

### Fri 9 Oct: Evidence tools + policy

**Damien**
- [x] `no_show_check()`: driver distance from pickup, arrival vs scheduled time, total wait, contact attempts, rider replies
- [x] `history_lookup()`: ratings, dispute history, fraud flags, account age summary
- [x] Tests against DISP-002 (e.g. wait = 8 min, contact attempts = 5, rider replies = 0)
- [x] Start `route_deviation()` once Marcus has route data

**Alpha**
- [x] Dispute filing form (trip ID, dispute type, description)
- [x] Ruling cards for rider and driver, showing verdict, amount, confidence, clauses cited, plain explanation
- [x] Evidence card component (displays evidence tool output)

**Marcus**
- [x] Finish the policy doc: route deviation, no-show, and safety (S-1.1: never auto-resolve) clauses, all numbered
- [x] Send the thresholds and refund formulas to Damien
- [ ] If no route deviation case is provided: write one in DISP-002's exact format (WorkBuddy can help)
- [ ] Start writing test cases: aim for 8–10 (see list below)

**Done when:** `no_show_check()` passes its tests on DISP-002; policy doc v1 shared; UI shows mock ruling + evidence cards.

---

### Sat 10 Oct: Agents end to end

**Damien**
- [x] `route_deviation()` + tests on the route deviation case (on `feature/route-deviation`; TC-07 data issues flagged to Marcus)
- [x] ADP dev app set up and tested (`vroomvroom-dev`)
- [x] `compute_no_show_outcome()` (refund/fee formula for no-show, per handoff)
- [x] LLM client for ADP (`backend/agents/llm.py`: reads `ADP_APP_KEY` from `.env`, caches responses, `USE_MOCK_LLM=true` replays the cache)
- [x] Stub `POST /api/disputes/resolve` for Alpha: real evidence tools + outcome formulas, mocked advocate/Judge messages (see API contract below)
- [x] Rider Advocate, Driver Advocate, Judge prompts (same structure for both advocates, length cap, must cite clause IDs and evidence) in `backend/agents/`. The Judge decides only route-deviation findings (`rider_requested_detour`, `traffic_justified`); outcome and amount come from code
- [x] Wire the flow: evidence tools → both advocates in parallel → Judge (plain `asyncio` in `agents/pipeline.py`; LangGraph moved to Sun)
- [x] Refund amount computed in code from the policy formula, not by the Judge (`compute_no_show_outcome()`, `compute_route_deviation_outcome()`)
- [x] Run DISP-002 end to end in a script. **Expected: charge UPHELD.** Never feed the dataset's "expected ruling" or evidence summary to the agents. ✅ `python3 scripts/run_case.py DISP-002` → charge_upheld, $5.00, confidence 0.95. Agents only see whitelisted case fields, never `test_case_description`.
- [x] RD-2.7 applied: route deviation needs ≥ 2 `in_trip` GPS points; TC-11 escalates

**Alpha**
- [x] Courtroom panel: messages appear one by one, labelled Rider Advocate / Driver Advocate / Judge
- [x] Simulate streaming from `mock_agent_log.json` with delays

**Marcus**
- [x] Create **one** ADP app with the settings in Section 4 (ADP setup); DM the AppKey to Damien
- [x] Finish the test cases (TC-07 GPS fixed, TC-11 added, RD-2.7 added, 10 Oct)
- [ ] Start the project description: overview + pain points sections

**Done when:** DISP-002 produces a correct ruling from a script; the courtroom panel animates mock messages.

---

### Sun 11 Oct: Integration day ⚠️

**Damien**
- [x] Wire the agents into LangGraph (`agents/graph.py`): evidence → advocates in parallel → Judge → human review or issued ruling. `run_case.py` uses the same graph
- [x] Replace the stub in `POST /api/disputes/resolve` with the real agent flow (same stream format). Stub kept behind `USE_STUB_AGENTS=true` for UI work without credits / demo fallback
- [x] Trim policy text sent to agents (~36% smaller; Python, Source, Classification, Discrepancy blocks and test-case references removed)
- [x] Judge option to see the driver's brief first (`--driver-first` in `run_case.py`, `"driver_first": true` in the API), for the advocate-order fairness test
- [x] Tighten advocate prompt: quote fact values exactly; dispute description is the filer's claim, not evidence
- [x] `safety_check()` (S-1.1): any hit escalates to human review (`S-1.1, S-1.2`, $0). TC-08 now escalates (verified live). Keywords match at word start: the handoff's substring match flagged 12 of 13 cases ("hit" in "White Toyota")
- [x] `fare_validate()`: fare type, charged amount (fare or cancellation fee), per-km rate, surge, breakdown check. Evidence only
- [ ] Pair with Alpha to connect frontend and backend

**Alpha**
- [x] Swap mock data for the real API (live hearing streams `/api/disputes/resolve`; demo mode still replays mocks)
- [x] Handle loading and error states (LLM slow, API fails): error banner instead of falling back to mocks

**Marcus**
- [x] ~~Remove test-case references from the policy doc~~ No longer needed: the backend strips them before the agents see the policy
- [ ] Run every test case through the integrated system: `python3 scripts/run_case.py TC-05` from `backend/` (add `--driver-first` for the order-swap fairness test). Run live (`USE_MOCK_LLM=false`); prompts changed on 11 Oct, so old cached runs no longer replay
- [ ] Log each result: expected vs actual ruling, time taken, any bugs → shared bug list for Damien & Alpha
  - 12 Oct: `docs/integration-test-results.md` added, but it covers the **unit tests only** (LLM replaced with canned replies). Its confidence values are copied from `expected_results.json`, not measured. Live runs still needed

**API contract (agreed with Alpha 10 Oct)**
- `POST /api/disputes/resolve` with `{"dispute_ticket": {"dispute_id": "..."}}`. The backend loads the full case from `data/` by `dispute_id` (e.g. `DISP-001`, `DISP-002-T5`) or test-case prefix (`TC-05`). Unknown ID → 404; bad body → 422.
- Response: NDJSON (`application/x-ndjson`), one JSON object per line:
  - `AgentLogMessage` lines (`type`: `evidence` / `argument` / `rebuttal` / `ruling`)
  - `{"type": "evidence_data", "data": EvidenceOutput}`, one per tool
  - `{"type": "brief_data", "data": AdvocateBrief}`, one per advocate
  - `{"type": "ruling_data", "data": Ruling}`, last
  - `{"type": "error", "content": "..."}` if something fails after streaming starts, then the stream ends
- `history_lookup` facts keep their nested `facts.rider` / `facts.driver` shape.
- **Real flow (11 Oct):** evidence lines arrive at once (`history_lookup`, `safety_check`, then `no_show_check` or `route_deviation`); then ~15–30 s of silence while the advocates run; each advocate's position + arguments (`type: argument`) and its `brief_data` arrive together as it finishes; then the Judge's `ruling` line and `ruling_data`; escalated cases end with a `system` line "Routed to the human review queue."
- Optional request field `"driver_first": true` makes the Judge read the driver's brief first (fairness test). The UI doesn't need it.
- `USE_STUB_AGENTS=true` on the backend replays mocked agent messages instead of calling ADP.

**Done when:** a dispute can be filed in the UI and a real ruling appears, with the agent conversation visible live. **This is the most important milestone. If it slips, cut stretch goals, not this.**

---

### Mon 12 Oct: Stretch goals + fixes

**Damien**
- [x] Escalation: confidence below 0.70 or any safety hit → `escalate` and the graph's `human_review` branch (done 11 Oct)
- [x] Human review queue backend (`backend/app/review_queue.py`), built to Alpha's contract in `frontend/review_queue.py`: `GET /api/review-queue`, `POST /api/review-queue/{id}/decision`, plus `POST /api/review-queue/{id}/appeal`. Escalated rulings join automatically; saved to `backend/.review_queue.json`
- [x] SLA routing: safety incidents and disputes with a charged fare ≥ S$30 are `high` (4 h SLA), others `normal` (24 h, vs Ryde's 24–72 h). Items carry `priority_reason`, `sla_hours`, `due_at`. Constants in `policy_constants.py` (PROPOSED)
- [x] Fix bugs from Marcus's list: UTF-8 on every file read/write (Windows), `tests/conftest.py` so pytest runs from any folder and ignores `.env` mode flags

**Alpha**
- [x] Human review queue page: list of escalated cases, approve / override buttons (switches to the backend queue when `GET /api/review-queue` responds; appeals should call the new `/appeal` endpoint)
- [x] GPS map (planned vs actual route, driver position at pickup) if time allows

**Marcus**
- [ ] Precedent KB in ADP: upload policy doc + 15–20 mock past rulings (if Damien has time to connect it)
- [ ] Architecture diagram (draft)
- [ ] Re-run test cases after fixes

**Done when:** a safety case is escalated, not auto-resolved; the review queue shows it.

---

### Tue 13 Oct: Deploy + test

**Damien**
- [ ] Fix remaining bugs; freeze features by evening
  - [x] First live route-deviation runs found two bugs that failed whole disputes (advocate cited a raw app event; position over 200 chars twice). Fixed: case-data citations allowed, bad citations dropped and over-long text trimmed after the retry. Live: TC-05 → refund $1.07 (28 s), TC-06 → no_action RD-2.3 (27 s)
- [x] Make sure keys are environment variables, not in code: audited tracked files and full git history, no keys anywhere; `.env` never committed
- [x] Deploy readiness: `Dockerfile.backend`, `Dockerfile.frontend` (build from repo root), `.dockerignore`, README "Deploy" section. Frontend reads `BACKEND_URL` / `DEMO_MODE` env vars; stream sends no-buffering headers. Backend checked in an image-like layout without `.env`; images not yet built (Docker not running locally)

**Alpha**
- [ ] **Deploy via CodeBuddy** (CloudBase Run or Lighthouse; EdgeOne Pages can't run the Python servers). Screenshot the deploy process for proof. See README "Deploy": backend needs `ADP_APP_KEY`, `USE_MOCK_LLM=false`, no `USE_STUB_AGENTS`; frontend needs `BACKEND_URL`, `DEMO_MODE=false`; request timeout ≥ 120 s
- [ ] Test the live link on a phone and a different laptop

**Marcus**
- [ ] Consistency test: same case 5 times → same ruling? Record the result. Run live each time (`USE_MOCK_LLM=false`); cached replays would trivially match
- [ ] Fairness tests: swap advocate order; swap rider/driver histories. Record results.
- [ ] Calculate business metrics: average resolution time, consistency %, % auto-resolved vs escalated

**Done when:** live link works for someone outside the team; metrics recorded.

---

### Wed 14 Oct: Content day

**Damien**
- [ ] README: what it is, how to run it, architecture summary
- [ ] Clean up repo, make sure it's complete for submission
- [ ] Help Alpha with the demo recording

**Alpha**
- [ ] Record the demo video (5–8 min) from Marcus's script
- [ ] Polish UI details judges will see

**Marcus**
- [ ] Demo script by midday: problem → live dispute → agents arguing → ruling → escalation case → metrics → how we used CodeBuddy
- [ ] Finish the project description (all 4 required sections)
- [ ] Final architecture diagram
- [ ] Cover image in Miora (16:9, 380×216)
- [ ] Title + blurb (**under 10 words**)

**Evening:** group run-through of the demo before the final recording.

**Done when:** video recorded; all written content drafted.

---

### Thu 15 Oct: Submit

**Everyone (morning)**
- [ ] Review the description, video and repo together
- [ ] Final fixes only, no new features

**Marcus (afternoon)**
- [ ] Go through the submission checklist (Section 8) line by line
- [ ] **Submit**
- [ ] Screenshot the submission confirmation

**Fri 16 Oct:** buffer only. Don't plan to use it.

---

### Test cases to write (Marcus)

| # | Type | Scenario | Expected |
|---|---|---|---|
| 1 | No-show | DISP-002 (provided) | Charge upheld |
| 2 | No-show | Driver waited only 3 min before cancelling | Charge reversed |
| 3 | No-show | Driver GPS 400 m from pickup | Charge reversed |
| 4 | No-show | Driver didn't attempt any contact | Charge reversed |
| 5 | Route | Route 40% longer, no rider request | Refund difference |
| 6 | Route | Route longer, but rider asked for a detour in chat | No refund |
| 7 | Route | Route 10% longer (under threshold) | No refund |
| 8 | Safety | Rider reports driver threatened them | Escalate to human |
| 9 | Edge | Evidence conflicts or is missing (e.g. GPS gap) | Low confidence → escalate |
| 10 | Fairness | Case 1 with rider/driver histories swapped | Same outcome on the facts |
| 11 | Route (edge) | Route deviation with incomplete GPS (only 1 in-trip point) | Low confidence → escalate (RD-2.7) |

---

## 8. Submission checklist

**Required**
- [ ] Project title
- [ ] Short blurb, **under 10 words** (hard limit)
- [ ] Project description covering:
  - [ ] Overview: target scenarios, users, value proposition
  - [ ] Real-world insights: pain points, target audience, problems solved
  - [ ] Solution design: business + technical architecture, how prompts drive the AI
  - [ ] Business value with metrics (see below)
- [ ] At least 3 CodeBuddy / WorkBuddy screenshots or a screen recording
- [ ] 16:9 cover image (recommended 380×216px)

**Required by the Ryde challenge**
- [ ] Working prototype handling at least 2 dispute types
- [ ] Architecture diagram (multi-agent system + key components)
- [ ] Demo walkthrough of a dispute processed and resolved autonomously
- [ ] Complete source code in a GitHub repo

**Optional but worth doing**
- [ ] 5–8 min demo video (overview, core agent features, reflection on build approach + CodeBuddy/WorkBuddy tips)
- [ ] Live project link (**bonus points**)

**Submission link:** https://tinyurl.com/TCHackathonSGProjectSubmission

### Business value metrics to show

- Resolution time: Ryde's current 24–72 hours → our time per dispute
- Ruling consistency: same case run multiple times → same result
- % of disputes auto-resolved vs escalated to humans

---

## 9. How we're judged

10 dimensions, 10 points each:

Impact & Relevance · Human-Centred Design · AI Interaction · Technical Execution · Feasibility · Demo & Storytelling · Innovation & Creativity · UX & Accessibility · Responsible AI & Ethics · Overall Impression

Top 2 teams per track go to **Demo Day (3 Nov, TBC)**. Finalists announced **23 Oct**.

---

## 10. Ideas to stand out

Most teams will build the same three-agent pipeline. Where we can differentiate:

- **Two explanations per ruling**, one written for the rider and one for the driver, aimed at keeping both on the platform (churn is one of Ryde's stated problems). Maybe an appeal button.
- **Prove fairness:** swap advocate order, or swap rider/driver histories, and show the ruling doesn't change unfairly.
- **Courtroom-style UI:** GPS replay map (planned vs actual route), evidence cards, visible "objections" between advocates.
- **Thoughtful policy design:** grace periods, thresholds, how dispute history is weighed.
- **Pitch story:** open with a frustrated rider *and* a driver who's also been wronged, then show both getting a fair answer in under a minute.

**Don't** get creative with the core spec (the three agents, two dispute types, visible communication). That's what we're primarily judged on.

---

## 11. Open decisions

- [ ] Frontend: Streamlit or React? (Alpha has built it in **Streamlit**; waiting on Marcus to confirm)
- [x] Orchestration: **LangGraph**
- [x] LLM: one ADP app (DeepSeek-V3.2, temp 0.1) on Marcus's account for everything
- [x] Assign real names to Person A, B and C → Damien, Alpha, Marcus
- [ ] Ask in the WhatsApp group: are other AI coding tools allowed alongside CodeBuddy?
- [ ] Project name + blurb

## Useful links

- Contest page: https://tch.tencentcloud.com/contest/44
- Submission: https://tinyurl.com/TCHackathonSGProjectSubmission
- Tencent Cloud ADP: https://adp.tencentcloud.com
- ADP Chat API endpoint: `https://wss.lke.tencentcloud.com/adp/v2/chat`
- Hackathon handbook: in the WhatsApp group / email
