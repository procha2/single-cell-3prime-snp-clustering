#!/usr/bin/env python
#
# Copyright (c) 2015 10X Genomics, Inc. All rights reserved.
#

SNP_REF_BASE_TYPE = 'ref'
SNP_ALT_BASE_TYPE = 'alt'
SNP_BASE_TYPES = [SNP_REF_BASE_TYPE, SNP_ALT_BASE_TYPE]
HOM_REF_ALLELE = '0|0'
HET_ALLELE = '1|0'
HOM_ALT_ALLELE = '1|1'
ALLELES = [HOM_REF_ALLELE, HET_ALLELE, HOM_ALT_ALLELE]
DEFAULT_MIN_SNP_CALL_QUAL = 50
DEFAULT_MIN_BCS_PER_SNP = 2
DEFAULT_MIN_SNP_OBS = 10
DEFAULT_BASE_ERROR_RATE = 1e-3
DEFAULT_MIN_SNP_BASE_QUAL = 20
REGION_SPLIT_SIZE = 5 * 10 ** 7