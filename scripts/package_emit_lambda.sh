#!/usr/bin/env bash
# Build a Lambda deployment zip for the secondary re-emit API.
# Prefers a manylinux/Lambda-compatible container when Docker is available.
# Requires: python3.12, pip, zip; docker optional but recommended.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST="${ROOT}/dist"
BUILD="${DIST}/lambda_build"
ZIP="${DIST}/emit_lambda.zip"
ZIP_TMP="${DIST}/emit_lambda.zip.tmp"
MAX_UNZIPPED_BYTES=$((250 * 1024 * 1024))

rm -rf "${BUILD}" "${ZIP_TMP}"
mkdir -p "${BUILD}" "${DIST}"

install_deps() {
  local target="$1"
  python3.12 -m pip install \
    --upgrade \
    --platform manylinux2014_x86_64 \
    --implementation cp \
    --python-version 3.12 \
    --only-binary=:all: \
    --target "${target}" \
    "boto3>=1.34" \
    "pydantic>=2.6" \
    "jsonschema>=4.21" \
    "httpx>=0.27" \
    "requests>=2.31" \
    "pyarrow>=15" \
    "pandas>=2.2" \
    || python3.12 -m pip install \
      --upgrade \
      --target "${target}" \
      "boto3>=1.34" \
      "pydantic>=2.6" \
      "jsonschema>=4.21" \
      "httpx>=0.27" \
      "requests>=2.31" \
      "pyarrow>=15" \
      "pandas>=2.2"

  # Install the local package (pure Python) into the same target.
  python3.12 -m pip install --upgrade --target "${target}" --no-deps "${ROOT}"
}

if command -v docker >/dev/null 2>&1; then
  echo "Building Lambda zip inside public.ecr.aws/lambda/python:3.12 (manylinux-compatible)..."
  docker run --rm \
    -v "${ROOT}:/var/task" \
    -w /var/task \
    public.ecr.aws/lambda/python:3.12 \
    bash -lc '
      set -euo pipefail
      rm -rf dist/lambda_build
      mkdir -p dist/lambda_build
      pip install --upgrade --target dist/lambda_build \
        boto3 pydantic jsonschema httpx requests "pyarrow>=15" "pandas>=2.2"
      pip install --upgrade --target dist/lambda_build --no-deps .
    '
else
  echo "Docker not found; installing with pip --platform manylinux2014_x86_64 (fallback to host wheels)."
  install_deps "${BUILD}"
fi

# Lambda handler module name expected by Terraform when the real zip is present.
cp "${ROOT}/src/sec_signals/api/handlers.py" "${BUILD}/handlers.py"

# Also copy auth helper if handlers import sibling package layout fails in flat zip —
# the installed sec_signals package under BUILD already covers package imports.
UNZIPPED_BYTES="$(du -sb "${BUILD}" | awk '{print $1}')"
if [[ "${UNZIPPED_BYTES}" -gt "${MAX_UNZIPPED_BYTES}" ]]; then
  echo "ERROR: unzipped Lambda package is ${UNZIPPED_BYTES} bytes (>250 MiB limit)." >&2
  echo "Trim dependencies or switch to a container image before deploying." >&2
  exit 1
fi

(
  cd "${BUILD}"
  zip -qr9 "${ZIP_TMP}" .
)
mv -f "${ZIP_TMP}" "${ZIP}"

echo "Wrote ${ZIP} (unzipped ~${UNZIPPED_BYTES} bytes)"
ls -lh "${ZIP}"
