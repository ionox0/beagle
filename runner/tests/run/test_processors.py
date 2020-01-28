import uuid
from rest_framework import status
from dictdiffer import diff
from runner.run.processors.port_processor import PortProcessor, PortAction
from rest_framework.test import APITestCase
from file_system.models import Storage, StorageType, FileGroup, File, FileType, FileMetadata


class ProcessorTest(APITestCase):

    def setUp(self):
        self.storage = Storage(name="test", type=StorageType.LOCAL)
        self.storage.save()
        self.file_group = FileGroup(name="Test Files", storage=self.storage)
        self.file_group.save()
        self.file_type_fasta = FileType(ext='fasta')
        self.file_type_fasta.save()
        self.file_type_vcf = FileType(ext='vcf')
        self.file_type_vcf.save()
        self.file_type_txt = FileType(ext='txt')
        self.file_type_txt.save()
        self.file_type_tsv = FileType(ext='tsv')
        self.file_type_tsv.save()
        self.file_type_maf = FileType(ext='maf')
        self.file_type_maf.save()
        self.file1 = File(
            file_name="S16_R1_001.fastq.gz",
            path="/path/to/file/S16_R1_001.fastq.gz",
            file_type=self.file_type_fasta, size=5966546453, file_group=self.file_group)
        self.file1.save()
        self.file2 = File(
            file_name="S16_R2_001.fastq.gz",
            path="/path/to/file/S16_R2_001.fastq.gz",
            file_type=self.file_type_fasta, size=5832468368, file_group=self.file_group)
        self.file2.save()
        self.file3 = File(
            file_name="P-S12_R1_001.fastq.gz",
            path="/path/to/file/Sample_P/P-S12_R1_001.fastq.gz",
            file_type=self.file_type_fasta, size=3576965127, file_group=self.file_group)
        self.file3.save()
        self.file4 = File(
            file_name="P-S12_R2_001.fastq.gz",
            path="/path/to/file/Sample_P/P-S12_R2_001.fastq.gz",
            file_type=self.file_type_fasta, size=3592299152, file_group=self.file_group)
        self.file4.save()
        self.file5 = File(
            file_name="refGene_b37.sorted.txt",
            path="/path/to/file/refGene_b37.sorted.txt",
            file_type=self.file_type_fasta, size=359229, file_group=self.file_group)
        self.file5.save()
        self.file6 = File(
            file_name="dbsnp_137.b37__RmDupsClean__plusPseudo50__DROP_SORT.vcf.gz",
            path="/path/to/file/dbsnp_137.b37__RmDupsClean__plusPseudo50__DROP_SORT.vcf.gz",
            file_type=self.file_type_vcf, size=359228, file_group=self.file_group)
        self.file6.save()
        self.file7 = File(
            file_name="FP_tiling_genotypes.txt",
            path="/path/to/file/FP_tiling_genotypes.txt",
            file_type=self.file_type_vcf, size=359228, file_group=self.file_group)
        self.file7.save()
        self.file8 = File(
            file_name="hotspot-list-union-v1-v2.txt",
            path="/path/to/file/hotspot-list-union-v1-v2.txt",
            file_type=self.file_type_vcf, size=359228, file_group=self.file_group)
        self.file8.save()
        self.file9 = File(
            file_name="human.hg19.excl.tsv",
            path="/path/to/file/human.hg19.excl.tsv",
            file_type=self.file_type_tsv, size=359228, file_group=self.file_group)
        self.file9.save()
        self.file10 = File(
            file_name="IDT_Exome_v1_FP_b37_baits.ilist",
            path="/path/to/file/IDT_Exome_v1_FP_b37_baits.ilist",
            file_type=self.file_type_tsv, size=359228, file_group=self.file_group)
        self.file10.save()
        self.file11 = File(
            file_name="hotspot-list-union-v1-v2.maf",
            path="/path/to/file/hotspot-list-union-v1-v2.maf",
            file_type=self.file_type_maf, size=359228, file_group=self.file_group)
        self.file11.save()
        self.file12 = File(
            file_name="IDT_Exome_v1_FP_b37_targets.ilist",
            path="/path/to/file/IDT_Exome_v1_FP_b37_targets.ilist",
            file_type=self.file_type_maf, size=359228, file_group=self.file_group)
        self.file12.save()
        self.file13 = File(
            file_name="FP_tiling_intervals.intervals",
            path="/path/to/file/FP_tiling_intervals.intervals",
            file_type=self.file_type_maf, size=359228, file_group=self.file_group)
        self.file13.save()



    def test_convert_list_to_bid(self):
        port_value_list = [
            {
                "CN": "MSKCC",
                "ID": "TEST_ID_1",
                "LB": "TEST_LB_1",
                "PL": "Illumina",
                "PU": [
                    "TEST_PU_1"
                ],
                "R1": [
                    {
                        "location": "juno:///path/to/file/S16_R1_001.fastq.gz",
                        "size": 5966546453,
                        "class": "File"
                    }
                ],
                "R2": [
                    {
                        "location": "juno:///path/to/file/S16_R2_001.fastq.gz",
                        "size": 5832468368,
                        "class": "File"
                    }
                ],
                "bam": [],
                "zR1": [],
                "zR2": [],
                "RG_ID": [
                    "TEST_RG_ID_1"
                ],
                "adapter": "AGATCGGAAGAGCACACGTCTGAACTCCAGTCACATGAGCATCTCGTATGCCGTCTTCTGCTTG",
                "adapter2": "AGATCGGAAGAGCGTCGTGTAGGGAAAGAGTGTAGATCTCGGTGGTCGCCGTATCATT",
                "bwa_output": "bwa_output_1.bam"
            },
            {
                "CN": "MSKCC",
                "ID": "TEST_ID_2",
                "LB": "TEST_LB_2",
                "PL": "Illumina",
                "PU": [
                    "TEST_PU_2"
                ],
                "R1": [
                    {
                        "location": "juno:///path/to/file/Sample_P/P-S12_R1_001.fastq.gz",
                        "size": 3576965127,
                        "class": "File"
                    }
                ],
                "R2": [
                    {
                        "location": "juno:///path/to/file/Sample_P/P-S12_R2_001.fastq.gz",
                        "size": 3592299152,
                        "class": "File"
                    }
                ],
                "bam": [],
                "zR1": [],
                "zR2": [],
                "RG_ID": [
                    "TEST_RG_ID_2"
                ],
                "adapter": "AGATCGGAAGAGCACACGTCTGAACTCCAGTCACATGAGCATCTCGTATGCCGTCTTCTGCTTG",
                "adapter2": "AGATCGGAAGAGCGTCGTGTAGGGAAAGAGTGTAGATCTCGGTGGTCGCCGTATCATT",
                "bwa_output": "bwa_output_2.bam"
            }
        ]
        result = PortProcessor.process_files(port_value_list, PortAction.CONVERT_TO_BID, None)
        difference = diff(port_value_list, result)
        difference = list(difference)
        self.assertEqual(difference[0][0], 'change')
        self.assertEqual(difference[0][1][0], 0)
        self.assertEqual(difference[0][1][1], 'R1')
        self.assertEqual(difference[0][1][2], 0)
        self.assertEqual(difference[0][1][3], 'location')
        self.assertEqual(difference[0][2][0], 'juno://%s' % self.file1.path)
        self.assertEqual(difference[0][2][1], 'bid://%s' % str(self.file1.id))
        self.assertEqual(difference[0][0], 'change')

        self.assertEqual(difference[1][1][0], 0)
        self.assertEqual(difference[1][1][1], 'R2')
        self.assertEqual(difference[1][1][2], 0)
        self.assertEqual(difference[1][1][3], 'location')
        self.assertEqual(difference[1][2][0], 'juno://%s' % self.file2.path)
        self.assertEqual(difference[1][2][1], 'bid://%s' % str(self.file2.id))

        self.assertEqual(difference[2][1][0], 1)
        self.assertEqual(difference[2][1][1], 'R1')
        self.assertEqual(difference[2][1][2], 0)
        self.assertEqual(difference[2][1][3], 'location')
        self.assertEqual(difference[2][2][0], 'juno://%s' % self.file3.path)
        self.assertEqual(difference[2][2][1], 'bid://%s' % str(self.file3.id))

        self.assertEqual(difference[3][1][0], 1)
        self.assertEqual(difference[3][1][1], 'R2')
        self.assertEqual(difference[3][1][2], 0)
        self.assertEqual(difference[3][1][3], 'location')
        self.assertEqual(difference[3][2][0], 'juno://%s' % self.file4.path)
        self.assertEqual(difference[3][2][1], 'bid://%s' % str(self.file4.id))

    def test_convert_dict_to_bid(self):
        port_value_dict = {
            "test_data": "string_value",
            "test_data_none": None,
            "test_data_int": 2,

            "refseq": {
                "location": "juno:///path/to/file/refGene_b37.sorted.txt",
                "class": "File"
            },
            "double_list_test": [[{
                "location": "juno:///path/to/file/dbsnp_137.b37__RmDupsClean__plusPseudo50__DROP_SORT.vcf.gz",
                "class": "File"
            }]],
            "conpair_markers_bed": "string_value_bed",
            "double_nested_port_list": [{
                "nested_port_list_1": [
                    {
                        "bait_intervals_1": {
                            "location": "juno:///path/to/file/IDT_Exome_v1_FP_b37_baits.ilist",
                            "class": "File"
                        },
                        "bait_intervals_2": {
                            "location": "juno:///path/to/file/IDT_Exome_v1_FP_b37_baits.ilist",
                            "class": "File"
                        }
                    }
                ]
            }]
        }
        result = PortProcessor.process_files(port_value_dict, PortAction.CONVERT_TO_BID, None)
        difference = diff(port_value_dict, result)
        difference = list(difference)

        self.assertEqual(difference[0][0], 'change')
        self.assertEqual(difference[0][1], 'refseq.location')
        self.assertEqual(difference[0][2][0], 'juno://%s' % self.file5.path)
        self.assertEqual(difference[0][2][1], 'bid://%s' % str(self.file5.id))

        self.assertEqual(difference[1][0], 'change')
        self.assertEqual(difference[1][1][0], 'double_list_test')
        self.assertEqual(difference[1][1][1], 0)
        self.assertEqual(difference[1][1][2], 0)
        self.assertEqual(difference[1][1][3], 'location')
        self.assertEqual(difference[1][2][0], 'juno://%s' % self.file6.path)
        self.assertEqual(difference[1][2][1], 'bid://%s' % str(self.file6.id))

        self.assertEqual(difference[2][0], 'change')
        self.assertEqual(difference[2][1][0], 'double_nested_port_list')
        self.assertEqual(difference[2][1][1], 0)
        self.assertEqual(difference[2][1][2], 'nested_port_list_1')
        self.assertEqual(difference[2][1][3], 0)
        self.assertEqual(difference[2][1][4], 'bait_intervals_1')
        self.assertEqual(difference[2][1][5], 'location')
        self.assertEqual(difference[2][2][0], 'juno://%s' % self.file10.path)
        self.assertEqual(difference[2][2][1], 'bid://%s' % self.file10.id)

        self.assertEqual(difference[3][0], 'change')
        self.assertEqual(difference[3][1][0], 'double_nested_port_list')
        self.assertEqual(difference[3][1][1], 0)
        self.assertEqual(difference[3][1][2], 'nested_port_list_1')
        self.assertEqual(difference[3][1][3], 0)
        self.assertEqual(difference[3][1][4], 'bait_intervals_2')
        self.assertEqual(difference[3][1][5], 'location')
        self.assertEqual(difference[3][2][0], 'juno://%s' % self.file10.path)
        self.assertEqual(difference[3][2][1], 'bid://%s' % self.file10.id)