-- ValiTrack schema.
-- Written as plain SQL on purpose: constraints, generated columns and sequences
-- live in the database, so no application bug can store an invalid state.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE SEQUENCE app_code_seq START 1;
CREATE SEQUENCE cr_code_seq START 1;
CREATE SEQUENCE dev_code_seq START 1;
CREATE SEQUENCE ticket_code_seq START 1;
CREATE SEQUENCE training_code_seq START 1;
CREATE SEQUENCE report_code_seq START 1;

-- ---------------------------------------------------------------- users

CREATE TABLE users (
    id               serial PRIMARY KEY,
    username         text NOT NULL UNIQUE,
    full_name        text NOT NULL,
    email            text NOT NULL,
    role             text NOT NULL CHECK (role IN
                       ('admin', 'validation_engineer', 'tester', 'qa_manager', 'system_owner', 'auditor')),
    department       text NOT NULL CHECK (department IN
                       ('IT', 'Quality Assurance', 'Regulatory Affairs', 'Production', 'R&D', 'Customer Service')),
    password_hash    text NOT NULL,
    is_active        boolean NOT NULL DEFAULT true,
    failed_logins    integer NOT NULL DEFAULT 0,
    locked_until     timestamptz,
    last_login_at    timestamptz,
    created_at       timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------- applications

CREATE TABLE applications (
    id                      serial PRIMARY KEY,
    code                    text NOT NULL UNIQUE
                              DEFAULT 'APP-' || lpad(nextval('app_code_seq')::text, 3, '0'),
    name                    text NOT NULL UNIQUE,
    description             text NOT NULL,
    vendor                  text NOT NULL,
    department              text NOT NULL,
    owner_id                integer NOT NULL REFERENCES users (id),
    gamp_category           smallint NOT NULL CHECK (gamp_category IN (1, 3, 4, 5)),
    intended_use            text NOT NULL,
    patient_safety_impact   boolean NOT NULL DEFAULT false,
    product_quality_impact  boolean NOT NULL DEFAULT false,
    data_integrity_impact   boolean NOT NULL DEFAULT false,
    risk_class              text GENERATED ALWAYS AS (
                              CASE
                                WHEN patient_safety_impact
                                     OR (product_quality_impact AND data_integrity_impact) THEN 'high'
                                WHEN product_quality_impact OR data_integrity_impact THEN 'medium'
                                ELSE 'low'
                              END) STORED,
    status                  text NOT NULL DEFAULT 'active' CHECK (status IN ('planned', 'active', 'retired')),
    created_at              timestamptz NOT NULL DEFAULT now(),
    updated_at              timestamptz NOT NULL DEFAULT now()
);
ALTER SEQUENCE app_code_seq OWNED BY applications.code;

-- Who uses the application. Drives the training matrix.
CREATE TABLE application_users (
    application_id  integer NOT NULL REFERENCES applications (id) ON DELETE CASCADE,
    user_id         integer NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    app_role        text NOT NULL DEFAULT 'user' CHECK (app_role IN ('user', 'key_user', 'administrator')),
    granted_at      timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (application_id, user_id)
);

CREATE TABLE app_versions (
    id                 serial PRIMARY KEY,
    application_id     integer NOT NULL REFERENCES applications (id) ON DELETE CASCADE,
    version            text NOT NULL,
    status             text NOT NULL DEFAULT 'in_validation'
                         CHECK (status IN ('in_validation', 'validated', 'superseded', 'retired')),
    urs_approved       boolean NOT NULL DEFAULT false,
    urs_baseline_hash  text,
    urs_approved_at    timestamptz,
    release_notes      text,
    created_by         integer NOT NULL REFERENCES users (id),
    created_at         timestamptz NOT NULL DEFAULT now(),
    validated_at       timestamptz,
    UNIQUE (application_id, version)
);
-- At most one validated (live) version per application.
CREATE UNIQUE INDEX one_validated_version_per_app ON app_versions (application_id) WHERE status = 'validated';

-- ---------------------------------------------------------------- requirements and tests

CREATE TABLE requirements (
    id               serial PRIMARY KEY,
    application_id   integer NOT NULL REFERENCES applications (id) ON DELETE CASCADE,
    code             text NOT NULL,
    kind             text NOT NULL CHECK (kind IN ('URS', 'FS')),
    parent_id        integer REFERENCES requirements (id),
    title            text NOT NULL,
    description      text NOT NULL,
    severity         smallint CHECK (severity BETWEEN 1 AND 3),
    probability      smallint CHECK (probability BETWEEN 1 AND 3),
    detectability    smallint CHECK (detectability BETWEEN 1 AND 3),
    rpn              integer GENERATED ALWAYS AS (severity * probability * detectability) STORED,
    risk_level       text GENERATED ALWAYS AS (
                       CASE
                         WHEN severity IS NULL OR probability IS NULL OR detectability IS NULL THEN NULL
                         WHEN severity * probability * detectability >= 12 THEN 'high'
                         WHEN severity * probability * detectability >= 6 THEN 'medium'
                         ELSE 'low'
                       END) STORED,
    status           text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'retired')),
    created_by       integer NOT NULL REFERENCES users (id),
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now(),
    UNIQUE (application_id, code),
    CHECK (kind = 'FS' OR parent_id IS NULL),
    CHECK (kind = 'URS' OR parent_id IS NOT NULL)
);

CREATE TABLE test_cases (
    id               serial PRIMARY KEY,
    application_id   integer NOT NULL REFERENCES applications (id) ON DELETE CASCADE,
    code             text NOT NULL,
    test_type        text NOT NULL CHECK (test_type IN ('IQ', 'OQ', 'PQ')),
    title            text NOT NULL,
    objective        text NOT NULL,
    preconditions    text,
    style            text NOT NULL DEFAULT 'scripted' CHECK (style IN ('scripted', 'unscripted')),
    status           text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'approved', 'retired')),
    revision         integer NOT NULL DEFAULT 1,
    created_by       integer NOT NULL REFERENCES users (id),
    approved_by      integer REFERENCES users (id),
    approved_at      timestamptz,
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now(),
    UNIQUE (application_id, code)
);

CREATE TABLE test_steps (
    id               serial PRIMARY KEY,
    test_case_id     integer NOT NULL REFERENCES test_cases (id) ON DELETE CASCADE,
    step_no          integer NOT NULL CHECK (step_no > 0),
    action           text NOT NULL,
    expected_result  text NOT NULL,
    UNIQUE (test_case_id, step_no)
);

CREATE TABLE requirement_test_links (
    requirement_id   integer NOT NULL REFERENCES requirements (id) ON DELETE CASCADE,
    test_case_id     integer NOT NULL REFERENCES test_cases (id) ON DELETE CASCADE,
    PRIMARY KEY (requirement_id, test_case_id)
);

-- ---------------------------------------------------------------- change control

CREATE TABLE change_requests (
    id                     serial PRIMARY KEY,
    code                   text NOT NULL UNIQUE
                             DEFAULT 'CR-' || lpad(nextval('cr_code_seq')::text, 4, '0'),
    application_id         integer NOT NULL REFERENCES applications (id),
    title                  text NOT NULL,
    change_type            text NOT NULL CHECK (change_type IN
                             ('bug_fix', 'enhancement', 'configuration', 'upgrade', 'patch')),
    business_need          text NOT NULL,
    description            text NOT NULL,
    priority               text NOT NULL DEFAULT 'normal' CHECK (priority IN ('low', 'normal', 'high', 'urgent')),
    requested_by           integer NOT NULL REFERENCES users (id),
    target_version         text NOT NULL,
    planned_release_date   date,
    affects_requirements   boolean NOT NULL DEFAULT false,
    status                 text NOT NULL DEFAULT 'draft' CHECK (status IN
                             ('draft', 'submitted', 'impact_assessment', 'pending_approval', 'approved',
                              'testing', 'ready_for_release', 'released', 'rejected', 'cancelled')),
    risk_level             text CHECK (risk_level IN ('low', 'medium', 'high')),
    requires_revalidation  boolean,
    target_version_id      integer REFERENCES app_versions (id),
    decision_reason        text,
    created_at             timestamptz NOT NULL DEFAULT now(),
    updated_at             timestamptz NOT NULL DEFAULT now(),
    released_at            timestamptz
);
ALTER SEQUENCE cr_code_seq OWNED BY change_requests.code;

CREATE TABLE change_impacts (
    id                      serial PRIMARY KEY,
    change_id               integer NOT NULL REFERENCES change_requests (id) ON DELETE CASCADE,
    department              text NOT NULL CHECK (department IN
                              ('IT', 'Quality Assurance', 'Regulatory Affairs', 'Production', 'R&D', 'Customer Service')),
    assessor_id             integer REFERENCES users (id),
    impact_level            text CHECK (impact_level IN ('none', 'low', 'medium', 'high')),
    affects_validated_state boolean,
    comment                 text,
    assessed_at             timestamptz,
    UNIQUE (change_id, department)
);

CREATE TABLE change_test_links (
    change_id        integer NOT NULL REFERENCES change_requests (id) ON DELETE CASCADE,
    test_case_id     integer NOT NULL REFERENCES test_cases (id) ON DELETE CASCADE,
    PRIMARY KEY (change_id, test_case_id)
);

-- ---------------------------------------------------------------- test execution

CREATE TABLE test_runs (
    id                  serial PRIMARY KEY,
    test_case_id        integer NOT NULL REFERENCES test_cases (id),
    test_case_revision  integer NOT NULL,
    app_version_id      integer NOT NULL REFERENCES app_versions (id),
    change_request_id   integer REFERENCES change_requests (id),
    status              text NOT NULL DEFAULT 'in_progress' CHECK (status IN ('in_progress', 'completed')),
    result              text CHECK (result IN ('passed', 'failed', 'blocked')),
    executed_by         integer NOT NULL REFERENCES users (id),
    started_at          timestamptz NOT NULL DEFAULT now(),
    completed_at        timestamptz,
    reviewed_by         integer REFERENCES users (id),
    reviewed_at         timestamptz,
    review_comment      text,
    CHECK ((status = 'completed') = (result IS NOT NULL))
);
CREATE INDEX test_runs_version_case_idx ON test_runs (app_version_id, test_case_id);

CREATE TABLE test_run_steps (
    id               serial PRIMARY KEY,
    run_id           integer NOT NULL REFERENCES test_runs (id) ON DELETE CASCADE,
    step_no          integer NOT NULL,
    action           text NOT NULL,
    expected_result  text NOT NULL,
    actual_result    text,
    result           text NOT NULL DEFAULT 'pending'
                       CHECK (result IN ('pending', 'passed', 'failed', 'blocked', 'na')),
    comment          text,
    executed_at      timestamptz,
    UNIQUE (run_id, step_no)
);

-- Evidence is stored in the database with its SHA-256 hash (data integrity, ALCOA+).
CREATE TABLE evidence (
    id            serial PRIMARY KEY,
    run_step_id   integer NOT NULL REFERENCES test_run_steps (id) ON DELETE CASCADE,
    filename      text NOT NULL,
    content_type  text NOT NULL,
    size_bytes    integer NOT NULL CHECK (size_bytes > 0 AND size_bytes <= 2097152),
    sha256        text NOT NULL,
    data          bytea NOT NULL,
    uploaded_by   integer NOT NULL REFERENCES users (id),
    uploaded_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE deviations (
    id                 serial PRIMARY KEY,
    code               text NOT NULL UNIQUE
                         DEFAULT 'DEV-' || lpad(nextval('dev_code_seq')::text, 4, '0'),
    application_id     integer NOT NULL REFERENCES applications (id),
    app_version_id     integer REFERENCES app_versions (id),
    test_run_id        integer REFERENCES test_runs (id),
    source             text NOT NULL DEFAULT 'manual' CHECK (source IN ('test_failure', 'manual')),
    title              text NOT NULL,
    description        text NOT NULL,
    severity           text NOT NULL CHECK (severity IN ('minor', 'major', 'critical')),
    root_cause         text,
    impact             text,
    corrective_action  text,
    preventive_action  text,
    owner_id           integer REFERENCES users (id),
    due_date           date,
    status             text NOT NULL DEFAULT 'open'
                         CHECK (status IN ('open', 'in_progress', 'resolved', 'closed', 'accepted')),
    closure_comment    text,
    closed_at          timestamptz,
    created_by         integer NOT NULL REFERENCES users (id),
    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now()
);
ALTER SEQUENCE dev_code_seq OWNED BY deviations.code;

-- ---------------------------------------------------------------- configuration, training, support

CREATE TABLE config_items (
    id                      serial PRIMARY KEY,
    application_id          integer NOT NULL REFERENCES applications (id) ON DELETE CASCADE,
    name                    text NOT NULL,
    value                   text NOT NULL,
    description             text,
    last_change_request_id  integer REFERENCES change_requests (id),
    updated_by              integer NOT NULL REFERENCES users (id),
    updated_at              timestamptz NOT NULL DEFAULT now(),
    UNIQUE (application_id, name)
);

CREATE TABLE training_sessions (
    id                serial PRIMARY KEY,
    code              text NOT NULL UNIQUE
                        DEFAULT 'TRN-' || lpad(nextval('training_code_seq')::text, 3, '0'),
    application_id    integer NOT NULL REFERENCES applications (id) ON DELETE CASCADE,
    app_version_id    integer NOT NULL REFERENCES app_versions (id),
    title             text NOT NULL,
    session_type      text NOT NULL CHECK (session_type IN
                        ('classroom', 'hands_on', 'online', 'read_and_understood')),
    trainer_id        integer NOT NULL REFERENCES users (id),
    session_date      date NOT NULL,
    duration_minutes  integer NOT NULL CHECK (duration_minutes > 0),
    materials         text,
    status            text NOT NULL DEFAULT 'planned' CHECK (status IN ('planned', 'completed', 'cancelled')),
    completed_at      timestamptz,
    created_at        timestamptz NOT NULL DEFAULT now()
);
ALTER SEQUENCE training_code_seq OWNED BY training_sessions.code;

CREATE TABLE training_attendees (
    session_id  integer NOT NULL REFERENCES training_sessions (id) ON DELETE CASCADE,
    user_id     integer NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    attended    boolean,
    PRIMARY KEY (session_id, user_id)
);

-- One row per user and application version: has this person been trained on this version?
CREATE TABLE training_records (
    id              serial PRIMARY KEY,
    application_id  integer NOT NULL REFERENCES applications (id) ON DELETE CASCADE,
    app_version_id  integer NOT NULL REFERENCES app_versions (id),
    user_id         integer NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    session_id      integer REFERENCES training_sessions (id),
    status          text NOT NULL CHECK (status IN ('required', 'completed', 'waived')),
    required_at     timestamptz,
    completed_at    timestamptz,
    comment         text,
    UNIQUE (app_version_id, user_id)
);

CREATE TABLE support_tickets (
    id              serial PRIMARY KEY,
    code            text NOT NULL UNIQUE
                      DEFAULT 'TCK-' || lpad(nextval('ticket_code_seq')::text, 4, '0'),
    application_id  integer NOT NULL REFERENCES applications (id),
    reporter_id     integer NOT NULL REFERENCES users (id),
    assignee_id     integer REFERENCES users (id),
    summary         text NOT NULL,
    description     text NOT NULL,
    category        text NOT NULL CHECK (category IN ('access', 'how_to', 'defect', 'configuration', 'other')),
    priority        text NOT NULL DEFAULT 'normal' CHECK (priority IN ('low', 'normal', 'high')),
    status          text NOT NULL DEFAULT 'open'
                      CHECK (status IN ('open', 'in_progress', 'waiting_user', 'resolved', 'closed')),
    resolution      text,
    change_id       integer REFERENCES change_requests (id),
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    resolved_at     timestamptz
);
ALTER SEQUENCE ticket_code_seq OWNED BY support_tickets.code;

CREATE TABLE ticket_comments (
    id          serial PRIMARY KEY,
    ticket_id   integer NOT NULL REFERENCES support_tickets (id) ON DELETE CASCADE,
    author_id   integer NOT NULL REFERENCES users (id),
    body        text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------- reports

CREATE TABLE report_documents (
    id              serial PRIMARY KEY,
    doc_number      text NOT NULL UNIQUE
                      DEFAULT 'VSR-' || lpad(nextval('report_code_seq')::text, 4, '0'),
    app_version_id  integer NOT NULL REFERENCES app_versions (id) ON DELETE CASCADE,
    status          text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'approved', 'superseded')),
    generated_by    integer NOT NULL REFERENCES users (id),
    generated_at    timestamptz NOT NULL DEFAULT now(),
    state_hash      text NOT NULL,
    sha256          text NOT NULL,
    gate_passed     boolean NOT NULL,
    pdf             bytea NOT NULL
);
ALTER SEQUENCE report_code_seq OWNED BY report_documents.doc_number;

-- ---------------------------------------------------------------- electronic signatures

CREATE TABLE e_signatures (
    id              serial PRIMARY KEY,
    user_id         integer NOT NULL REFERENCES users (id),
    signer_name     text NOT NULL,
    signer_role     text NOT NULL,
    meaning         text NOT NULL CHECK (meaning IN
                      ('Authored', 'Executed', 'Reviewed', 'Approved', 'Owner approved',
                       'Released', 'Closed', 'Training verified')),
    entity_type     text NOT NULL,
    entity_id       integer NOT NULL,
    entity_label    text NOT NULL,
    record_hash     text NOT NULL,
    comment         text,
    signed_at       timestamptz NOT NULL DEFAULT clock_timestamp(),
    signature_hash  text NOT NULL
);
CREATE INDEX e_signatures_entity_idx ON e_signatures (entity_type, entity_id);

CREATE INDEX requirements_app_idx ON requirements (application_id);
CREATE INDEX test_cases_app_idx ON test_cases (application_id);
CREATE INDEX change_requests_app_idx ON change_requests (application_id);
CREATE INDEX deviations_app_idx ON deviations (application_id);
CREATE INDEX support_tickets_app_idx ON support_tickets (application_id);
CREATE INDEX training_records_user_idx ON training_records (user_id);
