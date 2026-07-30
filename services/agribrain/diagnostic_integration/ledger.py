"""Append-only, hash-chained ledger for diagnostic contributions."""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Dict, Iterable, Optional, Tuple

from services.agribrain.scientific_contracts.exceptions import ContractViolation

from .contracts import DiagnosticContribution, canonical_hash


LEDGER_SCHEMA_VERSION = "diagnostic_contribution_ledger_v2"
GENESIS_HASH = "0" * 64


@dataclass(frozen=True)
class ContributionLedgerEntry:
    sequence: int
    contribution: DiagnosticContribution
    previous_entry_hash: str
    entry_hash: str

    def identity_payload(self) -> dict:
        return {
            "schema_version": LEDGER_SCHEMA_VERSION,
            "sequence": self.sequence,
            "contribution_id": self.contribution.contribution_id,
            "contribution_hash": self.contribution.content_hash,
            "previous_entry_hash": self.previous_entry_hash,
        }

    def validate(self) -> None:
        self.contribution.validate()
        if canonical_hash(self.identity_payload()) != self.entry_hash:
            raise ContractViolation(f"diagnostic ledger hash mismatch at sequence {self.sequence}")

    def to_dict(self) -> dict:
        return {
            **self.identity_payload(),
            "contribution_generated_at": self.contribution.generated_at,
            "entry_hash": self.entry_hash,
            "contribution": self.contribution.to_dict(),
        }


class ContributionLedger:
    """Run-scoped append-only ledger with strict ancestry ordering."""

    def __init__(self) -> None:
        self._entries: list[ContributionLedgerEntry] = []
        self._by_id: Dict[str, ContributionLedgerEntry] = {}
        self._lock = RLock()

    def _stage(
        self, contributions: Iterable[DiagnosticContribution]
    ) -> Tuple[ContributionLedgerEntry, ...]:
        staged = []
        known = dict(self._by_id)
        previous_hash = self._entries[-1].entry_hash if self._entries else GENESIS_HASH
        next_sequence = len(self._entries) + 1
        for contribution in contributions:
            if not isinstance(contribution, DiagnosticContribution):
                raise ContractViolation("diagnostic ledger accepts DiagnosticContribution only")
            contribution.validate()
            if contribution.contribution_id in known:
                raise ContractViolation(
                    f"duplicate diagnostic contribution_id: {contribution.contribution_id}"
                )
            missing = [
                parent_id
                for parent_id in contribution.input_contribution_ids
                if parent_id not in known
            ]
            if missing:
                raise ContractViolation(
                    "diagnostic contribution references absent or future parents: "
                    + ", ".join(missing)
                )
            for parent_id in contribution.input_contribution_ids:
                if known[parent_id].contribution.input_belief_id != contribution.input_belief_id:
                    raise ContractViolation("diagnostic contribution ancestry crosses belief identities")
            identity = {
                "schema_version": LEDGER_SCHEMA_VERSION,
                "sequence": next_sequence,
                "contribution_id": contribution.contribution_id,
                "contribution_hash": contribution.content_hash,
                "previous_entry_hash": previous_hash,
            }
            entry = ContributionLedgerEntry(
                sequence=next_sequence,
                contribution=contribution,
                previous_entry_hash=previous_hash,
                entry_hash=canonical_hash(identity),
            )
            staged.append(entry)
            known[contribution.contribution_id] = entry
            previous_hash = entry.entry_hash
            next_sequence += 1
        return tuple(staged)

    def append(self, contribution: DiagnosticContribution) -> ContributionLedgerEntry:
        return self.append_many((contribution,))[0]

    def validate_many(
        self, contributions: Iterable[DiagnosticContribution]
    ) -> Tuple[ContributionLedgerEntry, ...]:
        """Stage a batch without mutating the ledger."""
        with self._lock:
            return self._stage(tuple(contributions))

    def append_many(
        self, contributions: Iterable[DiagnosticContribution]
    ) -> Tuple[ContributionLedgerEntry, ...]:
        with self._lock:
            staged = self._stage(tuple(contributions))
            if not staged:
                raise ContractViolation("diagnostic ledger cannot append an empty batch")
            self._entries.extend(staged)
            self._by_id.update({entry.contribution.contribution_id: entry for entry in staged})
            return staged

    def get(self, contribution_id: str) -> Optional[DiagnosticContribution]:
        entry = self._by_id.get(str(contribution_id))
        return entry.contribution if entry is not None else None

    def entries(self) -> Tuple[ContributionLedgerEntry, ...]:
        return tuple(self._entries)

    def contributions(self, belief_id: Optional[str] = None) -> Tuple[DiagnosticContribution, ...]:
        values = tuple(entry.contribution for entry in self._entries)
        if belief_id is None:
            return values
        return tuple(value for value in values if value.input_belief_id == belief_id)

    @property
    def head_hash(self) -> str:
        return self._entries[-1].entry_hash if self._entries else GENESIS_HASH

    def verify(self) -> None:
        previous_hash = GENESIS_HASH
        seen: set[str] = set()
        for expected_sequence, entry in enumerate(self._entries, start=1):
            if entry.sequence != expected_sequence:
                raise ContractViolation("diagnostic ledger sequence is not contiguous")
            if entry.previous_entry_hash != previous_hash:
                raise ContractViolation("diagnostic ledger hash chain is broken")
            if entry.contribution.contribution_id in seen:
                raise ContractViolation("diagnostic ledger contains duplicate contribution IDs")
            missing = set(entry.contribution.input_contribution_ids) - seen
            if missing:
                raise ContractViolation("diagnostic ledger contains forward or absent ancestry")
            entry.validate()
            seen.add(entry.contribution.contribution_id)
            previous_hash = entry.entry_hash

    def to_dict(self) -> dict:
        self.verify()
        return {
            "schema_version": LEDGER_SCHEMA_VERSION,
            "head_hash": self.head_hash,
            "entry_count": len(self._entries),
            "entries": [entry.to_dict() for entry in self._entries],
        }
