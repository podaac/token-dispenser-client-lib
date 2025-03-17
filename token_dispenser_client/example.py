"""
Example module to drive/test TDS client library
"""
from token_dispenser_client import get_token
# Example:

if __name__ == "__main__":
    try:
        # /service/token-dispenser/sndbx is the real sndbx SSM name
        resp_str: str = get_token(client_id='davidyen', minimum_alive_secs=120,
        token_dispenser_arn_ssm_key='/service/token-dispenser/sndbx')
        print(f'calling tds with response : {resp_str}')

        resp_str: str = get_token(client_id='davidyen', minimum_alive_secs=300)
        print(f'calling tds with response : {resp_str}')
    except KeyError as kerr:
        print(f"An unexpected Key Error occurred: {kerr}")
    except Exception as ex:  # pylint: disable=broad-exception-caught
        print(f"An unexpected error occurred: {ex}")
