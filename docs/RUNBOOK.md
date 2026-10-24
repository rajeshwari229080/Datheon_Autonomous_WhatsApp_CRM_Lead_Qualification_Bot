# Datheon WhatsApp AI Platform
## Operational Runbook & Incident Response Guide

### 1. System Health & Observability
- **Liveness Probe**: `GET /health/live` (Returns HTTP 200 `{"status": "alive"}`).
- **Readiness Probe**: `GET /health/ready` (Returns HTTP 200 with database, LLM, calendar, and CRM connection statuses).
- **Prometheus Metrics**: `GET /metrics` (Exposes counters for `webhooks_received_total`, `webhook_auth_failures_total`, `idempotent_duplicate_events_total`, `leads_qualified_total`, `bookings_confirmed_total`, `human_escalations_total`).

---

### 2. Common Alert Response Procedures

#### Alert A: Webhook Authentication Failure Spike (`webhook_auth_failures_total`)
- **Symptoms**: Inbound webhooks from Meta returning HTTP 401 Unauthorized.
- **Root Cause**: The configured `WHATSAPP_APP_SECRET` does not match the Meta App Secret in Meta App Dashboard -> Basic Settings.
- **Remediation**:
  1. Verify the App Secret in Meta App Dashboard.
  2. Update `WHATSAPP_APP_SECRET` in environment variables or secret manager.
  3. Verify that reverse proxies or cloud load balancers are not stripping or altering the raw request body before HMAC verification.
  4. Perform test POST with `generate_hub_signature`.

#### Alert B: Calendar Slot Collision / Race Conditions (`SlotUnavailableError`)
- **Symptoms**: Customer selects a slot that was claimed by another party before confirmation.
- **System Behavior**: The platform automatically rejects duplicate double booking, preserves database integrity, fetches fresh available slots, and messages the customer with updated options.
- **Remediation**: Verify calendar provider API rate limits and buffer settings (`MEETING_BUFFER_MINUTES`).

#### Alert C: CRM Sync Failure Alert (`CRMSyncStatus.FAILED`)
- **Symptoms**: Calendar booking is confirmed locally, but Airtable / external CRM returned 5xx or timed out.
- **System Behavior**: The booking is recorded locally with `crm_sync_status = FAILED` and `crm_sync_error`. The customer's booking is NOT cancelled.
- **Remediation**:
  1. Trigger reconciliation worker: `await booking_service.reconcile_pending_crm_syncs()`.
  2. Check CRM API key permissions and table field schemas.

---

### 3. Human Escalation Management
- **Dashboard / API**: `GET /api/v1/escalations` lists all pending human handoff incidents.
- **Resolution**: `POST /api/v1/escalations/{conversation_id}/resolve`
  ```json
  {
    "agent_name": "Sales Rep Name",
    "resolution_notes": "Spoke on phone and answered custom contract questions.",
    "resume_automation": true
  }
  ```
  - `resume_automation = true`: Resumes autonomous WhatsApp bot in `QUALIFICATION` stage.
  - `resume_automation = false`: Closes conversation permanently (`CLOSED` stage).

---

### 4. Secret & Token Rotation
1. **WhatsApp Verify Token**:
   - Update in Meta Dashboard Webhooks -> Verify Token.
   - Update `WHATSAPP_VERIFY_TOKEN` in `.env` or secret manager.
2. **Meta App Secret**:
   - Regenerate in Meta Dashboard.
   - Update `WHATSAPP_APP_SECRET`.
3. **WhatsApp System User Permanent Access Token**:
   - Generate in Meta Business Manager -> System Users.
   - Update `WHATSAPP_ACCESS_TOKEN`.
