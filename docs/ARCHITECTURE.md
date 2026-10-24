# Datheon WhatsApp AI Lead Qualification, Automated Booking & Human Escalation Platform
## Technical Architecture Specification

### 1. Executive Summary
The Datheon Platform is an enterprise-grade asynchronous backend service designed to automate inbound WhatsApp conversations for high-value business lead qualification, autonomous demonstration booking, CRM synchronization, and intelligent human escalation.

The system uses a layered clean architecture governed by SOLID principles, strict typing with Pydantic V2, asynchronous I/O with FastAPI and SQLAlchemy 2.0, cryptographic request verification, and stateful conversation lifecycle management.

---

### 2. System Architecture Diagram

```mermaid
flowchart TB
    subgraph Client["External Clients & Networks"]
        Meta[Meta WhatsApp Cloud API]
        Agent[Human Sales Agent]
    end

    subgraph Security["Edge & Security Layer"]
        HMAC[HMAC-SHA256 Request Verifier]
        RateLimit[Rate Limiter & Replay Guard]
        CorrID[Correlation ID Middleware]
    end

    subgraph Ingestion["API Routing & Ingestion"]
        WebhookRoute["/api/v1/whatsapp/webhook"]
        AdminRoute["/api/v1/escalations"]
        HealthRoute["/health & /metrics"]
    end

    subgraph Orchestration["Service & Orchestration Layer"]
        ConvService[Conversation State Manager]
        StateMachine[Conversation State Machine]
        FrustEngine[Frustration & Escalation Engine]
        QualService[Structured Lead Qualification Service]
        BookService[Two-Phase Booking Coordinator]
    end

    subgraph Adapters["Integration Layer (Pluggable)"]
        LLMAdapter[LLM Adapter: Ollama / OpenAI / Gemini / Mock]
        CalAdapter[Calendar Adapter: Google / Cal.com / Mock]
        CRMAdapter[CRM Adapter: Airtable / Webhook / Mock]
        NotifyAdapter[Notification Adapter: Slack / Webhook / Mock]
    end

    subgraph Persistence["Storage & State Store"]
        DB[(SQLAlchemy Async: SQLite / PostgreSQL)]
        AuditLog[(Audit & Dead-Letter Logs)]
    end

    Meta -->|POST Webhook + Signature| CorrID
    CorrID --> HMAC
    HMAC --> RateLimit
    RateLimit --> WebhookRoute
    WebhookRoute -->|Fast Ack 200 OK| Meta
    WebhookRoute --> ConvService

    ConvService <--> StateMachine
    ConvService <--> DB
    ConvService --> FrustEngine

    FrustEngine -->|Escalate| NotifyAdapter
    FrustEngine -->|Continue| QualService
    NotifyAdapter --> Agent

    QualService <--> LLMAdapter
    QualService -->|Qualified| BookService

    BookService <--> CalAdapter
    BookService <--> CRMAdapter
    BookService --> DB

    AdminRoute <--> ConvService
    AdminRoute <--> AuditLog
```

---

### 3. Core Architectural Principles
1. **Separation of Concerns**: Clean layers separating routing (`api/`), business services (`services/`), database repositories (`db/`), schemas (`schemas/`), and third-party integrations (`integrations/`).
2. **Cryptographic Integrity**: Every inbound POST webhook is cryptographically authenticated using HMAC-SHA256 against Meta's App Secret before any processing occurs.
3. **Idempotency & Replay Protection**: Message identifiers (`wamid.xxx`) are deduplicated with database uniqueness constraints to ensure duplicate delivery from Meta never causes duplicate AI responses or multiple bookings.
4. **State Machine Integrity**: Conversations strictly transition through legal stages (`NEW -> GREETING -> QUALIFICATION -> QUALIFIED -> BOOKING -> BOOKED -> HUMAN_HANDOFF -> CLOSED`). State survives application restarts.
5. **Prompt Injection Defense**: Untrusted customer input is strictly delimited and filtered. LLM outputs are parsed into strict Pydantic models. Any model hallucination or deviation is caught and safely recovered.
6. **Two-Phase Booking**: Time slots are verified for availability before presentation, and re-verified immediately before booking to eliminate calendar race conditions.
7. **Immediate Escalation Cessation**: Upon escalation detection (frustration keywords, negative sentiment loop, or direct human request), autonomous bot replies halt immediately, preserving conversation history and alerting human staff.

---

### 4. Conversation State Machine Lifecycle

```mermaid
stateDiagram-v2
    [*] --> NEW: First Inbound Message
    NEW --> GREETING: Initial Welcome Sent
    GREETING --> QUALIFICATION: Customer Inquires / Responds
    QUALIFICATION --> QUALIFICATION: Asking Follow-up Question (One at a time)
    QUALIFICATION --> QUALIFIED: Budget, Size, Urgency Met
    QUALIFICATION --> NOT_QUALIFIED: Does Not Meet ICP Criteria
    QUALIFIED --> BOOKING: Available Slots Offered
    BOOKING --> BOOKING: Slot Selected / Awaiting Confirmation
    BOOKING --> BOOKED: Slot Confirmed & Calendar Booked
    BOOKED --> CLOSED: Follow-up Complete
    NOT_QUALIFIED --> CLOSED: Polite Rejection Sent

    NEW --> HUMAN_HANDOFF: Frustration / Explicit Human Request
    GREETING --> HUMAN_HANDOFF: Frustration / Explicit Human Request
    QUALIFICATION --> HUMAN_HANDOFF: Frustration / Explicit Human Request
    BOOKING --> HUMAN_HANDOFF: Frustration / Explicit Human Request

    HUMAN_HANDOFF --> CLOSED: Agent Resolves Issue
```
