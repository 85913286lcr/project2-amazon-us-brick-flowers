"""Run the whole pipeline once (FIND on 2023, then VERIFY on 2026), in process, and save a concise run record."""
import json
import os
from datetime import datetime, timezone

import dagster

from definitions import ASSETS, EVIDENCE, FIND, VERIFY, defs, weekly_schedule


def main():
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    job = defs.resolve_job_def('project2_flower_pipeline')
    # With DAGSTER_HOME set the run is stored there, so it also shows up in the Dagster UI.
    instance = dagster.DagsterInstance.get() if os.environ.get('DAGSTER_HOME') else None
    result = job.execute_in_process(raise_on_error=False, instance=instance)
    steps = [a.key.to_user_string() for a in ASSETS]
    succeeded = {e.step_key for e in result.all_events if e.is_step_success}
    report = {
        'dagster_version': dagster.__version__, 'run_id': result.run_id,
        'finished_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'job': job.name, 'schedule': {'name': weekly_schedule.name, 'cron': weekly_schedule.cron_schedule,
                                      'timezone': weekly_schedule.execution_timezone},
        'stages': {'find_2023': [x.key.to_user_string() for x in FIND], 'verify_2026': [x.key.to_user_string() for x in VERIFY]},
        'dependency_order': steps,
        'run_result': 'PASS' if result.success and len(succeeded) == len(steps) else 'FAIL',
        'stage_statuses': {s: 'PASS' if s in succeeded else 'FAIL/NOT_RUN' for s in steps},
        'stage_details': {s: json.loads((EVIDENCE / f'{s}.json').read_text()) for s in steps if s in succeeded},
    }
    (EVIDENCE / 'run_result.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({k: report[k] for k in ('run_id', 'run_result', 'stage_statuses')}, indent=2))
    raise SystemExit(0 if report['run_result'] == 'PASS' else 1)


if __name__ == '__main__':
    main()
