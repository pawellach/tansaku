# Tansaku roadmap

Tansaku's north star is a human-controlled delivery loop: an agent discovers the right project knowledge, prepares and implements a change, proves it with tests, and gives the requester a clear UAT handoff. Human approval remains the control point for ownership, business intent, and release.

## Current product direction

The current flow is:

```text
Jira intake → knowledge discovery → AI analysis → Jira comment
           → Waiting → human assignment decision → implementation handoff
```

The next step is to make the handoff genuinely executable and evidence-based.

## Track 0 — make the assignment differentiator real

### P0: complete the assignment transaction

- Resolve the selected team member to a Jira `accountId`.
- Assign the issue through Jira REST API.
- Transition the issue to `In Progress` only after assignment succeeds.
- Send a confirmation containing the Jira URL, assignee, transition, and timestamp.
- Keep `Skip` and timeout paths side-effect free.

### P0: make decisions safe under concurrency

- Correlate callbacks with both ticket key and notification message ID.
- Ignore callbacks for tickets that are already assigned or closed.
- Prevent two Tansaku workers from processing the same ticket simultaneously.
- Record the decision and resulting Jira mutation in an audit log.

## Track 1 — three knowledge surfaces

The source article [`2026-10-27-dwie-warstwy-wiedzy-dla-agentow-ai.md`](C:/Projekty/subtrack-export/export/2026-10-27-dwie-warstwy-wiedzy-dla-agentow-ai.md) becomes the design input for a three-surface knowledge architecture. These are different representations of the same controlled knowledge, not three competing sources of truth.

### 1. Agent documentation

Purpose: fast, navigable context for implementation agents.

Recommended contents:

- one short entry point and domain indexes;
- technical constraints, invariants, dependencies, and test commands;
- business-rule IDs linked to components and tests;
- source, status, owner, scope, and last-verified metadata;
- explicit distinction between fact, decision, hypothesis, and open question;
- links to primary sources instead of copied manuals.

This surface should live close to the code and be optimized for discovery and safe execution. It should not become a second copy of every human document.

### 2. OKF documentation for people

Purpose: readable, versioned knowledge that humans can review and approve.

Use OKF-style Markdown/YAML metadata for business rules, processes, concepts, requirements, architecture decisions, and runbooks. Keep the prose understandable without an agent, while retaining stable IDs and links to implementation evidence.

Minimum metadata contract:

```yaml
id: <stable-knowledge-id>
type: business-rule | process | architecture-decision | runbook
status: proposed | approved | deprecated
owner: <team-or-role>
source: <ticket-url-or-primary-source>
last_verified: <yyyy-mm-dd>
related_components: []
related_tests: []
```

### 3. Confluence publication

Purpose: discoverable operational and business documentation for the wider organisation.

Confluence should receive approved, human-facing material — not every intermediate agent note. Each published page should link back to its repository source or stable ID, show status and last verification, and identify the owner. Publication should be explicit and reviewable rather than an automatic blind mirror.

### Knowledge lifecycle

```text
Intake → discover → classify → verify sources → implement
      → run tests → assess knowledge impact → update agent/OKF views
      → review → publish approved material to Confluence
```

Initial implementation should prefer Markdown, indexes, stable IDs, link validation, and deterministic checks. A vector database or knowledge graph should be considered only after real-task measurements show that structured navigation and search are insufficient.

## Track 2 — selectable specialist delivery agents

Beyond developer assignment, the operator should be able to select a dedicated specialist agent for the task, for example:

- Salesforce Admin / configuration agent;
- backend or integration agent;
- frontend agent;
- data migration agent;
- QA/UAT agent;
- documentation and knowledge-maintenance agent.

### Target workflow

1. Tansaku analyses the ticket and proposes the most suitable specialist.
2. A human selects or confirms the agent in Telegram/Slack.
3. The specialist reads the relevant agent documentation and OKF knowledge.
4. The specialist creates a bounded implementation plan.
5. The specialist changes code/configuration in an isolated workspace or branch.
6. Automated tests, linting, and relevant validation checks run.
7. The agent reports changed files, test commands, results, risks, and unresolved questions.
8. Tansaku posts a requester-facing comment with concrete UAT steps, expected results, test data, and evidence links.
9. A human approves UAT and decides whether to merge, deploy, or request changes.

The specialist agent must not silently deploy to production or invent business acceptance criteria. Missing business decisions remain explicit questions for the requester.

### UAT comment contract

Every implementation handoff should include:

- what changed in user language;
- preconditions and test data;
- numbered UAT steps;
- expected result per step;
- test evidence and automated-test status;
- known limitations and rollback/cleanup notes;
- a clear request for confirmation or defect feedback.

## Track 3 — Docker and self-hosted operations

### Delivered

- Dockerfile and Docker Compose one-shot runner;
- separate `setup` Compose profile;
- `.env.example` and read-only configuration mounts;
- synthetic Telegram assignment showcase in the README.

### Next steps

- Add a scheduled worker mode or documented host-cron pattern.
- Add container health checks and structured log output.
- Add a non-root runtime user.
- Add image build and smoke-test workflow in GitHub Actions.
- Document Docker Desktop, VPS, and CI deployment paths.
- Add optional persistent state for locks, callback cursors, and audit events.

## Measures of progress

Track these on representative tickets rather than measuring document or agent count:

- time from Jira creation to actionable analysis;
- time from analysis to human assignment;
- assignment correction rate;
- percentage of tickets with successful automated tests;
- percentage of handoffs with usable UAT instructions;
- number of regressions caused by missed knowledge;
- knowledge discovery time and context size;
- percentage of published documentation with owner, source, and verification date.

## Suggested delivery order

1. Complete Jira assignment and callback correlation.
2. Add specialist selection with one concrete agent type.
3. Produce automated test results and UAT comments.
4. Introduce the agent-documentation index and stable knowledge IDs.
5. Add OKF review workflow and controlled Confluence publication.
6. Harden Docker operation and add CI smoke tests.
7. Measure the workflow on a small production pilot before adding semantic search or more agent types.

## Next sprint — 9–13 November 2026

This is a dry-run and code-quality sprint. Do not connect to or mutate a live Jira or Telegram environment.

### Monday — reproducible local verification

- Install project dependencies in a clean virtual environment.
- Run the complete unit test suite without live credentials.
- Validate PowerShell Docker helper syntax and Compose configuration.
- Document the exact dry-run command and expected output.

### Tuesday — specialist-agent contract

- Define the first specialist profile, starting with a generic developer agent.
- Specify inputs, allowed tools, workspace/branch boundary, test command, and output schema.
- Add explicit stop conditions for missing business decisions and unsafe deployment requests.

### Wednesday — UAT handoff vertical slice

- Convert test results into a requester-facing UAT comment.
- Require numbered steps, expected results, test data, evidence, limitations, and PASS/FAIL response format.
- Add a mocked test covering analysis → implementation summary → UAT comment.

### Thursday — knowledge architecture seed

- Add a minimal agent-knowledge index and one OKF-style example document.
- Link one business rule to one implementation component and one test.
- Define repository-to-Confluence publication metadata without implementing blind mirroring.

### Friday — portfolio and release hygiene

- Review README, GitHub Pages showcase, roadmap, Docker quickstart, and screenshots together.
- Add CI checks for Python compilation, unit tests, SVG/XML validity, and PowerShell parse validation.
- Record remaining gaps and decide whether the next sprint should focus on specialist execution or Confluence publication.

### Sprint acceptance criteria

- A clean checkout can reach a deterministic dry-run without live credentials.
- The specialist-agent contract is documented and testable.
- A mock implementation produces a complete UAT handoff.
- At least one knowledge relation is represented end-to-end.
- CI catches broken code, broken assets, or invalid operational instructions.
