import json
import unittest
from scripts.export_public_report import export


class PublicReportTests(unittest.TestCase):
    def test_api_omits_cases_secrets_and_paths(self):
        source = {'suite': 'model', 'dataset_split': 'development', 'total': 4, 'passed': 4,
                  'url': 'secret-url', 'cases': [{'question': 'private-customer'}],
                  'runtime_health': {'token': 'secret-token', 'prompt_version': 'answerability-2.6-restored'}}
        result = export(source, 'api')
        encoded = json.dumps(result)
        self.assertEqual(result['metrics']['passed'], 4)
        for text in ('private-customer', 'secret-token', 'secret-url'):
            self.assertNotIn(text, encoded)

    def test_performance_keeps_metrics_not_request_bodies(self):
        result = export({'backend_label': 'vllm', 'runs': {'4': {'summary': {'requests': 24, 'errors': 0}, 'requests': [{'question': 'private'}]}}}, 'performance')
        self.assertEqual(result['runs']['4']['requests'], 24)
        self.assertNotIn('private', json.dumps(result))

    def test_unexpected_metric_strings_are_rejected(self):
        with self.assertRaises(ValueError):
            export({'suite': 'model', 'dataset_split': 'development', 'passed': 'secret'}, 'api')

    def test_training_does_not_export_local_checkpoint(self):
        result = export({'training': {'train_loss': 0.12}, 'validation': {'eval_loss': 0.19}, 'test_used': False,
                         'best_checkpoint': '/home/private/checkpoint'}, 'training')
        self.assertNotIn('/home/private', json.dumps(result))
