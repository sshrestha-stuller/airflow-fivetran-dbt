
# -*- coding: utf-8 -*-
import json
import requests
import time
from datetime import datetime

class DbtCloudApi(object):
    """
    Class for interacting with the dbt Cloud API
    * :py:meth:`list_jobs` - list all Jobs for the specified Account ID
    * :py:meth:`get_run` - Get information about a specified Run ID
    * :py:meth:`trigger_job_run` - Trigger a Run for a specified Job ID
    * :py:meth: `try_get_run` - Attempts to get information about a specific Run ID for up to max_tries
    * :py:meth: `run_job` - Triggers a run for a job using the job name
    """

    def __init__(self, account_id, api_token, airflow_datetime_format, dbt_datetime_format):
        self.account_id = account_id
        self.api_token = api_token
        self.api_base = 'https://cloud.getdbt.com/api/v2'
        self.airflow_datetime_format = airflow_datetime_format
        self.dbt_datetime_format = dbt_datetime_format

    def _get(self, url_suffix):
        url = self.api_base + url_suffix
        headers = {'Authorization': 'Token %s' % self.api_token}
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return json.loads(response.content)
        else:
            raise RuntimeError(response.content)

    def _post(self, url_suffix, data=None):
        url = self.api_base + url_suffix
        print('request url: ', url)
        print('showing request body: ', json.dumps(data))
        headers = {'Content-Type': 'application/json', 'Authorization': 'Token %s' % self.api_token}

        response = requests.post(url, data=json.dumps(data), headers=headers)
        
        if response.status_code == 200:
            return json.loads(response.content)
        else:
            raise RuntimeError(response.text)

    def list_jobs(self, **kwargs):
        return self._get('/accounts/%s/jobs/' % self.account_id).get('data')

    def get_run(self, run_id, **kwargs):
        return self._get('/accounts/%s/runs/%s/' % (self.account_id, run_id)).get('data')

    def trigger_job_run(self, job_id, data=None):

        return self._post(url_suffix='/accounts/%s/jobs/%s/run/' % (self.account_id, job_id), data=data).get('data')
        
    def get_dbt_job_run_status(self, max_tries=3, **kwargs):
        
        ti = kwargs['ti']
        run_id = ti.xcom_pull(key='dbt_run_id', task_ids='dbt_job')
        dbt_job_run_start_time = ti.xcom_pull(key = 'dbt_run_start_time', task_ids='dbt_job')
        dbt_job_run_start_time = datetime.strptime(dbt_job_run_start_time, self.airflow_datetime_format)
        
        tracker = 0
        poll_for_success = True
        #while poll_for_success:
            # wait a few ticks before polling for the run status
        #    time.sleep(5)
            
            # check finished_at from runtime
        run_response = self.get_run(run_id=run_id)
        run_finish_time = run_response['finished_at']

        #run_finish_time = datetime.strptime(run_finish_time, self.dbt_datetime_format)
            
        return f'run start: {str(dbt_job_run_start_time)} -- run finish: {str(run_finish_time)}'

        # for i in range(max_tries):
        #     try:
        #         run = self.get_run(run_id)
        #         return run
            
        #     sexcept RuntimeError as e:
        #         print("Encountered a runtime error while fetching status for {}".format(run_id))
        #         time.sleep(10)

        # raise RuntimeError("Too many failures ({}) while querying for run status".format(run_id))

    def run_job(self, **kwargs):
        job_name = kwargs['dag_run'].conf['dbt_job_name']

        jobs = self.list_jobs()

        job_matches = [j for j in jobs if j['name'] == job_name]

        if len(job_matches) != 1:
            raise Exception("{} jobs found for {}".format(len(job_matches), job_name))

        job_def = job_matches[0]

        data = {
            "cause": "triggered from Airflow"
        }

        run_start_time = datetime.now()
        trigger_resp = self.trigger_job_run(job_id=job_def['id'], data=data)
        
        run_id = trigger_resp['id']
        kwargs['ti'].xcom_push(key='dbt_run_id', value=str(run_id))
        kwargs['ti'].xcom_push(key='dbt_run_start_time', value=str(run_start_time))

        return {
            'message': f'successfully triggered job {job_name}',
            'response': trigger_resp
        }

    def create_job(self, data=None, **kwargs):
        return self._post(url_suffix='/accounts/%s/jobs/' % (self.account_id), data=data)

    def update_job(self, job_id, data=None, **kwargs):
        return self._post(url_suffix='/accounts/%s/jobs/%s/' % (self.account_id, job_id), data=data)
