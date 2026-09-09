"""flight-parser-wrapper — EventBridge target.

Reads flight-routes.json from S3 (CONFIG_BUCKET) and fans out one async
flight-parser invocation per route.
"""
import json
import os

import boto3

BUCKET = os.environ["CONFIG_BUCKET"]
KEY = os.environ.get("ROUTES_KEY", "flight-routes.json")
PARSER = os.environ.get("PARSER_FUNCTION", "flight-parser")

_s3 = boto3.client("s3")
_lambda = boto3.client("lambda")


def handler(_event, _context):
    obj = _s3.get_object(Bucket=BUCKET, Key=KEY)
    routes = json.loads(obj["Body"].read())
    invoked = []
    for r in routes:
        payload = {"origin": r["origin"], "destination": r["destination"],
                   "route": f"{r['origin']}-{r['destination']}", "plan": r.get("plan")}
        _lambda.invoke(FunctionName=PARSER, InvocationType="Event", Payload=json.dumps(payload).encode())
        invoked.append(payload["route"])
        print(f"invoked parser for {payload['route']}")
    return {"ok": True, "routes": invoked}
