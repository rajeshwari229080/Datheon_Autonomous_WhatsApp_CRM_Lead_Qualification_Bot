# Datheon WhatsApp AI Platform
## Threat Model & Risk Management Register

### 1. Risk Matrix Overview
The following risk register covers all 14 mandatory operational and security threat vectors identified in Section 5 of the architectural charter.

| ID | Threat / Failure Vector | Probability | Impact | Mitigation Strategy | Verification / Test Case |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **R-01** | Forged Webhook Requests | High | Critical | Meta HMAC-SHA256 signature verification over raw request body using App Secret; constant-time comparison. | `tests/unit/test_webhook_security.py::test_webhook_forged_signature_rejected` |
| **R-02** | Replay Attacks & Duplicate Delivery | High | High | Message provider ID uniqueness constraint in database; idempotent processing lock. | `tests/unit/test_webhook_security.py::test_replay_duplicate_delivery_idempotent` |
| **R-03** | Prompt Injection & System Overrides | High | Critical | Delimiter-based input fencing, strict system role pinning, schema-constrained output, and rule verification. | `tests/unit/test_qualification.py::test_prompt_injection_defense` |
| **R-04** | Cross-Customer Data Leakage | Low | Critical | Strict conversation scoping by authenticated WhatsApp phone ID (`wa_id`); isolated session context. | `tests/unit/test_webhook_security.py::test_cross_customer_isolation` |
| **R-05** | Incorrect LLM Extraction / Hallucination | Medium | High | Deterministic business rules engine decoupled from LLM confidence; strict Pydantic schema validation. | `tests/unit/test_qualification.py::test_hallucination_and_missing_fields` |
| **R-06** | Unauthorized Calendar Booking | Medium | High | Two-phase booking requirement; mandatory customer confirmation token and qualification state gate. | `tests/unit/test_booking.py::test_unqualified_cannot_book` |
| **R-07** | Double Booking & Concurrent Race Conditions | Medium | High | Re-checking calendar slot availability immediately before lock; database transaction locking. | `tests/unit/test_booking.py::test_concurrent_slot_race_condition` |
| **R-08** | Calendar / CRM Partial Failures | Medium | Medium | Transactional boundary: local booking committed with `CRM_PENDING`; asynchronous reconciliation worker. | `tests/unit/test_booking.py::test_crm_partial_failure_reconciliation` |
| **R-09** | Secret Leakage via Logs or Repositories | Medium | Critical | PII and token scrubbing in structured JSON logger; strict `.gitignore` and `.env.example` sanitization. | `tests/unit/test_logging_security.py::test_secrets_not_logged` |
| **R-10** | WhatsApp API Rate Limits & Delivery Failures | High | Medium | Bounded exponential backoff with jitter; dead-letter queue persistence for exhausted retries. | `tests/unit/test_webhook_security.py::test_dead_letter_on_failure` |
| **R-11** | Frustrated Customers Trapped in Automation | High | High | Multi-signal frustration detection (sentiment, anger keywords, loop detection); immediate bot silence. | `tests/unit/test_escalation.py::test_frustrated_customer_immediate_silence` |
| **R-12** | Unbounded Retries or Resource Exhaustion | Medium | Medium | Fixed max-retry limit (3 attempts), timeout thresholds (10s on HTTPX), and memory circuit breakers. | `tests/unit/test_webhook_security.py::test_circuit_breaker_and_timeout` |
| **R-13** | Personal Data Retention & Compliance | Low | Medium | Configurable data retention policies and lead record anonymization routines for GDPR/CCPA. | `tests/unit/test_data_privacy.py::test_data_anonymization` |
| **R-14** | Deployment Misconfiguration & Missing Keys | High | High | Strict Pydantic-settings startup validation; fast-fail health checks with detailed diagnostic logging. | `tests/unit/test_config.py::test_missing_mandatory_config_fails_fast` |

---

### 2. Residual Risks & Operational Boundaries
- **Network Partitions with Meta**: If Meta's Cloud API is down or unreachable, webhooks queued by Meta will arrive out of order upon recovery. The idempotency and timestamp ordering mechanisms handle this safely.
- **Provider Key Revocation**: When calendar or CRM credentials expire, the system transitions to degraded mode, halts automated booking, records pending bookings locally, and alerts the engineering team.
