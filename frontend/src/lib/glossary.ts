/** Plain-English explanations. Shown as tooltips and on the About page. */
export const GLOSSARY: Record<string, { name: string; text: string }> = {
  GAMP: {
    name: "GAMP 5",
    text: "A guide from ISPE for validating computerised systems. It sorts software into categories (1, 3, 4, 5). The more an application is configured or custom-built, the more testing it needs.",
  },
  CSV: {
    name: "Computer system validation (CSV)",
    text: "Proving, with documents and tests, that a computer system does what it should for its intended use, and keeps doing so after changes.",
  },
  URS: {
    name: "URS (user requirement specification)",
    text: "The list of what the users need the system to do. Every requirement must later be covered by a test.",
  },
  FS: {
    name: "FS (functional specification)",
    text: "A more technical description of how the system meets a user requirement.",
  },
  IQ: {
    name: "IQ (installation qualification)",
    text: "Tests that show the system is installed and set up as specified.",
  },
  OQ: {
    name: "OQ (operational qualification)",
    text: "Tests that show each function works as specified.",
  },
  PQ: {
    name: "PQ (performance qualification)",
    text: "Tests that show the system works for the real process, with real users, from start to end.",
  },
  RPN: {
    name: "RPN (risk priority number)",
    text: "Severity x probability x detectability, each rated 1 to 3. A higher number means more testing effort.",
  },
  CAPA: {
    name: "CAPA (corrective and preventive action)",
    text: "Fix the problem now (corrective) and change something so that it does not come back (preventive).",
  },
  Deviation: {
    name: "Deviation",
    text: "Something that did not go as planned, for example a failed test. It must be analysed and closed by QA.",
  },
  "Audit trail": {
    name: "Audit trail",
    text: "A permanent log of who did what and when. Entries cannot be changed or deleted, and each one is linked to the one before by a hash.",
  },
  "Electronic signature": {
    name: "Electronic signature",
    text: "A signature made in the system. The signer types the password again, and the system stores name, role, time, meaning and a fingerprint of the signed record.",
  },
  "Part 11": {
    name: "21 CFR Part 11",
    text: "US rules (FDA) for electronic records and electronic signatures. ValiTrack follows its main ideas: access control, audit trail, signature manifestation.",
  },
  "Annex 11": {
    name: "EU GMP Annex 11",
    text: "The European rules for computerised systems in regulated manufacturing: risk-based validation, data integrity, audit trails, change control.",
  },
  ALCOA: {
    name: "ALCOA+",
    text: "Data should be Attributable, Legible, Contemporaneous, Original and Accurate, plus Complete, Consistent, Enduring and Available.",
  },
  "Release gate": {
    name: "Release gate",
    text: "A list of checks that must all be met before a version can be released as validated.",
  },
  "Change control": {
    name: "Change control",
    text: "A fixed process for changing a validated system: request, impact assessment, approval, testing, release.",
  },
  SoD: {
    name: "Segregation of duties",
    text: "Two different people must do two steps, for example one writes a test and another approves it.",
  },
  GxP: {
    name: "GxP",
    text: "Good practice rules (manufacturing, laboratory, clinical) that apply to regulated companies.",
  },
  Traceability: {
    name: "Traceability matrix",
    text: "A table that links each requirement to the tests that cover it and shows the latest result.",
  },
};
