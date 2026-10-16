# Proposed Feature Register — not yet approved

Source: 47-slide project presentation and speaker notes. These are **proposed** capabilities, not confirmed implementation or scientific validity. Phase 0 must evaluate each feature against free-tier, data availability, research goals, and team resources. Never remove a feature silently; mark a rationale and alternative in the decision register.

| ID | Proposed capability | Owner(s) | Status / gating dependency |
|---|---|---|---|
| F01 | CAD-related ML prediction & inference | AI / Backend | Proposed; exact medical outcome + supported labels TBD |
| F02 | Per-prediction explainability (e.g., SHAP/LIME) | AI / Backend / Web | Proposed; interpretation + reliability review TBD |
| F03 | Clinician dashboard: patients, risk timeline, triage | Backend / Frontend | Proposed; needs validated API and safe role/access model |
| F04 | Patient experience: health measures, survey, lifestyle, offline | Frontend / Backend | Proposed; input availability/consent TBD |
| F05 | Wearable adapters (HealthKit/Health Connect and others) | Mobile / Backend | Proposed; hardware, approval and real-data access TBD |
| F06 | Reassessment and patient-clinician follow-up | AI / Backend / Mobile / Web | Proposed; no unsupported clinical alert thresholds |
| F07 | Events, audit logging, user consent, data access | Backend | Proposed; research scope / privacy review required |
| F08 | Interoperability, FHIR mapping and export | Backend | Proposed; prioritize minimal compatible workflow |
| F09 | Extensible modular disease architecture | Cross-functional | Proposed; CAD-first; other diseases future, not Phase 0 |
| F10 | Reproducible evaluation and research reporting | AI / Research | Required goal; research questions and test protocol TBD |
| F11 | Authentication, access control, security | Backend / Frontend | Required for working prototype; don't claim regulatory compliance |
| F12 | AI–Backend versioned inference API & integration tests | AI / Backend | Required engineering gate; design in Phase 0 |

**Scientific gating questions**

- Does the selected dataset label *existing CAD*, CAD severity, or future event timing? Never label CAD classification as a 30-day event probability.
- Do paired ECG/wearable/clinical measurements and outcome labels exist for the intended multimodal research? If not, demonstrate separate validated modules without deceptive fusion claims.
- All alert thresholds and treatment recommendations in slides require clinical review and appropriate evidence; they are not approved safety logic.

Phase 0 report must reference features by ID and document whether fully implementable for $0, implementable with simulators (integration-only), or blocked by data/hardware/access.
