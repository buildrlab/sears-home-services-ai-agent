# ADR 0003: Use OpenAI for Agent and Vision

## Status

Accepted

## Context

The project requires conversational diagnostics and visual image analysis. The user chose OpenAI as the AI provider.

## Decision

Use OpenAI through a provider abstraction and the Responses API. Configure model
names by environment variables.

The default diagnostic model is `gpt-5.5` with low reasoning effort and low
verbosity for voice latency/cost control. Local development and tests use a
deterministic provider when no OpenAI API key is configured.

## Consequences

- The diagnostic agent can use structured outputs and tool calls.
- Image analysis can share the same provider abstraction.
- Local development can use a deterministic mock provider when no API key is configured.
- Secrets must be loaded from environment variables locally and Secrets Manager in AWS.
- Provider contract tests must cover request construction and tool-call parsing without making live OpenAI calls.

## Alternatives Considered

- AWS Bedrock: AWS-native, but the user selected OpenAI.
- Provider-specific direct calls throughout the codebase: simpler initially, but harder to test and swap.
