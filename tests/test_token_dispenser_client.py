"""
unit test for the token dispenser client
"""
import unittest
from unittest.mock import patch, MagicMock
import json
from token_dispenser_client.token_dispenser_client import (
    get_parameter_by_name,
    invoke_lambda,
    validate_input,
    get_tds_arn,
    get_token
)


class TestTokenDispenserClient(unittest.TestCase):
    """Test class for token_dispenser_client"""

    @patch('token_dispenser_client.token_dispenser_client.ssm')
    def test_get_parameter_by_name(self, mock_ssm):
        """Test get_parameter_by_name"""
        # Mock the response from SSM
        mock_ssm.get_parameter.return_value = {
            'Parameter': {'Value': 'test_value'}
        }

        result = get_parameter_by_name('test_name')
        self.assertEqual(result, 'test_value')
        mock_ssm.get_parameter.assert_called_once_with(Name='test_name')

    @patch('token_dispenser_client.token_dispenser_client.lambda_client')
    def test_invoke_lambda_success(self, mock_lambda_client):
        """Test invoke_lambda successful cases """
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
        """Test invoke_lambda failure cases """
        # Mock the response from Lambda with an error
        mock_lambda_client.invoke.return_value = {
            'Payload': MagicMock(read=MagicMock(return_value=b'{"error": "failure"}')),
            'FunctionError': 'Handled'
        }

        with self.assertRaises(Exception):
            invoke_lambda('{"param": "value"}', 'test_lambda_arn')

    def test_validate_input(self):
        """Test the validate_input function"""
        # Test valid input
        result = validate_input('client123', 300)
        self.assertEqual(result, [])

        # Test invalid client_id and minimum_alive_secs
        result = validate_input('', 'not_an_int')
        self.assertIn('client_id is required as a string', result)
        self.assertIn('Minimum alive interval, if provided, must be an integer', result)

        # Test invalid client_id pattern. However, this library
        # only verify the client_id type as str
        result = validate_input('invalid_client_id!', 300)
        self.assertEqual(result, [])

        # Test invalid minimum_alive_secs. Client only verify the type as int
        result = validate_input('client123', 4000)
        self.assertEqual(result, [])

    @patch('token_dispenser_client.token_dispenser_client.ssm')
    def test_get_tds_arn_specific_name(self, mock_ssm):
        """Test the get_tds_arn function with specific ssm name"""
        # Mock the response from SSM for a specific name
        mock_ssm.get_parameter.return_value = {
            'Parameter': {'Value': 'test_lambda_arn'}
        }

        result = get_tds_arn('test_ssm_name')
        self.assertEqual(result, 'test_lambda_arn')
        mock_ssm.get_parameter.assert_called_once_with(Name='test_ssm_name')

    @patch('token_dispenser_client.token_dispenser_client.ssm')
    def test_get_tds_arn_default_path(self, mock_ssm):
        """Test the get_tds_arn function with default ssm name"""
        # Mock the response from SSM for the default path
        mock_ssm.get_parameters_by_path.return_value = {
            'Parameters': [{'Name': 'test_param', 'Value': 'test_lambda_arn'}]
        }

        result = get_tds_arn(None)
        self.assertEqual(result, 'test_lambda_arn')

        mock_ssm.get_parameters_by_path.assert_called_once_with(
            Path='/service/token-dispenser',
            Recursive=True,
            MaxResults=2
        )

    @patch('token_dispenser_client.token_dispenser_client.get_tds_arn')
    @patch('token_dispenser_client.token_dispenser_client.invoke_lambda')
    def test_get_token(self, mock_invoke_lambda, mock_get_tds_arn):
        """Test the get_token function"""
        # Mock the TDS ARN and Lambda invocation
        mock_get_tds_arn.return_value = 'test_lambda_arn'
        mock_invoke_lambda.return_value = '{"token": "test_token"}'

        result = get_token('client123', 300)
        self.assertEqual(json.dumps(result), '{"token": "test_token"}')
        mock_get_tds_arn.assert_called_once_with(None)
        data = {
            "client_id": 'client123',
            "minimum_alive_secs": 300
        }
        json_data = json.dumps(data)
        mock_invoke_lambda.assert_called_once_with(
            input_params_json=json_data,
            lambda_arn='test_lambda_arn'
        )


if __name__ == '__main__':
    unittest.main()
