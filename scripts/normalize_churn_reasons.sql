-- normalize_churn_reasons.sql
-- One-time migration: maps free-text churn_reason values produced before
-- pipeline-side normalization was added to the five canonical labels.
--
-- Run against bankretaindb via Azure Data Studio (Entra auth) or sqlcmd with
-- the Entra token approach used in pipeline.py.
--
-- Safe to re-run: WHERE clause skips rows already in the canonical set.

DECLARE @tables TABLE (tbl NVARCHAR(100));
INSERT INTO @tables VALUES ('dbo.approved_outreach'), ('dbo.compliance_review_queue');

-- Preview what will change before committing
SELECT tbl, churn_reason, COUNT(*) AS cnt
FROM (
    SELECT 'approved_outreach' AS tbl, churn_reason FROM dbo.approved_outreach
    UNION ALL
    SELECT 'compliance_review_queue',  churn_reason FROM dbo.compliance_review_queue
) x
WHERE churn_reason NOT IN (
    'price_sensitivity', 'service_dissatisfaction',
    'product_lifecycle',  'inactivity', 'unknown'
)
GROUP BY tbl, churn_reason
ORDER BY tbl, cnt DESC;

-- ── Normalise approved_outreach ───────────────────────────────────────────────

UPDATE dbo.approved_outreach
SET churn_reason =
    CASE
        WHEN LOWER(churn_reason) IN (
                'price_sensitivity', 'service_dissatisfaction',
                'product_lifecycle',  'inactivity', 'unknown')
            THEN LOWER(churn_reason)
        -- service_dissatisfaction (check before inactivity to avoid "service inactivity" edge case)
        WHEN LOWER(churn_reason) LIKE '%complaint%'
          OR LOWER(churn_reason) LIKE '%incident%'
          OR LOWER(churn_reason) LIKE '%nps%'
            THEN 'service_dissatisfaction'
        -- product_lifecycle
        WHEN LOWER(churn_reason) LIKE '%lifecycle%'
          OR LOWER(churn_reason) LIKE '%rate%reset%'
          OR LOWER(churn_reason) LIKE '%mortgage%'
            THEN 'product_lifecycle'
        -- price_sensitivity
        WHEN LOWER(churn_reason) LIKE '%price%'
          OR LOWER(churn_reason) LIKE '%competitor%'
          OR LOWER(churn_reason) LIKE '%fee%'
          OR LOWER(churn_reason) LIKE '%salary%'
            THEN 'price_sensitivity'
        -- inactivity (largest catch-all bucket)
        WHEN LOWER(churn_reason) LIKE '%inactiv%'
          OR LOWER(churn_reason) LIKE '%dormant%'
          OR LOWER(churn_reason) LIKE '%dormancy%'
          OR LOWER(churn_reason) LIKE '%disengag%'
          OR LOWER(churn_reason) LIKE '%engagement%'
            THEN 'inactivity'
        ELSE 'unknown'
    END
WHERE churn_reason NOT IN (
    'price_sensitivity', 'service_dissatisfaction',
    'product_lifecycle',  'inactivity', 'unknown'
);

-- ── Normalise compliance_review_queue ─────────────────────────────────────────

UPDATE dbo.compliance_review_queue
SET churn_reason =
    CASE
        WHEN LOWER(churn_reason) IN (
                'price_sensitivity', 'service_dissatisfaction',
                'product_lifecycle',  'inactivity', 'unknown')
            THEN LOWER(churn_reason)
        WHEN LOWER(churn_reason) LIKE '%complaint%'
          OR LOWER(churn_reason) LIKE '%incident%'
          OR LOWER(churn_reason) LIKE '%nps%'
            THEN 'service_dissatisfaction'
        WHEN LOWER(churn_reason) LIKE '%lifecycle%'
          OR LOWER(churn_reason) LIKE '%rate%reset%'
          OR LOWER(churn_reason) LIKE '%mortgage%'
            THEN 'product_lifecycle'
        WHEN LOWER(churn_reason) LIKE '%price%'
          OR LOWER(churn_reason) LIKE '%competitor%'
          OR LOWER(churn_reason) LIKE '%fee%'
          OR LOWER(churn_reason) LIKE '%salary%'
            THEN 'price_sensitivity'
        WHEN LOWER(churn_reason) LIKE '%inactiv%'
          OR LOWER(churn_reason) LIKE '%dormant%'
          OR LOWER(churn_reason) LIKE '%dormancy%'
          OR LOWER(churn_reason) LIKE '%disengag%'
          OR LOWER(churn_reason) LIKE '%engagement%'
            THEN 'inactivity'
        ELSE 'unknown'
    END
WHERE churn_reason NOT IN (
    'price_sensitivity', 'service_dissatisfaction',
    'product_lifecycle',  'inactivity', 'unknown'
);

-- Verify — should return 0 rows after migration
SELECT 'approved_outreach' AS tbl, churn_reason, COUNT(*) AS cnt
FROM dbo.approved_outreach
WHERE churn_reason NOT IN (
    'price_sensitivity', 'service_dissatisfaction',
    'product_lifecycle',  'inactivity', 'unknown'
)
GROUP BY churn_reason
UNION ALL
SELECT 'compliance_review_queue', churn_reason, COUNT(*)
FROM dbo.compliance_review_queue
WHERE churn_reason NOT IN (
    'price_sensitivity', 'service_dissatisfaction',
    'product_lifecycle',  'inactivity', 'unknown'
)
GROUP BY churn_reason;
