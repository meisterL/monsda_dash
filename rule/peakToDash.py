rule themall:
    input:  "TABLES/{scombo}/peakTable.csv",
            "TABLES/{scombo}/peakTable_DF.pkl"

rule PeakToDash:
    input:  peak = "PEAKS/{combo}/{file}_peak_sorted_unique_dedup.bed.gz",
            anno = ANNO,
            fasta = REFERENCE
    output: odir = "TABLES/{scombo}",
            csv = "TABLES/{scombo}/peakTable.csv",
            pkl = "TABLES/{scombo}/peakTable_DF.pkl"
    log:    "LOGS/PEAKS/{combo}/PeakToDash.log"
    conda:  "dash_table.yaml"
    threads: 1
    params: bins = BINS,
            filterl = lambda wildcards: tool_params(wildcards.file, None, config, "PEAKS", PEAKENV)['OPTIONS'].get('FILTERLIMIT', ""),
            foldl = lambda wildcards: tool_params(wildcards.file, None, config, "PEAKS", PEAKENV)['OPTIONS'].get('FOLDLIMIT', ""),
            trackid = lambda wildcards: tool_params(wildcards.file, None, config, "PEAKS", PEAKENV)['OPTIONS'].get('TRACKID', ""),
            hub = lambda wildcards: tool_params(wildcards.file, None, config, "PEAKS", PEAKENV)['OPTIONS'].get('HUB', "")
    shell:  "python3 {params.bins}/scyphy_to_table.py -d {input.peak} -a {input.anno} -f {input.fasta} -m {params.filterl} -r {params.foldl} -t {params.trackid} -u {params.hub} -o {output.odir} 2>> {log}"
