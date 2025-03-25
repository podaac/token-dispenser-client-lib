# Token Dispenser Client

A Python client for Token Dispenser Service (TDS) discovery and calling

## Installation

A sample poetry dependency description by referencing to the TDS client library through a rev or a branch
```aiignore
[tool.poetry.dependencies]
python = "^3.12"
boto3 = "^1.37.3"
#token-dispenser-client = { git = "https://github.com/podaac/token-dispenser-client-lib.git", rev = "v0.1.0" }
token-dispenser-client-lib = { git = "https://github.com/podaac/token-dispenser-client-lib.git", branch = "feature/PODAAC-6601" }
```

# Usage
* The entry point of the TDS client module is 
  def get_token(client_id:str, minimum_alive_secs:int = 300, token_dispenser_arn_ssm_key:str = None) -> str:
Sample code:
```aiignore
from token_dispenser_client_lib import get_token

if __name__ == "__main__":
    path = "/service/token-dispenser"  # Replace with your parameter path
    region = "us-west-2" # Replace with your region.

    try:
        resp_str: str = get_token(client_id='davidyen', minimum_alive_secs=300, token_dispenser_arn_ssm_key='/service/token-dispenser/sndbx')
        print(f'calling tds with response : {resp_str}')

        # resp_str: str = get_token(client_id='davidyen', minimum_alive_secs=300)
        # print(f'calling tds with response : {resp_str}')

    except Exception as e:
        print(f"An unexpected error occurred: {e}")
```
# Input Parameters

| config key                                 | description                                                               |
|--------------------------------------------|---------------------------------------------------------------------------|
| `client_id`                                | Required field identifying the client id                                  |
| `minimum_alive_secs`                       | Optional, user wish to get minimum number of seconds before token expired |
| `token_dispenser_arn_ssm_key`              | Optional, if not provided, /service/token-dispenser will be assigned      |

## Input Parameters Details

* **`client_id` (str):**
    * A unique identifier for the client requesting the token.
    * Must be an alphanumeric string, 3 to 32 characters in length, matching the pattern `^[a-zA-Z0-9]{3,32}`.
    * The Token Dispenser Service (TDS) uses this `client_id` as a key to cache tokens in DynamoDB. Subsequent requests with the same `client_id` will attempt to retrieve the token from the cache.

* **`minimum_alive_secs` (int, optional):**
    * The minimum required remaining lifetime (in seconds) for a cached token to be considered valid. Defaults to `300` seconds.
    * If a cached token's remaining lifetime exceeds `minimum_alive_secs`, it will be returned.
    * Otherwise, TDS will generate a new token and update the cache in DynamoDB.

* **`token_dispenser_arn_ssm_key` (str, optional):**
    * The name of the AWS Systems Manager (SSM) Parameter Store entry containing the Token Dispenser Service (TDS) Lambda function's ARN.
    * TDS Lambda ARNs are stored in SSM under the path `/service/token-dispenser/${var.prefix}`, allowing for multiple deployments within the same AWS account.
    * If this parameter is omitted:
        * The library will retrieve all SSM parameters under the path `/service/token-dispenser`.
        * If multiple values are found, the library will raise an error, requiring you to provide the specific SSM parameter name.
        * If a single value is found, that value will be used as the lambda ARN.
    * Providing the full SSM parameter name directly avoids ambiguity and ensures the correct TDS Lambda function is invoked.

# Return type : str
* Sample error response:
```aiignore
{"statusCode": 422, "body": "Found more than one tds arn for: /service/token-dispenser"}
```

* Sample response with token:
```aiignore
"{\"authlevel\": 25, \"cookiename\": \"SMSESSION\", \"session_idletimeout\": 3600, \"session_maxtimeout\": 3600, \"sm_token\": \"D+Cklbxv/QmeYJA17BcwyeZsLRlswOIXsAVA0eVc/WkN8Amyhw=\", \"ssozone\": \"SM\", \"status\": \"success\", \"upn\": \"svgspodaac@ndc.nasa.gov\", \"userdn\": \"CN=svgspodaac,OU=Services,OU=Administrators,DC=ndc,DC=nasa,DC=gov\", \"expires_at\": 1740795628, \"created_at\": 1740792028}"
where created_at and expired_at are EPOCH time format
```
