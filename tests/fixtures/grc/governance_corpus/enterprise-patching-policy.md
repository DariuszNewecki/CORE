# Enterprise Patching Policy

> Status: DRAFT

## Table of contents
1. Purpose
2. Scope
3. Definitions
4. Principles
   4.1. Complete Inventory Prerequisite
   4.2. Patching Obligation
   4.3. Change Management Enforcement
   4.4. Emergency Patching
   4.5. Testing and Rollback
5. Roles and Accountability
6. RACI Matrix
7. Governance and Controls
8. References
9. Compliance
10. Review

## Purpose
This policy establishes the overarching framework for patch management across all IT, OT, and IoT assets within the organization. It ensures that every device connected to the corporate network is inventoried, assigned to an accountable owner, and included in a documented patch management cycle.

The policy directly addresses an internal audit recommendation requiring a systematic control procedure to guarantee that all active devices are identified and covered by patch management.

This policy also supports compliance with:
- NIS2 Directive, Article 21(2) on cybersecurity risk management measures,
- ISO/IEC 27001 Annex A.12.6 on technical vulnerability management.

## Scope
This policy applies to all IT hardware and software assets owned, leased, or otherwise managed by the organization, including but not limited to:
- Information Technology (IT) assets (servers, laptops, desktops, mobile devices, printers, network equipment, etc.).
- Operational Technology (OT) assets (industrial control systems, SCADA, control equipment, etc.).
- Internet of Things (IoT) assets (smart sensors, desk phones, connected devices).

All assets, whether physically on premises or remotely connected, fall under this policy. OT/IoT systems may require specific approaches such as vendor coordination, firmware updates, compensating controls, or virtual patching where direct patching is not immediately possible.

## Definitions
- **Asset:** Any IT, OT, or IoT device, software, or component recorded in the enterprise asset and configuration management system.
- **Configuration Item (CI):** A record in the enterprise asset and configuration management system representing an asset with defined attributes and ownership.
- **Patch:** A vendor-supplied update addressing vulnerabilities, bugs, or performance issues.
- **Patch Management Cycle:** The structured process of identifying, testing, approving, deploying, and verifying patches.
- **Asset Owner:** The individual accountable for the lifecycle, security, and patching compliance of a given asset.
- **Change Record:** A documented entry in the change management system evidencing the approval and completion of patch deployments.
- **Emergency Patch:** A patch deployed outside standard cycles to mitigate an urgent, high-risk vulnerability.

## Principles

### Complete Inventory Prerequisite
All IT, OT, and IoT assets must be recorded in the enterprise asset and configuration management system with a unique Configuration Item (CI) and an identified Asset Owner.

Devices not registered in the enterprise asset and configuration management system are considered unauthorized and are not permitted to connect to the corporate network.

### Patching Obligation
Every asset must be included in a documented patch management cycle that ensures timely remediation of security vulnerabilities, vendor updates, and configuration fixes. The patch management cycle must be defined according to the risk profile of the asset class (e.g., servers, endpoints, network devices, OT equipment).

Prioritization Criteria: Critical vulnerabilities must be patched within 7 days, high severity within 30 days, and medium within 60 days, unless compensating controls are formally documented and approved.

### Change Management Enforcement
All patch deployments must be executed through the Change Management process, ensuring traceability, approval, and evidence of successful implementation. Evidence of patching compliance will be validated via Change records.

### Emergency Patching
Zero-day or high-impact vulnerabilities require expedited patch deployment through a fast-tracked Change process. Emergency patches must still be documented, with post-implementation review.

### Testing and Rollback
All patches must be tested in an isolated environment where feasible before production deployment. Rollback procedures must be documented to restore service if patching causes disruption. For OT/IoT systems, patch deployment must minimize downtime and coordinate with operational safety requirements.

## Roles and Accountability
- **ITAM Process Owner:** Ensures the inventory of assets is complete and accurate; enforces that every asset has an identified Asset Owner; provides the authoritative dataset used by Security for patch compliance reporting.
- **Security & Infrastructure:** Define and maintain patching policies and cycles per asset class; ensure tools and processes are in place for vulnerability scanning, patch deployment, and reporting; monitor compliance and escalate deviations.
- **Asset Owners:** Accountable for ensuring that assets under their responsibility are patched in accordance with the defined cycle; review patching reports and remediate exceptions.
- **CSIRT / SOC:** Validate patch compliance during incident investigations; escalate non-compliance to the Asset Owner and Security; provide intelligence on emerging vulnerabilities requiring emergency patching.

## RACI Matrix
This structure ensures patching is a shared control: ITAM provides the authoritative inventory foundation, Security & Infrastructure enable patching, Asset Owners own compliance for their scope, and CSIRT / SOC ensure oversight through monitoring and incident investigation.

## Governance and Controls

### Asset Discovery and Inventory Controls
Automated and manual discovery methods must be used to maintain a complete and accurate view of assets connected to the network. Unauthorized assets identified through discovery must be investigated and either onboarded into the enterprise asset and configuration management system or blocked from access.

### Data Enrichment
Asset and enterprise system integrations will enrich discovered devices to prevent duplication and ensure proper classification. For assets without automated management solutions, manual enrichment and maintenance is mandatory.

### Audit Evidence
Compliance with this policy is evidenced by:
- Inventory completeness in the configuration management system,
- Patch Change records in the change management system,
- Security vulnerability scans showing alignment with patch cycles,
- Exception handling records for assets with deferred patches.

Metrics: % of assets patched within SLA, average vulnerability age, and number of approved exceptions.

## References
- Windows Servers Patching Procedure (internal knowledge base, TBD)
- Linux Servers Patching Procedure (internal knowledge base, TBD)
- Data Center Network Device Patch Policy (internal knowledge base, TBD)
- End-User Device Patch Policy (internal knowledge base, TBD)
- OT Patch Policy (internal knowledge base, TBD)
- Deskphone Patch Policy (internal knowledge base, TBD)

## Compliance
Non-compliance with this policy exposes the organization to significant operational and security risks and may constitute a violation of NIS2 requirements. Repeated or willful non-compliance will be escalated to the CISO Office and may trigger disciplinary measures.

## Review
This policy will be reviewed annually by the ITAM Process Owner in consultation with the CISO Office and Infrastructure Managers, or earlier if significant changes to the threat landscape, regulations, or infrastructure occur. Reviews will also be triggered by major incidents or regulatory changes.
