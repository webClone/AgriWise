"""MESIA Confirmation Evidence Levels — R6 §5.2.

Five levels of identity confirmation strength, from weak context through
trusted native/control receipt.  A learned classifier may propose
candidates but cannot create PROTOCOL_CONFIRMED by itself.

Safety preference (§5.3):
  Optimise precision and calibrated abstention for CONFIRMED identity.
  Lower recall is acceptable; false confirmation contaminates every
  downstream scientific result.
"""

from __future__ import annotations

from enum import IntEnum


class ConfirmationLevel(IntEnum):
    """Confirmation evidence strength — R6 §5.2.

    Ordered from weakest (1) to strongest (5).  Comparison operators
    reflect evidence strength: ``PROTOCOL_DECODE > WAVEFORM_STRUCTURE``.
    """

    WEAK_CONTEXT = 1
    """Known regulatory band, approximate bandwidth or vendor/device
    presence.  Useful only for candidate ranking."""

    WAVEFORM_STRUCTURE = 2
    """OFDM numerology, chirp, hopping, spreading, pulse or FMCW
    morphology.  Supports waveform class, not necessarily protocol."""

    REFERENCE_CORRELATION = 3
    """Preamble, PSS/SSS/SSB, GNSS PRN, LoRa preamble, Wi-Fi preamble,
    RFID reader command or radar trigger.  Supports a strong candidate."""

    PROTOCOL_DECODE = 4
    """Valid frame fields, CRC, cell/network/tag identity, channel/band/
    numerology consistency and repeated confirmation."""

    TRUSTED_NATIVE_CONTROL = 5
    """Known device/transmitter, signed configuration, task schedule,
    geometry, calibration and actual execution confirmation."""


# The minimum level that may produce PROTOCOL_CONFIRMED identity state.
MIN_CONFIRMATION_LEVEL = ConfirmationLevel.PROTOCOL_DECODE
