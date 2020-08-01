import uuid
import re
import os
from django.db.models import Q
from file_system.models import File, FileGroup, FileType
from rest_framework import serializers
from runner.operator.operator import Operator
from runner.serializers import APIRunCreateSerializer
import runner.operator.tempo_mpgen_operator.bin.tempo_sample as sample_obj
import runner.operator.tempo_mpgen_operator.bin.tempo_patient as patient_obj
from notifier.events import OperatorRequestEvent
from notifier.models import JobGroup
from notifier.tasks import send_notification
from file_system.repository.file_repository import FileRepository
from .construct_tempo_pair import construct_tempo_jobs
from notifier.events import UploadAttachmentEvent
from runner.models import Pipeline
from django.conf import settings
import json
from pathlib import Path
import pickle
import uuid
from beagle import __version__
from datetime import datetime
from file_system.models import File

from notifier.event_handler.jira_event_handler.jira_event_handler import JiraEventHandler

notifier = JiraEventHandler()


class TempoMPGenOperator(Operator):
    def build_recipe_query(self):
        """
        Build complex Q object assay query from given data
        Only does OR queries, as seen in line
           query |= item
        Very similar to build_assay_query, but "metadata__recipe"
        can't be sent as a value, so had to make a semi-redundant function
        """
        data = self.get_recipes()
        data_query_set = [Q(metadata__recipe=value) for value in set(data)]
        query = data_query_set.pop()
        for item in data_query_set:
            query |= item
        return query


    def build_assay_query(self):
        """
        Build complex Q object assay query from given data
        Only does OR queries, as seen in line
           query |= item
        Very similar to build_recipe_query, but "metadata__baitSet"
        can't be sent as a value, so had to make a semi-redundant function
        """
        data = self.get_assays()
        data_query_set = [Q(metadata__baitSet=value) for value in set(data)]
        query = data_query_set.pop()
        for item in data_query_set:
            query |= item
        return query


    def filter_out_missing_fields_query(self):
        """
        This is for legacy purposes - if FileMetadata don't contain sampleClass or cmoSampleName,
        remove them from the file set
        """
        query = Q(metadata__cmoSampleName__isnull=False) & Q(metadata__sampleClass__isnull=False)
        return query


    def get_jobs(self):
        tmpdir = os.path.join(settings.BEAGLE_SHARED_TMPDIR, str(uuid.uuid4()))
        self.OUTPUT_DIR = tmpdir 
        Path(self.OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

        recipe_query = self.build_recipe_query()
        assay_query = self.build_assay_query()
        igocomplete_query = Q(metadata__igocomplete=True)
        missing_fields_query = self.filter_out_missing_fields_query()
        q = recipe_query & assay_query & igocomplete_query & missing_fields_query
        files = FileRepository.all()
        tempo_files = FileRepository.filter(queryset=files, q=q)

        self.send_message("""
            Querying database for the following recipes:
                {recipes}

            Querying database for the following assays/bait sets:
                {assays}
            """.format(recipes="\t\n".join(self.get_recipes()),
                       assays="\t\n".join(self.get_assays()))
                      )

        exclude_query = self.get_exclusions()
        if exclude_query:
            tempo_files = tempo_files.exclude(exclude_query)
        patient_ids = set()
        patient_files = dict()
        no_patient_samples = list()
        for entry in tempo_files:
            patient_id = entry.metadata['patientId']
            if patient_id:
                patient_ids.add(patient_id)
                if patient_id not in patient_files:
                    patient_files[patient_id] = list()
                patient_files[patient_id].append(entry)
            else:
                no_patient_samples.append(entry)

        self.patients = dict()
        self.non_cmo_patients = dict()
        for patient_id in patient_files:
            if "C-" in patient_id[:2]:
                self.patients[patient_id] = patient_obj.Patient(patient_id, patient_files[patient_id])
            else:
                self.non_cmo_patients[patient_id] = patient_obj.Patient(patient_id, patient_files[patient_id])

        input_json = dict()
        # output these strings to file
        input_json['conflict_data'] = self.create_conflict_samples_txt_file()
        input_json['unpaired_data'] = self.create_unpaired_txt_file()
        input_json['mapping_data'] = self.create_mapping_file()
        input_json['pairing_data'] = self.create_pairing_file()
        input_json['tracker_data'] = self.create_tracker_file()

        pickle_file = os.path.join(self.OUTPUT_DIR, "patients_data_pickle")
        fh = open(pickle_file, 'wb')
        pickle.dump(self.patients, fh)
        os.chmod(pickle_file, 0o777)
        self.register_tmp_file(pickle_file)

        input_json['pickle_data'] = { 'class': 'File', 'location': "juno://" + pickle_file }

        beagle_version = __version__
        run_date = datetime.now().strftime("%Y%m%d_%H:%M:%f")

        tags = { "beagle_version": beagle_version,
                "run_date" : run_date}

        app = self.get_pipeline_id()
        pipeline = Pipeline.objects.get(id=app)
        pipeline_version = pipeline.version
        output_directory = pipeline.output_directory

        self.debug_json = input_json

        tempo_mpgen_outputs_job_data = {
            'app': app,
            'inputs': input_json,
            'name': "Tempo mpgen %s" % run_date,
            'tags': tags,
            'output_directory': output_directory,
            'notify_for_outputs': [ 'conflict_file', 'unpaired_file', 'mapping_file', 'pairing_file', 'tracker_file']
        }

        tempo_mpgen_outputs_job = [(APIRunCreateSerializer(
            data=tempo_mpgen_outputs_job_data), input_json)]
        return tempo_mpgen_outputs_job


    def write_to_file(self,fname,s):
        output = os.path.join(self.OUTPUT_DIR, fname)
        with open(output, "w+") as fh:
            fh.write(s)
        os.chmod(output, 0o777)
        self.register_tmp_file(output)
        return { 'class': 'File', 'location': "juno://" + output }


    def register_tmp_file(self, path):
        fname = os.path.basename(path)
        temp_file_group = FileGroup.objects.get(slug="temp")
        file_type = FileType.objects.get(name="txt")
        try:
            File.objects.get(path=path)
        except:
            print("Registering temp file %s" % path)
            f = File(file_name=fname,
                    path=path,
                    file_type=file_type,
                    file_group=temp_file_group)
            f.save()


    def create_unpaired_txt_file(self):
        # Add runDate
        fields = [ 'cmoSampleName', 'patientId', 'sampleId', 'specimenType', 'runMode', 'sampleClass', 'baitSet', 'runDate' ]
        unpaired_string = "\t".join(fields) + "\tPossible Reason?"
        for patient_id in self.patients:
            patient = self.patients[patient_id]
            unpaired_string += patient.create_unpaired_string(fields)
        unpaired_file_event = UploadAttachmentEvent(self.job_group_id, 'sample_unpaired.txt', unpaired_string).to_dict()
#        send_notification.delay(unpaired_file_event)
        return self.write_to_file('sample_unpaired.txt', unpaired_string)


    def send_message(self, msg):
        event = OperatorRequestEvent(self.job_group_id, msg)
        e = event.to_dict()
        send_notification.delay(e)


    def get_recipes(self):
        recipe = [ 
            "Agilent_v4_51MB_Human",
            "IDT_Exome_v1_FP",
            "WholeExomeSequencing",
        ]
        return recipe


    def get_assays(self):
        assays = [
        "Agilent_v4_51MB_Human_hg19_BAITS",
        "IDT_Exome_v1_FP_b37_baits",
        "IDT_Exome_v1_FP_BAITS",
        "SureSelect-All-Exon-V4-hg19"
        ]
        return assays

    def set_juno_uri_from_path(self, path):
        return "juno://" + path


    def create_mapping_file(self):
        mapping_string = "SAMPLE\tTARGET\tFASTQ_PE1\tFASTQ_PE2\tNUM_OF_PAIRS\n"
        for patient_id in self.patients:
            patient = self.patients[patient_id]
            mapping_string += patient.create_mapping_string()
        mapping_file_event = UploadAttachmentEvent(self.job_group_id, 'sample_mapping.txt', mapping_string).to_dict()
        return self.write_to_file('sample_mapping.txt', mapping_string)


    def create_conflict_samples_txt_file(self):       
        fields = [ 'cmoSampleName', 'patientId', 'sampleId', 'specimenType', 'runMode', 'sampleClass', 'baitSet', 'runDate' ]
        conflict_string = "\t".join(fields) + "\t" + "Conflict Reason"
        for patient_id in self.patients:
            patient = self.patients[patient_id]
            conflict_string += patient.create_conflict_string(fields)
        conflict_file_event = UploadAttachmentEvent(self.job_group_id, 'sample_conflict.txt', conflict_string).to_dict()
        return self.write_to_file('sample_conflict.txt', conflict_string)


    def create_pairing_file(self):
        pairing_string = "NORMAL_ID\tTUMOR_ID\n"
        for patient_id in self.patients:
            pairing_string += self.patients[patient_id].create_pairing_string()
        pairing_file_event = UploadAttachmentEvent(self.job_group_id, 'sample_pairing.txt', pairing_string).to_dict()
        return self.write_to_file('sample_pairing.txt', pairing_string)


    def exclude_requests(self,l):
        q = None
        for i in l:
            if q:
                q |= Q(metadata__requestId=i)
            else:
                q = Q(metadata__requestId=i)
        return q
    
    def get_exclusions(self):
        exclude_reqs = ['09315']
        return self.exclude_requests(exclude_reqs)


    def create_tracker_file(self):
        """
        Creates the string for tracker

        String is tab-delimited; special consideration taken so that the first two columns
        is the Tumor/Normal pairing (if the row Sample is a tumor) or 
        Normal/"N/A" (if row sample is a normal)

        The rest of the columns follow the metadata field names in the order set in lists key_order and extra_keys

        key_order has specifically formatted header values, as defined by the PMs, so they needed to be separate;
        extra_keys values are the metadata field names in the database, used as headers
        """
        tracker = ""
        key_order = [ "investigatorSampleId", "externalSampleId", "sampleClass" ]
        key_order += [ "baitSet", "requestId" ]
        extra_keys = [ "tumorOrNormal", "species", "recipe", "specimenType", "sampleId", "patientId" ]
        extra_keys += [ "investigatorName", "investigatorEmail", "piEmail", "labHeadName", "labHeadEmail", "preservation" ]
        extra_keys += [ "dataAnalystName", "dataAnalystEmail", "projectManagerName", "sampleName" ]


        tracker = "CMO_Sample_ID\tMatching_normal\tCollaborator_ID_(or_DMP_Sample_ID)\tHistorical_Investigator_ID_(for_CCS_use)\tSample_Class_(T/N)\tBait_set_(Agilent/_IDT/WGS)\tIGO_Request_ID_(Project_ID)\t"
        for key in extra_keys:
            tracker += key + "\t"
        tracker = tracker.strip() + "\n"

        seen = set()

        for patient_id in self.patients:
            patient = self.patients[patient_id]
            for pair in patient.sample_pairing:
                normal = pair[1]
                tumor = pair[0]
                n_meta = normal.dedupe_metadata_values()
                t_meta = tumor.dedupe_metadata_values()

                running = list()
                running.append(tumor.cmo_sample_name)
                running.append(normal.cmo_sample_name)

                for key in key_order:
                    running.append(t_meta[key])
                for key in extra_keys:
                    running.append(t_meta[key])

                tracker += "\t".join(running) + "\n"

                if normal.cmo_sample_name not in seen:
                    seen.add(normal.cmo_sample_name)
                    running_normal = list()
                    running_normal.append(normal.cmo_sample_name)
                    running_normal.append("N/A")
                    for key in key_order:
                        running_normal.append(n_meta[key])
                    for key in extra_keys:
                        running_normal.append(n_meta[key])
                    tracker += "\t".join(running_normal) + "\n"

        sample_tracker_event = UploadAttachmentEvent(self.job_group_id, 'sample_tracker.txt', tracker).to_dict()
        return self.write_to_file('sample_tracker.txt', tracker)
