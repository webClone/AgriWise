# AgriBrain Plan Suite Manifest & Authority Map

**Folder Revision**: 7 October 2026  
**Repository**: [webClone/AgriWise](https://github.com/webClone/AgriWise)  
**Historical Production Baseline**: `26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4`  
**Plan Revision Commit**: `96e515d6b1593f4b38756e79000313302971b936`  
**Draft PR #1 Head**: `bcb9eda6b8ef1aa6425f5828669f753a191227bc` (draft, unmerged)

---

## 1. Document Precedence Hierarchy

When interpreting contracts, requirements, and execution constraints, the documents in this repository adhere to the following strict precedence order:

1. **Target Specification**: French Master Monograph R3 (*Monographie Maître FR R3*), dated 30 September 2026, Volumes XI–XVII (referenced in `AgriWise_AgriBrain_Monographie_Maitre_FR_R3.pdf`). Defines the 153 canonical scientific and functional requirements.
2. **Package Definitions & Evidence**: [`AgriWise_AgriBrain_Deep_Repair_Plan_2026-10-06.md`](AgriWise_AgriBrain_Deep_Repair_Plan_2026-10-06.md). Governs package identities (F01–F40, T01–T12), defect evidence, production targets, and engineering estimates.
3. **Scheduling & Prerequisite Authority**: [`AgriBrain_Execution_Sequencing_Addendum_2026-10-07.md`](AgriBrain_Execution_Sequencing_Addendum_2026-10-07.md). Governs the 17-stage zero-inversion acceptance order and early-slice boundaries.
4. **Technical Implementation Blueprint**: [`AgriBrain_Detailed_Implementation_Plan_2026-10-07.md`](AgriBrain_Detailed_Implementation_Plan_2026-10-07.md). Provides detailed code-level specifications, domain invariants, edge cases, and consumer reconciliation.
5. **Execution Task Register**: [`AgriBrain_Work_Packages_Task_List_2026-10-07.md`](AgriBrain_Work_Packages_Task_List_2026-10-07.md). Decomposes packages into atomic engineering tickets with prerequisites and verification checks.
6. **Historical Verification Records**: [`AgriBrain_Repair_Plan_Audit_Verification_2026-10-07.md`](AgriBrain_Repair_Plan_Audit_Verification_2026-10-07.md) and [`AgriBrain_Plan_Folder_Deep_Review_2026-10-07.md`](AgriBrain_Plan_Folder_Deep_Review_2026-10-07.md). Forensic audit and qualification records.
7. **Correction Specifications**: [`AgriBrain_Plan_Folder_Correction_Specification_2026-10-07.md`](AgriBrain_Plan_Folder_Correction_Specification_2026-10-07.md). Detailed review amendments and Omega milestones.

## 2. Plan Suite Directory & Quick Links

| Document | Role & Purpose | Direct Link |
|---|---|---|
| **README.md** | Authority map, document precedence & provenance | [README.md](README.md) |
| **Master Deep Repair Plan** | 52 package cards (F01–F40, T01–T12), evidence & estimates | [AgriWise_AgriBrain_Deep_Repair_Plan_2026-10-06.md](AgriWise_AgriBrain_Deep_Repair_Plan_2026-10-06.md) |
| **Sequencing Addendum** | 17-stage execution order, early-slice boundaries | [AgriBrain_Execution_Sequencing_Addendum_2026-10-07.md](AgriBrain_Execution_Sequencing_Addendum_2026-10-07.md) |
| **Detailed Implementation Plan** | Stage-by-stage technical blueprint & domain invariants | [AgriBrain_Detailed_Implementation_Plan_2026-10-07.md](AgriBrain_Detailed_Implementation_Plan_2026-10-07.md) |
| **Work Packages Task List** | 285 atomic engineering tickets with checklist tracking | [AgriBrain_Work_Packages_Task_List_2026-10-07.md](AgriBrain_Work_Packages_Task_List_2026-10-07.md) |
| **Audit Verification** | Master plan forensic qualification & hash proofs | [AgriBrain_Repair_Plan_Audit_Verification_2026-10-07.md](AgriBrain_Repair_Plan_Audit_Verification_2026-10-07.md) |
| **Plan Folder Deep Review** | Deep review of commit 96e515d & 11 findings | [AgriBrain_Plan_Folder_Deep_Review_2026-10-07.md](AgriBrain_Plan_Folder_Deep_Review_2026-10-07.md) |
| **Correction Specification** | Task rewriting specs, early-slice register & Omega breakdown | [AgriBrain_Plan_Folder_Correction_Specification_2026-10-07.md](AgriBrain_Plan_Folder_Correction_Specification_2026-10-07.md) |

## 3. Scope & Execution Rules

- **Production files only**: strictly no tests, mocks, or audits treated as correctness truth.
- **Early slices** (F35, F37, F38, F39, F40, F32) unblock cold startup and local boundaries but do **not** grant full package completion.
- **Total hours locked**: 2,564 to 4,540 engineering hours matching parent plan cards exactly.
- **Remediation begins** with **Stage 00 (Package F37)** and **Stage 01 (Packages F01, F02)**.
