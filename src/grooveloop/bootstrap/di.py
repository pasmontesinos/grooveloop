from __future__ import annotations

from grooveloop.delivery.infrastructure.di import DeliveryModule
from grooveloop.journal.infrastructure.di import JournalModule
from grooveloop.learning.infrastructure.di import LearningModule
from grooveloop.shared.infrastructure.di import SharedModule
from grooveloop.slicing.infrastructure.di import SlicingModule
from grooveloop.verification.infrastructure.di import VerificationModule

modules = [
    SharedModule(),
    SlicingModule(),
    DeliveryModule(),
    LearningModule(),
    VerificationModule(),
    JournalModule(),
]
