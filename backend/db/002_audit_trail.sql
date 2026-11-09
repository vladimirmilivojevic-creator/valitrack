-- Audit trail and electronic signature integrity.
--
-- The audit trail is enforced in the database, not in the application:
--   * rows can only be inserted (UPDATE, DELETE and TRUNCATE are blocked by triggers);
--   * every row stores the hash of the row before it, so the rows form a chain;
--   * the server writes the time and the hash, the application cannot choose them.
-- verify_audit_chain() recalculates the whole chain and reports the first broken row.

CREATE TABLE audit_log (
    seq           bigint PRIMARY KEY,
    occurred_at   timestamptz NOT NULL,
    actor_id      integer,
    actor_name    text NOT NULL,
    action        text NOT NULL,
    entity_type   text NOT NULL,
    entity_id     text NOT NULL,
    entity_label  text,
    old_values    jsonb,
    new_values    jsonb,
    reason        text,
    prev_hash     text NOT NULL,
    entry_hash    text NOT NULL
);
CREATE INDEX audit_log_entity_idx ON audit_log (entity_type, entity_id);
CREATE INDEX audit_log_time_idx ON audit_log (occurred_at);

-- One place that defines what is hashed. The trigger and the verifier both use it.
CREATE FUNCTION audit_entry_hash(
    p_prev text, p_seq bigint, p_ts timestamptz, p_actor_id integer, p_actor_name text,
    p_action text, p_entity_type text, p_entity_id text, p_entity_label text,
    p_old jsonb, p_new jsonb, p_reason text
) RETURNS text
LANGUAGE sql IMMUTABLE AS $$
    SELECT encode(
        digest(
            p_prev || '|' || jsonb_build_array(
                p_seq,
                to_char(p_ts AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US'),
                p_actor_id, p_actor_name, p_action, p_entity_type, p_entity_id,
                p_entity_label, p_old, p_new, p_reason
            )::text,
            'sha256'),
        'hex')
$$;

CREATE FUNCTION audit_log_before_insert() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    last_seq  bigint;
    last_hash text;
BEGIN
    -- One writer at a time keeps the chain in a single line.
    PERFORM pg_advisory_xact_lock(7270001);
    SELECT seq, entry_hash INTO last_seq, last_hash FROM audit_log ORDER BY seq DESC LIMIT 1;
    NEW.seq := COALESCE(last_seq, 0) + 1;
    NEW.prev_hash := COALESCE(last_hash, repeat('0', 64));
    NEW.occurred_at := clock_timestamp();
    NEW.entry_hash := audit_entry_hash(
        NEW.prev_hash, NEW.seq, NEW.occurred_at, NEW.actor_id, NEW.actor_name, NEW.action,
        NEW.entity_type, NEW.entity_id, NEW.entity_label, NEW.old_values, NEW.new_values, NEW.reason);
    RETURN NEW;
END $$;

CREATE TRIGGER audit_log_chain
    BEFORE INSERT ON audit_log
    FOR EACH ROW EXECUTE FUNCTION audit_log_before_insert();

-- Append-only tables: no UPDATE, no DELETE.
CREATE FUNCTION forbid_change() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION '% on table "%" is not allowed: the table is append-only', TG_OP, TG_TABLE_NAME
        USING ERRCODE = 'integrity_constraint_violation';
END $$;

-- TRUNCATE is only possible while the demo reset sets valitrack.allow_reset.
CREATE FUNCTION forbid_truncate() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF current_setting('valitrack.allow_reset', true) = 'on' THEN
        RETURN NULL;
    END IF;
    RAISE EXCEPTION 'TRUNCATE on table "%" is not allowed: the table is append-only', TG_TABLE_NAME
        USING ERRCODE = 'integrity_constraint_violation';
END $$;

CREATE TRIGGER audit_log_no_change
    BEFORE UPDATE OR DELETE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION forbid_change();
CREATE TRIGGER audit_log_no_truncate
    BEFORE TRUNCATE ON audit_log
    FOR EACH STATEMENT EXECUTE FUNCTION forbid_truncate();

-- Electronic signatures: the server sets the time and the signature hash.
CREATE FUNCTION e_signatures_before_insert() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    NEW.signed_at := clock_timestamp();
    NEW.signature_hash := encode(
        digest(
            concat_ws('|', NEW.user_id, NEW.signer_name, NEW.signer_role, NEW.meaning,
                      NEW.entity_type, NEW.entity_id, NEW.record_hash,
                      to_char(NEW.signed_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US')),
            'sha256'),
        'hex');
    RETURN NEW;
END $$;

CREATE TRIGGER e_signatures_stamp
    BEFORE INSERT ON e_signatures
    FOR EACH ROW EXECUTE FUNCTION e_signatures_before_insert();
CREATE TRIGGER e_signatures_no_change
    BEFORE UPDATE OR DELETE ON e_signatures
    FOR EACH ROW EXECUTE FUNCTION forbid_change();
CREATE TRIGGER e_signatures_no_truncate
    BEFORE TRUNCATE ON e_signatures
    FOR EACH STATEMENT EXECUTE FUNCTION forbid_truncate();

-- Recalculates the chain. first_broken_seq is NULL when everything is intact.
CREATE FUNCTION verify_audit_chain()
RETURNS TABLE (entries bigint, first_broken_seq bigint, head_hash text)
LANGUAGE sql STABLE AS $$
    WITH ordered AS (
        SELECT a.*,
               lag(a.entry_hash) OVER (ORDER BY a.seq) AS previous_row_hash,
               row_number() OVER (ORDER BY a.seq)      AS position
        FROM audit_log a
    ),
    checked AS (
        SELECT o.seq,
               (   o.prev_hash IS DISTINCT FROM COALESCE(o.previous_row_hash, repeat('0', 64))
                OR o.seq <> o.position
                OR o.entry_hash IS DISTINCT FROM audit_entry_hash(
                       o.prev_hash, o.seq, o.occurred_at, o.actor_id, o.actor_name, o.action,
                       o.entity_type, o.entity_id, o.entity_label, o.old_values, o.new_values, o.reason)
               ) AS broken
        FROM ordered o
    )
    SELECT (SELECT count(*) FROM audit_log),
           (SELECT min(seq) FROM checked WHERE broken),
           (SELECT entry_hash FROM audit_log ORDER BY seq DESC LIMIT 1)
$$;
