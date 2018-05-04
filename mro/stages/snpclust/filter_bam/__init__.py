#!/usr/bin/env python
#
# Copyright (c) 2016 10X Genomics, Inc. All rights reserved.
#
import martian
import subprocess
import shutil
import collections
import itertools
import tenkit.bam as tk_bam
import cellranger.utils as cr_utils
import snpclust.constants as snp_constants
import fidlib.fidlib.intervals as fl_intervals
import os

__MRO__ = '''
stage FILTER_BAM(
    in  bam       input,
    in  path      reference_path,
    in  path      bed_file,
    in  tsv       cell_barcodes,
    out bam[]     output_bams, 
    out string[]  loci,
    src py     "stages/snpclust/filter_bam",
) split (
    in  string locus,
    in path    genome_fasta,
    out bam    output,
)
'''

def split(args):
    # bring in genome fasta and index it -- cellranger references have no fasta index or dict file
    genome_fasta_path = cr_utils.get_reference_genome_fasta(args.reference_path)
    local_path = martian.make_path('genome.fa')
    try:
        os.symlink(genome_fasta_path, local_path)
    except OSError:
        shutil.copy(genome_fasta_path, local_path)
    subprocess.check_call(['samtools', 'faidx', local_path])
    with open(local_path.replace('.fa', '.dict'), 'w') as outf:
        subprocess.check_call(['samtools', 'dict', local_path], stdout=outf)

    if args.bed_file is not None:
        loci = open(args.bed_file).readlines()
    else:
        # split up the genome, but only into exonic chunks.
        ref_gtf = cr_utils.get_reference_genes_gtf(args.reference_path)
        exons = find_exon_loci(ref_gtf)
        loci = build_loci(exons, snp_constants.REGION_SPLIT_SIZE)
    chunks = [{'locus': locus, 'genome_fasta': local_path, '__mem_gb': 16} for locus in loci]
    return {'chunks': chunks}


def main(args, outs):

    in_bam = tk_bam.create_bam_infile(args.input)
    out_bam, _ = tk_bam.create_bam_outfile(outs.output, None, None, template=in_bam)

    cell_bcs = set(cr_utils.load_barcode_tsv(args.cell_barcodes))
    loci = [x.split() for x in args.locus.split('\n')]
    for chrom, start, stop in loci:
        bam_iter = in_bam.fetch(chrom, int(start), int(stop), multiple_iterators=True)
        for (tid, pos), reads_iter in itertools.groupby(bam_iter, key=cr_utils.pos_sort_key):
            dupe_keys = set()
            for read in reads_iter:
                if cr_utils.get_read_barcode(read) not in cell_bcs:
                    continue

                if cr_utils.is_read_dupe_candidate(read, cr_utils.get_high_conf_mapq({'high_conf_mapq': 255})):
                    dupe_key = (cr_utils.si_pcr_dupe_func(read), cr_utils.get_read_umi(read))
                    if dupe_key in dupe_keys:
                        continue

                    dupe_keys.add(dupe_key)
                    read.is_duplicate = False
                    out_bam.write(read)

    out_bam.close()
    tk_bam.index(outs.output)


def join(args, outs, chunk_defs, chunk_outs):
    outs.coerce_strings()
    # pass along every BAM produced
    outs.output_bams = [chunk.output for chunk in chunk_outs]
    outs.loci = [chunk_def.locus for chunk_def in chunk_defs]


def find_exon_loci(ref_gtf):
    """
    Extracts exonic regions of a GTF into merged, sorted intervals
    """
    regions = collections.defaultdict(list)
    for l in open(ref_gtf):
        if '\texon\t' in l:
            l = l.split()
            i = fl_intervals.ChromosomeInterval(l[0], int(l[3]), int(l[4]), '.')
            regions[l[0]].append(i)
    merged_regions = {}
    for chrom, region_list in regions.iteritems():
        merged_regions[chrom] = fl_intervals.gap_merge_intervals(region_list, 0)
    # report a flat list
    return [item for sublist in merged_regions.itervalues() for item in sublist]


def build_loci(exons, chunk_size):
    """
    Given a list of intervals, pack bins with as many until chunk_size is exceeded
    :param chunk_size: Number of bases to pack into one bin
    :return: BED-like string
    """
    loci = []
    this_locus = []
    bin_size = 0
    for e in exons:
        this_locus.append(e)
        bin_size += len(e)
        if bin_size >= chunk_size:
            loci.append('\n'.join(['\t'.join(map(str, [e.chromosome, e.start, e.stop])) for e in this_locus]))
            this_locus = []
            bin_size = 0
    return loci