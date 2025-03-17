"""
A module discovers and invoke Token Dispenser Service (TDS) lambda
"""
import logging
import json
import re
from typing import List
from botocore.exceptions import ClientError
import boto3
lambda_client = boto3.client('lambda')
ssm = boto3.client('ssm')
# ssm parameter store default path for TDS ARN
_DEFAULT_SSM_PATH_: str = '/service/token-dispenser'
logger = logging.getLogger(__name__)


def get_parameter_by_name(name: str) -> str:
    """

    Args:
        name: the ssm name point to TDS arn

    Returns: tds arn as string
    """
    try:
        if not name.endswith('/'):  # Check if it's a specific parameter name
            response = ssm.get_parameter(
                Name=name
            )
        return response['Parameter']['Value']
    except KeyError as key_error:
        logger.exception("Missing Parameter or Value key with name:%s response:%s",
                         name, response)
        raise key_error
    except Exception as ex:  # Catch any other error.
        logger.exception("An unexpected error occurred during get_parameter: "
                         "name:%s response:%s", name, response)
        raise ex


def invoke_lambda(input_params_json, lambda_arn):
    """
    Invokes an AWS Lambda function with input parameters from a JSON string.

    Args:
        input_params_json (str): A JSON string containing input parameters.
        lambda_arn (str): The ARN of the Lambda function to invoke.

    Returns:
        str: The JSON-formatted response from the Lambda function, or an error message.
    """
    if not lambda_arn:
        return "Error: lambda_arn not provided"

    try:
        json.loads(input_params_json)
    except json.JSONDecodeError:
        return f'Error: Invalid JSON : {input_params_json}'

    try:
        response = lambda_client.invoke(
            FunctionName=lambda_arn,
            InvocationType='RequestResponse',  # Synchronous invocation
            Payload=input_params_json
        )

        payload = response['Payload'].read().decode('utf-8')

        # Check for function error
        if 'FunctionError' in response:
            raise RuntimeError(f"Error: Lambda function error: {payload}")

        return payload
    except ClientError as client_err:
        logger.exception("Lambda invokation error occured %s",client_err)
        return f"Error: Lambda invocation failed: {client_err}"
    except Exception as general_err:  # pylint: disable=broad-exception-caught
        logger.exception("An unexpected general error occurred "
                         "while invoking TDS: %s", general_err)
        return f"Error: Lambda invocation failed: {general_err}"


def validate_input(client_id: str, minimum_alive_secs: int) -> List[str]:
    """ validate the user inputs """
    err_msgs = []
    if client_id is None or client_id.strip() == '':
        err_msgs.append('Error: client_id is required')

    pattern = re.compile(r'^[a-zA-Z0-9]{3,32}$')
    if client_id and not pattern.match(client_id):
        err_msgs.append('client_id must be between length 3-32 '
                        'with pattern [a-zA-Z0-9]{3,32}')

    if minimum_alive_secs is not None and (not isinstance(minimum_alive_secs, int)):
        err_msgs.append('Minimum alive interval must be an integer')

    if isinstance(minimum_alive_secs, int) and (minimum_alive_secs > 3300 or
                                                minimum_alive_secs < 0):
        err_msgs.append('Minimum alive interval must be an integer between 1 and 3300')
    return err_msgs


def get_tds_arn(ssm_name: str) -> str:
    """
    :param ssm_name:
    :return:
    arn:str     : ARN of TDS lambda
    """
    response = None  # Initialize response to None
    if not ssm_name:
        ssm_name = _DEFAULT_SSM_PATH_
        try:
            response = ssm.get_parameters_by_path(
                Path=ssm_name,
                Recursive=True,
                MaxResults=2,
            )
            result_count = len(response.get('Parameters', []))
            if result_count == 2:
                raise ValueError(f"Found multiple parameters in path: {ssm_name}. Please provide "
                                 f"specific ssm name which points to the TDS lambda ARN. "
                                 f"Not path")
            logger.debug('Found single ssm param value by default ssm path')
            param = response.get('Parameters', []).pop(0)
            return param['Value']
        except KeyError as key_exception:
            logger.exception('ssm get_parameters_by_path error with path:%s '
                             'response:%s', ssm_name, response)
            raise key_exception
        except Exception as general_exception:
            logger.exception('Unexpected error in get_parameters_by_path with '
                             'path:%s response:%s', ssm_name, response)
            raise general_exception
    # if user provides a name, the code trusts it as a full name and let system fail if
    # provided name is not correct
    return get_parameter_by_name(name=ssm_name)


def get_token(client_id: str, minimum_alive_secs: int = 300,
              token_dispenser_arn_ssm_key: str = None) -> str:
    """
    Retrieves parameters from AWS Systems Manager Parameter Store by path.

    Args:
        client_id (str): Caller defined client_id
        minimum_alive_secs (int, optional): minimum alive secs for the token. Defaults to 300.
        If there is a cached token and the cached token has expiration time
        (current_time - expired_at)  shorter than the provided value,
        the token will be re-generated. Otherwise, a cached token will be returned.
        token_dispenser_arn_ssm_key (str, optional): If not provided, the program
        logic will /service/token-dispenser as root name space to get parameters.
        If only single value is returned, the returned value will be used as
        token dispenser arn.  Furthermore, the code will make a call to the token dispenser
        based on the retrieved ARN.

    Returns:
        str: A json string containing launchpad token with other fields such as created_at
        and expired_at all in EPOCH format

        Returns empty dict if no parameters found on the path.
            The return string could be a string showing error message
    """
    # Validate inputs.   minimum_alive_secs has a default value and won't be None
    err_msgs: List = validate_input(client_id=client_id,
                                    minimum_alive_secs=minimum_alive_secs)
    if len(err_msgs) > 0:
        raise ValueError(err_msgs)

    # TDS stands for Token Dispenser Service (it is a lambda)
    tds_arn = get_tds_arn(token_dispenser_arn_ssm_key)
    data = {
        "client_id": client_id,
        "minimum_alive_secs": minimum_alive_secs
    }
    json_data = json.dumps(data)
    resp: str = invoke_lambda(input_params_json=json_data, lambda_arn=tds_arn)
    return resp
