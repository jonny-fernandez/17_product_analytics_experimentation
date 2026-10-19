# Windows CI locked-design portability fix

The first published workflow run passed on Ubuntu but failed on Windows. The Windows pytest log showed `PREREGISTRATION_MISMATCH`: the Windows checkout SHA-256 was `fb17be4966d4cecafa51b26386ddbc38e0be93b68323d101da17109602c42ec7`, whereas the locked JSON's LF-byte SHA-256 is `83f26f31c75188df1b2a21c1afaa00b0c0a806e325ff80795035fcf2920af40a`.

The observed Windows hash is **exactly** the original JSON with LF newlines changed to CRLF newlines. The original locked JSON content, designated hash, experiment assumptions and outcome evidence are **unchanged**.

The narrow `.gitattributes` rule forces LF checkout for the locked design and its hash sidecar on every runner. Three regression tests verify the original bytes and LF policy, and confirm that CRLF tampering is still rejected. This fix does not weaken or bypass SHA-256 enforcement.

Status: fix validated by offline tests and simulated Windows-style `core.autocrlf=true` Git checkout. GitHub Actions requires a new run on the published fix commit before declaring cross-platform CI complete.
