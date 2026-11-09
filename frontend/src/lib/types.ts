// Shapes of the JSON that the API returns. They mirror the serializers in backend/app/api/serializers.py.

export type Role = "admin" | "validation_engineer" | "tester" | "qa_manager" | "system_owner" | "auditor";

export interface User {
  id: number;
  username: string;
  full_name: string;
  email: string;
  role: Role;
  department: string;
  is_active: boolean;
  last_login_at: string | null;
  created_at: string;
  locked: boolean;
}

export interface Session {
  user: User;
  permissions: string[];
  csrf_token: string;
}

export interface Version {
  id: number;
  application_id: number;
  version: string;
  status: "in_validation" | "validated" | "superseded" | "retired";
  urs_approved: boolean;
  urs_baseline_hash: string | null;
  urs_approved_at: string | null;
  release_notes: string | null;
  created_by: number;
  created_at: string;
  validated_at: string | null;
}

export interface Application {
  id: number;
  code: string;
  name: string;
  description: string;
  vendor: string;
  department: string;
  owner_id: number;
  owner_name: string | null;
  gamp_category: 1 | 3 | 4 | 5;
  gamp_name: string;
  required_tests: string[];
  intended_use: string;
  patient_safety_impact: boolean;
  product_quality_impact: boolean;
  data_integrity_impact: boolean;
  risk_class: "low" | "medium" | "high";
  status: string;
  live_version: Version | null;
  working_version: Version | null;
  approach?: string;
  versions?: Version[];
  users?: { user_id: number; app_role: string }[];
}

export interface Requirement {
  id: number;
  application_id: number;
  code: string;
  kind: "URS" | "FS";
  parent_id: number | null;
  title: string;
  description: string;
  severity: number | null;
  probability: number | null;
  detectability: number | null;
  rpn: number | null;
  risk_level: "low" | "medium" | "high" | null;
  status: "active" | "retired";
  created_by: number;
  test_case_ids: number[];
  test_codes: string[];
}

export interface TestStep {
  step_no: number;
  action: string;
  expected_result: string;
}

export interface TestCase {
  id: number;
  application_id: number;
  code: string;
  test_type: "IQ" | "OQ" | "PQ";
  title: string;
  objective: string;
  preconditions: string | null;
  style: "scripted" | "unscripted";
  status: "draft" | "approved" | "retired";
  revision: number;
  created_by: number;
  approved_by: number | null;
  approved_at: string | null;
  steps: TestStep[];
  requirement_ids: number[];
}

export interface Signature {
  id: number;
  user_id: number;
  signer_name: string;
  signer_role: string;
  meaning: string;
  entity_type: string;
  entity_id: number;
  entity_label: string;
  record_hash: string;
  comment: string | null;
  signed_at: string;
  signature_hash: string;
}

export interface Evidence {
  id: number;
  filename: string;
  content_type: string;
  size_bytes: number;
  sha256: string;
  uploaded_at: string;
}

export interface RunStep {
  step_no: number;
  action: string;
  expected_result: string;
  actual_result: string | null;
  result: "pending" | "passed" | "failed" | "blocked" | "na";
  comment: string | null;
  executed_at: string | null;
  evidence: Evidence[];
}

export interface Run {
  id: number;
  test_case_id: number;
  test_case_revision: number;
  app_version_id: number;
  change_request_id: number | null;
  status: "in_progress" | "completed";
  result: "passed" | "failed" | "blocked" | null;
  executed_by: number;
  started_at: string;
  completed_at: string | null;
  reviewed_by: number | null;
  reviewed_at: string | null;
  review_comment: string | null;
  test_code: string;
  test_title: string;
  test_type: "IQ" | "OQ" | "PQ";
  test_style: string;
  application_id: number;
  version: string;
  steps: RunStep[];
  signatures: Signature[];
}

export interface GateCheck {
  key: string;
  label: string;
  passed: boolean;
  detail: string;
}

export interface Gate {
  version_id: number;
  ready_for_report: boolean;
  passed: boolean;
  state_hash: string;
  checks: GateCheck[];
}

export interface ReportDoc {
  id: number;
  doc_number: string;
  app_version_id: number;
  status: "draft" | "approved" | "superseded";
  generated_by: number;
  generated_at: string;
  state_hash: string;
  sha256: string;
  gate_passed: boolean;
}

export interface Deviation {
  id: number;
  code: string;
  application_id: number;
  app_version_id: number | null;
  test_run_id: number | null;
  source: "test_failure" | "manual";
  title: string;
  description: string;
  severity: "minor" | "major" | "critical";
  root_cause: string | null;
  impact: string | null;
  corrective_action: string | null;
  preventive_action: string | null;
  owner_id: number | null;
  due_date: string | null;
  status: "open" | "in_progress" | "resolved" | "closed" | "accepted";
  closure_comment: string | null;
  closed_at: string | null;
  created_by: number;
  created_at: string;
  signatures: Signature[];
}

export interface ChangeImpact {
  id: number;
  change_id: number;
  department: string;
  assessor_id: number | null;
  impact_level: "none" | "low" | "medium" | "high" | null;
  affects_validated_state: boolean | null;
  comment: string | null;
  assessed_at: string | null;
}

export type ChangeStatus =
  | "draft"
  | "submitted"
  | "impact_assessment"
  | "pending_approval"
  | "approved"
  | "testing"
  | "ready_for_release"
  | "released"
  | "rejected"
  | "cancelled";

export interface Change {
  id: number;
  code: string;
  application_id: number;
  application_name: string;
  title: string;
  change_type: "bug_fix" | "enhancement" | "configuration" | "upgrade" | "patch";
  business_need: string;
  description: string;
  priority: "low" | "normal" | "high" | "urgent";
  requested_by: number;
  target_version: string;
  planned_release_date: string | null;
  affects_requirements: boolean;
  status: ChangeStatus;
  risk_level: "low" | "medium" | "high" | null;
  requires_revalidation: boolean | null;
  target_version_id: number | null;
  decision_reason: string | null;
  created_at: string;
  updated_at: string;
  released_at: string | null;
  impacts: ChangeImpact[];
  required_signatures: string[];
  signatures: Signature[];
  test_case_ids?: number[];
}

export interface ConfigItem {
  id: number;
  application_id: number;
  name: string;
  value: string;
  description: string | null;
  last_change_request_id: number | null;
  updated_by: number;
  updated_at: string;
}

export interface TrainingSession {
  id: number;
  code: string;
  application_id: number;
  app_version_id: number;
  title: string;
  session_type: "classroom" | "hands_on" | "online" | "read_and_understood";
  trainer_id: number;
  session_date: string;
  duration_minutes: number;
  materials: string | null;
  status: "planned" | "completed" | "cancelled";
  completed_at: string | null;
  attendees: { user_id: number; attended: boolean | null }[];
}

export interface MatrixRow {
  application_id: number;
  application_name: string;
  live_version: string;
  user_id: number;
  full_name: string;
  department: string;
  app_role: string;
  training_status: "trained" | "waived" | "retraining_needed" | "not_trained";
  completed_at: string | null;
}

export interface TicketComment {
  id: number;
  ticket_id: number;
  author_id: number;
  body: string;
  created_at: string;
}

export interface Ticket {
  id: number;
  code: string;
  application_id: number;
  reporter_id: number;
  assignee_id: number | null;
  summary: string;
  description: string;
  category: "access" | "how_to" | "defect" | "configuration" | "other";
  priority: "low" | "normal" | "high";
  status: "open" | "in_progress" | "waiting_user" | "resolved" | "closed";
  resolution: string | null;
  change_id: number | null;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
  comments: TicketComment[];
}

export interface BoardRow {
  application_id: number;
  code: string;
  name: string;
  gamp_category: number;
  risk_class: "low" | "medium" | "high";
  live_version: string | null;
  working_version: string | null;
  working_version_id: number | null;
  stage: "requirements" | "testing" | "report" | "release" | "validated";
  open_checks: number;
}

export interface Dashboard {
  board: BoardRow[];
  attention: {
    open_changes: number;
    changes_awaiting_approval: number;
    open_deviations: number;
    runs_awaiting_review: number;
    open_tickets: number;
    training_gaps: number;
  };
  activity: { seq: number; occurred_at: string; actor_name: string; action: string; entity_type: string; entity_label: string | null }[];
}

export interface AuditEntry {
  seq: number;
  occurred_at: string;
  actor_id: number | null;
  actor_name: string;
  action: string;
  entity_type: string;
  entity_id: string;
  entity_label: string | null;
  old_values: Record<string, unknown> | null;
  new_values: Record<string, unknown> | null;
  reason: string | null;
  prev_hash: string;
  entry_hash: string;
}

export interface ReportInfo {
  key: string;
  title: string;
  question: string;
  explain: string;
}

export interface ReportData extends ReportInfo {
  view: string;
  columns: string[];
  rows: (string | number | boolean | null)[][];
  sql: string;
}

export interface Meta {
  departments: string[];
  roles: Record<string, string>;
  permission_labels: Record<string, string>;
  role_permissions: Record<string, string[]>;
  gamp: Record<string, { name: string; examples: string; required_tests: string[]; summary: string }>;
  test_types: Record<string, string>;
  risk: {
    high_from: number;
    medium_from: number;
    severity: Record<string, string>;
    probability: Record<string, string>;
    detectability: Record<string, string>;
  };
  demo_mode: boolean;
}

export interface DemoAccounts {
  enabled: boolean;
  password?: string;
  accounts: { username: string; full_name: string; role: string; role_label: string; hint: string }[];
}

export interface TraceRow {
  application_id: number;
  requirement_id: number;
  requirement_code: string;
  test_case_id: number | null;
  test_code: string | null;
  latest_result: "passed" | "failed" | "blocked" | null;
}
