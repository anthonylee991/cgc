# CGC Site Builder Instructions

Instructions for the site-builder agent on how to implement licensing, tokens, and tier tracking for the CGC website (cgc.dev).

---

## Overview

CGC uses a three-tier licensing model:
- **Free** -- no account needed, context extension features only
- **Trial** -- automatic 14-day trial, full extraction access, tracked locally on the user's machine
- **Pro** -- paid license, cloud extraction, validated against Supabase

The website needs to handle: selling Pro licenses, generating tokens, and providing users with their license keys.

---

## Supabase Schema

CGC licenses are stored in the existing Supabase `purchases` table (shared with BotSight and Orunla).

### Relevant Columns

| Column | Type | Description |
|--------|------|-------------|
| `id` | uuid | Primary key (auto-generated) |
| `token` | uuid | The license key the user enters in `cgc activate <key>` |
| `product_id` | text | Must be `"cgc_standard"` for CGC |
| `email` | text | Buyer's email address |
| `created_at` | timestamp | Purchase timestamp |
| `status` | text | `"active"`, `"revoked"`, etc. |

### How Validation Works

When a user runs `cgc activate <key>`, the following happens:

1. CGC CLI sends `POST https://cgc-production.up.railway.app/v1/license/validate` with `{"key": "<uuid>"}`
2. The relay API queries Supabase: `GET /rest/v1/purchases?token=eq.<key>&product_id=eq.cgc_standard`
3. If a matching row exists, returns `{"valid": true}`
4. If not, returns `{"valid": false}`

### Creating a License Token (on purchase)

When a customer completes a purchase on the website:

1. Generate a UUID v4 token
2. Insert into `purchases` table:
   ```sql
   INSERT INTO purchases (token, product_id, email, status)
   VALUES ('generated-uuid-here', 'cgc_standard', 'buyer@email.com', 'active');
   ```
3. Display the token to the user and/or email it to them
4. The user enters this token in their terminal: `cgc activate <token>`

### Important: Product ID

The product ID **must** be exactly `cgc_standard`. This is hardcoded in the relay API's auth middleware. The relay checks:
```
purchases?token=eq.{key}&product_id=eq.cgc_standard
```

If you use a different product ID, validation will fail.

---

## How Tiers Work (Client-Side)

The CGC CLI manages tiers locally. The website does NOT need to track whether a user is on trial/free/pro -- that's handled entirely by the client.

### Trial (Automatic)

- When CGC is first installed and run, it automatically creates a 14-day trial
- No server interaction needed for trials
- Trial start date is stored locally in `~/.cgc/license.db` (encrypted)
- After 14 days, the tier automatically becomes Free
- The website has no visibility into trials -- they are purely local

### Free (After Trial Expires)

- All context extension features work (discover, sample, chunk, search, SQL)
- Extraction commands (`cgc extract`, `cgc extract-file`) return an error with upgrade instructions:
  ```
  Graph extraction requires CGC Pro.
  Run 'cgc activate <license-key>' to activate your license.
  Visit https://cgc.dev to purchase a license.
  ```
- The website does not need to track free users

### Pro (After Activation)

- User runs `cgc activate <key>` with their purchased token
- CGC validates the token against the relay, which checks Supabase
- If valid, the license is encrypted and stored locally
- Pro tier is revalidated every 7 days (automatic, transparent to user)
- 3-day grace period if revalidation fails (e.g., user is offline)
- After grace period, tier reverts to Free until they go online

---

## What the Website Needs to Do

### Purchase Flow

1. **User lands on cgc.dev** -- sees feature comparison (Free vs Pro)
2. **User clicks "Buy Pro"** -- payment flow (Stripe, Lemon Squeezy, etc.)
3. **On successful payment:**
   - Generate a UUID v4 token
   - Insert into Supabase `purchases` table with `product_id = "cgc_standard"`
   - Display the token prominently to the user
   - Send the token via email as a backup
4. **User copies the token** and runs `cgc activate <token>` in their terminal

### Post-Purchase Page Content

Show the user something like:

```
Your CGC Pro License Key:

  a1b2c3d4-e5f6-7890-abcd-ef1234567890

To activate, open your terminal and run:

  cgc activate a1b2c3d4-e5f6-7890-abcd-ef1234567890

You'll see "License activated successfully!" when it's done.

Keep this key safe -- you'll need it if you reinstall CGC or switch machines.
```

### Email Template

Subject: Your CGC Pro License Key

```
Thanks for purchasing CGC Pro!

Your license key: a1b2c3d4-e5f6-7890-abcd-ef1234567890

To activate:
1. Open your terminal (Command Prompt on Windows, Terminal on Mac)
2. Run: cgc activate a1b2c3d4-e5f6-7890-abcd-ef1234567890
3. You'll see "License activated successfully!"

If you need to move your license to another machine:
1. Run: cgc deactivate (on the old machine)
2. Run: cgc activate <your-key> (on the new machine)

Need help? Reply to this email.
```

---

## Revoking a License

To revoke a license (refund, abuse, etc.):

```sql
UPDATE purchases SET status = 'revoked' WHERE token = '<uuid>' AND product_id = 'cgc_standard';
```

Or simply delete the row:
```sql
DELETE FROM purchases WHERE token = '<uuid>' AND product_id = 'cgc_standard';
```

The user's CGC will continue working for up to 7 days (revalidation interval) + 3 days (grace period) = 10 days maximum before their tier reverts to Free.

---

## Relay API Details

The relay API runs at `https://cgc-production.up.railway.app` and handles:

1. **License validation** -- `POST /v1/license/validate`
   - Public endpoint, rate limited to 5 req/min per IP
   - Checks Supabase purchases table
   - Returns `{"valid": true/false}`

2. **Graph extraction** -- `POST /v1/extract/text`, `/v1/extract/file`, `/v1/extract/structured`
   - Requires `X-License-Key` header
   - Validates the key against Supabase (cached 5 min)
   - Rate limited to 20-30 req/min per key
   - Runs extraction and returns triplets

The website does NOT need to interact with the relay API directly. The relay is used by the CGC CLI/client only.

---

## Environment Variables (Relay)

The relay API on Railway uses these env vars (already configured):
- `SUPABASE_URL` -- Your Supabase project URL
- `SUPABASE_SERVICE_KEY` -- Supabase service role key (NOT the anon key)
- `PORT` -- Set by Railway automatically

---

## Testing the Full Flow

1. **Create a test token:**
   ```sql
   INSERT INTO purchases (token, product_id, email, status)
   VALUES (gen_random_uuid(), 'cgc_standard', 'test@example.com', 'active')
   RETURNING token;
   ```

2. **Activate on client:**
   ```
   cgc activate <token-from-step-1>
   ```

3. **Verify:**
   ```
   cgc license
   ```
   Should show `Tier: Pro`

4. **Test extraction:**
   ```
   cgc extract "John works at Google in New York" --no-gliner
   ```
   Should return triplets

5. **Revoke (optional):**
   ```sql
   DELETE FROM purchases WHERE token = '<token>';
   ```
   After 7+3 days, tier reverts to Free

---

## Summary

| Responsibility | Who Handles It |
|----------------|----------------|
| Trial tracking | CGC client (local, encrypted) |
| Free tier restrictions | CGC client (local check) |
| Token generation | Website (on purchase) |
| Token storage | Supabase `purchases` table |
| Token validation | Relay API (Railway) |
| Pro tier revalidation | CGC client (every 7 days, hits relay) |
| License encryption | CGC client (AES-256-GCM) |
| Extraction processing | Relay API (Railway) |
| Payment processing | Website (Stripe/LemonSqueezy/etc.) |
