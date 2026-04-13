# Authentication System — Data Flow

## Overview

Stateless JWT-based auth using **Supabase Auth** as the identity provider. Application roles, tenant isolation, and session management are handled by the backend and frontend layers.

## Authentication Flow

```mermaid
sequenceDiagram
    participant U as User (Browser)
    participant F as Frontend (React)
    participant B as Backend (FastAPI)
    participant S as Supabase Auth
    participant DB as PostgreSQL

    %% ── Login Flow ──
    rect rgb(240, 248, 255)
    Note over U,DB: Login Flow
    U->>F: Enter email + password
    F->>B: POST /auth/login {email, password}
    B->>DB: Check AdminUser exists & not locked
    alt Account locked (5 failures, 15-min window)
        B-->>F: 401 Account locked
        F-->>U: Show error
    end
    B->>S: POST /auth/v1/token?grant_type=password
    S-->>B: {access_token, refresh_token, expires_in}
    B->>DB: Reset failed_login_count, update last_login_at
    B-->>F: TokenResponse {access_token, refresh_token}
    F->>F: Store tokens in localStorage
    F->>B: GET /auth/me (Bearer token)
    B->>B: Validate JWT (see below)
    B->>DB: Load AdminUser (role, tenant_id)
    B-->>F: {id, email, role, tenant_id, tenant_name}
    F->>F: Set AuthContext (user, isAuthenticated)
    F-->>U: Redirect to dashboard
    end

    %% ── Authenticated Request ──
    rect rgb(245, 255, 245)
    Note over U,DB: Authenticated API Request
    U->>F: Interact with UI
    F->>B: API request + Bearer token + X-Tenant-Id header
    B->>B: Extract JWT from Authorization header
    B->>S: Fetch JWKS (cached) from /auth/v1/.well-known/jwks.json
    B->>B: Verify JWT signature (ES256/HS256), audience, expiry
    B->>DB: Load AdminUser by sub claim (UUID)
    B->>B: Check is_active, require_role()
    B->>B: Resolve tenant (user.tenant_id or X-Tenant-Id)
    B-->>F: API response
    end

    %% ── Token Refresh ──
    rect rgb(255, 248, 240)
    Note over U,DB: Token Refresh (on 401)
    F->>B: API request → 401 Unauthorized
    F->>F: Axios interceptor catches 401
    F->>B: POST /auth/refresh {refresh_token}
    B->>S: POST /auth/v1/token?grant_type=refresh_token
    S-->>B: New {access_token, refresh_token}
    B-->>F: New TokenResponse
    F->>F: Update localStorage tokens
    F->>B: Retry original request with new token
    B-->>F: Success response
    end

    %% ── Password Reset ──
    rect rgb(255, 245, 245)
    Note over U,S: Password Reset
    U->>F: Request password reset
    F->>B: POST /auth/reset-password {email}
    B->>S: POST /auth/v1/recover {email}
    B-->>F: 200 OK (always, prevents enumeration)
    S-->>U: Reset email with link
    end
```

## JWT Validation Flow

```mermaid
flowchart TD
    A[Incoming Request] --> B{Authorization header?}
    B -->|No| Z[401 Not Authenticated]
    B -->|Yes| C[Extract Bearer token]
    C --> D{Check JWT algorithm}
    D -->|ES256| E[Fetch JWKS from Supabase]
    E --> F[Match key by kid]
    F --> G[Construct RSA/EC public key]
    G --> H[Decode & verify JWT]
    D -->|HS256| I[Use supabase_jwt_secret]
    I --> H
    H --> J{Token valid?}
    J -->|No| Z
    J -->|Yes| K[Extract user_id from sub claim]
    K --> L[Load AdminUser from DB]
    L --> M{User active?}
    M -->|No| Z
    M -->|Yes| N{Role sufficient?}
    N -->|No| Y[403 Forbidden]
    N -->|Yes| O[Request proceeds]
```

## Multi-Tenant Context Resolution

```mermaid
flowchart TD
    A[Authenticated User] --> B{user.tenant_id?}
    B -->|Not NULL| C[Regular User]
    C --> D[Load tenant by user.tenant_id]
    D --> E{Tenant active?}
    E -->|No| F[403 Tenant inactive]
    E -->|Yes| G{Tenant paused?}
    G -->|Yes| H[403 Tenant paused]
    G -->|No| I[Request proceeds with tenant context]

    B -->|NULL| J[Super Admin]
    J --> K{X-Tenant-Id header?}
    K -->|No| L[403 Must specify tenant]
    K -->|Yes| M[Load tenant by header UUID]
    M --> N{Tenant exists?}
    N -->|No| O[404 Tenant not found]
    N -->|Yes| I
```

## Role Hierarchy

```mermaid
flowchart LR
    STAFF["STAFF (0)"] --> MANAGER["MANAGER (1)"]
    MANAGER --> OWNER["OWNER (2)"]
    OWNER --> SUPER_ADMIN["SUPER_ADMIN (3)"]

    style STAFF fill:#e8e8e8
    style MANAGER fill:#bde0fe
    style OWNER fill:#a2d2ff
    style SUPER_ADMIN fill:#ffd6a5
```

| Role | Scope | Capabilities |
|------|-------|-------------|
| STAFF | Own tenant | Read-only access |
| MANAGER | Own tenant | CRUD customers, bookings, settings |
| OWNER | Own tenant | All of MANAGER + manage admin users, update settings |
| SUPER_ADMIN | All tenants | All of OWNER + create/manage tenants, cross-tenant dashboard |

## Frontend Token Management

```mermaid
flowchart TD
    A[App Mount] --> B{Tokens in localStorage?}
    B -->|No| C[Show Login page]
    B -->|Yes| D[Decode JWT payload]
    D --> E[Set initial user from JWT]
    E --> F[GET /auth/me for full profile]
    F -->|Success| G[AuthContext ready]
    F -->|401| H[Trigger refresh]
    H -->|Success| F
    H -->|Fail| I[Clear tokens → Login page]

    G --> J[API Request]
    J --> K{Response 401?}
    K -->|No| L[Return response]
    K -->|Yes| M{Already retried?}
    M -->|Yes| I
    M -->|No| N[refreshAccessToken]
    N -->|Success| O[Retry with new token]
    N -->|Fail| I
    O --> L

    style I fill:#ffcccc
    style G fill:#ccffcc
```

## Security Features

- **Account Lockout**: 5 failed login attempts → 15-minute lockout
- **Rate Limiting**: Auth endpoints (login, refresh, reset) are rate-limited
- **Refresh Deduplication**: Single in-flight refresh promise prevents race conditions
- **Email Enumeration Prevention**: Login errors are generic; password reset always returns 200
- **Audience Validation**: JWT `aud` must be "authenticated"
- **Tenant Isolation**: Row-level filtering by tenant_id on every query
- **Stateless Sessions**: No server-side session store; tokens valid until expiry
