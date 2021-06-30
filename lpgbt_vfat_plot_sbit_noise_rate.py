from rw_reg_lpgbt import *
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib import cm
import numpy as np
import os, sys, glob
import argparse

if __name__ == '__main__':

    # Parsing arguments
    parser = argparse.ArgumentParser(description='Plotting VFAT Sbit Noise Rate')
    parser.add_argument("-f", "--filename", action="store", dest="filename", help="Noise rate result filename")
    args = parser.parse_args()

    plot_filename_prefix = args.filename.split(".txt")[0]
    file = open(args.filename)
    noise_result = {}
    time = 0
    for line in file.readlines():
        if "vfat" in line:
            continue
        vfat = int(line.split()[0])
        elink = int(line.split()[1])
        thr = int(line.split()[2])
        fired = int(line.split()[3])
        time = float(line.split()[4])
        if vfat not in noise_result:
            noise_result[vfat] = {}
        if elink not in noise_result[vfat]:
            noise_result[vfat][elink] = {}
        if fired == -9999:
            noise_result[vfat][elink][thr] = 0
        else:
            noise_result[vfat][elink][thr] = fired
    file.close()

    for vfat in noise_result:
        threshold = []
        noise_rate = []

        for elink in noise_result[vfat]:
            for thr in noise_result[vfat][elink]:
                threshold.append(thr)
                noise_rate.append(0)
            break
        for elink in noise_result[vfat]:
            for i in range(0,len(threshold)):
                thr = threshold[i]
                noise_rate[i] += noise_result[vfat][elink][thr]/time

        fig, ax = plt.subplots()
        plt.xlabel('Threshold (DAC)')
        plt.ylabel('SBit Rate (Hz)')
        plt.yscale('log')
        ax.plot(threshold, noise_rate, 'o')
        #leg = ax.legend(loc='center right', ncol=2)
        plt.title("VFAT# %02d"%vfat)
        plt.savefig((plot_filename_prefix+"_VFAT%02d.pdf")%vfat)










