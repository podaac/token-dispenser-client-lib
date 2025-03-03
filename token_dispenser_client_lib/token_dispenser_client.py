import boto3
import json
import re
lambda_client = boto3.client('lambda')
ssm = boto3.client('ssm')
_DEFAULT_SSM_PATH_: str = '/service/token-dispenser'  # ssm parameter store default path for TDS ARN

def get_parameter_by_name(name: str, with_decryption:bool = False)->str:
    if not name.endswith('/'):  # Check if it's a specific parameter name
        response = ssm.get_parameter(
            Name=name,
            WithDecryption=with_decryption
        )
    return response['Parameter']['Value']


def get_parameters_by_path(path:str, with_decryption=True):
    """
    Retrieves parameters from AWS Systems Manager Parameter Store by path.

    Args:
        path (str): The path to the parameters.
        with_decryption (bool, optional): Whether to decrypt SecureString parameters. Defaults to True.

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
                    WithDecryption=with_decryption,
                    NextToken=next_token
                )
            else:
                response = ssm.get_parameters_by_path(
                    Path=path,
                    Recursive=True,
                    WithDecryption=with_decryption
                )

            for param in response.get('Parameters', []):
                parameters[param['Name']] = param['Value']

            next_token = response.get('NextToken')
            if not next_token:
                break

        return parameters

    except Exception as e:
        print(f"Error retrieving parameters from path '{path}': {e}")
        return None


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
        return "Error: Invalid JSON"

    try:
        response = lambda_client.invoke(
            FunctionName=lambda_arn,
            InvocationType='RequestResponse',  # Synchronous invocation
            Payload=json.dumps(input_params).encode('utf-8')
        )

        payload = response['Payload'].read().decode('utf-8')

        # Check for function error
        if 'FunctionError' in response:
            return f"Error: Lambda function error: {payload}"

        return payload

    except Exception as e:
        return f"Error: Lambda invocation failed: {e}"

def validate_input(client_id:str, minimum_alive_secs:int) -> str:
    err_msg=''
    if client_id is None or client_id.strip() == '':
        err_msg='Error: client_id is required'

    pattern = re.compile(r'^[a-zA-Z0-9]{3,32}$')
    if client_id and not pattern.match(client_id):
        err_msg='client_id must be between length 3-32 with pattern [a-zA-Z0-9]{3,32}'

    if minimum_alive_secs is not None and (not minimum_alive_secs.is_integer()):
        err_msg = f'{err_msg}\n Minimum alive interval must be an integer'

    if ((minimum_alive_secs is not None and minimum_alive_secs.is_integer()) and
            (minimum_alive_secs > 3300 or minimum_alive_secs < 0)):
        err_msg = f'{err_msg}\n Minimum alive interval must be an integer between 1 and 3300'
    return err_msg


def get_tds_arn(ssm_name:str) -> (str, str):
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
        params = get_parameters_by_path(path=ssm_name, with_decryption=False)
        size = params.__len__()
        if size < 1:
            err_msg = f"Not able to find tds arn for: {ssm_name}"
        elif size > 1:
            err_msg = f"Found more than one tds arn for: {ssm_name}"
        elif size == 1:
            items_list = list(params.items())
            first_item = items_list[0]
            first_key, tds_arn = first_item
        return err_msg, tds_arn
    else:
        # if user provides a name, the code trusts it as a full name and let system fail if
        # provided name is not correct
        return err_msg, get_parameter_by_name(name=ssm_name, with_decryption=False)

def crete_err(err_code:int , err_msg:str) -> str:
    return json.dumps(dict(statusCode=err_code, body=err_msg))


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
    # Validate inputs
    err_msg = validate_input(client_id=client_id, minimum_alive_secs = minimum_alive_secs)
    if not err_msg.strip() == '':
        return crete_err(err_code=422, err_msg=err_msg)
    # TDS stands for Token Dispenser Service (it is a lambda)
    err_msg, tds_arn = get_tds_arn(token_dispenser_arn_ssm_key)
    if err_msg:
        return crete_err(err_code=500, err_msg=err_msg)

    # construct calling to TDS
    resp:str = invoke_lambda(input_params_json=
                             json.dumps(dict(client_id=client_id, minimum_alive_secs=minimum_alive_secs)),
                             lambda_arn=tds_arn)
    return resp


# Example:
if __name__ == "__main__":
    path = "/service/token-dispenser"  # Replace with your parameter path
    region = "us-west-2" # Replace with your region.

    try:
        # resp_str: str = get_token(client_id='davidyen', minimum_alive_secs=300, token_dispenser_arn_ssm_key='/service/token-dispenser/bla')
        # print(f'calling tds with response : {resp_str}')

        resp_str: str = get_token(client_id='davidyen', minimum_alive_secs=300)
        print(f'calling tds with response : {resp_str}')

    except Exception as e:
        print(f"An unexpected error occurred: {e}")
