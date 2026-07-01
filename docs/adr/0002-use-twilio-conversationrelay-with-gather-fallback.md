# ADR 0002: Use Twilio ConversationRelay with Gather Fallback

## Status

Accepted

## Context

The project requires a functioning inbound phone number and natural voice conversation. The system should remain testable if ConversationRelay access is not enabled immediately.

## Decision

Use Twilio ConversationRelay as the primary voice integration. Implement Twilio Gather as a fallback path.

For Phase 0.5 live-call verification, use the Gather fallback path through the
local smoke webhook. ConversationRelay remains the primary Phase 4 integration,
but Phase 0.5 should not block on account-level ConversationRelay enablement.

For deployed reviewer validation, Gather is the reliable live voice path until
the Twilio account-level AI/ML addendum and ConversationRelay feature gate are
confirmed. The backend keeps the ConversationRelay TwiML and WebSocket route
implemented so enabling ConversationRelay later is a configuration/provider
change, not a redesign.

## Consequences

- ConversationRelay handles low-latency speech-to-text, text-to-speech, turn-taking, and WebSocket messaging.
- The backend can focus on diagnostic and scheduling logic.
- Gather fallback supports deterministic smoke tests and keeps the phone flow usable if ConversationRelay onboarding is delayed.
- WebSocket signature validation and HTTP webhook validation are mandatory.
- Reviewers can validate the deployed phone integration through standard
  Twilio Voice/Gather even if ConversationRelay access is delayed.

## Alternatives Considered

- Raw Twilio Media Streams: more control, but significantly more audio infrastructure and latency risk.
- Amazon Connect: more AWS-native, but slower to configure for a take-home and less aligned with fast reviewer testing.
