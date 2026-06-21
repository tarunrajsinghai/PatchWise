# PatchWise
Evidence-Based CVE Upgrade Advisor for Scala and Angular
<img width="1280" height="720" alt="patchwise_github_banner_1280" src="https://github.com/user-attachments/assets/3a5c118a-8a57-4cb4-9bbc-fdc1f995b03d" />


A deterministic, evidence-first pipeline where SBOM, Trivy, constraints, resolvers, build/test output, and human approval provide the facts. Internal LLM writes only controlled explanations.

Design principle
Deterministic tools decide facts. AI explains verified evidence only.

Contents
Section	Purpose
1. Pipeline overview	End-to-end jobs and artifacts
2. Job 1 — Generate combined SBOM	Resolved dependency inventory
3. Job 2 — Trivy scan + triage	Vulnerabilities, fixed versions, suppression ledger
4. Job 3 — Feasibility engine	Constraints, upgrade groups, strict resolution, build/test
5. Job 4 — Evidence enrichment	Changelog/release-note signals with provenance
6. Job 5 — AI report generation	Internal LLM with schema and rule guardrails
7. Job 6 — Human approval gate	Approve/reject/manual strategy
8. Job 7 — Optional upgrade PR creation	Apply approved patches and open PR
9. Artifact summary	Inputs/outputs by job

Changes in this revision (v2)
•	Suppression ledger added: Job 2 applies .trivyignore / .trivyignore.yaml so accepted findings do not re-enter feasibility on every run.
•	Constraints enforced in feasibility: pins, allowed ranges, upgrade-together groups, and required tests feed Job 3, not only Job 4.
•	Upgrade-together groups: grouped packages such as Jackson modules are tested as a single candidate set.
•	Strict resolution: Job 3 fails loudly on dependency conflicts and verifies that the candidate version actually resolved and was not silently evicted.
•	Supporting fixes: explicit SBOM merge commands, conservative classification ladder, risk-signal provenance, and mandatory patch output for feasible items.

Important v2 behavior
Feasibility now tests the change you would actually ship: constraints and upgrade groups are applied before resolver/build/test checks.

Components and responsibilities
Component	Responsibility
SBOM	Inventory: dependencies present and their resolved versions.
Trivy + suppression ledger	Security scan and triage: vulnerabilities, fixed versions, and accepted findings.
Constraints file	Team-maintained pins, allowed ranges, upgrade-together groups, required tests, and owners.
Feasibility engine	Technical proof: strict resolve, build, and tests with the fixed candidate set.
Evidence enrichment	Release-note and changelog signals with source provenance and confidence.
Rules engine	Deterministic classification before the LLM writes anything.
Internal LLM LLM	Readable report writing only; no fact discovery or classification changes.
Human approval	Final approve/reject/manual strategy decision.

1. Pipeline overview
Job 1: Generate combined SBOM
  -> Job 2: Trivy scan + suppression triage
  -> Job 3: Feasibility engine (constraints/group-aware, strict resolution)
  -> Job 4: Evidence enrichment
  -> Job 5: AI report generation (internal LLM)
  -> Job 6: Human approval gate
  -> Job 7: Optional upgrade PR creation

Job	Question answered	Primary output
Job 1	What dependencies are present?	combined-sbom.json
Job 2	Which dependencies are vulnerable, and which findings are accepted?	trivy-results.json, suppressed.json
Job 3	Can the fixed version/group resolve, build, and test without breaking constraints?	feasibility.json, patches/, logs/
Job 4	What release evidence affects risk, and how confident are we?	evidence-bundle.json
Job 5	How should a human understand the upgrade strategy?	ai-report.json, ai-report.md
Job 6	Did a human approve the plan?	approval-result.json
Job 7	Can approved changes be prepared as a PR?	pull-request-result.json

Traceability model
Inventory, detection, feasibility, evidence, explanation, and approval are separate so every recommendation can be traced to a tool or a human decision.

2. Job 1 — Generate combined SBOM
Purpose
Create one resolved dependency inventory covering backend and frontend. This job answers what is present; it does not decide what is vulnerable.

Input example
repo/
  build.sbt
  project/plugins.sbt        # addSbtPlugin("com.github.sbt" % "sbt-sbom" % "0.5.0")
  project/Dependencies.scala
  backend/src/...
  frontend/package.json
  frontend/package-lock.json

Processing
# 1) Backend (Scala) -> CycloneDX BOM
sbt makeBom

# 2) Frontend (Angular) -> CycloneDX BOM from package-lock.json
cd frontend
npx --yes @cyclonedx/cyclonedx-npm@latest   --output-format JSON   --output-file frontend-sbom.json
cd ..

# 3) Merge into one SBOM
cyclonedx-cli merge   --input-files target/<name>-<version>.bom.xml frontend/frontend-sbom.json   --output-file combined-sbom.json   --output-format json

Output example
{
  "bomFormat": "CycloneDX",
  "specVersion": "1.5",
  "components": [
    {
      "type": "library",
      "group": "com.fasterxml.jackson.core",
      "name": "jackson-databind",
      "version": "2.13.5",
      "purl": "pkg:maven/com.fasterxml.jackson.core/jackson-databind@2.13.5"
    },
    {
      "type": "library",
      "name": "axios",
      "version": "1.5.0",
      "purl": "pkg:npm/axios@1.5.0"
    }
  ]
}

Output meaning
The SBOM records resolved versions only. Pins and upgrade policies live in the constraints file and are enforced later in Job 3.

3. Job 2 — Trivy scan + suppression triage
Purpose
Scan the combined SBOM for CVEs and apply the accepted-risk ledger. Installed versions come from the SBOM; fixed versions come from Trivy vulnerability data.

Processing
trivy sbom combined-sbom.json   --ignorefile .trivyignore   --format json   --output trivy-results.json

Suppression ledger examples
Simple .trivyignore
# .trivyignore
# Findings triaged and accepted with a reason and review date.
# Risk acceptance, not silent mute.

# CVE-2023-6378 - logback DoS, receiver component not deployed.
# Re-review by 2026-12-31.
CVE-2023-6378 exp:2026-12-31

Package-scoped YAML suppression
# .trivyignore.yaml
vulnerabilities:
  - id: CVE-2023-6378
    purls:
      - "pkg:maven/ch.qos.logback/logback-classic"
    statement: "Receiver component not deployed; not reachable."
    expired_at: 2026-12-31

Output example
{
  "Results": [
    {
      "Target": "combined-sbom.json",
      "Vulnerabilities": [
        {
          "VulnerabilityID": "CVE-2024-1111",
          "PkgName": "com.fasterxml.jackson.core:jackson-databind",
          "InstalledVersion": "2.13.5",
          "FixedVersion": "2.15.4",
          "Severity": "HIGH"
        },
        {
          "VulnerabilityID": "CVE-2024-2222",
          "PkgName": "axios",
          "InstalledVersion": "1.5.0",
          "FixedVersion": "1.6.8",
          "Severity": "HIGH"
        }
      ]
    }
  ]
}

Output meaning
Trivy identifies vulnerable versions and fixed versions. It does not prove the project can move to those versions; Job 3 does that.

4. Job 3 — Feasibility engine
Purpose
Prove whether fixed versions can technically work in this project. Job 3 reads team constraints, tests upgrade-together groups as one change, respects pins, and uses strict resolution so silent evictions cannot hide failed upgrades.

Core principle
Trivy:       this package is fixed in version X.
Constraints: these packages move together; these versions are pinned; these tests are required.
Job 3:       build the real candidate set in a temp copy, resolve strictly,
             verify X actually resolved, then build and test.

Constraints file example
# cve-advisor-constraints.yaml
pins:
  - package: "com.typesafe.akka:akka-actor-typed_2.13"
    version: "2.6.20"
    reason: "Last Apache-2.0 licensed Akka; do not move to BSL 2.7+."

allowedRanges:
  - package: "org.apache.kafka:kafka-clients"
    range: ">=3.4.0 <4.0.0"

upgradeTogether:
  - name: "jackson-family"
    packages:
      - "com.fasterxml.jackson.core:jackson-core"
      - "com.fasterxml.jackson.core:jackson-databind"
      - "com.fasterxml.jackson.core:jackson-annotations"
    reason: "Jackson modules must stay version-aligned."

requiredTests:
  - package: "com.fasterxml.jackson.core:jackson-databind"
    tests: ["sbt -batch testOnly *Json*"]
    reason: "Serialization/deserialization risk."

manualReview:
  - package: "com.example:internal-lib_2.13"
    reason: "No public changelog; always route to a human."

Processing steps
1. Read trivy-results.json and cve-advisor-constraints.yaml.
2. Build candidate sets: group CVEs by package, choose the highest fixed version, and expand upgrade-together groups.
3. Enforce allowed ranges and pins. If a candidate requires moving a pin, mark blocked-by-pin and do not override it.
4. Create a temporary workspace for each candidate set; never touch the real branch.
5. Apply the change: direct dependency becomes a version patch; transitive dependency becomes a temporary override only if policy allows it.
6. Resolve strictly and verify that the candidate version actually resolved.
7. Compare dependency graphs before/after to identify shared/common dependency impact.
8. Build and run required tests for the affected packages or groups.
9. Record status, logs, resolved-version checks, dependency graph impact, and a mandatory patch file for feasible items.

Scala strict resolution + verification
# Fail loudly on conflicts. Do not let resolver silently choose a winner.
coursier resolve --strict <full dependency set including candidate + existing pins>

# sbt configuration used by the feasibility workspace:
ThisBuild / conflictManager := ConflictManager.strict
ThisBuild / updateOptions  := updateOptions.value.withCachedResolution(false)

sbt -batch clean update compile
sbt -batch evicted

# Rule: if the candidate was evicted back to an older version,
# status = blocked-by-resolution, even if update/compile exited green.

Angular/npm strict resolution
# ERESOLVE on peer/version conflict = blocked-by-resolution.
# Do not pass --force or --legacy-peer-deps.
npm install --package-lock-only --ignore-scripts

# Clean install + Angular build:
npm ci --ignore-scripts
npm run build

# Required tests, if configured:
npm test -- --watch=false

Dependency graph impact example
{
  "dependencyGraphImpact": {
    "directDependencyChanged": false,
    "transitiveDependenciesChanged": [
      {
        "package": "com.fasterxml.jackson.core:jackson-databind",
        "from": "2.13.5",
        "to": "2.15.4",
        "affectedParents": [
          "com.typesafe.play:play-json_2.13:2.9.2",
          "com.company:kafka-client-wrapper_2.13:1.0.0"
        ],
        "impactType": "shared-common-dependency"
      }
    ],
    "evictionsOrOverrides": [
      {
        "package": "com.fasterxml.jackson.core:jackson-databind",
        "selectedVersion": "2.15.4",
        "evictedVersions": ["2.13.5"]
      }
    ]
  }
}

Output example
{
  "runId": "2026-06-21-001",
  "source": "trivy-results.json",
  "constraints": "cve-advisor-constraints.yaml",
  "summary": { "candidateSets": 4, "feasible": 1, "feasibleWithOverride": 1, "blocked": 2 },
  "results": [
    {
      "id": "scala-grp-jackson",
      "ecosystem": "scala",
      "group": "jackson-family",
      "packages": [
        "com.fasterxml.jackson.core:jackson-core",
        "com.fasterxml.jackson.core:jackson-databind",
        "com.fasterxml.jackson.core:jackson-annotations"
      ],
      "cves": ["CVE-2024-1111"],
      "candidateVersions": {
        "jackson-core": "2.15.4",
        "jackson-databind": "2.15.4",
        "jackson-annotations": "2.15.4"
      },
      "changeType": "temporary-dependencyOverride (group)",
      "status": "feasible-with-override",
      "resolutionCheck": "all three resolved at 2.15.4; none evicted",
      "commandsRun": [
        "coursier resolve --strict ...",
        "sbt -batch clean update compile",
        "sbt -batch evicted",
        "sbt -batch testOnly *Json*"
      ],
      "dependencyGraphImpact": {
        "impactType": "shared-common-dependency",
        "affectedParents": ["play-json_2.13", "kafka-client-wrapper_2.13"]
      },
      "patchFile": "patches/scala-jackson-2.15.4.patch",
      "logFile": "logs/scala-jackson-2.15.4.log"
    },
    {
      "id": "npm-axios",
      "ecosystem": "npm",
      "package": "axios",
      "cves": ["CVE-2024-2222"],
      "currentVersion": "1.5.0",
      "candidateVersion": "1.6.8",
      "changeType": "direct-package-json-bump",
      "status": "feasible",
      "resolutionCheck": "no ERESOLVE; axios@1.6.8 in lockfile",
      "commandsRun": [
        "npm install --package-lock-only --ignore-scripts",
        "npm ci --ignore-scripts",
        "npm run build"
      ],
      "patchFile": "patches/npm-axios-1.6.8.patch",
      "logFile": "logs/npm-axios-1.6.8.log"
    },
    {
      "id": "npm-nth-check",
      "ecosystem": "npm",
      "package": "nth-check",
      "cves": ["CVE-2021-3803"],
      "currentVersion": "1.0.2",
      "candidateVersion": "2.0.1",
      "changeType": "temporary-npm-override",
      "status": "blocked-by-resolution",
      "resolutionCheck": "npm install failed with ERESOLVE; parent constrains nth-check <2",
      "commandsRun": ["npm install --package-lock-only --ignore-scripts"],
      "logFile": "logs/npm-nth-check-2.0.1.log"
    },
    {
      "id": "scala-akka-stream",
      "ecosystem": "scala",
      "package": "com.typesafe.akka:akka-stream_2.13",
      "cves": ["CVE-EXAMPLE-AKKA"],
      "currentVersion": "2.6.20",
      "candidateVersion": "2.7.0",
      "changeType": "blocked",
      "status": "blocked-by-pin",
      "resolutionCheck": "candidate conflicts with pin akka 2.6.20; pin not overridden",
      "blockingPin": "com.typesafe.akka:akka-actor-typed_2.13@2.6.20",
      "logFile": "logs/scala-akka-stream-2.7.0.log"
    }
  ]
}

5. Job 4 — Evidence enrichment
Purpose
Add release/changelog context that helps a human judge risk. Constraints are already enforced in Job 3; Job 4 adds evidence and confidence and must not decide technical feasibility.

Provenance rule
Every risk signal must carry a source and matched text. If no reliable evidence is found, say so explicitly.

Processing steps
1. Read feasibility.json.
2. For each feasible or feasible-with-override item, locate release notes or CHANGELOG for the version range.
3. Extract risk signals such as security-fix, migration-note, deprecated-api, behavior-change, runtime-requirement.
4. Attach provenance: source file/URL, version range, and matched text.
5. Assign evidence confidence: high, medium, low, or none.
6. Record limitations when evidence is missing or unstructured.

Output example — evidence found
{
  "id": "scala-grp-jackson",
  "package": "com.fasterxml.jackson.core:jackson-databind",
  "ecosystem": "scala",
  "currentVersion": "2.13.5",
  "candidateVersion": "2.15.4",
  "feasibilityStatus": "feasible-with-override",
  "versionChangeType": "minor",
  "releaseEvidence": {
    "status": "found",
    "sourceType": "CHANGELOG.md",
    "confidence": "medium",
    "coveredRange": ">2.13.5 <=2.15.4"
  },
  "riskSignals": [
    {
      "type": "security-fix",
      "confidence": "medium",
      "source": "release-notes/VERSION-2.x",
      "matchedText": "Fix potential DoS in ...",
      "summary": "Security fix referenced in release notes."
    },
    {
      "type": "migration-note",
      "confidence": "high",
      "source": "CHANGELOG.md#2.15.0",
      "matchedText": "Custom serializers may need ...",
      "summary": "Custom serializers should run regression tests."
    }
  ],
  "limitations": ["Release notes are partly unstructured; not all behavior changes may be documented."],
  "recommendedReportHint": "needs-testing"
}

Output example — no changelog found
{
  "id": "scala-internal-lib",
  "package": "com.example:internal-lib_2.13",
  "currentVersion": "1.4.2",
  "candidateVersion": "1.4.9",
  "releaseEvidence": { "status": "not-found", "confidence": "none" },
  "riskSignals": [],
  "limitations": [
    "Package repository could not be identified.",
    "Breaking-change risk cannot be assessed from release notes."
  ],
  "recommendedReportHint": "needs-human-review"
}

6. Job 5 — AI report generation with internal LLM
Purpose
Turn structured evidence into a readable strategy report. The LLM does not discover facts, choose versions, or change classification.

Safety design
•	Send compact evidence JSON, never the full repo or raw logs.
•	Rules engine sets classificationFromRules before the model runs; the model must echo it and cannot change it.
•	Force JSON output and validate against a strict schema.
•	Require evidenceRefs that point to real input fields for every recommendation.
•	Reject output mentioning any package, version, CVE, command, or evidence reference not present in the input.
•	Render final Markdown using your own template; the model supplies only reason and recommendedAction prose.

Rule-based classification ladder
Evaluate all conditions; the most conservative outcome wins.

IF no fixed version:                          needs-human-review
ELSE IF blocked by pin:                       blocked-by-pin
ELSE IF blocked by allowed-range/policy:      blocked-by-policy
ELSE IF strict resolver rejected:             blocked-by-resolution
ELSE IF resolved version != candidate:        blocked-by-resolution
ELSE IF build failed:                         build-failed
ELSE IF required tests failed:                test-failed
ELSE IF required tests not run:               needs-testing
ELSE IF changelog confidence = none:          needs-human-review
ELSE IF breaking-change signals (high conf):  breaking
ELSE IF breaking-change signals:              needs-testing
ELSE IF major version bump:                   needs-testing
ELSE IF feasible-with-override:               needs-testing
ELSE IF shared dependency impact detected:    needs-testing
ELSE IF feasible + build passed + required tests passed + patch/minor bump:
                                                 safe-to-upgrade
ELSE:                                         needs-human-review

Prompt rules
You are given structured evidence for dependency upgrade candidates.
Use only the supplied JSON. Do not invent CVEs, versions, packages, changelog
facts, commands, blockers, or test results. Do not change classificationFromRules;
echo it. Every recommendation must include evidenceRefs pointing to fields in the
input. If evidence is insufficient, return needs-human-review. Return JSON only,
following the provided schema.

Output example
{
  "summary": {
    "totalItems": 4,
    "safeToUpgrade": 1,
    "needsTesting": 1,
    "blocked": 2,
    "needsHumanReview": 0
  },
  "recommendations": [
    {
      "id": "npm-axios",
      "package": "axios",
      "classification": "safe-to-upgrade",
      "priority": 1,
      "reason": "Clean npm install and Angular build passed; no breaking-change signal in the collected evidence.",
      "recommendedAction": "Apply the package.json bump and commit the updated package-lock.json.",
      "evidenceRefs": [
        "npm-axios.feasibility.status",
        "npm-axios.releaseEvidence.riskSignals"
      ]
    },
    {
      "id": "scala-grp-jackson",
      "package": "jackson-family",
      "classification": "needs-testing",
      "priority": 2,
      "reason": "Group resolves with overrides and builds, but policy and a migration note require serialization regression tests.",
      "recommendedAction": "Apply the Jackson group override in one PR and run JSON serialization tests.",
      "evidenceRefs": [
        "scala-grp-jackson.feasibility.status",
        "scala-grp-jackson.policyContext.requiredTests",
        "scala-grp-jackson.releaseEvidence.riskSignals"
      ]
    }
  ]
}

7. Job 6 — Human approval gate
Purpose
No automatic application until a human approves. Approval is item-level or group-level; an upgradeTogether group is approved as one unit.
•	Reviewer checks CVE severity, fixed version, resolution/build/test result, evidence confidence, constraints, AI explanation, and patch output.
•	Reviewer approves, rejects, or routes to manual strategy.
•	Approved items carry the patch produced in Job 3.

Output example
{
  "approvalStatus": "partially-approved",
  "approvedBy": "security-reviewer",
  "approvedItems": ["npm-axios", "scala-grp-jackson"],
  "rejectedItems": [],
  "manualReviewItems": [
    {
      "id": "npm-nth-check",
      "reason": "blocked-by-resolution; parent dependency needs a separate upgrade strategy."
    },
    {
      "id": "scala-akka-stream",
      "reason": "blocked-by-pin; requires a decision on the Akka 2.6.20 pin."
    }
  ]
}

8. Job 7 — Optional upgrade PR creation
Purpose
Prepare approved changes as a pull request. This is optional for MVP but useful after the pipeline is trusted.
1. Create a fresh branch.
2. Apply each approved Job 3 patch.
3. Re-run strict resolution, build, and required tests on the PR branch.
4. Open the PR with the AI report section and evidence attached.
5. Exclude blocked or manual-review items.

Output example
{
  "pullRequestCreated": true,
  "branch": "security/cve-upgrade-2026-06-21",
  "includedItems": ["npm-axios", "scala-grp-jackson"],
  "excludedItems": [
    {
      "id": "npm-nth-check",
      "reason": "blocked-by-resolution"
    },
    {
      "id": "scala-akka-stream",
      "reason": "blocked-by-pin"
    }
  ]
}

9. Artifact summary
Job	Inputs	Outputs
Job 1	Repo dependency files; package-lock.json; sbt project	combined-sbom.json
Job 2	combined-sbom.json; .trivyignore/.trivyignore.yaml	trivy-results.json; suppressed.json
Job 3	trivy-results.json; constraints file; repo source	feasibility.json; patches/; logs/
Job 4	feasibility.json; release/changelog sources	evidence-bundle.json
Job 5	trivy-results.json; feasibility.json; evidence-bundle.json; rule classifications	ai-report.json; ai-report.md
Job 6	AI report; feasibility evidence; patches	approval-result.json
Job 7	approval result; patches	pull-request-result.json

Final responsibility split
SBOM inventories. Trivy detects. Constraints express project policy. Job 3 proves technical feasibility. Job 4 adds evidence. Rules classify. LLM explains. Humans approve.
