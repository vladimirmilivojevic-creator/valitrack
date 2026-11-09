-- Report views. Each view answers one plain question. The Reports page shows
-- the data and the SQL of the view, and the dashboard reads from the same views.

-- Helper: the most recent completed run of every test case on every version.
CREATE VIEW vw_latest_runs AS
SELECT DISTINCT ON (r.app_version_id, r.test_case_id)
       r.id, r.test_case_id, r.app_version_id, r.change_request_id, r.result,
       r.executed_by, r.completed_at, r.reviewed_by, r.reviewed_at
FROM test_runs r
WHERE r.status = 'completed'
ORDER BY r.app_version_id, r.test_case_id, r.completed_at DESC, r.id DESC;

-- 1. Where does each application stand in its validation?
CREATE VIEW vw_validation_status AS
WITH working_version AS (
    SELECT DISTINCT ON (v.application_id) v.*
    FROM app_versions v
    WHERE v.status IN ('in_validation', 'validated')
    ORDER BY v.application_id, (v.status = 'in_validation') DESC, v.id DESC
)
SELECT a.id            AS application_id,
       a.code          AS application_code,
       a.name          AS application_name,
       a.gamp_category,
       a.risk_class,
       v.id            AS version_id,
       v.version,
       v.status        AS version_status,
       req.total       AS requirements_total,
       req.covered     AS requirements_covered,
       CASE WHEN req.total = 0 THEN 0
            ELSE round(100.0 * req.covered / req.total, 1) END AS coverage_pct,
       COALESCE(run.passed, 0)  AS tests_passed,
       COALESCE(run.failed, 0)  AS tests_failed,
       GREATEST(tc.total - COALESCE(run.passed, 0) - COALESCE(run.failed, 0) - COALESCE(run.blocked, 0), 0)
                               AS tests_not_run,
       (SELECT count(*) FROM deviations d
         WHERE d.application_id = a.id AND d.status IN ('open', 'in_progress', 'resolved')) AS open_deviations
FROM applications a
LEFT JOIN working_version v ON v.application_id = a.id
CROSS JOIN LATERAL (
    SELECT count(*) AS total,
           count(*) FILTER (WHERE EXISTS (
               SELECT 1 FROM requirement_test_links l
               JOIN test_cases t ON t.id = l.test_case_id AND t.status = 'approved'
               WHERE l.requirement_id = r.id)) AS covered
    FROM requirements r
    WHERE r.application_id = a.id AND r.status = 'active'
) req
CROSS JOIN LATERAL (
    SELECT count(*) AS total FROM test_cases t WHERE t.application_id = a.id AND t.status = 'approved'
) tc
LEFT JOIN LATERAL (
    SELECT count(*) FILTER (WHERE lr.result = 'passed')  AS passed,
           count(*) FILTER (WHERE lr.result = 'failed')  AS failed,
           count(*) FILTER (WHERE lr.result = 'blocked') AS blocked
    FROM vw_latest_runs lr
    JOIN test_cases t ON t.id = lr.test_case_id
    WHERE lr.app_version_id = v.id AND t.status = 'approved'
) run ON true
WHERE a.status <> 'retired';

-- 2. Traceability: requirement -> test case -> latest result on the working version.
CREATE VIEW vw_traceability AS
SELECT r.application_id,
       a.name       AS application_name,
       r.id         AS requirement_id,
       r.code       AS requirement_code,
       r.kind,
       r.title      AS requirement_title,
       r.risk_level,
       t.id         AS test_case_id,
       t.code       AS test_code,
       t.test_type,
       t.title      AS test_title,
       t.status     AS test_status,
       v.version,
       lr.result    AS latest_result,
       lr.completed_at
FROM requirements r
JOIN applications a ON a.id = r.application_id
LEFT JOIN LATERAL (
    SELECT v2.* FROM app_versions v2
    WHERE v2.application_id = r.application_id AND v2.status IN ('in_validation', 'validated')
    ORDER BY (v2.status = 'in_validation') DESC, v2.id DESC
    LIMIT 1
) v ON true
LEFT JOIN requirement_test_links l ON l.requirement_id = r.id
LEFT JOIN test_cases t ON t.id = l.test_case_id AND t.status <> 'retired'
LEFT JOIN vw_latest_runs lr ON lr.test_case_id = t.id AND lr.app_version_id = v.id
WHERE r.status = 'active';

-- 3. How did IQ, OQ and PQ go on each version?
CREATE VIEW vw_test_execution_summary AS
SELECT a.name       AS application_name,
       v.version,
       t.test_type,
       count(*)                                          AS tests_executed,
       count(*) FILTER (WHERE lr.result = 'passed')      AS passed,
       count(*) FILTER (WHERE lr.result = 'failed')      AS failed,
       count(*) FILTER (WHERE lr.result = 'blocked')     AS blocked,
       round(100.0 * count(*) FILTER (WHERE lr.result = 'passed') / count(*), 1) AS pass_rate_pct
FROM vw_latest_runs lr
JOIN test_cases t   ON t.id = lr.test_case_id
JOIN app_versions v ON v.id = lr.app_version_id
JOIN applications a ON a.id = v.application_id
GROUP BY a.name, v.version, t.test_type;

-- 4. Which changes are still open, how old are they, and who are they waiting for?
CREATE VIEW vw_open_changes AS
SELECT c.code,
       a.name          AS application_name,
       c.title,
       c.change_type,
       c.status,
       c.risk_level,
       c.priority,
       u.full_name     AS requested_by,
       c.target_version,
       c.planned_release_date,
       (current_date - c.created_at::date) AS age_days,
       CASE c.status
         WHEN 'draft'             THEN 'Requester must submit'
         WHEN 'submitted'         THEN 'Coordinator must start the impact assessment'
         WHEN 'impact_assessment' THEN 'Impact from: ' || COALESCE((
              SELECT string_agg(i.department, ', ' ORDER BY i.department)
              FROM change_impacts i WHERE i.change_id = c.id AND i.assessed_at IS NULL), 'nobody')
         WHEN 'pending_approval'  THEN 'Approval signatures'
         WHEN 'approved'          THEN 'Testing must start'
         WHEN 'testing'           THEN 'Test execution and review'
         WHEN 'ready_for_release' THEN 'Report approval and release'
       END AS waiting_for
FROM change_requests c
JOIN applications a ON a.id = c.application_id
JOIN users u        ON u.id = c.requested_by
WHERE c.status NOT IN ('released', 'rejected', 'cancelled');

-- 5. Is everybody trained on the version that is live now?
CREATE VIEW vw_training_compliance AS
SELECT a.id          AS application_id,
       a.name        AS application_name,
       v.version     AS live_version,
       u.id          AS user_id,
       u.full_name,
       u.department,
       au.app_role,
       CASE
         WHEN tr.status = 'completed' THEN 'trained'
         WHEN tr.status = 'waived'    THEN 'waived'
         WHEN EXISTS (SELECT 1 FROM training_records old
                      WHERE old.application_id = a.id AND old.user_id = u.id AND old.status = 'completed')
              THEN 'retraining_needed'
         ELSE 'not_trained'
       END           AS training_status,
       tr.completed_at
FROM applications a
JOIN app_versions v        ON v.application_id = a.id AND v.status = 'validated'
JOIN application_users au  ON au.application_id = a.id
JOIN users u               ON u.id = au.user_id AND u.is_active
LEFT JOIN training_records tr ON tr.app_version_id = v.id AND tr.user_id = u.id;

-- 6. Open deviations and how long they have been open.
CREATE VIEW vw_deviation_aging AS
SELECT d.code,
       a.name        AS application_name,
       d.title,
       d.severity,
       d.status,
       o.full_name   AS owner,
       d.due_date,
       (current_date - d.created_at::date) AS age_days,
       CASE
         WHEN d.due_date IS NOT NULL AND d.due_date < current_date THEN 'overdue'
         WHEN current_date - d.created_at::date > 30 THEN 'older than 30 days'
         ELSE 'on track'
       END           AS aging
FROM deviations d
JOIN applications a ON a.id = d.application_id
LEFT JOIN users o   ON o.id = d.owner_id
WHERE d.status IN ('open', 'in_progress', 'resolved');

-- 7. Support load per application.
CREATE VIEW vw_support_by_application AS
SELECT a.name        AS application_name,
       count(*)                                           AS tickets_total,
       count(*) FILTER (WHERE t.status IN ('open', 'in_progress', 'waiting_user')) AS tickets_open,
       count(*) FILTER (WHERE t.category = 'defect')      AS defects,
       count(*) FILTER (WHERE t.category = 'how_to')      AS how_to_questions,
       round(avg(extract(epoch FROM (t.resolved_at - t.created_at)) / 3600.0)
             FILTER (WHERE t.resolved_at IS NOT NULL)::numeric, 1) AS avg_hours_to_resolve
FROM support_tickets t
JOIN applications a ON a.id = t.application_id
GROUP BY a.name;

-- 8. What happened in the system, per day and record type?
CREATE VIEW vw_audit_activity AS
SELECT date_trunc('day', occurred_at)::date AS day,
       entity_type,
       count(*)                             AS events,
       count(DISTINCT actor_name)           AS people
FROM audit_log
GROUP BY 1, 2;
