"""Placeholder Lambda when dist/emit_lambda.zip is not built yet.

Replace via scripts/package_emit_lambda.sh before production deploy.
Stub must not pretend batch emit succeeded for anonymous callers.
API Gateway still requires AWS_IAM on POST /v1/signals:batchEmit.
"""


def lambda_handler(event, context):  # noqa: ANN001, ARG001
    path = (event or {}).get("rawPath") or (event or {}).get("path") or ""
    method = (
        ((event or {}).get("requestContext") or {}).get("http") or {}
    ).get("method") or (event or {}).get("httpMethod") or "GET"
    if path.endswith("/v1/health") and method == "GET":
        return {
            "statusCode": 200,
            "headers": {"content-type": "application/json"},
            "body": '{"status":"ok","note":"stub package; build dist/emit_lambda.zip"}',
        }
    return {
        "statusCode": 503,
        "headers": {"content-type": "application/json"},
        "body": (
            '{"code":"stub_package",'
            '"message":"emit Lambda stub only; build dist/emit_lambda.zip and redeploy"}'
        ),
    }
