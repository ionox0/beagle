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
        return "1060973e-66e7-45ca-a36d-2b2e26a78d83" # Return ID of the pipeline

    def get_jobs(self):
        files = self.files.filter(filemetadata__metadata__requestId=self.request_id, filemetadata__metadata__igocomplete=True).all()
        tempo_jobs = list() #  [APIRunCreateSerializer(data={'app': self.get_pipeline_id(), 'inputs': inputs})]

        data = list()
        for file in files:
            sample = dict()
            sample['id'] = file.id
            sample['path'] = file.path
            sample['file_name'] = file.file_name
            filemetadata_id = files.filter(id=file.id).values('filemetadata')[0]['filemetadata']
            sample['metadata'] = self.filemetadata.get(id=filemetadata_id).metadata
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
            tempo_jobs.append((APIRunCreateSerializer(data={'app': self.get_pipeline_id(), 'inputs': tempo_inputs}), job))

        return tempo_jobs # Not returning anything for some reason for inputs; deal with later