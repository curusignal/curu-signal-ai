-- CURU SIGNAL AI: migración 001 - proteger historial comercial.
-- Ejecutar una sola vez en PostgreSQL después de crear las tablas base.
-- init_db() también instala estas protecciones automáticamente al arrancar.
CREATE OR REPLACE FUNCTION curu_prevent_historical_mutation()
RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'CURU historical records are immutable';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS curu_no_delete_users ON users;
CREATE TRIGGER curu_no_delete_users BEFORE DELETE ON users
    FOR EACH ROW EXECUTE FUNCTION curu_prevent_historical_mutation();
DROP TRIGGER IF EXISTS curu_no_truncate_users ON users;
CREATE TRIGGER curu_no_truncate_users BEFORE TRUNCATE ON users
    FOR EACH STATEMENT EXECUTE FUNCTION curu_prevent_historical_mutation();

DROP TRIGGER IF EXISTS curu_no_delete_trial_grants ON trial_grants;
CREATE TRIGGER curu_no_delete_trial_grants BEFORE DELETE ON trial_grants
    FOR EACH ROW EXECUTE FUNCTION curu_prevent_historical_mutation();
DROP TRIGGER IF EXISTS curu_no_truncate_trial_grants ON trial_grants;
CREATE TRIGGER curu_no_truncate_trial_grants BEFORE TRUNCATE ON trial_grants
    FOR EACH STATEMENT EXECUTE FUNCTION curu_prevent_historical_mutation();

DROP TRIGGER IF EXISTS curu_no_delete_reports ON reports;
CREATE TRIGGER curu_no_delete_reports BEFORE DELETE ON reports
    FOR EACH ROW EXECUTE FUNCTION curu_prevent_historical_mutation();
DROP TRIGGER IF EXISTS curu_no_truncate_reports ON reports;
CREATE TRIGGER curu_no_truncate_reports BEFORE TRUNCATE ON reports
    FOR EACH STATEMENT EXECUTE FUNCTION curu_prevent_historical_mutation();

DROP TRIGGER IF EXISTS curu_no_delete_subscriptions ON subscriptions;
CREATE TRIGGER curu_no_delete_subscriptions BEFORE DELETE ON subscriptions
    FOR EACH ROW EXECUTE FUNCTION curu_prevent_historical_mutation();
DROP TRIGGER IF EXISTS curu_no_truncate_subscriptions ON subscriptions;
CREATE TRIGGER curu_no_truncate_subscriptions BEFORE TRUNCATE ON subscriptions
    FOR EACH STATEMENT EXECUTE FUNCTION curu_prevent_historical_mutation();

DROP TRIGGER IF EXISTS curu_no_delete_payment_intents ON payment_intents;
CREATE TRIGGER curu_no_delete_payment_intents BEFORE DELETE ON payment_intents
    FOR EACH ROW EXECUTE FUNCTION curu_prevent_historical_mutation();
DROP TRIGGER IF EXISTS curu_no_truncate_payment_intents ON payment_intents;
CREATE TRIGGER curu_no_truncate_payment_intents BEFORE TRUNCATE ON payment_intents
    FOR EACH STATEMENT EXECUTE FUNCTION curu_prevent_historical_mutation();

DROP TRIGGER IF EXISTS curu_no_delete_payments ON payments;
CREATE TRIGGER curu_no_delete_payments BEFORE DELETE ON payments
    FOR EACH ROW EXECUTE FUNCTION curu_prevent_historical_mutation();
DROP TRIGGER IF EXISTS curu_no_truncate_payments ON payments;
CREATE TRIGGER curu_no_truncate_payments BEFORE TRUNCATE ON payments
    FOR EACH STATEMENT EXECUTE FUNCTION curu_prevent_historical_mutation();

DROP TRIGGER IF EXISTS curu_no_delete_report_deliveries ON report_deliveries;
CREATE TRIGGER curu_no_delete_report_deliveries BEFORE DELETE ON report_deliveries
    FOR EACH ROW EXECUTE FUNCTION curu_prevent_historical_mutation();
DROP TRIGGER IF EXISTS curu_no_truncate_report_deliveries ON report_deliveries;
CREATE TRIGGER curu_no_truncate_report_deliveries BEFORE TRUNCATE ON report_deliveries
    FOR EACH STATEMENT EXECUTE FUNCTION curu_prevent_historical_mutation();

DROP TRIGGER IF EXISTS curu_no_delete_webhook_events ON webhook_events;
CREATE TRIGGER curu_no_delete_webhook_events BEFORE DELETE ON webhook_events
    FOR EACH ROW EXECUTE FUNCTION curu_prevent_historical_mutation();
DROP TRIGGER IF EXISTS curu_no_truncate_webhook_events ON webhook_events;
CREATE TRIGGER curu_no_truncate_webhook_events BEFORE TRUNCATE ON webhook_events
    FOR EACH STATEMENT EXECUTE FUNCTION curu_prevent_historical_mutation();

DROP TRIGGER IF EXISTS curu_no_delete_audit_events ON audit_events;
CREATE TRIGGER curu_no_delete_audit_events BEFORE DELETE ON audit_events
    FOR EACH ROW EXECUTE FUNCTION curu_prevent_historical_mutation();
DROP TRIGGER IF EXISTS curu_no_truncate_audit_events ON audit_events;
CREATE TRIGGER curu_no_truncate_audit_events BEFORE TRUNCATE ON audit_events
    FOR EACH STATEMENT EXECUTE FUNCTION curu_prevent_historical_mutation();
