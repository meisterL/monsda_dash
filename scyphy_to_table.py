#!/usr/bin/python

from heapq import merge
import logging
import sys
import os
from zipapp import create_archive
import pandas as pd
import pybedtools
import pickle
import datetime
import warnings
import time
import RNA
import argparse


def parse_args():
    parser = argparse.ArgumentParser(description="create table")
    parser.add_argument("-d", "--fls_dir", action="store")
    parser.add_argument("-a", "--anno_fl", action="store")
    parser.add_argument("-f", "--fasta_fl", action="store")
    parser.add_argument("-m", "--max_filter", action="store", type=int)
    parser.add_argument("-r", "--rna_limit", default=30, action="store", type=int)
    parser.add_argument("-p", "--pkl_fl", action="store")
    parser.add_argument(
        "-t",
        "--track_id",
        default="289039575_YBfPH3PcZLRQ4IcjY242DYci9ggv",
        action="store",
    )
    parser.add_argument("-u", "--hub", default="hub_393513_genome", action="store")
    parser.add_argument("-l", "--loglevel", default="warning", action="store")

    args = parser.parse_args()
    return args


def logger(fn):
    def inner(*args, **kwargs):
        print(f"{fn.__name__} ", end="\r")
        start = time.time()
        to_execute = fn(*args, **kwargs)
        print(
            f"{fn.__name__} -- executed in {time.strftime('%H:%M:%S', time.gmtime(time.time() - start))}"
        )
        return to_execute

    return inner


CN = [
    "chr",
    "peak_merge_start",
    "peak_merge_end",
    "peak_all_start",
    "peak_all_end",
    "peak_profile_all",
    "score_min",
    "score_max",
    "score_mean",
    "score_stdev",
    "peak_strand",
    "pv_min",
    "pv_max",
    "pv_mean",
    "pv_stdev",
    "prot",
    "prot_hits",
    "cond",
    "cond_hits",
    "date",
    "date_hits",
    "feat_start",
    "feat_end",
    "feat_name",
    "feat_strand",
    "filter_min",
    "filter_max",
    "peak_seq",
    "feat_seq",
    "sec_structure",
    "minimum_free_energy",
    "hits_total",
    "filter_levels",
]

CL = [
    [2, "distinct"],  # peak_all_start
    [3, "distinct"],  # peak_all_end
    [4, "distinct"],  # peak_profile_all
    [5, "min"],  # score_min
    [5, "max"],  # score_max
    [5, "mean"],  # score_mean
    [5, "stdev"],  # score_stdev
    [6, "distinct"],  # peak_strand
    [7, "min"],  # pv_min
    [7, "max"],  # pv_max
    [7, "mean"],  # pv_mean
    [7, "stdev"],  # pv_stdev
    [8, "distinct"],  # prot
    [8, "count_distinct"],  # prot_hits
    [9, "distinct"],  # cond
    [9, "count_distinct"],  # cond_hits
    [10, "distinct"],  # date
    [10, "count_distinct"],  # date_hits
    [12, "distinct"],  # feat_start
    [13, "distinct"],  # feat_end
    [14, "distinct"],  # feat_name
    [16, "distinct"],  # feat_strand
    [17, "min"],  # filter_min
    [17, "max"],  # filter_max
    [18, "distinct"],  # peak_seq
    [19, "distinct"],  # feat_seq
    [20, "distinct"],  # sec_structure
    [21, "distinct"],  # mfe
    [1, "count"],  # hits_total
]

c_list = []
o_list = []
for cl in CL:
    c_list.append(cl[0])
    o_list.append(cl[1])


@logger
def replace_comma_with_newlines(df):
    c = [
        "peak_all_start",
        "peak_all_end",
        "peak_strand",
        "feat_start",
        "feat_end",
        "feat_name",
        "feat_strand",
        "peak_seq",
        "feat_seq",
        "sec_structure",
        "minimum_free_energy",
        "links",
    ]
    df[c] = df[c].replace(",", "\n", regex=True)


@logger
def rearrange_columns(df):
    print(df.keys())
    print(df.iloc[0])
    df = df[
        [
            "filter_levels",
            "chr",
            "peak_merge_start",
            "peak_merge_end",
            "links",
            "peak_strand",
            "score_min",
            "score_max",
            "score_mean",
            "score_stdev",
            "pv_min",
            "pv_max",
            "pv_mean",
            "pv_stdev",
            "hits_total",
            "prot",
            "prot_hits",
            "cond",
            "cond_hits",
            "date",
            "date_hits",
            "peak_all_start",
            "peak_all_end",
            "feat_start",
            "feat_end",
            "feat_name",
            "feat_strand",
            "peak_seq",
            "feat_seq",
            "sec_structure",
            "minimum_free_energy",
            "filter_min",
            "filter_max",
            "peak_profile_all",
        ]
    ]
    return df


def len_filter(feature, L):
    return len(feature) <= L


def lower_peak(pstart, pend, fstart, fseq):
    fseq_list = list(fseq)
    lstart = int(pstart) - int(fstart)
    lend = int(pend) - int(fstart)
    if pstart < fstart:
        fseq_edit = "<-" + fseq
    if pend > fstart + len(fseq):
        fseq_edit = fseq + "->"
    else:
        for i in range(lstart, lend):
            fseq_list[i] = fseq_list[i].lower()
        fseq_edit = "".join(fseq_list)
    return fseq_edit


@logger
def get_seqs(fasta, coordinates, limit):
    seqs = coordinates.sequence(fi=fasta)
    seqs = [x.strip() for x in open(seqs.seqfn).readlines()]
    seqs = pd.Series(seqs[1::2])
    seqs = seqs.apply(lambda x: "NA" if len(x) > limit else x)
    return seqs


@logger
def prepare_peak_file(fl, fls_dir, peak_fls):
    logging.debug(f"peak file: {fl} / {peak_fls.index(fl)+1} of {len(peak_fls)}")
    f = pybedtools.BedTool(os.path.join(fls_dir, fl))
    df1 = f.to_dataframe(header=None)
    df1["prtcl"] = fl.split("_")[0].split("-")[0]
    df1["cndtn"] = fl.split("_")[0].split("-")[1]
    df1["date"] = fl.split("_")[0].split("-")[2]
    f_cond = pybedtools.BedTool.from_dataframe(df1)
    return f_cond.sort()


@logger
def create_intersect_df(tbl, filt, fasta, rna_limit):
    logging.debug(f"create intersect df:")
    df = tbl.to_dataframe(header=None)
    df["filter"] = filt
    df["pseq"] = get_seqs(fasta, tbl, rna_limit)
    df["fseq"] = get_seqs(
        fasta, pybedtools.BedTool.cut(tbl, [10, 11, 12], stream=False), rna_limit
    )
    df["ss"] = "NA"
    df["mfe"] = "NA"
    return df.reset_index(drop=True)


@logger
def add_rna_structures(df):
    logging.debug(f"add RNA structures to df:")
    for index, row in df.iterrows():
        if row["fseq"] == "NA":
            continue
        row = row.copy()
        seq = row["fseq"]
        df.loc[index, "fseq"] = lower_peak(row[1], row[2], row[11], row["fseq"])
        (ss, mfe) = RNA.fold(seq.replace("U", "T"))
        df.loc[index, "ss"] = str(ss)
        df.loc[index, "mfe"] = str(mfe)


@logger
def remove_duplicates(merge_list):
    logging.debug(f"mark duplicates from merge list")
    DF = pd.concat([df for df in merge_list])
    DF = DF.reset_index()
    DF = DF.drop(["index"], axis=1)
    chroms = list(DF[0].unique())
    for chrom in chroms:
        chrom_select = DF.loc[(DF[0] == chrom)]
        logging.debug(f"chromosome {chrom} / {chroms.index(chrom)+1} of {len(chroms)}")
        for start in chrom_select[1].unique():
            start_select = chrom_select.loc[(DF[1] == start)]
            for end in start_select[2].unique():
                a = min(start_select.loc[(start_select[2] == end)][25])
                b = max(start_select.loc[(start_select[2] == end)][26])
                c = ",".join([str(fi) for fi in range(a, (b + 1))])
                DF.loc[(DF[1] == start) & (DF[2] == end), 25] = a
                DF.loc[(DF[1] == start) & (DF[2] == end), 26] = b
                # add filter_level column
                DF.loc[(DF[1] == start) & (DF[2] == end), 32] = c
    logging.debug("drop duplicates and return")
    DF = DF.drop_duplicates(subset=[1, 2], keep="first")
    return DF


@logger
def merge_peak_files(max_filter, fls_dir, anno_fl, fasta_fl, rna_limit):
    peak_fls = os.listdir(fls_dir)
    width_filter = [i + 1 for i in range(max_filter)]
    logging.debug("merge_peak_files")
    anno = pybedtools.BedTool(anno_fl)
    fasta = pybedtools.example_filename(fasta_fl)
    merge_list = []
    for filt in width_filter:
        logging.debug(f"filter level: {filt} of {len(width_filter)}")
        filt_list = []
        for fl in peak_fls:
            f_cond_sorted = prepare_peak_file(fl, fls_dir, peak_fls)
            f_cond_sorted_intersect = f_cond_sorted.intersect(
                anno, wb=True, wa=True, s=False
            )
            f_cond_sorted_intersect_sorted = f_cond_sorted_intersect.sort()
            x = f_cond_sorted_intersect_sorted.filter(len_filter, L=filt)
            f_cond_sorted_intersect_sorted_filterWidth = x.saveas()
            df = create_intersect_df(
                f_cond_sorted_intersect_sorted_filterWidth, filt, fasta, rna_limit
            )
            add_rna_structures(df)
            logging.debug(f"add intersected file to list")
            f_cond_sorted_intersect_sorted_filterWidth_filt = (
                pybedtools.BedTool.from_dataframe(df)
            )
            f_cond_sorted_intersect_sorted_filterWidth_filt_sorted = (
                f_cond_sorted_intersect_sorted_filterWidth_filt.sort()
            )
            filt_list.append(f_cond_sorted_intersect_sorted_filterWidth_filt_sorted)

        logging.debug(f"merge filter list on level {filt}")
        f_01_cat = filt_list[0].cat(*filt_list[1:], s=True, d=-1, c=c_list, o=o_list)
        df = f_01_cat.to_dataframe()
        df.columns = [i for i in range(len(CL) + 3)]
        df = df.sort_values(by=[len(CL) + 2], ascending=False)
        logging.debug(f"add merged peaks to merge list")
        merge_list.append(df)
    DF = remove_duplicates(merge_list)
    return DF


@logger
def set_column_names(df):
    df.set_axis(CN, axis=1, inplace=True)


@logger
def print_pkl_tsv_file(df, out_dir):
    os.mkdir(out_dir)
    print("print pkl and tsv")
    file = open(os.path.join(out_dir, "DF_fin.pkl"), "wb")
    pickle.dump(df, file)
    file.close()
    df.to_csv(os.path.join(out_dir, "DF_fin.tsv"), sep=",")


@logger
def load_data_from_pkl(pkl_fl):
    file = open(pkl_fl, "rb")
    df = pickle.load(file)
    file.close()
    df.to_csv("DF_fin.tsv", sep="\t", line_terminator="\n")
    return df


def create_url(hub, trackid, chr, start, end):
    links = []
    for (
        s,
        e,
    ) in zip(str(start).split(","), str(end).split(",")):
        links.append(
            f"[UCSC Track Hub](https://genome-euro.ucsc.edu/cgi-bin/hgTracks?db={hub}&lastVirtModeType=default&lastVirtModeExtraState=&virtModeType=default&virtMode=0&nonVirtPosition=&position={chr}%3A{int(s)-15}%2D{int(e)+15}&hgsid={trackid})"
        )
    return ",".join(links)


@logger
def add_hublinks(df, hub, track_id):
    df["links"] = ""
    for index, row in df.iterrows():
        df.loc[index, "links"] = create_url(hub, track_id, row[0], row[21], row[22])


def main():
    start = time.time()
    now = datetime.datetime.now()
    directory = os.getcwd()
    print("\nSTART create TSV table\n")
    args = parse_args()
    warnings.filterwarnings("ignore")
    logging.basicConfig(level=args.loglevel.upper())
    pd.set_option("display.max_columns", 40)

    out_dir = f"{now.strftime('%Y-%m-%d_%H-%M')}_{args.anno_fl.split('.')[0]}_flt{args.max_filter}"

    if args.pkl_fl:
        print(f"Load data from pkl file: {os.path.join(directory,args.pkl_fl)}")
        DF = load_data_from_pkl(os.path.join(directory, args.pkl_fl))
    else:
        print(f"Read peak files:")
        print("\n".join(x for x in os.listdir(os.path.join(directory, args.fls_dir))))
        DF = merge_peak_files(
            args.max_filter,
            os.path.join(directory, args.fls_dir),
            os.path.join(directory, args.anno_fl),
            os.path.join(directory, args.fasta_fl),
            args.rna_limit,
        )
    set_column_names(DF)
    add_hublinks(DF, args.hub, args.track_id)
    replace_comma_with_newlines(DF)
    DF = rearrange_columns(DF)
    print_pkl_tsv_file(DF, out_dir)

    print(
        f"\nFINISHED in {time.strftime('%H:%M:%S', time.gmtime(time.time() - start))}\n"
    )


if __name__ == "__main__":
    main()
