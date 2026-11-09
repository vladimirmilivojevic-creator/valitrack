# How ValiTrack relates to the regulations

ValiTrack is a demonstration. It is **designed around the ideas** of the rules below. It is not certified, it has not been
validated itself, and nothing here is legal advice. The tables show where each idea appears in the product, and what a real
installation would still have to add.

Sources: 21 CFR Part 11 (FDA), EU GMP Annex 11 (2011 text), GAMP 5 (ISPE, second edition 2022), ISO 13485:2016 clause 4.1.6,
FDA guidance *Computer Software Assurance for Production and Quality System Software* (final, September 2025).
The European Commission published a draft revision of Annex 11 and a new Annex 22 in July 2025. Check their current status before relying on the 2011 numbering.

## 21 CFR Part 11: electronic records and signatures

| Idea | In ValiTrack | A real installation still needs |
|---|---|---|
| 11.10(a) Validation of the system | The test suite and the CI pipeline are the start of a validation package | A validation plan and report for ValiTrack itself |
| 11.10(d), (g) Limit access, authority checks | Roles with fixed permissions (`core/permissions.py`). A test calls every changing route as the read-only auditor and expects a refusal | Single sign-on, periodic access review |
| 11.10(e) Audit trail: secure, computer-generated, time-stamped, does not obscure old data | Append-only table, server time, hash chain, reason for change on edits | A database role without update and delete rights, external time source, regular review of the trail |
| 11.10(f) Enforce the order of steps | State machines: change requests, versions, test cases, runs, deviations. Steps in the wrong order are refused | |
| 11.10(i) People are trained | Training sessions and records per application version | |
| 11.10(k) Control of system documentation | Requirements baseline with a hash. Changes to approved items need a reason and show up in the release gate | |
| 11.50 Signature manifestation: name, date and time, meaning | Every signature shows the printed name, role, time and meaning (`Authored`, `Executed`, `Reviewed`, `Approved`, `Owner approved`, `Released`, `Closed`, `Training verified`) | |
| 11.70 Signature linked to the record | The signature stores a hash of the record content. The signature table is append only | |
| 11.100 Unique to one individual | One account per person. Accounts are deactivated, never deleted or reused | Identity proofing at account creation |
| 11.200 Two components | User name from the session plus the password, typed again at **every** signing | |
| 11.300(d) Safeguards against unauthorised use | Lockout after five wrong passwords, counted for logins and signatures. Failures are audited | Alerts to a security contact |

## EU GMP Annex 11: computerised systems (2011)

| Section | In ValiTrack |
|---|---|
| 1 Risk management | Risk per requirement (severity x probability x detectability) decides the testing effort |
| 4 Validation | URS, risk assessment, IQ/OQ/PQ, traceability matrix, summary report, release gate. Requirements are traceable through the life cycle |
| 5, 12.4 Data and security | Records are attributable to a named person. Times are set by the server |
| 7 Data storage | Evidence and reports are stored with SHA-256 hashes. Backups are a deployment task |
| 9 Audit trails | Hash-chained, append only, filterable, exportable as CSV, with a one-click integrity check. A reason is required for changes |
| 10 Change and configuration management | The change workflow. The configuration of a validated application can only be changed under an approved change request |
| 13 Incident management | Deviations with root cause and corrective and preventive action |
| 14 Electronic signature | Permanently linked to the record, with date and time |

## GAMP 5 and risk-based validation

| Idea | In ValiTrack |
|---|---|
| Software categories 1, 3, 4, 5 (category 2 no longer exists in the second edition) | A table in `services/gamp.py` decides which test types a category needs: 1 = IQ, 3 = IQ + OQ, 4 and 5 = IQ + OQ + PQ |
| Scale the effort to the risk | Requirements of low risk may be tested without a script. Tests of high-risk requirements need a QA review |
| Leverage supplier evidence | Not modelled. Category 3 and 4 applications are tested for the functions the company actually uses |
| Critical thinking, not paperwork | The release gate gives a reason in words for every open item instead of a bare yes or no |

## ISO 13485:2016 clause 4.1.6 and computer software assurance

ISO 13485 4.1.6 asks a medical device manufacturer to validate software used in its quality system before first use and
after changes, with an effort that is proportionate to the risk, and to keep records. Document control, training records,
calibration and complaint tools are typical examples. ValiTrack is built for that situation.

The FDA computer software assurance (CSA) guidance supports the same risk-based thinking and says that unscripted
testing is acceptable for lower-risk functions. ValiTrack implements this literally: *unscripted* test cases exist,
and they are accepted only for low-risk requirements.

IEC 62304 is a different standard: it governs software that **is** a medical device or part of one. ValiTrack is about the
software a company **uses** to run its quality system.

## What is deliberately not built

- Periodic review of the audit trail, and a periodic evaluation of validated systems (Annex 11 section 11).
- Supplier assessment and supplier audits (Annex 11 section 3).
- Archiving and retrieval over many years (section 17), business continuity (section 16).
- A password ageing policy. Passwords are checked for length and content only.
