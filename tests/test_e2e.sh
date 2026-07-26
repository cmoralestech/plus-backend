#!/bin/bash
# End-to-end test suite for Arranged
# Usage: bash tests/test_e2e.sh [base_url]

BASE="${1:-https://sugardads-api.fly.dev}"
PASS=0
FAIL=0
RAND=$RANDOM

log_pass() { echo "  PASS: $1"; PASS=$((PASS+1)); }
log_fail() { echo "  FAIL: $1"; FAIL=$((FAIL+1)); }

echo "============================================"
echo "  ARRANGED E2E TEST SUITE"
echo "  Base: $BASE"
echo "============================================"
echo ""

# --- Register sugar daddy ---
echo "TEST 1: Register sugar daddy"
REG=$(curl -s -X POST "$BASE/api/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"e2e-sd-${RAND}@test.com\",\"password\":\"testpass123\",\"user_type\":\"sugar\"}")
TOKEN_S=$(echo "$REG" | python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])" 2>/dev/null)
UID_S=$(echo "$REG" | python3 -c "import json,sys; print(json.load(sys.stdin)['user']['id'])" 2>/dev/null)
[ -n "$TOKEN_S" ] && [ "$TOKEN_S" != "null" ] && log_pass "User $UID_S" || log_fail "Registration failed"

# --- Register attractive member ---
echo "TEST 2: Register attractive member"
REG_A=$(curl -s -X POST "$BASE/api/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"e2e-sb-${RAND}@test.com\",\"password\":\"testpass123\",\"user_type\":\"attractive\"}")
TOKEN_A=$(echo "$REG_A" | python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])" 2>/dev/null)
UID_A=$(echo "$REG_A" | python3 -c "import json,sys; print(json.load(sys.stdin)['user']['id'])" 2>/dev/null)
[ -n "$TOKEN_A" ] && [ "$TOKEN_A" != "null" ] && log_pass "User $UID_A" || log_fail "Registration failed"

# --- No profile yet ---
echo "TEST 3: No profile before onboarding"
NOPROFILE=$(curl -s "$BASE/api/profiles/me" -H "Authorization: Bearer $TOKEN_S")
echo "$NOPROFILE" | python3 -c "import json,sys; d=json.load(sys.stdin); exit(0 if 'not found' in d.get('detail','').lower() else 1)" 2>/dev/null \
  && log_pass "404 as expected" || log_fail "Profile should not exist yet"

# --- Create profiles ---
echo "TEST 4: Create sugar daddy profile"
P_S=$(curl -s -X POST "$BASE/api/profiles/" \
  -H "Authorization: Bearer $TOKEN_S" -H "Content-Type: application/json" \
  -d '{"display_name":"E2E Sugar","date_of_birth":"1985-03-15","gender":"male","city":"Miami","looking_for":"Testing"}')
echo "$P_S" | python3 -c "import json,sys; d=json.load(sys.stdin); exit(0 if d.get('id') else 1)" 2>/dev/null \
  && log_pass "Profile created" || log_fail "Profile creation failed"

echo "TEST 5: Create attractive profile"
P_A=$(curl -s -X POST "$BASE/api/profiles/" \
  -H "Authorization: Bearer $TOKEN_A" -H "Content-Type: application/json" \
  -d '{"display_name":"E2E Baby","date_of_birth":"1998-07-20","gender":"female","city":"Miami","looking_for":"Testing"}')
echo "$P_A" | python3 -c "import json,sys; d=json.load(sys.stdin); exit(0 if d.get('id') else 1)" 2>/dev/null \
  && log_pass "Profile created" || log_fail "Profile creation failed"

# --- Subscription tier ---
echo "TEST 6: Sugar daddy is free tier"
SUB=$(curl -s "$BASE/api/subscription/" -H "Authorization: Bearer $TOKEN_S")
TIER=$(echo "$SUB" | python3 -c "import json,sys; print(json.load(sys.stdin).get('tier',''))" 2>/dev/null)
[ "$TIER" = "free" ] && log_pass "Tier=free (blur applies)" || log_fail "Expected free, got $TIER"

# --- Discover ---
echo "TEST 7: Discover returns profiles"
DISC=$(curl -s "$BASE/api/discover/?page_size=5" -H "Authorization: Bearer $TOKEN_S")
DCOUNT=$(echo "$DISC" | python3 -c "import json,sys; print(len(json.load(sys.stdin)))" 2>/dev/null)
[ "$DCOUNT" -gt 0 ] 2>/dev/null && log_pass "$DCOUNT profiles" || log_fail "No profiles returned"

# --- Verification ---
echo "TEST 8: Submit photo verification"
VER=$(curl -s -X POST "$BASE/api/profiles/verify/photo" -H "Authorization: Bearer $TOKEN_S")
echo "$VER" | python3 -c "import json,sys; exit(0 if json.load(sys.stdin).get('submitted') else 1)" 2>/dev/null \
  && log_pass "Submitted" || log_fail "Verification failed"

echo "TEST 9: Duplicate verification rejected"
VER2=$(curl -s -X POST "$BASE/api/profiles/verify/photo" -H "Authorization: Bearer $TOKEN_S")
echo "$VER2" | python3 -c "import json,sys; exit(0 if 'pending' in json.load(sys.stdin).get('detail','').lower() else 1)" 2>/dev/null \
  && log_pass "Rejected" || log_fail "Should reject duplicate"

# --- Verification status ---
echo "TEST 10: Verification status shows pending"
VSTAT=$(curl -s "$BASE/api/profiles/verify/status" -H "Authorization: Bearer $TOKEN_S")
echo "$VSTAT" | python3 -c "import json,sys; d=json.load(sys.stdin); exit(0 if d.get('pending_photo') else 1)" 2>/dev/null \
  && log_pass "pending_photo=true" || log_fail "Should show pending"

# --- Checkout ---
echo "TEST 11: Stripe checkout URL generates"
CHECKOUT=$(curl -s -X POST "$BASE/api/billing/checkout?tier=premium" -H "Authorization: Bearer $TOKEN_S")
echo "$CHECKOUT" | python3 -c "import json,sys; d=json.load(sys.stdin); exit(0 if 'stripe.com' in d.get('checkout_url','') else 1)" 2>/dev/null \
  && log_pass "Checkout URL works" || log_fail "No checkout URL"

# --- Contact form ---
echo "TEST 12: Contact form"
CONTACT=$(curl -s -X POST "$BASE/api/contact" \
  -H "Content-Type: application/json" \
  -d '{"name":"E2E Test","email":"e2e@test.com","category":"general","message":"This is an automated test message from the E2E test suite."}')
echo "$CONTACT" | python3 -c "import json,sys; exit(0 if 'sent' in json.load(sys.stdin).get('message','').lower() else 1)" 2>/dev/null \
  && log_pass "Contact form works" || log_fail "Contact form failed"

# --- Newsletter ---
echo "TEST 13: Newsletter subscribe"
NEWS=$(curl -s -X POST "$BASE/api/newsletter/subscribe" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"e2e-news-${RAND}@test.com\",\"source\":\"test\"}")
echo "$NEWS" | python3 -c "import json,sys; exit(0 if json.load(sys.stdin).get('subscribed') else 1)" 2>/dev/null \
  && log_pass "Subscribed" || log_fail "Subscribe failed"

# --- Health ---
echo "TEST 14: Health check"
HEALTH=$(curl -s "$BASE/api/health")
echo "$HEALTH" | python3 -c "import json,sys; exit(0 if json.load(sys.stdin).get('status')=='ok' else 1)" 2>/dev/null \
  && log_pass "Healthy" || log_fail "Unhealthy"

# --- Summary ---
echo ""
echo "============================================"
TOTAL=$((PASS+FAIL))
echo "  $PASS/$TOTAL PASSED"
[ $FAIL -gt 0 ] && echo "  $FAIL FAILED" || echo "  ALL TESTS PASSED"
echo "============================================"
exit $FAIL
