"""""""""""""""""""""""""""""
" ACCESS-Pipeline
" github.com/mskcc/access-pipeline
"""""""""""""""""""""""""""""

from collections import defaultdict
from itertools import groupby
from runner.operator.operator import Operator
from runner.serializers import APIRunCreateSerializer
from file_system.repository.file_repository import FileRepository

from notifier.events import InputCreationFailedEvent
from notifier.tasks import send_notification

import json
from jinja2 import Template

REQUIRED_META_FIELDS = [
    "cmoSampleName",
    "requestId",
    "tumorOrNormal",
]

REQUIRED_INPUT_FIELDS = [
    "read_group_identifier",
    "read_group_sequencing_center",
    "read_group_library",
    "read_group_platform_unit",
    "read_group_sequencing_platform",
    "output_name_collapsed_gzip_R1",
    "output_name_collapsed_gzip_R2",
    "standard_aln_output_file_name",
    "standard_picard_addrg_output_filename",
    "collapsing_aln_output_file_name",
    "collapsing_picard_output_file_name",
    "sort_first_pass_output_file_name",
]

ADAPTER = "GATCGGAAGAGC"
ADAPTER2 = "AGATCGGAAGAGC"
SAMPLE_GROUP_SIZE = 20

"""
This returns a list of keys that are subset of `fields`, that do not exist
in source or exist with an empty value.
"""
def get_missing_fields(source, fields):
    return filter(lambda field: field not in source or not source[field], fields)


def construct_title_file(samples):
    return "path_to_title_file"

def construct_sample_inputs(samples):
    with open('runner/operator/access/v1_0_0/legacy/input_template.json.jinja2') as file:
        template = Template(file.read())

    sample_inputs = list()
    errors = 0

    # Pair FASTQs
    sample_pairs = groupby(samples, lambda x: x["metadata"]["sampleId"])

    for sample_group in chunks(sample_pairs, SAMPLE_GROUP_SIZE):
        meta = sample_group[0]["metadata"]

        missing_fields = get_missing_fields(meta, REQUIRED_META_FIELDS)
        if missing_fields:
            ic_error = InputCreationFailedEvent(
                "The follwing fields are missing from the input: {}", ",".join(missing_fields)
                group_id,
                meta["requestId"],
                sample_id
            ).to_dict()
            send_notification.delay(ic_error)
            errors += 1
            continue

        barcodeIds = []
        tumorOrNormals = []
        cmoSampleNames = []
        patientIds = []
        add_rg_LBs = [1] * SAMPLE_GROUP_SIZE
        adapters = [ADAPTER] * SAMPLE_GROUP_SIZE
        adapters2 = [ADAPTER2] * SAMPLE_GROUP_SIZE
        title_file_path = construct_title_file(samples)
        fastq1_files = []
        fastq2_files = []

        for sample in sample_group:
            add_rg_PU.append(meta["barcodeId"])
            sample_class.append(meta["tumorOrNormal"])
            add_rg_SM.append(meta["cmoSampleName"])
            patient_id.append(meta["cmoPatientId"])
            add_rg_LBs.append(1)
            fastq1_files.append({
                "class": "File",
                "path": "juno://" + sample_group[0]["path"]
            })

            fastq2_files.append({
                "class": "File",
                "path": "juno://" + sample_group[1]["path"]
            })

        input_file = template.render(
            barcodeIds=bardcodeIds,
            tumorOrNormals=tumorOrNormals,
            cmoSampleNames=cmoSampleNames,
            add_rg_LBs=add_rg_LBs,
            adapters=adapters,
            adapters2=adapters2,
            fastq1_files=fastq1_files,
            fastq2_files=fastq2_files,
            title_file_path=title_file_path,
            request_id=meta["requestId"],
        )

        sample = json.loads(input_file)

        missing_fields = get_missing_fields(sample, REQUIRED_INPUT_FIELDS)
        if missing_fields:
            ic_error = InputCreationFailedEvent(
                "The follwing fields are missing from the input: {}", ",".join(missing_fields)
                group_id,
                meta["requestId"],
                sample_id
            ).to_dict()
            send_notification.delay(ic_error)
            errors += 1
            continue

        sample_inputs.append(sample)

    return (sample_inputs, errors)

class AccessFastqToBamOperator(Operator):
    def get_jobs(self):
        files = FileRepository.filter(queryset=self.files,
                                      metadata={'requestId': self.request_id,
                                                'igocomplete': True})
        data = [
            {
                "id": f.file.id,
                "path": f.file.path,
                "file_name": f.file.file_name,
                "metadata": f.metadata
            } for f in files
        ]

        (sample_inputs, no_of_errors) = construct_sample_inputs(data)
        if no_of_errors:
            return

        number_of_inputs = len(sample_inputs)

        return [
            (
                APIRunCreateSerializer(
                    data={
                        'name': "ACCESS M1: %s, %i of %i" % (self.request_id, i + 1, number_of_inputs),
                        'app': self.get_pipeline_id(),
                        'inputs': job,
                        'tags': {'requestId': self.request_id, 'sampleId': job.cmo_sample_name}}
                ),
                job
             )

            for i, job in enumerate(sample_inputs)
        ]


def chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]