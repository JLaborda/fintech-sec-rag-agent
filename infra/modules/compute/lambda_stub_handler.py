"""Placeholder Lambda when dist/emit_lambda.zip is not built yet.

Replace via scripts/package_emit_lambda.sh before production deploy.
"""


def lambda_handler(event, context):  # noqa: ANN001, ARG001
    return {
        "statusCode": 200,
        "headers": {"content-type": "application/json"},
        "body": '{"status":"ok","note":"stub package; build dist/emit_lambda.zip"}',
    }
