# Security policy

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability or include customer media, credentials, signed URLs, tokens, or exploit details in public channels.

Before a private reporting address is configured, contact the repository owner through the existing private project channel and label the message **Security vulnerability**. Include the affected area/version, impact, minimal reproduction, and suggested mitigation if known. Share only synthetic evidence and use an encrypted channel for sensitive material.

The owner should acknowledge a report within three business days, establish severity and containment, and provide updates at least weekly until resolution. Timelines are targets, not a bug-bounty commitment. Coordinated disclosure timing will be agreed with the reporter.

## Supported versions

There is no released product yet. Once releases begin, this file will list supported versions and security-update policy.

## Handling guidance

Immediately revoke exposed credentials and signed URLs, preserve restricted audit evidence, and stop affected workflow admission when containment requires it. Suspected cross-tenant access, malicious media execution, or provider data leakage is high severity. Do not destructively alter evidence during diagnosis.

See [the security design](docs/security.md) for the proposed controls and threat model.
