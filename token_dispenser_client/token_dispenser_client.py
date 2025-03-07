import boto3
import json
import re
from typing import List
lambda_client = boto3.client('lambda')
ssm = boto3.client('ssm')
# ssm parameter store default path for TDS ARN
_DEFAULT_SSM_PATH_: str = '/service/token-dispenser'
import logging
logger = logging.getLogger(__name__)

def get_parameter_by_name(name: str)->str:
    try:
        if not name.endswith('/'):  # Check if it's a specific parameter name
            response = ssm.get_parameter(
                Name=name
            )
        return response['Parameter']['Value']
    except KeyError:
        logger.exception(f"Missing 'Parameter' or 'Value' key with name: {name} response:{response}")
        raise KeyError(f"Missing 'Parameter' or 'Value' key with name: {name} response:{response}")
    except Exception as e:  # Catch any other error.
        logger.exception(f"An unexpected error occurred during get_parameter: name: {name} response:{response}")
        raise e


def get_parameters_by_path(path:str):
    """
    Retrieves parameters from AWS Systems Manager Parameter Store by path.

    Args:
        path (str): The path to the parameters.

    Returns:
        dict: A dictionary containing the parameter names and values, or None if an error occurs.
        Returns empty dict if no parameters found on the path.
    Raises:
        botocore.exceptions.ClientError: If an error occurs while calling the SSM API.
    """
    try:
        parameters = {}
        next_token = None
        while True:
            if next_token:
                response = ssm.get_parameters_by_path(
                    Path=path,
                    Recursive=True,
                    NextToken=next_token
                )
            else:
                response = ssm.get_parameters_by_path(
                    Path=path,
                    Recursive=True,
                )

            for param in response.get('Parameters', []):
                parameters[param['Name']] = param['Value']

            next_token = response.get('NextToken')
            if not next_token:
                break
        return parameters
    except(ssm.exceptions.InternalServerError, ssm.exceptions.InvalidFilterKey, ssm.exceptions.InvalidFilterOption,
           ssm.exceptions.InvalidFilterValue, ssm.exceptions.InvalidKeyId, ssm.exceptions.InvalidNextToken) \
            as ssm_exception:
        logger.exception(f'ssm get_parameters_by_path error with path: {path}')
        raise ssm_exception
    except Exception as e:
        logger.exception(f'Unexpected error in get_parameters_by_path with path: {path}')
        raise e


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
        input_params = json.loads(input_params_json)
    except json.JSONDecodeError:
        return f'Error: Invalid JSON : {input_params_json}'

    try:
        response = lambda_client.invoke(
            FunctionName=lambda_arn,
            InvocationType='RequestResponse',  # Synchronous invocation
            Payload=input_params
        )

        payload = response['Payload'].read().decode('utf-8')

        # Check for function error
        if 'FunctionError' in response:
            raise RuntimeError(f"Error: Lambda function error: {payload}")

        return payload

    except Exception as e:
        return f"Error: Lambda invocation failed: {e}"

def validate_input(client_id:str, minimum_alive_secs:int) -> List[str]:
    err_msgs=[]
    if client_id is None or client_id.strip() == '':
        err_msgs.append('Error: client_id is required')

    pattern = re.compile(r'^[a-zA-Z0-9]{3,32}$')
    if client_id and not pattern.match(client_id):
        err_msgs.append('client_id must be between length 3-32 with pattern [a-zA-Z0-9]{3,32}')

    if minimum_alive_secs is not None and (not isinstance(minimum_alive_secs, int)):
        err_msgs.append('Minimum alive interval must be an integer')

    if isinstance(minimum_alive_secs, int) and (minimum_alive_secs > 3300 or minimum_alive_secs < 0):
        err_msgs.append('Minimum alive interval must be an integer between 1 and 3300')
    return err_msgs


def get_tds_arn(ssm_name:str) -> str:
    """
    :param ssm_name:
    :return:
    err_msg:str : error message if there is error
    arn:str     : ARN of TDS lambda
    """
    err_msg=''
    if ssm_name is None:
        ssm_name=_DEFAULT_SSM_PATH_
        tds_arn = ''
        params = get_parameters_by_path(path=ssm_name)
        size = params.__len__()
        if size < 1:
            raise ValueError(f"Not able to find tds arn for: {ssm_name}")
        elif size > 1:
            raise ValueError(f"Found more than one tds arn for: {ssm_name}")
        elif size == 1:
            items_list = list(params.items())
            first_item = items_list[0]
            first_key, tds_arn = first_item
        return tds_arn

    # if user provides a name, the code trusts it as a full name and let system fail if
    # provided name is not correct
    return get_parameter_by_name(name=ssm_name)

def create_err(err_msg:str) -> str:
    return json.dumps(dict(body=err_msg))


def get_token(client_id:str, minimum_alive_secs:int = 300, token_dispenser_arn_ssm_key:str = None) -> str:
    """
    Retrieves parameters from AWS Systems Manager Parameter Store by path.

    Args:
        client_id (str): Caller defined client_id
        minimum_alive_secs (int, optional): minimum alive secs for the token. Defaults to 300. If there is a cached token
        and the cached token has expiration time (current_time - expired_at) shorter than the provided value,
        the token will be re-generated. Otherwise, a cached token will be returned.
        token_dispenser_arn_ssm_key (str, optional): If not provided, the program logic will /service/token-dispenser as
        root name space to get parameters.  If only single value is returned, the returned value will be used as
        token dispenser arn.  Furthermore, the code will make a call to the token dispenser based on the retrieved ARN.

    Returns:
        str: A json string containing launchpad token with other fields such as created_at and expired_at all in
        EPOCH format
        Returns empty dict if no parameters found on the path.
            The return string could be a string showing error message
    """
    # Validate inputs.   minimum_alive_secs has a default value and won't be None
    err_msgs:List = validate_input(client_id=client_id, minimum_alive_secs = minimum_alive_secs)
    if len(err_msgs) >0:
        raise ValueError(err_msgs)

    # TDS stands for Token Dispenser Service (it is a lambda)
    try:
        tds_arn = get_tds_arn(token_dispenser_arn_ssm_key)
    except ValueError as ve:
        return create_err(ve.args[0])

    # construct calling to TDS
    resp:str = invoke_lambda(input_params_json=
                             json.dumps(dict(client_id=client_id, minimum_alive_secs=minimum_alive_secs)),
                             lambda_arn=tds_arn)
    return resp

