"""
Unit tests for the token dispenser client
"""
import unittest
from unittest.mock import patch, MagicMock
import json
from token_dispenser_client.token_dispenser_client import (
    invoke_lambda,
    validate_input,
    get_tds_arn,
    get_token
)


class TestTokenDispenserClient(unittest.TestCase):

    @patch('token_dispenser_client.token_dispenser_client.lambda_client')
    def test_invoke_lambda_success(self, mock_lambda_client):
        # Mock the response from Lambda
        mock_lambda_client.invoke.return_value = {
            'Payload': MagicMock(read=MagicMock(return_value=b'{"result": "success"}'))
        }

        result = invoke_lambda('{"param": "value"}', 'test_lambda_arn')
        self.assertEqual(result, '{"result": "success"}')
        mock_lambda_client.invoke.assert_called_once_with(
            FunctionName='test_lambda_arn',
            InvocationType='RequestResponse',
            Payload='{"param": "value"}'
        )


    @patch('token_dispenser_client.token_dispenser_client.lambda_client')
    def test_invoke_lambda_failure(self, mock_lambda_client):
        # Mock the response from Lambda with an error
        mock_lambda_client.invoke.return_value = {
            'Payload': MagicMock(read=MagicMock(return_value=b'{"error": "failure"}')),
            'FunctionError': 'Handled'
        }

        with self.assertRaises(RuntimeError):
            invoke_lambda('{"param": "value"}', 'test_lambda_arn')


    def test_validate_input(self):
        # Test valid input
        result = validate_input('client123', 300)
        self.assertEqual(result, [])

        # Test invalid client_id and minimum_alive_secs
        result = validate_input('', 'not_an_int')
        self.assertIn('client_id is required as a string', result)
        self.assertIn('Minimum alive interval, if provided, must be an integer', result)


    @patch('token_dispenser_client.token_dispenser_client.ssm')
    def test_get_tds_arn_single_value(self, mock_ssm):
        # Mock the response from SSM for a single value
        mock_ssm.get_parameters_by_path.return_value = {
            'Parameters': [{'Name': 'test_param', 'Value': 'test_lambda_arn'}]
        }

        result = get_tds_arn()
        self.assertEqual(result, 'test_lambda_arn')
        mock_ssm.get_parameters_by_path.assert_called_once_with(
            Path='/service/token-dispenser',
            Recursive=True,
            MaxResults=2
        )


    @patch('token_dispenser_client.token_dispenser_client.ssm')
    def test_get_tds_arn_multiple_values(self, mock_ssm):
        # Mock the response from SSM for multiple values
        mock_ssm.get_parameters_by_path.return_value = {
            'Parameters': [
                {'Name': 'test_param1', 'Value': 'test_lambda_arn1'},
                {'Name': 'test_param2', 'Value': 'test_lambda_arn2'}
            ]
        }

        with self.assertRaises(ValueError):
            get_tds_arn()


    @patch('token_dispenser_client.token_dispenser_client.ssm')
    def test_get_tds_arn_no_values(self, mock_ssm):
        # Mock the response from SSM for no values
        mock_ssm.get_parameters_by_path.return_value = {'Parameters': []}

        with self.assertRaises(ValueError):
            get_tds_arn()


    @patch('token_dispenser_client.token_dispenser_client.get_tds_arn')
    @patch('token_dispenser_client.token_dispenser_client.invoke_lambda')
    def test_get_token(self, mock_invoke_lambda, mock_get_tds_arn):
        # Mock the TDS ARN and Lambda invocation
        mock_get_tds_arn.return_value = 'test_lambda_arn'
        mock_invoke_lambda.return_value = '{"token": "test_token"}'

        result = get_token('client123', 300)
        self.assertEqual(result, {"token": "test_token"})
        mock_get_tds_arn.assert_called_once_with()
        mock_invoke_lambda.assert_called_once_with(
            # input_params_json=json.dumps({"client_id": "client123", "minimum_alive_secs": 300}),
            # input_params=dict(client_id='client123', minimum_alive_secs=300),
            # lambda_arn='test_lambda_arn'
            input_params_json='{"client_id": "client123"}', lambda_arn='test_lambda_arn'
        )


if __name__ == '__main__':
    unittest.main()
