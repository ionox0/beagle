import uuid
from rest_framework import serializers
from runner.operator.operator import Operator
from runner.serializers import APIRunCreateSerializer
from .construct_tempo_pair import construct_tempo_jobs
from .bin.pair_request import compile_pairs
from .bin.make_sample import build_sample

class TempoOperator(Operator):

    def __init__(self, request_id):
        Operator.__init__(self, request_id)

    def get_pipeline_id(self):
        return "5a51cbd3-5fb3-4ab5-a683-14700ee8e7c1" # Return ID of the pipeline

    def get_jobs(self):
        files = self.files.filter(filemetadata__metadata__requestId=self.request_id).all()
        tempo_jobs = list()

        data = list()
        for file in files:
            sample = dict()
            sample['id'] = file.id
            sample['path'] = file.path
            sample['file_name'] = file.file_name
            sample['metadata'] = file.filemetadata_set.first().metadata
            data.append(sample)

        samples = list()
        # group by igoId
        igo_id_group = dict()
        for sample in data:
            igo_id = sample['metadata']['igoId']
            if igo_id not in igo_id_group:
                igo_id_group[igo_id] = list()
            igo_id_group[igo_id].append(sample)

        for igo_id in igo_id_group:
            samples.append(build_sample(igo_id_group[igo_id]))

        tempo_inputs = construct_tempo_jobs(samples)

        for job in tempo_inputs:
            tempo_jobs.append(APIRunCreateSerializer(data={'app': self.get_pipeline_id(), 'inputs': job}))

        return tempo_jobs # Not returning anything for some reason for inputs; deal with later