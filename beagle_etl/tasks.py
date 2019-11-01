import logging
import importlib
import datetime
from celery import shared_task
from django.db import transaction
from beagle_etl.models import JobStatus, Job
from beagle_etl.jobs.lims_etl_jobs import TYPES


logger = logging.getLogger(__name__)


@shared_task
def fetch_requests_lims():
    logger.info("Fetching requestIDs")
    latest = Job.objects.filter(run=TYPES['DELIVERY']).order_by('-created_date').first()
    timestamp = None
    if latest:
        timestamp = int(latest.created_date.timestamp()) * 1000
    else:
        timestamp = int((datetime.datetime.now() - datetime.timedelta(hours=120)).timestamp()) * 1000
    job = Job(run='beagle_etl.jobs.lims_etl_jobs.fetch_new_requests_lims', args={'timestamp': timestamp},
              status=JobStatus.CREATED,
              max_retry=3, children=[])
    job.save()
    logger.info("Fetching fetch_new_requests_lims job created")


@shared_task
def job_processor(job_id):
    logger.info("Creating job: %s" % str(job_id))
    job = JobObject(job_id)
    logger.info("Processing job: %s with args: %s" % (str(job.job.id), str(job.job.args)))
    job.process()


@shared_task
def scheduler():
    jobs = get_pending_jobs()
    logger.info("Pending jobs: %s" % jobs)
    for job in jobs:
        with transaction.atomic():
            j = Job.objects.get(id=job.id)
            if not j.lock:
                logger.info("Submitting job: %s" % str(job.id))
                j.lock = True
                j.save()
                job_processor.delay(j.id)
            else:
                logger.info("Job already locked: %s" % str(job.id))


def get_pending_jobs():
    jobs = Job.objects.filter(status__in=(JobStatus.CREATED, JobStatus.IN_PROGRESS, JobStatus.WAITING_FOR_CHILDREN))
    return jobs


class JobObject(object):
    logger = logging.getLogger(__name__)

    def __init__(self, job_id):
        self.job = Job.objects.get(id=job_id)

    def process(self):
        if self.job.status == JobStatus.CREATED:
            self.job.status = JobStatus.IN_PROGRESS

        elif self.job.status == JobStatus.IN_PROGRESS:
            self.job.retry_count = self.job.retry_count + 1
            try:
                self._process()
                self.job.status = JobStatus.WAITING_FOR_CHILDREN
            except Exception as e:
                if self.job.retry_count == self.job.max_retry:
                    self.job.status = JobStatus.FAILED
                    self.job.message = {"details": "Error: %s" % e}

        elif self.job.status == JobStatus.WAITING_FOR_CHILDREN:
            self._check_children()

        with transaction.atomic():
            self.job.lock = False
            self.job.save()

        logger.info("Job %s in status: %s" % (str(self.job.id), JobStatus(self.job.status).name))
        self._save()

    def _save(self):
        self.job.save()

    def _process(self):
        mod_name, func_name = self.job.run.rsplit('.', 1)
        mod = importlib.import_module(mod_name)
        func = getattr(mod, func_name)
        children = func(**self.job.args)
        self.job.children = children or []

    def _check_children(self):
        status = JobStatus.COMPLETED
        for child_id in self.job.children:
            try:
                child_job = Job.objects.get(id=child_id)
            except Job.DoesNotExist:
                status = JobStatus.FAILED
                self.job.message = {"details": "Child job %s does't exist!" % child_id}
                break
            if child_job.status == JobStatus.FAILED:
                status = JobStatus.FAILED
                self.job.message = {"details": "Child job %s failed" % child_id}
                break
            if child_job.status in (JobStatus.IN_PROGRESS, JobStatus.CREATED):
                status = JobStatus.WAITING_FOR_CHILDREN
                break
        self.job.status = status
        # Create OperatorJob