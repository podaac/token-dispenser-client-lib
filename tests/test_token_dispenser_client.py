import unittest
from unittest.mock import patch, MagicMock
import json
import re
from token_dispenser_client_lib.token_dispenser_client import (
    get_parameter_by_name,
    get_parameters_by_path,
    invoke_lambda,
    validate_input,
    get_tds_arn,
    get_token,
    _DEFAULT_SSM_PATH_
)

class TestTokenDispenserClient(unittest.TestCase):

    @patch('token_dispenser_client_lib.token_dispenser_client.ssm')
    def test_get_parameter_by_name(self, mock_ssm):
        mock_ssm.get_parameter.return_value = {'Parameter': {'Value': 'test_value'}}
        result = get_parameter_by_name('test_name')
        self.assertEqual(result, 'test_value')

        mock_ssm.get_parameter.assert_called_once_with(Name='test_name', WithDecryption=False)

    @patch('token_dispenser_client_lib.token_dispenser_client.ssm')
    def test_get_parameters_by_path(self, mock_ssm):
        mock_ssm.get_parameters_by_path.side_effect = [
            {'Parameters': [{'Name': '/test/param1', 'Value': 'value1'}, {'Name': '/test/param2', 'Value': 'value2'}]},
            {}
        ]
        result = get_parameters_by_path('/test')
        self.assertEqual(result, {'/test/param1': 'value1', '/test/param2': 'value2'})

        mock_ssm.get_parameters_by_path.side_effect = [{'Parameters': []}]
        result = get_parameters_by_path('/empty')
        self.assertEqual(result, {})

        mock_ssm.get_parameters_by_path.side_effect = Exception("Test Exception")
        result = get_parameters_by_path('/exception')
        self.assertEqual(result, None)

    @patch('token_dispenser_client_lib.token_dispenser_client.lambda_client')
    def test_invoke_lambda(self, mock_lambda):
        mock_lambda.invoke.return_value = {'Payload': MagicMock(read=MagicMock(return_value=b'{"result": "success"}'))}
        result = invoke_lambda('{"input": "test"}', 'arn:aws:lambda:us-east-1:123456789012:function:test_function')
        self.assertEqual(result, '{"result": "success"}')

        mock_lambda.invoke.return_value = {'Payload': MagicMock(read=MagicMock(return_value=b'{"result": "success"}')), 'FunctionError': 'Some Error'}
        result = invoke_lambda('{"input": "test"}', 'arn:aws:lambda:us-east-1:123456789012:function:test_function')
        self.assertTrue(result.startswith("Error: Lambda function error:"))

        self.assertEqual(invoke_lambda('invalid_json', 'arn'), "Error: Invalid JSON")
        self.assertEqual(invoke_lambda('{"input": "test"}', None), "Error: lambda_arn not provided")
        mock_lambda.invoke.side_effect = Exception("Lambda Error")
        self.assertTrue(invoke_lambda('{"input": "test"}', 'arn').startswith("Error: Lambda invocation failed:"))

    def test_validate_input(self):
        self.assertEqual(validate_input(None, 300), "Error: client_id is required")
        self.assertEqual(validate_input('test', 300), "")
        self.assertEqual(validate_input('test', 3301), '\n Minimum alive interval must be an integer between 1 and 3300')
        self.assertEqual(validate_input('test', -1), '\n Minimum alive interval must be an integer between 1 and 3300')
        self.assertEqual(validate_input('test', 300.5), '\n Minimum alive interval must be an integer')
        self.assertEqual(validate_input('test!@#', 300), 'client_id must be between length 3-32 with pattern [a-zA-Z0-9]{3,32}')

    @patch('token_dispenser_client_lib.token_dispenser_client.get_parameters_by_path')
    def test_get_tds_arn(self, mock_get_parameters_by_path):
        mock_get_parameters_by_path.return_value = {}
        err_msg, tds_arn = get_tds_arn(None)
        self.assertTrue(err_msg.startswith("Not able to find tds arn"))
        self.assertEqual(tds_arn, '')

        mock_get_parameters_by_path.return_value = {"key1": "value1", "key2": "value2"}
        err_msg, tds_arn = get_tds_arn(None)
        self.assertTrue(err_msg.startswith("Found more than one tds arn"))
        self.assertEqual(tds_arn, '')

        mock_get_parameters_by_path.return_value = {"key1": "value1"}
        err_msg, tds_arn = get_tds_arn(None)
        self.assertEqual(err_msg, '')
        self.assertEqual(tds_arn, 'value1')

        with patch('token_dispenser_client_lib.token_dispenser_client.get_parameter_by_name') as mock_get_parameter_by_name:
            mock_get_parameter_by_name.return_value = "test_arn"
            err_msg, tds_arn = get_tds_arn("test_name")
            self.assertEqual(err_msg, '')
            self.assertEqual(tds_arn, "test_arn")

    @patch('token_dispenser_client_lib.token_dispenser_client.get_tds_arn')
    @patch('token_dispenser_client_lib.token_dispenser_client.invoke_lambda')
    @patch('token_dispenser_client_lib.token_dispenser_client.validate_input')
    def test_get_token(self, mock_validate_input, mock_invoke_lambda, mock_get_tds_arn):
        mock_validate_input.return_value = ''
        mock_get_tds_arn.return_value = ('', 'arn:lambda')
        mock_invoke_lambda.return_value = '{"token": "test_token"}'

        result = get_token('test_client', 300)
        self.assertEqual(result, '{"token": "test_token"}')

        mock_validate_input.return_value = 'Validation Error'
        result = get_token('test_client', 300)
        # '{"statusCode": 422, "body": "Validation Error"}'
        self.assertEqual(json.loads(result).get('statusCode'), 422)
        self.assertEqual(json.loads(result).get('body'), "Validation Error")

        mock_validate_input.return_value = ''
        mock_get_tds_arn.return_value = ('TDS Error', '')
        result = get_token('test_client', 300)
        # '{"statusCode": 500, "body": "TDS Error"}'
        self.assertEqual(json.loads(result).get('statusCode'), 500)
        self.assertEqual(json.loads(result).get('body'), "TDS Error")


if __name__ == '__main__':
    unittest.main()