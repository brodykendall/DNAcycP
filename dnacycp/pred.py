import keras
import pandas as pd
import numpy as np
from numpy import array
from Bio import SeqIO

network_final_original = keras.models.load_model("irlstm")
detrend_int_original = 0.029905550181865692
detrend_slope_original = 0.973293125629425
normal_mean_original = -0.18574825868055558
normal_std_original = 0.4879013326394626

network_final_smooth = keras.models.load_model("irlstm_smooth")
detrend_int_smooth = 0.001641373848542571
detrend_slope_smooth = 1.0158132314682007
# Mean and stdev of smoothed C0 for Tiling library:
# (calculated from/on the scale of normalized Cn values)
normal_mean_smooth = -0.011196041799376931
normal_std_smooth = 0.651684644408004

def dnaOneHot(sequence):
    seq_array = array(list(sequence))
    code = {"A": [0], "C": [1], "G": [2], "T": [3], "N": [4],
            "a": [0], "c": [1], "g": [2], "t": [3], "n": [4]}
    onehot_encoded_seq = []
    for char in seq_array:
        onehot_encoded = np.zeros(5)
        onehot_encoded[code[char]] = 1
        onehot_encoded_seq.append(onehot_encoded[0:4])
    return onehot_encoded_seq

def cycle_fasta(inputfile:str, outputbase:str, smooth:bool=True):
    """
    Make predictions for a given FASTA file.

    Parameters
    ----------
    inputfile : str
        The path to the FASTA file to predict.
    outputbase : str
        The base name of the output files.
    smooth : bool, optional
        Whether to use the smoothed model or not. The default is True.
        smooth=True corresponds to DNAcycP2, smooth=False corresponds to DNAcycP

    Notes
    -----
    The output files will be named as `<outputbase>_cycle_<chrom>.txt`, where `<chrom>` is the chromosome ID from the FASTA file.
    """
    genome_file = SeqIO.parse(open(inputfile),'fasta')

    network_final = network_final_smooth if smooth else network_final_original
    detrend_int = detrend_int_smooth if smooth else detrend_int_original
    detrend_slope = detrend_slope_smooth if smooth else detrend_slope_original
    normal_mean = normal_mean_smooth if smooth else normal_mean_original
    normal_std = normal_std_smooth if smooth else normal_std_original

    if smooth:
        print(f"Making smooth predictions (DNAcycP2)\n\n")
    else:
        print(f"Making predictions (DNAcycP)\n\n")

    for fasta in genome_file:
        chrom = fasta.id
        genome_sequence = str(fasta.seq)
        onehot_sequence = dnaOneHot(genome_sequence)
        onehot_sequence = array(onehot_sequence)
        onehot_sequence = onehot_sequence.reshape((onehot_sequence.shape[0],4,1))
        print("sequence length: "+chrom+" "+str(onehot_sequence.shape[0]))
        fit = []
        fit_reverse = []
        for ind_local in np.array_split(range(25, onehot_sequence.shape[0]-24), 100):
            onehot_sequence_local = []
            for i in ind_local:
                s = onehot_sequence[(i-25):(i+25),]
                onehot_sequence_local.append(s)
            onehot_sequence_local = array(onehot_sequence_local)
            onehot_sequence_local = onehot_sequence_local.reshape((onehot_sequence_local.shape[0],50,4,1))
            onehot_sequence_local_reverse = np.flip(onehot_sequence_local,[1,2])
            fit_local = network_final.predict(onehot_sequence_local)
            fit_local = fit_local.reshape((fit_local.shape[0]))
            fit.append(fit_local)
            fit_local_reverse = network_final.predict(onehot_sequence_local_reverse)
            fit_local_reverse = fit_local_reverse.reshape((fit_local_reverse.shape[0]))
            fit_reverse.append(fit_local_reverse)
        fit = [item for sublist in fit for item in sublist]
        fit = array(fit)
        fit_reverse = [item for sublist in fit_reverse for item in sublist]
        fit_reverse = array(fit_reverse)
        fit = detrend_int + (fit + fit_reverse) * detrend_slope/2
        fit2 = fit * normal_std + normal_mean
        n = fit.shape[0]
        fitall = np.vstack((range(25,25+n),fit,fit2))
        fitall = pd.DataFrame([*zip(*fitall)])
        fitall.columns = ["posision","c_score_norm","c_score_unnorm"]
        fitall = fitall.astype({"posision": int})
        fitall.to_csv(outputbase+"_cycle_"+chrom+".txt", index = False)
        print("Output file: "+outputbase+"_cycle_"+chrom+".txt")

def cycle_txt(inputfile:str, outputbase:str, smooth:bool=True):
    """
    Make predictions for a given TXT file.

    Parameters
    ----------
    inputfile : str
        The path to the TXT file to predict.
    outputbase : str
        The base name of the output files.
    smooth : bool, optional
        Whether to use the smoothed model or not. The default is True.
        smooth=True corresponds to DNAcycP2, smooth=False corresponds to DNAcycP

    Notes
    -----
    The output files will be named as `<outputbase>_cycle_norm.txt` and `<outputbase>_cycle_unnorm.txt`, where `<outputbase>` is the base name given as an argument.
    """
    network_final = network_final_smooth if smooth else network_final_original
    detrend_int = detrend_int_smooth if smooth else detrend_int_original
    detrend_slope = detrend_slope_smooth if smooth else detrend_slope_original
    normal_mean = normal_mean_smooth if smooth else normal_mean_original
    normal_std = normal_std_smooth if smooth else normal_std_original

    if smooth:
        print(f"Making smooth predictions (DNAcycP2)\n\n")
    else:
        print(f"Making predictions (DNAcycP)\n\n")

    with open(inputfile) as f:
            input_sequence = f.readlines()
    X = []
    all50 = True
    print("Reading sequences...")
    for loop_sequence in input_sequence:
        loop_sequence = loop_sequence.rstrip()
        if len(loop_sequence) != 50:
            all50=False
        X.append(dnaOneHot(loop_sequence))
    if all50:
        print("Predicting cyclizability...")
        X = array(X)
        X = X.reshape((X.shape[0],50,4,1))
        X_reverse = np.flip(X,[1,2])

        model_pred = network_final.predict(X)
        model_pred_reverse = network_final.predict(X_reverse)

        model_pred = detrend_int + (model_pred + model_pred_reverse) * detrend_slope/2
        output_cycle = model_pred.flatten()
        output_cycle2 = np.array([item * normal_std + normal_mean for item in output_cycle])
        output_cycle = list(output_cycle)
        output_cycle2 = list(output_cycle2)
    else:
        print("Not all sequences are length 50, predicting every subsequence...")
        output_cycle = []
        lenX = len(X)
        for j, onehot_loop in enumerate(X):
            l = len(onehot_loop)
            onehot_loop = array(onehot_loop)
            onehot_loop = onehot_loop.reshape((l,4,1))
            onehot_loops = []
            for i in range(l-49):
                onehot_loops.append(onehot_loop[i:i+50])
            onehot_loops = array(onehot_loops)
            onehot_loops_reverse = np.flip(onehot_loops,[1,2])
            if l > 1000:
                # Provide status bar for long sequences:
                cycle_local = network_final.predict(onehot_loops)
                cycle_local_reverse = network_final.predict(onehot_loops_reverse)
            else:
                # No status bar for short sequences (verbose=0):
                cycle_local = network_final.predict(onehot_loops, verbose=0)
                cycle_local_reverse = network_final.predict(onehot_loops_reverse, verbose=0)
            cycle_local = detrend_int + (cycle_local + cycle_local_reverse) * detrend_slope/2
            cycle_local = cycle_local.reshape(cycle_local.shape[0])
            output_cycle.append(cycle_local)
            if j%10==9:
                print(f"Completed {j+1} out of {lenX} total sequences")
        output_cycle2 = [item * normal_std + normal_mean for item in output_cycle]
    with open(outputbase+"_cycle_norm.txt", "w") as file:
        for row in output_cycle:
            if isinstance(row, (np.floating, float)):
                s = str(row)
            else:
                s = " ".join(map(str, row))
            file.write(s+'\n')
    with open(outputbase+"_cycle_unnorm.txt", "w") as file:
        for row in output_cycle2:
            if isinstance(row, (np.floating, float)):
                s = str(row)
            else:
                s = " ".join(map(str, row))
            file.write(s+'\n')
