# CGC Security Guide

This guide explains how to secure your CGC installation, especially when exposing it to the internet.

---

## Table of Contents

- [Security Overview](#security-overview)
- [Quick Start: Secure Setup](#quick-start-secure-setup)
- [API Key Management](#api-key-management)
- [Rate Limiting](#rate-limiting)
- [Data Protection](#data-protection)
- [Network Security](#network-security)
- [Best Practices](#best-practices)
- [Security Configuration](#security-configuration)

---

## Security Overview

CGC includes multiple layers of security:

| Layer | What it protects against |
|-------|-------------------------|
| API Keys | Unauthorized access |
| Rate Limiting | Abuse and denial of service |
| SQL Validation | SQL injection attacks |
| Path Validation | Directory traversal attacks |
| Security Headers | XSS, clickjacking, MIME sniffing |

### When to Enable Security

| Scenario | Security Level |
|----------|---------------|
| Local testing only | Optional |
| Local network/team use | Recommended |
| Internet access (ngrok, etc.) | **Required** |
| Production deployment | **Required** |

---

## Quick Start: Secure Setup

### Step 1: Start the Secure Server

The secure server has all protections enabled by default:

```
cgc serve --secure
```

You'll see:
```
Starting secure CGC API server on 127.0.0.1:8420
Authentication: REQUIRED
Rate limiting: ENABLED
```

### Step 2: Create Your First API Key

Since authentication is required, you need to create a key first. Temporarily disable auth:

**Windows (Command Prompt):**
```
set CGC_REQUIRE_AUTH=false
cgc serve --secure
```

**Windows (PowerShell):**
```
$env:CGC_REQUIRE_AUTH = "false"
cgc serve --secure
```

**Mac/Linux:**
```
CGC_REQUIRE_AUTH=false cgc serve --secure
```

### Step 3: Create an Admin Key

With the server running, open your browser to:
```
http://localhost:8420/docs
```

Find the `POST /admin/api-keys` endpoint and click "Try it out".

Fill in:
- **name**: `admin` (or your preferred name)
- **permissions**: `*,admin` (full access including admin)
- **expires_days**: `365` (or leave blank for no expiration)

Click "Execute".

**Important:** Copy the API key from the response! It looks like:
```
cgc_lGlmobBzC2ReZZZq...
```

This key is only shown once. Save it somewhere safe!

### Step 4: Restart with Authentication

Stop the server (Ctrl+C) and restart normally:

```
cgc serve --secure
```

### Step 5: Test Your Key

Try accessing the API with your key:

```
curl -H "X-API-Key: cgc_your_key_here" http://localhost:8420/sources
```

You should see a list of sources (empty if none connected yet).

Without the key:
```
curl http://localhost:8420/sources
```

You'll get an authentication error.

---

## API Key Management

### Creating Keys

Keys can have different permission levels:

**Full Access (Admin):**
```
permissions: *,admin
```

**Read Only:**
```
permissions: read
```

**SQL Only (no file access):**
```
permissions: sql:read
```

**Specific Sources:**
```
allowed_sources: mydb,documents
```

### Key Properties

| Property | Description |
|----------|-------------|
| name | Human-readable identifier |
| permissions | What the key can do |
| expires_days | When the key expires (optional) |
| allowed_sources | Which sources the key can access |

### Revoking Keys

If a key is compromised:

1. Go to `http://localhost:8420/docs`
2. Use the admin endpoints to list and revoke keys
3. Create new keys for affected users

### Key Security Tips

- **Never share keys** in code repositories or public places
- **Use environment variables** instead of hardcoding keys
- **Create separate keys** for each user or application
- **Set expiration dates** for temporary access
- **Regularly rotate** keys for sensitive applications

---

## Rate Limiting

Rate limiting prevents abuse by limiting how many requests can be made.

### Default Limits

| Setting | Default | Description |
|---------|---------|-------------|
| Requests per window | 100 | Maximum requests allowed |
| Window size | 60 seconds | Time period for counting |

This means: 100 requests per minute per IP address.

### Rate Limit Headers

Every response includes these headers:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1705312800
```

- **Limit**: Maximum requests in the window
- **Remaining**: Requests left in current window
- **Reset**: Unix timestamp when the window resets

### When Rate Limited

If you exceed the limit, you'll receive:

```
HTTP 429 Too Many Requests

{
  "error": "Rate limit exceeded",
  "message": "Too many requests. Limit: 100 per 60s"
}
```

The response includes a `Retry-After` header telling you when to try again.

### Customizing Rate Limits

Set via environment variables:

```
CGC_RATE_LIMIT_REQUESTS=200
CGC_RATE_LIMIT_WINDOW=60
```

Or in the config file (`~/.cgc/security.json`):

```json
{
  "rate_limit_enabled": true,
  "rate_limit_requests": 200,
  "rate_limit_window_seconds": 60
}
```

### Per-Key Rate Limits

Different API keys can have different limits:

```json
{
  "name": "high-volume-client",
  "rate_limit": 1000
}
```

---

## Data Protection

### SQL Injection Protection

CGC blocks dangerous SQL keywords by default:

**Blocked:**
- DROP, DELETE, TRUNCATE
- ALTER, CREATE
- INSERT, UPDATE
- GRANT, REVOKE
- EXEC, EXECUTE
- Comments (--, /*, */)

**Allowed:**
- SELECT queries only

If you need write access, grant `sql:write` permission to specific keys.

### Path Traversal Protection

CGC blocks access to sensitive paths:

**Always Blocked:**
- System directories (`/etc`, `/var`, `C:\Windows`)
- Home directories (`/home`, `C:\Users`)
- Hidden files (`.env`, `.git`, `.ssh`)
- Credential files (`id_rsa`, `credentials`, `secrets`)

**Allowed Paths:**

By default, any path not on the blocked list is allowed. For stricter control, set allowed paths:

```json
{
  "allowed_paths": [
    "C:\\Data\\Reports",
    "C:\\Data\\Documents"
  ]
}
```

### Credential Masking

Sensitive information is automatically masked in logs and error messages:

```
Before: Connection failed: postgresql://admin:secret123@localhost/db
After:  Connection failed: postgresql://admin:****@localhost/db
```

---

## Network Security

### Binding to Localhost

By default, CGC only accepts connections from your local machine:

```
bind_host: 127.0.0.1
```

This means other computers on your network can't access it.

### Allowing Network Access

To allow access from other machines:

**Local Network:**
```
CGC_BIND_HOST=0.0.0.0 cgc serve --secure
```

**Caution:** This exposes CGC to your entire network.

### Using ngrok

For internet access, use ngrok:

1. **Install ngrok** from https://ngrok.com

2. **Start CGC** with security enabled:
   ```
   cgc serve --secure
   ```

3. **Start ngrok**:
   ```
   ngrok http 8420
   ```

4. **Use the ngrok URL** (like `https://abc123.ngrok.io`)

**Important:** Always use the secure server when exposing to the internet!

### CORS Configuration

By default, only localhost origins are allowed:

```json
{
  "allowed_origins": ["http://localhost:*"]
}
```

To allow specific domains:

```json
{
  "allowed_origins": [
    "https://your-app.com",
    "https://n8n.your-company.com"
  ]
}
```

**Never use `*` in production!** This allows any website to access your API.

---

## Best Practices

### For Local Development

1. Use `cgc serve` (without security) for quick testing
2. Use `cgc serve --secure` when testing security features
3. Create a dedicated development API key

### For Team/Office Use

1. Always use `cgc serve --secure`
2. Create separate keys for each team member
3. Use permission restrictions based on role
4. Set key expiration (e.g., 30-90 days)

### For Internet Exposure

1. **Always** use `cgc serve --secure`
2. Use strong, unique API keys
3. Set up ngrok with authentication if possible
4. Monitor access logs regularly
5. Set aggressive rate limits
6. Restrict allowed paths strictly
7. Consider a VPN instead of public exposure

### For Production

1. Run behind a reverse proxy (nginx, traefik)
2. Use HTTPS (the proxy handles SSL)
3. Implement IP whitelisting if possible
4. Set up log aggregation and alerting
5. Regular security audits
6. Keep CGC updated

---

## Security Configuration

### Configuration File

Create `~/.cgc/security.json`:

```json
{
  "require_auth": true,
  "api_keys_file": "~/.cgc/api_keys.json",

  "rate_limit_enabled": true,
  "rate_limit_requests": 100,
  "rate_limit_window_seconds": 60,

  "allow_raw_sql": false,
  "sql_max_rows": 10000,
  "sql_timeout_seconds": 30,
  "blocked_sql_keywords": [
    "DROP", "DELETE", "TRUNCATE", "ALTER", "CREATE",
    "INSERT", "UPDATE", "GRANT", "REVOKE", "EXEC"
  ],

  "allowed_paths": [],
  "blocked_paths": [
    "/etc", "/var", "/root", "/home",
    "C:\\Windows", "C:\\Program Files",
    ".env", ".git", ".ssh", "credentials", "secrets"
  ],
  "max_file_size_mb": 100,

  "allowed_origins": ["http://localhost:*"],
  "bind_host": "127.0.0.1",
  "bind_port": 8420,

  "max_request_size_mb": 10,
  "request_timeout_seconds": 60,

  "log_requests": true,
  "log_queries": true,
  "mask_credentials": true
}
```

### Environment Variables

All settings can be overridden with environment variables:

| Variable | Description |
|----------|-------------|
| `CGC_REQUIRE_AUTH` | Require API keys (true/false) |
| `CGC_BIND_HOST` | Server IP address |
| `CGC_BIND_PORT` | Server port |
| `CGC_RATE_LIMIT_ENABLED` | Enable rate limiting |
| `CGC_RATE_LIMIT_REQUESTS` | Requests per window |
| `CGC_RATE_LIMIT_WINDOW` | Window size in seconds |
| `CGC_ALLOW_RAW_SQL` | Allow non-SELECT queries |
| `CGC_SQL_MAX_ROWS` | Maximum result rows |
| `CGC_ALLOWED_PATHS` | Comma-separated allowed paths |
| `CGC_BLOCKED_PATHS` | Comma-separated blocked paths |
| `CGC_ALLOWED_ORIGINS` | Comma-separated CORS origins |
| `CGC_LOG_REQUESTS` | Log all requests |
| `CGC_LOG_QUERIES` | Log SQL queries |

---

## Incident Response

### If an API Key is Compromised

1. **Immediately revoke** the compromised key
2. **Create a new key** for the affected user
3. **Review access logs** for suspicious activity
4. **Change any credentials** the key had access to

### If You See Suspicious Activity

1. **Check rate limit logs** for unusual patterns
2. **Review blocked requests** (SQL injection attempts, etc.)
3. **Temporarily increase** rate limiting if under attack
4. **Consider IP blocking** at the network level

### Security Updates

- Watch for CGC updates that address security issues
- Apply security patches promptly
- Review the changelog for security-related changes

---

## Next Steps

- [API Reference](API.md) - Detailed endpoint documentation
- [CLI Reference](CLI.md) - Command-line usage
- [Technical Overview](TECHNICAL.md) - How CGC works
