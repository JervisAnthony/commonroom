# Security Policy

## Responsible Disclosure

The **Commonroom** team takes security and privacy seriously. If you discover a security vulnerability or potential threat in this repository or any of its applications, please report it responsibly so it can be addressed before public disclosure.

### How to Report a Vulnerability
- **Private Reporting**: If GitHub Private Vulnerability Reporting is enabled on this repository, please submit your report via the **Security** tab -> **Advisories** -> **Report a vulnerability**.
- **Alternative Private Contact**: If private vulnerability reporting is unavailable, please contact the repository owner privately via GitHub profile contact details.
- **Do NOT open public issues**: Please do not file public GitHub issues, pull requests, or discussions for security vulnerabilities or active exploits until they have been remediated.

### What NOT to Include in Reports
- ❌ **Real credentials or API keys**: Never include real tokens, secrets, or passwords.
- ❌ **Real GPS coordinates or location traces**: Never submit real-world coordinate history or personally identifiable location data.
- ❌ **Personal data**: Never include private personal identifiable information (PII).
- Please use sanitized examples or synthetic mock data when demonstrating a proof-of-concept.

---

## Vulnerability Priority Tiers

Because Commonroom encompasses diverse applications with varying risk profiles, security reports are prioritized by domain impact:

### High Priority: Privacy & Access Control
- **The Burrow Clock (Location & Privacy)**: Any flaw allowing unauthorized location tracking, geofence interception, consent bypass, permission escalation, or failure of revocation mechanisms is treated as a critical privacy priority.
- **Authentication & Authorization**: Any vulnerability in cross-application identity contracts, token validation, user impersonation, or data boundary leakage across users.

### High Priority: AI Safety & Exfiltration
- **Pensieve (AI Companion & Retrieval)**: System prompt injection vulnerabilities that result in sensitive data exfiltration, unauthorized tool invocation, or persistent memory corruption are treated as security concerns.

### Moderate Priority: Game & Content Integrity
- **Hogwarts Trials (Quiz Integrity)**: Quiz score spoofing, client-side answer tampering, or leaderboard manipulation are treated as application integrity issues and addressed promptly, but are categorized distinctly from personal privacy or account security vulnerabilities.

