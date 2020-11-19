import argparse
import csv
import os
import re
from multiprocessing import Pool
import subprocess
import sys
import numpy as np
import pandas as pd
from Bio import SeqIO
#from Bio.Alphabet import IUPAC
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

parser = argparse.ArgumentParser()
parser.add_argument("-p",
                    help="Output prefix")
parser.add_argument("-hla_type",
                    help="HLA type file generated by optitype")
parser.add_argument("-var_info",
                    help="Variant information tsv format file")
parser.add_argument("-var_db",
                    help="Variant database file")
parser.add_argument("-o",
                    help="Output folder")
parser.add_argument("-netmhcpan",
                    help="NetMHCpan path")

args = parser.parse_args()

sample_id = args.p
allele_file = args.hla_type
AA_form_file = args.var_info
protein_file = args.var_db
save_path = args.o
netMHCpan = args.netmhcpan

if save_path[-1] != '/':
    save_path = save_path + '/'

os.system('mkdir ' + save_path + 'tmp')
# extract HLA typing information

alleles = []
with open(allele_file) as csvfile:
    spamreader = csv.reader(csvfile, delimiter='\t')
    for row in spamreader:
        alleles.append(row)
alleles = np.array(alleles)

HLA_types = []
for HLA in alleles[1, 1:-2]:
    HLA_types.append(HLA.replace('*', ':').split(':'))
for line in HLA_types:
    line[0] = 'HLA-' + line[0]

# extract somatic mutation information
protein_data = list(SeqIO.parse(protein_file, 'fasta'))
ids = []
for record in protein_data:
    ids.append(record.id)

long_AA_sequence_list = []

with open(AA_form_file) as csvfile2:
    spamreader = csv.reader(csvfile2, delimiter='\t')
    with open(save_path + 'tmp/somatic_mutation_reference.csv', "a") as csvfile1:
        writer = csv.writer(csvfile1, delimiter=',')

        for row in spamreader:
            #print("Each row: ", row, "\n")
            AA = np.delete(np.array(row).reshape(1, len(row)), [10, 11, 12], 1)
            #print("After deleting: ", AA, "\n")

            if AA[0, 0] == 'Variant_ID':
                colnames = np.hstack((AA[0, :10],
                                      ['Neoepitope', 'Variant_Start', 'Variant_End',
                                       'AA_before', 'AA_after']))
                writer.writerow(colnames)

            else:
                AA_change = []
                a, (b, c, d) = AA[0, :10], AA[0, 10:13]
                Variant_info = a
                AA_Ref = b
                AA_Pos = c
                AA_Var = d
                Variant_Type = Variant_info[6]

                if Variant_Type == "frameshift insertion":
                    # AA_Var has * suffix sometime
                    AA_Var = re.sub(r'\W+', '', AA_Var)

                    if "-" in AA_Pos:
                        start_position = int(AA_Pos.split('-')[0])
                        end_position = start_position + len(AA_Var) - 1
                    else:
                        start_position = int(AA_Pos)
                        end_position = start_position + len(AA_Var) - 1
                elif Variant_Type == "frameshift substitution":
                    # AA_Var has * suffix sometime

                    if "-" in AA_Pos:
                        start_position = int(AA_Pos.split('-')[0])
                        end_position = start_position + len(AA_Var) - 1
                    else:
                        start_position = int(AA_Pos)
                        end_position = start_position + len(AA_Var) - 1
                    
                elif Variant_Type == "frameshift deletion":
                    if AA_Var == "-":
                        continue
                    elif AA_Var == "*":
                        continue
                    else:
                        if "-" in AA_Pos:
                            start_position = int(AA_Pos.split('-')[0])
                            end_position = start_position + len(AA_Var) - 1
                        else:
                            start_position = int(AA_Pos)
                            end_position = start_position + len(AA_Var) - 1
                elif Variant_Type == "stoploss":
                    start_position = int(AA_Pos)

                    # AA_Var has * suffix sometime
                    AA_Var = re.sub(r'\W+', '', AA_Var)

                    end_position = int(AA_Pos) + len(AA_Var) - 1
                elif Variant_Type == "nonsynonymous SNV":
                    if "-" in AA_Pos:
                        continue
                    else:
                        start_position = int(AA_Pos)
                        end_position = int(AA_Pos)
                elif Variant_Type == "nonframeshift insertion":
                    if "-" in AA_Pos:
                        start_position = int(AA_Pos.split('-')[0]) - 1
                        end_position = int(AA_Pos.split('-')[1])
                    else:
                        start_position = int(AA_Pos)
                        end_position = int(AA_Pos)

                elif Variant_Type == "nonframeshift deletion":
                    if "-" in AA_Pos:
                        # Last AA no sense
                        start_position = int(AA_Pos.split('-')[0]) - 1
                        end_position = int(AA_Pos.split('-')[0])
                    else:
                        start_position = int(AA_Pos) - 1
                        end_position = int(AA_Pos)

                elif Variant_Type == "stopgain":
                    continue
                else:
                    start_position = int(AA_Pos)
                    end_position = int(AA_Pos)

                line = np.hstack((np.array(Variant_info).reshape(1, 10),
                                  np.array(AA_Ref).reshape(1, 1),
                                  np.array(start_position).reshape(1, 1),
                                  np.array(end_position).reshape(1, 1),
                                  np.array(AA_Var).reshape(1, 1)
                                  ))

                # print("line is ", line)

                start = int(line[0, 11]) - 1
                end = int(line[0, 12]) - 1
                var_info = line[0, 0:10].reshape(1, 10)
                var_id = var_info[0, 0]
                gap = end - start

                reference_seq = protein_data[ids.index(var_id)]
                cut_start = 0
                cut_end = len(reference_seq)
                if start > 11:
                    cut_start = start - 11

                if end < cut_end - 11:
                    cut_end = end + 11

                long_AA_seq = reference_seq.seq[cut_start:cut_end]
                long_AA_seq = str(long_AA_seq)
                # print("long_AA_seq from db is ", long_AA_seq)
                long_AA_sequence_list.append(long_AA_seq)

                for AA_len in range(8, 12):
                    p_end = 1
                    for ind in range(AA_len + gap):
                        AA_seq = protein_data[ids.index(var_id)].seq[end - ind:end + AA_len - ind]
                        AA_sequence = str(AA_seq)
                        AA_info = var_info
                        AA_id = str(var_id)
                        if p_end > AA_len:
                            p2 = AA_len
                            position_end = p2
                        else:
                            p2 = p_end
                            position_end = p2
                        if p_end - gap < 1:
                            p1 = 1
                            position = p1
                        else:
                            p1 = p_end - gap
                            position = p1
                        p_end = p_end + 1
                        AA_change = []
                        AA_change.append(line[0, 10])
                        AA_change.append(str(AA_seq)[p1 - 1:p2])

                        output_line = np.hstack((np.array(AA_info).reshape(1, 10),
                                                 np.array(AA_sequence).reshape(1, 1),
                                                 np.array(position).reshape(1, 1),
                                                 np.array(position_end).reshape(1, 1),
                                                 np.array(AA_change).reshape(1, 2)))
                        # print("Output line is ", output_line)

                        if int(len(output_line[0, 10])) == AA_len:
                            writer.writerow(output_line.reshape(output_line.shape[1], ))

records = []
for seq in set(long_AA_sequence_list):
    if seq != '':
        #records.append(SeqRecord(Seq(seq, IUPAC.protein)))
        records.append(SeqRecord(Seq(seq)))
fasta_file = save_path + 'tmp/neoantigen_candidates.fasta'
SeqIO.write(records, fasta_file, "fasta")


# netMHCpan for neoantigen binding affinity prediction

def typing(line,netMHCpan,out_dir):
    HLA_type_long = str(line[0]) + str(line[1]) + ':' + str(line[2])
    HLA_type_short = str(line[0]) + str(line[1]) + str(line[2])
    
    netMHCpan_argument = []
    a1 = '-f ' + fasta_file
    a2 = '-a ' + HLA_type_long
    a3 = '-l 8,9,10,11'
    a4 = '>' + out_dir + 'tmp/' + HLA_type_short + "_netMHCpan.csv"
    netMHCpan_argument.extend((netMHCpan, a1, a2, a3, '-BA', a4))
    cmd = ' '.join(netMHCpan_argument)
    try:
        rv = subprocess.run([cmd],shell=True,stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True)
    except subprocess.CalledProcessError as sub_error:
        print("netMHCpan error: %s" % (sub_error.stdout.decode('utf-8')),file=sys.stderr)
        sys.exit(1)
    #os.system(' '.join(netMHCpan_argument))


#pool = Pool(n)
#pool.map(typing, HLA_types)
#pool.close()
for hla in HLA_types:
    typing(hla,netMHCpan,save_path)

# combine netMHCpan result
typing_files = []
for x in os.listdir(save_path + 'tmp/'):
    if 'netMHCpan' in x: typing_files.append(x)

save_name = save_path + 'tmp/netMHCpan_binding_result.csv'

for raw_path in typing_files:
    HLA_type = raw_path.split('_')[0]
    HLA_type = HLA_type[:5] + '*' + HLA_type[5:7] + ':' + HLA_type[7:]
    raw_data = []
    with open(save_path + 'tmp/' + raw_path) as csvfile3:
        spamreader = csv.reader(csvfile3, delimiter=' ')
        for row in spamreader:
            filtered = []
            for item in row:
                if item != '':
                    filtered.append(item)
            if filtered != [] and len(filtered) > 1:
                if filtered[1].startswith("HLA-"):
                    seq = [HLA_type, filtered[2], filtered[12], filtered[13]]
                    # save_name = save_path + 'tmp/netMHCpan_binding_result.csv'
                    with open(save_name, "a") as csvfile4:
                        writer = csv.writer(csvfile4, delimiter=',')
                        writer.writerow(seq)

# Make Master Matrix
if (len(records) != 0):
    binding_result = pd.read_csv(save_name,
                             header=None,
                             names=['HLA_type',
                                    'Neoepitope',
                                    'netMHCpan_binding_affinity_nM',
                                    'netMHCpan_precentail_rank'], low_memory=False)
    somatic_mutation = pd.read_csv(save_path + 'tmp/somatic_mutation_reference.csv', low_memory=False)
    master_matrix = pd.merge(somatic_mutation, binding_result, on='Neoepitope')
    master_matrix.to_csv(save_path + sample_id + '_binding_prediction_result.csv', index=False)

# clean up
os.system('rm -r ' + save_path + 'tmp/')

