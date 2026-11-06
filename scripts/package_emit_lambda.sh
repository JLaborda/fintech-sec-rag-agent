#!/usr/bin/env bash
# Build a Lambda deployment zip for the secondary re-emit API.
# Requires: python3.12, pip, zip.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST="${ROOT}/dist"
BUILD="${DIST}/lambda_build"
ZIP="${DIST}/emit_lambda.zip"

rm -rf "${BUILD}" "${ZIP}"
mkdir -p "${BUILD}"

python3.12 -m pip install \
  --upgrade \
  --target "${BUILD}" \
  "${ROOT}" \
  "boto3>=1.34" \
  "pydantic>=2.6" \
  "jsonschema>=4.21" \
  "httpx>=0.27" \
  "requests>=2.31" \
  "pyarrow>=15" \
  "pandas>=2.2"

# Lambda handler module name expected by Terraform when the real zip is present.
cp "${ROOT}/src/sec_signals/api/handlers.py" "${BUILD}/handlers.py"

(
  cd "${BUILD}"
  zip -qr9 "${ZIP}" .
)

echo "Wrote ${ZIP}"
ls -lh "${ZIP}"
