-- CURU SIGNAL AI: migración 002 - órdenes y pagos multi-moneda.
-- Ejecutar una sola vez sobre PostgreSQL existente antes de desplegar el código nuevo.
ALTER TABLE payment_intents
    ADD COLUMN IF NOT EXISTS expected_amount NUMERIC(18, 6),
    ADD COLUMN IF NOT EXISTS expected_currency VARCHAR(3);

ALTER TABLE payments
    ADD COLUMN IF NOT EXISTS amount NUMERIC(18, 6);

-- Conserva todas las órdenes/pagos históricos como COP sin alterar su importe.
UPDATE payment_intents
SET expected_amount = expected_amount_cop,
    expected_currency = 'COP'
WHERE expected_amount IS NULL;

UPDATE payments
SET amount = amount_cop
WHERE amount IS NULL;
