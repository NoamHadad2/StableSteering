# Oracle Target-Recovery Results

This directory contains the oracle-based steering study in which a hidden real target image is paired with a manually written caption.

Protocol summary:

- the generator sees only the caption and negative prompt
- the oracle sees the hidden target image
- each round selects the candidate with highest CLIP image similarity to the target
- steering runs for 10 rounds per target

Current bundle summary: 3 targets, 30 rounds, and 120 candidate rows.
