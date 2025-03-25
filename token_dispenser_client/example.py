"""
Example module to drive/test TDS client library
"""

# import get_token from token_dispenser_client_lib
from token_dispenser_client import get_token


def main():
    """
    Main function to test the TDS client library
    """
    try:
        resp: dict = get_token(client_id='davidyen', minimum_alive_secs=300)
        print(f'calling tds with response : {resp}')

        # Ths following example is commented out.  It is in case the caller wants to use
        #  a specific token_dispenser_arn_ssm_key.  Or, if not providing
        #  token_dispenser_arn_ssm_key, the client library throws example about finding multiple
        #  or None parameters in the path.

        # resp: dict = get_token(client_id='davidyen', minimum_alive_secs=120,
        #                        token_dispenser_arn_ssm_key='/service/token-dispenser/sndbx')
        # print(f'calling tds with response : {resp}')
        # print(f'calling tds with sm_token : {resp["sm_token"]}')

    except KeyError as kerr:
        print(f"An unexpected Key Error occurred: {kerr}")
    except Exception as ex:  # pylint: disable=broad-exception-caught
        print(f"An unexpected error occurred: {ex}")


if __name__ == "__main__":
    main()
