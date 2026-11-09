export type Tone = "pass" | "fail" | "warn" | "info" | "accent" | "neutral";

/** One place that decides how every status looks. A status is never shown by colour alone: it always has text and an icon. */
export const STATUS: Record<string, { label: string; tone: Tone }> = {
  // versions
  in_validation: { label: "In validation", tone: "info" },
  validated: { label: "Validated", tone: "pass" },
  superseded: { label: "Superseded", tone: "neutral" },
  retired: { label: "Retired", tone: "neutral" },
  // test cases and requirements
  draft: { label: "Draft", tone: "neutral" },
  approved: { label: "Approved", tone: "pass" },
  active: { label: "Active", tone: "pass" },
  // runs and steps
  in_progress: { label: "In progress", tone: "info" },
  completed: { label: "Completed", tone: "neutral" },
  passed: { label: "Passed", tone: "pass" },
  failed: { label: "Failed", tone: "fail" },
  blocked: { label: "Blocked", tone: "warn" },
  na: { label: "Not applicable", tone: "neutral" },
  pending: { label: "Not done", tone: "neutral" },
  not_run: { label: "Not run", tone: "neutral" },
  // changes
  submitted: { label: "Submitted", tone: "info" },
  impact_assessment: { label: "Impact assessment", tone: "info" },
  pending_approval: { label: "Awaiting approval", tone: "warn" },
  testing: { label: "Testing", tone: "info" },
  ready_for_release: { label: "Ready for release", tone: "accent" },
  released: { label: "Released", tone: "pass" },
  rejected: { label: "Rejected", tone: "fail" },
  cancelled: { label: "Cancelled", tone: "neutral" },
  // deviations and tickets
  open: { label: "Open", tone: "warn" },
  resolved: { label: "Resolved", tone: "info" },
  closed: { label: "Closed", tone: "neutral" },
  accepted: { label: "Accepted", tone: "neutral" },
  waiting_user: { label: "Waiting for user", tone: "neutral" },
  // training
  trained: { label: "Trained", tone: "pass" },
  waived: { label: "Waived", tone: "neutral" },
  retraining_needed: { label: "Retraining needed", tone: "warn" },
  not_trained: { label: "Not trained", tone: "fail" },
  required: { label: "Required", tone: "warn" },
  planned: { label: "Planned", tone: "info" },
  // reports
  superseded_report: { label: "Superseded", tone: "neutral" },
  // severity and priority
  minor: { label: "Minor", tone: "neutral" },
  major: { label: "Major", tone: "warn" },
  critical: { label: "Critical", tone: "fail" },
  low: { label: "Low", tone: "neutral" },
  normal: { label: "Normal", tone: "neutral" },
  high: { label: "High", tone: "warn" },
  urgent: { label: "Urgent", tone: "fail" },
  none: { label: "None", tone: "neutral" },
};

export const RISK: Record<string, { label: string; tone: Tone }> = {
  high: { label: "High risk", tone: "accent" },
  medium: { label: "Medium risk", tone: "warn" },
  low: { label: "Low risk", tone: "neutral" },
};

export const CHANGE_TYPES: Record<string, string> = {
  bug_fix: "Bug fix",
  enhancement: "Enhancement",
  configuration: "Configuration",
  upgrade: "Upgrade",
  patch: "Patch",
};

export const TICKET_CATEGORIES: Record<string, string> = {
  access: "Access",
  how_to: "How-to question",
  defect: "Defect",
  configuration: "Configuration",
  other: "Other",
};

export const SESSION_TYPES: Record<string, string> = {
  classroom: "Classroom",
  hands_on: "Hands-on",
  online: "Online",
  read_and_understood: "Read and understood",
};

export const IMPACT_LEVELS = ["none", "low", "medium", "high"] as const;

/** The steps of a change request, in order. Used for the timeline. */
export const CHANGE_FLOW = [
  "draft",
  "submitted",
  "impact_assessment",
  "pending_approval",
  "approved",
  "testing",
  "ready_for_release",
  "released",
] as const;
