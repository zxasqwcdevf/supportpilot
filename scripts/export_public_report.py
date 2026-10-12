"""Export aggregate metrics only; never export request text or local configuration."""
import argparse
import hashlib
import json
import math
from pathlib import Path

KEYS = set('all by_task answerability direct_evidence total passed metrics decision json_object reference_ids schema user_facts rate confusion tp tn fp fn invalid latency_ms p50 p95 count p50_ms p95_ms all_requests local_llm_responses non_llm_responses request_errors requests completed_without_pipeline_error errors successful_p50_ms successful_p95_ms all_p95_ms wall_seconds completed_requests_per_second train_runtime train_samples_per_second train_steps_per_second total_flos train_loss epoch eval_loss eval_runtime eval_samples_per_second eval_steps_per_second elapsed_seconds_including_model_load peak_allocated_gib peak_reserved_gib shared_peak_allocated_gib test_used smoke'.split())


def numeric_metrics(value):
    if isinstance(value, dict):
        return {key: numeric_metrics(item) for key, item in value.items() if key in KEYS}
    if value is None or type(value) is bool or type(value) is int:
        return value
    if type(value) is float and math.isfinite(value):
        return value
    raise ValueError('Unexpected non-numeric metric value')


def export(source, kind):
    result = {'export_version': '1.0', 'kind': kind,
              'scope': 'aggregate_metrics_only', 'provenance': 'user_provided_WSL_report',
              'limitations': 'Source text, cases, paths and environment details omitted. Aggregates are not an independent rerun.'}
    if kind == 'performance':
        if source.get('backend_label') not in ('transformers', 'vllm'):
            raise ValueError('Unexpected backend')
        result['backend'] = source['backend_label']
        result['runs'] = {key: numeric_metrics(run['summary']) for key, run in source['runs'].items() if key in ('1', '2', '4')}
    elif kind == 'comparison':
        if source.get('split') not in ('validation', 'test'):
            raise ValueError('Unexpected split')
        result['split'] = source['split']
        result['metrics'] = {mode: numeric_metrics(source['summary'][mode]) for mode in ('base', 'adapter')}
        result['test_used'] = source['test_used']
        if source.get('prompt_profile') in ('saved', 'explicit-v2', 'explicit-v3'):
            result['prompt_profile'] = source['prompt_profile']
        result['reference_correction_count'] = len(source.get('reference_corrections', []))
        result['timings_reused'] = source.get('timings_reused', False)
    elif kind == 'training':
        result['training'] = numeric_metrics(source['training'])
        result['validation'] = numeric_metrics(source['validation'])
        result['metrics'] = numeric_metrics(source)
    elif kind == 'api':
        if source.get('suite') not in ('rules', 'model') or source.get('dataset_split') not in ('development', 'validation', 'final'):
            raise ValueError('Unexpected API suite or dataset')
        result['suite'] = source['suite']
        result['split'] = source['dataset_split']
        result['metrics'] = numeric_metrics(source)
        result['latency_groups'] = numeric_metrics(source.get('latency_groups', {}))
        prompt = source.get('runtime_health', {}).get('prompt_version')
        if prompt in ('answerability-2.3', 'answerability-2.4-explicit-v3', 'answerability-2.5-correction', 'answerability-2.6-restored'):
            result['prompt_version'] = prompt
    else:
        raise ValueError('Unknown report kind')
    for key in ('dataset_sha256', 'policies_sha256'):
        value = source.get(key)
        if isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value):
            result[key] = value
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--kind', choices=['performance', 'comparison', 'training', 'api'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    raw = args.source.read_bytes()
    result = export(json.loads(raw), args.kind)
    result['source_sha256'] = hashlib.sha256(raw).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(f'Exported aggregate report: {args.output}')


if __name__ == '__main__':
    main()
