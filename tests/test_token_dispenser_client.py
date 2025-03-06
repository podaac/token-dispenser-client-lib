import unittest
from unittest.mock import patch, MagicMock
import json
import re
from token_dispenser_client.token_dispenser_client import (
    get_parameter_by_name,
    get_parameters_by_path,
    invoke_lambda,
    validate_input,
    get_tds_arn,
    get_token,
    _DEFAULT_SSM_PATH_
)

class TestTokenDispenserClient(unittest.TestCase):

    @patch('token_dispenser_client.token_dispenser_client.ssm')
    def test_get_parameter_by_name(self, mock_ssm):
        mock_ssm.get_parameter.return_value = {'Parameter': {'Value': 'test_value'}}
        result = get_parameter_by_name('test_name')
        self.assertEqual(result, 'test_value')

        mock_ssm.get_parameter.assert_called_once_with(Name='test_name', WithDecryption=False)


    @patch('token_dispenser_client.token_dispenser_client.ssm')
    def test_get_parameters_by_path(self, mock_ssm):
        # Use side_effect for more complicated call and return values
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
        with self.assertRaises(Exception):
            get_parameters_by_path('/exception')


    @patch('token_dispenser_client.token_dispenser_client.lambda_client')
    def test_invoke_lambda(self, mock_lambda):
        mock_lambda.invoke.return_value = {'Payload': MagicMock(read=MagicMock(return_value=b'{"result": "success"}'))}
        result = invoke_lambda('{"input": "test"}', 'arn:aws:lambda:us-east-1:123456789012:function:test_function')
        self.assertEqual(result, '{"result": "success"}')

        mock_lambda.invoke.return_value = {'Payload': MagicMock(read=MagicMock(return_value=b'{"result": "success"}')), 'FunctionError': 'Some Error'}
        result = invoke_lambda('{"input": "test"}', 'arn:aws:lambda:us-east-1:123456789012:function:test_function')
        self.assertTrue(result.startswith("Error: Lambda function error:"))

        self.assertEqual(invoke_lambda('invalid_json', 'arn'), "Error: Invalid JSON : invalid_json")
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


    @patch('token_dispenser_client.token_dispenser_client.get_parameters_by_path')
    @patch('token_dispenser_client.token_dispenser_client.get_parameter_by_name')
    def test_get_tds_arn(self, mock_get_parameter_by_name, mock_get_parameters_by_path):
        mock_get_parameters_by_path.return_value = {'/service/token-dispenser/test': 'arn:aws:lambda:region:account-id:function:function-name'}
        self.assertEqual(get_tds_arn(None), 'arn:aws:lambda:region:account-id:function:function-name')
        mock_get_parameters_by_path.assert_called_once_with(path='/service/token-dispenser', with_decryption=False)

        mock_get_parameter_by_name.return_value = 'arn:aws:lambda:region:account-id:function:function-name'
        self.assertEqual(get_tds_arn('specific_name'), 'arn:aws:lambda:region:account-id:function:function-name')
        mock_get_parameter_by_name.assert_called_once_with(name='specific_name', with_decryption=False)


    @patch('token_dispenser_client.token_dispenser_client.invoke_lambda')
    @patch('token_dispenser_client.token_dispenser_client.get_tds_arn')
    @patch('token_dispenser_client.token_dispenser_client.validate_input')
    def test_get_token(self, mock_validate_input, mock_get_tds_arn, mock_invoke_lambda):
        mock_validate_input.return_value = ''
        mock_get_tds_arn.return_value = 'arn:aws:lambda:region:account-id:function:function-name'
        mock_invoke_lambda.return_value = '{"token": "test_token"}'

        result = get_token('client123', 300)
        self.assertEqual(result, '{"token": "test_token"}')
        mock_validate_input.assert_called_once_with(client_id='client123', minimum_alive_secs=300)
        mock_get_tds_arn.assert_called_once_with(None)
        mock_invoke_lambda.assert_called_once_with(
            input_params_json=json.dumps(dict(client_id='client123', minimum_alive_secs=300)),
            lambda_arn='arn:aws:lambda:region:account-id:function:function-name'
        )


if __name__ == '__main__':
    unittest.main()
